# Phase 1, Gate 5c: D0 opening, carry, clearance and stop. Preregistration

*Written 2026-11-25 **before** any 5c variant was run. Experiments `P1-5C-*`. Baseline D0-B = the Gate 5a engine as scored in the corrected 5b (OOF 30 cycles, convention `events`, mode T). Existing data only. Evidence label: historical reproduction on development cycles; nothing here is independent. Nothing committed. Reference simulator, B1 and the 5b archive are untouched.*

## 1. What 5b showed (inputs to this gate)
Order-level keys F1 (60 s) 0.420 vs shift placebo 0.238; weakest blocks: opening window (691 missing body sells, 332 body longs, 238 buy-backs), clearance window, 15:30+, stop timing. Order splitting (S category) dominates counts and is an **execution** matter, handled in 5d as a sensitivity, not as a strategy rule.

## 2. Evidence already in the repository (not re-run; cited)
| Item | Evidence | Consequence here |
|---|---|---|
| Cycle stop | `D0_STOP_CLEAR.md`, stored `outputs/bl_d0x_s2.csv`: cumulative MTM (D-1 + D0) marked on the minute close at L = 1.20 lakh: **11/11 stops, 0 false alarms in 19 cycles**; the constant lies in 1.17-1.29 lakh; completed-bar timing is not recoverable (prev-close F1 0.53) | **X2 = diagnostic only**: no stop rule change. Engine/real stop disagreements (3 engine-only, 3 real-only cycles of 30; 8 of 11 both) are classified inherited (engine book differs after D0 decisions) because the rule on the real book has no miss and no false alarm |
| Clearance clock | `D0_STOP_CLEAR.md`, 5b profile: post-auction single wave at minute 359 in 8/10 cycles; pre-auction later and spread (start median 363.5; register decoded 15:18-15:19) | **X1** |
| Opening long buys | `D0_OPEN_ROLL.md`: a clock event at 09:16:00, size follows the lots sold in that minute (rho 0.92, within 2 lots in 89% of cycle-rights, median ratio 1.00); strike unresolved | **X3** (count rule only; strike keeps the engine's opening-wing rule, labelled unresolved) |
| Opening sells (485 solo lots), body-stream long strikes and intraday longs, burst buy-backs, other buy-backs | `D0_OPEN_ROLL.md`, `D0_BURST_LONG.md`: counts/strikes/sets not predictable on unseen cycles | **Not tested again**; classified Unresolved/data-limited in 5d |

## 3. Experiments (each tested once; counted for selection: 2 variants)
| ID | Change | Implementation |
|---|---|---|
| X1 CLK | pre-auction cycles (D0 expiry < 2026-08-03) clear at minute **363** (15:18); post-auction keep 359 | adapter-level `clearance_minute` per cycle (no engine change); 363 is the first decoded minute of the register's 15:18-15:19; **364 is run as a labelled sensitivity only and cannot be selected** |
| X3 OPEN | `opening_long_clock = True` and the fitted j=0 opening wings off: at minute 1 (09:16) buy as many body-stream longs per right as the lots sold on that right in that minute | engine switch (default off; 4 unit tests, mutation-checked) |
Other 5c items (carry, buy-backs, stop) have no new mechanism beyond what 2-4 and the register hold; they are not re-fitted here (no grid search without a new mechanism).

## 4. Acceptance criteria (fixed now; baseline numbers are computed by the evaluator **before** the variants run and written in Addendum 1)
Common to both (OOF 30 cycles, `events`, 60 s keys): **C1** overall keys F1 >= D0-B - 0.003; **C2** legacy lot-level OOF F1 >= 0.4103 - 0.005; **C3** every class F1 >= D0-B - 0.02; **C4** no cycle's keys F1 falls by more than 0.05; **C5** forward A and B directions agree (overall keys F1 not lower than D0-B by more than 0.003).
**X1 specific:** **K1** pre-auction clearance-window (orders from minute 359) buy-back keys F1 >= D0-B + 0.10; **K2** clearance-window F1 improves in a majority of the pre-auction cycles that have a clearance; **K3** post-auction cycles' orders identical to D0-B.
**X3 specific:** **O1** opening-window (minutes 0-2) body-long recall >= D0-B + 0.10 and precision >= D0-B - 0.05; **O2** opening-window body-long F1 improves in a majority of cycles that have real opening longs.
A variant failing any criterion is rejected and archived; criteria are not relaxed. A passing variant is a **candidate correction** (default stays off in the frozen config until Gate 8's freeze decision), not a baseline replacement.

## 5. Limits stated in advance
Same development cycles; minute-resolution simulated times; the era boundary and clock constant come from the same cycles (in-sample); the X3 strike is unresolved so its strict/strike-level score cannot improve beyond the opening-wing rule; the stop is minute-close-marked (it knows the close of the minute it stops in, up to 60 s early in real time): a live implementation must act at the next minute (prev-close variant F1 0.53).

## Addendum 1 (after the baseline V0 was computed, **before any variant X1/X3 ran**)
**Baseline D0-B (V0; reproduces 5b: OOF keys F1 0.4198, legacy lot-level F1 0.4103).**
| Window metric | `events` | `one_lot` |
|---|---|---|
| clearance window (minute >= 359) body buy-back: real / sim orders | 1,062 / 104; recall 0.053, precision 0.673, **F1 0.098** | 1,062 / 1,395; recall 0.205, precision 0.203, **F1 0.204** |
| opening window (minutes 0-2) body long: real / sim orders | 617 / 50; recall **0.342**, precision **0.780**, F1 0.475 | 617 / 409; recall 0.681, precision 0.435, F1 0.531 |
**Pre-run amendment (made after seeing these baselines, before any variant result; labelled):** under `events` the engine emits one aggregated order per contract at clearance (104) while the real log has 1,062 single-lot orders, so clearance-window recall is capped near 0.10 by splitting alone and **K1 as written (events window F1 + 0.10) cannot be met by any clock change**. K1 is therefore evaluated on the `one_lot` convention (baseline 0.204; threshold **>= 0.304**) **and** the `events` window F1 must not fall. The arbitrary choice of which convention is tested was made without any variant output; both are reported. O1 stays as written on `events` (recall >= 0.442 and precision >= 0.730), and the `one_lot` opening-window values are reported alongside. No other criterion changed.
