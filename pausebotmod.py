from helpers.parameters import (
    parse_args, load_config
)
# Load arguments then parse settings
args = parse_args()
#get config file
DEFAULT_CONFIG_FILE = 'config.yml'
config_file = args.config if args.config else DEFAULT_CONFIG_FILE
parsed_config = load_config(config_file)

from tradingview_ta import TA_Handler, Interval, Exchange
import os
import time
import threading

INTERVAL = Interval.INTERVAL_1_MINUTE #Timeframe for analysis

EXCHANGE = 'BINANCE'
SCREENER = 'CRYPTO'
SYMBOL = parsed_config['trading_options']['PAIR_WITH'] + 'USDT'
TYPE = 'SELL'
THRESHOLD = parsed_config['trading_options']['PAUSEBOTMOD_THRESHOLD'] # 7 of 15 MA's indicating sell
TIME_TO_WAIT = parsed_config['trading_options']['TIME_DIFFERENCE'] # Minutes to wait between analysis
FULL_LOG = parsed_config['trading_options']['VERBOSE_MODE'] # List analysis result to console

def analyze():
    analysis = {}
    handler = {}

    handler = TA_Handler(
            symbol=SYMBOL,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval=INTERVAL,
            timeout= 10)

    try:
        analysis = handler.get_analysis()
    except Exception as e:
        print("pausebotmod:")
        print("Exception:")
        print(e)

    ma_analysis = analysis.moving_averages[TYPE]
    if ma_analysis >= THRESHOLD:
        paused = True
        print(f'pausebotmod: {SYMBOL} Market not looking too good, bot paused from buying {ma_analysis}/{THRESHOLD} Waiting {TIME_TO_WAIT} minutes for next market checkup')
    else:
        print(f'pausebotmod: {SYMBOL} Market looks ok, bot is running {ma_analysis}/{THRESHOLD} Waiting {TIME_TO_WAIT} minutes for next market checkup ')
        paused = False

    return paused
#if __name__ == '__main__':
def do_work():

    while True:
        if not threading.main_thread().is_alive(): exit()
        # print(f'pausebotmod: Fetching market state')
        paused = analyze()
        if paused:
            with open('signals/paused.exc','a+') as f:
                f.write('yes')
        else:
            if os.path.isfile("signals/paused.exc"):
                os.remove('signals/paused.exc')

        # print(f'pausebotmod: Waiting {TIME_TO_WAIT} minutes for next market checkup')
        time.sleep((TIME_TO_WAIT*60))
