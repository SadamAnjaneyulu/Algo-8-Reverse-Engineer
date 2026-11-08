"""ALPHA-4: which module's sales earn the carry? Hold-to-expiry P&L of every body sale, by clock module x side x day x index, with
session-bootstrap CIs.  python3 analysis/alpha_by_module.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged(); ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
settle = ix.groupby(['und', ix.ts.dt.normalize()]).close.last()
ok = d.groupby(['und', 'expiry']).dte.agg(lambda x: (x >= 1).any() and (x == 0).any())
s = d[(d.tp == 'num') & (d.side == 'Sell')].copy()
s = s[[ok.get((u, e), False) for u, e in zip(s.und, s.expiry)]]
s['ST'] = [settle.get((u, e), np.nan) for u, e in zip(s.und, s.expiry)]; s = s.dropna(subset=['ST'])
s['intr'] = np.where(s.cp == 'CE', np.maximum(s.ST - s.strike, 0), np.maximum(s.strike - s.ST, 0))
s['hold'] = s.qty_fill * (s.px_fill - s.intr)
# module by order decision phase (first fill of order)
first = s.groupby('oid').t.transform('min'); ph = ((first - first.dt.normalize() - pd.Timedelta('09:15:00')).dt.total_seconds()) % 900
s['module'] = np.where((ph >= 55) & (ph < 180), 'grid A', np.where((ph >= 13 * 60 + 45) | (ph < 15), 'clock B', np.where(ph < 55, 'grid :00', 'unchained')))
s['cheap'] = s.px_fill < 10
s.loc[s.cheap, 'module'] = 'cheap (<Rs10) sales'
s['day'] = np.where(s.dte >= 1, 'D-1', 'D0')
step = np.where(s.und == 'NIFTY', 50, 100)
pd.set_option('display.width', 220)
t = s.groupby(['und', 'day', 'module']).agg(lots=('lots', 'sum'), hold_Rs_lakh=('hold', lambda x: x.sum() / 1e5)).round(2)
print(t.to_string())
print('\n=== by module x side (both indices), Rs lakh and session-bootstrap 95% CI of the module total ===')
rng = np.random.default_rng(0)
for (mod, cp), x in s.groupby(['module', 'cp']):
    per = x.groupby(['und', 'date']).hold.sum()
    bs = [per.sample(len(per), replace=True, random_state=i).sum() for i in range(2000)]
    print(f'{mod:20s} {cp}: {per.sum() / 1e5:+7.2f} L  CI [{np.percentile(bs, 2.5) / 1e5:+.2f}, {np.percentile(bs, 97.5) / 1e5:+.2f}]  sessions {len(per)}')
print('\ntotal hold-to-expiry carry of all body sales: Rs', round(s.hold.sum() / 1e5, 2), 'lakh')
