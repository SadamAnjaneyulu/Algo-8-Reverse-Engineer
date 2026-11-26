"""Gate 5d: full D0 validation report for D0-C (Gate 5a engine + candidate X1), mode T. Standards: reports/PHASE1_GATE5D_STANDARDS.md (fixed before this ran). Real orders are used for evaluation only."""
import sys, os, json, time, warnings, hashlib; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d0_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C, bl_oscore as Q, bl_common
from d0_algo import D0Engine
OUT = bl_common.OUT; CFG = os.environ.get('P1_CFG', 'legacy'); OD = f'{OUT}/phase1/5d' if CFG == 'legacy' else f'{OUT}/phase1/9/final_{CFG}'; SETS = C.SETS; MOD = C.mod_clk(363) if CFG == 'legacy' else C.MODS[CFG]
def run_items(PR, keys):
    items = []; opens = {}; risk = dict(runs=0, rejected=0, max_short_lots_per_right=0, max_sell_decisions_per_minute=0, violations=0, reconciled=0, deterministic=0, stopped=[], cleared=0, clearance_lots={}, stop_j={})
    for k in keys:
        P = PR[k]
        for i in P['test']:
            def mk():
                c = MOD(A.config_of(P, i), i); c.risk_mode = 'enforce'; op = A.opening_of(i); e = D0Engine(c, A.market_of(i), op); e.run(); return e, op
            e, op = mk(); e2, _ = mk(); items.append((i, e)); opens[i] = op; r = A.CY.iloc[i]; cyc = f'{r.und}|{r.expiry}'
            risk['runs'] += 1; risk['rejected'] += len(e.rejected); risk['violations'] += len(e.violations); risk['reconciled'] += int(e.reconcile(op)); risk['deterministic'] += int(e2.events_frame().equals(e.events_frame()))
            risk['max_sell_decisions_per_minute'] = max(risk['max_sell_decisions_per_minute'], max(e._decisions.values(), default=0)); risk['max_short_lots_per_right'] = max(risk['max_short_lots_per_right'], getattr(e, 'max_short_seen', 0))
            if e.stopped: risk['stopped'].append(cyc); risk['stop_j'][cyc] = int(min(ev.j for ev in e.events if ev.cls == 'stop'))
            risk['cleared'] += int(e.cleared)
            if e.cleared: risk['clearance_lots'][cyc] = int(sum(ev.lots for ev in e.events if ev.cls == 'body_buyback' and ev.j == e.cfg.clearance_minute))
    return items, opens, risk
if __name__ == '__main__':
    t0 = time.time(); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); os.makedirs(OD, exist_ok=True); summary = {}; RISK = {}
    for name, keys in SETS.items():
        items, opens, risk = run_items(PR, keys); RISK[name] = risk; cids = [i for i, _ in items]; real = B.real_frame(cids); attrs = B.attrs_of(cids, real)
        for conv in ('events', 'one_lot'):
            sim = B.sim_frame(items, one_lot=(conv == 'one_lot')); d = f'{OD}/{name}_{conv}'; os.makedirs(d, exist_ok=True)
            R = Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=True, bootstrap=1000)
            for k, v in R.items():
                if isinstance(v, pd.DataFrame) and not k.startswith('_'): v.to_csv(f'{d}/{k}.csv', index=False)
            for k, v in R['unmatched'].items():
                if isinstance(v, pd.DataFrame): v.to_csv(f'{d}/unmatched_{k}.csv', index=False)
            R['_pairs'].to_csv(f'{d}/pairs.csv', index=False); real.to_csv(f'{d}/real_orders.csv', index=False); sim.to_csv(f'{d}/sim_orders.csv', index=False); attrs.to_csv(f'{d}/attrs.csv', index=False)
            CS = B.carry_state(Q.prepare_real(real), Q.prepare_sim(sim), R['_pairs'], opens); CS.to_csv(f'{d}/carry_state.csv', index=False)
            st = R['strictness']; f = lambda tol, lvl: float(st[(st.cumulative_tolerance_s == tol) & (st.level == lvl)].F1.iloc[0])
            ex = {i: e.events_frame() for i, e in items}; leg = Q.legacy_d0_scores(ex, sorted(ex), A.CY, A.O(), None) if conv == 'events' else None
            summary[f'{name}_{conv}'] = dict(cycles=len(cids), real_orders=int(len(real)), sim_orders=int(len(sim)), keys_F1_0s=f(0, 'keys'), keys_F1_5s=f(5, 'keys'), keys_F1_60s=f(60, 'keys'), strict_F1_60s=f(60, 'lots_exact'), strike_exact_F1_60s=f(60, 'strike_exact'), carry_state_L1_median=float(CS.l1_norm.median()), placebo_keys_F1_60s=R['time_shift_placebo']['F1_keys_at_60s'], per_cycle_F1=R['per_cycle_F1'], ci=R['pooled_F1_ci95'], by_class=R['by_class'].to_dict('records') if hasattr(R['by_class'], 'to_dict') else None, legacy_lot_level=leg)
            json.dump({k: v for k, v in R.items() if k in ('run', 'ambiguity', 'timing', 'strike', 'quantity', 'type', 'by_class', 'by_block', 'per_cycle_F1', 'pooled_F1_ci95', 'tie_break_range', 'time_shift_placebo', 'by_attribute')}, open(f'{d}/report.json', 'w'), indent=1, default=lambda o: o.to_dict('records') if hasattr(o, 'to_dict') else float(o))
            print(name, conv, round(summary[f'{name}_{conv}']['keys_F1_60s'], 4), 'strict', round(summary[f'{name}_{conv}']['strict_F1_60s'], 4), flush=True)
    json.dump(summary, open(f'{OD}/summary.json', 'w'), indent=1, default=float); json.dump(RISK, open(f'{OD}/risk_determinism.json', 'w'), indent=1, default=float); print('seconds', round(time.time() - t0))
