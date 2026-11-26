"""F vs TF-E comparison tables (plan reports/D1_TFE_PLAN.md): real-order recovery, extras, decomposition, block gap, per-cycle, pre-emption diagnostic. Reads saved scoring runs only. No P&L, nothing tuned."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_common
OUT = bl_common.OUT; S = f'{OUT}/scoring'; OD = f'{S}/tfe_comparison'; os.makedirs(OD, exist_ok=True)
RUNS = {'F': 'd1_F_v2_onelot', 'TFE_all': 'd1_TFE_v2_onelot', 'TFE_first': 'd1_TFE_first_v2_onelot', 'TFEm_all': 'd1_TFE_m_v2_onelot', 'TFEm_first': 'd1_TFE_m_first_v2_onelot'}
real = pd.read_csv(f'{S}/{RUNS["F"]}/real_orders.csv')
for k, d in RUNS.items():
    if os.path.exists(f'{S}/{d}/real_orders.csv'): assert pd.read_csv(f'{S}/{d}/real_orders.csv').equals(real), f'real orders differ in {d}'
P = {k: pd.read_csv(f'{S}/{d}/all/pairs.csv') for k, d in RUNS.items() if os.path.exists(f'{S}/{d}/all/pairs.csv')}
def matched(k, tol):                                                        # boolean array over real orders: matched in run k within cumulative tier <= tol (0: exact, 1: <=5 s, 2: <=60 s)
    m = np.zeros(len(real), bool); p = P[k]; m[p.ri[p.tier <= tol].values] = True; return m
blk = (real.t // 1800).astype(int); out = {}
def classify(a, b):                                                         # a = F matched, b = TF-E matched
    return np.where(a & b, 'both', np.where(~a & b, 'TFE_only', np.where(a & ~b, 'F_only', 'neither')))
rec_rows = []; dec = {}
for k in [x for x in P if x != 'F']:
    for tol, nm in ((0, '0s'), (1, '5s'), (2, '60s')):
        c = classify(matched('F', tol), matched(k, tol)); tab = pd.crosstab(real.cls, c).reindex(columns=['both', 'TFE_only', 'F_only', 'neither'], fill_value=0)
        tab['total'] = tab.sum(axis=1); tab.loc['ALL'] = tab.sum(); tab = tab.reset_index().assign(treatment=k, tolerance=nm); rec_rows.append(tab)
        a = tab[tab.cls == 'ALL'].iloc[0]; fmiss = a.TFE_only + a.neither; dec[f'{k}@{nm}'] = dict(F_missing=int(fmiss), recovered_by_TFE=int(a.TFE_only), harmed_F_only=int(a.F_only), persistent_neither=int(a.neither), share_of_F_missing_recovered=float(a.TFE_only / max(fmiss, 1)), share_of_F_missing_persistent=float(a.neither / max(fmiss, 1)), net_change_in_matched=int(a.TFE_only - a.F_only))
pd.concat(rec_rows).to_csv(f'{OD}/real_order_recovery.csv', index=False)
# per block recovery at 60 s (first decisions and all)
for k in ('TFE_all', 'TFE_first'):
    c = classify(matched('F', 2), matched(k, 2)); t = pd.crosstab(blk, c).reindex(columns=['both', 'TFE_only', 'F_only', 'neither'], fill_value=0).reset_index().rename(columns={'t': 'block'}); t['block_start'] = [f'{(b * 1800) // 3600:02d}:{((b * 1800) % 3600) // 60:02d}' for b in t.iloc[:, 0]]; t.to_csv(f'{OD}/recovery_by_block_{k}.csv', index=False)
# extras and class tables side by side
ex = None
for k, d in RUNS.items():
    f = f'{S}/{d}/all/unmatched_extra_by_cls.csv'
    if os.path.exists(f): z = pd.read_csv(f)[['cls', 'orders']].rename(columns={'orders': k}); ex = z if ex is None else ex.merge(z, on='cls', how='outer')
ex.fillna(0).to_csv(f'{OD}/extra_orders_by_class.csv', index=False)
bc = None
for k, d in RUNS.items():
    f = f'{S}/{d}/all/by_class.csv'
    if os.path.exists(f): z = pd.read_csv(f)[['cls', 'sim', 'recall', 'precision', 'F1']].rename(columns=lambda c: c if c == 'cls' else f'{c}_{k}'); bc = z if bc is None else bc.merge(z, on='cls', how='outer')
bc.to_csv(f'{OD}/by_class_side_by_side.csv', index=False)
bb = None
for k, d in RUNS.items():
    f = f'{S}/{d}/all/by_block.csv'
    if os.path.exists(f): z = pd.read_csv(f)[['block_start', 'real', 'sim', 'recall', 'precision', 'F1']].rename(columns=lambda c: c if c == 'block_start' else f'{c}_{k}'); bb = z if bb is None else bb.merge(z, on='block_start', how='outer')
bb.to_csv(f'{OD}/by_block_side_by_side.csv', index=False)
# per-cycle
pc = None
for k, d in RUNS.items():
    f = f'{S}/{d}/all/per_cycle.csv'
    if os.path.exists(f): z = pd.read_csv(f)[['cyc', 'sim', 'matched', 'F1']].rename(columns=lambda c: c if c == 'cyc' else f'{c}_{k}'); pc = z if pc is None else pc.merge(z, on='cyc')
for k in ('TFE_all', 'TFE_first'): pc[f'dF1_{k}'] = pc[f'F1_{k}'] - pc['F1_F']
pc.to_csv(f'{OD}/per_cycle_side_by_side.csv', index=False)
pcs = {k: dict(improved=int((pc[f'dF1_{k}'] > 0).sum()), harmed=int((pc[f'dF1_{k}'] < 0).sum()), median_dF1=float(pc[f'dF1_{k}'].median()), min_dF1=float(pc[f'dF1_{k}'].min()), max_dF1=float(pc[f'dF1_{k}'].max())) for k in ('TFE_all', 'TFE_first')}
# pre-emption diagnostic: real wing/stop orders matched in F but not in TF-E (first decisions): was the simulator LATER than the real order in F (dt = sim - real > 0)? then a real reaction already in the forced book pre-empts the simulator's own reaction
pf = P['F'].set_index('ri'); pre = {}
for k in ('TFE_all', 'TFE_first'):
    harmed = np.where(matched('F', 2) & ~matched(k, 2))[0]; z = real.iloc[harmed].assign(dtF=pf.loc[harmed, 'dt'].values)
    pre[k] = {c: dict(n=int((z.cls == c).sum()), sim_later_than_real_in_F=float((z[z.cls == c].dtF > 0).mean()) if (z.cls == c).any() else None, median_dt_F=float(z[z.cls == c].dtF.median()) if (z.cls == c).any() else None) for c in ('wing_buy', 'wing_sell', 'body_buyback', 'body_sell', 'opening_wings', 'lump')}
    ref = real.iloc[np.where(matched('F', 2) & matched(k, 2))[0]].assign(dtF=pf.loc[np.where(matched('F', 2) & matched(k, 2))[0], 'dt'].values); pre[k]['all_matched_in_both_reference'] = {c: dict(n=int((ref.cls == c).sum()), sim_later_than_real_in_F=float((ref[ref.cls == c].dtF > 0).mean()) if (ref.cls == c).any() else None) for c in ('wing_buy', 'wing_sell', 'body_buyback')}
# carpet diagnostic: how many matched TF-E stop buy-backs are re-decisions (repeats created by the reset loop)?
sa = pd.read_csv(f'{S}/{RUNS["TFE_all"]}/sim_orders.csv'); pa = P['TFE_all']; mm = sa.iloc[pa.si.values]; carpet = dict(stop_orders_all=int((sa.role == 'stop_buyback').sum()), stop_redecisions=int(((sa.role == 'stop_buyback') & sa.redecision).sum()), matched_stop_orders=int((mm.role == 'stop_buyback').sum()), matched_stop_orders_that_are_redecisions=int(((mm.role == 'stop_buyback') & mm.redecision).sum()))
carpet['share_of_matched_stop_orders_that_are_redecisions'] = carpet['matched_stop_orders_that_are_redecisions'] / max(carpet['matched_stop_orders'], 1)
# drift
dr = pd.read_csv(f'{S}/{RUNS["TFE_all"]}/pre_reset_drift.csv'); dr['l1_norm'] = dr.l1 / dr.gross_real.clip(lower=1); dr['block'] = (dr.t // 1800).astype(int); dr['SL_equal'] = (dr.S_sim_CE == dr.S_real_CE) & (dr.S_sim_PE == dr.S_real_PE) & (dr.L_sim_CE == dr.L_real_CE) & (dr.L_sim_PE == dr.L_real_PE)
dg = dr.groupby('block').agg(resets=('t', 'size'), SL_equal=('SL_equal', 'mean'), l1_norm_mean=('l1_norm', 'mean'), l1_norm_p90=('l1_norm', lambda x: x.quantile(.9))).reset_index(); dg['block_start'] = [f'{(b * 1800) // 3600:02d}:{((b * 1800) % 3600) // 60:02d}' for b in dg.block]; dg.to_csv(f'{OD}/pre_reset_drift_by_block.csv', index=False)
res = dict(carpet_diagnostic=carpet, decomposition=dec, per_cycle_change=pcs, preemption_diagnostic=pre, pre_reset_drift=dict(resets=int(len(dr)), SL_equal_share=float(dr.SL_equal.mean()), l1_norm_mean=float(dr.l1_norm.mean()), l1_norm_median=float(dr.l1_norm.median()), l1_norm_p90=float(dr.l1_norm.quantile(.9))))
json.dump(res, open(f'{OD}/comparison.json', 'w'), indent=1)
pd.set_option('display.width', 250); print(json.dumps(res['decomposition'], indent=1)); print(json.dumps(pcs, indent=1)); print(json.dumps(pre, indent=1)[:2500]); print(json.dumps(res['pre_reset_drift'], indent=1)); print(dg.round(3).to_string(index=False))
r60 = pd.read_csv(f'{OD}/real_order_recovery.csv'); print(r60[(r60.tolerance == '60s') & (r60.treatment == 'TFE_first')].to_string(index=False)); print(bc.round(3).to_string(index=False)); print(bb.round(3)[['block_start', 'F1_F', 'F1_TFE_all', 'F1_TFE_first']].to_string(index=False))
