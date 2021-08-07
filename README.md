# Dynamic Binance Trading Bot

## Description
This Binance trading bot analyses the changes in price across all coins on Binance it constructs so called "market resistance" and "market support" based on those prices and buys coins that pass support lines and sells coins that pass resistance line.



## Internal Operation

- Bot automatically creates list from binance coins and sorts it based on volume or price changes
- Bot then scans price changes based on given time interval and creates market resistance and support
- Bot puts coins that passed support line into trailing buy and waits for price to stop falling and then places a buy
- Bot then monitors bought coins and pools for prices every recheck interval and if price is over market resistance
  activates trailing stoploss
- Bot sells coin and logs if its win or loss for internal calculations (dynamic settings adjustment, stoploss etc)
- Bot adjuststs all settings based on previous win/loss ratio and based on accumulated profit detects
- Bot recreates list and restarts cycle

## Features

- Automatic coins list creation polling binance coins list
- Automatic list sorting based on VOLUME or PRICECHANGE
- Automatic stoploss modification based on closed trades percent and win/loss ratio
- Automatic buy treshold based on market support and TAKE PROFIT based on market resistance
- Automatic buy trailing based on price dropping/rising
- Automatic session restart after bot stopped with all current strategies
- Reporting to discord channel and telegram optional
- Automatic changing of settings from config file on the fly based on wins / losses

## READ BEFORE USE
1. If you use the `TEST_MODE: False` in your config, you will be using REAL money.
2. To ensure you do not do this, ALWAYS check the `TEST_MODE` configuration item in the config.yml file..


## 💥 Disclaimer

All investment strategies and investments involve risk of loss.
**Nothing contained in this program, scripts, code or repositoy should be construed as investment advice.**
Any reference to an investment's past or potential performance is not,
and should not be construed as, a recommendation or as a guarantee of
any specific outcome or profit.
By using this program you accept all liabilities, and that no claims can be made against the developers or others connected with the program.
