"""Before/after comparison of the execution convention (freeze_v1 baseline vs one_lot_v2). Reads the two saved scoring runs; writes outputs/scoring/split_comparison/. No P&L. Strictly a comparison of order granularity; decisions are checked for equality, not tuned."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_common
OUT = bl_common.OUT; A = f'{OUT}/scoring/d1_F'; B = f'{OUT}/scoring/d1_F_v2_onelot'; OD = f'{OUT}/scoring/split_comparison'; os.makedirs(OD, exist_ok=True)
KEY = ['cyc', 't', 'cp', 'side', 'strike', 'role']
s1 = pd.read_csv(f'{A}/sim_orders.csv'); s2 = pd.read_csv(f'{B}/sim_orders.csv'); real = pd.read_csv(f'{A}/real_orders.csv'); real2 = pd.read_csv(f'{B}/real_orders.csv')
chk = {}
chk['real_orders_identical_between_runs'] = bool(real.equals(real2))
g1 = s1.groupby(KEY).lots.sum().rename('lots_v1'); g2 = s2.groupby(KEY).lots.sum().rename('lots_v2'); m = pd.concat([g1, g2], axis=1)
chk['decision_keys_v1'] = int(g1.shape[0]); chk['decision_keys_v2'] = int(g2.shape[0]); chk['keys_only_in_one_run'] = int(m.isna().any(axis=1).sum()); chk['keys_with_different_total_lots'] = int((m.lots_v1.fillna(0) != m.lots_v2.fillna(0)).sum())
chk['total_lots_v1'] = int(s1.lots.sum()); chk['total_lots_v2'] = int(s2.lots.sum())
key_t = KEY
split = ['opening_wing_buy', 'stop_buyback']; o1 = s1[~s1.role.isin(split)].sort_values(['cyc', 't', 'seq']).reset_index(drop=True); o2 = s2[~s2.role.isin(split)].sort_values(['cyc', 't', 'seq']).reset_index(drop=True)
cols = ['cyc', 't', 'cp', 'side', 'strike', 'lots', 'role', 'validity', 'module', 'cls']
chk['non_split_roles_rows_v1'] = int(len(o1)); chk['non_split_roles_rows_v2'] = int(len(o2)); chk['non_split_roles_identical_row_by_row'] = bool(len(o1) == len(o2) and o1[cols].equals(o2[cols]))
chk['split_role_lots_all_one_v2'] = bool((s2[s2.role.isin(split)].lots == 1).all())
R = {}
for r in split:
    R[r] = dict(orders_v1=int((s1.role == r).sum()), orders_v2=int((s2.role == r).sum()), lots_v1=int(s1[s1.role == r].lots.sum()), lots_v2=int(s2[s2.role == r].lots.sum()), share_multilot_v1=float((s1[s1.role == r].lots > 1).mean()), share_multilot_v2=float((s2[s2.role == r].lots > 1).mean()))
# real-log evidence for the convention (observed)
CLASS = {'opening_wings': 'opening_wing_buy', 'body_buyback': 'stop_buyback'}; ev = {}
for c, nm in CLASS.items():
    z = real[real.cls == c]; ev[nm] = dict(real_orders=int(len(z)), real_lots=int(z.lots.sum()), share_multilot=float((z.lots > 1).mean()), max_lots=int(z.lots.max()))
other = {c: dict(real_orders=int((real.cls == c).sum()), share_multilot=float((real[real.cls == c].lots > 1).mean())) for c in sorted(real.cls.unique())}
def load(n, f): return pd.read_csv(f'{n}/all/{f}')
t1, t2 = load(A, 'tiers.csv'), load(B, 'tiers.csv'); st1, st2 = load(A, 'strictness.csv'), load(B, 'strictness.csv')
tiers = t1.merge(t2, on='tier', suffixes=('_v1', '_v2'))[['tier', 'matched_v1', 'matched_v2', 'share_of_real_v1', 'share_of_real_v2', 'share_of_sim_v1', 'share_of_sim_v2']]
stri = st1.merge(st2, on=['cumulative_tolerance_s', 'level'], suffixes=('_v1', '_v2')); stri['dF1'] = stri.F1_v2 - stri.F1_v1
b1, b2 = load(A, 'by_class.csv'), load(B, 'by_class.csv'); kk = [c for c in b1.columns if c in ('cls', 'class', 'tier', 'cumulative_tolerance_s')]
bc = b1.merge(b2, on=kk, suffixes=('_v1', '_v2'))
tiers.to_csv(f'{OD}/tiers_before_after.csv', index=False); stri.to_csv(f'{OD}/strictness_before_after.csv', index=False); bc.to_csv(f'{OD}/by_class_before_after.csv', index=False)
J = json.dumps(dict(checks=chk, split_roles=R, real_log_evidence=ev, real_log_other_classes=other), indent=1); open(f'{OD}/comparison.json', 'w').write(J); print(J)
print(tiers.round(4).to_string(index=False)); print(stri[['cumulative_tolerance_s', 'level', 'matched_v1', 'matched_v2', 'precision_v1', 'precision_v2', 'recall_v1', 'recall_v2', 'F1_v1', 'F1_v2', 'dF1']].round(4).to_string(index=False)); print(bc.round(4).to_string(index=False))
