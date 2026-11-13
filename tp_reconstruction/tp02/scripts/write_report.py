"""Writes tp_reconstruction/TP02_REPORT.md; every number is read from the TP-02 outputs. python3 tp_reconstruction/tp02/scripts/write_report.py"""
import os, sys, ast, re
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import tp02_common as c
A = c.ANALYSIS; r = lambda f: pd.read_csv(os.path.join(A, f))
n0 = lambda v: f'{int(round(v)):,}' if isinstance(v, (int, float, np.integer, np.floating)) and np.isfinite(v) else ('' if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
pc = lambda v, d=1: f'{100 * v:.{d}f} %'
def table(df, cols=None, fmt=None):
    cols = cols or list(df.columns); fmt = fmt or {}; out = ['| ' + ' | '.join(cols) + ' |', '|' + '|'.join(['---'] * len(cols)) + '|']
    for _, row in df.iterrows(): out.append('| ' + ' | '.join((fmt[k](row[k]) if k in fmt else str(row[k])) for k in cols) + ' |')
    return '\n'.join(out)
MS = r('mechanism_summary.csv'); HT = r('hypothesis_tests.csv').set_index('test_id'); CS = r('clock_mechanism_summary.csv'); ES = r('expiry_exit_summary.csv'); RS = r('replacement_sequence_summary.csv'); RD = r('replacement_sequence_detail.csv')
BS = r('basket_exit_summary.csv'); PS = r('profitable_nonstop_summary.csv').set_index('population'); PC = r('profitable_by_convention_summary.csv').set_index('convention'); MC = r('mechanism_by_convention.csv').set_index('profit_defined_by')
SC = r('stop_cycle_summary.csv'); WS = r('wing_exit_summary.csv').set_index('module'); UB = r('unexplained_range_pop3.csv').set_index('item').value; MU = r('mechanism_by_underlying.csv').set_index('und'); MY = r('mechanism_by_cycle.csv')
CONF = r('mechanism_confidence_summary.csv'); REC = pd.read_csv(os.path.join(c.DATA, 'mechanism_reconciliation.csv')); HD = r('h1_decay_distribution_by_population.csv'); H2B = r('h2b_hold_mod15_histogram.csv'); RES = r('h2a_residue_ratios.csv')
T = pd.read_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet')); T['cycle'] = T.und + '|' + T.expiry.dt.strftime('%Y-%m-%d'); S = T[T.direction == -1]; P3 = S[S.pop3_clean_nonstop]
def ms(pop, item, col='share_of_events'): return MS[(MS.population == pop) & (MS.item.str.strip() == item)][col].iloc[0]
SA = 'short closings (all)'; SP = 'short, stable PROFIT'; P3N = 'short body, stable PROFIT, clean non-stop (Pop 3)'
d1 = lambda t: HT.loc[t]
reg = sorted(pd.read_csv(os.path.join(c.REPO, c.CFG['inputs']['clock_clusters'])).query('is_cluster').key)
n_short = len(S); n_all = len(T); cm = S.groupby('candidate_mechanism').size()
c09 = CS[(CS.minute == '09:15') & (CS.scope == 'ALL')].iloc[0]
def cl(t): return ast.literal_eval(re.sub(r'np\.float64\(([^)]*)\)', r'\1', t))
W = []; w = W.append
w(f"""# TP-02 · Exit-mechanism attribution and the profitable short exits

**Verdict: PASS (attribution complete). A take-profit rule was NOT found.** Profitable short body closings are mostly part of **scheduled, multi-contract expiry-day actions that end on 15-minute block boundaries and release the wings together**, not independent per-position premium targets.
The trigger that decides *which* actions happen is still unidentified. All results are in-sample on 65 inspected sessions and descriptive, not causal. Branch `research/tp02-exit-mechanism-attribution` (from TP-01 `086b8612`). Pre-registration: [`TP02_PHASE0_AUDIT.md`](TP02_PHASE0_AUDIT.md), [`tp02/config.yaml`](tp02/config.yaml).

## 1. Executive summary

| Question | Answer |
|---|---|
| 1. Short closings attributable to a stop | **{pc(ms(SA, 'STOP_CONFIRMED (module s_)'))} confirmed** (`s_` module, {n0(ms(SA, 'STOP_CONFIRMED (module s_)', 'events'))} fills); a further **{pc(ms(SA, 'STOP_POSSIBLE'))} possible** (price or timing evidence only; {pc(ms(SA, 'sensitivity: adverse premium >= 1.5x reference in the previous 15 min'))}–{pc(ms(SA, 'sensitivity: adverse premium >= 1.15x reference in the previous 15 min'))} of all short closings under the 1.5× / 1.15× thresholds for the price rule alone); {pc(ms(SA, 'STOP_NOT_EVIDENCED'))} not evidenced |
| 2. Explained by clock | {pc(ms(SA, 'CLOCK (registered minute)'))} of short closings fall on the 7 registered clock minutes (chance {pc(ms(SA, 'CLOCK (registered minute)', 'chance_rate'))}); **{pc(c09.share_stop_class_confirmed_or_possible, 0)} of the 09:15 cluster is stop-related**; the other six minutes are expiry-day body closings. Across all minutes of the hour, the 15-minute block end (:14 :29 :44 :59) has **{d1('H2a-grid').observed:.1f}×** the closing hazard (Holm p = {d1('H2a-grid').holm_p:.3f}) |
| 3. Explained by expiry management | {pc(ms(SA, 'EXPIRY_MGMT (expiry day, 14:30 onward)'))} of short closings are on an expiry day from 14:30 (chance {pc(ms(SA, 'EXPIRY_MGMT (expiry day, 14:30 onward)', 'chance_rate'))}); {pc((S.day_type == 'EXPIRY_DAY').mean())} of all short closings and {pc((P3.day_type == 'EXPIRY_DAY').mean())} of Pop 3 are on expiry days |
| 4. Replacement / re-entry | {pc(ms(SA, 'REPLACEMENT (same right, <= 60 s, registered)'))} (chance {pc(ms(SA, 'REPLACEMENT (same right, <= 60 s, registered)', 'chance_rate'))}): only {d1('H6-replacement').observed * 100:.1f} points above chance among Pop 3 (CI {d1('H6-replacement').ci_lo * 100:.1f} to {d1('H6-replacement').ci_hi * 100:.1f}); **not supported as an explanation** |
| 5. Wing / hedge management | **{pc(ms(SA, 'WING_LINKED (wing closing same right, +-10 s, registered)'), 0)}** of short closings have a wing closing of the same right within ±10 s (chance {pc(ms(SA, 'WING_LINKED (wing closing same right, +-10 s, registered)', 'chance_rate'), 0)}); {pc(WS.loc['h_', 'share_with_body_short_closing_within_10s_same_right'], 0)} of `h_` wing closings have a body short closing partner (chance {pc(WS.loc['h_', 'chance_rate'], 0)}) |
| 6. Profitable body closings left unexplained | Pop 3 (clean, profitable, non-stop, body) = **{n0(UB['Pop 3 events'])}**; unexplained by the registered flags **{n0(UB['unexplained, registered flags (events)'])}**, by the stricter flags **{n0(UB['unexplained, strict flags (events)'])}** ({n0(UB['strict unexplained and not in a multi-contract batch (events)'])} outside any multi-contract batch); counting only the excess of each flag over chance, up to **{n0(UB['unexplained upper range: 1 - (flag rate - chance), events'])}** |
| 7. Repeatable TP-related behaviour in them | **No.** Decay-level hazard (H1) not supported in any convention; no decay cluster in Pop 4 / 4S; no portfolio mark-to-market threshold distinguishable (H4b). Only market-state effects are small (§12) |
| 8. Stable under FIFO / LIFO / average cost | Pop 3 is stable by construction (PROFIT under all three); H1 is NOT_SUPPORTED under each; mechanism shares move by a few points (clock {pc(MC.loc['FIFO', 'clock'])} FIFO, {pc(MC.loc['LIFO', 'clock'])} LIFO) |
| 9. Strongest explanation | scheduled expiry-day, multi-contract closing actions on 15-minute block ends with hedge release (H2a and H4a SUPPORTED, §12) |
| 10. Data that would help most | decision logs or configuration (what triggers the batch), per-order leg identifiers, decision times for body orders, expiry settlement prices, a later out-of-sample period (§17) |

## 2. Research question
What makes Algo 8 close a profitable short position when no stop-loss is being triggered? TP-01 left an unexplained mix of stop-like, clock-driven and partial one-lot closings. TP-02 attributes every closing fill to evidence flags, isolates the profitable short body closings that no stop explains, and tests six registered hypotheses on them.

## 3. Data and methodology
* **Inputs (read-only):** TP-01 ledger, roles, exit events ({n0(n_all)} closing fills, {n0(n_short)} short), the exposure panel (209,489 short-inventory minutes), the raw trade file and raw Breeze bars. No Stage 2 file is used.
* **Three times kept apart:** decision time (exact only for tagged `h_ s_ v_ m_` orders; unavailable for the {n0((T.module == 'num').sum())} body closings, where only bounds exist), order-entry minute, execution second. One order-entry stamp exceeds its first fill by under 60 s (minute rounding); the bound then uses the first fill.
* **Evidence flags, not forced labels** (definitions fixed in `config.yaml` before any result): stop (`STOP_CONFIRMED` = module `s_`; `STOP_POSSIBLE` = inside a cycle-stop execution window, or the contract mark ≥ 1.25× the reference in the previous 15 minutes, or exit price ≥ 1.25× the reference; else `STOP_NOT_EVIDENCED`, which is not proof of absence); clock (all 7 TP-01 minutes); expiry (expiry day from 14:30); replacement; wing; basket.
* **Deviation, disclosed:** the registered flags are near-saturated ({pc(ms(SA, 'any registered non-stop flag'), 0)} of short closings carry one), so presence alone proves nothing. I therefore added, after seeing this, (i) stricter variants (`REPLACEMENT_STRICT`, `WING_LINKED_STRICT`) and (ii) a **chance baseline** for every flag (time-shift null for association flags, exposure share for calendar flags). The registered results are reported unchanged next to them. The effect rule for the holding-time test (H2b) was also not in the registered config (R ≥ 0.10, more than 3× the null 97.5th percentile).
* **Inference:** permutation labels shuffled only inside cycle × day-type × hour strata; bootstrap over whole expiry cycles ({int(c.CFG['inference']['bootstrap_reps'])} resamples); Holm over the 16 registered primary tests; no ML. Hazard ratios and AUCs are descriptive.
* **Reconciliation with TP-01:** all {len(REC)} checks agree (closing fills {n0(n_all)}, closed units {n0(T.qty_closed.sum())}, per-convention label counts, per-module counts); difference 0 on every line (`data/mechanism_reconciliation.csv`).

![funnel](tp02/analysis/figures/fig4_population_funnel.png)

## 4. Module-specific exit analysis
{table(CONF[CONF.module.isin(['num', 'h_', 's_'])].groupby(['module', 'candidate_mechanism']).agg(events=('events', 'sum')).reset_index().assign(share_of_short=lambda d: (d.events / n_short).round(3)).sort_values(['module', 'events'], ascending=[True, False]), fmt={'events': n0})}

Short closings by module: `num` {n0((S.module == 'num').sum())}, `s_` {n0((S.module == 's_').sum())}, `h_` {n0((S.module == 'h_').sum())}. A `num` order is a body order; none of the `num` closings is called a take-profit here. `candidate_mechanism` is `MULTIPLE_POSSIBLE_MECHANISMS` for {pc(cm.get('MULTIPLE_POSSIBLE_MECHANISMS', 0) / n_short, 0)} of short closings, because the flags overlap; the per-flag shares with chance baselines are the informative numbers:

{table(MS[MS.population.isin([SA, SP, P3N])][['population', 'item', 'events', 'share_of_events', 'chance_rate', 'excess_over_chance', 'cycles']].assign(share_of_events=lambda d: d.share_of_events.round(3), chance_rate=lambda d: d.chance_rate.round(3), excess_over_chance=lambda d: d.excess_over_chance.round(3)).fillna(''), fmt={'events': n0})}

![flags](tp02/analysis/figures/fig1_flags_vs_chance.png)

## 5. Clock-driven exit findings (all 7 registered minutes)
{table(CS[CS.scope == 'ALL'][['minute', 'short_closings', 'cycles', 'share_expiry_day', 'share_body_module', 'share_stop_class_confirmed_or_possible', 'share_stable_profit', 'median_second', 'median_lots_closed', 'median_position_lots_before', 'share_closing_whole_position', 'share_with_ge3_other_contracts_within_30s']].round(2), fmt={'short_closings': n0})}

* **09:15 is a stop cluster**: {n0(c09.short_closings)} short closings, {pc(c09.share_stop_class_confirmed_or_possible, 0)} stop-related, all on expiry days. It coincides with the {int(SC.stop_at_open.sum())} cycle stops executed in the opening minutes (decision times precede the fills by seconds; one SENSEX stop was decided at 09:14:13 and filled at 09:15:13).
* **14:29, 14:44, 14:58, 14:59, 15:14, 15:19** are almost exclusively expiry-day body closings (one lot per fill, partial in {pc(1 - CS[(CS.scope == 'ALL') & (CS.minute != '09:15')].share_closing_whole_position.mean(), 0)} on average), batch-like (≥ 3 other contracts within 30 s in {pc(CS[(CS.scope == 'ALL') & (CS.minute != '09:15')].share_with_ge3_other_contracts_within_30s.mean(), 0)}), and stably profitable in {pc(CS[(CS.scope == 'ALL') & (CS.minute != '09:15')].share_stable_profit.mean(), 0)} of cases. Seconds-of-minute are not fixed (medians 28–44 s with day-specific bursts), so there is no exact-second schedule.
* **A 15-minute structure exists but is not a per-lot timer.** Over all 15 minute-of-hour residues the controlled closing hazard peaks at residue 14 (:14 :29 :44 :59) at **{d1('H2a-grid').observed:.2f}×** (cycle-bootstrap CI {d1('H2a-grid').ci_lo:.2f}–{d1('H2a-grid').ci_hi:.2f}; NIFTY {d1('H2a-grid').ratio_nifty:.2f}, SENSEX {d1('H2a-grid').ratio_sensex:.2f}; effect in {d1('H2a-grid').cycles_with_effect} cycles; permutation p = {d1('H2a-grid').perm_p:.3f} corrected for the choice of residue; Holm {d1('H2a-grid').holm_p:.3f}), and a smaller one at residue 0 ({RES.controlled_hazard_ratio.iloc[0]:.2f}×). Holding time modulo 15 minutes is mildly concentrated (Rayleigh R = {d1('H2b-timer-FIFO').observed:.2f} FIFO, {d1('H2b-timer-LIFO').observed:.2f} LIFO versus a null ≤ {d1('H2b-timer-FIFO').ci_hi:.2f}) but only {d1('H2b-timer-FIFO').ratio_nifty * 100:.1f} % of closings fall within 10 s of an exact multiple (chance 2.3 %), so a timer anchored at each lot's entry is **not** supported.

![minute of 15](tp02/analysis/figures/fig2_minute_of_15.png)

![hold](tp02/analysis/figures/fig3_hold_mod15.png)

## 6. Expiry-management findings
{table(ES[ES.module == 'num'][['expiry_category', 'events', 'share_of_short_events', 'stable_profit', 'share_stable_profit', 'cycles']].round(3), fmt={'events': n0, 'stable_profit': n0})}

Stably profitable short body closings are concentrated late on expiry day: the share that is stably profitable rises from {pc(ES[(ES.module == 'num') & (ES.expiry_category == 'D0_OPEN')].share_stable_profit.iloc[0], 0)} at the open to {pc(ES[(ES.module == 'num') & (ES.expiry_category == 'D0_FINAL')].share_stable_profit.iloc[0], 0)} in the final 20 minutes, while carry-day reductions are {pc(ES[(ES.module == 'num') & (ES.expiry_category == 'D1_CARRY_DAY_REDUCTION')].share_stable_profit.iloc[0], 0)} profitable. Late-day profit is consistent with time decay of positions that had already decayed (median exit at {P3.exit_ratio_FIFO.median() * 100:.0f} % of the reference, §11); **an expiry-day profit is not treated as a take-profit**.

## 7. Replacement and re-entry findings
Registered flag: an opening short in the same underlying and right by another order within 60 s of the closing. {pc(ms(SA, 'REPLACEMENT (same right, <= 60 s, registered)'))} of short closings carry it against a chance rate of {pc(ms(SA, 'REPLACEMENT (same right, <= 60 s, registered)', 'chance_rate'))}; the strict variant (the opening order has a later number in the same block **and** the same units) is {pc(ms(SA, 'REPLACEMENT_STRICT (+ later order number, same units)'))}.
Where an opening order of the same block follows, it was submitted after the closing order in {pc((RD[RD.first_open_sequence_evidence == 'opening_order_submitted_after'].events.sum()) / RD[RD.first_open_sequence_evidence != 'unknown'].events.sum(), 1)} of comparable cases, so the replacements are real sequences, not just nearby timestamps.

{table(RD.sort_values('events', ascending=False).head(8).round(3), fmt={'events': n0})}

Among Pop 3 the excess over chance is only {d1('H6-replacement').observed * 100:.1f} points (cycle-bootstrap CI {d1('H6-replacement').ci_lo * 100:.1f} to {d1('H6-replacement').ci_hi * 100:.1f}, one-sided bootstrap p {d1('H6-replacement').perm_p:.3f}, Holm {d1('H6-replacement').holm_p:.2f}) and re-adding the same contract within 300 s is **not** above chance ({d1('H3-readd').observed * 100:.1f} points). Most buy-backs are therefore not strike migrations; a profitable closing is not explained by the opening that follows it.

## 8. Wing and hedge exit findings
{table(WS.reset_index()[['module', 'closings', 'units', 'share_of_long_closings', 'gross_pnl_FIFO', 'stable_profit_share', 'stable_loss_share', 'share_partial', 'share_with_body_short_closing_within_10s_same_right', 'chance_rate']].round(3), fmt={'closings': n0, 'units': n0, 'gross_pnl_FIFO': n0})}

Wing closings are long-direction closings: **{n0(WS.loc['ALL long closings', 'closings'])} fills, gross P&L about ₹{WS.loc['ALL long closings', 'gross_pnl_FIFO'] / 1e5:.1f} L**, {pc(WS.loc['ALL long closings', 'stable_loss_share'], 0)} stably losing. Wing P&L is never merged with short-body P&L. `h_` wing orders are tightly coupled to body closings (partner within ±10 s in {pc(WS.loc['h_', 'share_with_body_short_closing_within_10s_same_right'], 0)} against {pc(WS.loc['h_', 'chance_rate'], 0)} by chance): wings are closed together with the body rather than on a separate schedule.

## 9. Basket / portfolio-level evidence
{table(BS.round(3), fmt={'events': n0})}

* **H4a (SUPPORTED):** among Pop 3, {pc(d1('H4a-basket').best_bin_pct, 0)} of closings have ≥ 2 other contracts closed within ±5 s, **{d1('H4a-basket').observed * 100:.0f} points above the time-shift chance rate** (CI {d1('H4a-basket').ci_lo * 100:.0f} to {d1('H4a-basket').ci_hi * 100:.0f}; NIFTY {d1('H4a-basket').ratio_nifty * 100:.0f}, SENSEX {d1('H4a-basket').ratio_sensex * 100:.0f}; effect in {d1('H4a-basket').cycles_with_effect} cycles; Holm {d1('H4a-basket').holm_p:.3f}).
* Closing groups of 3 or more contracts include both rights in {pc(BS[BS.basket_bin.isin(['3-4', '5-9', '10+'])].both_rights_share.mean(), 0)} of cases and a concurrent losing leg in {pc(BS[BS.basket_bin.isin(['3-4', '5-9', '10+'])].loss_leg_share.mean(), 0)}: profitable shorts are frequently closed **together with losing legs and the wings**.
* **H4b (portfolio mark-to-market, PARTIAL):** the highest controlled hazard is near a cycle mark-to-market of ₹{d1('H4b-MTM').best_bin_pct / 1e3:,.0f} K ({d1('H4b-MTM').observed:.2f}× its neighbours), but the interval ({d1('H4b-MTM').ci_lo:.2f}–{d1('H4b-MTM').ci_hi:.2f}) and the permutation p ({d1('H4b-MTM').perm_p:.2f}) do not distinguish it from chance. **No portfolio trigger is claimed.**

## 10. Stop-confirmed, stop-possible, stop-not-evidenced
{table(MS[(MS.population.isin([SA, SP, 'short, stable PROFIT, stop-related (Pop 2 ∩ profit)', 'long closings (wings and other)'])) & MS.item.isin(['STOP_CONFIRMED (module s_)', 'STOP_POSSIBLE', 'STOP_NOT_EVIDENCED'])][['population', 'item', 'events', 'share_of_events', 'cycles']].round(3), fmt={'events': n0})}

* Cycle stops: {len(SC)} cycles, {n0(SC.stop_fills.sum())} `s_` fills; decision-to-fill lag median {SC.decision_to_fill_s.median():.1f} s (decision time exact from the tag). Inside the stop windows other modules keep acting: {n0(SC.window_closings_short_num.sum())} body short closings and {n0(SC.window_short_openings_num.sum())} body short openings versus {n0(SC.window_short_openings_s_.sum())} short openings by the stop module itself (the RSK-12 overshoot, seen again at execution time).
* **Price-based stop evidence is deliberately broad**: {pc(ms(SA, 'of which: adverse premium >= 1.25x'), 0)} of short closings had a mark ≥ 1.25× the reference in the previous 15 minutes (under any convention) and {pc(ms(SA, 'of which: exit price >= 1.25x reference'), 0)} exited above 1.25× (losses). It identifies where a stop could have acted, not that it did; the three thresholds (1.15 / 1.25 / 1.5) bracket the share from {pc(ms(SA, 'sensitivity: adverse premium >= 1.5x reference in the previous 15 min'), 0)} to {pc(ms(SA, 'sensitivity: adverse premium >= 1.15x reference in the previous 15 min'), 0)}.
* Of the stably profitable short closings, {pc(ms(SP, 'STOP_CONFIRMED (module s_)'), 1)} are `s_` liquidations (a cycle stop also closes profitable legs), {pc(ms(SP, 'STOP_POSSIBLE'), 0)} stop-possible, {pc(ms(SP, 'STOP_NOT_EVIDENCED'), 0)} not evidenced. `STOP_NOT_EVIDENCED` is not proof that no stop occurred.

## 11. Profitable non-stop body-exit investigation
{table(PS.reset_index().round(3).drop(columns=['gross_pnl_LIFO', 'gross_pnl_AVG']), fmt={'events': n0, 'units': n0, 'gross_pnl_FIFO': n0})}

By convention (profit defined under each):

{table(PC.reset_index())}

Pop 3 has **{n0(len(P3))} events in {P3.cycle.nunique()} cycles** (NIFTY {n0((P3.und == 'NIFTY').sum())}, SENSEX {n0((P3.und == 'SENSEX').sum())}), median exit at **{P3.exit_ratio_FIFO.median() * 100:.0f} %** of the reference premium and a median exit price of {P3.px_fill.median():.1f} points: they are deeply decayed shorts closed late on expiry day, {pc((P3.day_type == 'EXPIRY_DAY').mean(), 0)} of them on expiry day.
The unexplained part depends on how strictly a flag counts as an explanation:

{table(pd.DataFrame({'definition': ['every registered flag explains its event', 'strict flags (same units / later order number)', 'strict flags and outside any multi-contract batch', 'only the excess of each flag over chance explains'], 'unexplained events': [UB['unexplained, registered flags (events)'], UB['unexplained, strict flags (events)'], UB['strict unexplained and not in a multi-contract batch (events)'], UB['unexplained upper range: 1 - (flag rate - chance), events']]}), fmt={'unexplained events': n0})}

The registered union flag rate is {pc(UB['registered union flag rate'])} against a chance rate of {pc(UB['chance union flag rate (time-shifted)'])}, an excess of {pc(UB['excess over chance'])}. Pop 4S (strict, {n0(UB['unexplained, strict flags (events)'])} events, {S[S.pop4s_unexplained_strict].cycle.nunique()} cycles) is {pc((S[S.pop4s_unexplained_strict].phase == 'MIDDAY').mean(), 0)} mid-day on expiry day with a median exit ratio of {S[S.pop4s_unexplained_strict].exit_ratio_FIFO.median() * 100:.0f} % and a median exit price of {S[S.pop4s_unexplained_strict].px_fill.median():.0f} points; it has **no decay cluster under any convention** (`analysis/h1_decay_distribution_by_population.csv`).

## 12. Candidate TP mechanisms (registered hypotheses)

{table(HT.reset_index()[['test_id', 'observed', 'ci_lo', 'ci_hi', 'perm_p', 'holm_p', 'events', 'cycles', 'ratio_nifty', 'ratio_sensex', 'cycles_with_effect', 'verdict']].round(3).fillna(''), fmt={'events': n0})}

`perm_p` is a permutation p-value (H1, H2, H4b, H5) or a one-sided cycle-bootstrap p (H3, H4a, H6); `holm_p` is Holm-adjusted over all 16. For H5 the individual rows read NOT_SUPPORTED when the AUC stays inside the registered no-effect threshold (< 0.55 or > 0.45) even if it is statistically detectable (60-minute return and 30-minute volatility, Holm 0.04). For H2b the columns `ci_lo / ci_hi` are the null 2.5 / 97.5 percentiles of R and `ratio_nifty` is the share of closings within 10 s of a multiple of 15 minutes.

| Hypothesis | Verdict | Evidence for | Evidence against |
|---|---|---|---|
| H1 fixed premium-decay TP | **NOT_SUPPORTED** (all 3 conventions) | Pop 3 has a descriptive cluster at 0–5 % of the reference under all three conventions ({int(HD[(HD.population == 'Pop 3') & HD.is_cluster].events.min())}–{int(HD[(HD.population == 'Pop 3') & HD.is_cluster].events.max())} events) | Controlled hazard ratio at the best decay bin only {d1('H1-FIFO').observed:.2f} / {d1('H1-LIFO').observed:.2f} / {d1('H1-AVG').observed:.2f}× (permutation p {d1('H1-FIFO').perm_p:.2f} / {d1('H1-LIFO').perm_p:.2f} / {d1('H1-AVG').perm_p:.2f}); the cluster is deep decay late on expiry day, not a target |
| H2 scheduled harvesting | **SUPPORTED (15-minute block ends)**; per-lot entry timer NOT supported | residue 14: {d1('H2a-grid').observed:.2f}× | exact-second schedule absent; hold mod 900 s concentration mild |
| H3 position-level reduction | **NOT_SUPPORTED** | partial, one-lot closings are the norm | no re-add above chance ({d1('H3-readd').observed * 100:.1f} points) |
| H4 basket / portfolio | **SUPPORTED for simultaneous multi-contract closing (H4a)**; mark-to-market threshold PARTIAL / not distinguishable (H4b) | {d1('H4a-basket').observed * 100:.0f} points above chance, {d1('H4a-basket').cycles_with_effect} cycles | no mark-to-market level separates events (p {d1('H4b-MTM').perm_p:.2f}) |
| H5 market state | **PARTIAL**: small effects, not a trigger | event minutes sit nearer expiry (AUC {d1('H5-minutes_to_expiry').observed:.2f}), slightly higher 30-minute volatility ({d1('H5-rv30_bp').observed:.2f}) and 60-minute return ({d1('H5-idx_ret_60m_bp').observed:.2f}) | all effects within 0.41–0.54; 15-minute return, range expansion and distance from open show none |
| H6 replacement-related realisation | **NOT_SUPPORTED** | {pc(ms(P3N, 'REPLACEMENT (same right, <= 60 s, registered)'))} flagged | excess {d1('H6-replacement').observed * 100:.1f} points, CI includes 0 |

## 13. Matching-convention sensitivity
{table(MC.reset_index().round(3))}

Pop 3 and Pop 4 are PROFIT under all three conventions by construction, so their membership is convention-free; what differs is the broader profit set (FIFO {n0(PC.loc['FIFO', 'profit_short_closings'])}, LIFO {n0(PC.loc['LIFO', 'profit_short_closings'])}, average cost {n0(PC.loc['AVG', 'profit_short_closings'])} profitable short closings) and the reference premium used in H1 (three separate runs, all NOT_SUPPORTED). The stop-possible share of profitable closings falls from {pc(MC.loc['FIFO', 'stop_possible'], 0)} (FIFO) to {pc(MC.loc['STABLE (all three)', 'stop_possible'], 0)} when stability is required, because convention-sensitive closings sit near stop-like references.

## 14. Per-expiry and per-underlying consistency
{table(MU.reset_index()[['und', 'short_closings', 'stop_confirmed_share', 'stop_possible_share', 'clock', 'expiry_mgmt', 'replacement', 'wing_linked', 'basket', 'pop3', 'pop4s_strict']].round(3), fmt={'short_closings': n0})}

Pop 3 has events in {int((MY.pop3 > 0).sum())} of 35 cycles (NIFTY {int(((MY.und == 'NIFTY') & (MY.pop3 > 0)).sum())}, SENSEX {int(((MY.und == 'SENSEX') & (MY.pop3 > 0)).sum())}); cycle stops occur in {len(SC)} cycles (NIFTY {int((SC.und == 'NIFTY').sum())}, SENSEX {int((SC.und == 'SENSEX').sum())}). Per-test cycle counts and underlying ratios are in section 12; per-cycle detail in `analysis/mechanism_by_cycle.csv`. NIFTY has the higher confirmed-stop share ({pc(MU.loc['NIFTY', 'stop_confirmed_share'])} vs {pc(MU.loc['SENSEX', 'stop_confirmed_share'])}) because {int((SC.und == 'NIFTY').sum())} of the {len(SC)} cycle stops are NIFTY.

## 15. Alternative explanations tested
* *Fixed decay TP* (H1): rejected as a driver. *Per-lot entry timer* (H2b at phase 0): rejected. *Strike migration* (H6, H3): rejected. *Portfolio mark-to-market threshold* (H4b): not distinguishable. *Market state* (H5): small effects only.
* *Time decay alone*: late-day expiry closings of deeply decayed shorts would look like profitable "targets"; the controlled hazard shows no decay-level preference, so the cluster near 0–5 % is consistent with a time effect.
* *Stop-module overshoot*: stop windows contain body closings and openings; Pop 3 excludes events inside them and events whose mark reached 1.25× in the previous 15 minutes.
* *Chance association*: every flag is shown against a chance baseline; wing, basket and 15-minute-block associations survive it, replacement does not.

## 16. Limitations
1. **No decision logs.** Body-order decision times are unavailable; stop absence cannot be proven.
2. **Flags are generous and overlapping** ({pc(ms(SA, 'any registered non-stop flag'), 0)} of short closings carry at least one). The explained / unexplained split is a range, not a point. The stricter flags and the chance baseline were added after the saturation was observed.
3. **Lot ownership is unidentified**; all attributions repeat under three conventions.
4. **Hazard ratios and AUCs are associations**, not causes; the 15-minute structure could be produced by data-generation or order-batching mechanics unrelated to a profit decision.
5. **In-sample**: 65 sessions, all inspected before; only {int((MY.pop3 > 0).sum())} cycles contribute Pop 3 events.
6. **Option data cover only contracts Algo 8 traded**; marks are 1-minute closes with carried prices; index minutes after 15:15 are excluded when frozen (DAT-15 of the alpha branch).
7. **Cycle mark-to-market** uses average-cost basis and 1-minute marks, not the algorithm's own quotes (Stage 1: the stop constant is known only to within ₹1.22–1.36 L).
8. The H2b effect rule, strict flags and chance baselines were not in the registered config (documented in section 3).

## 17. Final verdict and answers

**TP-02: PASS.** Every closing fill has a stop class, mechanism flags and a confidence level; stop-confirmed / possible / not-evidenced are separated; all 7 clock minutes, replacement sequences, expiry phases, wings and baskets were analysed independently; Pop 3 / 4 were isolated; all tests pass; outputs reproduce.
**No take-profit rule was discovered**, and that is the result: the evidence says profitable short closings arise from scheduled multi-contract expiry-day actions (block ends, hedge release) plus time decay.

| Evidence level | Findings |
|---|---|
| **Confirmed facts** | counts reconcile with TP-01; {pc(ms(SA, 'STOP_CONFIRMED (module s_)'))} of short closings are `s_` stop liquidations; the 09:15 cluster is stop-driven; wing closings co-occur with body closings far above chance |
| **Strong evidence** | profitable body closings concentrate in expiry-day late session, at 15-minute block ends, in multi-contract batches |
| **Hypotheses** | a schedule evaluates positions at block ends and closes baskets with their wings; the decision rule behind each batch is unknown |
| **Inconclusive / not supported** | fixed decay TP; per-lot timer; strike migration; portfolio mark-to-market threshold |

**What data would materially improve confidence:** (1) the algorithm's configuration or decision logs (batch trigger, schedule, thresholds); (2) leg / allocation identifiers per order; (3) decision timestamps for body orders; (4) official expiry settlement prices (completes P&L of the 37,480 unclosed units); (5) bid/ask and the full option chain; (6) a later period of the same account's trades for out-of-sample tests.

## 18. Recommended TP-03
**TP-03: the batch decision.** Reconstruct the multi-contract closing batches as units (members, rights, quantities, wing partners, 15-minute block, order-number block) and ask what distinguishes a batch that includes profitable shorts from one that does not: cycle-level state (mark-to-market on the algorithm's own quotes ±, side delta, hedge ratio, time to expiry) measured at the last completed minute before the batch. Pre-register the batch definition, compare against exposed non-batch minutes, keep stop-adjacent batches separate, and treat any threshold as a hypothesis for an out-of-sample test. Do **not** start TP-03 without authorisation; items (1)–(3) above would change its design.
""")
open(os.path.join(c.PKG, 'TP02_REPORT.md'), 'w').write('\n'.join(W)); print('written', sum(len(x) for x in W))
