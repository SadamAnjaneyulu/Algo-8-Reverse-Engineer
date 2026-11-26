"""Builds reports/POSTCAS_REBUILD_RESULT.md (plan reports/POSTCAS_REBUILD_PLAN.md) from outputs/postcas/* and outputs/prepaper{,_v2}/*."""
import os, json, numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RP = os.path.join(os.path.dirname(OUT), 'reports'); PC = f'{OUT}/postcas'
def _md(d):
    f = lambda v: ('' if pd.isna(v) else (f'{v:,.0f}' if isinstance(v, (float, np.floating)) and abs(v) >= 100 else (f'{v:.2f}' if isinstance(v, (float, np.floating)) else str(v))))
    return '| ' + ' | '.join(map(str, d.columns)) + ' |\n|' + '---|' * len(d.columns) + '\n' + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
D = pd.read_csv(f'{PC}/diag_cycles.csv'); E = pd.read_csv(f'{PC}/eval.csv'); dec = json.load(open(f'{PC}/eval_decision.json')); ev = pd.read_csv(f'{PC}/eval_cycles.csv')
g1 = pd.read_csv(f'{OUT}/prepaper/gates.csv'); g2 = pd.read_csv(f'{OUT}/prepaper_v2/gates.csv'); s1 = json.load(open(f'{OUT}/prepaper/pp_summary.json')); s2 = json.load(open(f'{OUT}/prepaper_v2/pp_summary.json'))
e1 = pd.read_csv(f'{OUT}/prepaper/eras.csv'); e2 = pd.read_csv(f'{OUT}/prepaper_v2/eras.csv')
dg = D.groupby(['era', 'src'])[['d1', 'd0', 'total', 'd1_sold', 'd0_sold']].mean().reset_index().rename(columns={'d1': 'D-1 P&L', 'd0': 'D0 P&L', 'total': 'total', 'd1_sold': 'D-1 lots sold', 'd0_sold': 'D0 lots sold'})
Et = E.rename(columns={'real_mean': 'real mean (₹)', 'sim_mean': 'simulator mean (₹)', 'mae': 'mean abs. error (₹)', 'sim_only_stops': 'simulator-only stops', 'real_only_stops': 'real-only stops', 'stops_agree': 'stops agree'})
G = g1[['gate', 'passed']].merge(g2[['gate', 'passed', 'value']], on='gate', suffixes=(' original', ' rebuilt')); G['passed original'] = G['passed original'].map({True: 'PASS', False: 'FAIL'}); G['passed rebuilt'] = G['passed rebuilt'].map({True: 'PASS', False: 'FAIL'}); G = G.rename(columns={'value': 'rebuilt value'})
ER = e1[['era', 'cycles', 'mean_net']].merge(e2[['era', 'mean_net']], on='era', suffixes=(' original (₹)', ' rebuilt (₹)'))
val = ev[ev.group == 'validation']
md = f"""# Post-auction rebuild — result

*Plan: `POSTCAS_REBUILD_PLAN.md` (committed before the simulator was changed). Exploratory; real-log cycles split into development (D0 3 Aug – 15 Sep 2026) and validation (D0 16 Sep – 22 Oct 2026).*

## Verdict
* **The rebuild failed its pre-registered validation** (mean absolute error per cycle on validation ₹{dec['val_mae_old']:,.0f} → ₹{dec['val_mae_new']:,.0f}, stop agreement {dec['val_agree_old']} → {dec['val_agree_new']} of {len(val)}). By the plan's rule the original simulator is kept for the verdict.
* **The battery re-run on the rebuilt simulator gives the same result: NO-GO, {int(g2.passed.sum())} of 8 gates** (G4, G5, G8 fail in both). The post-auction era stays negative in the simulator (₹{e1.iloc[-1].mean_net:,.0f} → ₹{e2.iloc[-1].mean_net:,.0f} per cycle).
* **What is actually wrong:** not a post-auction mechanism but the expiry-day reconstruction itself. Cycle by cycle the simulator's D0 trading departs from the real one, most in the newest timetable versions (B/V2 from 16 Sep 2026). Fixing that needs more real post-auction cycles than exist (the real log ends on 22 Oct 2026); any further change would have to be tuned on the same 11 validation cycles.

## 1. Diagnosis (real vs simulator, means per cycle)
{_md(dg)}

* After the auction the gap is mainly on expiry day; volumes are similar, management differs.
* The simulator's cycle stop fired in 12 of 23 post-auction cycles vs 9 in the real log, and stopped 5 cycles the real system never stopped. Real stop triggers sit at −₹1.36 to −₹1.47 lakh; the simulator used a fitted ₹1.2 lakh.
* Real behaviour not modelled (cache ends 15:29): the overnight lump is bought after 15:30 since the auction (median minute 375 vs 358 before); final clearance on D0 runs a few minutes past 15:14; derivatives trade until 15:40.

## 2. The change tested (R1) and its validation
R1: cycle stop = median real trigger of the non-opening stops in the development period (−₹1.533, −₹1.394, −₹1.448 lakh) → **₹1.45 lakh** (was ₹1.2 lakh). No other change.

{_md(Et)}

* Accept rule: validation error falls **and** stop agreement does not fall **and** pre-auction error rises ≤ 10% → **not met** (validation error rose; agreement unchanged; 4 simulator-only stops remain because the simulator's book loses more than the real one in those cycles, not because of the threshold).
* Validation cycles show the real reason: e.g. 1 Oct 2026 — real D0 sold 679 lots and made ₹2.93 lakh, the simulator stopped at 09:16 after 82 lots; 13 Oct — real sold 309 lots and stopped, the simulator sold 1,080 and did not.

## 3. Battery: original vs rebuilt simulator (gates unchanged)
{_md(G)}

* Headline: mean net ₹{s1['base']:,.0f} → ₹{s2['base']:,.0f} per cycle; OOS ₹{s1['oos']:,.0f} → ₹{s2['oos']:,.0f}; break-even {s1['breakeven_mult']:.2f}× → {s2['breakeven_mult']:.2f}×; PBO {s1['PBO']:.2f} → {s2['PBO']:.2f}; random-timetable null: real above {100 * s1['null_pct']:.0f}% → {100 * s2['null_pct']:.0f}% of runs.

By era (simulator mean net per cycle):
{_md(ER)}

## 4. What this means for paper trading
* The verdict stays **NO-GO**. The reconstruction is not reliable enough in the current regime to stand in for Algo 8 on paper.
* A legitimate path: **paper-trade by shadowing, not by simulating** — log the real system's decisions (or a broker-side copy) forward from now, and use the simulator only as a reference; or collect more real post-auction cycles (≥ 30) before any further rebuild, split in time, with the rebuild frozen before the validation cycles are looked at.
* Nothing here changes the alpha findings (`FINAL_ALPHA.md`); it limits what the simulator can be trusted for.
"""
open(f'{RP}/POSTCAS_REBUILD_RESULT.md', 'w').write(md); print('ok')
