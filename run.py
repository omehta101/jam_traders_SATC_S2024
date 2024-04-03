import shift
from time import sleep
from datetime import datetime, timedelta
import datetime as dt
from threading import Thread

def cancel_orders(trader, ticker):
    # cancel all the remaining orders
    for order in trader.get_waiting_list():
        if (order.symbol == ticker):
            trader.submit_cancellation(order)
            sleep(1)  # the order cancellation needs a little time to go through

def get_prices(trader: shift.Trader, ticker: str):

    best_prices = trader.get_best_price(ticker)
    bid = best_prices.get_bid_price()
    ask = best_prices.get_ask_price()
    mid = (ask+bid)/2
    return [ask, bid, mid]

def place_orders(order_type: shift.Order.Type, ticker: str, size: int):

    order = shift.Order(order_type, ticker, size)
    trader.submit_order(order)
    return [order]

def individual_upl(trader: shift.Trader, ticker: str, type: str):

    price = trader.get_last_price()
    item = trader.get_portfolio_item(ticker)
    curr_long_val, curr_short_val = item.get_long_shares() * price, item.get_short_shares() * price
    cost_long, cost_short = item.get_long_price() * price, item.get_short_price() * price
    short_pl = curr_short_val - cost_short
    long_pl = curr_long_val - cost_long

    if type == 'short':
        return short_pl
    else: return long_pl

def cover_shorts(trader: shift.Trader, ticker: str):

    item = trader.get_portfolio_item(ticker)
    
    while item.get_short_shares() > 0:
        orders = place_orders(shift.Order.MARKET_BUY, ticker, int(item.get_short_shares/100))
        sleep(10)
        item = trader.get_portfolio_item(ticker)
        print(f'Covering {ticker} short at {get_prices(trader, ticker)[0]} for {'profit' if individual_upl(trader, ticker, 'short') > 0 else 'loss'}')

def strategy(trader: shift.Trader, ticker: str, endtime):

    check_freq = 1
    order_size = 4

    while trader.get_last_trade_time() < endtime:
        ask, bid, mid = get_prices(trader, ticker)

        if bid == 0 or ask == 0:
            continue 

        order = shift.Order(shift.Order.Type.MARKET_SELL, ticker, order_size)
        trader.submit_order(order)

def main(trader):
   
    check_frequency = 60 
    current = trader.get_last_trade_time()
    start_time = datetime.combine(current, dt.time(9,33,0))
    end_time = datetime.combine(current, dt.time(10,00,0))

    while trader.get_last_trade_time() < start_time:

        print(f"Awaiting market open at {trader.get_last_trade_time()}")
        sleep(check_frequency)

    initial_pl = trader.get_portfolio_summary().get_total_realized_pl()

    threads = []

    # in this example, we simultaneously and independantly run our trading alogirthm on two tickers
    tickers = ['VZ',
           'XOM',
           'MMM',
           'IBM',
           'JNJ',
           'CVX']

    print("START")

    for ticker in tickers:
        # initializes threads containing the strategy for each ticker
        threads.append(
            Thread(target=strategy, args=(trader, ticker, end_time)))

    for thread in threads:
        thread.start()
        sleep(1)

    # wait until endtime is reached
    while trader.get_last_trade_time() < end_time:
        sleep(check_frequency)

    # wait for all threads to finish
    for thread in threads:
        # NOTE: this method can stall your program indefinitely if your strategy does not terminate naturally
        # setting the timeout argument for join() can prevent this
        thread.join()

    # make sure all remaining orders have been cancelled and all positions have been closed
    for ticker in tickers:
        cancel_orders(trader, ticker)
        cover_shorts(trader, ticker)

    print("END")
    print(f"final bp: {trader.get_portfolio_summary().get_total_bp()}")
    print(
        f"final profits/losses: {trader.get_portfolio_summary().get_total_realized_pl() - initial_pl}")


if __name__ == '__main__':
    with shift.Trader("jam_traders_test004") as trader:
        trader.connect("initiator.cfg", "mNifF1Kq")
        sleep(1)
        trader.sub_all_order_book()
        sleep(1)

        main(trader)