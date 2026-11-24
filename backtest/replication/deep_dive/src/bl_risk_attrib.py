"""Which orders move the book toward delta-neutrality between 14:15 and the close? (follow-up to reports/LATE_SALE_RISK_PLAN.md; EXPLORATORY, counted as a post-hoc analysis)
For every complete cycle the end-of-session book (prices of the last minute) is rebuilt WITHOUT one group of orders placed after 14:15 and compared with the actual book:
late shorts (>=15:15), earlier shorts (14:15-15:14), overnight lump (module v_), wings (module h_), stops/covers, everything else. effect = |delta without| - |delta actual| (positive: the group reduces |net delta|).
Output outputs/risk/attrib_cycles.csv, attrib_summary.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import binomtest
import bl_bt3_sim as S, bl_d0x_diag as DG, bl_risk_book as B
OUT = S.OUT; RK = f'{OUT}/risk'; GROUPS = ['late_shorts_1515+', 'mid_shorts_1415-1514', 'lump_v_', 'wings_h_', 'covers_stops', 'other']
def group(q):
    if q.jj < 300: return None
    if q.role == 'open_short': return 'late_shorts_1515+' if q.jj >= 360 else 'mid_shorts_1415-1514'
    if q.module == 'v_': return 'lump_v_'
    if q.module == 'h_': return 'wings_h_'
    if q.role == 'cover_short': return 'covers_stops'
    return 'other'
if __name__ == '__main__':
    O = DG.real_orders(); O = O.assign(jj=(O.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); rows = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_last', 'row']).reset_index(drop=True)
        if not len(g): continue
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); op = cx['opt1']; Kc = op['K']; kidx = {int(k): i for i, k in enumerate(Kc)}; nmin = op[('CE', 'close')].shape[1]; spot = cx['spot1'].close.values; unit = float(r.unit); jend = nmin - 1
        Pc = op[('CE', 'close')][:, jend - 1]; Pp = op[('PE', 'close')][:, jend - 1]; F = B.parity_forward(Kc, Pc, Pp, spot[jend - 1]); now = pd.Timestamp(r.d1) + pd.Timedelta(hours=9, minutes=15 + jend); Tt = max((pd.Timestamp(r.d0) + pd.Timedelta(hours=15, minutes=30) - now).total_seconds() / 86400 / 365, 1e-5); V = B.leg_values(Kc, Pc, Pp, F, Tt)
        pos = {gname: np.zeros((len(Kc), 2)) for gname in GROUPS + ['before1415']}
        for _, q in g.iterrows():
            k = kidx.get(int(q.strike)); c = 0 if q.cp == 'CE' else 1
            if k is None: continue
            gn = group(q); pos['before1415' if gn is None else gn][k, c] += q.sg * q.lots
        total = sum(pos.values()); act = B.state(total, V, F, unit); row = dict(und=r.und, d1=r.d1, era='after' if r.d0 >= '2026-08-03' else 'before', outlier=int((r.und, r.d1) == ('NIFTY', '2026-10-16')), abs_delta_actual=abs(act['delta_rs_pct']), gap_worst_actual=act['gap_worst'], start_abs_delta=abs(B.state(pos['before1415'], V, F, unit)['delta_rs_pct']))
        for gn in GROUPS:
            st = B.state(total - pos[gn], V, F, unit); row[f'd_absdelta_{gn}'] = abs(st['delta_rs_pct']) - abs(act['delta_rs_pct']); row[f'd_gap_{gn}'] = act['gap_worst'] - st['gap_worst']; row[f'lots_{gn}'] = float(np.abs(pos[gn]).sum())
        rows.append(row)
    A = pd.DataFrame(rows); A.to_csv(f'{RK}/attrib_cycles.csv', index=False); P = A[A.outlier == 0]; out = {}
    for gn in GROUPS:
        act_ = P[P[f'lots_{gn}'] > 0]; e = act_[f'd_absdelta_{gn}']; gp = act_[f'd_gap_{gn}']
        out[gn] = dict(cycles_with_orders=int(len(act_)), reduces_abs_delta=int((e > 0).sum()), p_sign=float(binomtest(int((e > 0).sum()), len(act_), 0.5).pvalue) if len(act_) else None, median_effect_rs_per_1pct=float(e.median()) if len(act_) else None, mean_effect=float(e.mean()) if len(act_) else None,
                       improves_gap_worst=int((gp > 0).sum()), median_gap_effect=float(gp.median()) if len(act_) else None)
    out['median_abs_delta_start_vs_end'] = [float(P.start_abs_delta.median()), float(P.abs_delta_actual.median())]; out['cycles'] = int(len(P))
    json.dump(out, open(f'{RK}/attrib_summary.json', 'w'), indent=1, default=float)
    for gn in GROUPS: print(f'{gn:24s}', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[gn].items()})
    print('median |delta| ₹/1% at 14:15 (book before 14:15) vs close:', [round(x) for x in out['median_abs_delta_start_vs_end']], 'cycles', out['cycles'])
