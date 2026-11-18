"""Shared paths and loaders for the OHLCV indicator / alpha research (separate from analysis/ and alpha_freeze/; nothing there is modified).
ONLY these fields are used anywhere in this package: open, high, low, close, volume, timestamps, instrument / strike / expiry identifiers, and the Algo 8 order ledger.
open_interest is present in the option files but is NEVER loaded here; index 'provider_volume' is all zero and is not used.
Market directory: env ALGO8_MARKET_DIR (the data/breeze/normalized folder of branch data/local-breeze-fetch), read-only."""
import os, sys, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
RES = os.path.join(HERE, 'results'); os.makedirs(RES, exist_ok=True)
CACHE = os.path.join(HERE, '_cache'); os.makedirs(CACHE, exist_ok=True)          # git-ignored, regenerable
MARKET = os.environ.get('ALGO8_MARKET_DIR', os.path.join(REPO, 'data', 'breeze', 'normalized'))
SESSION_OPEN, SESSION_BARS = pd.Timedelta('09:15:00'), 375                      # 09:15 ... 15:29 bar starts
STEP = {'NIFTY': 50, 'SENSEX': 100}; LOT = {'NIFTY': 65, 'SENSEX': 20}
DEV_END, VAL_END = pd.Timestamp('2026-08-20'), pd.Timestamp('2026-09-22')       # same whole-cycle splits as analysis/exit_engine/common.py

def split_of(expiry):
    e = pd.Timestamp(expiry); return 'DEV' if e <= DEV_END else ('VAL' if e <= VAL_END else 'TEST')

def _ts(s):
    """'2026-08-03T09:15:00+05:30' -> naive IST timestamp (bar START)."""
    return pd.to_datetime(s.str.slice(0, 19))

def load_index(with_files=False):
    """index 1-minute bars: und, ts (bar start, IST), open, high, low, close.  provider_volume is dropped (all zero)."""
    p = os.path.join(CACHE, 'index.pkl')
    if os.path.exists(p) and not with_files: return pd.read_pickle(p)
    parts = []
    for f in sorted(glob.glob(os.path.join(MARKET, 'indices', '*', '*.csv'))):
        x = pd.read_csv(f); x['file'] = os.path.relpath(f, MARKET); parts.append(x)
    x = pd.concat(parts, ignore_index=True); x['tz'] = x.timestamp_ist.str.slice(19); x['ts'] = _ts(x.timestamp_ist)
    x = x.rename(columns={'underlying': 'und'})
    if with_files: return x
    x = x[['und', 'ts', 'open', 'high', 'low', 'close']].drop_duplicates(['und', 'ts']).sort_values(['und', 'ts']).reset_index(drop=True); x.to_pickle(p); return x

def load_options(with_files=False):
    """option 1-minute bars: und, expiry, strike, cp, ts (bar start, IST), open, high, low, close, volume.  open_interest is never read."""
    p = os.path.join(CACHE, 'options.pkl')
    if os.path.exists(p) and not with_files: return pd.read_pickle(p)
    cols = ['timestamp_ist', 'underlying', 'expiry_date', 'strike', 'option_type', 'open', 'high', 'low', 'close', 'volume']
    parts = []
    for f in sorted(glob.glob(os.path.join(MARKET, 'options', '*', '*', '*', '*.csv'))):
        x = pd.read_csv(f, usecols=cols); x['file'] = os.path.relpath(f, MARKET); parts.append(x)
    x = pd.concat(parts, ignore_index=True); x['tz'] = x.timestamp_ist.str.slice(19); x['ts'] = _ts(x.timestamp_ist)
    x = x.rename(columns={'underlying': 'und', 'expiry_date': 'expiry', 'option_type': 'cp'}); x['expiry'] = pd.to_datetime(x.expiry)
    if with_files: return x
    x = x[['und', 'expiry', 'strike', 'cp', 'ts', 'open', 'high', 'low', 'close', 'volume']].drop_duplicates(['und', 'expiry', 'strike', 'cp', 'ts'])
    x = x.sort_values(['und', 'expiry', 'strike', 'cp', 'ts']).reset_index(drop=True); x.to_pickle(p); return x

def load_orders():
    """clean Algo 8 order ledger (one row per order, column-163 key) from PR #3's exit engine; read-only reuse."""
    import importlib.util                                    # loaded under another name: this package also has a common.py
    sys.path.insert(0, os.path.join(REPO, 'analysis'))
    spec = importlib.util.spec_from_file_location('exit_engine_common', os.path.join(REPO, 'analysis', 'exit_engine', 'common.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.orders()

def load_fills():
    import importlib.util
    spec = importlib.util.spec_from_file_location('algo8_load', os.path.join(REPO, 'analysis', 'load.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.load_tagged()
