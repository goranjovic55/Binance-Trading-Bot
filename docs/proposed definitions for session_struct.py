""" Current session_struct items and their definitions"""

session_struct = {
    # Profits, gains and fees
    "session_profit": 0,  # Profit in PAIR_WITH, including fees
    "market_price": 0,  # Market price in USDT for PAIR_WITH
    "investment_value": 0,  # Value in USDT of the crypto bot started with
    "investment_value_gain": 0,  # Change in value of the investment (USDT)
    "TOTAL_GAINS": 0,  # ? duplicate of investment_value_gain?
    "NEW_BALANCE": 0,  # ? investment_value + investment_value_gain?
    "INVESTMENT_GAIN": 0,  # Percentage gain of investment?
    "win_trade_count": 0,  # Trades ended with profit (including fees)
    "loss_trade_count": 0,  # Trades ended with loss (including fees)
    "closed_trades_percent": 0,  # Percentage won or lost on completed trades
    "unrealised_percent": 0,  # Percentage won or lost by selling bought coins at current price
    "CURRENT_EXPOSURE": 0,  # How much crypto is currently in another coin than PAIR_WITH ?
    # Market info
    "market_support": 0,  # ?
    "market_resistance": 0,  # ?
    "exchange_symbol": "USDT",  # Symbol used to track investment value
    "price_list_counter": 0,  # ? Seems only used in settings.py
    "symbol_info": {},  # Decimal places used on Binance for each coinpair
    # Settings
    "trade_slots": 0,  # Amount of slots bot can use
    # Flags / constants
    "STARTUP": True,  # Did bot just start?
    "LIST_AUTOCREATE": False,  # Should bot make ticker files automatically?
    "tickers_list_changed": False,  # Was the ticker list changed?
    "sell_all_coins": False,  # Does bot need to sell all coins now?
    "dynamic": "none",  # Current state of the dynamic adjustments
    # Variables & counters
    "price_timedelta": 0,  # Time in minutes when prices were last compared
    "session_start_time": 0,  # When did bot start?
    "session_uptime": 0,  # How long is bot running (time since session_start_time)
    "last_report_time": 0,
}

""" Proposed new session_struct terms and definitions"""
session_struct = {
    # Profits, gains and fees
    "session_profit": 0,  # Profit in PAIR_WITH, excluding fees
    "session_fees": 0,  # Fees paid this session, in BNB
    "investment": 0,  # Amount of crypto bot started with (in PAIR_WITH)
    "balance": 0,  # Amount of crypto after adding gains/losses (in PAIR_WITH)
    "bnb_investment": 0,  # BNB starting balance
    "bnb_balance": 0,  # BNB current balance (after payment of fees)
    "investment_value": 0,  # Value of the crypto bot started with (in exchange_symbol)
    "investment_value_gain": 0,  # Change in value of the investment (in exchange_symbol)
    "investment_percent_gain": 0,  # Percentage gain of investment (%)
    "net_investment_value_gain": 0,  # Change in value of the investment after fees (in exchange_symbol)
    "net_investment_percent_gain": 0,  # Percentage gain of investment after fees (%)
    "win_trade_count": 0,  # Trades ended with profit (including fees)
    "loss_trade_count": 0,  # Trades ended with loss (including fees)
    "closed_trades_percent": 0,  # Percentage won or lost on completed trades (excluding fees)
    "unrealised_percent": 0,  # Percentage won or lost by selling bought coins at current price (excluding fees)
    "CURRENT_EXPOSURE": 0,  # How much crypto is currently in another coin than PAIR_WITH ?
    # Market info
    "market_support": 0,  # ?
    "market_resistance": 0,  # ?
    "exchange_symbol": "USDT",  # Symbol used to track investment value
    "price_list_counter": 0,  # ? Seems only used in settings.py
    "symbol_info": {},  # Decimal places used on Binance for each coinpair
    "market_price": 0,  # Market price in USDT for PAIR_WITH
    # Settings
    "trade_slots": 0,  # Amount of slots bot can use
    # Flags / constants
    "STARTUP": True,  # Did bot just start?
    "LIST_AUTOCREATE": False,  # Should bot make ticker files automatically?
    "tickers_list_changed": False,  # Was the ticker list changed?
    "sell_all_coins": False,  # Does bot need to sell all coins now?
    "dynamic": "none",  # Current state of the dynamic adjustments
    # Variables & counters
    "price_timedelta": 0,  # Time in minutes when prices were last compared
    "session_start_time": 0,  # When did bot start?
    "session_uptime": 0,  # How long is bot running (time since session_start_time)
    "last_report_time": 0,
}
