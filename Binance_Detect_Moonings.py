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
from modules.rsi_signalmod_nigec import FULL_LOG

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

#import bot extension functions including main function for trading
from bot.settings import *
from bot.dynamics import *
from bot.report import *
from bot.session import *
from bot.tickers_list import *
from bot.grab import *
from bot.trade import *

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
           report(SESSION_REPORT_STYLE, '.')

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


if __name__ == '__main__':

    mymodule = {}

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


    # get decimal places for each coin as used by Binance
    get_symbol_info()

    # load historical price for PAIR_WITH
    get_historical_price()

    # seed initial prices
    get_price()

    #load previous session parameters
    session('load')

    #report that bot is started to defined communication channels
    report('message', 'Bot initiated')

    while True:

        pause_bot()

        #main trading function
        trade_crypto()

        #recreate tickers list and reload it
        reload_tickers()

        #use dynamic settings to adjust change in price and take profit based on market support and resistance
        dynamic_settings('mrs_settings', TIME_DIFFERENCE, RECHECK_INTERVAL)

        #gogos MOD to adjust dynamically stoploss trailingstop loss and take profit based on wins
        dynamic_settings(type, TIME_DIFFERENCE, RECHECK_INTERVAL)

        #session calculations like unrealised potential etc
        session('calc')

        #save session data to session_info file
        session('save')

        #write report to console
        if time.time() - session_struct['last_report_time'] > REPORT_FREQUENCY:
            report(SESSION_REPORT_STYLE,'')
            report('console',report_struct['buy_report'])
            report('console',report_struct['sell_report'])

        #sleep for RECHECK_INTERVAL time
        time.sleep(round(settings_struct['RECHECK_INTERVAL']))
