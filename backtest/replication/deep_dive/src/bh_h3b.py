"""H3b: contract-level quiet-time balance. At T = (a body order's fill second + 30 s) with no other body order in (t, T], per (cycle, right):
S = short lots (sum over contracts of max(0, -net)), L = long lots (sum of max(0, net)), net per contract over ALL modules (ownership-free). gap = S - L. Cycles with unknown carry-in excluded.
Also L_h = long lots from h_ and v_ orders only (net by contract over those modules) to see whether other modules' longs matter. Output outputs/bh_h3b_quiet.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
X = fills_x(); X['tt'] = X.dayno * 100000 + X.sec; X['sl'] = X.sgn * X.n_lots
O = order_table(X); B = O[O.module == 'num']
rows = []
for (u, e), c in X.groupby(['und', 'expiry']):
    if not bool(c.carry_in_known.iloc[0]): continue
    for cp in ('CE', 'PE'):
        x = c[c.cp == cp].sort_values(['tt', 'row']); b = B[(B.und == u) & (B.expiry == e) & (B.cp == cp)].sort_values('tt_first'); bt = b.tt_first.values
        if not len(b): continue
        keys = sorted(x.strike.unique()); cum = {}; cumw = {}
        for k in keys:
            y = x[x.strike == k]; cum[k] = (y.tt.values, np.cumsum(y.sl.values)); yw = y[y.module.isin(['h_', 'v_'])]; cumw[k] = (yw.tt.values, np.cumsum(yw.sl.values))
        def net(d, T):
            i = np.searchsorted(d[0], T, side='right'); return d[1][i - 1] if i > 0 else 0
        for i, t in enumerate(bt):
            T = t + 30; nxt = bt[i + 1] if i + 1 < len(bt) else 1e18
            if nxt <= T: continue            # not quiet
            n = np.array([net(cum[k], T) for k in keys]); nw = np.array([net(cumw[k], T) for k in keys])
            S = -n[n < 0].sum(); Lg = n[n > 0].sum(); Lh = nw[nw > 0].sum()
            rows.append((u, e, cp, int(b.dayno.iloc[i]), t, T, S, Lg, Lh))
Q = pd.DataFrame(rows, columns=['und', 'expiry', 'cp', 'dayno', 'tt', 'T', 'S', 'L_all', 'L_hv']); Q['gap_all'] = Q.S - Q.L_all; Q['gap_hv'] = Q.S - Q.L_hv; Q.to_csv(f'{OUT}/bh_h3b_quiet.csv', index=False)
print('quiet samples', len(Q), 'cycles', Q.groupby(['und', 'expiry']).ngroups)
for nm, g in Q.groupby('dayno'):
    print('day', nm, len(g), 'gap_all==0', (g.gap_all == 0).mean().round(3), '|gap|<=1', (g.gap_all.abs() <= 1).mean().round(3), 'gap_hv==0', (g.gap_hv == 0).mean().round(3), 'median S', g.S.median(), 'median L_all', g.L_all.median(), 'gap_all quantiles', g.gap_all.quantile([.1, .25, .5, .75, .9]).tolist())
