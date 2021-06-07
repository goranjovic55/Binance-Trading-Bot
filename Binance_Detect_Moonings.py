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
import os

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


# tracks profit/loss each session
global session_profit, unrealised_percent, market_price, investment_value
global investment_value_gain
investment_value = 0
investment_value_gain = 0
session_profit = 0
unrealised_percent = 0

#gogo MOD WIN/LOSS COunter and global dynamic stoploss and takeprofit and trailing takeprofit etc
global win_trade_count, loss_trade_count
win_trade_count = 0
loss_trade_count = 0

global dynamic, sell_all_coins, tickers_list_changed, exchange_symbol
dynamic = 'none'
sell_all_coins = False
tickers_list_changed = False

global CURRENT_EXPOSURE, TOTAL_GAINS, NEW_BALANCE, INVESTMENT_GAIN
CURRENT_EXPOSURE = 0
NEW_BALANCE = 0

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
    #list below is in the order that Binance displays them, apologies for not using ASC order
    if (PAIR_WITH == ( 'USDT' or 'BUSD' or 'AUD' or 'BRL' or 'EUR' or 'GBP' or 'RUB' or 'TRY' or 'TUSD' or 'USDC' or 'PAX' or 'BIDR' or 'DAI' or 'IDRT' or 'UAH' or 'NGN' or 'VAI' or 'BVND')):
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

    global historical_prices, hsp_head, market_price, exchange_symbol

    initial_price = {}
    prices = client.get_all_tickers()

    for coin in prices:

        if CUSTOM_LIST:
            if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}
        else:
            if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}

    if add_to_historical:
        hsp_head += 1

        if hsp_head == RECHECK_INTERVAL:
            hsp_head = 0

        historical_prices[hsp_head] = initial_price

    if is_fiat():

        market_price = 1
        exchange_symbol = PAIR_WITH

    else:
        exchange_symbol = PAIR_WITH + 'USDT'
        market_historic = client.get_historical_trades(symbol=exchange_symbol)
        market_price = market_historic[0].get('price')

    return initial_price


def wait_for_price(type):
    '''calls the initial price and ensures the correct amount of time has passed
    before reading the current price again'''

    global historical_prices, hsp_head, volatility_cooloff
    volatile_coins = {}
    externals = {}

    coins_up = 0
    coins_down = 0
    coins_unchanged = 0

    pause_bot()

    if historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'] > datetime.now() - timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)):

        # sleep for exactly the amount of time required

        time.sleep((timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)) - (datetime.now() - historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'])).total_seconds())

    report('console', '.')

    # retrieve latest prices
    get_price()

    # calculate the difference in prices
    for coin in historical_prices[hsp_head]:

        # minimum and maximum prices over time period
        min_price = min(historical_prices, key = lambda x: float("inf") if x is None else float(x[coin]['price']))
        max_price = max(historical_prices, key = lambda x: -1 if x is None else float(x[coin]['price']))

        threshold_check = (-1.0 if min_price[coin]['time'] > max_price[coin]['time'] else 1.0) * (float(max_price[coin]['price']) - float(min_price[coin]['price'])) / float(min_price[coin]['price']) * 100

        if type == 'percent_mix_signal':

           # each coin with higher gains than our CHANGE_IN_PRICE is added to the volatile_coins dict if less than TRADE_SLOTS is not reached.
           if threshold_check > CHANGE_IN_PRICE_MIN and threshold_check < CHANGE_IN_PRICE_MAX:
               coins_up +=1

               if os.path.exists('signals/custsignalmod.exs') or os.path.exists('signals/signalsample.exs'):
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
        try:
            os.remove(filename)
        except:
            if DEBUG: print(f"{txcolors.WARNING}Could not remove external signalling file{txcolors.DEFAULT}")

    return external_list


def pause_bot():
    '''Pause the script when external indicators detect a bearish trend in the market'''
    global bot_paused, session_profit, hsp_head, dynamic, sell_all_coins
    # start counting for how long the bot has been paused
    start_time = time.perf_counter()

    while os.path.isfile("signals/paused.exc"):

        if bot_paused == False:
            print(f"{txcolors.WARNING}Buying paused due to negative market conditions, stop loss and take profit will continue to work...{txcolors.DEFAULT}")
            # sell all bought coins if bot is bot_paused
            if STOP_LOSS_ON_PAUSE == True:
               sell_all_coins = True
            bot_paused = True

        # sell all bought coins if bot is bot_paused
        if STOP_LOSS_ON_PAUSE == True:
           sell_all_coins = True

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



        # resume the bot and ser pause_bot to False
        if  bot_paused == True:
            print(f"{txcolors.WARNING}Resuming buying due to positive market conditions, total sleep time: {time_elapsed}{txcolors.DEFAULT}")
            tickers_list(SORT_LIST_TYPE)
            dynamic = 'reset'
            sell_all_coins = False
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


def buy():
    '''Place Buy market orders for each volatile coin found'''
    volume, last_price = convert_volume()
    orders = {}

    for coin in volume:

        # only buy if the there are no active trades on the coin
        if coin not in coins_bought:
            print(f"{txcolors.BUY}Preparing to buy {volume[coin]} {coin}{txcolors.DEFAULT}")

            if TEST_MODE:
                orders[coin] = [{
                    'symbol': coin,
                    'orderId': 0,
                    'time': datetime.now().timestamp()
                }]

                # Log trades
                write_log(f"Buy : {volume[coin]} {coin} - {last_price[coin]['price']}")

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
                    print('Order returned, saving order to file')

                    # Log trade
                    write_log(f"Buy : {volume[coin]} {coin} - {last_price[coin]['price']}")


        else:
            print(f'Signal detected, but there is already an active trade on {coin}')

    return orders, last_price, volume

def sell_coins():
    '''sell coins that have reached the STOP LOSS or TAKE PROFIT threshold'''

    global hsp_head, session_profit, win_trade_count, loss_trade_count, dynamic, sell_all_coins

    last_price = get_price(False) # don't populate rolling window
    #last_price = get_price(add_to_historical=True) # don't populate rolling window
    coins_sold = {}

    for coin in list(coins_bought):
        # define stop loss and take profit
        TP = float(coins_bought[coin]['bought_at']) + (float(coins_bought[coin]['bought_at']) * coins_bought[coin]['take_profit']) / 100
        SL = float(coins_bought[coin]['bought_at']) + (float(coins_bought[coin]['bought_at']) * coins_bought[coin]['stop_loss']) / 100

        LastPrice = float(last_price[coin]['price'])
        # sell fee below would ofc only apply if transaction was closed at the current LastPrice
        sellFee = (coins_bought[coin]['volume'] * LastPrice) * (TRADING_FEE/100)
        BuyPrice = float(coins_bought[coin]['bought_at'])
        buyFee = (coins_bought[coin]['volume'] * BuyPrice) * (TRADING_FEE/100)
        PriceChange = float((LastPrice - BuyPrice) / BuyPrice * 100)

        # check that the price is above the take profit and readjust SL and TP accordingly if trialing stop loss used
        if LastPrice > TP and USE_TRAILING_STOP_LOSS:

            # increasing TP by TRAILING_TAKE_PROFIT (essentially next time to readjust SL)
            coins_bought[coin]['take_profit'] = PriceChange + TRAILING_TAKE_PROFIT
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - TRAILING_STOP_LOSS
            if DEBUG: print(f"{coin} TP reached, adjusting TP {coins_bought[coin]['take_profit']:.{decimals()}f}  and SL {coins_bought[coin]['stop_loss']:.{decimals()}f} accordingly to lock-in profit")
            continue

        # check that the price is below the stop loss or above take profit (if trailing stop loss not used) and sell if this is the case
        if sell_all_coins == True or LastPrice < SL or LastPrice > TP and not USE_TRAILING_STOP_LOSS:
            print(f"{txcolors.SELL_PROFIT if PriceChange >= 0. else txcolors.SELL_LOSS}TP or SL reached, selling {coins_bought[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} : {PriceChange-(buyFee+sellFee):.2f}% Est: {(QUANTITY*(PriceChange-(buyFee+sellFee)))/100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")
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
                # adding maths as this is really hurting my brain
                # example here for buying 1x coin at 5 and selling at 10
                # if buy is 5, fee is 0.00375
                # if sell is 10, fee is 0.0075
                # for the above, buyFee + sellFee = 0.07875
                profit = ((LastPrice - BuyPrice) * coins_sold[coin]['volume']) * (1-(buyFee + sellFee))

                #gogo MOD to trigger trade lost or won and to count lost or won trades
                if profit > 0:
                   win_trade_count = win_trade_count + 1
                   dynamic = 'performance_adjust_up'
                   write_log(f"Sell: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Profit: {profit:.{decimals()}f} {PriceChange-(TRADING_FEE*2):.{decimals()}f}%")
                else:
                   loss_trade_count = loss_trade_count + 1
                   dynamic = 'performance_adjust_down'
                   write_log(f"Sell: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Profit: {profit:.{decimals()}f} {PriceChange-(TRADING_FEE*2):.{decimals()}f}%")

                # LastPrice (10) - BuyPrice (5) = 5
                # 5 * coins_sold (1) = 5
                # 5 * (1-(0.07875)) = 4.60625
                # profit = 4.60625, it seems ok!
#                write_log(f"Sell: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Profit: {profit:.{decimals()}f} {PAIR_WITH} ({PriceChange-(buyFee+sellFee):.2f}%)")
                session_profit = session_profit + (PriceChange-(buyFee+sellFee))

                #print balance report
                report('message', f"Sell: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Profit: {profit:.{decimals()}f} {PriceChange-(TRADING_FEE*2):.{decimals()}f}%")

                tickers_list(SORT_LIST_TYPE)

            continue

        # no action; print once every TIME_DIFFERENCE
        if hsp_head == 1:
            if len(coins_bought) > 0:
                print(f"TP:{TP:.{decimals()}f}:{coins_bought[coin]['take_profit']:.2f} or SL:{SL:.{decimals()}f}:{coins_bought[coin]['stop_loss']:.2f} not yet reached, not selling {coin} for now {BuyPrice} - {LastPrice} : {txcolors.SELL_PROFIT if PriceChange >= 0. else txcolors.SELL_LOSS}{PriceChange-(buyFee+sellFee):.2f}% Est: {(QUANTITY*(PriceChange-(buyFee+sellFee)))/100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")

    if hsp_head == 1 and len(coins_bought) == 0: print(f"No trade slots are currently in use")

    return coins_sold


def update_portfolio(orders, last_price, volume):

    global session_profit

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

        session('save')

        print(f'Order with id {orders[coin][0]["orderId"]} placed and saved to file')
        # print balance report
#        balance_report(f"report")

def remove_from_portfolio(coins_sold):
    '''Remove coins sold due to SL or TP from portfolio'''
    for coin in coins_sold:
        coins_bought.pop(coin)

    with open(coins_bought_file_path, 'w') as file:
        json.dump(coins_bought, file, indent=4)

    session('save')

def write_log(logline):
    timestamp = datetime.now().strftime("%d/%m %H:%M:%S")
    with open(LOG_FILE,'a+') as f:
        f.write(timestamp + ' ' + logline + '\n')

def report(type, reportline):

    global session_profit, CURRENT_EXPOSURE, NEW_BALANCE
    global INVESTMENT_GAIN, TOTAL_GAINS, win_trade_count, loss_trade_count, unrealised_perecent
    global investment_value, investment_value_gain, exchange_symbol

    SETTINGS_STRING = 'TD:'+str(round(TIME_DIFFERENCE, 2))+'>RI:'+str(round(RECHECK_INTERVAL, 2))+'>CIP:'+str(round(CHANGE_IN_PRICE_MIN, 2))+'-'+str(round(CHANGE_IN_PRICE_MAX, 2))+'>SL:'+str(round(STOP_LOSS, 2))+'>TP:'+str(round(TAKE_PROFIT, 2))+'>TSL:'+str(round(TRAILING_STOP_LOSS, 2))+'>TTP:'+str(round(TRAILING_TAKE_PROFIT, 2))

    if len(coins_bought) > 0:
        UNREALISED_PERCENT = unrealised_percent/len(coins_bought)
    else:
        UNREALISED_PERCENT = 0

    #gogo MOD todo more verbose having all the report things in it!!!!!
    if type == 'console':
       print(f"{txcolors.NOTICE}>> Using {len(coins_bought)}/{TRADE_SLOTS} trade slots. OT:{UNREALISED_PERCENT:.2f}%> SP:{session_profit:.2f}%> Est:{TOTAL_GAINS:.{decimals()}f} {PAIR_WITH}> W:{win_trade_count}> L:{loss_trade_count}> IT:{INVESTMENT:.{decimals()}f} {PAIR_WITH}> CE:{CURRENT_EXPOSURE:.{decimals()}f} {PAIR_WITH}> NB:{NEW_BALANCE:.{decimals()}f} {PAIR_WITH}> IV:{investment_value:.2f} {exchange_symbol}> IG:{INVESTMENT_GAIN:.2f}%> IVG:{investment_value_gain:.{decimals()}f} {exchange_symbol} <<{txcolors.DEFAULT}")

    if type == 'message':
       report_string = 'SP:'+str(round(session_profit, 2))+'>CE:'+str(round(CURRENT_EXPOSURE, 4))+'>W:'+str(win_trade_count)+'>L:'+str(loss_trade_count)+'>IG:'+str(round(INVESTMENT_GAIN, 4))+'%'+'>IT:'+str(round(INVESTMENT, 4))+'>NB:'+str(round(NEW_BALANCE, 4))+'>IV:'+str(round(investment_value, 4))+str(exchange_symbol)+'>IGV:'+str(round(investment_value_gain, 4))+'>IVP:'+str(round(investment_value_gain, 4))

       bot_message = SETTINGS_STRING + '\n' + reportline + '\n' + report_string + '\n'

       if TELEGRAM_BOT:
          bot_token = TELEGRAM_BOT_TOKEN
          bot_chatID = TELEGRAM_BOT_ID

#       print(f'Bot Token: {TELEGRAM_BOT_TOKEN} Bot ID: {TELEGRAM_BOT_ID}')
          send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
          response = requests.get(send_text)

#function to perform dynamic stoploss, take profit and trailing stop loss modification on the fly
def dynamic_settings(type, DYNAMIC_WIN_LOSS_UP, DYNAMIC_WIN_LOSS_DOWN, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN):

    global last_trade_won, last_trade_lost, dynamic

    if DYNAMIC_SETTINGS:

      if type == 'performance_adjust_up':
        STOP_LOSS = STOP_LOSS + (STOP_LOSS * DYNAMIC_WIN_LOSS_UP) / 100
        TAKE_PROFIT = TAKE_PROFIT + (TAKE_PROFIT * DYNAMIC_WIN_LOSS_UP) / 100
        TRAILING_STOP_LOSS = TRAILING_STOP_LOSS + (TRAILING_STOP_LOSS * DYNAMIC_WIN_LOSS_UP) / 100
        CHANGE_IN_PRICE_MAX = CHANGE_IN_PRICE_MAX + (CHANGE_IN_PRICE_MAX * DYNAMIC_WIN_LOSS_DOWN) /100
        CHANGE_IN_PRICE_MIN = CHANGE_IN_PRICE_MIN - (CHANGE_IN_PRICE_MIN * DYNAMIC_WIN_LOSS_DOWN) /100
        dynamic = 'none'
        print(f'{txcolors.NOTICE}>> Last Trade WON Changing STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f}  - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} <<{txcolors.DEFAULT}')

      if type == 'performance_adjust_down':
        STOP_LOSS = STOP_LOSS - (STOP_LOSS * DYNAMIC_WIN_LOSS_DOWN) / 100
        TAKE_PROFIT = TAKE_PROFIT - (TAKE_PROFIT * DYNAMIC_WIN_LOSS_DOWN) / 100
        TRAILING_STOP_LOSS = TRAILING_STOP_LOSS - (TRAILING_STOP_LOSS * DYNAMIC_WIN_LOSS_DOWN) / 100
        CHANGE_IN_PRICE_MAX = CHANGE_IN_PRICE_MAX - (CHANGE_IN_PRICE_MAX * DYNAMIC_WIN_LOSS_DOWN) /100
        CHANGE_IN_PRICE_MIN = CHANGE_IN_PRICE_MIN + (CHANGE_IN_PRICE_MIN * DYNAMIC_WIN_LOSS_DOWN) /100
        dynamic = 'none'
        print(f'{txcolors.NOTICE}>> Last Trade LOST Changing STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}  - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} <<{txcolors.DEFAULT}')

      if type == 'reset':
        STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
        TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
        TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
        CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX']
        CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN']
        print(f'{txcolors.NOTICE}>> DYNAMIC SETTINGS RESET - STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}  - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} <<{txcolors.DEFAULT}')

    return STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN

#various session calculations like uptime 24H gain profit risk to reward ratio unrealised profit etc
def session(type):

    global unrealised_percent, investment_value, investment_value_gain
    global NEW_BALANCE, INVESTMENT_TOTAL, TOTAL_GAINS, INVESTMENT_GAIN
    global market_price, session_profit, win_trade_count, loss_trade_count

    if type == 'calc':

       TOTAL_GAINS = ((QUANTITY * session_profit) / 100)
       NEW_BALANCE = (INVESTMENT + TOTAL_GAINS)
       INVESTMENT_GAIN = (TOTAL_GAINS / INVESTMENT) * 100
       CURRENT_EXPOSURE = (QUANTITY * len(coins_bought))
       unrealised_percent = 0

       for coin in list(coins_bought):
           LastPrice = float(last_price[coin]['price'])

           # sell fee below would ofc only apply if transaction was closed at the current LastPrice
           sellFee = (LastPrice * (TRADING_FEE/100))
           BuyPrice = float(coins_bought[coin]['bought_at'])
           buyFee = (BuyPrice * (TRADING_FEE/100))
           PriceChange = float((LastPrice - BuyPrice) / BuyPrice * 100)
           if len(coins_bought) > 0:
              unrealised_percent = unrealised_percent + (PriceChange-(buyFee+sellFee))

       #this number is your actual ETH or other coin value in correspondence to USDT aka your market investment_value
       #it is important cuz your exchange aha ETH or BTC can vary and if you pause bot during that time you gain profit
       investment_value = float(market_price) * NEW_BALANCE
       investment_value_gain = float(market_price) * (NEW_BALANCE - INVESTMENT)

    if type == 'save':

       session_info = {}
       session_info_file_path = 'session_info.json'
       session_info = {
           'session_profit': session_profit,
           'win_trade_count': win_trade_count,
           'loss_trade_count': loss_trade_count,
#           'investment_value': investment_value,
           'new_balance': NEW_BALANCE,
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

          session_profit = session_info['session_profit']
          win_trade_count = session_info['win_trade_count']
          loss_trade_count = session_info['loss_trade_count']
          #investment_value = session['investment_value']
          NEW_BALANCE = session_info['new_balance']

       TOTAL_GAINS = ((QUANTITY * session_profit) / 100)
       NEW_BALANCE = (INVESTMENT + TOTAL_GAINS)
       INVESTMENT_GAIN = (TOTAL_GAINS / INVESTMENT) * 100

def tickers_list(type):

    global historical_prices, hsp_head, tickers_list_changed

    tickers_list_volume = {}
    tickers_list_price_change = {}

# get all info on tickers from binance
    tickers_binance = client.get_ticker()

#create list with voleume and change in price on our pairs
    for coin in tickers_binance:

        if CUSTOM_LIST:
           if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in FIATS):
              tickers_list_volume[coin['symbol']] = { 'volume': coin['volume']}
              tickers_list_price_change[coin['symbol']] = { 'priceChangePercent': coin['priceChangePercent']}

        else:
           if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
              tickers_list_volume[coin['symbol']] = { 'volume': coin['volume']}
              tickers_list_price_change[coin['symbol']] = { 'priceChangePercent': coin['priceChangePercent']}

#sort tickers by descending order volume and price
    list_tickers_volume = list(sorted( tickers_list_volume.items(), key=lambda x: x[1]['volume'], reverse=True))
    list_tickers_price_change = list(sorted( tickers_list_price_change.items(), key=lambda x: x[1]['priceChangePercent'], reverse=True))

    if type == 'volume' and CUSTOM_LIST:
    #write sorted lists to files

       with open (TICKERS_LIST, 'w') as f:
            for sublist in list_tickers_volume:
               f.writelines(str(sublist[0].replace(PAIR_WITH,''))+'\n')
       tickers_list_changed = True
       print(f'>> Tickers List {TICKERS_LIST} recreated and loaded!! <<')

    if type == 'price_change':
    #write sorted list to files

       with open (TICKERS_LIST, 'w') as f:
            for sublist in list_tickers_price_change:
               f.writelines(str(sublist[0].replace(PAIR_WITH,''))+'\n')
       tickers_list_changed = True
       print(f'>> Tickers List {TICKERS_LIST} recreated and loaded!! <<')

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
#     LOG_TRADES = parsed_config['script_options'].get('LOG_TRADES')
    LOG_FILE = parsed_config['script_options'].get('LOG_FILE')
    DEBUG_SETTING = parsed_config['script_options'].get('DEBUG')
    AMERICAN_USER = parsed_config['script_options'].get('AMERICAN_USER')
    TELEGRAM_BOT =  parsed_config['script_options'].get('TELEGRAM_BOT')

    # Load trading vars
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    INVESTMENT = parsed_config['trading_options']['INVESTMENT']
    TRADE_SLOTS = parsed_config['trading_options']['TRADE_SLOTS']
    FIATS = parsed_config['trading_options']['FIATS']
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

    QUANTITY = INVESTMENT/TRADE_SLOTS

    if DEBUG_SETTING or args.debug:
        DEBUG = True
    # Load creds for correct environment
    access_key, secret_key = load_correct_creds(parsed_creds)

    # Telegram_Bot enabled? # **added by*Coding60plus

    if TELEGRAM_BOT:
       TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ID = load_telegram_creds(parsed_creds)

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
            print('WARNING: Waiting 30 seconds before live trading as a security measure!')
            time.sleep(30)

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

#load previous session stuff
    session('load')

#sort tickers list by volume
    tickers_list(SORT_LIST_TYPE)

    while True:

#reload tickers list by volume if triggered recreation
        if tickers_list_changed == True :
           tickers=[line.strip() for line in open(TICKERS_LIST)]
           tickers_list_changed = False
#           print(f'Tickers list changed and loaded: {tickers}')

        orders, last_price, volume = buy()
        update_portfolio(orders, last_price, volume)
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)

        #gogos MOD to adjust dynamically stoploss trailingstop loss and take profit based on wins
        STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN = dynamic_settings(dynamic, DYNAMIC_WIN_LOSS_UP, DYNAMIC_WIN_LOSS_DOWN, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN)
        #session calculations like unrealised potential etc
        session('calc')
