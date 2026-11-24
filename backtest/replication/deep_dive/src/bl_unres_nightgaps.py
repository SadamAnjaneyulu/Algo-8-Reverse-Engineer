"""Overnight gaps of the 275 cycle nights measured at the FIRST print of D0 (09:15 open) against the D-1 close, cross-checked against the repo's daily NIFTY / SENSEX files; and the overnight variance ratio recomputed at the first print.
Corrects an earlier measurement that used the 09:16 open. Output outputs/unres/cycle_night_gaps.csv, nightgap_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); UN = f'{OUT}/unres'; REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(OUT)))), 'data_validation', 'reference'); os.makedirs(UN, exist_ok=True)
T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]; D = {}
for u, f in (('NIFTY', 'yahoo_daily_NSEI.csv'), ('SENSEX', 'yahoo_daily_BSESN.csv')):
    d = pd.read_csv(f'{REF}/{f}', parse_dates=['date_ist']).sort_values('date_ist').reset_index(drop=True); d['prev_date'] = d.date_ist.shift(1); d['prev_close'] = d.close.shift(1); D[u] = d.set_index(d.date_ist.dt.strftime('%Y-%m-%d'))
rows = []
for r in T0.itertuples():
    c = pd.read_pickle(f'{OUT}/bt3/{r.und}_{r.expiry}.pkl.gz'); O0 = float(c['spot0'].open.iloc[0]); O1 = float(c['spot0'].open.iloc[1]); C1 = float(c['spot1'].close.iloc[374]); y = D[r.und].loc[r.d0]
    rows.append(dict(und=r.und, expiry=r.expiry, d1=r.d1, d0=r.d0, gap_min_0915=np.log(O0 / C1), gap_min_0916=np.log(O1 / C1), gap_daily=np.log(y.open / y.prev_close), prev_ok=y.prev_date.strftime('%Y-%m-%d') == r.d1, split=r.split3))
g = pd.DataFrame(rows); g.to_csv(f'{UN}/cycle_night_gaps.csv', index=False)
T1 = pd.read_csv(f'{OUT}/thesis/thesis_t1.csv'); v = T1[T1.segment == 'overnight (D0 09:15 open)'].dropna(subset=['iv_used', 'rv']); v = v[v.iv_used > 0].copy(); v['ratio'] = v.rv / v.iv_used; top = v.rv.sort_values(ascending=False)
a = g.gap_min_0915.abs(); b = g.gap_min_0916.abs()
S = dict(max_abs_first_print=float(a.max()), max_abs_0916=float(b.max()), n_over_1pct=int((a > .01).sum()), n_over_2pct=int((a > .02).sum()), n_over_3pct=int((a > .03).sum()), n_over_4pct=int((a > .04).sum()), corr_min_vs_daily=float(g.gap_min_0915.corr(g.gap_daily)), prev_day_matches=float(g.prev_ok.mean()),
         first_print_cycles=int(len(v)), first_print_ratio=float(v.rv.sum() / v.iv_used.sum()), first_print_median_ratio=float(v.ratio.median()), first_print_share_over_1=float((v.ratio > 1).mean()), first_print_top10_share=float(top.head(int(np.ceil(.1 * len(top)))).sum() / top.sum()))
json.dump(S, open(f'{UN}/nightgap_summary.json', 'w'), indent=1); print(S)
