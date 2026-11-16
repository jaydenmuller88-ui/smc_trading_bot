import MetaTrader5 as mt5
import pandas as pd
import numpy as np

MIN_FVG_PIPS = 0.00010  

def init_mt5():
    if not mt5.initialize():
        print(f"❌ MT5 Initialization failed: {mt5.last_error()}")
        return False
    return True

def detect_fair_value_gaps(df, min_gap_pips=MIN_FVG_PIPS):
    """
    Detects valid Fair Value Gaps with:
    1. Minimum gap threshold (filters micro-gaps).
    2. Strong displacement middle candle (body > 50% of total range).
    """
    df['bullish_fvg'] = False
    df['bearish_fvg'] = False
    df['fvg_top'] = np.nan
    df['fvg_bottom'] = np.nan

    for i in range(2, len(df)):
        prev_range = df['high'].iloc[i-1] - df['low'].iloc[i-1]
        prev_body = abs(df['close'].iloc[i-1] - df['open'].iloc[i-1])
        is_displacement = (prev_body / prev_range) >= 0.50 if prev_range > 0 else False

        
        gap_size_bull = df['low'].iloc[i] - df['high'].iloc[i-2]
        if gap_size_bull >= min_gap_pips and is_displacement:
            df.loc[df.index[i], 'bullish_fvg'] = True
            df.loc[df.index[i], 'fvg_top'] = df['low'].iloc[i]
            df.loc[df.index[i], 'fvg_bottom'] = df['high'].iloc[i-2]

        
        gap_size_bear = df['low'].iloc[i-2] - df['high'].iloc[i]
        if gap_size_bear >= min_gap_pips and is_displacement:
            df.loc[df.index[i], 'bearish_fvg'] = True
            df.loc[df.index[i], 'fvg_top'] = df['low'].iloc[i-2]
            df.loc[df.index[i], 'fvg_bottom'] = df['high'].iloc[i]

    return df

def detect_break_of_structure(df, lookback=20):
    """
    True BOS requires a candle CLOSE past the recent swing high/low.
    """
    df['bullish_bos'] = False
    df['bearish_bos'] = False

    for i in range(lookback, len(df)):
        recent_high = df['high'].iloc[i - lookback:i - 1].max()
        recent_low = df['low'].iloc[i - lookback:i - 1].min()

        if df['close'].iloc[i] > recent_high:
            df.loc[df.index[i], 'bullish_bos'] = True
        elif df['close'].iloc[i] < recent_low:
            df.loc[df.index[i], 'bearish_bos'] = True

    return df

def detect_liquidity_sweeps(df, lookback=20):
    """
    True Liquidity Sweep requires a WICK piercing the liquidity level, 
    but the candle CLOSE must stay back inside the previous structure range.
    """
    df['bullish_sweep'] = False
    df['bearish_sweep'] = False

    for i in range(lookback, len(df)):
        recent_high = df['high'].iloc[i - lookback:i - 1].max()
        recent_low = df['low'].iloc[i - lookback:i - 1].min()

        
        if df['low'].iloc[i] < recent_low and df['close'].iloc[i] > recent_low:
            df.loc[df.index[i], 'bullish_sweep'] = True

        
        if df['high'].iloc[i] > recent_high and df['close'].iloc[i] < recent_high:
            df.loc[df.index[i], 'bearish_sweep'] = True

    return df