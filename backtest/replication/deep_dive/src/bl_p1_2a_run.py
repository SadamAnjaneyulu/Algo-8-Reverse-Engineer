"""Run P1-2A candidate variants (plan reports/PHASE1_GATE2A_PLAN.md) on the 32 cycles under the accepted one_lot_v2 convention, score with spec v1.1 (mode F, historical reproduction), save under outputs/phase1/2A/<ID>/. Usage: python bl_p1_2a_run.py V01 V02 ..."""
import sys, os, json, time, hashlib, datetime, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
VARIANTS = {'SL10': dict(stop_latency_s=10.0), 'SL20': dict(stop_latency_s=20.0), 'SL30': dict(stop_latency_s=30.0), 'BK0': dict(breakout_one_lot=True), 'BK1': dict(breakout_one_lot=True, breakout_size_after_s=10.0), 'BK2': dict(breakout_one_lot=True, breakout_size_after_s=30.0), 'BK3': dict(breakout_one_lot=True, breakout_size_after_s=60.0), 'V00': {}, 'V01': dict(ladder_book_condition=True), 'V02': dict(ladder_gate_min=15), 'V03': dict(ladder_gate_min=5), 'V04': dict(ladder_lots_mode='steps'), 'V05': dict(ladder_lots_mode='steps', ladder_step=0.1), 'V06': dict(ladder_lots_mode='steps', ladder_step=0.05), 'V07': dict(ladder_step=0.1), 'V08': dict(ladder_step=0.05)}
def _run(args):
    import validate_engine as V
    i, ov = args; return V.run_cycle(i, dict(order_split='one_lot_v2', **ov))
if __name__ == '__main__':
    import bl_common, bl_oscore as Q, bl_fr_sim as S, bl_score_d1_F as B, bl_p1_eval as E
    OUT = bl_common.OUT; CY = S.CY; ids = sys.argv[1:]
    for vid in ids:
        ov = VARIANTS[vid] if vid in VARIANTS else json.loads(os.environ['P1_OVERRIDES']); OD = f'{OUT}/phase1/' + ('2D' if vid.startswith('BK') else '3A' if vid.startswith('SL') else '2A') + f'/{vid}'
        if os.path.exists(f'{OD}/run_record.json'): print(vid, 'already exists; baseline/candidate runs are never overwritten'); continue
        os.makedirs(f'{OD}/all', exist_ok=True); t0 = time.time()
        with Pool(8) as p: res = p.map(_run, [(i, ov) for i in range(len(CY))])
        ORD = {i: df for i, df, _ in res}; rej = int(sum(n for _, _, n in res)); sim = B.build_sim(ORD, CY); real = B.build_real(CY); attrs = B.build_attrs(CY)
        leg = Q.legacy_d1_scores(ORD, CY, S.REAL, bl_common.ref.STEP).set_index('cls').loc['ALL']
        R = Q.score(real, sim, attrs, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
        for k in ('tiers', 'strictness', 'by_class', 'by_block', 'per_cycle', 'state_after_matched', 'checkpoints', 'class_confusion'):
            if isinstance(R.get(k), pd.DataFrame): R[k].to_csv(f'{OD}/all/{k}.csv', index=False)
        for k, v in R['unmatched'].items():
            if isinstance(v, pd.DataFrame): v.to_csv(f'{OD}/all/unmatched_{k}.csv', index=False)
        R['_pairs'].to_csv(f'{OD}/all/pairs.csv', index=False); sim.to_csv(f'{OD}/sim_orders.csv', index=False); real.to_csv(f'{OD}/real_orders.csv', index=False)
        sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest(); eng = '../../../../d1_strategy/d1_algo'
        json.dump(dict(id=vid, overrides=ov, order_split='one_lot_v2', mode='F', evidence_label='historical reproduction', engine_orders=int(len(sim)), real_orders=int(len(real)), rejected=rej, legacy_f1=float(leg.F1), engine_sha256={f: sha(f'{eng}/{f}') for f in ('engine.py', 'config.py', 'risk.py', 'models.py')}, spec=Q.spec_record(), seconds=round(time.time() - t0), run_at=datetime.datetime.now(datetime.timezone.utc).isoformat()), open(f'{OD}/run_record.json', 'w'), indent=1)
        m = E.body_metrics(OD); print(vid, ov, '| orders', len(sim), 'rej', rej, 'legacy', round(float(leg.F1), 4), '| body F1', round(m['F1'], 4), 'strict', round(m['strict_F1'], 4), 'rec', round(m['recall'], 3), 'prec', round(m['precision'], 3), 'lots', m['sim_lots'], 'extras', m['extras'], flush=True)
