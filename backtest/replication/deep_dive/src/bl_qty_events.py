"""Lot-construction step 3: quantity per event. For body sells, per cycle x right x minute cell where both real and simulated sells exist (same minute), real lots by real sub-type vs simulated lots by simulated type; and per reactive entry (real pair-minute) real lots (pairs + attached extras) vs simulated lots.
Outputs bl_qty_events.csv, bl_summary_qe1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
SDo = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); SDo['sub'] = np.where(SDo.deep, 'deep', np.where((SDo.typ == 'solo') & (SDo.te >= 54000), 'late', SDo.typ))
ORD = pd.read_pickle(f'{OUT}/bl_fr_orders.pkl.gz')['FR free-running (primary)']; rows = []
for i in ids:
    o = ORD[i]; o = o[o.cls == 'body_sell']; s = SDo[SDo.cid == i]
    rc = s.groupby(['cp', 'j', 'sub']).lots.sum().unstack('sub', fill_value=0); sc = o.groupby(['cp', 'j', 'typ']).lots.sum().unstack('typ', fill_value=0)
    keys = set(rc.index) | set(sc.index)
    for k in keys:
        rr = rc.loc[k] if k in rc.index else pd.Series(dtype=float); ss = sc.loc[k] if k in sc.index else pd.Series(dtype=float)
        rows.append(dict(cid=i, cp=k[0], j=k[1], real=int(rr.sum()), sim=int(ss.sum()), real_main=rr.idxmax() if rr.sum() else '-', sim_main=ss.idxmax() if ss.sum() else '-', **{f'r_{t}': int(rr.get(t, 0)) for t in ('scheduled', 'reactive', 'solo', 'late', 'deep')}, **{f's_{t}': int(ss.get(t, 0)) for t in ('scheduled', 'reactive', 'extra', 'solo', 'late')}))
Q = pd.DataFrame(rows); Q.to_csv(f'{OUT}/bl_qty_events.csv', index=False); both = Q[(Q.real > 0) & (Q.sim > 0)]
print('cells', len(Q), 'both', len(both), 'real-only', int(((Q.real > 0) & (Q.sim == 0)).sum()), 'sim-only', int(((Q.real == 0) & (Q.sim > 0)).sum()))
both = both.assign(diff=both.real - both.sim); print(both.groupby('real_main').agg(cells=('diff', 'size'), real_mean=('real', 'mean'), sim_mean=('sim', 'mean'), shortfall=('diff', lambda d: int(d.clip(lower=0).sum())), excess=('diff', lambda d: int((-d).clip(lower=0).sum()))).round(2).to_string())
# reactive cells: real composition (pairs per leg + solo extras on the cell's right) vs sim
rx = both[both.r_reactive > 0]; print('reactive cells: real reactive lots per leg mean', round(rx.r_reactive.mean(), 2), 'sim reactive', round(rx.s_reactive.mean(), 2), '| real solo (extras) in same cell', round(rx.r_solo.mean(), 2), 'sim extra', round(rx.s_extra.mean(), 2))
print('real reactive lots per leg distribution', rx.r_reactive.value_counts().sort_index().to_dict(), '| sim', rx.s_reactive.value_counts().sort_index().to_dict())
print('real extras in reactive cells', rx.r_solo.value_counts().sort_index().to_dict(), '| sim extras', rx.s_extra.value_counts().sort_index().to_dict())
