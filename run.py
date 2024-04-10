import shift
from time import sleep
from datetime import datetime, timedelta
import datetime as dt
from threading import Thread

initial_bp = 1000000

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
    return ask, bid, mid

def place_orders(order_type: shift.Order.Type, ticker: str, size: int):

    order = shift.Order(order_type, ticker, size)
    trader.submit_order(order)
    return [order]

def cover_shorts(trader: shift.Trader, ticker: str):

    item = trader.get_portfolio_item(ticker)
    
    while item.get_short_shares() > 0:
        orders = place_orders(shift.Order.MARKET_BUY, ticker, int(item.get_short_shares()/100))
        sleep(10)
        item = trader.get_portfolio_item(ticker)
        print(f'submitted buy for {ticker}')

def sell_long(trader: shift.Trader, ticker: str):
    item = trader.get_portfolio_item(ticker)
    while(item.get_long_shares() > 0):
        orders_placed = place_orders(shift.Order.Type.MARKET_SELL,ticker, int(item.get_long_shares() / 100))
        sleep(10)
        item = trader.get_portfolio_item(ticker)
        print(f'submitted sell for {ticker}')

def place_orders(order_type: shift.Order.Type, ticker: str, size: int):
    order = shift.Order(order_type, ticker, size)
    trader.submit_order(order)
    return [order]

def place_limit_order(order_type: shift.Order.Type, ticker: str, size: int, price: float):
    order = shift.Order(order_type, ticker, size, price)
    trader.submit_order(order)
    return order

def get_order_status(order):
    return trader.get_order(order.id).status

def check_order(order, trader: shift.Trader):
    sleep(1)
    status = get_order_status(order)
    tries = 0
    while status != shift.Order.Status.REJECTED and status != shift.Order.Status.FILLED and tries < 10:
        sleep(1)
        tries += 1
        status = get_order_status(order)
    if status != shift.Order.Status.REJECTED and status != shift.Order.Status.FILLED:
        trader.submit_cancellation(order)


def mm_short(trader: shift.Trader, ticker: str, end_time):
    
    min_spread = 0.02
    max_allocation = 0.1
    allocation = max_allocation * initial_bp
    while trader.get_last_trade_time() < end_time:
        
        sleep(3)

        item = trader.get_portfolio_item(ticker)
        short_shares = item.get_short_shares()
        ask, bid, mid = get_prices(trader, ticker)
        if int(ask) == 0 or int(bid) == 0:
            continue

        spread = ask-bid
        current_port_val = short_shares*mid

        if allocation > current_port_val:
            
            lots = 3
            price = ask

            if spread < min_spread:
                price += 0.01
            
            order = place_limit_order(shift.Order.Type.LIMIT_SELL, ticker, lots, price)
            print(f'market making sell on {ticker} at {price} with {trader.get_portfolio_summary().get_total_bp()} buying power at {trader.get_last_trade_time()}')
            check_order(order, trader)
        
        else:
            continue

def mm_long(trader: shift.Trader, ticker: str, end_time):
    
    min_spread = 0.02
    max_allocation = 0.1
    allocation = max_allocation * initial_bp
    while trader.get_last_trade_time() < end_time:
        
        sleep(3)

        item = trader.get_portfolio_item(ticker)
        short_shares = item.get_long_shares()
        ask, bid, mid = get_prices(trader, ticker)
        if int(ask) == 0 or int(bid) == 0:
            continue

        spread = ask-bid
        current_port_val = short_shares*mid

        if allocation > current_port_val:
            
            lots = 3
            price = ask

            if spread < min_spread:
                price -= 0.01
            
            order = place_limit_order(shift.Order.Type.LIMIT_BUY, ticker, lots, price)
            print(f'market making buy on {ticker} at {price} with {trader.get_portfolio_summary().get_total_bp()} buying power at {trader.get_last_trade_time()}')
            check_order(order, trader)
        
        else:
            continue


def unrealized_pl(trader: shift.Trader, ticker: str):

    price = trader.get_last_price(ticker)
    item = trader.get_portfolio_item(ticker)
    long_shares = item.get_long_shares()
    short_shares = item.get_short_shares()
    upl = 0

    curr_long_value = long_shares * price
    cost_long = long_shares * item.get_long_price()
    curr_short_value = short_shares * price
    cost_short = short_shares * item.get_short_price()

    
    if cost_long != 0:
        upl += (curr_long_value - cost_long)/float(cost_long)
    if cost_short != 0:
        upl -= (curr_short_value - cost_short)/float(cost_short)

    return upl

def manage_inventory(trader: shift.Trader, ticker: str, end_time):
    while trader.get_last_trade_time() < end_time:            
        sleep(3)
        upl = unrealized_pl(trader, ticker)
        item = trader.get_portfolio_item(ticker)
        print(f"UPL {ticker} = {upl}")
        if upl >= 0.004 or upl <= -0.003:
            print(f"Closing positions on {ticker} for {upl} {'loss' if upl <= -0.002 else 'profit'}")
            if item.get_long_shares() > 0:
                sell_long(trader, ticker)
            if item.get_short_shares() > 0:
                cover_shorts(trader, ticker)

def main(trader):

    check_frequency = 60 
    current = trader.get_last_trade_time()
    start_time = datetime.combine(current, dt.time(10,00,00))
    end_time = datetime.combine(current, dt.time(15,15,00))

    while trader.get_last_trade_time() < start_time:

        print(f"Awaiting market open at {trader.get_last_trade_time()}")
        sleep(3)

    initial_pl = trader.get_portfolio_summary().get_total_realized_pl()

    threads = []

    tickers = ['CS1', 'CS2']

    print(f"START @ {trader.get_last_trade_time()}")
    sleep(1)

    for ticker in tickers:
        # initializes threads containing the strategy for each ticker
        threads.append(
            Thread(target=mm_long, args=(trader, ticker, end_time))
            )
        threads.append(
            Thread(target=mm_short, args=(trader, ticker, end_time))
            )
        threads.append(
            Thread(target=manage_inventory, args=(trader, ticker, end_time))
        )

    for thread in threads:
        thread.start()
        sleep(3)

    # wait until endtime is reached
    while trader.get_last_trade_time() < end_time - timedelta(seconds = 15):
        sleep(check_frequency) 

    print('CLOSING OUT POSITIONS NOW')

    # wait for all threads to finish
    for thread in threads:
        # NOTE: this method can stall your program indefinitely if your strategy does not terminate naturally
        # setting the timeout argument for join() can prevent this
        thread.join(timeout=1)

    for order in trader.get_waiting_list():
        trader.submit_cancellation(order)

    # make sure all remaining orders have been cancelled and all positions have been closed
    for ticker in tickers:
        item = trader.get_portfolio_item(ticker)
        if item.get_long_shares() > 0:
            print(f'CLOSING LONG {ticker}')
            sell_long(trader, ticker)
            sleep(1)
    sleep(5) # change this to sleep 10 for real

    for ticker in tickers:
        item = trader.get_portfolio_item(ticker)
        if item.get_short_shares() > 0:
            print(f'CLOSING SHORT {ticker}')
            cover_shorts(trader, ticker)
            sleep(1)
    sleep(5) # change this to sleep 10 for real

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