"""Builds reports/BODY_REACTIVE_BOOK.md from computed outputs (bl_bk_*, bl_pc_*, bl_summary_bk1-3, pc1-4)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); K1, K3, P1, P2, P3, P4 = J('bk1'), J('bk3'), J('pc1'), J('pc2'), J('pc3'), J('pc4')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
UN = pd.read_csv(f'{OUT}/bl_bk_uni.csv'); BK = pd.read_csv(f'{OUT}/bl_bk_blocks.csv'); PU = pd.read_csv(f'{OUT}/bl_bk_pace_uni.csv'); PCV = pd.read_csv(f'{OUT}/bl_pc_cv.csv'); BO = pd.read_csv(f'{OUT}/bl_pc_boot.csv'); AG = pd.read_csv(f'{OUT}/bl_pc_age.csv'); SP = pd.read_csv(f'{OUT}/bl_pc_splits.csv'); CR = pd.read_csv(f'{OUT}/bl_pc_cross.csv'); RG = pd.read_csv(f'{OUT}/bl_pc_reg.csv'); FL = pd.read_csv(f'{OUT}/bl_bk_flow.csv'); DEC = pd.read_csv(f'{OUT}/bl_bk_decile.csv')
names = {'delta_vs_move': 'book net delta signed against the move', 'delta_vs_move_norm': 'same, per open short lot', 'delta': 'book net delta (signed)', 'delta_ce': 'delta of the call side', 'delta_pe': 'delta of the put side', 'gamma': 'book gamma', 'short_lots': 'open short lots', 'itm_short': 'in-the-money short lots', 'net_lots': 'net lots (long − short)', 'dist_out_move': 'distance of spot to the outermost short strike on the move side (steps)', 'dist_out_opp': 'same, opposite side', 'dist_in_move': 'distance to the nearest short strike, move side', 'dist_in_opp': 'same, opposite side', 'pnl_pct': 'mark-to-market P&L (% of ₹2 crore)', 'pnl_chg5': 'P&L change, 5 min', 'pnl_chg15': 'P&L change, 15 min', 'pnl_chg30': 'P&L change, 30 min', 'delta_chg5': 'book delta change, 5 min', 'delta_chg15': 'book delta change, 15 min', 'delta_chg30': 'book delta change, 30 min', 'sig': 'implied σ√T (ATM straddle)', 'sig_chg5': 'σ√T change, 5 min', 'sig_chg15': 'σ√T change, 15 min', 'sig_chg30': 'σ√T change, 30 min', 'prem_tgt': 'premium of the target pair', 'prem_ratio_atm': 'target pair premium / ATM straddle', 'prem_pos60': 'target pair premium: position in its own 60-min range', 'prem_chg15': 'target pair premium change, 15 min', 'pair_delta_1lot': 'delta one pair would add'}
u = UN[UN.form == 'value'].copy(); u['edge'] = (u.AUC_within_edge - .5).abs(); u = u.sort_values('edge', ascending=False).head(10); u['variable'] = u.variable.map(names).fillna(u.variable); u = u[['variable', 'AUC_all', 'AUC_within_edge', 'AUC_even', 'AUC_odd']].round(3); u.columns = ['state variable', 'AUC vs random seconds (all)', 'AUC within the range-edge seconds', 'even cycles (all)', 'odd cycles (all)']
la = BK[BK.population.str.startswith('LOOK-AHEAD')]; base = la[(la.features == 'edge only')].set_index('model').AUC
t = pd.DataFrame({'block added to the edge features': [f for f in la[la.model == 'lr'].features if f != 'edge only'], 'logistic gain (95% CI)': [f'{g:+.3f} ({lo:+.3f} … {hi:+.3f})' for g, lo, hi in zip(la[(la.model == 'lr') & (la.features != 'edge only')].gain, la[(la.model == 'lr') & (la.features != 'edge only')].gain_lo, la[(la.model == 'lr') & (la.features != 'edge only')].gain_hi)], 'boosting gain (95% CI)': [f'{g:+.3f} ({lo:+.3f} … {hi:+.3f})' for g, lo, hi in zip(la[(la.model == 'gb') & (la.features != 'edge only')].gain, la[(la.model == 'gb') & (la.features != 'edge only')].gain_lo, la[(la.model == 'gb') & (la.features != 'edge only')].gain_hi)], 'logistic AUC': la[(la.model == 'lr') & (la.features != 'edge only')].AUC.round(3).values})
pu = PU[(PU.population == 'LOOK-AHEAD breakout minutes')].copy(); pu = pu[pu.variable.isin(['def_react', 'def_tot', 'def_sched', 'n_react', 'age_react', 'delta_vs_move', 'itm_short', 'pnl_pct', 'prem_pos60'])]; pu['variable'] = pu.variable.map({'def_react': 'pace deficit, reactive pairs', 'def_tot': 'pace deficit, all pairs', 'def_sched': 'pace deficit, scheduled pairs', 'n_react': 'reactive pairs so far', 'age_react': 'minutes since the last reactive pair', 'delta_vs_move': 'book delta against the move', 'itm_short': 'in-the-money short lots', 'pnl_pct': 'P&L', 'prem_pos60': 'premium position in its range'}); pu = pu[['variable', 'AUC', 'AUC_even', 'AUC_odd']].round(3); pu.columns = ['variable (look-ahead breakout minutes)', 'AUC', 'even cycles', 'odd cycles']
pv = PCV.copy(); pv['machine'] = pv.family.map({'M10': 'M10 range edge AND behind a pace of one reactive entry per D min', 'M11': 'M11 range edge AND behind a pace for ALL pairs', 'M12': 'M12 range edge AND behind the other cycles\' mean reactive curve', 'M13': 'M13 range edge AND behind the other cycles\' mean curve of all pairs'}); pv['information'] = pv['info'].map({'bar': 'completed bars', 'intra': 'current-minute close'})
for k in ('precision_tol1', 'recall_tol1', 'F1_tol1', 'F1_tol0', 'null_p99', 'fires_per_cycle', 'count_var_over_mean'): pv[k] = pv[k].round(3)
pv = pv[['machine', 'information', 'chosen', 'precision_tol1', 'recall_tol1', 'F1_tol1', 'F1_tol0', 'null_p99', 'fires_per_cycle', 'count_var_over_mean']]; pv.columns = ['machine', 'information', 'parameters chosen (N, D, θ) fold 1 / fold 2', 'precision (±1 min)', 'recall (±1 min)', 'F1 (±1 min)', 'F1 same minute', 'null F1 99th pct', 'fires per cycle', 'fires variance/mean']
bo = BO.copy(); bo['difference in F1 (95% CI)'] = [f'{d:+.3f} ({a:+.3f} … {b:+.3f})' for d, a, b in zip(bo['diff'], bo.lo, bo.hi)]; bo['F1 pace'] = bo.F1_a.round(3); bo['F1 refractory'] = bo.F1_b.round(3); bo['cycles where pace is better'] = bo.share_of_cycles_a_better.map(lambda v: pct(v)); bo = bo[['comparison', 'F1 pace', 'F1 refractory', 'difference in F1 (95% CI)', 'cycles where pace is better']]
ag = AG.copy(); ag['gain over "time since last pair" (95% CI)'] = [f'{g:+.3f} ({a:+.3f} … {b:+.3f})' for g, a, b in zip(ag.gain_vs_age_only, ag.lo, ag.hi)]; ag['AUC'] = ag.AUC.round(3); ag = ag[['model', 'AUC', 'gain over "time since last pair" (95% CI)']]
cr = CR.copy(); cr['precision'] = cr.precision.round(3); cr['recall'] = cr.recall.round(3); cr['F1'] = cr.F1.round(3); cr.columns = ['fit on', 'scored on (frozen)', 'parameters (N, D, θ)', 'precision', 'recall', 'F1']
rg = RG.copy(); rg['KS distance observed'] = rg.KS_observed.round(3); rg['random placement mean (5th pct)'] = [f'{a:.3f} ({b:.3f})' for a, b in zip(rg.KS_random_mean, rg.KS_random_p05)]; rg['p (more regular than random)'] = rg.p_value_regular.round(3); rg = rg[['group', 'cycles', 'KS distance observed', 'random placement mean (5th pct)', 'p (more regular than random)']]
fl = FL[FL.window == 'after: 30 s'].sort_values('lift', ascending=False).head(4)[['order_kind', 'share_of_pairs', 'share_of_control_seconds', 'lift']].copy(); fl['share_of_pairs'] = fl.share_of_pairs.map(lambda v: pct(v, 1)); fl['share_of_control_seconds'] = fl.share_of_control_seconds.map(lambda v: pct(v, 1)); fl['lift'] = fl.lift.round(1); fl.columns = ['order within 3–30 s AFTER the pair', 'share of reactive pairs', 'share of random seconds', 'lift']
fb = FL[FL.window == 'before: 30 s'].sort_values('lift', ascending=False).head(5)[['order_kind', 'share_of_pairs', 'share_of_control_seconds', 'lift']].copy(); fb['share_of_pairs'] = fb.share_of_pairs.map(lambda v: pct(v, 1)); fb['share_of_control_seconds'] = fb.share_of_control_seconds.map(lambda v: pct(v, 1)); fb['lift'] = fb.lift.round(1); fb.columns = ['order within 3–30 s BEFORE the pair', 'share of reactive pairs', 'share of random seconds', 'lift']
m10 = PCV[(PCV.family == 'M10') & (PCV['info'] == 'bar')].iloc[0]; m10i = PCV[(PCV.family == 'M10') & (PCV['info'] == 'intra')].iloc[0]; sp = P1['splits']; ag_all = AG.set_index('model'); fires = P2['fires_per_cycle']; dec_d = DEC[DEC.variable == 'delta_vs_move']
txt = f"""# Algo 8 — reactive pairs: is it linked to the state of the book? (and what *is* the second variable)

*Investigation only. In-sample (D-1 of 32 live cycles; 363 reactive pairs vs 10,890 random seconds, and 9,152 cycle-minutes). Plan written before the tests: `BODY_REACTIVE_BOOK_PLAN.md`; the **pace** variables, the pace machines and the regularity/age comparisons were added after the first results and are labelled post-hoc. Figures: `figures/bl_pc_example_NIFTY.png`, `figures/bl_pc_example_SENSEX.png`. This report **supersedes the "cooldown" description of `BODY_REACTIVE_TRACKER.md`**: a fixed silence period has no economic meaning and is replaced below by variables a practitioner would recognise. Nothing here shows what Algo 8's code does.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Is the reactive pair a delta hedge / re-centring of the book?** | **No.** One pair adds ≈ **{K1['mean_pair_delta_lots']:.2f} lot** of delta (always in the direction of the move); the book's net delta is typically ±{K1['abs_delta_events_median']:.1f} lots and drifts to −15 / −22 lots in the example cycles **without any reset at the pairs**. Pairs are placed with the book exposed against the move {pct(K1['share_book_exposed_against_move_before'])} of the time vs {pct(K1['share_book_exposed_against_move_controls_edge'])} for random seconds at the range edge; within the edge the book-delta variable separates pairs from non-pairs at AUC 0.58. | Observed |
| **Premium richness / vol spike, P&L, margin, distance to the book's strikes, other greeks?** | **None of them gates the pair.** Within the range-edge seconds every such variable has AUC between 0.43 and 0.58 (table in §1); adding all of them to the edge model changes the AUC by {BK[(BK.population.str.startswith('LOOK-AHEAD')) & (BK.features.str.startswith('edge + book + premium')) & (BK.model == 'gb')].gain.iloc[0]:+.3f} (boosting) / {BK[(BK.population.str.startswith('LOOK-AHEAD')) & (BK.features.str.startswith('edge + book + premium')) & (BK.model == 'lr')].gain.iloc[0]:+.3f} (logistic), CIs include 0. | Observed |
| **What does show up outside price?** | **How many pairs have already been done relative to the clock — a pace.** A cycle that is *behind* the usual cumulative number of pairs fires at the range edge far more often: within the edge, AUC **{PU[(PU.population == 'LOOK-AHEAD breakout minutes') & (PU.variable == 'def_tot')].AUC.iloc[0]:.2f}** (minutes) / {P2['def_tot_auc_within_edge'][0]:.2f} (seconds) for the all-pairs deficit, against {P2['def_short_auc_within_edge'][0]:.2f} for a deficit in *open short lots* (so it is a count of entries, not exposure or margin). Hazard is {DEC[(DEC.variable == 'delta_vs_move')].events_per_control_second.min():.2f}–{DEC[(DEC.variable == 'delta_vs_move')].events_per_control_second.max():.2f} across book-delta bins but rises from {P2['pace_quintiles'][0]['events_per_control_second']:.2f} to {P2['pace_quintiles'][-1]['events_per_control_second']:.2f} events per control second from the most-ahead to the most-behind pace quintile (§2). | Observed (predictive; post-hoc) |
| **A machine with no timer?** | **Range edge AND behind a pace of one reactive entry per ~30 minutes from 10:30** reproduces the pair times better than the refractory machine: out-of-fold precision {pct(m10.precision_tol1)}, recall {pct(m10.recall_tol1)}, **F1 {m10.F1_tol1:.2f}** (±1 min; null 99th pct {m10.null_p99:.2f}); with the current-minute close **same-minute F1 {m10i.F1_tol0:.2f}** (was 0.14 / 0.33). Random half-splits {sp['F1_mean']:.2f} ({sp['F1_q'][0]:.2f}–{sp['F1_q'][1]:.2f}); fitted on one underlying/schedule version and frozen on the other {CR.F1.min():.2f}–{CR.F1.max():.2f}. F1 is {BO['diff'].iloc[0]:+.3f} above the refractory machine (95% CI {BO.lo.iloc[0]:+.3f} … {BO.hi.iloc[0]:+.3f}). | Observed (description); mechanism **Inferred** |
| **Is it proved to be a pace/schedule?** | **No.** Pace adds only +{ag_all.loc['time since last pair + pace deficit (all pairs)', 'gain_vs_age_only']:.3f} AUC over "time since the last pair" inside the edge (CI {ag_all.loc['time since last pair + pace deficit (all pairs)', 'lo']:+.3f} … {ag_all.loc['time since last pair + pace deficit (all pairs)', 'hi']:+.3f}); the cumulative count follows a straight pace only marginally (fires p = {RG.p_value_regular.iloc[1]:.2f}, pairs not more regular than random); there is **no catch-up signature** (gap after a long gap is not shorter: {P2['next_gap_after_long_gap_median']:.0f} vs {P2['next_gap_after_short_gap_median']:.0f} min). Pace and "time since the last pair" are close relatives in this data. | Observed; mechanism **Unresolved** |
| **What else was found?** | The **hedge module reacts to the pair, not the other way round**: {pct(FL[(FL.window == 'after: 30 s') & (FL.order_kind == 'h_ | open_long | PE')].share_of_pairs.iloc[0], 1)} of reactive pairs are followed within 30 s by a long-wing purchase (random seconds {pct(FL[(FL.window == 'after: 30 s') & (FL.order_kind == 'h_ | open_long | PE')].share_of_control_seconds.iloc[0], 1)}). The earlier "clustering with other orders" is mostly this consequence plus pairs placed together. | Observed |

## 1. Book-state variables (plan tests A, B)
Book = all orders of every module on D-1 up to the second (flat at the open); Greeks from σ√T of the ATM straddle (no smile); P&L in % of ₹ 2 crore. 29 variables × 2 forms. Top ten by strength **within the range-edge seconds** ({int(UN.events_edge.iloc[0])} pairs / {int(UN.n_edge.iloc[0])} seconds):

{table(u)}
* **Delta re-centring is ruled out on size and on timing.** A pair adds ≈ {K1['mean_pair_delta_lots']:.2f} lot vs a book of |delta| ≈ {K1['abs_delta_events_median']:.1f} lots (median); after the pair the median |delta| is {K1['abs_delta_after_events_median']:.1f}. {pct(K1['share_pair_reduces_abs_delta'])} of pairs reduce |delta| only because about half the time the book happens to be on the right side; the pair direction itself is always the move direction (100%). Book delta by quintile (within the edge) is flat or non-monotonic: events per control second {', '.join(f'{v:.2f}' for v in dec_d.events_per_control_second)}.
* **Breach of the book's outer strikes, premium/vol jumps, P&L and in-the-money lots** do not gate the pair either (non-monotonic bins, AUC ≤ 0.58 within the edge). In-the-money short lots rise then fall (0.21 → 0.46 → 0.28): an artefact of time of day, not a trigger.
* Block models (look-ahead breakout minutes, leave-one-cycle-out; edge-only AUC logistic {base['lr']:.3f}, boosting {base['gb']:.3f}):

{table(t)}
## 2. The variable that does show up: pace (post-hoc)
Pace deficit = (mean cumulative number of pairs of the **other** 31 cycles at this time) − (this cycle's cumulative pairs). Inside the range-edge minutes:

{table(pu)}
* **A count of entries, not exposure:** the deficit in *open short lots* or ₹ notional scores {P2['def_short_auc_within_edge'][0]:.2f} within the edge ({P2['def_short_auc_within_edge'][1]:.2f} / {P2['def_short_auc_within_edge'][2]:.2f} in the two cycle halves) whereas the deficit in pairs placed scores {P2['def_react_auc_within_edge'][0]:.2f}–{P2['def_tot_auc_within_edge'][0]:.2f}, so buy-backs and stops (which change open lots) are not what the tracker watches.
* **Pace vs time since the last pair** (inside the range-edge seconds, leave-one-cycle-out logistic):

{table(ag)}
  Pace is at best a modest improvement over the time-since-last-pair clock: they describe nearly the same thing. I cannot separate "paced entries" from "silence after an entry" with this data.
* **Regularity test** (distance of each cycle's cumulative count from a straight line 10:30–15:15, vs the same number of events at random times):

{table(rg)}
  Fires are slightly more regular than random (p = {RG.p_value_regular.iloc[1]:.2f}); pairs (which include 2–3 pair-lots placed in the same second) are not. So the pace is a weak regularity, not a rigid schedule.
* **No catch-up:** consecutive fire gaps are uncorrelated beyond what shuffling gives (ρ = {P2['gap_autocorr']['rho']:+.2f}, shuffled mean {P2['gap_autocorr']['null_mean']:+.2f}); after a gap longer than 50 minutes the next gap is not shorter.

## 3. Forward-simulated pace machines (no timer, parameters chosen out-of-fold)
{table(pv)}
* **M10 is the best machine so far:** F1 {m10.F1_tol1:.2f} ({m10i.F1_tol1:.2f} with the current-minute close); chosen parameters are stable (N = 70–90, D = 30 minutes, θ = 1 pair). {m10.fires_per_cycle:.1f} fires per cycle ≈ 285 min / 30 = 9.5 and ≈ the real {fires['mean']:.1f} fires per cycle (clusters within 5 s) — but the machine is **too regular** (count variance/mean {m10.count_var_over_mean:.2f} vs {fires['var_over_mean']:.2f} real).
* Against the refractory machine of the previous report:

{table(bo)}
* Frozen cross-validation of M10 (fit on one group, score on the other):

{table(cr)}
* The same pace for **all** pairs (M11) fits poorly (F1 0.38–0.39): the reactive stream has its **own** pace, separate from the scheduled timetable. A nonparametric target (the other cycles' mean curve, no timer parameter at all, M13) reaches F1 0.52.

## 4. What the example plots show
Same two cycles as the tracker report (NIFTY 2026-09-08, SENSEX 2026-10-22; chosen by a rule fixed in advance).

![NIFTY](figures/bl_pc_example_NIFTY.png)

![SENSEX](figures/bl_pc_example_SENSEX.png)

* Row 2: the cumulative reactive pairs stay close to the "one per 30 minutes from 10:30" line; pace-tracker fires (crosses) fall at or just before real pairs in most cases. The three pairs at 15:09 push the count above the line (several pair-lots at one second).
* Row 3: the "armed" periods (behind pace) are where the pairs occur once the price touches the edge; the long stretches at the edge while **ahead** of pace have no pair.
* Row 4: **the book's net delta drifts steadily to −15 (NIFTY) and −22 lots (SENSEX) and is never reset at a reactive pair** — the pair is not managing delta.

## 5. Order flow around the pairs (H5)
{table(fl)}
{table(fb)}
* The hedge module buys a long wing on **both legs within seconds after** nearly every reactive pair: hedge follows the pair (a pointer for the hedge-module study), it is not a trigger.
* Before a pair, other body sells (another pair placed in the previous 30 s), buy-backs and wing closes are over-represented (lift 5–7): pairs come in bursts and sometimes right after a close; this explains part of the earlier "clustering with other orders" but is a minority of pairs (5–22%).
* Time to or since the nearest scheduled wave has no effect (AUC 0.50 within the edge).

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| The reactive pair is not a delta re-centring (size 0.21 lot vs |delta| ≈ {K1['abs_delta_events_median']:.0f}; book delta never reset) | **Observed** | §1, §4 |
| Premium richness, vol spike, P&L, margin proxy, breach of book strikes do not gate the pair | **Observed** | within-edge AUC 0.43–0.58, block gains include 0 |
| A count-of-entries pace deficit separates pairs from non-pairs at the range edge (AUC 0.71–0.73) | **Observed (predictive, post-hoc)** | §2 |
| Range edge AND behind a ~30-min pace reproduces the pair times (F1 {m10.F1_tol1:.2f}; {m10i.F1_tol0:.2f} same-minute with current close) | **Observed (description)** | §3 |
| Pace beats the refractory machine | **Observed** | F1 {BO['diff'].iloc[0]:+.3f} (CI {BO.lo.iloc[0]:+.3f} … {BO.hi.iloc[0]:+.3f}) |
| The system follows a fixed entry schedule | **Not established** | regularity weak (fires p = {RG.p_value_regular.iloc[1]:.2f}), no catch-up, pace ≈ age |
| Hedge wings follow every reactive pair | **Observed** | {pct(FL[(FL.window == 'after: 30 s') & (FL.order_kind == 'h_ | open_long | PE')].share_of_pairs.iloc[0], 1)} within 30 s |
| What fires the remaining pairs | **Unresolved** | best out-of-fold F1 ≈ 0.56 |

## 7. Limits and how this could be wrong
* **Greeks are approximate:** one σ√T from the ATM straddle for all strikes (no smile), lot unit per cycle, wings valued at the last price; the delta-size argument is robust (0.2 vs ≈ 7 lots) but the book delta level is not exact.
* **The pace target is the other cycles' mean (or a 30-minute line):** the true schedule, if any, is unknown; D = 30 hit the upper edge of the grid in no fold (grid 8–40).
* **Post-hoc:** the pace variables and machines were added after seeing that no book variable worked; leave-one-cycle-out, random splits and cross-instrument checks reduce but do not remove the selection risk ({P1['n_configs']} pace configurations; ≈ 3,250 configurations across the whole tracker line of studies).
* **Look-ahead variant** uses the current minute's close; ±1-minute tolerance is generous (random-shift null 99th pct ≈ {m10.null_p99:.2f}).
* In-sample; D-1 only; close-based range; predictive not causal; no source code. Missing variables might be tick-level timing, true intraday high/low, or internal state.

## 8. Files
`src/bl_bk_build.py` (book state at every event/control second and cycle-minute) → `bl_bk_tests.py` (variables, mechanism) → `bl_bk_blocks.py` (block models incl. pace) → `bl_bk_flow.py` (order flow) → `bl_pc_sim.py` (pace machines) → `bl_pc_tests.py` (bootstrap, age vs pace, catch-up) → `bl_pc_reg.py` (regularity) → `bl_pc_example.py` (figures) → `make_bk_report.py`. Outputs `outputs/bl_bk_*`, `bl_pc_*`, `bl_summary_bk1…3.json`, `bl_summary_pc1…4.json`. Tests `tests/test_bl.py` (`test_bk_*`, `test_pc_*`).
"""
open(f'{RP}/BODY_REACTIVE_BOOK.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
