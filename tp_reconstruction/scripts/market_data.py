"""Raw Breeze 1-minute bars (index and options) for the market-context analysis. No fallback to caches: the directory must be given in ALGO8_MARKET_DIR.
Bar label = bar START (confirmed in the Stage 1 data audit); a bar labelled m is complete at m + 1 minute."""
import os, glob
import numpy as np, pandas as pd
import tp_common as tc


def market_dir():
    d = os.environ.get(tc.CFG['source']['market_env_var'])
    if not d or not os.path.isdir(os.path.join(d, 'indices')): raise RuntimeError('set ALGO8_MARKET_DIR to the raw Breeze normalized folder (no fallback)')
    return d


def index_bars():
    fs = sorted(glob.glob(os.path.join(market_dir(), 'indices', '*', '*.csv')))
    x = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True); x['ts'] = pd.to_datetime(x.timestamp_ist.str.slice(0, 19))
    x = x.rename(columns={'underlying': 'und'})[['und', 'ts', 'open', 'high', 'low', 'close']].drop_duplicates(['und', 'ts']).sort_values(['und', 'ts']).reset_index(drop=True)
    return x


def option_bars():
    cols = ['timestamp_ist', 'underlying', 'expiry_date', 'strike', 'option_type', 'close', 'volume']
    fs = sorted(glob.glob(os.path.join(market_dir(), 'options', '*', '*', '*', '*.csv')))
    x = pd.concat([pd.read_csv(f, usecols=cols) for f in fs], ignore_index=True)
    x['ts'] = pd.to_datetime(x.timestamp_ist.str.slice(0, 19)); x['expiry'] = pd.to_datetime(x.expiry_date)
    x = x.rename(columns={'underlying': 'und', 'option_type': 'cp'})[['und', 'expiry', 'strike', 'cp', 'ts', 'close', 'volume']]
    x['contract_id'] = x.und + '|' + x.expiry.dt.strftime('%Y-%m-%d') + '|' + x.cp + '|' + x.strike.map(lambda v: f'{v:g}')
    return x.drop_duplicates(['contract_id', 'ts']).sort_values(['contract_id', 'ts']).reset_index(drop=True)


def frozen_sessions(I):
    """(und, date) sessions whose closing minutes are frozen carried prices (flat bar equal to the previous close from bar 300 on); see Stage 2 register DAT-15"""
    I = I.copy(); I['date'] = I.ts.dt.normalize(); I['k'] = ((I.ts - I.date).dt.total_seconds() // 60 - 555).astype(int)
    I['flat'] = (I.open == I.high) & (I.high == I.low) & (I.low == I.close); I['same'] = I.groupby(['und', 'date']).close.shift().eq(I.close)
    f = I[(I.k >= 300) & I.flat & I.same]; return set(zip(f.und, f.date))
