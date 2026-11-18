"""P4b: per-leg premium-target strike selector vs nearest-ATM.   python3 analysis/p4_premium_target.py
For each body sell order, candidates = strikes K0-3..K0+3 steps (K0 = ATM from previous-minute index close) with a previous-minute option close.
Rule: pick candidate whose prev-minute premium is closest to target T. Target variants are causal (known before the order)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
f = pd.read_pickle(os.path.join(C, 'p4_orders_feat.pkl')).sort_values('t').reset_index(drop=True)
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
# previous-minute close lookup: price available at minute m = close of bar m-1
pc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).set_index(['und', 'expiry', 'cp', 'm', 'strike']).c.sort_index()
f['K0'] = (f.prev_close / f.step).round() * f.step
cand = []
for r in f.itertuples():
    ks = [r.K0 + j * r.step for j in range(-3, 4)]
    try: s = pc.loc[(r.und, r.expiry, r.cp, r.m)]
    except KeyError: cand.append(None); continue
    cand.append({k: s.get(k, np.nan) for k in ks})
f['cand'] = cand
f = f[f.cand.notna()].copy()
f['p_atm'] = [c.get(k0, np.nan) for c, k0 in zip(f.cand, f.K0)]
f['p_sold'] = [c.get(k, np.nan) for c, k in zip(f.cand, f.strike)]
# other-leg ATM premium (same minute) for straddle-half target
other = {('CE'): 'PE', ('PE'): 'CE'}
f['p_other_atm'] = [pc.get((u, e, other[cp], m, k0), np.nan) for u, e, cp, m, k0 in zip(f.und, f.expiry, f.cp, f.m, f.K0)]
# causal targets
f['T_first'] = f.groupby(['date', 'cp']).p_sold.transform('first')          # premium of the day's first sale of that leg
f['T_prev'] = f.groupby(['date', 'cp']).p_sold.shift(1)                       # premium of previous sale of that leg
f['T_half'] = (f.p_atm + f.p_other_atm) / 2                                    # half the current ATM straddle
def pick(c, T):
    if not np.isfinite(T): return np.nan
    v = {k: p for k, p in c.items() if np.isfinite(p)}
    return min(v, key=lambda k: abs(v[k] - T)) if v else np.nan
out = []
f['pred_atm'] = f.K0
for T in ['T_first', 'T_prev', 'T_half']:
    f['pred_' + T] = [pick(c, t) for c, t in zip(f.cand, f[T])]
pd.set_option('display.width', 200)
for (day, grid), g in f.groupby(['day', 'grid']):
    row = dict(day=day, grid=grid, n=len(g))
    for p in ['pred_atm', 'pred_T_first', 'pred_T_prev', 'pred_T_half']:
        ok = g[p].notna(); row[p] = round((g.loc[ok, p] == g.loc[ok, 'strike']).mean(), 3)
    out.append(row)
print(pd.DataFrame(out).to_string(index=False))
f.drop(columns=['cand']).to_pickle(os.path.join(C, 'p4_orders_prem.pkl'))
