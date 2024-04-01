import shift
from time import sleep
import datetime
from threading import Thread
from typing import List


tickers = ['AXP', 'V', 'PG', 'HD', 'NKE']
check_period = 4
wait_time = 5
reserve = 200000


def sell_market(trader: shift.Trader, symbol: str, amount: int):
    order = shift.Order(shift.Order.MARKET_SELL, symbol, amount)
    trader.submit_order(order)

def buy_market(trader: shift.Trader, symbol: str, amount: int):
    order = shift.Order(shift.Order.MARKET_BUY, symbol, amount)
    trader.submit_order(order)

def buy_limit(trader: shift.Trader, symbol: str, amount: int, limit: float):
    order = shift.Order(shift.Order.LIMIT_BUY, symbol, amount, limit)
    trader.submit_order(order)

def sell_limit(trader: shift.Trader, symbol: str, amount: int, limit: float):
    order = shift.Order(shift.Order.LIMIT_SELL, symbol, amount, limit)
    trader.submit_order(order)

def cover_short(trader: shift.Trader, symbol: str):
    holding = trader.get_portfolio_item(symbol)
    price_info = trader.get_best_price(symbol)
    ask_price = price_info.get_ask_price()
    
    while holding.get_short_shares() > 0:
        buy_market(trader, symbol, int(holding.get_short_shares() / 100))
        sleep(8)
        print(f'Covered {symbol} at ${ask_price}')

def liquidate_position(trader: shift.Trader, symbol: str):
    holding = trader.get_portfolio_item(symbol)
    price_info = trader.get_best_price(symbol)
    bid_price = price_info.get_bid_price()

    while holding.get_long_shares() > 0:
        sell_market(trader, symbol, int(holding.get_long_shares() / 100))
        sleep(8)
        print(f'Liquidated {symbol} at ${bid_price}')

def fetch_prices(trader: shift.Trader, symbol: str):
    price_data = trader.get_best_prices(symbol)
    bid = price_data.get_bid_price()
    ask = price_data.get_ask_price()
    midpoint = (bid + ask) / 2
    return ask, bid, midpoint

def order_status_check(current_order: shift.Order, trader: shift.Trader):
    sleep(1)
    status = trader.get_order(current_order.id).status
    tries = 0
    while status in [shift.Order.Status.REJECTED, shift.Order.Status.PENDING] and tries < 10:
        sleep(1)
        tries += 1
        status = trader.get_order(current_order.id).status
    if status not in [shift.Order.Status.REJECTED, shift.Order.Status.FILLED]:
        trader.submit_cancellation(current_order)

def trade_shorts(symbol: str, trader: shift.Trader, till: datetime.datetime):
    min_spread = 0.02
    max_ratio = 0.1
    while trader.get_last_trade_time() < till:
        sleep(check_period)
        item = trader.get_portfolio_item(symbol)
        shorts = item.get_short_shares()
        ask, bid, _ = fetch_prices(trader, symbol)
        if not ask or not bid:
            continue
        spread = ask - bid
        portfolio_val = shorts * ((ask + bid) / 2)
        max_val = max_ratio * trader.get_portfolio_summary().get_total_bp()
        if max_val > portfolio_val and spread >= min_spread:
            qty = 3
            limit_price = ask if spread < min_spread else ask + 0.01
            order = sell_limit(trader, symbol, qty, limit_price)
            order_status_check(order, trader)

def trade_longs(symbol: str, trader: shift.Trader, till: datetime.datetime):
    min_spread = 0.02
    investment_limit = 0.1
    while trader.get_last_trade_time() < till:
        sleep(check_period)
        item = trader.get_portfolio_item(symbol)
        longs = item.get_long_shares()
        ask, bid, midpoint = fetch_prices(trader, symbol)
        if bid == 0 or ask == 0:
            continue
        spread = ask - bid
        
        investment_value = longs * midpoint
        allowed_investment = investment_limit * trader.get_portfolio_summary().get_total_bp()
        
        if allowed_investment > investment_value:
            quantity = 3
            limit_price = bid if spread > min_spread else bid - 0.01
            order = buy_limit(trader, symbol, quantity, limit_price)
            order_status_check(order, trader)

def process_unrealized_gains(symbol: str, trader: shift.Trader, till: datetime.datetime):
    acceptable_gain = 0.004
    acceptable_loss = -0.002
    while trader.get_last_trade_time() < till:
        sleep(check_period)
        unrealized_pl = calculate_unrealized_pl(symbol, trader)
        item = trader.get_portfolio_item(symbol)
        if unrealized_pl >= acceptable_gain or unrealized_pl <= acceptable_loss:
            action = 'profit' if unrealized_pl >= acceptable_gain else 'loss'
            print(f"Adjusting {symbol} for {action}: UPL={unrealized_pl}")
            if item.get_long_shares() > 0:
                liquidate_position(trader, symbol)
            if item.get_short_shares() > 0:
                cover_short(trader, symbol)

def calculate_unrealized_pl(symbol: str, trader: shift.Trader):
    current_price = trader.get_last_price(symbol)
    portfolio_item = trader.get_portfolio_item(symbol)
    long_shares = portfolio_item.get_long_shares()
    short_shares = portfolio_item.get_short_shares()
    upl = 0

    if long_shares > 0:
        buy_price = portfolio_item.get_long_price()
        current_value_long = long_shares * current_price
        invested_amount_long = long_shares * buy_price
        upl += (current_value_long - invested_amount_long) / invested_amount_long

    if short_shares > 0:
        sell_price = portfolio_item.get_short_price()
        current_value_short = short_shares * current_price
        invested_amount_short = short_shares * sell_price
        upl -= (current_value_short - invested_amount_short) / invested_amount_short

    return upl


def start_threads(trader: shift.Trader, till: datetime.datetime) -> List[Thread]:
    threads = []
    for symbol in tickers:
        threads.append(Thread(target=trade_shorts, args=(symbol, trader, till)))
        threads.append(Thread(target=trade_longs, args=(symbol, trader, till)))
        threads.append(Thread(target=process_unrealized_gains, args=(symbol, trader, till)))
    #threads.append(Thread(target=routine_summary, args=(trader, till)))
    for thread in threads:
        thread.start()
    return threads

def stop_threads(threads: List[Thread]):
    for thread in threads:
        thread.join(timeout=1)

def main(trader):

    check_freq = 60
    now = trader.get_last_trade_time()

    trading_start = datetime.datetime.combine(now.date(), datetime.time(10, 0, 0))
    trading_end = datetime.datetime.combine(now.date(), datetime.time(15, 30, 0))

    threads = []

    while now < trading_start:
        print("Awaiting market open...")
        sleep(check_freq)
        now = trader.get_last_trade_time()
    threads.extend(start_threads(trader, trading_end))
    while now < trading_end:
        print("Market in session...")
        sleep(check_freq)
        now = trader.get_last_trade_time()
    stop_threads(threads)
    for order in trader.get_waiting_list():
        trader.submit_cancellation(order)

    
    for t in tickers:
        item = trader.get_portfolio_item(t)
        if item.get_long_shares() > 0:

            print(f'CLOSING LONG {t}')

            sell_market(t, trader)
            sleep(1)
    sleep(10)
    for t in tickers:
        item = trader.get_portfolio_item(t)
        if item.get_short_shares() > 0:
            print(f'CLOSING SHORT {t}')
            cover_short(t, trader)
            sleep(1)

    sleep(15)
    print(trader.get_last_trade_time())

if __name__ == '__main__':
    sleep(5)
    trader = shift.Trader("jam_traders")
    trader.connect("initiator.cfg", "mNifF1Kq")
    trader.sub_all_order_book()

    sleep(15)

    main(trader)
    trader.disconnect()
