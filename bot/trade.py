import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading

#gogo MOD telegram needs import request
import requests

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
from bot.grab import *

def trade_calculations(type,priceChange, coinHoldingTimeLimit, current_time):

    global session_struct, settings_struct, trading_struct

    if type == 'holding':
       if trading_struct['max_holding_price'] < priceChange :
           trading_struct['max_holding_price'] = priceChange

       if trading_struct['target_max_holding_price'] > 0:
          trading_struct['time_max_holding_price_counter'] += 1

       if trading_struct['target_max_holding_price'] < priceChange:
           trading_struct['time_to_max_holding_price'] = trading_struct['time_max_holding_price_counter']
           trading_struct['time_max_holding_price_counter'] = 0

       if trading_struct['min_holding_price'] > priceChange :
           trading_struct['min_holding_price'] = priceChange

       if trading_struct['target_max_holding_price'] < 0:
          trading_struct['time_min_holding_price_counter'] += 1

       if trading_struct['target_min_holding_price'] > priceChange:
           trading_struct['time_to_min_holding_price'] = trading_struct['time_min_holding_price_counter']
           trading_struct['time_min_holding_price_counter'] = 0

    if type == 'sell':
        #gogo MOD to trigger trade lost or won and to count lost or won trades
        if priceChange > 0:
           session_struct['win_trade_count'] = session_struct['win_trade_count'] + 1
           session_struct['last_trade_won'] = True
           if coinHoldingTimeLimit < current_time:
               trading_struct['holding_timeout_sell'] = 'positive'

           trading_struct['won_trade_percent'] = priceChange
           trading_struct['sum_won_trades'] = trading_struct['sum_won_trades'] + trading_struct['won_trade_percent']

        else:
           session_struct['loss_trade_count'] = session_struct['loss_trade_count'] + 1
           session_struct['last_trade_won'] = False
           if coinHoldingTimeLimit < current_time:
               trading_struct['holding_timeout_sell'] = 'negative'

           trading_struct['lost_trade_percent'] = priceChange
           trading_struct['sum_lost_trades'] = trading_struct['sum_lost_trades'] + trading_struct['lost_trade_percent']

        session_struct['closed_trades_percent'] = session_struct['closed_trades_percent'] + priceChange
        session_struct['reload_tickers_list'] = True

        trading_struct['sum_max_holding_price'] = trading_struct['sum_max_holding_price'] + trading_struct['max_holding_price']
        trading_struct['sum_min_holding_price'] = -(trading_struct['sum_min_holding_price'] - trading_struct['min_holding_price'])

        if (session_struct['win_trade_count'] > 1 and session_struct['loss_trade_count'] > 1 ) and (trading_struct['sum_max_holding_price'] != 0 and trading_struct['sum_min_holding_price'] != 0):
           trading_struct['target_max_holding_price'] = trading_struct['sum_max_holding_price'] / (session_struct['win_trade_count'] + session_struct['loss_trade_count'])
           trading_struct['target_min_holding_price'] = trading_struct['sum_min_holding_price'] / (session_struct['win_trade_count'] + session_struct['loss_trade_count'])

        trading_struct['sum_time_to_target_max_price'] = trading_struct['sum_time_to_target_max_holding_price'] + trading_struct['time_to_target_max_holding_price']
        trading_struct['sum_time_to_target_min_price'] = trading_struct['sum_time_to_target_min_holding_price'] + trading_struct['time_to_target_min_holding_price']

        if (session_struct['win_trade_count'] > 1 and session_struct['win_trade_count'] > 1 ) and (trading_struct['target_time_to_target_max_holding_price'] != 0 and trading_struct['target_time_to_target_min_holding_price'] != 0):
           trading_struct['target_time_to_target_max_holding_price'] = trading_struct['sum_time_to_target_max_holding_price'] / (session_struct['win_trade_count'] + session_struct['loss_trade_count'])
           trading_struct['target_time_to_target_min_holding_price'] = trading_struct['sum_time_to_target_min_holding_price'] / (session_struct['win_trade_count'] + session_struct['loss_trade_count'])


def convert_volume():
    '''Converts the volume given in QUANTITY from USDT to the each coin's volume'''

    #added feature to buy only if percent and signal triggers uses PERCENT_SIGNAL_BUY true or false from config
    if PERCENT_SIGNAL_BUY == True:
       volatile_coins, number_of_coins, last_price = wait_for_price('percent_mix_signal')
    else:
       volatile_coins, number_of_coins, last_price = wait_for_price('percent_and_signal')

    lot_size = {}
    volume = {}

    for coin in volatile_coins:

        # Find the correct step size for each coin
        # max accuracy for BTC for example is 6 decimal points
        # while XRP is only 1
        try:
            step_size = session_struct['symbol_info'][coin]
            lot_size[coin] = step_size.index('1') - 1
        except KeyError:
            # not retrieved at startup, try again
            try:
                coin_info = client.get_symbol_info(coin)
                step_size = coin_info['filters'][2]['stepSize']
                lot_size[coin] = step_size.index('1') - 1
            except:
                pass
        lot_size[coin] = max(lot_size[coin], 0)

        # calculate the volume in coin from QUANTITY in USDT (default)
        volume[coin] = float(QUANTITY / float(last_price[coin]['price']))

        # define the volume with the correct step size
        if coin not in lot_size:
            volume[coin] = float('{:.1f}'.format(volume[coin]))

        else:
            # if lot size has 0 decimal points, make the volume an integer
            if lot_size[coin] == 0:
                volume[coin] = int(volume[coin])
            else:
                volume[coin] = float('{:.{}f}'.format(volume[coin], lot_size[coin]))

    return volume, last_price

def test_order_id():
    import random
    """returns a fake order id by hashing the current time"""
    test_order_id_number = random.randint(100000000,999999999)
    return test_order_id_number

def buy():
    '''Place Buy market orders for each volatile coin found'''
    global UNIQUE_BUYS
    volume, last_price = convert_volume()
    orders = {}

    for coin in volume:
        BUYABLE = True
        if UNIQUE_BUYS and (coin in coins_bought):
            BUYABLE = False

        # only buy if the there are no active trades on the coin
        if BUYABLE:
            print(f"{txcolors.BUY}Preparing to buy {volume[coin]} {coin}{txcolors.DEFAULT}")

            REPORT = str(f"Buy : {volume[coin]} {coin} - {last_price[coin]['price']}")

            if TEST_MODE:
                orders[coin] = [{
                    'symbol': coin,
                    'orderId': test_order_id(),
                    'time': datetime.now().timestamp()
                }]

                # Log trades
                report_struct['report'] = REPORT
                report_struct['log'] = True

                continue

            # try to create a real order if the test orders did not raise an exception
            try:
                order_details = client.create_order(
                    symbol = coin,
                    side = 'BUY',
                    type = 'MARKET',
                    quantity = volume[coin]
                )

            # error handling here in case position cannot be placed
            except Exception as e:
                print(e)

            # run the else block if the position has been placed and return order info
            else:
                orders[coin] = client.get_all_orders(symbol=coin, limit=1)

                # binance sometimes returns an empty list, the code will wait here until binance returns the order
                while orders[coin] == []:
                    print('Binance is being slow in returning the order, calling the API again...')

                    orders[coin] = client.get_all_orders(symbol=coin, limit=1)
                    time.sleep(1)

                else:
                    # Log, announce, and report trade
                    print('Order returned, saving order to file')

                    if not TEST_MODE:
                       orders[coin] = extract_order_data(order_details)
                       REPORT = str(f"BUY: bought {orders[coin]['volume']} {coin} - average price: {orders[coin]['avgPrice']} {PAIR_WITH}")
                       report_struct['report'] = REPORT
                       report_struct['log'] = True

        else:
            print(f'Signal detected, but there is already an active trade on {coin}')

    return orders, last_price, volume

def sell_coins():
    '''sell coins that have reached the STOP LOSS or TAKE PROFIT threshold'''
    global session_struct, settings_struct, trading_struct

    global hsp_head
    global FULL_LOG
    last_price = get_price(False) # don't populate rolling window
    #last_price = get_price(add_to_historical=True) # don't populate rolling window
    coins_sold = {}

    for coin in list(coins_bought):

        BUY_PRICE = float(coins_bought[coin]['bought_at'])
        # coinTakeProfit is the price at which to 'take profit' based on config % markup
        coinTakeProfit = BUY_PRICE + ((BUY_PRICE * coins_bought[coin]['take_profit']) / 100)
        # coinStopLoss is the price at which to 'stop losses' based on config % markdown
        coinStopLoss = BUY_PRICE + ((BUY_PRICE * coins_bought[coin]['stop_loss']) / 100)
        # coinHoldingTimeLimit is the time limit for holding onto a coin
        coinHoldingTimeLimit = float(coins_bought[coin]['timestamp']) + settings_struct['HOLDING_TIME_LIMIT']
        lastPrice = float(last_price[coin]['price'])
        LAST_PRICE = "{:.8f}".format(lastPrice)
        sellFee = (coins_bought[coin]['volume'] * lastPrice) * (TRADING_FEE/100)
        buyPrice = float(coins_bought[coin]['bought_at'])
        BUY_PRICE = "{:.8f}". format(buyPrice)
        buyFee = (coins_bought[coin]['volume'] * buyPrice) * (TRADING_FEE/100)
        # Note: priceChange and priceChangeWithFee are percentages!
        priceChange = float((lastPrice - buyPrice) / buyPrice * 100)
        # priceChange = (0.00006648 - 0.00006733) / 0.00006733 * 100
        # volume = 150
        # buyPrice: 0.00006733
        # lastPrice: 0.00006648
        # buyFee = (150 * 0.00006733) * (0.075/100)
        # buyFee = 0.000007574625
        # sellFee = (150 * 0.00006648) * (0.075/100)
        # sellFee = 0.000007479

        # check that the price is above the take profit and readjust coinStopLoss and coinTakeProfit accordingly if trialing stop loss used
        if lastPrice > coinTakeProfit and USE_TRAILING_STOP_LOSS:
            # increasing coinTakeProfit by TRAILING_TAKE_PROFIT (essentially next time to readjust coinStopLoss)
            coins_bought[coin]['take_profit'] = priceChange + settings_struct['TRAILING_TAKE_PROFIT']
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - settings_struct['TRAILING_STOP_LOSS']
            if DEBUG: print(f"{coin} TP reached, adjusting TP {coins_bought[coin]['take_profit']:.{decimals()}f} and SL {coins_bought[coin]['stop_loss']:.{decimals()}f} accordingly to lock-in profit")
            continue

        if not TEST_MODE:
           current_time = float(round(time.time() * 1000))
#           print(f'TL:{coinHoldingTimeLimit}, time: {current_time} HOLDING_TIME_LIMIT: {HOLDING_TIME_LIMIT}, TimeLeft: {(coinHoldingTimeLimit - current_time)/1000/60} ')

        if TEST_MODE:
           current_time = float(round(time.time()))
#           print(f'TL:{coinHoldingTimeLimit}, time: {current_time} HOLDING_TIME_LIMIT: {HOLDING_TIME_LIMIT}, TimeLeft: {(coinHoldingTimeLimit - current_time)/60} ')

        trade_calculations('holding', priceChange, coinHoldingTimeLimit, current_time)

        # check that the price is below the stop loss or above take profit (if trailing stop loss not used) and sell if this is the case
        if session_struct['sell_all_coins'] == True or lastPrice < coinStopLoss or lastPrice > coinTakeProfit and not USE_TRAILING_STOP_LOSS or coinHoldingTimeLimit < current_time:
            print(f"{txcolors.SELL_PROFIT if priceChange >= 0. else txcolors.SELL_LOSS}TP or SL reached, selling {coins_bought[coin]['volume']} {coin}. Bought at: {BUY_PRICE} (Price now: {LAST_PRICE})  - {priceChange:.2f}% - Est: {(QUANTITY * priceChange) / 100:.{decimals()}f} {PAIR_WITH}{txcolors.DEFAULT}")
            # try to create a real order
            try:

                if not TEST_MODE:
                    order_details = client.create_order(
                        symbol = coin,
                        side = 'SELL',
                        type = 'MARKET',
                        quantity = coins_bought[coin]['volume']
                    )

            # error handling here in case position cannot be placed
            except Exception as e:
                print(e)

            # run the else block if coin has been sold and create a dict for each coin sold
            else:
                if not TEST_MODE:

                   coins_sold[coin] = extract_order_data(order_details)
                   lastPrice = coins_sold[coin]['avgPrice']
                   sellFee = coins_sold[coin]['tradeFee']
                   coins_sold[coin]['orderid'] = coins_bought[coin]['orderid']
                   priceChange = float((lastPrice - buyPrice) / buyPrice * 100)

                else:
                   coins_sold[coin] = coins_bought[coin]

                trade_calculations('sell', priceChange, coinHoldingTimeLimit, current_time)

                # prevent system from buying this coin for the next TIME_DIFFERENCE minutes
                volatility_cooloff[coin] = datetime.now()

                # Log trade
                profit = ((lastPrice - buyPrice) * coins_sold[coin]['volume']) - (buyFee + sellFee)

                if session_struct['sell_all_coins'] == True: REPORT =  f"PAUSE_SELL - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice < coinStopLoss: REPORT =  f"STOP_LOSS - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if lastPrice > coinTakeProfit: REPORT =  f"TAKE_PROFIT - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"
                if coinHoldingTimeLimit < current_time: REPORT =  f"HOLDING_TIMEOUT - SELL: {coins_sold[coin]['volume']} {coin} - Bought at {buyPrice:.{decimals()}f}, sold at {lastPrice:.{decimals()}f} - Profit: {profit:.{decimals()}f} {PAIR_WITH} ({priceChange:.2f}%)"

                session_struct['session_profit'] = session_struct['session_profit'] + profit

                report_struct['report'] = REPORT
                report_struct['message'] = True
                report_struct['log'] = True

            continue

        if len(coins_bought) > 0:
           print(f"TP:{coinTakeProfit:.{decimals()}f}:{coins_bought[coin]['take_profit']:.2f} or SL:{coinStopLoss:.{decimals()}f}:{coins_bought[coin]['stop_loss']:.2f} not yet reached, not selling {coin} for now >> Bought at: {BUY_PRICE} - Now: {LAST_PRICE} : {txcolors.SELL_PROFIT if priceChange >= 0. else txcolors.SELL_LOSS}{priceChange:.2f}% Est: {(QUANTITY*(priceChange-(buyFee+sellFee)))/100:.{decimals()}f} {PAIR_WITH} - CIP: {settings_struct['CHANGE_IN_PRICE_MIN']:.2f}/{settings_struct['CHANGE_IN_PRICE_MAX']:.2f} - TAKE_PROFIT: {settings_struct['TAKE_PROFIT']:.2f}{txcolors.DEFAULT}")


    return coins_sold

def extract_order_data(order_details):
    global TRADING_FEE, STOP_LOSS, TAKE_PROFIT
    transactionInfo = {}
    # adding order fill extractions here
    #
    # just to explain what I am doing here:
    # Market orders are not always filled at one price, we need to find the averages of all 'parts' (fills) of this order.
    #
    # reset other variables to 0 before use
    FILLS_TOTAL = 0
    FILLS_QTY = 0
    FILLS_FEE = 0
    BNB_WARNING = 0
    # loop through each 'fill':
    for fills in order_details['fills']:
        FILL_PRICE = float(fills['price'])
        FILL_QTY = float(fills['qty'])
        FILLS_FEE += float(fills['commission'])
        # check if the fee was in BNB. If not, log a nice warning:
        if (fills['commissionAsset'] != 'BNB') and (TRADING_FEE == 0.75) and (BNB_WARNING == 0):
            print(f"WARNING: BNB not used for trading fee, please ")
            BNB_WARNING += 1
        # quantity of fills * price
        FILLS_TOTAL += (FILL_PRICE * FILL_QTY)
        # add to running total of fills quantity
        FILLS_QTY += FILL_QTY
        # increase fills array index by 1

    # calculate average fill price:
    FILL_AVG = (FILLS_TOTAL / FILLS_QTY)

    tradeFeeApprox = (float(FILLS_QTY) * float(FILL_AVG)) * (TRADING_FEE/100)
    # create object with received data from Binance
    transactionInfo = {
        'symbol': order_details['symbol'],
        'orderId': order_details['orderId'],
        'timestamp': order_details['transactTime'],
        'avgPrice': float(FILL_AVG),
        'volume': float(FILLS_QTY),
        'tradeFeeBNB': float(FILLS_FEE),
        'tradeFee': tradeFeeApprox,
    }
    return transactionInfo

def update_portfolio(orders, last_price, volume):

    global session_struct

    '''add every coin bought to our portfolio for tracking/selling later'''
    if DEBUG: print(orders)
    for coin in orders:

        if not TEST_MODE:
           coins_bought[coin] = {
               'symbol': orders[coin]['symbol'],
               'orderid': orders[coin]['orderId'],
               'timestamp': orders[coin]['timestamp'],
               'bought_at': orders[coin]['avgPrice'],
               'volume': orders[coin]['volume'],
               'buyFeeBNB': orders[coin]['tradeFeeBNB'],
               'buyFee': orders[coin]['tradeFee'],
               'stop_loss': -settings_struct['STOP_LOSS'],
               'take_profit': settings_struct['TAKE_PROFIT'],
               }
        else:
           coins_bought[coin] = {
               'symbol': orders[coin][0]['symbol'],
               'orderid': orders[coin][0]['orderId'],
               'timestamp': orders[coin][0]['time'],
               'bought_at': last_price[coin]['price'],
               'volume': volume[coin],
               'stop_loss': -settings_struct['STOP_LOSS'],
               'take_profit': settings_struct['TAKE_PROFIT'],
               }

        # save the coins in a json file in the same directory
        with open(coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent=4)

        if TEST_MODE: print(f'Order for {orders[coin][0]["symbol"]} with ID {orders[coin][0]["orderId"]} placed and saved to file.')
        if not TEST_MODE: print(f'Order for {orders[coin]["symbol"]} with ID {orders[coin]["orderId"]} placed and saved to file.')

        session_struct['trade_slots'] = len(coins_bought)


def remove_from_portfolio(coins_sold):

    global session_struct

    '''Remove coins sold due to SL or TP from portfolio'''
    for coin,data in coins_sold.items():
        symbol = coin
        order_id = data['orderid']
        # code below created by getsec <3
        for bought_coin, bought_coin_data in coins_bought.items():
            if bought_coin_data['orderid'] == order_id:
                print(f"Sold {bought_coin}, removed order ID {order_id} from history.")
                coins_bought.pop(bought_coin)
                with open(coins_bought_file_path, 'w') as file:
                    json.dump(coins_bought, file, indent=4)
                break
        session_struct['trade_slots'] = len(coins_bought)
        session_struct['reload_tickers_list'] = True


def trade_crypto():
    global CONNECTION_ERROR_COUNT, READ_TIMEOUT_COUNT
    try:

        orders, last_price, volume = buy()
        update_portfolio(orders, last_price, volume)
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)
    except ReadTimeout as rt:
        READ_TIMEOUT_COUNT += 1
        print(f'We got a timeout error from from binance. Going to re-loop. Current Count: {READ_TIMEOUT_COUNT}')
    except ConnectionError as ce:
        CONNECTION_ERROR_COUNT +=1
        print(f'{txcolors.WARNING}We got a timeout error from from binance. Going to re-loop. Current Count: {CONNECTION_ERROR_COUNT}\n{ce}{txcolors.DEFAULT}')
