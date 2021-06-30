import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading

from helpers.parameters import (
    parse_args, load_config
)

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key,
    load_telegram_creds
)

# used for dates
from datetime import date, datetime, timedelta
import time

# used to store trades and sell assets
import json

from bot.settings import *

def session(type):
    #various session calculations like uptime 24H gain profit risk to reward ratio unrealised profit etc
    global session_struct, settings_struct

    if type == 'calc':
        session_struct['TOTAL_GAINS'] = session_struct['session_profit']
        session_struct['NEW_BALANCE'] = (INVESTMENT + session_struct['TOTAL_GAINS'])
        session_struct['INVESTMENT_GAIN'] = (session_struct['TOTAL_GAINS'] / INVESTMENT) * 100
        session_struct['CURRENT_EXPOSURE'] = (QUANTITY * session_struct['trade_slots'])
        session_struct['unrealised_percent'] = 0

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
            'last_trade_won': session_struct['last_trade_won'],
            'TIME_DIFFERENCE': settings_struct['TIME_DIFFERENCE'],
            'RECHECK_INTERVAL': settings_struct['RECHECK_INTERVAL'],
            'CHANGE_IN_PRICE_MIN': settings_struct['CHANGE_IN_PRICE_MIN'],
            'CHANGE_IN_PRICE_MAX': settings_struct['CHANGE_IN_PRICE_MAX'],
            'STOP_LOSS': settings_struct['STOP_LOSS'],
            'TAKE_PROFIT': settings_struct['TAKE_PROFIT'],
            'TRAILING_STOP_LOSS': settings_struct['TRAILING_STOP_LOSS'],
            'TRAILING_TAKE_PROFIT': settings_struct['TRAILING_TAKE_PROFIT'],
            'HOLDING_TIME_LIMIT': settings_struct['HOLDING_TIME_LIMIT'],
            'market_resistance': session_struct['market_resistance'],
            'market_support': session_struct['market_support'],
            'trade_slots': session_struct['trade_slots'],
            
            'trade_support': trading_struct['trade_support'],
            'trade_resistance': trading_struct['trade_resistance']
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
            session_struct['session_uptime'] = session_info['session_uptime']
            session_struct['last_trade_won'] = session_info['last_trade_won']
            session_struct['market_resistance'] = session_info['market_resistance']
            session_struct['market_support'] = session_info['market_support']
            session_struct['trade_slots'] = session_info['trade_slots']

            settings_struct['TIME_DIFFERENCE'] = session_info['TIME_DIFFERENCE']
            settings_struct['RECHECK_INTERVAL'] = session_info['RECHECK_INTERVAL']
            settings_struct['CHANGE_IN_PRICE_MIN'] = session_info['CHANGE_IN_PRICE_MIN']
            settings_struct['CHANGE_IN_PRICE_MAX'] = session_info['CHANGE_IN_PRICE_MAX']
            settings_struct['STOP_LOSS'] = session_info['STOP_LOSS']
            settings_struct['TAKE_PROFIT'] = session_info['TAKE_PROFIT']
            settings_struct['TRAILING_STOP_LOSS'] = session_info['TRAILING_STOP_LOSS']
            settings_struct['TRAILING_TAKE_PROFIT'] = session_info['TRAILING_TAKE_PROFIT']
            settings_struct['HOLDING_TIME_LIMIT'] = session_info['HOLDING_TIME_LIMIT']


        session_struct['TOTAL_GAINS'] = (session_struct['session_profit'])
        session_struct['NEW_BALANCE'] = (INVESTMENT + session_struct['TOTAL_GAINS'])
        session_struct['INVESTMENT_GAIN'] = (session_struct['TOTAL_GAINS'] / INVESTMENT) * 100
