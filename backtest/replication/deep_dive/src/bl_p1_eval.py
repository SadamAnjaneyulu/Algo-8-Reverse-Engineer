"""Phase 1 evaluator for body-sell candidates (plan reports/PHASE1_GATE2A_PLAN.md). Works on a saved scoring run directory (sim_orders.csv, real_orders.csv, all/pairs.csv, all/by_class.csv, all/state_after_matched.csv) and returns the preregistered metrics.
Pure functions over saved runs: no engine access, no P&L."""
import os, json, numpy as np, pandas as pd
def _f1(p, r): return 2 * p * r / (p + r) if (p + r) else 0.0
def body_metrics(run_dir, cycles=None):
    real = pd.read_csv(f'{run_dir}/real_orders.csv'); sim = pd.read_csv(f'{run_dir}/sim_orders.csv'); P = pd.read_csv(f'{run_dir}/all/pairs.csv')
    real['m'] = False; sim['m'] = False; real.loc[P.ri.values, 'm'] = True; sim.loc[P.si.values, 'm'] = True
    ok = (P.dstrike == 0) & (P.dlots == 0); real['strict'] = False; sim['strict'] = False; real.loc[P.ri[ok].values, 'strict'] = True; sim.loc[P.si[ok].values, 'strict'] = True
    tier = pd.Series(np.nan, index=real.index); tier.loc[P.ri.values] = P.tier.values; real['tier'] = tier
    rb = real[(real.cls == 'body_sell') & (real.side.str.lower() == 'sell')]; sb = sim[(sim.cls == 'body_sell') & (sim.side.str.lower() == 'sell')]
    if cycles is not None: rb = rb[rb.cyc.isin(cycles)]; sb = sb[sb.cyc.isin(cycles)]
    out = dict(real=int(len(rb)), sim=int(len(sb)), recall=float(rb.m.mean()), precision=float(sb.m.mean()), sim_lots=int(sb.lots.sum()), real_lots=int(rb.lots.sum()), extras=int((~sb.m).sum()), missing=int((~rb.m).sum()))
    out['F1'] = _f1(out['precision'], out['recall']); out['strict_recall'] = float(rb.strict.mean()); out['strict_precision'] = float(sb.strict.mean()); out['strict_F1'] = _f1(out['strict_precision'], out['strict_recall'])
    out['exact_second_share_of_real'] = float((rb.tier == 0).mean()); out['near_share_of_real'] = float((rb.tier == 1).mean())
    sch = sb[sb.role == 'scheduled_straddle']; out['scheduled_sim'] = int(len(sch)); out['scheduled_matched'] = int(sch.m.sum()); schr = pd.Series(sch.m.values)
    mm = P[P.si.isin(sch.index)]; out['scheduled_exact_second_share'] = float((mm.tier == 0).mean()) if len(mm) else None
    for role in ('ladder_solo', 'breakout_straddle', 'breakout_extra'): z = sb[sb.role == role]; out[f'{role}_orders'] = int(len(z)); out[f'{role}_matched'] = int(z.m.sum())
    return out
def class_f1(run_dir):
    c = pd.read_csv(f'{run_dir}/all/by_class.csv').set_index('cls'); return {k: float(c.loc[k, 'F1']) for k in c.index if c.loc[k, 'F1'] == c.loc[k, 'F1']}
def state_l1(run_dir):
    st = pd.read_csv(f'{run_dir}/all/state_after_matched.csv'); return float(st.l1_norm.median())
def per_cycle_body(run_dir):
    """per cycle: real/sim body sells, matched counts, F1 (harmonic mean of recall and precision), for leave-one-cycle-out selection and the per-cycle criterion"""
    real = pd.read_csv(f'{run_dir}/real_orders.csv'); sim = pd.read_csv(f'{run_dir}/sim_orders.csv'); P = pd.read_csv(f'{run_dir}/all/pairs.csv'); real['m'] = False; sim['m'] = False; real.loc[P.ri.values, 'm'] = True; sim.loc[P.si.values, 'm'] = True
    rb = real[(real.cls == 'body_sell') & (real.side.str.lower() == 'sell')]; sb = sim[(sim.cls == 'body_sell') & (sim.side.str.lower() == 'sell')]; rows = []
    for c in sorted(set(real.cyc)):
        r = rb[rb.cyc == c]; s = sb[sb.cyc == c]; rec = r.m.mean() if len(r) else 0; pre = s.m.mean() if len(s) else 0; rows.append(dict(cyc=c, real=len(r), sim=len(s), tp_real=int(r.m.sum()), tp_sim=int(s.m.sum()), F1=_f1(pre, rec)))
    return pd.DataFrame(rows)
def pooled_f1(pc):
    r = pc.tp_real.sum() / pc.real.sum(); p = pc.tp_sim.sum() / max(pc.sim.sum(), 1); return _f1(p, r)
if __name__ == '__main__':
    import sys; d = sys.argv[1]; print(json.dumps(body_metrics(d), indent=1)); print(class_f1(d), state_l1(d))

def window_metrics(run_dir, t_min, cycles):
    """body-sell metrics restricted to orders from second-of-day t_min on, in the given cycles (the late window of Gate 2C)"""
    real = pd.read_csv(f'{run_dir}/real_orders.csv'); sim = pd.read_csv(f'{run_dir}/sim_orders.csv'); P = pd.read_csv(f'{run_dir}/all/pairs.csv'); real['m'] = False; sim['m'] = False; real.loc[P.ri.values, 'm'] = True; sim.loc[P.si.values, 'm'] = True
    rb = real[(real.cls == 'body_sell') & (real.side.str.lower() == 'sell') & (real.t >= t_min) & real.cyc.isin(cycles)]; sb = sim[(sim.cls == 'body_sell') & (sim.side.str.lower() == 'sell') & (np.floor(sim.t) >= t_min) & sim.cyc.isin(cycles)]
    r = float(rb.m.mean()) if len(rb) else 0.0; p = float(sb.m.mean()) if len(sb) else 0.0
    per = {}
    for c in sorted(set(rb.cyc) | set(sb.cyc)):
        a = rb[rb.cyc == c]; b = sb[sb.cyc == c]; per[c] = _f1(float(b.m.mean()) if len(b) else 0.0, float(a.m.mean()) if len(a) else 0.0)
    return dict(real=int(len(rb)), sim=int(len(sb)), recall=r, precision=p, F1=_f1(p, r), per_cycle_F1=per)
