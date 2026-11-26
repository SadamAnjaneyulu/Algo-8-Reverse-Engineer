"""Phase A G2 (plan: reports/PHASE_A_G1_G6_PLAN.md): accounting of the late open-short orders. Classes: frozen ladder (same side), V1 extended breakout (any side), both, neither, plus the G1b closing-pair bursts (added after G1; labelled).
No rule is fitted. Output outputs/phaseA/g2.json, g2_orders.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_pa_g1 as G1, bl_bt3_sim as S
PA = f'{S.OUT}/phaseA'
def run():
    per, B, lo = G1.load(); T = pd.read_csv(f'{PA}/g1b_table.csv'); cond = set(T[T.cond].cyc); P = B[(B.pair == 1) & (B.j0 >= 368)]; res = {}
    lo = lo.reset_index(drop=True); lo['closing_pair'] = False
    for r in P.itertuples():
        if r.cyc in cond: lo.loc[(lo.cyc == r.cyc) & (lo.t >= r.t0) & (lo.t <= r.t0 + 15), 'closing_pair'] = True
    for tol in (1, 2, 5):
        lo[f'lad{tol}'] = [any((r.j + d, r.cp) in per[r.cyc]['lad'] for d in range(-tol, tol + 1)) for r in lo.itertuples()]; lo[f'v1_{tol}'] = [any(abs(j - r.j) <= tol for j, s, d in per[r.cyc]['v1']) for r in lo.itertuples()]
        lo[f'either{tol}'] = lo[f'lad{tol}'] | lo[f'v1_{tol}']; lo[f'any{tol}'] = lo[f'either{tol}'] | lo.closing_pair
    n = len(lo); tab = []
    for tol in (1, 2, 5):
        tab.append(dict(tolerance_min=tol, ladder=int(lo[f'lad{tol}'].sum()), v1_breakout=int(lo[f'v1_{tol}'].sum()), either=int(lo[f'either{tol}'].sum()), closing_pair_G1b=int(lo.closing_pair.sum()), explained_any=int(lo[f'any{tol}'].sum()), unexplained=int((~lo[f'any{tol}']).sum()), unexplained_share=float((~lo[f'any{tol}']).mean())))
    res['orders'] = n; res['orders_post'] = int(lo.post.sum()); res['sensitivity'] = tab
    U = lo[~lo.any1]; res['unexplained_tol1'] = dict(n=int(len(U)), cycles=int(U.cyc.nunique()), by_cycle=U.cyc.value_counts().to_dict(), by_5min_block={f'{(555 + 360 + 5 * b) // 60:02d}:{(555 + 360 + 5 * b) % 60:02d}': int(v) for b, v in (((U.j - 360) // 5).value_counts().sort_index().items())}, by_side=U.cp.value_counts().to_dict(), post=int(U.post.sum()))
    res['unexplained_single_cycle_max_share'] = float(U.cyc.value_counts().iloc[0] / len(U)) if len(U) else 0.0
    lo.to_csv(f'{PA}/g2_orders.csv', index=False); json.dump(res, open(f'{PA}/g2.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
if __name__ == '__main__': run()
