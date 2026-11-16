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
CANDLE_COUNT = 25000              

INITIAL_BALANCE = 10000.0
RISK_PERCENT = 0.02                
TARGET_RR = 2.0                    

def is_in_killzone(candle_time):
    hour = candle_time.hour
    return (7 <= hour < 10) or (12 <= hour < 16)

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def run_portfolio_backtest():
    if not init_mt5():
        return

    total_account_balance = INITIAL_BALANCE
    all_portfolio_trades = []

    print(f"🚀 Running Multi-Asset SMC Strategy Across {SYMBOLS} (2% Dynamic Risk)...")

    for symbol in SYMBOLS:
        print(f"\n📊 Processing {symbol}...")
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, CANDLE_COUNT)
        htf_rates = mt5.copy_rates_from_pos(symbol, HTF_TIMEFRAME, 0, CANDLE_COUNT // 12)

        if rates is None or len(rates) == 0:
            print(f"❌ Failed to fetch data for {symbol}")
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

        symbol_trades = []
        active_trade_until_index = -1

        for i in range(50, len(df) - 50):
            if i < active_trade_until_index:
                continue

            candle = df.iloc[i]
            if not is_in_killzone(candle['time']):
                continue

            htf_match = htf_df[htf_df['time'] <= candle['time']]
            if len(htf_match) < 200:
                continue
            
            htf_ema = htf_match['ema200'].iloc[-1]
            htf_close = htf_match['close'].iloc[-1]
            
            htf_bullish = htf_close > htf_ema
            htf_bearish = htf_close < htf_ema

            recent_bullish_sweep = df['bullish_sweep'].iloc[max(0, i-15):i+1].any()
            recent_bearish_sweep = df['bearish_sweep'].iloc[max(0, i-15):i+1].any()

            valid_buy = htf_bullish and recent_bullish_sweep and candle['bullish_fvg']
            valid_sell = htf_bearish and recent_bearish_sweep and candle['bearish_fvg']

            atr = candle['atr'] if not np.isnan(candle['atr']) else 0.0008

            
            current_risk_dollars = total_account_balance * RISK_PERCENT

            # --- BUY EXECUTION ---
            if valid_buy:
                limit_price = candle['low'] + ((candle['high'] - candle['low']) * 0.5)
                sl = limit_price - (atr * 1.0)
                risk_dist = limit_price - sl
                tp1 = limit_price + risk_dist
                tp2 = limit_price + (risk_dist * TARGET_RR)

                filled = False
                fill_index = -1

                for k in range(i + 1, min(i + 20, len(df))):
                    if df['low'].iloc[k] <= limit_price:
                        filled = True
                        fill_index = k
                        break

                if filled:
                    outcome = "HOLD"
                    pnl = 0.0
                    tp1_hit = False

                    for j in range(fill_index + 1, min(fill_index + 120, len(df))):
                        high_p = df['high'].iloc[j]
                        low_p = df['low'].iloc[j]

                        if not tp1_hit and high_p >= tp1:
                            tp1_hit = True

                        if high_p >= tp2:
                            outcome = "WIN"
                            pnl = (current_risk_dollars * 0.5) + (current_risk_dollars * 0.5 * TARGET_RR)
                            active_trade_until_index = j + 2
                            break

                        if low_p <= sl:
                            outcome = "PARTIAL_LOSS" if tp1_hit else "LOSS"
                            pnl = 0.0 if tp1_hit else -current_risk_dollars
                            active_trade_until_index = j + 2
                            break

                    if outcome != "HOLD":
                        total_account_balance += pnl
                        symbol_trades.append({"symbol": symbol, "time": candle['time'], "outcome": outcome, "pnl": pnl})

        
            elif valid_sell:
                limit_price = candle['high'] - ((candle['high'] - candle['low']) * 0.5)
                sl = limit_price + (atr * 1.0)
                risk_dist = sl - limit_price
                tp1 = limit_price - risk_dist
                tp2 = limit_price - (risk_dist * TARGET_RR)

                filled = False
                fill_index = -1

                for k in range(i + 1, min(i + 20, len(df))):
                    if df['high'].iloc[k] >= limit_price:
                        filled = True
                        fill_index = k
                        break

                if filled:
                    outcome = "HOLD"
                    pnl = 0.0
                    tp1_hit = False

                    for j in range(fill_index + 1, min(fill_index + 120, len(df))):
                        high_p = df['high'].iloc[j]
                        low_p = df['low'].iloc[j]

                        if not tp1_hit and low_p <= tp1:
                            tp1_hit = True

                        if low_p <= tp2:
                            outcome = "WIN"
                            pnl = (current_risk_dollars * 0.5) + (current_risk_dollars * 0.5 * TARGET_RR)
                            active_trade_until_index = j + 2
                            break

                        if high_p >= sl:
                            outcome = "PARTIAL_LOSS" if tp1_hit else "LOSS"
                            pnl = 0.0 if tp1_hit else -current_risk_dollars
                            active_trade_until_index = j + 2
                            break

                    if outcome != "HOLD":
                        total_account_balance += pnl
                        symbol_trades.append({"symbol": symbol, "time": candle['time'], "outcome": outcome, "pnl": pnl})

        all_portfolio_trades.extend(symbol_trades)
        print(f"  -> {symbol} Resolved Trades: {len(symbol_trades)}")

    mt5.shutdown()

    total_trades = len(all_portfolio_trades)
    wins = len([t for t in all_portfolio_trades if t['outcome'] == 'WIN'])
    partial_losses = len([t for t in all_portfolio_trades if t['outcome'] == 'PARTIAL_LOSS'])
    full_losses = len([t for t in all_portfolio_trades if t['outcome'] == 'LOSS'])
    total_pnl = total_account_balance - INITIAL_BALANCE
    roi_percent = (total_pnl / INITIAL_BALANCE) * 100

    print("\n" + "="*50)
    print("🔥 HIGH-YIELD MULTI-ASSET PORTFOLIO RESULTS")
    print("="*50)
    print(f"Starting Balance:        ${INITIAL_BALANCE:,.2f}")
    print(f"Total Resolved Trades:   {total_trades}")
    print(f"Full Target Wins:        {wins}")
    print(f"Partial TP Saved Losses: {partial_losses}")
    print(f"Full Losses:             {full_losses}")
    print("-" * 50)
    print(f"Total Profit / Loss:     ${total_pnl:+,.2f}")
    print(f"Return on Investment:    +{roi_percent:.2f}%")
    print(f"Final Account Total:     ${total_account_balance:,.2f}")
    print("="*50)

if __name__ == "__main__":
    run_portfolio_backtest()