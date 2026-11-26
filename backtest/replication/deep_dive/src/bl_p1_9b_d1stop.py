"""P1-9-BE-D1: D-1 engine cycle-stop candidate (plan reports/PHASE1_LOOP2_B_PLAN.md section 3). Compares candidate L=1.25 lakh with the B1 re-run through the same runner. Real s_ orders are mapped to class `stop` for BOTH runs here (B1's stored files are untouched)."""
import sys, os, json, time, warnings; os.environ['ORDER_SPLIT'] = 'one_lot_v2'
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..', '..', '../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S, bl_oscore as Q, bl_score_d1_F as F1M, validate_engine as V
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
OUT = bl_common.OUT; OD = f'{OUT}/phase1/9'; CY = S.CY; ROLE2CLS = dict(V.ROLE2CLS, cycle_stop_buyback='stop', cycle_stop_sell='stop')
def run1(args):
    i, L = args; r = CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']; feed = ReplayFeed(o.open.values, o.high.values, o.low.values, o.close.values, d['K'], {k: v for k, v in op.items() if isinstance(k, tuple)})
    cfg = config_for(r.und, r.d1, order_split='one_lot_v2', **({} if L is None else dict(cycle_stop_rupees=L))); eng = D1Engine(cfg, feed, PaperBroker(feed)); run_replay(eng, feed); df = eng.orders_frame()
    if len(df): df['cls'] = df.role.map(ROLE2CLS); df['cid'] = i; df['cp'] = df.right; df['j'] = df.minute; df['step'] = cfg.strike_step
    return i, df, len(eng.rejected), eng.stop_time, int(sum(len(v) for v in eng.book.shorts.values()))
def score(ORD):
    sim = F1M.build_sim(ORD, CY); real = F1M.build_real(CY); real.loc[real.module == 's_', 'cls'] = 'stop'; attrs = F1M.build_attrs(CY)
    R = Q.score(real, sim, attrs, 'F', 'historical reproduction', shift_placebo=True, bootstrap=0); st = R['strictness']; f = lambda l: float(st[(st.cumulative_tolerance_s == 60) & (st.level == l)].F1.iloc[0])
    pr, ps = Q.prepare_real(real), Q.prepare_sim(sim); m = R['_pairs']; m = m[m.tier <= 60]; sched = ps.index[ps.role == 'scheduled_straddle']
    leg = Q.legacy_d1_scores(ORD, CY, S.REAL, bl_common.ref.STEP).set_index('cls').loc['ALL']
    return R, dict(keys=f('keys'), strict=f('lots_exact'), legacy=float(leg.F1), sched_matched=int(m.si.isin(sched).sum()), sched_total=int(len(sched)), by_class={r['cls']: r['F1'] for r in R['by_class'].to_dict('records')}, per_cycle=dict(zip(R['per_cycle'].cyc, R['per_cycle'].F1)), placebo=R['time_shift_placebo']['F1_keys_at_60s'], sim=int(len(sim)), real=int(len(real)))
if __name__ == '__main__':
    t0 = time.time(); L = 1.25e5
    with Pool(4) as p: base = p.map(run1, [(i, None) for i in range(len(CY))]); cand = p.map(run1, [(i, L) for i in range(len(CY))])
    B0 = {i: df for i, df, *_ in base}; C0 = {i: df for i, df, *_ in cand}; stops = {i: st for i, _, _, st, _ in cand}; resid = {i: sh for i, _, _, _, sh in cand}
    Rb, mb = score(B0); Rc, mc = score(C0); res = dict(L=L, base=mb, cand=mc, stop_cycles={}, rejected_base=int(sum(x[2] for x in base)), rejected_cand=int(sum(x[2] for x in cand)))
    real = F1M.build_real(CY); real_stop = real[real.module == 's_'].groupby('cyc').t.min()
    same = 0; diff = []
    for i, st in stops.items():
        cyc = f'{CY.iloc[i].und}|{CY.iloc[i].expiry}'
        if st is None:
            a, b = B0[i], C0[i]; ok = (len(a) == len(b)) and (a.reset_index(drop=True)[['ts', 'right', 'strike', 'lots', 'side', 'role']].equals(b.reset_index(drop=True)[['ts', 'right', 'strike', 'lots', 'side', 'role']]) if len(a) else True); same += int(ok)
            if not ok: diff.append(cyc)
        else:
            a, b = B0[i], C0[i]; rs = real[(real.cyc == cyc)]; rstop = real_stop.get(cyc, None)
            res['stop_cycles'][cyc] = dict(stop_minute=int((st - 33300) // 60), stop_second=float(st), real_stop_minute=None if rstop is None else int((rstop - 33300) // 60), baseline_orders_after_stop=int((a.ts > st).sum()), baseline_lots_after_stop=int(a[a.ts > st].lots.sum()), stop_orders=int(C0[i].role.str.startswith('cycle_stop').sum()), stop_lots=int(C0[i][C0[i].role.str.startswith('cycle_stop')].lots.sum()), real_orders_after_real_stop=(None if rstop is None else int((rs.t > rstop).sum())), residual_short_lots=resid[i], baseline_late_orders_1515=int(((a.ts >= 33300 + 360 * 60) & (a.ts > st)).sum()), real_late_orders_1515=int((rs.t >= 33300 + 360 * 60).sum()))
    res['cycles_without_stop_identical_to_B1']=dict(identical=same, total=sum(1 for s in stops.values() if s is None), different=diff)
    es = {c for c in res['stop_cycles']}; res['engine_stop_cycles'] = sorted(es); res['real_stop_cycles'] = sorted(real_stop.index)
    json.dump(res, open(f'{OD}/BE_D1_result.json', 'w'), indent=1, default=float); pd.to_pickle(dict(base=B0, cand=C0), f'{OD}/BE_D1_orders.pkl.gz')
    print('seconds', round(time.time() - t0)); print('B1 rerun', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in mb.items() if k not in ('by_class', 'per_cycle')}); print('cand   ', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in mc.items() if k not in ('by_class', 'per_cycle')})
    print('stops', json.dumps(res['stop_cycles'], indent=1, default=float)); print('identical', res['cycles_without_stop_identical_to_B1']); print('class dF1', {c: round(mc['by_class'].get(c, np.nan) - v, 4) for c, v in mb['by_class'].items()})
