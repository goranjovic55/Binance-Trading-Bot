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

from bot.settings import *

def dynamic_settings(type: str, TIME_DIFFERENCE: float, RECHECK_INTERVAL: float) -> None:
    global session_struct, settings_struct, trading_struct

    DYNAMIC_STOP_LOSS = settings_struct['STOP_LOSS']

    STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
    TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
    TIME_DIFFERENCE = parsed_config['trading_options']['TIME_DIFFERENCE']
    DYNAMIC_MIN_MAX = parsed_config['trading_options']['DYNAMIC_MIN_MAX']
    HOLDING_PRICE_THRESHOLD = parsed_config['trading_options']['HOLDING_PRICE_THRESHOLD']
    TRADE_SLOTS = parsed_config['trading_options']['TRADE_SLOTS']

# calculate and define win/loss percent for STOPLOSS calculations

    if (session_struct['win_trade_count'] > 0) and (session_struct['loss_trade_count'] > 0):
        WIN_LOSS_PERCENT = round((session_struct['win_trade_count'] / (session_struct['win_trade_count'] + session_struct['loss_trade_count'])) * 100, 2)
    else:
        WIN_LOSS_PERCENT = 100

    if DYNAMIC_SETTINGS:

#limiting STOP_LOSS TIME_DIFFERENCE and TRAILING_STOP_LOSS to dynamic min and max values
        if settings_struct['STOP_LOSS'] < STOP_LOSS / DYNAMIC_MIN_MAX:
           settings_struct['STOP_LOSS'] = STOP_LOSS / DYNAMIC_MIN_MAX

        if settings_struct['TRAILING_STOP_LOSS'] < TRAILING_STOP_LOSS / DYNAMIC_MIN_MAX:
           settings_struct['TRAILING_STOP_LOSS'] = TRAILING_STOP_LOSS /DYNAMIC_MIN_MAX

# modifying of STOPLOSS based on closedtrades/tradeslots * win/loss percent and trailing stoploss based on profit to trade ratio
# so we can not loose more than we can afford to

        if session_struct['closed_trades_percent'] > 0 and WIN_LOSS_PERCENT > 0 and session_struct['trade_slots'] > 0 and trading_struct['stop_loss_adjust'] == True:
           DYNAMIC_STOP_LOSS = session_struct['closed_trades_percent'] / TRADE_SLOTS * WIN_LOSS_PERCENT / 100
           settings_struct['STOP_LOSS'] = (settings_struct['STOP_LOSS'] + DYNAMIC_STOP_LOSS) / 2
           settings_struct['TRAILING_STOP_LOSS'] = settings_struct['TRAILING_STOP_LOSS'] + session_struct['profit_to_trade_ratio'] / 2
           trading_struct['stop_loss_adjust'] = False

        if settings_struct['TIME_DIFFERENCE'] < TIME_DIFFERENCE / DYNAMIC_MIN_MAX:
           settings_struct['TIME_DIFFERENCE'] = TIME_DIFFERENCE / DYNAMIC_MIN_MAX

        #if settings_struct['STOP_LOSS'] > STOP_LOSS * DYNAMIC_MIN_MAX:
           #settings_struct['STOP_LOSS'] = STOP_LOSS * DYNAMIC_MIN_MAX
        if settings_struct['TIME_DIFFERENCE'] > TIME_DIFFERENCE * DYNAMIC_MIN_MAX:
           settings_struct['TIME_DIFFERENCE'] = TIME_DIFFERENCE * DYNAMIC_MIN_MAX
        if settings_struct['TRAILING_STOP_LOSS'] > STOP_LOSS * DYNAMIC_MIN_MAX:
           settings_struct['TRAILING_STOP_LOSS'] = TRAILING_STOP_LOSS * DYNAMIC_MIN_MAX

        if settings_struct['HOLDING_PRICE_THRESHOLD'] < HOLDING_PRICE_THRESHOLD:
           settings_struct['HOLDING_PRICE_THRESHOLD'] = HOLDING_PRICE_THRESHOLD

# this part checks to see if last trade was a win if it was it checks to see what was previous dynamics state and if it was up
# it will go up with TIMEDIFFERENCE by % percent and if it was down it will go down with it, also it will TRIGGER
# all other settings adding % on every win

        if session_struct['last_trade_won'] == True:
            if session_struct['dynamics_state'] == 'up':
               settings_struct['TIME_DIFFERENCE'] = settings_struct['TIME_DIFFERENCE'] + (settings_struct['TIME_DIFFERENCE'] * DYNAMIC_WIN_LOSS_UP) /100
               session_struct['dynamics_state'] = 'up'

            if session_struct['dynamics_state'] == 'down':
               settings_struct['TIME_DIFFERENCE'] = settings_struct['TIME_DIFFERENCE'] - (settings_struct['TIME_DIFFERENCE'] * DYNAMIC_WIN_LOSS_UP) /100
               session_struct['dynamics_state'] = 'down'

           session_struct['last_trade_won'] = 'none'
           type = 'performance_adjust_up'

# this code will change "direction" for timedifference change aka if it was up it will go down and vice versa on next win
# to prevent accumulating losses on same timedifference and to sync with market better, also it will subtract all other
# dynamic settings by corresponding numberes to protect from consecutive losses

        if session_struct['last_trade_won'] == False:
           if session_struct['dynamics_state'] == 'up':
              session_struct['dynamics_state'] = 'down'

           if session_struct['dynamics_state'] == 'down':
              session_struct['dynamics_state'] = 'up'

           session_struct['last_trade_won'] = 'none'
           type = 'performance_adjust_down'

# this part of code jumps to different part of timedifference scale this is to protect from consecutive losses
# and to change context so bot goes from 5 minute range to 50 minute range for example if those were corresponding
# scale values, it jumps on 2 consecutive losses

        if trading_struct['consecutive_loss'] > 1:
           if settings_struct['TIME_DIFFERENCE'] > TIME_DIFFERENCE:
              settings_struct['TIME_DIFFERENCE'] = TIME_DIFFERENCE - (settings_struct['TIME_DIFFERENCE'] / TIME_DIFFERENCE * TIME_DIFFERENCE/DYNAMIC_MIN_MAX)
              print(f"TIMEFRAME JUMP TRIGGERED! TIME_DIFFERENCE: {settings_struct['TIME_DIFFERENCE']}")

           if settings_struct['TIME_DIFFERENCE'] < TIME_DIFFERENCE:
              settings_struct['TIME_DIFFERENCE'] = (TIME_DIFFERENCE * DYNAMIC_MIN_MAX) - (settings_struct['TIME_DIFFERENCE']/TIME_DIFFERENCE * TIME_DIFFERENCE * DYNAMIC_MIN_MAX)
              print(f"TIMEFRAME JUMP TRIGGERED! TIME_DIFFERENCE: {settings_struct['TIME_DIFFERENCE']}")

           trading_struct['consecutive_loss'] = 0


        #print(f'{txcolors.NOTICE}>> TRADE_WON: {session_struct['last_trade_won']} and DYNAMICS_STATE: {session_struct['dynamics_state']} <<<{txcolors.DEFAULT}')

# this part of code alteres trading settings for next trade based on win/loss so if we win all our settings get more
# if we loose they get less so we protect from consecutive losses and we are more "brave" on consecutive wins

        if type == 'performance_adjust_up':
            settings_struct['STOP_LOSS'] = settings_struct['STOP_LOSS'] + (settings_struct['STOP_LOSS'] * DYNAMIC_WIN_LOSS_UP) / 100
            settings_struct['TAKE_PROFIT'] = settings_struct['TAKE_PROFIT'] + (settings_struct['TAKE_PROFIT'] * DYNAMIC_WIN_LOSS_UP) / 100
            settings_struct['TRAILING_STOP_LOSS'] = settings_struct['TRAILING_STOP_LOSS'] + (settings_struct['TRAILING_STOP_LOSS'] * DYNAMIC_WIN_LOSS_UP) / 100
            settings_struct['CHANGE_IN_PRICE_MAX'] = settings_struct['CHANGE_IN_PRICE_MAX'] - (settings_struct['CHANGE_IN_PRICE_MAX'] * DYNAMIC_WIN_LOSS_UP) /100
            settings_struct['CHANGE_IN_PRICE_MIN'] = settings_struct['CHANGE_IN_PRICE_MIN'] + (settings_struct['CHANGE_IN_PRICE_MIN'] * DYNAMIC_WIN_LOSS_UP) /100
            settings_struct['DYNAMIC_CHANGE_IN_PRICE'] = settings_struct['DYNAMIC_CHANGE_IN_PRICE'] - (settings_struct['DYNAMIC_CHANGE_IN_PRICE'] * DYNAMIC_WIN_LOSS_UP) / 100 \
                                                         - (settings_struct['DYNAMIC_CHANGE_IN_PRICE'] * settings_struct['TIME_DIFFERENCE']) / 100
            settings_struct['HOLDING_PRICE_THRESHOLD'] = settings_struct['HOLDING_PRICE_THRESHOLD'] + (settings_struct['HOLDING_PRICE_THRESHOLD'] * DYNAMIC_WIN_LOSS_UP) / 100
            session_struct['dynamic'] = 'none'

            print(f"{txcolors.NOTICE}>> DYNAMICS_UP Changing STOP_LOSS: {settings_struct['STOP_LOSS']:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} - TAKE_PROFIT: {settings_struct['TAKE_PROFIT']:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} - TRAILING_STOP_LOSS: {settings_struct['TRAILING_STOP_LOSS']:.2f}/{DYNAMIC_WIN_LOSS_UP:.2f} CIP:{settings_struct['CHANGE_IN_PRICE_MIN']:.4f}/{settings_struct['CHANGE_IN_PRICE_MAX']:.4f}/{DYNAMIC_WIN_LOSS_UP:.2f} HTL: {settings_struct['HOLDING_TIME_LIMIT']:.2f} TD: {settings_struct['TIME_DIFFERENCE']} RI: {settings_struct['RECHECK_INTERVAL']} <<{txcolors.DEFAULT}")

        if type == 'performance_adjust_down':
            settings_struct['STOP_LOSS'] = settings_struct['STOP_LOSS'] - (settings_struct['STOP_LOSS'] * DYNAMIC_WIN_LOSS_DOWN) / 100
            settings_struct['TAKE_PROFIT'] = settings_struct['TAKE_PROFIT'] - (settings_struct['TAKE_PROFIT'] * DYNAMIC_WIN_LOSS_DOWN) / 100
            settings_struct['TRAILING_STOP_LOSS'] = settings_struct['TRAILING_STOP_LOSS'] - (settings_struct['TRAILING_STOP_LOSS'] * DYNAMIC_WIN_LOSS_DOWN) / 100
            settings_struct['CHANGE_IN_PRICE_MAX'] = settings_struct['CHANGE_IN_PRICE_MAX'] + (settings_struct['CHANGE_IN_PRICE_MAX'] * DYNAMIC_WIN_LOSS_DOWN) /100
            settings_struct['CHANGE_IN_PRICE_MIN'] = settings_struct['CHANGE_IN_PRICE_MIN'] - (settings_struct['CHANGE_IN_PRICE_MIN'] * DYNAMIC_WIN_LOSS_DOWN) /100
            settings_struct['DYNAMIC_CHANGE_IN_PRICE'] = settings_struct['DYNAMIC_CHANGE_IN_PRICE'] + (settings_struct['DYNAMIC_CHANGE_IN_PRICE'] * DYNAMIC_WIN_LOSS_DOWN) / 100 \
                                                         + (settings_struct['DYNAMIC_CHANGE_IN_PRICE'] * settings_struct['TIME_DIFFERENCE']) / 100
            settings_struct['HOLDING_PRICE_THRESHOLD'] = settings_struct['HOLDING_PRICE_THRESHOLD'] - (settings_struct['HOLDING_PRICE_THRESHOLD'] * DYNAMIC_WIN_LOSS_DOWN) / 100
            session_struct['dynamic'] = 'none'

            print(f"{txcolors.NOTICE}>> DYNAMICS_DOWN Changing STOP_LOSS: {settings_struct['STOP_LOSS']:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TAKE_PROFIT: {settings_struct['TAKE_PROFIT']:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} - TRAILING_STOP_LOSS: {settings_struct['TRAILING_STOP_LOSS']:.2f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} CIP:{settings_struct['CHANGE_IN_PRICE_MIN']:.4f}/{settings_struct['CHANGE_IN_PRICE_MAX']:.4f}/{DYNAMIC_WIN_LOSS_DOWN:.2f} HTL: {settings_struct['HOLDING_TIME_LIMIT']:.2f} TD: {settings_struct['TIME_DIFFERENCE']} RI: {settings_struct['RECHECK_INTERVAL']} <<{txcolors.DEFAULT}")

# this code makes our market resistance and support levels triggres for buys and also applyies our dynamics based on wins/losses

        if type == 'mrs_settings':
           if session_struct['prices_grabbed'] == True:
              settings_struct['CHANGE_IN_PRICE_MIN'] = session_struct['market_support'] + (session_struct['market_support'] * settings_struct['DYNAMIC_CHANGE_IN_PRICE']) / 100
              settings_struct['CHANGE_IN_PRICE_MAX'] = session_struct['market_support'] - (session_struct['market_support'] * settings_struct['DYNAMIC_CHANGE_IN_PRICE']) / 100
              settings_struct['TAKE_PROFIT'] = session_struct['market_resistance'] + (session_struct['market_resistance'] * settings_struct['DYNAMIC_CHANGE_IN_PRICE']) / 100

              if session_struct['loss_trade_count'] > 1:
                 trading_struct['trade_support'] = trading_struct['sum_lost_trades'] / session_struct['loss_trade_count']

              if session_struct['win_trade_count'] > 1:
                 trading_struct['trade_resistance'] = trading_struct['sum_won_trades'] / session_struct['win_trade_count']
                 settings_struct['TRAILING_STOP_LOSS'] = trading_struct['trade_resistance']

# this part of code changes time if we use TEST or REAL mode based on timing in each, aka realmode uses miliseconds so we
# multiply for HOLDING TIME LIMIT

        if not TEST_MODE: settings_struct['HOLDING_TIME_LIMIT'] = (settings_struct['TIME_DIFFERENCE'] * 60 * 1000) * HOLDING_INTERVAL_LIMIT
        if TEST_MODE: settings_struct['HOLDING_TIME_LIMIT'] = (settings_struct['TIME_DIFFERENCE'] * 60) * HOLDING_INTERVAL_LIMIT
