import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading
import subprocess

from helpers.parameters import (
    parse_args, load_config
)

# used to store trades and sell assets
import json

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key,
    load_telegram_creds
)

# needed for the binance API / websockets / Exception handling
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ReadTimeout, ConnectionError

# for colourful logging to the console
class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DIM = '\033[2m\033[35m'
    DEFAULT = '\033[39m'
    NOTICE = '\033[96m'

global historical_prices
global hsp_head
global session_struct
global settings_struct
global trading_struct
global trail_buy_historical
global trail_buy_coins

trail_buy_coins = {}
trail_buy_historical = {}

session_struct = {
     'session_profit': 0,
     'unrealised_percent': 0,
     'market_price': 0,
     'investment_value': 0,
     'investment_value_gain': 0,
     'session_uptime': 0,
     'session_start_time': 0,
     'closed_trades_percent': 0,
     'win_trade_count': 0,
     'loss_trade_count': 0,
     'market_support': 0,
     'market_resistance': 0,
     'dynamic': 'none',
     'sell_all_coins': False,
     'tickers_list_changed': False,
     'exchange_symbol': 'USDT',
     'price_list_counter': 0,
     'CURRENT_EXPOSURE': 0,
     'TOTAL_GAINS': 0,
     'NEW_BALANCE': 0,
     'INVESTMENT_GAIN': 0,
     'STARTUP': True,
     'LIST_AUTOCREATE': False,
     'symbol_info': {},
     'price_timedelta': 0,
     'trade_slots': 0,
     'dynamics_state': 'up',
     'last_trade_won': 2,
     'last_report_time': 0,
     'session_start': False,
     'prices_grabbed': False,
     'reload_tickers_list': True,
     'profit_to_trade_ratio': 0
}

report_struct = {
      'report': '',
      'message': False,
      'log': False
}

def get_git_commit_number():

    try:
       git_commit_count = str(subprocess.check_output(['git', 'rev-list', '--count', 'HEAD']))[:-3][2:]

    except Exception:
        git_commit_count = "NONE"

    return git_commit_count

def decimals():
    # set number of decimals for reporting fractions
    if is_fiat():
        return 2

    return 8

def is_fiat():
    # check if we are using a fiat as a base currency
    global hsp_head
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    #list below is in the order that Binance displays them, apologies for not using ASC order but this is easier to update later
    fiats = ['USDT', 'BUSD', 'AUD', 'BRL', 'EUR', 'GBP', 'RUB', 'TRY', 'TUSD', \
             'USDC', 'PAX', 'BIDR', 'DAI', 'IDRT', 'UAH', 'NGN', 'VAI', 'BVND']

    return bool(PAIR_WITH in fiats)


args = parse_args()

DEFAULT_CONFIG_FILE = 'config.yml'
DEFAULT_CREDS_FILE = 'creds.yml'

config_file = args.config if args.config else DEFAULT_CONFIG_FILE
creds_file = args.creds if args.creds else DEFAULT_CREDS_FILE
parsed_config = load_config(config_file)
parsed_creds = load_config(creds_file)

# Load system vars
TEST_MODE = parsed_config['script_options']['TEST_MODE']
# LOG_TRADES = parsed_config['script_options'].get('LOG_TRADES')
LOG_FILE = parsed_config['script_options'].get('LOG_FILE')
SESSION_REPORT_STYLE = parsed_config['script_options']['SESSION_REPORT_STYLE']
DEBUG_SETTING = parsed_config['script_options'].get('VERBOSE_MODE')
AMERICAN_USER = parsed_config['script_options'].get('AMERICAN_USER')
BOT_MESSAGE_REPORTS =  parsed_config['script_options'].get('BOT_MESSAGE_REPORTS')
BOT_ID = parsed_config['script_options'].get('BOT_ID')
UNIQUE_BUYS = parsed_config['script_options'].get('UNIQUE_BUYS')

# Load trading vars
PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
INVESTMENT = parsed_config['trading_options']['INVESTMENT']
TRADE_SLOTS = parsed_config['trading_options']['TRADE_SLOTS']
EXCLUDED_PAIRS = parsed_config['trading_options']['EXCLUDED_PAIRS']
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
DYNAMIC_CHANGE_IN_PRICE = parsed_config['trading_options']['DYNAMIC_CHANGE_IN_PRICE']
DYNAMIC_SETTINGS = parsed_config['trading_options']['DYNAMIC_SETTINGS']
DYNAMIC_MIN_MAX = parsed_config['trading_options']['DYNAMIC_MIN_MAX']
HOLDING_PRICE_THRESHOLD = parsed_config['trading_options']['HOLDING_PRICE_THRESHOLD']
TRAILING_BUY_THRESHOLD = parsed_config['trading_options']['TRAILING_BUY_THRESHOLD']
STOP_LOSS_ON_PAUSE = parsed_config['trading_options']['STOP_LOSS_ON_PAUSE']
PERCENT_SIGNAL_BUY = parsed_config['trading_options']['PERCENT_SIGNAL_BUY']
SORT_LIST_TYPE = parsed_config['trading_options']['SORT_LIST_TYPE']
LIST_AUTOCREATE = parsed_config['trading_options']['LIST_AUTOCREATE']
LIST_CREATE_TYPE = parsed_config['trading_options']['LIST_CREATE_TYPE']
IGNORE_LIST = parsed_config['trading_options']['IGNORE_LIST']

REPORT_FREQUENCY = parsed_config['script_options']['REPORT_FREQUENCY']
HOLDING_INTERVAL_LIMIT = parsed_config['trading_options']['HOLDING_INTERVAL_LIMIT']
QUANTITY = INVESTMENT/TRADE_SLOTS

if not TEST_MODE: 
    HOLDING_TIME_LIMIT = (TIME_DIFFERENCE * 60 * 1000) * HOLDING_INTERVAL_LIMIT
else:
    HOLDING_TIME_LIMIT = (TIME_DIFFERENCE * 60) * HOLDING_INTERVAL_LIMIT

settings_struct = {
      'TIME_DIFFERENCE': TIME_DIFFERENCE,
      'RECHECK_INTERVAL': RECHECK_INTERVAL,
      'CHANGE_IN_PRICE_MIN': CHANGE_IN_PRICE_MIN,
      'CHANGE_IN_PRICE_MAX': CHANGE_IN_PRICE_MAX,
      'STOP_LOSS': STOP_LOSS,
      'TAKE_PROFIT': TAKE_PROFIT,
      'TRAILING_STOP_LOSS': TRAILING_STOP_LOSS,
      'TRAILING_TAKE_PROFIT': TRAILING_TAKE_PROFIT,
      'HOLDING_TIME_LIMIT': HOLDING_TIME_LIMIT,
      'DYNAMIC_CHANGE_IN_PRICE': DYNAMIC_CHANGE_IN_PRICE,
      'SESSION_REPORT_STYLE': SESSION_REPORT_STYLE,
      'HOLDING_PRICE_THRESHOLD': HOLDING_PRICE_THRESHOLD,
      'TRAILING_BUY_THRESHOLD': TRAILING_BUY_THRESHOLD
}

trading_struct = {
      'holding_timeout_dynamic': 'up',
      'holding_timeout_sell': 'none',
      'lost_trade_percent': 0,
      'won_trade_percent': 0,
      'trade_support': 0,
      'trade_resistance': 0,
      'sum_won_trades': settings_struct['TRAILING_STOP_LOSS'],
      'sum_lost_trades': -settings_struct['STOP_LOSS'],
      'max_holding_price': 0,
      'min_holding_price': 0,
      'sum_min_holding_price': 0,
      'sum_max_holding_price': 0,
      'consecutive_loss': 0,
}

# Default no debugging
DEBUG = False

if DEBUG_SETTING or args.debug:
    DEBUG = True
# Load creds for correct environment
access_key, secret_key = load_correct_creds(parsed_creds)

# Telegram_Bot enabled? # **added by*Coding60plus

if BOT_MESSAGE_REPORTS:
    TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ID, TEST_DISCORD_WEBHOOK, LIVE_DISCORD_WEBHOOK = load_telegram_creds(parsed_creds)

# set to false at Start
global bot_paused
bot_paused = False

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

# Telegram_Bot enabled? # **added by*Coding60plus
if DEBUG:
    print(f'Loaded config below\n{json.dumps(parsed_config, indent=4)}')
    print(f'Your credentials have been loaded from {creds_file}')

# Load coins to be ignored from file
ignorelist=[line.strip() for line in open(IGNORE_LIST)]

# Use CUSTOM_LIST symbols if CUSTOM_LIST is set to True
if CUSTOM_LIST: 
    tickers=[line.strip() 
    for line in open(TICKERS_LIST)]

# prevent including a coin in volatile_coins if it has already appeared there less than TIME_DIFFERENCE minutes ago
volatility_cooloff = {}

# try to load all the coins bought by the bot if the file exists and is not empty
coins_bought = {}

# path to the saved coins_bought file
coins_bought_file_path = 'coins_bought.json'

# use separate files for testing and live trading
if TEST_MODE:
   coins_bought_file_path = 'test_' + coins_bought_file_path

# if saved coins_bought json file exists and it's not empty then load it
if os.path.isfile(coins_bought_file_path) and os.stat(coins_bought_file_path).st_size!= 0:
    with open(coins_bought_file_path) as file:
            coins_bought = json.load(file)

# Initiate the conneciton error counters
READ_TIMEOUT_COUNT=0
CONNECTION_ERROR_COUNT = 0
