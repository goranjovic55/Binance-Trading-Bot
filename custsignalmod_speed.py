# Available indicators here: https://python-tradingview-ta.readthedocs.io/en/latest/usage.html#retrieving-the-analysis

from tradingview_ta import TA_Handler, Interval, Exchange, get_multiple_analysis
# use for environment variables
import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading

from helpers.parameters import load_config, parse_args



args = parse_args()
config_file = args.config if args.config else 'config.yml'
parsed_config = load_config(config_file)

OSC_INDICATORS = ['MACD', 'Stoch.RSI', 'Mom', 'BBP', 'AO', 'RSI'] # Indicators to use in Oscillator analysis
OSC_THRESHOLD = 3 # Must be less or equal to number of items in OSC_INDICATORS
MA_INDICATORS = ['EMA10', 'EMA20', 'Ichimoku','VWMA'] # Indicators to use in Moving averages analysis
MA_THRESHOLD = 2 # Must be less or equal to number of items in MA_INDICATORS
INTERVAL = Interval.INTERVAL_5_MINUTES #Timeframe for analysis

EXCHANGE = 'BINANCE'
SCREENER = 'CRYPTO'
PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
TICKERS = parsed_config['trading_options']['TICKERS_LIST']
SIGNAL_OUTPUT_PATH = 'signals'
TIME_TO_WAIT = parsed_config['trading_options']['SIGNALS_FREQUENCY'] # Minutes to wait between analysis
FULL_LOG = parsed_config['trading_options']['VERBOSE_MODE'] # List analysis result to console


def analyze(total_pairs):
    signal_coins = {}
    analysis = {}
    handler = {}
#     print(f'Module Path: {os.path.dirname(os.path.realpath(__file__))}')
    if os.path.exists(f'{SIGNAL_OUTPUT_PATH}/custsignalmod.exs'):
        os.remove(f'{SIGNAL_OUTPUT_PATH}/custsignalmod.exs')

    # # Add exchange to pair list...
    exchange_and_pair_list = [f'{EXCHANGE}:{pair}' for pair in total_pairs]
    
    signals_to_buy = []

    # love this name
    multiple_anal = get_multiple_analysis(
        screener=SCREENER, 
        interval=INTERVAL, 
        symbols=exchange_and_pair_list,
        timeout=20)


    for pair_name, analysis in multiple_anal.items():
        pair_without_exchange = pair_name.split(':')[1]
        oscilator_check = 0
        moving_average_check= 0
        
        for indicator in OSC_INDICATORS:
            if analysis.oscillators ['COMPUTE'][indicator] == 'BUY': 
                oscilator_check +=1
        for indicator in MA_INDICATORS:
            if analysis.moving_averages ['COMPUTE'][indicator] == 'BUY': 
                moving_average_check +=1

        if FULL_LOG: print(f'Custsignalmod:{pair_without_exchange} Oscillators:{oscilator_check}/{len(OSC_INDICATORS)} Moving averages:{moving_average_check}/{len(MA_INDICATORS)}')

        if oscilator_check >= OSC_THRESHOLD and moving_average_check >= MA_THRESHOLD:
            signal_coins[pair_without_exchange] = pair_without_exchange
#             print(f'Custsignalmod: Signal detected on {pair_without_exchange} at {oscilator_check}/{len(OSC_INDICATORS)} oscillators and {moving_average_check}/{len(MA_INDICATORS)} moving averages.')
            signals_to_buy.append(pair_without_exchange)

#     print(f'WRITING THIS SHIT: {signals_to_buy}')
    print(f'Custsignalmod: Identified {len(signals_to_buy)}/{len(total_pairs)} coins to execute on')

    # # write all pairs instead of opening the file handler for each one...
    with open(f'{SIGNAL_OUTPUT_PATH}/custsignalmod.exs','a+') as f:
        for item in signals_to_buy:
            f.write(f"{item}\n")
                
#     print(signal_coins)
    return signal_coins

def do_work():
    signal_coins = {}
    pairs = {}

    pairs=[line.strip() for line in open(TICKERS)]
    for line in open(TICKERS):
        pairs=[line.strip() + PAIR_WITH for line in open(TICKERS)] 
    
    while True:
        if not threading.main_thread().is_alive(): exit()
        print(f'Custsignalmod: Analyzing {len(pairs)} coins')
        signal_coins = analyze(pairs)
        print(f'Custsignalmod: {len(signal_coins)} coins above {OSC_THRESHOLD}/{len(OSC_INDICATORS)} oscillators and {MA_THRESHOLD}/{len(MA_INDICATORS)} moving averages Waiting {TIME_TO_WAIT} minutes for next analysis.')
        time.sleep((TIME_TO_WAIT*60))
