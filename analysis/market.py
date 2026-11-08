"""Loader for the Breeze 1-minute candles shipped on branch research/ml-decision-engine (data/breeze/normalized).
Set ALGO8_MARKET_DIR to the checkout's data/breeze/normalized directory (default: ../data/breeze/normalized relative to repo).
bar timestamps are bar START (IST).
"""
import os, glob
import pandas as pd, numpy as np
BASE = os.environ.get('ALGO8_MARKET_DIR',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'breeze', 'normalized'))

def load_options():
    """all option minute candles -> DataFrame[und, expiry, strike, cp, ts, o,h,l,c, vol, oi]"""
    fs = glob.glob(os.path.join(BASE, 'options', '*', '*', '*', '*.csv'))
    parts = []
    for f in fs:
        x = pd.read_csv(f)
        parts.append(x)
    o = pd.concat(parts, ignore_index=True)
    o['ts'] = pd.to_datetime(o.timestamp_ist.str.slice(0, 19))
    o = o.rename(columns={'underlying': 'und', 'expiry_date': 'expiry', 'option_type': 'cp', 'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c', 'volume': 'vol', 'open_interest': 'oi'})
    o['expiry'] = pd.to_datetime(o.expiry)
    return o[['und', 'expiry', 'strike', 'cp', 'ts', 'o', 'h', 'l', 'c', 'vol', 'oi']].sort_values(['und', 'expiry', 'strike', 'cp', 'ts']).reset_index(drop=True)

def load_index():
    fs = glob.glob(os.path.join(BASE, 'indices', '*', '*.csv'))
    x = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    x['ts'] = pd.to_datetime(x.timestamp_ist.str.slice(0, 19))
    return x.rename(columns={'underlying': 'und'})[['und', 'ts', 'open', 'high', 'low', 'close']].sort_values(['und', 'ts']).reset_index(drop=True)
