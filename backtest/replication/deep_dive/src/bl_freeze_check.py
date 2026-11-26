"""Integrity check after the decision-id/guard refactor: (1) freeze_v1 replay == saved baseline outputs/scoring/d1_F/sim_orders.csv (all columns); (2) one_lot_v2 replay == saved outputs/scoring/d1_F_v2_onelot/sim_orders.csv. Writes outputs/scoring/split_comparison/freeze_integrity.json only."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
import pandas as pd, validate_engine as V, bl_fr_sim as S, bl_common
import bl_score_d1_F as B
def run(conv):
    B.CONV = conv
    with Pool(8) as p: res = p.map(_f1 if conv == 'freeze_v1' else _f2, range(len(S.CY)))
    return B.build_sim({i: df for i, df, _ in res}, S.CY), int(sum(n for _, _, n in res))
def _f1(i): return V.run_cycle(i)
def _f2(i): return V.run_cycle(i, dict(order_split='one_lot_v2'))
if __name__ == '__main__':
    OUT = bl_common.OUT; o = {}
    for conv, path in (('freeze_v1', f'{OUT}/scoring/d1_F/sim_orders.csv'), ('one_lot_v2', f'{OUT}/scoring/d1_F_v2_onelot/sim_orders.csv')):
        sim, rej = run(conv); saved = pd.read_csv(path); cols = [c for c in saved.columns]
        a = sim[cols].reset_index(drop=True); b = saved.reset_index(drop=True)
        same = bool(len(a) == len(b) and a.astype(str).equals(b.astype(str)))
        o[conv] = dict(rows=int(len(a)), rows_saved=int(len(b)), identical_to_saved=same, rejected=rej, columns_compared=cols)
    json.dump(o, open(f'{OUT}/scoring/split_comparison/freeze_integrity.json', 'w'), indent=1); print(json.dumps({k: {x: y for x, y in v.items() if x != 'columns_compared'} for k, v in o.items()}, indent=1))
