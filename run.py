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

def individual_upl(trader: shift.Trader, ticker: str):

    price = get_prices(trader, ticker)[2]
    item = trader.get_portfolio_item(ticker)
    short_shares = item.get_short_shares()
    short_val = short_shares * price
    cost = item.get_short_price() * short_shares
    return short_val - cost


def cover_shorts(trader: shift.Trader, ticker: str):

    item = trader.get_portfolio_item(ticker)
    
    while item.get_short_shares() > 0:
        orders = place_orders(shift.Order.MARKET_BUY, ticker, int(item.get_short_shares()/100))
        sleep(10)
        item = trader.get_portfolio_item(ticker)
        print(f"Covering {ticker} short at {get_prices(trader, ticker)[0]} for {individual_upl(trader, ticker)} P&L at {trader.get_last_trade_time()}")

def strategy(trader: shift.Trader, ticker: str, endtime):

    check_freq = 30
    order_size = 2
    item = trader.get_portfolio_item(ticker)
    acceptable_trade = trader.get_portfolio_summary().get_total_bp()*0.6 > get_prices(trader, ticker)[1]*200
    orders = 0

    while trader.get_last_trade_time() < endtime and acceptable_trade and orders <= 35:
        sleep(30)
        ask, bid, mid = get_prices(trader, ticker)

        if bid == 0 or ask == 0:
            continue 

        order = shift.Order(shift.Order.Type.MARKET_SELL, ticker, order_size)
        trader.submit_order(order)
        orders += 1
        print(f"shorted {order_size*100} shares of {ticker} at {trader.get_last_trade_time()} at {bid}")
        item = trader.get_portfolio_item(ticker)

   

def main(trader):
   
    check_frequency = 60 
    current = trader.get_last_trade_time()
    start_time = datetime.combine(current, dt.time(10,00,00))
    end_time = datetime.combine(current, dt.time(15,30,00))

    while trader.get_last_trade_time() < start_time:

        print(f"Awaiting market open at {trader.get_last_trade_time()}")
        sleep(3)

    initial_pl = trader.get_portfolio_summary().get_total_realized_pl()

    threads = []

    tickers = ['VZ',
           'XOM',
           'MMM',
           'IBM',
           'JNJ',
           'CVX']

    print("START")
    sleep(2)
    print(trader.get_last_trade_time())

    for ticker in tickers:
        # initializes threads containing the strategy for each ticker
        threads.append(
            Thread(target=strategy, args=(trader, ticker, end_time)))

    for thread in threads:
        thread.start()
        sleep(3)

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
    with shift.Trader("jam_traders") as trader:
        trader.connect("initiator.cfg", "mNifF1Kq")
        sleep(1)
        trader.sub_all_order_book()
        sleep(1)

        main(trader)