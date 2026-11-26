"""Gate 5c variant runner (plan reports/PHASE1_GATE5C_PLAN.md). Scores a D0 engine variant on the OOF 30 cycles and the forward sets with the corrected 5b convention (mode T, 'events'), plus window metrics, class F1, legacy lot-level F1 and per-cycle deltas.
Variants differ only by a config modifier applied per cycle; the real log is used for evaluation only."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d0_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_p1_5a_port as A, bl_p1_5b as B, bl_oscore as Q, bl_common
from d0_algo import D0Engine
OUT = bl_common.OUT; OD = f'{OUT}/phase1/5c'; SETS = {'OOF': ['OOF half 0 test', 'OOF half 1 test'], 'forwardA': ['forward A (same version, later cycles)'], 'forwardB': ['forward B (train V1, test V2)']}
def era(i): return 'after' if A.CY.iloc[i].expiry >= '2026-08-03' else 'before'
def mod_base(c, i): return c
def mod_clk(minute): 
    def f(c, i):
        if era(i) == 'before': c.clearance_minute = minute
        return c
    return f
def mod_open(c, i): c.opening_long_clock = True; c.enable_opening_wings = False; return c
def mod_fwd(c, i): c.cycle_stop_rupees = 1.25e5; return c                                   # P1-9 final: forward/production D0 configuration (clearance 359 everywhere, stop 1.25 lakh)
def mod_hr(c, i): c = mod_clk(363)(c, i); c.cycle_stop_rupees = 1.25e5; return c           # P1-9 final: historical-reproduction configuration (+ experimental in-sample era clearance 363 for pre-auction expiries)
MODS = {'legacy': None, 'fwd': mod_fwd, 'hr': mod_hr}
VARIANTS = {'V0': mod_base, 'X1': mod_clk(363), 'X1s364': mod_clk(364), 'X3': mod_open}
def run_set(PR, keys, mod):
    items = []; opens = {}
    for k in keys:
        P = PR[k]
        for i in P['test']:
            c = mod(A.config_of(P, i), i); c.risk_mode = 'enforce'; op = A.opening_of(i); e = D0Engine(c, A.market_of(i), op); e.run(); items.append((i, e)); opens[i] = op
    return items, opens
def win_f1(real, sim, pairs, cls, lo, hi):
    """class-specific window F1 on the 60 s keys pairs: window on the minute of the real/sim order (minute index from 09:15)"""
    pr, ps = Q.prepare_real(real), Q.prepare_sim(sim); rm = ((pr.t - 33300) // 60).astype(int); sm = ((ps.t - 33300) // 60).astype(int)
    rI = pr.index[(pr.cls == cls) & (rm >= lo) & (rm <= hi)]; sI = ps.index[(ps.cls == cls) & (sm >= lo) & (sm <= hi)]
    m = pairs[pairs.tier <= 60] if 'tier' in pairs else pairs; mr = m.ri.isin(rI).sum(); ms = m.si.isin(sI).sum()
    rec = mr / len(rI) if len(rI) else np.nan; pre = ms / len(sI) if len(sI) else np.nan; f1 = 2 * rec * pre / (rec + pre) if rec == rec and pre == pre and rec + pre > 0 else (0.0 if len(rI) and len(sI) else np.nan)
    return dict(real=int(len(rI)), sim=int(len(sI)), matched_real=int(mr), matched_sim=int(ms), recall=float(rec), precision=float(pre), F1=float(f1))
def evaluate(name, mod, PR, REF_ONLY=False):
    res = {}
    for sname, keys in SETS.items():
        items, opens = run_set(PR, keys, mod); cids = [i for i, _ in items]; real = B.real_frame(cids); attrs = B.attrs_of(cids, real); sim = B.sim_frame(items)
        R = Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=False, bootstrap=0); st = R['strictness']; f = lambda tol, lvl: float(st[(st.cumulative_tolerance_s == tol) & (st.level == lvl)].F1.iloc[0])
        pairs = R['_pairs']; bc = {r['cls']: r['F1'] for r in R['by_class'].to_dict('records')} if hasattr(R['by_class'], 'to_dict') else {}
        pc = R['per_cycle_F1']; D = dict(cycles=len(cids), real=int(len(real)), sim=int(len(sim)), keys_F1_60s=f(60, 'keys'), strict_F1_60s=f(60, 'lots_exact'), by_class=bc,
            win_clear_buyback_pre=None, win_clear_buyback_all=win_f1(real, sim, pairs, 'body_buyback', 359, 400), win_open_long=win_f1(real, sim, pairs, 'body_long', 0, 2), win_open_sell=win_f1(real, sim, pairs, 'body_sell', 0, 2), win_open_buyback=win_f1(real, sim, pairs, 'body_buyback', 0, 2))
        # per-cycle keys F1 and per-cycle window F1 (for K2/O2/C4)
        per = {}
        for cyc, rg in real.groupby('cyc'):
            rr = real[real.cyc == cyc].reset_index(drop=True); ss = sim[sim.cyc == cyc].reset_index(drop=True)
            if not len(ss): per[cyc] = dict(f1=0.0); continue
            Rc = Q.score(rr, ss, attrs[attrs.cyc == cyc].reset_index(drop=True), 'T', 'historical reproduction', shift_placebo=False, bootstrap=0); sc = Rc['strictness']; per[cyc] = dict(f1=float(sc[(sc.cumulative_tolerance_s == 60) & (sc.level == 'keys')].F1.iloc[0]), clear=win_f1(rr, ss, Rc['_pairs'], 'body_buyback', 359, 400), openl=win_f1(rr, ss, Rc['_pairs'], 'body_long', 0, 2))
        sim1 = B.sim_frame(items, one_lot=True); R1 = Q.score(real, sim1, attrs, 'T', 'historical reproduction', shift_placebo=False, bootstrap=0); p1 = R1['_pairs']; s1 = R1['strictness']
        D['one_lot'] = dict(keys_F1_60s=float(s1[(s1.cumulative_tolerance_s == 60) & (s1.level == 'keys')].F1.iloc[0]), win_clear_buyback_all=win_f1(real, sim1, p1, 'body_buyback', 359, 400), win_open_long=win_f1(real, sim1, p1, 'body_long', 0, 2))
        D['per_cycle'] = per; D['era'] = {f'{A.CY.iloc[i].und}|{A.CY.iloc[i].expiry}': era(i) for i in cids}
        if sname == 'OOF':
            ref = {}; ex = {}; 
            for i, e in items: ex[i] = e.events_frame()
            D['legacy_D0_OOF'] = Q.legacy_d0_scores(ex, sorted(ex), A.CY, A.O(), None)
        # post-auction orders (for K3 identity)
        D['sim_orders_hash'] = {cyc: int(pd.util.hash_pandas_object(sim[sim.cyc == cyc][['cp', 'side', 'strike', 'lots', 't', 'cls']].reset_index(drop=True)).sum()) for cyc in real.cyc.unique()}
        res[sname] = D
    return res
if __name__ == '__main__':
    os.makedirs(OD, exist_ok=True); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); names = sys.argv[1:] or ['V0']
    for n in names:
        r = evaluate(n, VARIANTS[n], PR); json.dump(r, open(f'{OD}/{n}.json', 'w'), indent=1, default=float)
        o = r['OOF']; print(n, 'OOF keys F1', round(o['keys_F1_60s'], 4), 'legacy', round(o['legacy_D0_OOF']['F1'], 4), 'clear-window bb', {k: round(v, 3) for k, v in o['win_clear_buyback_all'].items()}, 'open-long', {k: round(v, 3) for k, v in o['win_open_long'].items()}, '| one_lot: keys', round(o['one_lot']['keys_F1_60s'], 4), 'clear', {k: round(v, 3) for k, v in o['one_lot']['win_clear_buyback_all'].items()}, 'open-long', {k: round(v, 3) for k, v in o['one_lot']['win_open_long'].items()}, flush=True)
