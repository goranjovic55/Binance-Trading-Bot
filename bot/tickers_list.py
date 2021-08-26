import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading

#gogo MOD telegram needs import request
import requests
import re

# needed for the binance API / websockets / Exception handling
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ReadTimeout, ConnectionError

# used to store trades and sell assets
import json

from helpers.parameters import (
    parse_args, load_config
)

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key,
    load_telegram_creds
)

from bot.settings import *

def tickers_list() -> None:

    global LIST_AUTOCREATE, LIST_CREATE_TYPE, SORT_LIST_TYPE, session_struct

    # Load coins to be ignored from file
    ignorelist=[line.strip() for line in open(IGNORE_LIST)]

    # Use CUSTOM_LIST symbols if CUSTOM_LIST is set to True
    if CUSTOM_LIST: 
        session_struct['tickers']=[line.strip() for line in open(TICKERS_LIST)]

    tickers_sort = {}

    # get all info on tickers from binance
    # with retry on error reading
    while True:
        try:
            tickers_binance = client.get_ticker()
        except:
            print(f"{txcolors.WARNING}Binance Problem Get Tickers{txcolors.DEFAULT}")
            time.sleep(1)
            continue
        break

    if LIST_AUTOCREATE:
    # pull coins from trading view and create a list
        if LIST_CREATE_TYPE == 'tradingview':
            response = requests.get('https://scanner.tradingview.com/crypto/scan')
            ta_data = response.json()
            signals_file = open(TICKERS_LIST,'w')
            with open (TICKERS_LIST, 'w') as f:
                for i in ta_data['data']:
                    if i['s'][:7]=='BINANCE' and i['s'][-len(PAIR_WITH):] == PAIR_WITH and i['s'][8:-len(PAIR_WITH)] not in ignorelist:
                        f.writelines(str(i['s'][8:-len(PAIR_WITH)])+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers CREATED from TradingView tickers!!!{TICKERS_LIST} <<')

        if LIST_CREATE_TYPE == 'edgesforledges':
            url = 'http://edgesforledges.com/watchlists/download/binance/' + LIST_CREATE_TYPE_OPTION
            response = requests.get(url)
            signals_file = open(TICKERS_LIST,'w')
            with open (TICKERS_LIST, 'w') as f:
                for line in response.text.splitlines():
                    if line.endswith(PAIR_WITH):
                        coin = re.sub(r'BINANCE:(.*)'+PAIR_WITH,r'\1',line)
                        if coin not in ignorelist:
                            f.writelines(coin+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers CREATED from {url} tickers!!!{TICKERS_LIST} <<')

        # pull coins from binance and create list
        if LIST_CREATE_TYPE == 'binance':
            with open (TICKERS_LIST, 'w') as f:
                for ticker in tickers_binance:
                    if ticker['symbol'].endswith(PAIR_WITH):
                        coin = ticker['symbol'].replace(PAIR_WITH,"")
                        if coin not in ignorelist:
                            f.writelines(coin+'\n')
            session_struct['tickers_list_changed'] = True
            print(f'>> Tickers CREATED from Binance tickers!!!{TICKERS_LIST} <<')

        # Reload Tickers
        session_struct['tickers']=[line.strip() for line in open(TICKERS_LIST)]

    if SORT_LIST_TYPE == 'volume' or SORT_LIST_TYPE == 'price_change':
    #  create list with volume and change in price on our pairs
        for coin in tickers_binance:
            if any(item + PAIR_WITH == coin['symbol'] for item in session_struct['tickers']) and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                if SORT_LIST_TYPE == 'volume':
                    tickers_sort[coin['symbol']] = { 'volume': Decimal(coin['volume'])}
                if SORT_LIST_TYPE == 'price_change':    
                    tickers_sort[coin['symbol']] = { 'priceChangePercent': Decimal(coin['priceChangePercent'])}

        # sort tickers by descending order volume and price
        if SORT_LIST_TYPE == 'volume':
            tickers_sort = list(sorted( tickers_sort.items(), key=lambda x: x[1]['volume'], reverse=True))
        if SORT_LIST_TYPE == 'price_change':    
            tickers_sort = list(sorted( tickers_sort.items(), key=lambda x: x[1]['priceChangePercent'], reverse=True))

        # write sorted lists to files
        with open (TICKERS_LIST, 'w') as f:
                for sublist in tickers_sort:
                    f.writelines(str(sublist[0].replace(PAIR_WITH,''))+'\n')
        session_struct['tickers_list_changed'] = True

        print(f'>> Tickers sort List {TICKERS_LIST} by {SORT_LIST_TYPE}<<')
        session_struct['tickers']=[line.strip() for line in open(TICKERS_LIST)]

    session_struct['tickers_list_changed'] = False
    session_struct['reload_tickers_list'] = False    

def reload_tickers() -> None:
    if session_struct['reload_tickers_list'] == True:
       tickers_list()

tickers_list()