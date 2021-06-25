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

from settings import *

def dynamic_settings(type, DYNAMIC_WIN_LOSS_UP, DYNAMIC_WIN_LOSS_DOWN, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN, HOLDING_TIME_LIMIT, TIME_DIFFERENCE, RECHECK_INTERVAL):

    global session_struct

    if DYNAMIC_SETTINGS:

        if session_struct['last_trade_won'] == True and session_struct['dynamics_state'] == 'up':
           type = 'performance_adjust_up'

        if session_struct['last_trade_won'] == True and session_struct['dynamics_state'] == 'down':
           type = 'performance_adjust_down'

        if session_struct['last_trade_won'] == False and session_struct['dynamics_state'] == 'up':
           type = 'performance_adjust_down'

        if session_struct['last_trade_won'] == False and session_struct['dynamics_state'] == 'down':
           type = 'performance_adjust_up'


        if type == 'performance_adjust_up':
            STOP_LOSS = STOP_LOSS + (STOP_LOSS * DYNAMIC_WIN_LOSS_UP) / 100
            TAKE_PROFIT = TAKE_PROFIT + (TAKE_PROFIT * DYNAMIC_WIN_LOSS_UP) / 100
            TRAILING_STOP_LOSS = TRAILING_STOP_LOSS + (TRAILING_STOP_LOSS * DYNAMIC_WIN_LOSS_UP) / 100
            CHANGE_IN_PRICE_MAX = CHANGE_IN_PRICE_MAX + (CHANGE_IN_PRICE_MAX * DYNAMIC_WIN_LOSS_UP) /100
            CHANGE_IN_PRICE_MIN = CHANGE_IN_PRICE_MIN - (CHANGE_IN_PRICE_MIN * DYNAMIC_WIN_LOSS_UP) /100
            HOLDING_TIME_LIMIT = HOLDING_TIME_LIMIT + (HOLDING_TIME_LIMIT * DYNAMIC_WIN_LOSS_UP) / 100
            TIME_DIFFERENCE = TIME_DIFFERENCE * 2
            RECHECK_INTERVAL = RECHECK_INTERVAL * 2
            session_struct['dynamic'] = 'none'
            session_struct['dynamics_state'] = 'up'
            session_struct['last_trade_won'] = 'none'
            print(f'{txcolors.NOTICE}>> DYNAMICS_UP Changing STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f}  - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL: {HOLDING_TIME_LIMIT:.2f} TD: {TIME_DIFFERENCE} RI: {RECHECK_INTERVAL} <<{txcolors.DEFAULT}')

        if type == 'performance_adjust_down':
            STOP_LOSS = STOP_LOSS - (STOP_LOSS * DYNAMIC_WIN_LOSS_DOWN) / 100
            TAKE_PROFIT = TAKE_PROFIT - (TAKE_PROFIT * DYNAMIC_WIN_LOSS_DOWN) / 100
            TRAILING_STOP_LOSS = TRAILING_STOP_LOSS - (TRAILING_STOP_LOSS * DYNAMIC_WIN_LOSS_DOWN) / 100
            CHANGE_IN_PRICE_MAX = CHANGE_IN_PRICE_MAX - (CHANGE_IN_PRICE_MAX * DYNAMIC_WIN_LOSS_DOWN) /100
            CHANGE_IN_PRICE_MIN = CHANGE_IN_PRICE_MIN + (CHANGE_IN_PRICE_MIN * DYNAMIC_WIN_LOSS_DOWN) /100
            HOLDING_TIME_LIMIT = HOLDING_TIME_LIMIT - (HOLDING_TIME_LIMIT * DYNAMIC_WIN_LOSS_DOWN) / 100
            if TIME_DIFFERENCE != 1: TIME_DIFFERENCE = TIME_DIFFERENCE/2
            if RECHECK_INTERVAL != 1: RECHECK_INTERVAL = RECHECK_INTERVAL/2
            session_struct['dynamic'] = 'none'
            session_struct['dynamics_state'] = 'down'
            session_struct['last_trade_won'] = 'none'
            print(f'{txcolors.NOTICE}>> DYNAMICS_DOWN Changing STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}  - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL:{HOLDING_TIME_LIMIT:.2f}  TD: {TIME_DIFFERENCE} RI: {RECHECK_INTERVAL} <<{txcolors.DEFAULT}')

        if type == 'reset':
            STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
            TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
            TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
            CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX']
            CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN']
            TIME_DIFFERENCE = parsed_config['trading_options']['TIME_DIFFERENCE']

            if not TEST_MODE: HOLDING_TIME_LIMIT = (parsed_config['trading_options']['TIME_DIFFERENCE'] * 60 * 1000) * parsed_config['trading_options']['HOLDING_INTERVAL_LIMIT']
            if TEST_MODE: HOLDING_TIME_LIMIT = (parsed_config['trading_options']['TIME_DIFFERENCE'] * 60) * parsed_config['trading_options']['HOLDING_INTERVAL_LIMIT']

            print(f'{txcolors.NOTICE}>> DYNAMIC SETTINGS RESET - STOP_LOSS: {STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {TAKE_PROFIT:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}  - TRAILING_STOP_LOSS: {TRAILING_STOP_LOSS:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f}CIP:{CHANGE_IN_PRICE_MIN:.4f}/{CHANGE_IN_PRICE_MAX:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL: {HOLDING_TIME_LIMIT:.2f}  TD: {TIME_DIFFERENCE} RI: {RECHECK_INTERVAL} <<{txcolors.DEFAULT}')
            session_struct['dynamic'] = 'none'

        if CHANGE_IN_PRICE_MIN > 0:
            CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN'] - (CHANGE_IN_PRICE_MIN * session_struct['market_support'])
            CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX'] - (CHANGE_IN_PRICE_MAX * session_struct['market_support'])

        if CHANGE_IN_PRICE_MAX < 0:
            CHANGE_IN_PRICE_MIN = parsed_config['trading_options']['CHANGE_IN_PRICE_MIN'] + (CHANGE_IN_PRICE_MIN * session_struct['market_support'])
            CHANGE_IN_PRICE_MAX = parsed_config['trading_options']['CHANGE_IN_PRICE_MAX'] + (CHANGE_IN_PRICE_MAX * session_struct['market_support'])

    return STOP_LOSS, TAKE_PROFIT, TRAILING_STOP_LOSS, CHANGE_IN_PRICE_MAX, CHANGE_IN_PRICE_MIN, HOLDING_TIME_LIMIT, TIME_DIFFERENCE, RECHECK_INTERVAL
