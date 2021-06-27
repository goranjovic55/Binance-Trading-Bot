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

# used for dates
from datetime import date, datetime, timedelta
import time

#gogo MOD telegram needs import request
import requests

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key,
    load_telegram_creds
)

from bot.settings import *

def decimals():
    # set number of decimals for reporting fractions
    if is_fiat():
        return 2
    else:
        return 8

def is_fiat():
    # check if we are using a fiat as a base currency
    global hsp_head
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    #list below is in the order that Binance displays them, apologies for not using ASC order but this is easier to update later
    fiats = ['USDT', 'BUSD', 'AUD', 'BRL', 'EUR', 'GBP', 'RUB', \
             'TRY', 'TUSD', 'USDC', 'PAX', 'BIDR', 'DAI', 'IDRT', \
             'UAH', 'NGN', 'VAI', 'BVND']

    if PAIR_WITH in fiats:
        return True
    else:
        return False

def discord_avatar():
    # Custom coin avatar dependant on PAIR_WITH
    # Fallback image is a nice Binance logo, yay!
    DISCORD_AVATAR =  "https://i.imgur.com/w1vS5Oc.png"
    if PAIR_WITH == 'ETH':
        DISCORD_AVATAR =  "https://i.imgur.com/L9Txc9F.jpeg"
    if PAIR_WITH == 'BTC':
        DISCORD_AVATAR =  "https://i.imgur.com/oIeAiEo.jpeg"
    if PAIR_WITH == 'USDT':
        DISCORD_AVATAR =  "https://i.imgur.com/VyOdlRS.jpeg"
    return DISCORD_AVATAR

def report(type, reportline):

    global session_struct, settings_struct

    try: # does it exist?
        session_struct['investment_value_gain']
    except NameError: # if not, set to 0
        session_struct['investment_value_gain'] = 0

    WON = session_struct['win_trade_count']
    LOST = session_struct['loss_trade_count']
    DECIMALS = int(decimals())
    INVESTMENT_TOTAL = round((QUANTITY * TRADE_SLOTS), DECIMALS)
    CURRENT_EXPOSURE = round(session_struct['CURRENT_EXPOSURE'], DECIMALS)
    session_struct['TOTAL_GAINS'] = round(session_struct['TOTAL_GAINS'], DECIMALS)
    INVESTMENT_VALUE_GAIN = round(session_struct['investment_value_gain'], 2)

    # testing:
    NEW_BALANCE_TRIM = "%g" % round(session_struct['NEW_BALANCE'], DECIMALS)
    INVESTMENT_VALUE_TRIM =  "%g" % round(session_struct['investment_value'], 2)
    INVESTMENT_VALUE_GAIN_TRIM =  "%g" % round(session_struct['investment_value_gain'], 2)
    CURRENT_EXPOSURE_TRIM = "%g" % session_struct['CURRENT_EXPOSURE']
    INVESTMENT_TOTAL_TRIM = "%g" % INVESTMENT_TOTAL
    CLOSED_TRADES_PERCENT_TRIM = "%g" % round(session_struct['closed_trades_percent'], 2)
    SESSION_PROFIT_TRIM = format(session_struct['session_profit'], '.8f')
    # SESSION_PROFIT_TRIM = "%g" % round(session_profit, DECIMALS)

    SETTINGS_STRING = 'Time: '+str(round(settings_struct['TIME_DIFFERENCE'], 2))+' | Interval: '\
                      +str(round(settings_struct['RECHECK_INTERVAL'], 2))+' | Price change min/max: '\
                      +str(round(settings_struct['CHANGE_IN_PRICE_MIN'], 2))+'/'\
                      +str(round(settings_struct['CHANGE_IN_PRICE_MAX'], 2))+'% | Stop loss: '\
                      +str(round(settings_struct['STOP_LOSS'], 2))+' | Take profit: '\
                      +str(round(settings_struct['TAKE_PROFIT'], 2))+' | Trailing stop loss: '\
                      +str(round(settings_struct['TRAILING_STOP_LOSS'], 2))+' | Trailing take profit: '\
                      +str(round(settings_struct['TRAILING_TAKE_PROFIT'], 2))

    if session_struct['trade_slots'] > 0:
        UNREALISED_PERCENT = round(session_struct['unrealised_percent']/session_struct['trade_slots'], 2)
    else:
        UNREALISED_PERCENT = 0
    if (session_struct['win_trade_count'] > 0) and (session_struct['loss_trade_count'] > 0):
        WIN_LOSS_PERCENT = round((session_struct['win_trade_count']  / (session_struct['win_trade_count']  + session_struct['loss_trade_count'])) * 100, 2)
    else:
        WIN_LOSS_PERCENT = 100

    # adding all the stats together:
    report_string= 'Trade slots: '+str(session_struct['trade_slots'])+'/'\
                   +str(TRADE_SLOTS)+' ('+str(CURRENT_EXPOSURE_TRIM)+'/'\
                   +str(INVESTMENT_TOTAL_TRIM)+' '+PAIR_WITH+') | Session: '\
                   +str(SESSION_PROFIT_TRIM)+' '+PAIR_WITH+' ('+str(CLOSED_TRADES_PERCENT_TRIM)+'%) | Win/Loss: '\
                   +str(WON)+'/'+str(LOST)+' ('+str(WIN_LOSS_PERCENT)+'%) | Gains: '\
                   +str(round(session_struct['INVESTMENT_GAIN'], 4))+'%'+' | Balance: '\
                   +str(NEW_BALANCE_TRIM)+' | Value: '+str(INVESTMENT_VALUE_TRIM)+' USD | Value gain: '\
                   +str(INVESTMENT_VALUE_GAIN_TRIM)+' | Uptime: '\
                   +str(timedelta(seconds=(int(session_struct['session_uptime']/1000))))

    #gogo MOD todo more verbose having all the report things in it!!!!!
    if type == 'console':
        # print(f"{txcolors.NOTICE}>> Using {len(coins_bought)}/{TRADE_SLOTS} trade slots. OT:{UNREALISED_PERCENT:.2f}%> SP:{session_profit:.2f}%> Est:{TOTAL_GAINS:.{decimals()}f} {PAIR_WITH}> W:{win_trade_count}> L:{loss_trade_count}> IT:{INVESTMENT:.{decimals()}f} {PAIR_WITH}> CE:{CURRENT_EXPOSURE:.{decimals()}f} {PAIR_WITH}> NB:{NEW_BALANCE:.{decimals()}f} {PAIR_WITH}> IV:{investment_value:.2f} {exchange_symbol}> IG:{INVESTMENT_GAIN:.2f}%> IVG:{investment_value_gain:.{decimals()}f} {exchange_symbol}> {reportline} <<{txcolors.DEFAULT}")
        print(f"{report_string}")

    #More detailed/verbose report style
    if type == 'detailed':
        print(f"{txcolors.NOTICE}>> Using {session_struct['trade_slots']}/{TRADE_SLOTS} trade slots. << \n"
        ,f"Profit on unsold coins:  {txcolors.SELL_PROFIT if UNREALISED_PERCENT >= 0 else txcolors.SELL_LOSS}{UNREALISED_PERCENT:.2f}%\n"
        ,f"Closed trades:           {txcolors.SELL_PROFIT if session_struct['closed_trades_percent'] >= 0 else txcolors.SELL_LOSS}{str(CLOSED_TRADES_PERCENT_TRIM)}%\n"
        ,f"Session profit:          {txcolors.SELL_PROFIT if session_struct['session_profit'] >= 0 else txcolors.SELL_LOSS}{str(SESSION_PROFIT_TRIM)} {PAIR_WITH}\n"
        ,f"Est. total gains:        {txcolors.SELL_PROFIT if session_struct['TOTAL_GAINS'] >= 0 else txcolors.SELL_LOSS}{session_struct['TOTAL_GAINS']:g} {PAIR_WITH}\n"
        ,f"Trades won/lost:         {txcolors.SELL_PROFIT if session_struct['win_trade_count'] >= session_struct['loss_trade_count'] else txcolors.SELL_LOSS}{session_struct['win_trade_count']} / {txcolors.SELL_PROFIT if session_struct['win_trade_count'] >= session_struct['loss_trade_count'] else txcolors.SELL_LOSS}{session_struct['loss_trade_count']}\n"
        ,f"Investment:              {txcolors.DEFAULT}{INVESTMENT_TOTAL:g} {PAIR_WITH}\n"
        ,f"Current exposure:        {txcolors.DEFAULT}{session_struct['CURRENT_EXPOSURE']:g} {PAIR_WITH}\n"
        ,f"New balance:             {txcolors.SELL_PROFIT if session_struct['NEW_BALANCE'] >= INVESTMENT_TOTAL else txcolors.SELL_LOSS}{session_struct['NEW_BALANCE']:g} {PAIR_WITH}\n"
        ,f"Initial investment:      {txcolors.SELL_PROFIT if session_struct['investment_value'] >= INVESTMENT else txcolors.SELL_LOSS}{session_struct['investment_value']:.2f} USD\n"
        ,f"Investment gain:         {txcolors.SELL_PROFIT if session_struct['INVESTMENT_GAIN'] >= 0 else txcolors.SELL_LOSS}{session_struct['INVESTMENT_GAIN']:.2f}%\n"
        ,f"Investment value vain:   {txcolors.SELL_PROFIT if session_struct['investment_value_gain'] >= 0 else txcolors.SELL_LOSS}{str(INVESTMENT_VALUE_GAIN)} USD\n"
        ,f"{reportline} {txcolors.DEFAULT}")

    if type == 'message':
        TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ID, DISCORD_WEBHOOK = load_telegram_creds(parsed_creds)
        bot_message = SETTINGS_STRING + '\n' + reportline + '\n' + report_string + '\n'

        if BOT_MESSAGE_REPORTS and TELEGRAM_BOT_TOKEN:
            bot_token = TELEGRAM_BOT_TOKEN
            bot_chatID = TELEGRAM_BOT_ID
            send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + BOT_ID + bot_message
            response = requests.get(send_text)

        if BOT_MESSAGE_REPORTS and DISCORD_WEBHOOK:

            mUrl = "https://discordapp.com/api/webhooks/"+DISCORD_WEBHOOK
            data = {"username" : BOT_ID , "avatar_url": discord_avatar(), "content": bot_message}
            response = requests.post(mUrl, json=data)
            #   print(response.content)

    if type == 'log':
        timestamp = datetime.now().strftime("%d/%m %H:%M:%S")
        # print(f'LOG_FILE: {LOG_FILE}')
        with open(LOG_FILE,'a+') as f:
            f.write(timestamp + ' ' + reportline + '\n')
