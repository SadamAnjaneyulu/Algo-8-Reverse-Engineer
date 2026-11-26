"""P1-2C candidate runs (reports/PHASE1_GATE2C_PLAN.md): C1 = rebased-futures series from minute 360 in post-auction cycles (feed only); C2 = C1 + late ladder gate of 5 minutes from minute 360. Pre-auction cycles untouched.
Usage: python bl_p1_2c_run.py C1 C2   ->  outputs/phase1/2C/<ID>/"""
import sys, os, json, time, hashlib, datetime, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
CAS = '2026-08-03'; VARIANTS = {'C0': (False, {}), 'C1': (True, {}), 'C2': (True, dict(ladder_late_gate_min=5, late_start_min=360))}
def _run(args):
    import validate_engine as V, bl_fr_sim as S, bl_common
    from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
    i, use_fut, ov = args; r = V.CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']; opd = {k: v for k, v in op.items() if isinstance(k, tuple)}
    if use_fut and r.d1 >= CAS:
        c = pd.read_pickle(f"{bl_common.OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz"); s = c['spot1']; n = len(s); assert n >= 375 and (s.close.values[:360] == o.close.values[:360]).all(), 'rebased series must equal the index series before minute 360'
        ob, oh, ol, oc = s.open.values, s.high.values, s.low.values, s.close.values; pad = n - 375; opd = {k: np.concatenate([v, np.repeat(v[:, -1:], pad, axis=1)], axis=1) if pad > 0 else v for k, v in opd.items()}
    else: ob, oh, ol, oc = o.open.values, o.high.values, o.low.values, o.close.values
    feed = ReplayFeed(ob, oh, ol, oc, d['K'], opd); cfg = config_for(r.und, r.d1, order_split='one_lot_v2', **ov); eng = D1Engine(cfg, feed, PaperBroker(feed)); run_replay(eng, feed); df = eng.orders_frame()
    if len(df): df['cls'] = df.role.map(V.ROLE2CLS); df['cid'] = i; df['cp'] = df.right; df['j'] = df.minute; df['step'] = cfg.strike_step
    return i, df, len(eng.rejected)
if __name__ == '__main__':
    import bl_common, bl_oscore as Q, bl_fr_sim as S, bl_score_d1_F as B, bl_p1_eval as E
    OUT = bl_common.OUT; CY = S.CY
    for vid in sys.argv[1:]:
        use_fut, ov = VARIANTS[vid]; OD = f'{OUT}/phase1/2C/{vid}'
        if os.path.exists(f'{OD}/run_record.json'): print(vid, 'exists; never overwritten'); continue
        os.makedirs(f'{OD}/all', exist_ok=True); t0 = time.time()
        with Pool(8) as p: res = p.map(_run, [(i, use_fut, ov) for i in range(len(CY))])
        ORD = {i: df for i, df, _ in res}; rej = int(sum(n for _, _, n in res)); sim = B.build_sim(ORD, CY); real = B.build_real(CY); attrs = B.build_attrs(CY); leg = Q.legacy_d1_scores(ORD, CY, S.REAL, bl_common.ref.STEP).set_index('cls').loc['ALL']
        R = Q.score(real, sim, attrs, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
        for k in ('tiers', 'strictness', 'by_class', 'by_block', 'per_cycle', 'state_after_matched', 'checkpoints', 'class_confusion'):
            if isinstance(R.get(k), pd.DataFrame): R[k].to_csv(f'{OD}/all/{k}.csv', index=False)
        R['_pairs'].to_csv(f'{OD}/all/pairs.csv', index=False); sim.to_csv(f'{OD}/sim_orders.csv', index=False); real.to_csv(f'{OD}/real_orders.csv', index=False)
        json.dump(dict(id=vid, feed_rebased_futures=use_fut, overrides=ov, order_split='one_lot_v2', mode='F', evidence_label='historical reproduction', engine_orders=int(len(sim)), rejected=rej, legacy_f1=float(leg.F1), seconds=round(time.time() - t0), run_at=datetime.datetime.now(datetime.timezone.utc).isoformat()), open(f'{OD}/run_record.json', 'w'), indent=1)
        post = [f'{r.und}|{r.expiry}' for r in CY.itertuples() if r.d1 >= CAS]; w = E.window_metrics(OD, 33300 + 360 * 60, post); m = E.body_metrics(OD)
        print(vid, '| orders', len(sim), 'rej', rej, 'legacy', round(float(leg.F1), 4), '| body F1', round(m['F1'], 4), 'strict', round(m['strict_F1'], 4), '| window real', w['real'], 'sim', w['sim'], 'rec', round(w['recall'], 3), 'prec', round(w['precision'], 3), 'F1', round(w['F1'], 4), flush=True)
