"""
Disclaimer

All investment strategies and investments involve risk of loss.
Nothing contained in this program, scripts, code or repositoy should be
construed as investment advice.Any reference to an investment's past or
potential performance is not, and should not be construed as, a recommendation
or as a guarantee of any specific outcome or profit.

By using this program you accept all liabilities,
and that no claims can be made against the developers,
or others connected with the program.
"""


# use for environment variables
from genericpath import exists
import os
from rsi_signalmod_nigec import FULL_LOG

# use if needed to pass args to external modules
import sys

# used to create threads & dynamic loading of modules
import threading
import importlib

# used for directory handling
import glob

#gogo MOD telegram needs import request
import requests

# Needed for colorful console output Install with: python3 -m pip install colorama (Mac/Linux) or pip install colorama (PC)
from colorama import init
init()

# needed for the binance API / websockets / Exception handling
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ReadTimeout, ConnectionError

# used for dates
from datetime import date, datetime, timedelta
import time

# used to repeatedly execute the code
from itertools import count

# used to store trades and sell assets
import json

# Load helper modules
from helpers.parameters import (
    parse_args, load_config
)

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key,
    load_telegram_creds
)


# for colourful logging to the console
class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DIM = '\033[2m\033[35m'
    DEFAULT = '\033[39m'
    NOTICE = '\033[96m'

global session_struct

session_struct = {
     'session_profit': 0,
     'unrealised_percent': 0,
     'market_price': 0,
     'investment_value': 0,
     'investment_value_gain': 0,
     'session_uptime': 0,
     'session_start_time': 0,
     'closed_trades_percent': 0,
     'win_trade_count': 0,
     'loss_trade_count': 0,
     'market_support': 0,
     'market_resistance': 0,
     'dynamic': 'none',
     'sell_all_coins': False,
     'tickers_list_changed': False,
     'exchange_symbol': 'USDT',
     'price_list_counter': 0,
     'CURRENT_EXPOSURE': 0,
     'TOTAL_GAINS': 0,
     'NEW_BALANCE': 0,
     'INVESTMENT_GAIN': 0,
     'STARTUP': True,
     'LIST_AUTOCREATE': False,
}

# print with timestamps
old_out = sys.stdout
class St_ampe_dOut:
    """Stamped stdout."""
    nl = True
    def write(self, x):
        """Write function overloaded."""
        if x == '\n':
            old_out.write(x)
            self.nl = True
        elif self.nl:
            old_out.write(f'{txcolors.DIM}[{str(datetime.now().replace(microsecond=0))}]{txcolors.DEFAULT} {x}')
            self.nl = False
        else:
            old_out.write(x)

    def flush(self):
        pass

sys.stdout = St_ampe_dOut()

def is_fiat():
    # check if we are using a fiat as a base currency
    global hsp_head
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    #list below is in the order that Binance displays them, apologies for not using ASC order but this is easier to update later
    fiats = ['USDT', 'BUSD', 'AUD', 'BRL', 'EUR', 'GBP', 'RUB', 'TRY', 'TUSD', 'USDC', 'PAX', 'BIDR', 'DAI', 'IDRT', 'UAH', 'NGN', 'VAI', 'BVND']

    if PAIR_WITH in fiats:
        return True
    else:
        return False

def decimals():
    # set number of decimals for reporting fractions
    if is_fiat():
        return 2
    else:
        return 8


def get_price(add_to_historical=True):
    '''Return the current price for all coins on binance'''

    global historical_prices, hsp_head, session_struct

    initial_price = {}
    prices = client.get_all_tickers()

    for coin in prices:
        if CUSTOM_LIST:
            if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}
        else:
            if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}

    if add_to_historical:
        hsp_head += 1

        if hsp_head == RECHECK_INTERVAL:
            hsp_head = 0

        historical_prices[hsp_head] = initial_price

    if is_fiat():

        session_struct['market_price'] = 1
        session_struct['exchange_symbol'] = PAIR_WITH

    else:
        session_struct['exchange_symbol'] = PAIR_WITH + 'USDT'
        market_historic = client.get_historical_trades(symbol=session_struct['exchange_symbol'])
        session_struct['market_price'] = market_historic[0].get('price')

    return initial_price


def wait_for_price(type):
    '''calls the initial price and ensures the correct amount of time has passed
    before reading the current price again'''

    global historical_prices, prehistorical_prices, hsp_head, volatility_cooloff, session_struct

    session_struct['market_resistance'] = 0
    session_struct['market_support'] = 0

    volatile_coins = {}
    externals = {}

    coins_up = 0
    coins_down = 0
    coins_unchanged = 0

    pause_bot()

    if historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'] > datetime.now() - timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)):

        # sleep for exactly the amount of time required
        time.sleep((timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)) - (datetime.now() - historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'])).total_seconds())

    # retrieve latest prices
    get_price()

    # calculate the difference in prices
    for coin in historical_prices[hsp_head]:

        # minimum and maximum prices over time period
        min_price = min(historical_prices, key = lambda x: float("inf") if x is None else float(x[coin]['price']))
        max_price = max(historical_prices, key = lambda x: -1 if x is None else float(x[coin]['price']))

        threshold_check = (-1.0 if min_price[coin]['time'] > max_price[coin]['time'] else 1.0) * (float(max_price[coin]['price']) - float(min_price[coin]['price'])) / float(min_price[coin]['price']) * 100

        if threshold_check > 0:
            session_struct['market_resistance'] = session_struct['market_resistance'] + threshold_check
            coins_up = coins_up +1
        else:
            session_struct['market_support'] = session_struct['market_support'] - threshold_check
            coins_down = coins_down +1

        if type == 'percent_mix_signal':

           # each coin with higher gains than our CHANGE_IN_PRICE is added to the volatile_coins dict if less than TRADE_SLOTS is not reached.
           if threshold_check > CHANGE_IN_PRICE_MIN and threshold_check < CHANGE_IN_PRICE_MAX:
               coins_up +=1

               if os.path.exists('signals/nigec_custsignalmod.exs') or os.path.exists('signals/djcommie_custsignalmod.exs') or os.path.exists('signals/firewatch_signalsample.exs'):
                  externals = external_signals()

                  for excoin in externals:

                      if excoin == coin:

                         if coin not in volatility_cooloff:
                            volatility_cooloff[coin] = datetime.now() - timedelta(minutes=TIME_DIFFERENCE)

                         # only include coin as volatile if it hasn't been picked up in the last TIME_DIFFERENCE minutes already
                         if datetime.now() >= volatility_cooloff[coin] + timedelta(minutes=TIME_DIFFERENCE):
                            volatility_cooloff[coin] = datetime.now()

                            if len(coins_bought) + len(volatile_coins) < TRADE_SLOTS or TRADE_SLOTS == 0:
                               volatile_coins[coin] = round(threshold_check, 3)
                               print(f"{coin} has gained {volatile_coins[coin]}% within the last {TIME_DIFFERENCE} minutes, and coin {excoin} recived a signal... calculating {QUANTITY} {PAIR_WITH} value of {coin} for purchase!")

                            else:
                               print(f"{txcolors.WARNING}{coin} has gained {round(threshold_check, 3)}% within the last {TIME_DIFFERENCE} minutes, , and coin {excoin} recived a signal... but you are using all available trade slots!{txcolors.DEFAULT}")

        if type == 'percent_and_signal':

            # each coin with higher gains than our CHANGE_IN_PRICE is added to the volatile_coins dict if less than TRADE_SLOTS is not reached.
            if threshold_check > CHANGE_IN_PRICE_MIN and threshold_check < CHANGE_IN_PRICE_MAX:
                coins_up +1

                if coin not in volatility_cooloff:
                    volatility_cooloff[coin] = datetime.now() - timedelta(minutes=TIME_DIFFERENCE)

                # only include coin as volatile if it hasn't been picked up in the last TIME_DIFFERENCE minutes already
                if datetime.now() >= volatility_cooloff[coin] + timedelta(minutes=TIME_DIFFERENCE):
                    volatility_cooloff[coin] = datetime.now()

                if len(coins_bought) + len(volatile_coins) < TRADE_SLOTS or TRADE_SLOTS == 0:
                    volatile_coins[coin] = round(threshold_check, 3)
                    print(f"{coin} has gained {volatile_coins[coin]}% within the last {TIME_DIFFERENCE} minutes {QUANTITY} {PAIR_WITH} value of {coin} for purchase!")

                else:
                   print(f"{txcolors.WARNING}{coin} has gained {round(threshold_check, 3)}% within the last {TIME_DIFFERENCE} minutes but you are using all available trade slots!{txcolors.DEFAULT}")

            externals = external_signals()
            exnumber = 0

            for excoin in externals:
                if excoin not in volatile_coins and excoin not in coins_bought and (len(coins_bought) + exnumber) < TRADE_SLOTS:
                    volatile_coins[excoin] = 1
                    exnumber +=1
                    print(f"External signal received on {excoin}, calculating {QUANTITY} {PAIR_WITH} value of {excoin} for purchase!")

        if threshold_check < CHANGE_IN_PRICE_MIN and threshold_check > CHANGE_IN_PRICE_MAX:
             coins_down +=1

        else:
            coins_unchanged +=1

    if coins_up != 0: session_struct['market_resistance'] = session_struct['market_resistance'] / coins_up
    if coins_down != 0: session_struct['market_support'] = session_struct['market_support'] / coins_down

    if DETAILED_REPORTS == True and hsp_head == 1:
        report('detailed',f"Market Resistance:      {txcolors.DEFAULT}{session_struct['market_resistance']:.4f}\n Market Support:         {txcolors.DEFAULT}{session_struct['market_support']:.4f}")
    else:
        report('console', f" MR:{session_struct['market_resistance']:.4f}/MS:{session_struct['market_support']:.4f} ")

    return volatile_coins, len(volatile_coins), historical_prices[hsp_head]


def external_signals():
    external_list = {}
    signals = {}

    # check directory and load pairs from files into external_list
    signals = glob.glob("signals/*.exs")
    for filename in signals:
        for line in open(filename):
            symbol = line.strip()
            external_list[symbol] = symbol
            print(f'>>> SIGNAL DETECTED ON: {symbol} - SIGNALMOD: {filename} <<<<')
        try:
            os.remove(filename)
        except:
            if DEBUG: print(f"{txcolors.WARNING}Could not remove external signalling file{txcolors.DEFAULT}")

    return external_list


def pause_bot():
    '''Pause the script when external indicators detect a bearish trend in the market'''
    global bot_paused, hsp_head
    global LIST_AUTOCREATE
    # start counting for how long the bot has been paused
    start_time = time.perf_counter()

    while os.path.isfile("signals/paused.exc"):

        if bot_paused == False:
            print(f"{txcolors.WARNING}Buying paused due to negative market conditions, stop loss and take profit will continue to work...{txcolors.DEFAULT}")
            # sell all bought coins if bot is bot_paused
            if STOP_LOSS_ON_PAUSE == True:
               session_struct['sell_all_coins'] = True
            bot_paused = True

        # sell all bought coins if bot is bot_paused
        if STOP_LOSS_ON_PAUSE == True:
           session_struct['sell_all_coins'] = True

        # Sell function needs to work even while paused
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)
        get_price(True)

        # pausing here

        #gogo MOD todo more verbose having all the report things in it!!!!!
        if hsp_head == 1:
           report('console', '.')

        time.sleep((TIME_DIFFERENCE * 60) / RECHECK_INTERVAL)

    else:
        # stop counting the pause time
        stop_time = time.perf_counter()
        time_elapsed = timedelta(seconds=int(stop_time-start_time))

        # resume the bot and set pause_bot to False
        if  bot_paused == True:
            print(f"{txcolors.WARNING}Resuming buying due to positive market conditions, total sleep time: {time_elapsed}{txcolors.DEFAULT}")
            if LIST_AUTOCREATE:
                tickers_list(SORT_LIST_TYPE)
            session_struct['dynamic'] = 'reset'
            session_struct['sell_all_coins'] = False
            bot_paused = False

    return


def convert_volume():
    '''Converts the volume given in QUANTITY from USDT to the each coin's volume'''

    #added feature to buy only if percent and signal triggers uses PERCENT_SIGNAL_BUY true or false from config
    if PERCENT_SIGNAL_BUY == True:
       volatile_coins, number_of_coins, last_price = wait_for_price('percent_mix_signal')
    else:
       volatile_coins, number_of_coins, last_price = wait_for_price('percent_and_signal')

    lot_size = {}
    volume = {}

    for coin in volatile_coins:

        # Find the correct step size for each coin
        # max accuracy for BTC for example is 6 decimal points
        # while XRP is only 1
        try:
            info = client.get_symbol_info(coin)
            step_size = info['filters'][2]['stepSize']
            lot_size[coin] = step_size.index('1') - 1

            if lot_size[coin] < 0:
                lot_size[coin] = 0

        except:
            pass

        # calculate the volume in coin from QUANTITY in USDT (default)
        volume[coin] = float(QUANTITY / float(last_price[coin]['price']))

        # define the volume with the correct step size
        if coin not in lot_size:
            volume[coin] = float('{:.1f}'.format(volume[coin]))

        else:
            # if lot size has 0 decimal points, make the volume an integer
            if lot_size[coin] == 0:
                volume[coin] = int(volume[coin])
            else:
                volume[coin] = float('{:.{}f}'.format(volume[coin], lot_size[coin]))

    return volume, last_price


def test_order_id():
    import random
    """returns a fake order id by hashing the current time"""
    test_order_id_number = random.randint(100000000,999999999)
    return test_order_id_number


def buy():
    '''Place Buy market orders for each volatile coin found'''
    global UNIQUE_BUYS
    volume, last_price = convert_volume()
    orders = {}

    for coin in volume:
        BUYABLE = True
        if UNIQUE_BUYS and (coin in coins_bought):
            BUYABLE = False

        # only buy if the there are no active trades on the coin
        if BUYABLE:
            print(f"{txcolors.BUY}Preparing to buy {volume[coin]} {coin}{txcolors.DEFAULT}")

            REPORT = str(f"Buy : {volume[coin]} {coin} - {last_price[coin]['price']}")

            if TEST_MODE:
                orders[coin] = [{
                    'symbol': coin,
                    'orderId': test_order_id(),
                    'time': datetime.now().timestamp()
                }]

                # Log trades
                report('log',REPORT)

                continue

            # try to create a real order if the test orders did not raise an exception
            try:
                buy_limit = client.create_order(
                    symbol = coin,
                    side = 'BUY',
                    type = 'MARKET',
                    quantity = volume[coin]
                )

            # error handling here in case position cannot be placed
            except Exception as e:
                print(e)

            # run the else block if the position has been placed and return order info
            else:
                orders[coin] = client.get_all_orders(symbol=coin, limit=1)

                # binance sometimes returns an empty list, the code will wait here until binance returns the order
                while orders[coin] == []:
                    print('Binance is being slow in returning the order, calling the API again...')

                    orders[coin] = client.get_all_orders(symbol=coin, limit=1)
                    time.sleep(1)

                else:
                    # Log, announce, and report trade
                    print('Order returned, saving order to file')
                    report('log',REPORT)


        else:
            print(f'Signal detected, but there is already an active trade on {coin}')

    return orders, last_price, volume


def sell_coins():
    '''sell coins that have reached the STOP LOSS or TAKE PROFIT threshold'''
    global session_struct

    global hsp_head
    global FULL_LOG
    last_price = get_price(False) # don't populate rolling window
    #last_price = get_price(add_to_historical=True) # don't populate rolling window
    coins_sold = {}

    for coin in list(coins_bought):

        BUY_PRICE = float(coins_bought[coin]['bought_at'])
        # TP is the price at which to 'take profit' based on config % markup
        TP = BUY_PRICE + ((BUY_PRICE * coins_bought[coin]['take_profit']) / 100)
        # SL is the price at which to 'stop losses' based on config % markdown
        SL = BUY_PRICE + ((BUY_PRICE * coins_bought[coin]['stop_loss']) / 100)
        # TL is the time limit for holding onto a coin
        TL = float(coins_bought[coin]['timestamp']) + HOLDING_TIME_LIMIT

        lastPrice = float(last_price[coin]['price'])
        LAST_PRICE = "{:.8f}".format(lastPrice)
        sellFee = (coins_bought[coin]['volume'] * lastPrice) * (TRADING_FEE/100)
        buyPrice = float(coins_bought[coin]['bought_at'])
        BUY_PRICE = "{:.8f}". format(buyPrice)
        buyFee = (coins_bought[coin]['volume'] * buyPrice) * (TRADING_FEE/100)
        # Note: priceChange and priceChangeWithFee are percentages!
        priceChange = float((lastPrice - buyPrice) / buyPrice * 100)
        # priceChange = (0.00006648 - 0.00006733) / 0.00006733 * 100
        # volume = 150
        # buyPrice: 0.00006733
        # lastPrice: 0.00006648
        # buyFee = (150 * 0.00006733) * (0.075/100)
        # buyFee = 0.000007574625
        # sellFee = (150 * 0.00006648) * (0.075/100)
        # sellFee = 0.000007479

        # check that the price is above the take profit and readjust SL and TP accordingly if trialing stop loss used
        if lastPrice > TP and USE_TRAILING_STOP_LOSS:
            # increasing TP by TRAILING_TAKE_PROFIT (essentially next time to readjust SL)
            coins_bought[coin]['take_profit'] = priceChange + TRAILING_TAKE_PROFIT
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - TRAILING_STOP_LOSS
            if DEBUG: print(f"{coin} TP reached, adjusting TP {coins_bought[coin]['take_profit']:.{decimals()}f} and SL {coins_bought[coin]['stop_loss']:.{decimals()}f} accordingly to lock-in profit")
            continue

        if not TEST_MODE:
           current_time = float(round(time.time() * 1000))
#           print(f'TL:{TL}, time: {current_time} HOLDING_TIME_LIMIT: {HOLDING_TIME_LIMIT}, TimeLeft: {(TL - current_time)/1000/60} ')

        if TEST_MODE:
           current_time = float(round(time.time()))
#           print(f'TL:{TL}, time: {current_time} HOLDING_TIME_LIMIT: {HOLDING_TIME_LIMIT}, TimeLeft: {(TL - current_time)/60} ')

        # check that the price is below the stop loss or above take profit (if trailing stop loss not used) and sell if this is the case
        if session_struct['sell_all_coins'] == True or lastPrice < SL or lastPrice > TP and not USE_TRAILING_STOP_LOSS or TL < current_time:
            print(f"{txcolors.SELL_PROFIT if priceChange >= 0. else txcolors.SELL_LOSS}TP or SL reached, selling {coins_bought[coin]['volume']} {coin}. Bought at: {BUY_PRICE} (Price now: {LAST_PRICE})  - {priceChange:.2f}% - Est: {(QUANTITY * priceChange) / 100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")
            # try to create a real order
            try:

                if not TEST_MODE:
                    sell_coins_limit = client.create_order(
                        symbol = coin,
                        side = 'SELL',
                        type = 'MARKET',
                        quantity = coins_bought[coin]['volume']
                    )

            # error handling here in case position cannot be placed
            except Exception as e:
                print(e)

            # run the else block if coin has been sold and create a dict for each coin sold
            else:
                coins_sold[coin] = coins_bought[coin]

                # prevent system from buying this coin for the next TIME_DIFFERENCE minutes
                volatility_cooloff[coin] = datetime.now()

                # Log trade
                profit = ((lastPrice - buyPrice) * coins_sold[coin]['volume']) - (buyFee + sellFee)

                #gogo MOD to trigger trade lost or won and to count lost or won trades
                if profit > 0:
                   session_struct['win_trade_count'] = session_struct['win_trade_count'] + 1
                   session_struct['dynamic'] = 'performance_adjust_up'
                else:
                   session_struct['loss_trade_count'] = session_struct['loss_trade_count'] + 1
                   dynamic = 'performance_adjust_down'

                if session_struct['sell_all_coins'] == True: REPORT =  f"PAUSE_SELL - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice < SL: REPORT =  f"STOP_LOSS - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice > TP: REPORT =  f"TAKE_PROFIT - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if TL < current_time: REPORT =  f"HOLDING_TIMEOUT - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"

                session_struct['session_profit'] = session_struct['session_profit'] + profit
                session_struct['closed_trades_percent'] = session_struct['closed_trades_percent'] + priceChange

                report('message',f"{REPORT}")
                report('log',f"{REPORT}")
                tickers_list(SORT_LIST_TYPE)

            continue

        # no action; print once every TIME_DIFFERENCE
        if hsp_head == 1:
            if len(coins_bought) > 0:
                print(f"TP:{TP:.{decimals()}f}:{coins_bought[coin]['take_profit']:.2f} or SL:{SL:.{decimals()}f}:{coins_bought[coin]['stop_loss']:.2f} not yet reached, not selling {coin} for now >> Bought at: {BUY_PRICE} - Now: {LAST_PRICE} : {txcolors.SELL_PROFIT if priceChange >= 0. else txcolors.SELL_LOSS}{priceChange:.2f}% Est: {(QUANTITY*(priceChange-(buyFee+sellFee)))/100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")
    if FULL_LOG:
        if hsp_head == 1 and len(coins_bought) == 0: print(f"No trade slots are currently in use")

    return coins_sold


def update_portfolio(orders, last_price, volume):

    '''add every coin bought to our portfolio for tracking/selling later'''
    if DEBUG: print(orders)
    for coin in orders:

        coins_bought[coin] = {
            'symbol': orders[coin][0]['symbol'],
            'orderid': orders[coin][0]['orderId'],
            'timestamp': orders[coin][0]['time'],
            'bought_at': last_price[coin]['price'],
            'volume': volume[coin],
            'stop_loss': -STOP_LOSS,
            'take_profit': TAKE_PROFIT,
            }

        # save the coins in a json file in the same directory
        with open(coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent=4)

        print(f'Order for {orders[coin][0]["symbol"]} with ID {orders[coin][0]["orderId"]} placed and saved to file.')

        session('save')


def remove_from_portfolio(coins_sold):
    '''Remove coins sold due to SL or TP from portfolio'''
    for coin,data in coins_sold.items():
        symbol = coin
        order_id = data['orderid']
        # code below created by getsec <3
        for bought_coin, bought_coin_data in coins_bought.items():
            if bought_coin_data['orderid'] == order_id:
                print(f"Sold {bought_coin}, removed order ID {order_id} from history.")
                coins_bought.pop(bought_coin)
                with open(coins_bought_file_path, 'w') as file:
                    json.dump(coins_bought, file, indent=4)
                break

        session('save')


def report(type, reportline):

    global session_struct

    try: # does it exist?
        session_struct['investment_value_gain']
    except NameError: # if not, set to 0
        sessio_struct['investment_value_gain'] = 0

    WON = session_struct['win_trade_count']
    LOST = session_struct['loss_trade_count']
    DECIMALS = int(decimals())
    INVESTMENT_TOTAL = round((QUANTITY * TRADE_SLOTS), DECIMALS)
    CURRENT_EXPOSURE = round(session_struct['CURRENT_EXPOSURE'], DECIMALS)
    session_struct['TOTAL_GAINS'] = round(session_struct['TOTAL_GAINS'], DECIMALS)
    INVESTMENT_VALUE_GAIN = round(session_struct['investment_value_gain'], 2)

    # testing:
    NEW_BALANCE_TRIM = "%g" % round(session_struct['NEW_BALANCE'], DECIMALS)
    INVESTMENT_VALUE_TRIM =  "%g" % round(session_struct['investment_value'], 2)
    INVESTMENT_VALUE_GAIN_TRIM =  "%g" % round(session_struct['investment_value_gain'], 2)
    CURRENT_EXPOSURE_TRIM = "%g" % session_struct['CURRENT_EXPOSURE']
    INVESTMENT_TOTAL_TRIM = "%g" % INVESTMENT_TOTAL
    CLOSED_TRADES_PERCENT_TRIM = "%g" % round(session_struct['closed_trades_percent'], 2)
    SESSION_PROFIT_TRIM = format(session_struct['session_profit'], '.8f')
    # SESSION_PROFIT_TRIM = "%g" % round(session_profit, DECIMALS)

    SETTINGS_STRING = 'Time: '+str(round(TIME_DIFFERENCE, 2))+' | Interval: '+str(round(RECHECK_INTERVAL, 2))+' | Price change min/max: '+str(round(CHANGE_IN_PRICE_MIN, 2))+'/'+str(round(CHANGE_IN_PRICE_MAX, 2))+'% | Stop loss: '+str(round(STOP_LOSS, 2))+' | Take profit: '+str(round(TAKE_PROFIT, 2))+' | Trailing stop loss: '+str(round(TRAILING_STOP_LOSS, 2))+' | Trailing take profit: '+str(round(TRAILING_TAKE_PROFIT, 2))

    if len(coins_bought) > 0:
        UNREALISED_PERCENT = round(session_struct['unrealised_percent']/len(coins_bought), 2)
    else:
        UNREALISED_PERCENT = 0
    if (session_struct['win_trade_count'] > 0) and (session_struct['loss_trade_count'] > 0):
        WIN_LOSS_PERCENT = round((session_struct['win_trade_count']  / (session_struct['win_trade_count']  + session_struct['loss_trade_count'])) * 100, 2)
    else:
        WIN_LOSS_PERCENT = 100

    # adding all the stats together:
    report_string= 'Trade slots: '+str(len(coins_bought))+'/'+str(TRADE_SLOTS)+' ('+str(CURRENT_EXPOSURE_TRIM)+'/'+str(INVESTMENT_TOTAL_TRIM)+' '+PAIR_WITH+') | Session: '+str(SESSION_PROFIT_TRIM)+' '+PAIR_WITH+' ('+str(CLOSED_TRADES_PERCENT_TRIM)+'%) | Win/Loss: '+str(WON)+'/'+str(LOST)+' ('+str(WIN_LOSS_PERCENT)+'%) | Gains: '+str(round(session_struct['INVESTMENT_GAIN'], 4))+'%'+' | Balance: '+str(NEW_BALANCE_TRIM)+' | Value: '+str(INVESTMENT_VALUE_TRIM)+' USD | Value gain: '+str(INVESTMENT_VALUE_GAIN_TRIM)+' | Uptime: '+str(timedelta(seconds=(int(session_struct['session_uptime']/1000))))

    #gogo MOD todo more verbose having all the report things in it!!!!!
    if type == 'console':
        # print(f"{txcolors.NOTICE}>> Using {len(coins_bought)}/{TRADE_SLOTS} trade slots. OT:{UNREALISED_PERCENT:.2f}%> SP:{session_profit:.2f}%> Est:{TOTAL_GAINS:.{decimals()}f} {PAIR_WITH}> W:{win_trade_count}> L:{loss_trade_count}> IT:{INVESTMENT:.{decimals()}f} {PAIR_WITH}> CE:{CURRENT_EXPOSURE:.{decimals()}f} {PAIR_WITH}> NB:{NEW_BALANCE:.{decimals()}f} {PAIR_WITH}> IV:{investment_value:.2f} {exchange_symbol}> IG:{INVESTMENT_GAIN:.2f}%> IVG:{investment_value_gain:.{decimals()}f} {exchange_symbol}> {reportline} <<{txcolors.DEFAULT}")
        print(f"{report_string}")

    #More detailed/verbose report style
    if type == 'detailed':
        print(f"{txcolors.NOTICE}>> Using {len(coins_bought)}/{TRADE_SLOTS} trade slots. << \n"
        ,f"Profit on unsold coins:  {txcolors.SELL_PROFIT if UNREALISED_PERCENT >= 0 else txcolors.SELL_LOSS}{UNREALISED_PERCENT:.2f}%\n"
        ,f"Closed trades:           {txcolors.SELL_PROFIT if session_struct['closed_trades_percent'] >= 0 else txcolors.SELL_LOSS}{str(CLOSED_TRADES_PERCENT_TRIM)}%\n"
        ,f"Session profit:          {txcolors.SELL_PROFIT if session_struct['session_profit'] >= 0 else txcolors.SELL_LOSS}{str(SESSION_PROFIT_TRIM)} {PAIR_WITH}\n"
        ,f"Est. total gains:        {txcolors.SELL_PROFIT if session_struct['TOTAL_GAINS'] >= 0 else txcolors.SELL_LOSS}{session_struct['TOTAL_GAINS']:g} {PAIR_WITH}\n"
        ,f"Trades won/lost:         {txcolors.SELL_PROFIT if session_struct['win_trade_count'] >= session_struct['loss_trade_count'] else txcolors.SELL_LOSS}{session_struct['win_trade_count']} / {txcolors.SELL_PROFIT if session_struct['win_trade_count'] >= session_struct['loss_trade_count'] else txcolors.SELL_LOSS}{session_struct['loss_trade_count']}\n"
        ,f"Investment:              {txcolors.DEFAULT}{INVESTMENT_TOTAL:g} {PAIR_WITH}\n"
        ,f"Current exposure:        {txcolors.DEFAULT}{session_struct['CURRENT_EXPOSURE']:g} {PAIR_WITH}\n"
        ,f"New balance:             {txcolors.SELL_PROFIT if session_struct['NEW_BALANCE'] >= INVESTMENT_TOTAL else txcolors.SELL_LOSS}{session_struct['NEW_BALANCE']:g} {PAIR_WITH}\n"
        ,f"Initial investment:      {txcolors.SELL_PROFIT if session_struct['investment_value'] >= INVESTMENT else txcolors.SELL_LOSS}{session_struct['investment_value']:.2f} USD\n"
        ,f"Investment gain:         {txcolors.SELL_PROFIT if session_struct['INVESTMENT_GAIN'] >= 0 else txcolors.SELL_LOSS}{session_struct['INVESTMENT_GAIN']:.2f}%\n"
        ,f"Investment value vain:   {txcolors.SELL_PROFIT if session_struct['investment_value_gain'] >= 0 else txcolors.SELL_LOSS}{str(INVESTMENT_VALUE_GAIN)} USD\n"
        ,f"{reportline} {txcolors.DEFAULT}")

    if type == 'message':
        TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ID, DISCORD_WEBHOOK = load_telegram_creds(parsed_creds)
        bot_message = SETTINGS_STRING + '\n' + reportline + '\n' + report_string + '\n'

        if BOT_MESSAGE_REPORTS and TELEGRAM_BOT_TOKEN:
            bot_token = TELEGRAM_BOT_TOKEN
            bot_chatID = TELEGRAM_BOT_ID
            send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + BOT_ID + bot_message
            response = requests.get(send_text)

        if BOT_MESSAGE_REPORTS and DISCORD_WEBHOOK:

            mUrl = "https://discordapp.com/api/webhooks/"+DISCORD_WEBHOOK
            data = {"username" : BOT_ID , "avatar_url": discord_avatar(), "content": bot_message}
            response = requests.post(mUrl, json=data)
            #   print(response.content)

    if type == 'log':
        timestamp = datetime.now().strftime("%d/%m %H:%M:%S")
        # print(f'LOG_FILE: {LOG_FILE}')
        with open(LOG_FILE,'a+') as f:
            f.write(timestamp + ' ' + reportline + '\n')


def discord_avatar():
    # testing avatars dependant on PAIR_WITH
    if PAIR_WITH == 'ETH':
        DISCORD_AVATAR =  "https://i.imgur.com/L9Txc9F.jpeg"
    if PAIR_WITH == 'BTC':
        DISCORD_AVATAR =  "https://i.imgur.com/oIeAiEo.jpeg"
    if PAIR_WITH == 'USDT':
        DISCORD_AVATAR =  "https://i.imgur.com/VyOdlRS.jpeg"
    return DISCORD_AVATAR


#function to perform dynamic stoploss, take profit and trailing stop loss modification on the fly
def dynamic_settings(type, DYNAMIC_WIN_LOSS_UP, DYNAMIC_WIN_LOSS_DOWN, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN, HOLDING_TIME_LIMIT):

    global session_struct

    if DYNAMIC_SETTINGS:

        if type == 'performance_adjust_up':
            STOP_LOSS = STOP_LOSS + (STOP_LOSS * DYNAMIC_WIN_LOSS_UP) / 100
            TAKE_PROFIT = TAKE_PROFIT + (TAKE_PROFIT * DYNAMIC_WIN_LOSS_UP) / 100
            TRAILING_STOP_LOSS = TRAILING_STOP_LOSS + (TRAILING_STOP_LOSS * DYNAMIC_WIN_LOSS_UP) / 100
            CHANGE_IN_PRICE_MAX = CHANGE_IN_PRICE_MAX + (CHANGE_IN_PRICE_MAX * DYNAMIC_WIN_LOSS_DOWN) /100
            CHANGE_IN_PRICE_MIN = CHANGE_IN_PRICE_MIN - (CHANGE_IN_PRICE_MIN * DYNAMIC_WIN_LOSS_DOWN) /100
            HOLDING_TIME_LIMIT = HOLDING_TIME_LIMIT + (HOLDING_TIME_LIMIT * DYNAMIC_WIN_LOSS_UP) / 100
            session_struct['dynamic'] = 'none'
            print(f'{txcolors.NOTICE}>> Last Trade WON Changing STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f}  - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL: {HOLDING_TIME_LIMIT:.2f} <<{txcolors.DEFAULT}')

        if type == 'performance_adjust_down':
            STOP_LOSS = STOP_LOSS - (STOP_LOSS * DYNAMIC_WIN_LOSS_DOWN) / 100
            TAKE_PROFIT = TAKE_PROFIT - (TAKE_PROFIT * DYNAMIC_WIN_LOSS_DOWN) / 100
            TRAILING_STOP_LOSS = TRAILING_STOP_LOSS - (TRAILING_STOP_LOSS * DYNAMIC_WIN_LOSS_DOWN) / 100
            CHANGE_IN_PRICE_MAX = CHANGE_IN_PRICE_MAX - (CHANGE_IN_PRICE_MAX * DYNAMIC_WIN_LOSS_DOWN) /100
            CHANGE_IN_PRICE_MIN = CHANGE_IN_PRICE_MIN + (CHANGE_IN_PRICE_MIN * DYNAMIC_WIN_LOSS_DOWN) /100
            HOLDING_TIME_LIMIT = HOLDING_TIME_LIMIT - (HOLDING_TIME_LIMIT * DYNAMIC_WIN_LOSS_DOWN) / 100
            session_struct['dynamic'] = 'none'
            print(f'{txcolors.NOTICE}>> Last Trade LOST Changing STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}  - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL:{HOLDING_TIME_LIMIT:.2f} <<{txcolors.DEFAULT}')

        if type == 'reset':
            STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
            TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
            TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
            CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX']
            CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN']

            if not TEST_MODE: HOLDING_TIME_LIMIT = (parsed_config['trading_options']['TIME_DIFFERENCE'] * 60 * 1000) * parsed_config['trading_options']['HOLDING_INTERVAL_LIMIT']
            if TEST_MODE: HOLDING_TIME_LIMIT = (parsed_config['trading_options']['TIME_DIFFERENCE'] * 60) * parsed_config['trading_options']['HOLDING_INTERVAL_LIMIT']

            print(f'{txcolors.NOTICE}>> DYNAMIC SETTINGS RESET - STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}  - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL: {HOLDING_TIME_LIMIT:.2f} <<{txcolors.DEFAULT}')
            session_struct['dynamic'] = 'none'

        if CHANGE_IN_PRICE_MIN > 0:
            CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN'] - (CHANGE_IN_PRICE_MIN * session_struct['market_support'])
            CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX'] - (CHANGE_IN_PRICE_MAX * session_struct['market_support'])

        if CHANGE_IN_PRICE_MAX < 0:
            CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN'] + (CHANGE_IN_PRICE_MIN * session_struct['market_support'])
            CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX'] + (CHANGE_IN_PRICE_MAX * session_struct['market_support'])

    return STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN, HOLDING_TIME_LIMIT


def session(type):
    #various session calculations like uptime 24H gain profit risk to reward ratio unrealised profit etc
    global session_struct

    if type == 'calc':
        session_struct['TOTAL_GAINS'] = ((QUANTITY * session_struct['session_profit']) / 100)
        session_struct['NEW_BALANCE'] = (INVESTMENT + session_struct['TOTAL_GAINS'])
        session_struct['INVESTMENT_GAIN'] = (session_struct['TOTAL_GAINS'] / INVESTMENT) * 100
        session_struct['CURRENT_EXPOSURE'] = (QUANTITY * len(coins_bought))
        session_struct['unrealised_percent'] = 0

        for coin in list(coins_bought):
            lastPrice = float(last_price[coin]['price'])
            sellFee = (coins_bought[coin]['volume'] * lastPrice) * (TRADING_FEE/100)
            buyPrice = float(coins_bought[coin]['bought_at'])
            buyFee = (coins_bought[coin]['volume'] * buyPrice) * (TRADING_FEE/100)
            priceChange = float((lastPrice - buyPrice) / buyPrice * 100)
            if len(coins_bought) > 0:
                session_struct['unrealised_percent'] = session_struct['unrealised_percent'] + (priceChange-(buyFee+sellFee))

        # this number is your actual ETH or other coin value in correspondence to USDT aka your market investment_value
        # it is important cuz your exchange aha ETH or BTC can vary and if you pause bot during that time you gain profit
        session_struct['investment_value'] = float(session_struct['market_price']) * session_struct['NEW_BALANCE']
        session_struct['investment_value_gain'] = float(session_struct['market_price']) * (session_struct['NEW_BALANCE'] - INVESTMENT)

        current_time = float(round(time.time() * 1000))
        if session_struct['session_start_time'] == 0: session_struct['session_start_time'] = current_time
        session_struct['session_uptime'] = current_time - session_struct['session_start_time']

    if type == 'save':

        session_info = {}
        session_info_file_path = 'session_info.json'
        session_info = {
            'session_profit': session_struct['session_profit'],
            'win_trade_count': session_struct['win_trade_count'],
            'loss_trade_count': session_struct['loss_trade_count'],
            # 'investment_value': investment_value,
            'new_balance': session_struct['NEW_BALANCE'],
            'session_start_time': session_struct['session_start_time'],
            'session_uptime': session_struct['session_uptime'],
            'closed_trades_percent': session_struct['closed_trades_percent'],
            }

        # save the coins in a json file in the same directory
        with open(session_info_file_path, 'w') as file:
            json.dump(session_info, file, indent=4)

    if type == 'load':

        session_info = {}
        #gogo MOD path to session info file and loading variables from previous sessions
        #sofar only used for session profit TODO implement to use other things too
        #session_profit is calculated in % wich is innacurate if QUANTITY is not the same!!!!!
        session_info_file_path = 'session_info.json'

        if os.path.isfile(session_info_file_path) and os.stat(session_info_file_path).st_size!= 0:
            json_file=open(session_info_file_path)
            session_info=json.load(json_file)
            json_file.close()

            session_struct['session_profit'] = session_info['session_profit']
            session_struct['win_trade_count'] = session_info['win_trade_count']
            session_struct['loss_trade_count'] = session_info['loss_trade_count']
            # investment_value = session['investment_value']
            session_struct['NEW_BALANCE'] = session_info['new_balance']
            session_struct['session_start_time'] = session_info['session_start_time']
            session_struct['closed_trades_percent'] = session_info['closed_trades_percent']

        session_struct['TOTAL_GAINS'] = ((QUANTITY * session_struct['session_profit']) / 100)
        session_struct['NEW_BALANCE'] = (INVESTMENT + session_struct['TOTAL_GAINS'])
        session_struct['INVESTMENT_GAIN'] = (session_struct['TOTAL_GAINS'] / INVESTMENT) * 100


def tickers_list(type):

    global historical_prices, hsp_head
    global LIST_AUTOCREATE

    tickers_list_volume = {}
    tickers_list_price_change = {}

    # get all info on tickers from binance
    tickers_binance = client.get_ticker()
    tickers_pairwith = {}
    tickers_new = {}

    if LIST_AUTOCREATE:
    # pull coins from trading view and create a list
        if type == 'create_ta':
            response = requests.get('https://scanner.tradingview.com/crypto/scan')
            ta_data = response.json()
            signals_file = open(TICKERS_LIST,'w')
            with open (TICKERS_LIST, 'w') as f:
                for i in ta_data['data']:
                    if i['s'][:7]=='BINANCE' and i['s'][-len(PAIR_WITH):] == PAIR_WITH and i['s'][8:-len(PAIR_WITH)] not in ignorelist:
                        f.writelines(str(i['s'][8:-len(PAIR_WITH)])+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers CREATED from TradingView tickers!!!{TICKERS_LIST} <<')

        if type == 'volume' or type == 'price_change':
        #  create list with volume and change in price on our pairs
                for coin in tickers_binance:
                    if CUSTOM_LIST:
                        if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                            tickers_list_volume[coin['symbol']] = { 'volume': coin['volume']}
                            tickers_list_price_change[coin['symbol']] = { 'priceChangePercent': coin['priceChangePercent']}

                    else:
                        if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                            tickers_list_volume[coin['symbol']] = { 'volume': coin['volume']}
                            tickers_list_price_change[coin['symbol']] = { 'priceChangePercent': coin['priceChangePercent']}

                # sort tickers by descending order volume and price
                list_tickers_volume = list(sorted( tickers_list_volume.items(), key=lambda x: x[1]['volume'], reverse=True))
                list_tickers_price_change = list(sorted( tickers_list_price_change.items(), key=lambda x: x[1]['priceChangePercent'], reverse=True))

        # pull coins from binance and create list
        if type == 'create_b':
            for coin in tickers_binance:
                if PAIR_WITH in coin['symbol']:
                    tickers_pairwith[coin['symbol']] = coin['symbol']
                    if tickers_pairwith[coin['symbol']].endswith(PAIR_WITH):
                        tickers_new[coin['symbol']] = tickers_pairwith[coin['symbol']]

            list_tickers_new = list(tickers_new)


            with open (TICKERS_LIST, 'w') as f:
                for ele in list_tickers_new:
                    f.writelines(str(ele.replace(PAIR_WITH,''))+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers CREATED from binance tickers!!!{TICKERS_LIST} <<')

            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers CREATED from Binance tickers!!!{TICKERS_LIST} <<')

        if type == 'volume' and CUSTOM_LIST:
        # write sorted lists to files
            with open (TICKERS_LIST, 'w') as f:
                    for sublist in list_tickers_volume:
                        f.writelines(str(sublist[0].replace(PAIR_WITH,''))+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers List {TICKERS_LIST} recreated and loaded!! <<')

        if type == 'price_change':
        # write sorted list to files
            with open (TICKERS_LIST, 'w') as f:
                    for sublist in list_tickers_price_change:
                        f.writelines(str(sublist[0].replace(PAIR_WITH,''))+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers List {TICKERS_LIST} recreated and loaded!! <<')


def bot_launch():
    # Bot relays session start to Discord channel
    bot_message = "Bot initiated"
    report('message', bot_message)


if __name__ == '__main__':

    # Load arguments then parse settings
    args = parse_args()
    mymodule = {}

    # set to false at Start
    global bot_paused
    bot_paused = False

    DEFAULT_CONFIG_FILE = 'config.yml'
    DEFAULT_CREDS_FILE = 'creds.yml'

    config_file = args.config if args.config else DEFAULT_CONFIG_FILE
    creds_file = args.creds if args.creds else DEFAULT_CREDS_FILE
    parsed_config = load_config(config_file)
    parsed_creds = load_config(creds_file)

    # Default no debugging
    DEBUG = False

    # Load system vars
    TEST_MODE = parsed_config['script_options']['TEST_MODE']
    # LOG_TRADES = parsed_config['script_options'].get('LOG_TRADES')
    LOG_FILE = parsed_config['script_options'].get('LOG_FILE')
    DETAILED_REPORTS = parsed_config['script_options']['DETAILED_REPORTS']
    DEBUG_SETTING = parsed_config['script_options'].get('VERBOSE_MODE')
    AMERICAN_USER = parsed_config['script_options'].get('AMERICAN_USER')
    BOT_MESSAGE_REPORTS =  parsed_config['script_options'].get('BOT_MESSAGE_REPORTS')
    BOT_ID = parsed_config['script_options'].get('BOT_ID')
    UNIQUE_BUYS = parsed_config['script_options'].get('UNIQUE_BUYS')

    # Load trading vars
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    INVESTMENT = parsed_config['trading_options']['INVESTMENT']
    TRADE_SLOTS = parsed_config['trading_options']['TRADE_SLOTS']
    EXCLUDED_PAIRS = parsed_config['trading_options']['EXCLUDED_PAIRS']
    TIME_DIFFERENCE = parsed_config['trading_options']['TIME_DIFFERENCE']
    RECHECK_INTERVAL = parsed_config['trading_options']['RECHECK_INTERVAL']
    CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN']
    CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX']
    STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
    TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
    CUSTOM_LIST = parsed_config['trading_options']['CUSTOM_LIST']
    TICKERS_LIST = parsed_config['trading_options']['TICKERS_LIST']
    USE_TRAILING_STOP_LOSS = parsed_config['trading_options']['USE_TRAILING_STOP_LOSS']
    TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
    TRAILING_TAKE_PROFIT = parsed_config['trading_options']['TRAILING_TAKE_PROFIT']
    TRADING_FEE = parsed_config['trading_options']['TRADING_FEE']
    SIGNALLING_MODULES = parsed_config['trading_options']['SIGNALLING_MODULES']
    DYNAMIC_WIN_LOSS_UP = parsed_config['trading_options']['DYNAMIC_WIN_LOSS_UP']
    DYNAMIC_WIN_LOSS_DOWN = parsed_config['trading_options']['DYNAMIC_WIN_LOSS_DOWN']
    DYNAMIC_SETTINGS = parsed_config['trading_options']['DYNAMIC_SETTINGS']
    STOP_LOSS_ON_PAUSE = parsed_config['trading_options']['STOP_LOSS_ON_PAUSE']
    PERCENT_SIGNAL_BUY = parsed_config['trading_options']['PERCENT_SIGNAL_BUY']
    SORT_LIST_TYPE = parsed_config['trading_options']['SORT_LIST_TYPE']
    LIST_AUTOCREATE = parsed_config['trading_options']['LIST_AUTOCREATE']
    LIST_CREATE_TYPE = parsed_config['trading_options']['LIST_CREATE_TYPE']
    IGNORE_LIST = parsed_config['trading_options']['IGNORE_LIST']

    DETAILED_REPORTS = parsed_config['script_options']['DETAILED_REPORTS']
    HOLDING_INTERVAL_LIMIT = parsed_config['trading_options']['HOLDING_INTERVAL_LIMIT']
    QUANTITY = INVESTMENT/TRADE_SLOTS

    if not TEST_MODE: HOLDING_TIME_LIMIT = (TIME_DIFFERENCE * 60 * 1000) * HOLDING_INTERVAL_LIMIT
    if TEST_MODE: HOLDING_TIME_LIMIT = (TIME_DIFFERENCE * 60) * HOLDING_INTERVAL_LIMIT

    if DEBUG_SETTING or args.debug:
        DEBUG = True
    # Load creds for correct environment
    access_key, secret_key = load_correct_creds(parsed_creds)

    # Telegram_Bot enabled? # **added by*Coding60plus

    if BOT_MESSAGE_REPORTS:
        TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ID, DISCORD_WEBHOOK = load_telegram_creds(parsed_creds)

    # Telegram_Bot enabled? # **added by*Coding60plus
    if DEBUG:
        print(f'Loaded config below\n{json.dumps(parsed_config, indent=4)}')
        print(f'Your credentials have been loaded from {creds_file}')

    # Authenticate with the client, Ensure API key is good before continuing
    if AMERICAN_USER:
        client = Client(access_key, secret_key, tld='us')
    else:
        client = Client(access_key, secret_key)

    # If the users has a bad / incorrect API key.
    # this will stop the script from starting, and display a helpful error.
    api_ready, msg = test_api_key(client, BinanceAPIException)
    if api_ready is not True:
        exit(f'{txcolors.SELL_LOSS}{msg}{txcolors.DEFAULT}')
    # Load coins to be ignored from file
    ignorelist=[line.strip() for line in open(IGNORE_LIST)]

    #sort tickers list by volume
    if LIST_AUTOCREATE:
        if LIST_CREATE_TYPE == 'binance':
            tickers_list('create_b')
            tickers=[line.strip() for line in open(TICKERS_LIST)]

        if LIST_CREATE_TYPE == 'tradingview':
            tickers_list('create_ta')
            tickers=[line.strip() for line in open(TICKERS_LIST)]

    # Use CUSTOM_LIST symbols if CUSTOM_LIST is set to True
    if CUSTOM_LIST: tickers=[line.strip() for line in open(TICKERS_LIST)]

    # try to load all the coins bought by the bot if the file exists and is not empty
    coins_bought = {}

    # path to the saved coins_bought file
    coins_bought_file_path = 'coins_bought.json'

    # rolling window of prices; cyclical queue
    historical_prices = [None] * (TIME_DIFFERENCE * RECHECK_INTERVAL)
    hsp_head = -1

    # prevent including a coin in volatile_coins if it has already appeared there less than TIME_DIFFERENCE minutes ago
    volatility_cooloff = {}

    # use separate files for testing and live trading
    if TEST_MODE:
        coins_bought_file_path = 'test_' + coins_bought_file_path

    # if saved coins_bought json file exists and it's not empty then load it
    if os.path.isfile(coins_bought_file_path) and os.stat(coins_bought_file_path).st_size!= 0:
        with open(coins_bought_file_path) as file:
                coins_bought = json.load(file)

    print('Press Ctrl-Q to stop the script')

    if not TEST_MODE:
        if not args.notimeout: # if notimeout skip this (fast for dev tests)
            print('WARNING: test mode is disabled in the configuration, you are using live funds.')
            print('WARNING: Waiting 10 seconds before live trading as a security measure!')
            time.sleep(10)

    signals = glob.glob("signals/*.exs")
    for filename in signals:
        for line in open(filename):
            try:
                os.remove(filename)
            except:
                if DEBUG: print(f'{txcolors.WARNING}Could not remove external signalling file {filename}{txcolors.DEFAULT}')

    if os.path.isfile("signals/paused.exc"):
        try:
            os.remove("signals/paused.exc")
        except:
            if DEBUG: print(f'{txcolors.WARNING}Could not remove external signalling file {filename}{txcolors.DEFAULT}')

    # load signalling modules
    try:
        if len(SIGNALLING_MODULES) > 0:
            for module in SIGNALLING_MODULES:
                print(f'Starting {module}')
                mymodule[module] = importlib.import_module(module)
                t = threading.Thread(target=mymodule[module].do_work, args=())
                t.daemon = True
                t.start()
                time.sleep(2)
        else:
            print(f'No modules to load {SIGNALLING_MODULES}')
    except Exception as e:
        print(e)

    # seed initial prices
    get_price()

    READ_TIMEOUT_COUNT=0
    CONNECTION_ERROR_COUNT = 0
    #load previous session stuff
    session('load')
    bot_launch()

    while True:

        #reload tickers list by volume if triggered recreation
        if session_struct['tickers_list_changed'] == True :
            tickers=[line.strip() for line in open(TICKERS_LIST)]
            tickers_list_changed = False
        # print(f'Tickers list changed and loaded: {tickers}')
        try:
            orders, last_price, volume = buy()
            update_portfolio(orders, last_price, volume)
            coins_sold = sell_coins()
            remove_from_portfolio(coins_sold)
        except ReadTimeout as rt:
            READ_TIMEOUT_COUNT += 1
            print(f'We got a timeout error from from binance. Going to re-loop. Current Count: {READ_TIMEOUT_COUNT}')
        except ConnectionError as ce:
            CONNECTION_ERROR_COUNT +=1
            print(f'{txcolors.WARNING}We got a timeout error from from binance. Going to re-loop. Current Count: {CONNECTION_ERROR_COUNT}\n{ce}{txcolors.DEFAULT}')
        #gogos MOD to adjust dynamically stoploss trailingstop loss and take profit based on wins
        STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN, HOLDING_TIME_LIMIT = dynamic_settings(session_struct['dynamic'], DYNAMIC_WIN_LOSS_UP, DYNAMIC_WIN_LOSS_DOWN, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN, HOLDING_TIME_LIMIT)
        #session calculations like unrealised potential etc
        session('calc')
