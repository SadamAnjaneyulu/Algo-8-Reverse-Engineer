"""Gate 5b mismatch ledger for the D0 OOF run (events as orders, mode T): every unmatched real order and every extra simulated order gets exactly one category (cascade fixed in reports/PHASE1_GATE5B_PLAN.md), by class, with window flags.
Categories (missing real order R / extra simulated order E, same option type and same side; one-to-one matching is maximal so any same-type neighbour within 60 s is matched elsewhere):
  S  supply/count: a same-type, same-side counterpart within +/-60 s matched elsewhere     W  possible wrong side: an unmatched opposite-side counterpart within 60 s
  T  timing offset: an unmatched same-side counterpart 61-300 s away                      A  absent: none within 300 s"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_common, bl_oscore as Q
import os as _os
OUT = bl_common.OUT; TAG = _os.environ.get('LEDGER_TAG', '5b'); D = f'{OUT}/phase1/{TAG}/OOF_events'; OPEN_S = 33300
real = Q.prepare_real(pd.read_csv(f'{D}/real_orders.csv')); sim = Q.prepare_sim(pd.read_csv(f'{D}/sim_orders.csv')); P = pd.read_csv(f'{D}/pairs.csv'); real['m'] = False; sim['m'] = False; real.loc[P.ri.values, 'm'] = True; sim.loc[P.si.values, 'm'] = True
for df, tc in ((real, 't'), (sim, 'sec')): df['minute'] = ((df[tc] - OPEN_S) // 60).astype(int); df['side'] = df.side.str.lower()
def pool(df, tc):
    out = {}
    for (cyc, cp, side), g in df.groupby(['cyc', 'cp', 'side']): g = g.sort_values(tc); out[(cyc, cp, side)] = (g[tc].values.astype(int), g.m.values.astype(bool))
    return out
PS, PR = pool(sim, 'sec'), pool(real, 't')
OPP = {'buy': 'sell', 'sell': 'buy'}
def near(pl, cyc, cp, side, t, only_unmatched=False):
    p = pl.get((cyc, cp, side))
    if p is None: return None
    ts, ms = p; mask = ~ms if only_unmatched else np.ones(len(ts), bool)
    if not mask.any(): return None
    d = np.where(mask, np.abs(ts - t), 10 ** 9); return int(d.min())
def cat(pl, cyc, cp, side, t):
    s = near(pl, cyc, cp, side, t); w = near(pl, cyc, cp, OPP[side], t, True); tt = near(pl, cyc, cp, side, t, True)
    if s is not None and s <= 60: return 'S'
    if w is not None and w <= 60: return 'W'
    if tt is not None and 60 < tt <= 300: return 'T'
    return 'A'
miss = real[~real.m].copy(); miss['category'] = [cat(PS, r.cyc, r.cp, r.side, int(r.t)) for r in miss.itertuples()]
ext = sim[~sim.m].copy(); ext['category'] = [cat(PR, r.cyc, r.cp, r.side, int(r.sec)) for r in ext.itertuples()]
for df in (miss, ext): df['window'] = np.where(df.minute <= 2, 'opening (to 09:17)', np.where(df.minute >= 359, 'clearance (15:14 on)', np.where(df.minute >= 345, '15:00-15:13', 'intraday')))
miss.to_csv(f'{D}/ledger_missing_real.csv', index=False); ext.to_csv(f'{D}/ledger_extra_sim.csv', index=False)
res = dict(real_orders=int(len(real)), sim_orders=int(len(sim)), matched=int(real.m.sum()), missing_real=int(len(miss)), extra_sim=int(len(ext)))
res['missing_by_class_category'] = pd.crosstab(miss.cls, miss.category).to_dict('index'); res['extra_by_class_category'] = pd.crosstab(ext.cls, ext.category).to_dict('index'); res['missing_by_class_window'] = pd.crosstab(miss.cls, miss.window).to_dict('index'); res['extra_by_class_window'] = pd.crosstab(ext.cls, ext.window).to_dict('index')
res['missing_lots_by_class'] = miss.groupby('cls').lots.sum().to_dict(); res['extra_lots_by_class'] = ext.groupby('cls').lots.sum().to_dict(); res['real_lots_by_class'] = real.groupby('cls').lots.sum().to_dict(); res['sim_lots_by_class'] = sim.groupby('cls').lots.sum().to_dict()
bc = pd.read_csv(f'{D}/by_class.csv'); res['by_class'] = bc[['cls', 'real', 'sim', 'recall', 'precision', 'F1']].round(4).to_dict('records')
json.dump(res, open(f'{OUT}/phase1/{TAG}/ledger_summary.json', 'w'), indent=1, default=float)
pd.set_option('display.width', 250); print(bc[['cls', 'real', 'sim', 'recall', 'precision', 'F1']].round(3).to_string(index=False)); print(pd.crosstab(miss.cls, miss.category)); print(pd.crosstab(ext.cls, ext.category)); print(pd.crosstab(miss.cls, miss.window)); print(pd.crosstab(ext.cls, ext.window))
