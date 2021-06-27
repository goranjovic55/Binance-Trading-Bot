import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading

#gogo MOD telegram needs import request
import requests

# needed for the binance API / websockets / Exception handling
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ReadTimeout, ConnectionError

# used to store trades and sell assets
import json

from helpers.parameters import (
    parse_args, load_config
)

# used for dates
from datetime import date, datetime, timedelta
import time

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key,
    load_telegram_creds
)

from bot.settings import *

# rolling window of prices; cyclical queue
historical_prices = [None] * 2
hsp_head = -1

def is_fiat():
    # check if we are using a fiat as a base currency
    global hsp_head
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    #list below is in the order that Binance displays them, apologies for not using ASC order but this is easier to update later
    fiats = ['USDT', 'BUSD', 'AUD', 'BRL', 'EUR', 'GBP', 'RUB', 'TRY', 'TUSD', \
             'USDC', 'PAX', 'BIDR', 'DAI', 'IDRT', 'UAH', 'NGN', 'VAI', 'BVND']

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
       get_price(add_to_historical=True)
       externals = external_signals()
       session_struct['price_timedelta'] = current_time_minutes
       session_struct['market_resistance'] = 0
       session_struct['market_support'] = 0
       coins_up = 0
       coins_down = 0
       session_struct['prices_grabbed'] = True


       if session_struct['prices_grabbed'] == True:
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
              if threshold_check > settings_struct['CHANGE_IN_PRICE_MIN'] and threshold_check < settings_struct['CHANGE_IN_PRICE_MAX']:

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
                            if session_struct['trade_slots'] + len(volatile_coins) < TRADE_SLOTS or TRADE_SLOTS == 0:
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

                   if session_struct['trade_slots'] + len(volatile_coins) < TRADE_SLOTS or TRADE_SLOTS == 0:
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

    return volatile_coins, len(volatile_coins), historical_prices[hsp_head]
