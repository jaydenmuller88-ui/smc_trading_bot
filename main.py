import time
from datetime import datetime, timezone
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from smc_detector import (
    init_mt5, 
    detect_fair_value_gaps, 
    detect_break_of_structure, 
    detect_liquidity_sweeps
)

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
TIMEFRAME = mt5.TIMEFRAME_M5
HTF_TIMEFRAME = mt5.TIMEFRAME_H1
RISK_PERCENT = 0.02          # 2.0% dynamic balance risk
TARGET_RR = 2.0              # 1:2 Final R:R Target
MAGIC_NUMBER = 888111        # Unique Magic ID for tracking bot orders

def is_in_killzone():
    """London (07:00-10:00 UTC) & NY (12:00-16:00 UTC) Killzones."""
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour
    return (7 <= hour < 10) or (12 <= hour < 16)

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def get_position_size(symbol, risk_amount, stop_loss_pips):
    """Calculates lot size based on account balance and dynamic PIP risk."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return 0.01

    point = symbol_info.point
    tick_value = symbol_info.trade_tick_value
    
    if stop_loss_pips <= 0 or tick_value <= 0:
        return 0.01

    risk_per_lot = (stop_loss_pips / point) * tick_value
    raw_lots = risk_amount / risk_per_lot

    vol_step = symbol_info.volume_step
    lots = round(raw_lots / vol_step) * vol_step
    
    min_vol = symbol_info.volume_min
    max_vol = symbol_info.volume_max
    return max(min_vol, min(max_vol, lots))

def place_limit_order(symbol, order_type, price, sl, tp, risk_amount):
    """Sends Limit Order request to MT5 with validated precision."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ [{symbol}] Failed to fetch symbol info.")
        return

    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    digits = symbol_info.digits
    tick_size = symbol_info.trade_tick_size

    # Ensure price aligns with tick step precision
    price = round(round(price / tick_size) * tick_size, digits)
    sl = round(round(sl / tick_size) * tick_size, digits)
    tp = round(round(tp / tick_size) * tick_size, digits)

    # Validate against current market prices to avoid Invalid Price rejection
    current_bid = symbol_info.bid
    current_ask = symbol_info.ask

    if order_type == "BUY":
        if price >= current_ask:
            # Adjust limit price just below ask if market already moved
            price = round(current_ask - (5 * symbol_info.point), digits)
        order_type_mt5 = mt5.ORDER_TYPE_BUY_LIMIT
    else:
        if price <= current_bid:
            # Adjust limit price just above bid if market already moved
            price = round(current_bid + (5 * symbol_info.point), digits)
        order_type_mt5 = mt5.ORDER_TYPE_SELL_LIMIT

    sl_dist = abs(price - sl)
    volume = get_position_size(symbol, risk_amount, sl_dist)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type_mt5,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": MAGIC_NUMBER,
        "comment": "SMC Bot Live Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        comment = result.comment if result else "Unknown MT5 error"
        print(f"❌ [{symbol}] Limit Order Failed: {comment}")
    else:
        print(f"✅ [{symbol}] {order_type} LIMIT PLACED @ {price} | Lots: {volume} | SL: {sl} | TP: {tp}")

def manage_open_positions():
    """Manages 50% Partial Take-Profit when 1:1 R:R is achieved."""
    positions = mt5.positions_get(magic=MAGIC_NUMBER)
    if not positions:
        return

    for pos in positions:
        symbol_info = mt5.symbol_info(pos.symbol)
        if symbol_info is None:
            continue
            
        sl_dist = abs(pos.price_open - pos.sl)
        current_price = symbol_info.bid if pos.type == mt5.ORDER_TYPE_BUY else symbol_info.ask

        profit_dist = (current_price - pos.price_open) if pos.type == mt5.ORDER_TYPE_BUY else (pos.price_open - current_price)

        if profit_dist >= sl_dist and pos.volume > symbol_info.volume_min:
            partial_vol = round((pos.volume / 2.0) / symbol_info.volume_step) * symbol_info.volume_step
            if partial_vol >= symbol_info.volume_min:
                close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": partial_vol,
                    "type": close_type,
                    "position": pos.ticket,
                    "price": current_price,
                    "magic": MAGIC_NUMBER,
                    "comment": "SMC Bot 50% Partial TP",
                    "type_filling": mt5.ORDER_FILLING_RETURN,
                }
                res = mt5.order_send(request)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"💰 [{pos.symbol}] 50% PARTIAL TP BANKED on Position #{pos.ticket}")

def analyze_and_trade():
    """Scans all symbols for active setup triggers."""
    account_info = mt5.account_info()
    if account_info is None:
        return

    balance = account_info.balance
    risk_dollars = balance * RISK_PERCENT

    for symbol in SYMBOLS:
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 300)
        htf_rates = mt5.copy_rates_from_pos(symbol, HTF_TIMEFRAME, 0, 100)

        if rates is None or htf_rates is None:
            continue

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        htf_df = pd.DataFrame(htf_rates)
        htf_df['time'] = pd.to_datetime(htf_df['time'], unit='s')

        htf_df['ema200'] = htf_df['close'].ewm(span=200, adjust=False).mean()
        df['atr'] = calculate_atr(df, 14)

        df = detect_fair_value_gaps(df)
        df = detect_break_of_structure(df)
        df = detect_liquidity_sweeps(df)

        last_idx = len(df) - 1
        candle = df.iloc[last_idx]

        htf_match = htf_df[htf_df['time'] <= candle['time']]
        if len(htf_match) < 50:
            continue

        htf_ema = htf_match['ema200'].iloc[-1]
        htf_close = htf_match['close'].iloc[-1]

        htf_bullish = htf_close > htf_ema
        htf_bearish = htf_close < htf_ema

        recent_bullish_sweep = df['bullish_sweep'].iloc[max(0, last_idx-15):last_idx+1].any()
        recent_bearish_sweep = df['bearish_sweep'].iloc[max(0, last_idx-15):last_idx+1].any()

        valid_buy = htf_bullish and recent_bullish_sweep and candle['bullish_fvg']
        valid_sell = htf_bearish and recent_bearish_sweep and candle['bearish_fvg']

        atr = candle['atr'] if not np.isnan(candle['atr']) else 0.08 if "JPY" in symbol else 0.0008

        existing_orders = mt5.orders_get(symbol=symbol, magic=MAGIC_NUMBER)
        existing_positions = mt5.positions_get(symbol=symbol, magic=MAGIC_NUMBER)

        if (existing_orders is None or len(existing_orders) == 0) and (existing_positions is None or len(existing_positions) == 0):
            if valid_buy:
                limit_price = candle['low'] + ((candle['high'] - candle['low']) * 0.5)
                sl = limit_price - (atr * 1.0)
                risk_dist = limit_price - sl
                tp = limit_price + (risk_dist * TARGET_RR)
                place_limit_order(symbol, "BUY", limit_price, sl, tp, risk_dollars)

            elif valid_sell:
                limit_price = candle['high'] - ((candle['high'] - candle['low']) * 0.5)
                sl = limit_price + (atr * 1.0)
                risk_dist = sl - limit_price
                tp = limit_price - (risk_dist * TARGET_RR)
                place_limit_order(symbol, "SELL", limit_price, sl, tp, risk_dollars)

def main():
    if not init_mt5():
        return

    print("🤖 Live SMC Trading Bot Engine Initialized.")
    print("🎯 Monitoring EURUSD, GBPUSD, USDJPY on M5 Timeframe...\n")

    now_str = datetime.now(timezone.utc).strftime('%H:%M:%S')
    if is_in_killzone():
        print(f"⚡ [{now_str} UTC] ACTIVE SESSION: Scanning market for setups...")
    else:
        print(f"💤 [{now_str} UTC] Outside London/NY Killzones. Standby mode active...")

    try:
        while True:
            if is_in_killzone():
                manage_open_positions()
                analyze_and_trade()
            else:
                now = datetime.now(timezone.utc).strftime('%H:%M:%S')
                print(f"[{now} UTC] Outside London/NY Killzones. Standby mode...")
            
            time.sleep(60)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down SMC Bot...")
        mt5.shutdown()

if __name__ == "__main__":
    main()