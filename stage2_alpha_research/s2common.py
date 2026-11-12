"""Stage 2 shared loaders.  Authoritative inputs only; nothing here reads a PR #3 / PR #6 cache as an input.

Raw market files are read from the directory named by the environment variable in configs/stage2.yaml.  There is NO fallback:
if the directory is missing the loaders raise, so one dataset can never be silently substituted for another.
Derived tables are written to stage2_alpha_research/_cache (git-ignored) together with a manifest of the source files."""
import os, sys, glob, hashlib, importlib.util
import numpy as np, pandas as pd, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
CFG = yaml.safe_load(open(os.path.join(HERE, 'configs', 'stage2.yaml')))
RES = os.path.join(HERE, 'results'); CACHE = os.path.join(HERE, '_cache')
for _d in (RES, CACHE): os.makedirs(_d, exist_ok=True)
OPEN = pd.Timedelta(CFG['market']['session_open']); N = int(CFG['market']['session_bars'])
STEP = {k: v['strike_step'] for k, v in CFG['instruments'].items()}; LOT = {k: v['lot'] for k, v in CFG['instruments'].items()}


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def market_dir():
    d = os.environ.get(CFG['market']['env_var'])
    if not d or not os.path.isdir(os.path.join(d, 'indices')) or not os.path.isdir(os.path.join(d, 'options')):
        raise RuntimeError(f"raw market directory not found: set {CFG['market']['env_var']} to the Breeze 'normalized' folder (no fallback to caches)")
    return d


def feature_library():
    """PR #6 causal feature library, imported unchanged."""
    return _module('pr6_features', os.path.join(REPO, 'ohlcv_research', 'features.py'))


def _hash_files(files):
    h = hashlib.sha256(); nbytes = 0
    for f in files:
        b = open(f, 'rb').read(); nbytes += len(b); h.update(hashlib.sha256(b).digest())
    return h.hexdigest(), nbytes


def raw_index():
    """every row of every raw index file (duplicates kept): und, ts (bar start, naive IST), tz, open, high, low, close, file"""
    files = sorted(glob.glob(os.path.join(market_dir(), 'indices', '*', '*.csv')))
    x = pd.concat([pd.read_csv(f).assign(file=os.path.basename(f)) for f in files], ignore_index=True)
    x['tz'] = x.timestamp_ist.str.slice(19); x['ts'] = pd.to_datetime(x.timestamp_ist.str.slice(0, 19))
    return x.rename(columns={'underlying': 'und'})[['und', 'ts', 'tz', 'open', 'high', 'low', 'close', 'file']], files


def raw_options():
    """every row of every raw option file (duplicates kept); open_interest is never read"""
    cols = ['timestamp_ist', 'underlying', 'expiry_date', 'strike', 'option_type', 'open', 'high', 'low', 'close', 'volume']
    files = sorted(glob.glob(os.path.join(market_dir(), 'options', '*', '*', '*', '*.csv')))
    x = pd.concat([pd.read_csv(f, usecols=cols) for f in files], ignore_index=True)
    x['tz'] = x.timestamp_ist.str.slice(19); x['ts'] = pd.to_datetime(x.timestamp_ist.str.slice(0, 19))
    x = x.rename(columns={'underlying': 'und', 'expiry_date': 'expiry', 'option_type': 'cp'}); x['expiry'] = pd.to_datetime(x.expiry)
    return x[['und', 'expiry', 'strike', 'cp', 'ts', 'tz', 'open', 'high', 'low', 'close', 'volume']], files


def build_market(force=False):
    """Stage 2 market tables from the raw files -> (index, options, manifest rows).  Cached with the source hash."""
    pi, po, pm = (os.path.join(CACHE, f) for f in ('s2_index.pkl', 's2_options.pkl', 's2_market_manifest.pkl'))
    if not force and all(os.path.exists(p) for p in (pi, po, pm)):
        return pd.read_pickle(pi), pd.read_pickle(po), pd.read_pickle(pm)
    ri, fi = raw_index(); ro, fo = raw_options()
    hi, bi = _hash_files(fi); ho, bo = _hash_files(fo)
    I = ri[['und', 'ts', 'open', 'high', 'low', 'close']].drop_duplicates(['und', 'ts']).sort_values(['und', 'ts']).reset_index(drop=True)
    O = ro.drop(columns='tz').drop_duplicates(['und', 'expiry', 'strike', 'cp', 'ts']).sort_values(['und', 'expiry', 'strike', 'cp', 'ts']).reset_index(drop=True)
    man = [dict(dataset='index 1-minute bars (raw Breeze)', files=len(fi), raw_rows=len(ri), rows=len(I), bytes=bi, sha256=hi, first=str(I.ts.min()), last=str(I.ts.max())),
           dict(dataset='option 1-minute bars (raw Breeze)', files=len(fo), raw_rows=len(ro), rows=len(O), bytes=bo, sha256=ho, first=str(O.ts.min()), last=str(O.ts.max()))]
    I.to_pickle(pi); O.to_pickle(po); pd.to_pickle(man, pm)
    return I, O, man


def session_minute(ts):
    """minutes since 09:15 of a bar start (can be outside 0..374 for post-close bars)"""
    return ((ts - ts.dt.normalize() - OPEN).dt.total_seconds() // 60).astype(int)


def fills():
    """raw broker fills (authoritative): analysis/load.py::load_tagged (column-163 order key in `tag`)"""
    return _module('algo8_load', os.path.join(REPO, 'analysis', 'load.py')).load_tagged()


def feature_tables(force=False):
    """PR #6 index and ATM-straddle feature tables rebuilt from the Stage 2 market tables (never from a PR #6 cache)."""
    px, pz = os.path.join(CACHE, 's2_feat_index.pkl'), os.path.join(CACHE, 's2_feat_straddle.pkl')
    if not force and os.path.exists(px) and os.path.exists(pz): return pd.read_pickle(px), pd.read_pickle(pz)
    I, O, _ = build_market(); F = feature_library()
    X = F.index_features(I[['und', 'ts', 'open', 'high', 'low', 'close']]); Z = F.straddle_features(O[['und', 'expiry', 'strike', 'cp', 'ts', 'open', 'high', 'low', 'close', 'volume']], I[['und', 'ts', 'open', 'high', 'low', 'close']], STEP)
    X.to_pickle(px); Z.to_pickle(pz); return X, Z
