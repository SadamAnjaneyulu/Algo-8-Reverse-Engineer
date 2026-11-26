"""Post-hoc check of the reading "stop-loss buy-back of R + sale of the opposite right R' at the same time, to control sharp moves".
Per stop-loss event: sale of R' within windows; change in the lot balance (R' lots - R lots) over the next two minutes; spot move over the next 15 minutes in the direction that hurt R.
Outputs bl_d0n_userview.csv, bl_summary_d0n6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import json
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz')
rng = np.random.default_rng(131); R = {}; other = lambda c: 'PE' if c == 'CE' else 'CE'
EV = X[X.type == '3 stop-loss'].groupby(['cid', 'cp', 'tod']).agg(lots=('lid', 'size'), j=('j', 'min')).reset_index(); K = PN.set_index(['cid', 'j', 'cp'])
rows = []
for q in EV.itertuples():
    s = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp))]; d = s.tod.values - q.tod; o = other(q.cp)
    r_ = dict(cid=q.cid, cp=q.cp, j=int(q.j), lots=q.lots, **{f'sale_{w}': bool((np.abs(d) <= w).any()) for w in (2, 5, 10, 60)}, sale_after_0_60=bool(((d >= 0) & (d <= 60)).any()))
    a = (q.cid, int(q.j), o); b = (q.cid, int(q.j) + 2, o)
    if a in K.index and b in K.index: r_['d_balance'] = (K.loc[b, 'n_own'] - K.loc[b, 'n_other']) - (K.loc[a, 'n_own'] - K.loc[a, 'n_other'])                # R' lots minus R lots, minute j -> j+2
    c = SP[(CY.und.iloc[q.cid], CY.expiry.iloc[q.cid])].close.values; st = float(ref.STEP[CY.und.iloc[q.cid]]); sg = 1.0 if q.cp == 'CE' else -1.0                  # + = the direction that hurt R
    if q.j + 15 < len(c): r_['after_15'] = sg * (c[q.j + 15] - c[q.j]) / st; r_['after_5'] = sg * (c[q.j + 5] - c[q.j]) / st
    r_['before_5'] = sg * (c[q.j] - c[max(q.j - 5, 0)]) / st; rows.append(r_)
E = pd.DataFrame(rows); E.to_csv(f'{OUT}/bl_d0n_userview.csv', index=False)
R['events'] = len(E); R['share_with_sale'] = {w: float(E[f'sale_{w}'].mean()) for w in (2, 5, 10, 60)}
R['d_balance'] = {k: dict(n=int(g.d_balance.notna().sum()), mean=float(g.d_balance.mean()), median=float(g.d_balance.median()), share_up=float((g.d_balance > 0).mean()), share_down=float((g.d_balance < 0).mean())) for k, g in E.groupby('sale_2')}
R['after_15'] = {k: dict(n=int(g.after_15.notna().sum()), mean=float(g.after_15.mean()), median=float(g.after_15.median())) for k, g in E.groupby('sale_2')}; R['before_5'] = {k: float(g.before_5.mean()) for k, g in E.groupby('sale_2')}
u = E.cid.unique(); b = []
for _ in range(300):
    g = pd.concat([E[E.cid == c_] for c_ in rng.choice(u, len(u))]); a1 = g[g.sale_2].after_15.mean(); a0 = g[~g.sale_2].after_15.mean(); b.append(a1 - a0)
R['after_15_diff_with_minus_without'] = dict(diff=float(E[E.sale_2].after_15.mean() - E[~E.sale_2].after_15.mean()), ci=[float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))])
rec('d0n6', R); print(json.dumps(R, indent=1, default=float) if False else R)
