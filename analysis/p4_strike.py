"""P4: which reference price does the body use to pick the sold strike?   python3 analysis/p4_strike.py
Unit: each body (numeric-tag) SELL order with price >= 10 (excludes cheap-wing sales). Candidate references from Breeze bars:
index close of previous minute / open of current minute / close of current minute / mid; synthetic forward from option bars (parity at the
traded strike, same minute). Accuracy = share of orders whose strike == round(ref/step)*step."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged()
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')).set_index(['und', 'ts']).sort_index()
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
f = d[(d.tp == 'num') & (d.side == 'Sell') & (d.px_fill >= 10)].groupby('oid').first().reset_index()
f['m'] = f.t.dt.floor('min'); f['step'] = np.where(f.und == 'NIFTY', 50, 100)
def ixv(u, ts, col):
    try: return ix.loc[(u, ts), col]
    except KeyError: return np.nan
f['prev_close'] = [ixv(u, m - pd.Timedelta(minutes=1), 'close') for u, m in zip(f.und, f.m)]
f['cur_open'] = [ixv(u, m, 'open') for u, m in zip(f.und, f.m)]
f['cur_close'] = [ixv(u, m, 'close') for u, m in zip(f.und, f.m)]
f['prev2_close'] = [ixv(u, m - pd.Timedelta(minutes=2), 'close') for u, m in zip(f.und, f.m)]
# synthetic forward from previous-minute option closes at the sold strike: F = K + C - P
oc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).pivot_table(index=['und', 'expiry', 'strike', 'm'], columns='cp', values='c', aggfunc='last')
key = list(zip(f.und, f.expiry, f.strike, f.m))
cc = oc.reindex(key)
f['syn_fwd_prev'] = f.strike.values + cc['CE'].values - cc['PE'].values
f['day'] = np.where(f.dte >= 1, 'D-1', 'D0')
mins = (f.t.dt.hour * 60 + f.t.dt.minute) - (9 * 60 + 16); f['grid'] = (mins % 15 <= 2) & (mins >= 0)
res = []
for ref in ['prev_close', 'prev2_close', 'cur_open', 'cur_close', 'syn_fwd_prev']:
    atm = (f[ref] / f.step).round() * f.step
    f['off_' + ref] = ((f.strike - atm) / f.step)
    ok = f.strike == atm
    for (day, g), sub in f.assign(ok=ok).groupby(['day', 'grid']):
        res.append(dict(ref=ref, day=day, grid_slot=g, n=len(sub), exact=round(sub.ok.mean(), 3), within1=round((sub['off_' + ref].abs() <= 1).mean(), 3)))
pd.set_option('display.width', 200)
print(pd.DataFrame(res).pivot_table(index='ref', columns=['day', 'grid_slot'], values='exact').round(3).to_string())
f.to_pickle(os.path.join(C, 'p4_orders.pkl'))
