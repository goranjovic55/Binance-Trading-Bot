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

# Authenticate with the client, Ensure API key is good before continuing
if AMERICAN_USER:
    client = Client(access_key, secret_key, tld='us')
else:
    client = Client(access_key, secret_key)

# Load coins to be ignored from file
ignorelist=[line.strip() for line in open(IGNORE_LIST)]

# Use CUSTOM_LIST symbols if CUSTOM_LIST is set to True
if CUSTOM_LIST: tickers=[line.strip() for line in open(TICKERS_LIST)]

def tickers_list(type: str) -> None:

    global LIST_AUTOCREATE

    tickers_list_volume = {}
    tickers_list_price_change = {}

    # get all info on tickers from binance
    # with retry on error reading
    while True:
        try:
            tickers_binance = client.get_ticker()
        except:
            time.sleep(1)
            continue
        break
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

        if type == 'create_edge':
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


        if type == 'volume' or type == 'price_change':
        #  create list with volume and change in price on our pairs
                for coin in tickers_binance:
                    if CUSTOM_LIST:
                        if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                            tickers_list_volume[coin['symbol']] = { 'volume': float(coin['volume'])}
                            tickers_list_price_change[coin['symbol']] = { 'priceChangePercent': float(coin['priceChangePercent'])}

                    else:
                        if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in EXCLUDED_PAIRS):
                            tickers_list_volume[coin['symbol']] = { 'volume': float(coin['volume'])}
                            tickers_list_price_change[coin['symbol']] = { 'priceChangePercent': float(coin['priceChangePercent'])}

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

        if type == 'volume':
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

def reload_tickers() -> None:
    if session_struct['reload_tickers_list'] == True:
       tickers_list(SORT_LIST_TYPE)
       session_struct['reload_tickers_list'] = False

    #reload tickers list by volume if triggered recreation
    if session_struct['tickers_list_changed'] == True :
        tickers=[line.strip() for line in open(TICKERS_LIST)]
        print(f'>> Tickers RELOADED from tickers!!!{TICKERS_LIST} <<')
        session_struct['tickers_list_changed'] = False
    # print(f'Tickers list changed and loaded: {tickers}')

#sort tickers list by volume
if LIST_AUTOCREATE:
    if LIST_CREATE_TYPE == 'binance':
        tickers_list('create_b')
        tickers=[line.strip() for line in open(TICKERS_LIST)]

    if LIST_CREATE_TYPE == 'tradingview':
        tickers_list('create_ta')
        tickers=[line.strip() for line in open(TICKERS_LIST)]

    if LIST_CREATE_TYPE == 'edgesforledges':
        tickers_list('create_edge')
        tickers=[line.strip() for line in open(TICKERS_LIST)]
