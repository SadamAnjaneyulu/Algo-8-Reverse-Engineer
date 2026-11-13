"""TP-03 Phase 1: per-underlying / per-day-type / per-cycle breakdown of the E6 wing-rule match and the E7 window ratio (descriptive companions to the registered tests; the rule logic is identical to p1_structure_tests.py)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec
tc.assert_frozen(); A = tc.ANALYSIS; CFG = tc.CFG; D = ec.Data(); STEP = ec.STEP
wg = pd.read_csv(os.path.join(A, 'p1_e6_wing_orders.csv'), parse_dates=['E', 'first_fill', 'date', 'expiry']); OFFS = np.arange(-3, 4)
def chain(r):
    t = r.E.floor('min') - pd.Timedelta(minutes=1); st = STEP[r.und]; return [D.opt_close(f'{r.und}|{r.expiry:%Y-%m-%d}|{r.cp}|{int(r.strike + j * st)}', t) for j in OFFS]
CH = np.array([chain(r) for r in wg.itertuples()]); dirn = np.where(wg.cp.values == 'CE', -1, 1)
def rule_eval(P_, budget):
    ok = np.isfinite(P_) & np.isfinite(budget)[:, None] & (P_ <= budget[:, None]); masked = np.where(ok, P_, -np.inf); jb = masked.argmax(1); has = np.isfinite(masked.max(1)) & ok.any(1)
    inward = jb + dirn; valid_in = (inward >= 0) & (inward <= 6); ii = np.clip(inward, 0, 6); pin = P_[np.arange(len(P_)), ii]; verified = has & valid_in & np.isfinite(pin) & (pin > budget)
    return verified & (jb == 3), verified & (np.abs(jb - 3) <= 1), verified
refs = {'algo_quote_from_limit': (wg.wing_quote_limit.values, wg.body_quote_limit.values), 'last_completed_bar_close': (CH[:, 3], wg.atm_leg_bar.values), 'fill_price': (wg.px.values, wg.body_fill_px.values)}
wg['cycle'] = wg.und + '|' + wg.expiry.dt.strftime('%Y-%m-%d'); rows = []; cyc_rows = []
for name, (own, atm) in refs.items():
    P_ = CH.copy(); P_[:, 3] = own; ex, wi, ck = rule_eval(P_, CFG['entry']['wing_budget_fraction'] * atm); wg['ex_' + name] = ex; wg['ck_' + name] = ck; wg['wi_' + name] = wi
    for keys, g in wg.groupby(['und', 'day_type']): rows.append(dict(reference=name, und=keys[0], day_type=keys[1], checkable=int(g['ck_' + name].sum()), exact=float(g['ex_' + name].sum() / max(g['ck_' + name].sum(), 1)), within_one=float(g['wi_' + name].sum() / max(g['ck_' + name].sum(), 1))))
    c = wg.groupby('cycle').apply(lambda g: g['ex_' + name].sum() / g['ck_' + name].sum() if g['ck_' + name].sum() >= 10 else np.nan, include_groups=False); cyc_rows.append(dict(reference=name, cycles_with_ge10_checkable=int(c.notna().sum()), share_cycles_exact_rate_above_chance_floor_20pct=float((c.dropna() > 0.20).mean()), median_cycle_exact_rate=float(c.median()), min_cycle_exact_rate=float(c.min())))
pd.DataFrame(rows).to_csv(os.path.join(A, 'p1_e6_breakdown.csv'), index=False); pd.DataFrame(cyc_rows).to_csv(os.path.join(A, 'p1_e6_cycle_consistency.csv'), index=False)
C1 = pd.read_csv(os.path.join(A, 'p1_e7_c1_windows.csv')); r = []
for (und, kind), g in C1.groupby(['und', 'kind']):
    x = np.round(g.ratio, 2); r.append(dict(und=und, kind=kind, n=len(g), share_ratio_exactly_1=float((x == 1).mean()), median=float(g.ratio.median()), share_ge_1=float((g.ratio >= 1).mean())))
pd.DataFrame(r).to_csv(os.path.join(A, 'p1_e7_c1_breakdown.csv'), index=False); cs = C1.groupby('cycle').apply(lambda g: (np.round(g.ratio, 2) == 1).mean(), include_groups=False); pd.DataFrame([dict(cycles=len(cs), share_cycles_with_majority_ratio_1=float((cs > 0.5).mean()))]).to_csv(os.path.join(A, 'p1_e7_cycle_consistency.csv'), index=False)
pd.set_option('display.width', 250); print(pd.DataFrame(rows).to_string()); print(pd.DataFrame(cyc_rows).to_string()); print(pd.DataFrame(r).to_string()); print(cs.describe())
