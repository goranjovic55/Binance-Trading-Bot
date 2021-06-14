# Available indicators here: https://python-tradingview-ta.readthedocs.io/en/latest/usage.html#retrieving-the-analysis

from tradingview_ta import TA_Handler, Interval, Exchange
# use for environment variables
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
# Load arguments then parse settings
args = parse_args()
#get config file
DEFAULT_CONFIG_FILE = 'config.yml'
config_file = args.config if args.config else DEFAULT_CONFIG_FILE
parsed_config = load_config(config_file)


OSC_INDICATORS = ['RSI', 'Stoch.RSI'] # Indicators to use in Oscillator analysis
OSC_THRESHOLD = 2 # Must be less or equal to number of items in OSC_INDICATORS
MA_INDICATORS = ['EMA10', 'EMA20'] # Indicators to use in Moving averages analysis
MA_THRESHOLD = 2 # Must be less or equal to number of items in MA_INDICATORS
INTERVAL = Interval.INTERVAL_5_MINUTES #Timeframe for analysis
EXCHANGE = 'BINANCE'
SCREENER = 'CRYPTO'
PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
TICKERS = parsed_config['trading_options']['TICKERS_LIST']
SIGNAL_OUTPUT_PATH = 'signals'
TIME_TO_WAIT = parsed_config['trading_options']['SIGNALS_FREQUENCY'] # Minutes to wait between analysis
FULL_LOG = parsed_config['script_options']['VERBOSE_MODE'] # List analysis result to console

# TODO: check every 1 minute on 5 minute timeframes by keeping a circular buffer array
global last_RSI
last_RSI = {}

def analyze(pairs):
    global last_RSI

    signal_coins = {}
    analysis = {}
    handler = {}

    if os.path.exists(f'{SIGNAL_OUTPUT_PATH}/custsignalmod.exs'):
        os.remove(f'{SIGNAL_OUTPUT_PATH}/custsignalmod.exs')

    for pair in pairs:
        handler[pair] = TA_Handler(
            symbol=pair,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval=INTERVAL,
            timeout= 10)

    for pair in pairs:
        try:
            analysis = handler[pair].get_analysis()
        except Exception as e:
            print("Signalsample:")
            print("Exception:")
            print(e)
            print (f'Coin: {pair}')
            print (f'handler: {handler[pair]}')

        oscCheck=0
        maCheck=0
        for indicator in OSC_INDICATORS:
            oscResult = analysis.oscillators ['COMPUTE'][indicator]
            #print(f'Indicator for {indicator} is {oscResult}')
            if analysis.oscillators ['COMPUTE'][indicator] != 'SELL': oscCheck +=1

        for indicator in MA_INDICATORS:
            if analysis.moving_averages ['COMPUTE'][indicator] == 'BUY': maCheck +=1

        # TODO: Use same type of analysis for sell indicators

        # Stoch.RSI (25 - 52) & Stoch.RSI.K > Stoch.RSI.D, RSI (49-67), EMA10 > EMA20 > EMA100, Stoch.RSI = BUY, RSI = BUY, EMA10 = EMA20 = BUY
        RSI = float(analysis.indicators['RSI'])
        STOCH_RSI_K = float(analysis.indicators['Stoch.RSI.K'])
        # STOCH_RSI_D = float(analysis.indicators['Stoch.D'])
        EMA10 = float(analysis.indicators['EMA10'])
        EMA20 = float(analysis.indicators['EMA20'])
        EMA100 = float(analysis.indicators['EMA100'])
        STOCH_K = float(analysis.indicators['Stoch.K'])
        STOCH_D = float(analysis.indicators['Stoch.D'])

        #print(f'Custsignalmod: {pair} stats = RSI:{RSI}, STOCH_RSI_K:{STOCH_RSI_K}, STOCH_K:{STOCH_K}, STOCH_D:{STOCH_D} EMA10:{EMA10}, EMA20:{EMA20}, EMA100:{EMA100}')
        if pair in last_RSI and (RSI - last_RSI[pair] >= 2.5) and (RSI >= 49 and RSI <= 67) and (STOCH_RSI_K >= 25 and STOCH_RSI_K <= 58) and \
            '''(EMA10 > EMA20 and EMA20 > EMA100)''' and (STOCH_K - STOCH_D >= 4.5):

            if oscCheck >= OSC_THRESHOLD and maCheck >= MA_THRESHOLD:
                signal_coins[pair] = pair

                if FULL_LOG:
                    print(f'\033[92mCustsignalmod: Signal detected on {pair} at {oscCheck}/{len(OSC_INDICATORS)} oscillators and {maCheck}/{len(MA_INDICATORS)} moving averages.')
                with open('signals/custsignalmod.exs','a+') as f:
                    f.write(pair + '\n')

        last_RSI[pair] = RSI
            print(f'Custsignalmod:{pair} Oscillators:{oscCheck}/{len(OSC_INDICATORS)} Moving averages:{maCheck}/{len(MA_INDICATORS)}')

    return signal_coins

def do_work():
    signal_coins = {}
    pairs = {}

    pairs=[line.strip() for line in open(TICKERS)]
    for line in open(TICKERS):
        pairs=[line.strip() + PAIR_WITH for line in open(TICKERS)]

    while True:
        if not threading.main_thread().is_alive(): exit()
        signal_coins = analyze(pairs)
        if FULL_LOG:
            print(f'Custsignalmod: Analyzing {len(pairs)} coins')
            print(f'Custsignalmod: {len(signal_coins)} coins above {OSC_THRESHOLD}/{len(OSC_INDICATORS)} oscillators and {MA_THRESHOLD}/{len(MA_INDICATORS)} moving averages Waiting {TIME_TO_WAIT} minutes for next analysis.')
        time.sleep((TIME_TO_WAIT*60))
