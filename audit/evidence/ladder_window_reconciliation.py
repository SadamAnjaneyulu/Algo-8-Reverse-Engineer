"""Read-only reconciliation of the 10:15 / 10:16 D-1 ladder size (lineage X modal 4 vs lineage Y modal 2-3). Descriptive counts of actual body sales only.
Lineage X window: [T-2 s, T+3 min) around 10:15; lineage Y (analysis/ladder.py): fills floored to the minute, minutes 0-2 after 10:16:00 -> [10:16:00, 10:19:00).
Run:  python3 audit/evidence/ladder_window_reconciliation.py <path to analysis/> -> audit/evidence/ladder_window_reconciliation.csv"""
import sys, os, collections
AN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'analysis')
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine'))
import numpy as np, pandas as pd
from common import orders
o = orders(); s = o[(o.side == 'Sell') & (o.label == 'open') & (o.dte >= 1) & (o.tp == 'num')].copy(); s['t'] = pd.to_datetime(s.t_fill)
wins = {'lineage Y window [10:16:00, 10:19:00)': (0, 180), 'last 10 s before 10:16:00 [10:15:50, 10:16:00)': (-10, 0),
        'exact two seconds before 10:16:00 [10:15:58, 10:16:00)': (-2, 0),
        'lineage X window [10:15:58, 10:19:00)': (-2, 180), 'whole minute 10:15 [10:15:00, 10:16:00)': (-60, 0)}
res = {k: {'CE': [], 'PE': []} for k in wins}
for (u, e, d), g in s.groupby(['und', 'expiry', 'date']):
    base = pd.Timestamp(d) + pd.Timedelta('10:16:00')
    for name, (a, b) in wins.items():
        w = g[(g.t >= base + pd.Timedelta(seconds=a)) & (g.t < base + pd.Timedelta(seconds=b))]
        for cp in ('CE', 'PE'): res[name][cp].append(int(w[w.cp == cp].lots.sum()))
rows = []
for name, r in res.items():
    for cp, v in r.items():
        v = np.array(v); mc = collections.Counter(v).most_common(2)
        rows.append(dict(window=name, side=cp, sessions=len(v), mean_lots=round(float(v.mean()), 2), modal_lots=int(mc[0][0]), modal_share=round(mc[0][1] / len(v), 2),
                         second_mode=int(mc[1][0]) if len(mc) > 1 else None, sessions_with_any=int((v > 0).sum())))
# additivity check on a per-session basis: X-window lots == Y-window lots + exact-2-second lots (no double counting, no gap)
chk = {cp: np.array(res['lineage X window [10:15:58, 10:19:00)'][cp]) - np.array(res['lineage Y window [10:16:00, 10:19:00)'][cp]) - np.array(res['exact two seconds before 10:16:00 [10:15:58, 10:16:00)'][cp]) for cp in ('CE', 'PE')}
print('per-session residual X - Y - exact2s (must be 0):', {cp: int(np.abs(v).sum()) for cp, v in chk.items()})
R = pd.DataFrame(rows); R.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ladder_window_reconciliation.csv'), index=False); print(R.to_string(index=False))
