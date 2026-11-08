"""Minute-level cycle MTM from fills (exact cash/positions) + Breeze option candle closes (marks).
Cycle = (und, expiry). MTM(m) = cumulative cash through minute m + sum(pos * lot * close_m).   python3 analysis/mtm.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged

def cycle_mtm(d, o, und, expiry, mark='close'):
    c = d[(d.und == und) & (d.expiry == expiry)].sort_values(['t', 'row'])
    lot = c.lot.iloc[0]
    c = c.assign(minute=c.t.dt.floor('min'))
    oc = o[(o.und == und) & (o.expiry == expiry)].copy()
    oc['key'] = oc.cp + oc.strike.astype(int).astype(str)
    days = sorted(c.date.unique())
    oc = oc[oc.ts.dt.normalize().isin(days)]
    px = oc.pivot_table(index='ts', columns='key', values='c' if mark == 'close' else 'o', aggfunc='last').sort_index().ffill()
    c['key'] = c.cp + c.strike.astype(int).astype(str)
    pos = c.pivot_table(index='minute', columns='key', values='sl', aggfunc='sum').reindex(px.index).fillna(0).cumsum()
    cash = c.groupby('minute').cash.sum().reindex(px.index).fillna(0).cumsum()
    pxa = px.reindex(columns=pos.columns)
    # contracts with no candle at all: fall back to last fill price
    lastfill = c.groupby('key').px_fill.last()
    for k in pxa.columns[pxa.isna().all()]:
        pxa[k] = lastfill[k]
    pxa = pxa.ffill().bfill()
    mtm = cash + (pos * pxa).sum(axis=1) * lot
    return mtm

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
    d = load_tagged()
    o = pd.read_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache', 'opt_candles.pkl'))
    stops = d[d.tp == 's_'].groupby(['und', 'expiry']).t.min()
    rows = []
    for (u, e), c in d.groupby(['und', 'expiry']):
        m = cycle_mtm(d, o, u, e)
        trig = stops.get((u, e), pd.NaT)
        row = dict(und=u, expiry=e.date(), stop=pd.notna(trig), final=round(c.cash.sum()))
        if pd.notna(trig):
            tm = trig.floor('min'); pre = m[m.index < tm]
            row.update(trig=trig.strftime('%m-%d %H:%M'), mtm_prev_min=round(pre.iloc[-1]), mtm_trig_min=round(m.loc[tm]) if tm in m.index else np.nan,
                       min_before=round(pre.min()), min_before_t=pre.idxmin().strftime('%m-%d %H:%M'))
        else:
            row.update(min_all=round(m.min()), min_t=m.idxmin().strftime('%m-%d %H:%M'))
        rows.append(row)
    r = pd.DataFrame(rows)
    print('=== STOP cycles: MTM at the minute before / of trigger; and lowest MTM before trigger ===')
    print(r[r.stop][['und', 'expiry', 'trig', 'mtm_prev_min', 'mtm_trig_min', 'min_before', 'min_before_t', 'final']].to_string(index=False))
    print('\n=== NON-STOP cycles: lowest MTM reached ===')
    print(r[~r.stop][['und', 'expiry', 'min_all', 'min_t', 'final']].to_string(index=False))
    r.to_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache', 'cycle_mtm_summary.pkl'))

def cycle_mtm_adverse(d, o, und, expiry):
    """pessimistic intraminute MTM: shorts marked at bar HIGH, longs at bar LOW (lower bound of the true intraminute MTM)."""
    c = d[(d.und == und) & (d.expiry == expiry)].sort_values(['t', 'row'])
    lot = c.lot.iloc[0]; c = c.assign(minute=c.t.dt.floor('min'))
    oc = o[(o.und == und) & (o.expiry == expiry)].copy(); oc['key'] = oc.cp + oc.strike.astype(int).astype(str)
    oc = oc[oc.ts.dt.normalize().isin(sorted(c.date.unique()))]
    c['key'] = c.cp + c.strike.astype(int).astype(str)
    hi = oc.pivot_table(index='ts', columns='key', values='h', aggfunc='last').sort_index().ffill()
    lo = oc.pivot_table(index='ts', columns='key', values='l', aggfunc='last').reindex(hi.index).ffill()
    # positions held at START of minute (fills before minute)
    pos = c.pivot_table(index='minute', columns='key', values='sl', aggfunc='sum').reindex(hi.index).fillna(0).cumsum().shift(1).fillna(0)
    cash = c.groupby('minute').cash.sum().reindex(hi.index).fillna(0).cumsum().shift(1).fillna(0)
    lastfill = c.groupby('key').px_fill.last()
    H = hi.reindex(columns=pos.columns); Lw = lo.reindex(columns=pos.columns)
    for k in H.columns[H.isna().all()]: H[k] = lastfill[k]; Lw[k] = lastfill[k]
    H = H.ffill().bfill(); Lw = Lw.ffill().bfill()
    val = (pos.clip(upper=0) * H + pos.clip(lower=0) * Lw).sum(axis=1) * lot
    return cash + val

def cycle_mtm_directional(d, o, und, expiry):
    """intraminute extreme consistent with ONE spot path: scenario UP (CE at high, PE at low) and DOWN (CE at low, PE at high);
    returns min(UP, DOWN) per minute, positions/cash as of minute start."""
    c = d[(d.und == und) & (d.expiry == expiry)].sort_values(['t', 'row'])
    lot = c.lot.iloc[0]; c = c.assign(minute=c.t.dt.floor('min'))
    oc = o[(o.und == und) & (o.expiry == expiry)].copy(); oc['key'] = oc.cp + oc.strike.astype(int).astype(str)
    oc = oc[oc.ts.dt.normalize().isin(sorted(c.date.unique()))]
    c['key'] = c.cp + c.strike.astype(int).astype(str)
    H = oc.pivot_table(index='ts', columns='key', values='h', aggfunc='last').sort_index()
    idx = H.index
    Lw = oc.pivot_table(index='ts', columns='key', values='l', aggfunc='last').reindex(idx)
    C = oc.pivot_table(index='ts', columns='key', values='c', aggfunc='last').reindex(idx)
    pos = c.pivot_table(index='minute', columns='key', values='sl', aggfunc='sum').reindex(idx).fillna(0).cumsum().shift(1).fillna(0)
    cash = c.groupby('minute').cash.sum().reindex(idx).fillna(0).cumsum().shift(1).fillna(0)
    lastfill = c.groupby('key').px_fill.last()
    def al(X):
        X = X.reindex(columns=pos.columns)
        for k in X.columns[X.isna().all()]: X[k] = lastfill[k]
        return X
    # missing bar in a minute -> use previous close for both extremes
    Cf = al(C).ffill().bfill(); Hh = al(H).fillna(Cf); Ll = al(Lw).fillna(Cf)
    isce = np.array([k.startswith('CE') for k in pos.columns])
    up = np.where(isce, Hh, Ll); dn = np.where(isce, Ll, Hh)
    vu = (pos.values * up).sum(axis=1) * lot; vd = (pos.values * dn).sum(axis=1) * lot
    return pd.Series(np.minimum(vu, vd), index=idx) + cash
