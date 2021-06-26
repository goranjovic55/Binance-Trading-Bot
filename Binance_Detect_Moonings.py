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

from settings import *
from dynamics import *
from report import *
from session import *
from tickers_list import *

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


def get_symbol_info(url='https://api.binance.com/api/v3/exchangeInfo'):
    global session_struct
    response = requests.get(url)
    json_message = json.loads(response.content)

    for symbol_info in json_message['symbols']:
        session_struct['symbol_info'][symbol_info['symbol']] = symbol_info['filters'][2]['stepSize']


def get_historical_price():
    global session_struct
    if is_fiat():
        session_struct['market_price'] = 1
        session_struct['exchange_symbol'] = PAIR_WITH
    else:
        session_struct['exchange_symbol'] = PAIR_WITH + 'USDT'
        market_historic = client.get_historical_trades(symbol=session_struct['exchange_symbol'])
        session_struct['market_price'] = market_historic[0].get('price')


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

        if hsp_head == 2:
            hsp_head = 0

        historical_prices[hsp_head] = initial_price

    return initial_price


def wait_for_price(type):
    '''calls the initial price and ensures the correct amount of time has passed
    before reading the current price again'''

    global historical_prices, hsp_head, volatility_cooloff, session_struct, settings_struct

    volatile_coins = {}
    externals = {}

    current_time_minutes = float(round(time.time()))/60

    pause_bot()

    #first time we just skip untill we find a way for historic fata to be grabbed here
    if session_struct['price_timedelta'] == 0: session_struct['price_timedelta'] = current_time_minutes
    #we give local variable value of time that we use for checking to grab prices again
    price_timedelta_value = session_struct['price_timedelta']

    #if historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'] > datetime.now() - timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)):

        # sleep for exactly the amount of time required
        #time.sleep((timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)) - (datetime.now() - historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'])).total_seconds())
    #print(f'PRICE_TIMEDELTA: {price_timedelta_value} - CURRENT_TIME: {current_time_minutes} - TIME_DIFFERENCE: {TIME_DIFFERENCE}')

    if session_struct['price_timedelta'] < current_time_minutes - float(settings_struct['TIME_DIFFERENCE']):

       #print(f'GET PRICE TRIGGERED !!!!! PRICE_TIMEDELTA: {price_timedelta_value} - TIME_DIFFERENCE: {TIME_DIFFERENCE}')
       # retrieve latest prices
       get_price()
       externals = external_signals()
       session_struct['price_timedelta'] = current_time_minutes
       session_struct['market_resistance'] = 0
       session_struct['market_support'] = 0
       coins_up = 0
       coins_down = 0

       # calculate the difference in prices
       for coin in historical_prices[hsp_head]:

           # minimum and maximum prices over time period
           min_price = min(historical_prices, key = lambda x: float("inf") if x is None else float(x[coin]['price']))
           max_price = max(historical_prices, key = lambda x: -1 if x is None else float(x[coin]['price']))

           threshold_check = (-1.0 if min_price[coin]['time'] > max_price[coin]['time'] else 1.0) * (float(max_price[coin]['price']) - float(min_price[coin]['price'])) / float(min_price[coin]['price']) * 100

           if threshold_check > 0:
              session_struct['market_resistance'] = session_struct['market_resistance'] + threshold_check
              coins_up = coins_up +1

           if threshold_check < 0:
              session_struct['market_support'] = session_struct['market_support'] - threshold_check
              coins_down = coins_down +1

       if coins_up != 0: session_struct['market_resistance'] = session_struct['market_resistance'] / coins_up
       if coins_down != 0: session_struct['market_support'] = -session_struct['market_support'] / coins_down


    # calculate the difference in prices
    for coin in historical_prices[hsp_head]:

        # minimum and maximum prices over time period
        min_price = min(historical_prices, key = lambda x: float("inf") if x is None else float(x[coin]['price']))
        max_price = max(historical_prices, key = lambda x: -1 if x is None else float(x[coin]['price']))

        threshold_check = (-1.0 if min_price[coin]['time'] > max_price[coin]['time'] else 1.0) * (float(max_price[coin]['price']) - float(min_price[coin]['price'])) / float(min_price[coin]['price']) * 100

        if type == 'percent_mix_signal':

           # each coin with higher gains than our CHANGE_IN_PRICE is added to the volatile_coins dict if less than TRADE_SLOTS is not reached.
           if threshold_check > settings_struct['CHANGE_IN_PRICE_MIN'] and threshold_check < settings_struct['CHANGE_IN_PRICE_MAX'] and threshold_check > session_struct['market_support']:

               #if os.path.exists('signals/nigec_custsignalmod.exs') or os.path.exists('signals/djcommie_custsignalmod.exs') or os.path.exists('signals/firewatch_signalsample.exs'):
               #signals = glob.glob("signals/*.exs")

               for excoin in externals:
                   #print(f'EXCOIN: {excoin}')
                   if excoin == coin:
                     # print(f'EXCOIN: {excoin} == COIN: {coin}')
                      if coin not in volatility_cooloff:
                         volatility_cooloff[coin] = datetime.now() - timedelta(minutes=settings_struct['TIME_DIFFERENCE'])
                      # only include coin as volatile if it hasn't been picked up in the last TIME_DIFFERENCE minutes already
                      if datetime.now() >= volatility_cooloff[coin] + timedelta(minutes=settings_struct['TIME_DIFFERENCE']):
                         volatility_cooloff[coin] = datetime.now()
                         if len(coins_bought) + len(volatile_coins) < TRADE_SLOTS or TRADE_SLOTS == 0:
                            volatile_coins[coin] = round(threshold_check, 3)
                            print(f"{coin} has gained {volatile_coins[coin]}% within the last {settings_struct['TIME_DIFFERENCE']} minutes, and coin {excoin} recived a signal... calculating {QUANTITY} {PAIR_WITH} value of {coin} for purchase!")
                         #else:
                            #print(f"{txcolors.WARNING}{coin} has gained {round(threshold_check, 3)}% within the last {TIME_DIFFERENCE} minutes, , and coin {excoin} recived a signal... but you are using all available trade slots!{txcolors.DEFAULT}")


        if type == 'percent_and_signal':

            # each coin with higher gains than our CHANGE_IN_PRICE is added to the volatile_coins dict if less than TRADE_SLOTS is not reached.
            if threshold_check > settings_struct['CHANGE_IN_PRICE_MIN'] and threshold_check < settings_struct['CHANGE_IN_PRICE_MAX']:

                if coin not in volatility_cooloff:
                    volatility_cooloff[coin] = datetime.now() - timedelta(minutes=settings_struct['TIME_DIFFERENCE'])

                # only include coin as volatile if it hasn't been picked up in the last TIME_DIFFERENCE minutes already
                if datetime.now() >= volatility_cooloff[coin] + timedelta(minutes=settings_struct['TIME_DIFFERENCE']):
                    volatility_cooloff[coin] = datetime.now()

                if len(coins_bought) + len(volatile_coins) < TRADE_SLOTS or TRADE_SLOTS == 0:
                    volatile_coins[coin] = round(threshold_check, 3)
                    print(f"{coin} has gained {volatile_coins[coin]}% within the last {settings_struct['TIME_DIFFERENCE']} minutes {QUANTITY} {PAIR_WITH} value of {coin} for purchase!")

                #else:
                   #print(f"{txcolors.WARNING}{coin} has gained {round(threshold_check, 3)}% within the last {TIME_DIFFERENCE} minutes but you are using all available trade slots!{txcolors.DEFAULT}")

            externals = external_signals()
            exnumber = 0

            for excoin in externals:
                if excoin not in volatile_coins and excoin not in coins_bought and (len(coins_bought) + exnumber) < TRADE_SLOTS:
                    volatile_coins[excoin] = 1
                    exnumber +=1
                    print(f"External signal received on {excoin}, calculating {QUANTITY} {PAIR_WITH} value of {excoin} for purchase!")


    # Report session status every minute. TODO: make report interval configurable
    if time.time() - session_struct['last_report_time'] > 1:
        if DETAILED_REPORTS:
            report('detailed',f"Market Resistance:      {txcolors.DEFAULT}{session_struct['market_resistance']:.4f}\n Market Support:         {txcolors.DEFAULT}{session_struct['market_support']:.4f}")
        else:
            report('console', f" MR:{session_struct['market_resistance']:.4f}/MS:{session_struct['market_support']:.4f} ")
        session_struct['last_report_time'] = time.time()

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
    global bot_paused, hsp_head, settings_struct
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
        if hsp_head:
           report('console', '.')

        time.sleep(settings_struct['RECHECK_INTERVAL'])

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
            step_size = session_struct['symbol_info'][coin]
            lot_size[coin] = step_size.index('1') - 1
        except KeyError:
            # not retrieved at startup, try again
            try:
                coin_info = client.get_symbol_info(coin)
                step_size = coin_info['filters'][2]['stepSize']
                lot_size[coin] = step_size.index('1') - 1
            except:
                pass
        lot_size[coin] = max(lot_size[coin], 0)

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
                order_details = client.create_order(
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

                    if not TEST_MODE:
                       orders[coin] = extract_order_data(order_details)
                       REPORT = str(f"BUY: bought {orders[coin]['volume']} {coin} - average price: {orders[coin]['avgPrice']} {PAIR_WITH}")
                    report('log',REPORT)



        else:
            print(f'Signal detected, but there is already an active trade on {coin}')

    return orders, last_price, volume


def sell_coins():
    '''sell coins that have reached the STOP LOSS or TAKE PROFIT threshold'''
    global session_struct, settings_struct

    global hsp_head
    global FULL_LOG
    last_price = get_price(False) # don't populate rolling window
    #last_price = get_price(add_to_historical=True) # don't populate rolling window
    coins_sold = {}

    for coin in list(coins_bought):

        BUY_PRICE = float(coins_bought[coin]['bought_at'])
        # coinTakeProfit is the price at which to 'take profit' based on config % markup
        coinTakeProfit = BUY_PRICE + ((BUY_PRICE * coins_bought[coin]['take_profit']) / 100)
        # coinStopLoss is the price at which to 'stop losses' based on config % markdown
        coinStopLoss = BUY_PRICE + ((BUY_PRICE * coins_bought[coin]['stop_loss']) / 100)
        # coinHoldingTimeLimit is the time limit for holding onto a coin
        coinHoldingTimeLimit = float(coins_bought[coin]['timestamp']) + settings_struct['HOLDING_TIME_LIMIT']
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

        # check that the price is above the take profit and readjust coinStopLoss and coinTakeProfit accordingly if trialing stop loss used
        if lastPrice > coinTakeProfit and USE_TRAILING_STOP_LOSS:
            # increasing coinTakeProfit by TRAILING_TAKE_PROFIT (essentially next time to readjust coinStopLoss)
            coins_bought[coin]['take_profit'] = priceChange + settings_struct['TRAILING_TAKE_PROFIT']
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - settings_struct['TRAILING_STOP_LOSS']
            if DEBUG: print(f"{coin} TP reached, adjusting TP {coins_bought[coin]['take_profit']:.{decimals()}f} and SL {coins_bought[coin]['stop_loss']:.{decimals()}f} accordingly to lock-in profit")
            continue

        if not TEST_MODE:
           current_time = float(round(time.time() * 1000))
#           print(f'TL:{coinHoldingTimeLimit}, time: {current_time} HOLDING_TIME_LIMIT: {HOLDING_TIME_LIMIT}, TimeLeft: {(coinHoldingTimeLimit - current_time)/1000/60} ')

        if TEST_MODE:
           current_time = float(round(time.time()))
#           print(f'TL:{coinHoldingTimeLimit}, time: {current_time} HOLDING_TIME_LIMIT: {HOLDING_TIME_LIMIT}, TimeLeft: {(coinHoldingTimeLimit - current_time)/60} ')

        # check that the price is below the stop loss or above take profit (if trailing stop loss not used) and sell if this is the case
        if session_struct['sell_all_coins'] == True or lastPrice < coinStopLoss or lastPrice > coinTakeProfit and not USE_TRAILING_STOP_LOSS or coinHoldingTimeLimit < current_time or lastPrice > session_struct['market_resistance']:
            print(f"{txcolors.SELL_PROFIT if priceChange >= 0. else txcolors.SELL_LOSS}TP or SL reached, selling {coins_bought[coin]['volume']} {coin}. Bought at: {BUY_PRICE} (Price now: {LAST_PRICE})  - {priceChange:.2f}% - Est: {(QUANTITY * priceChange) / 100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")
            # try to create a real order
            try:

                if not TEST_MODE:
                    order_details = client.create_order(
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
                if not TEST_MODE:

                   coins_sold[coin] = extract_order_data(order_details)
                   lastPrice = coins_sold[coin]['avgPrice']
                   sellFee = coins_sold[coin]['tradeFee']
                   coins_sold[coin]['orderid'] = coins_bought[coin]['orderid']
                   priceChange = float((lastPrice - buyPrice) / buyPrice * 100)

                else:
                   coins_sold[coin] = coins_bought[coin]


                # prevent system from buying this coin for the next TIME_DIFFERENCE minutes
                volatility_cooloff[coin] = datetime.now()

                # Log trade
                profit = ((lastPrice - buyPrice) * coins_sold[coin]['volume']) - (buyFee + sellFee)

                #gogo MOD to trigger trade lost or won and to count lost or won trades
                if priceChange > 0:
                   session_struct['win_trade_count'] = session_struct['win_trade_count'] + 1
                   session_struct['last_trade_won'] = True

                else:
                   session_struct['loss_trade_count'] = session_struct['loss_trade_count'] + 1
                   session_struct['last_trade_won'] = False

                if session_struct['sell_all_coins'] == True: REPORT =  f"PAUSE_SELL - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice < coinStopLoss: REPORT =  f"STOP_LOSS - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice > coinTakeProfit: REPORT =  f"TAKE_PROFIT - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice > session_struct['market_resistance']: REPORT = f"MARKET_RESISTANCE - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if coinHoldingTimeLimit < current_time: REPORT =  f"HOLDING_TIMEOUT - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"

                session_struct['session_profit'] = session_struct['session_profit'] + profit
                session_struct['closed_trades_percent'] = session_struct['closed_trades_percent'] + priceChange

                report('message',REPORT)
                report('log',REPORT)
                tickers_list(SORT_LIST_TYPE)

            continue

    if len(coins_bought) > 0:
       print(f"TP:{coinTakeProfit:.{decimals()}f}:{coins_bought[coin]['take_profit']:.2f} or SL:{coinStopLoss:.{decimals()}f}:{coins_bought[coin]['stop_loss']:.2f} not yet reached, not selling {coin} for now >> Bought at: {BUY_PRICE} - Now: {LAST_PRICE} : {txcolors.SELL_PROFIT if priceChange >= 0. else txcolors.SELL_LOSS}{priceChange:.2f}% Est: {(QUANTITY*(priceChange-(buyFee+sellFee)))/100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")
    if FULL_LOG:
        if hsp_head == 1 and len(coins_bought) == 0: print(f"No trade slots are currently in use")

    return coins_sold


def extract_order_data(order_details):
    global TRADING_FEE, STOP_LOSS, TAKE_PROFIT
    transactionInfo = {}
    # adding order fill extractions here
    #
    # just to explain what I am doing here:
    # Market orders are not always filled at one price, we need to find the averages of all 'parts' (fills) of this order.
    #
    # reset other variables to 0 before use
    FILLS_TOTAL = 0
    FILLS_QTY = 0
    FILLS_FEE = 0
    BNB_WARNING = 0
    # loop through each 'fill':
    for fills in order_details['fills']:
        FILL_PRICE = float(fills['price'])
        FILL_QTY = float(fills['qty'])
        FILLS_FEE += float(fills['commission'])
        # check if the fee was in BNB. If not, log a nice warning:
        if (fills['commissionAsset'] != 'BNB') and (TRADING_FEE == 0.75) and (BNB_WARNING == 0):
            print(f"WARNING: BNB not used for trading fee, please ")
            BNB_WARNING += 1
        # quantity of fills * price
        FILLS_TOTAL += (FILL_PRICE * FILL_QTY)
        # add to running total of fills quantity
        FILLS_QTY += FILL_QTY
        # increase fills array index by 1

    # calculate average fill price:
    FILL_AVG = (FILLS_TOTAL / FILLS_QTY)

    tradeFeeApprox = (float(FILLS_QTY) * float(FILL_AVG)) * (TRADING_FEE/100)
    # create object with received data from Binance
    transactionInfo = {
        'symbol': order_details['symbol'],
        'orderId': order_details['orderId'],
        'timestamp': order_details['transactTime'],
        'avgPrice': float(FILL_AVG),
        'volume': float(FILLS_QTY),
        'tradeFeeBNB': float(FILLS_FEE),
        'tradeFee': tradeFeeApprox,
    }
    return transactionInfo


def update_portfolio(orders, last_price, volume):

    global session_struct

    '''add every coin bought to our portfolio for tracking/selling later'''
    if DEBUG: print(orders)
    for coin in orders:

        if not TEST_MODE:
           coins_bought[coin] = {
               'symbol': orders[coin]['symbol'],
               'orderid': orders[coin]['orderId'],
               'timestamp': orders[coin]['timestamp'],
               'bought_at': orders[coin]['avgPrice'],
               'volume': orders[coin]['volume'],
               'buyFeeBNB': orders[coin]['tradeFeeBNB'],
               'buyFee': orders[coin]['tradeFee'],
               'stop_loss': -settings_struct['STOP_LOSS'],
               'take_profit': settings_struct['TAKE_PROFIT'],
               }
        else:
           coins_bought[coin] = {
               'symbol': orders[coin][0]['symbol'],
               'orderid': orders[coin][0]['orderId'],
               'timestamp': orders[coin][0]['time'],
               'bought_at': last_price[coin]['price'],
               'volume': volume[coin],
               'stop_loss': -settings_struct['STOP_LOSS'],
               'take_profit': settings_struct['TAKE_PROFIT'],
               }

        # save the coins in a json file in the same directory
        with open(coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent=4)

        if TEST_MODE: print(f'Order for {orders[coin][0]["symbol"]} with ID {orders[coin][0]["orderId"]} placed and saved to file.')
        if not TEST_MODE: print(f'Order for {orders[coin]["symbol"]} with ID {orders[coin]["orderId"]} placed and saved to file.')

        session_struct['trade_slots'] = len(coins_bought)
        session('save')


def remove_from_portfolio(coins_sold):

    global session_struct

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
        session_struct['trade_slots'] = len(coins_bought)
        session('save')


def bot_launch():
    # Bot relays session start to Discord channel
    bot_message = "Bot initiated"
    report('message', bot_message)


if __name__ == '__main__':

    mymodule = {}

    # set to false at Start
    global bot_paused
    bot_paused = False

    # try to load all the coins bought by the bot if the file exists and is not empty
    coins_bought = {}

    # get decimal places for each coin as used by Binance
    get_symbol_info()

    # path to the saved coins_bought file
    coins_bought_file_path = 'coins_bought.json'

    # rolling window of prices; cyclical queue
    historical_prices = [None] * (TIME_DIFFERENCE * RECHECK_INTERVAL)
    hsp_head = -1

    # load historical price for PAIR_WITH
    get_historical_price()

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


    #sort tickers list by volume
    if LIST_AUTOCREATE:
        if LIST_CREATE_TYPE == 'binance':
            tickers_list('create_b')
            tickers=[line.strip() for line in open(TICKERS_LIST)]

        if LIST_CREATE_TYPE == 'tradingview':
            tickers_list('create_ta')
            tickers=[line.strip() for line in open(TICKERS_LIST)]

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
        dynamic_settings(type, TIME_DIFFERENCE, RECHECK_INTERVAL)
        #session calculations like unrealised potential etc
        session('calc')
        time.sleep(settings_struct['RECHECK_INTERVAL'])
