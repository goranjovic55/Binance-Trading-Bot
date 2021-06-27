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
