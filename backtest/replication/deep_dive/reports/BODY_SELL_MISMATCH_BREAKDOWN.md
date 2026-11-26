# Body-sell mismatches: ledger and failure categories (D-1, accepted F run)

*2026-11-25. Step 1 of diagnose, fix, verify. Pre-registration: `BODY_SELL_MISMATCH_PLAN.md` (one post-hoc addendum for descriptive checks, labelled below). Evidence label for all numbers: **historical reproduction**, 32 development cycles, F under `one_lot_v2`. **No engine change, nothing fitted, nothing committed.** Ledgers: `outputs/bodysell/`.*

## Result
**The 1,145 is not 1,145 wrong decisions. It is 1,179 real body sells with no simulated sell of the same type within 60 s (1,145 still unmatched under TF-E), and most of them sit in clusters where the real system fires several sells and the simulator fires fewer.** The clock-driven scheduled straddles reproduce; the misses live in the solo/ladder component.

| | Real body sells (4,408) | Simulated body sells (4,091) |
|---|---|---|
| Missing / extra | **1,179 missing** (1,145 persist under TF-E, 34 recovered) | **873 extra** (84% are solo-ladder: 730) |
| Matched | 3,229: strike exact 78.4% (**699 wrong strikes**), lots exact 99.3% (22 wrong) | |
Counts reconcile exactly to F's class tables; the probe replay of the engine reproduces all 4,091 simulated body sells; every order has exactly one status and category (`tests/test_bodysell_ledger.py`, `test_bodysell_breakdown_outputs.py`, mutation-checked).

## Failure categories (pre-set cascade)
**Missing real sells (1,179):**
| ID | Reading | Orders | Share | Persist in TF-E |
|---|---|--:|--:|--:|
| **M1** | **supply/count**: a same-type simulated sell within 60 s was matched elsewhere | **727** | 61.7% | 695 |
| **M4** | **trigger never fires**: no simulated sell of that type within 300 s | **305** | 25.9% | 303 |
| **M3** | **timing offset**: an unmatched same-type simulated sell 61-300 s away (median 170 s) | 123 | 10.4% | 123 |
| **M2** | **possible wrong side**: an unmatched opposite-type simulated sell within 60 s | 24 | 2.0% | 24 |
**Extra simulated sells (873):** X4 no real decision within 300 s **359** (41%); X1 real supply exhausted **324** (37%); X3 timing **109** (12%); X2 possible wrong side **81** (9%). By role: ladder solo 730 (X4 337, X1 210, X3 105, X2 78); breakout straddle 61 and extra 56 (mostly X1); scheduled straddle 26.
**Matched-order detail ("wrong strike", "wrong quantity"):** by simulated partner role:
| Partner | Matched | Strike exact | +/-1 step | 2+ steps | Lots exact |
|---|--:|--:|--:|--:|--:|
| scheduled straddle | 2,084 | 94.5% | 5.4% | 0.1% | 100% |
| breakout straddle | 384 | 78.6% | 18.5% | 2.9% | 100% |
| breakout extra | 171 | 69.6% | 19.9% | 10.5% | 100% |
| **ladder solo** | 547 | **25.6%** | 39.7% | **34.7%** | 99.8% |
| protective wing sell (cross-class) | 43 | 0% | 0% | 100% | 51% |
Wrong strikes: ladder 407, scheduled 115, breakout 134, cross-class 43 (total 699). **Wrong side, quantity and order type are not material for body sells** (24 and 81 side candidates; 22 lot differences).

## Where they sit (Observed)
* **Module (inferred, the log has no label):** scheduled clock 18 misses (of about 2,100 waves), pair 486, **solo 675**. Misses by module and category: solo M1 353 / M4 209 / M3 90 / M2 23; pair M1 356 / M4 96 / M3 33.
* **Time:** 321 of 1,179 (27%) are at 15:00 or later (M4 153, M1 106, M3 48, M2 14). Every hour has misses; all 32 cycles are affected (median 36.5 per cycle, top five 25%: SENSEX 10 Sep 76, NIFTY 18 Aug 59, NIFTY 28 Jul 57, SENSEX 13 Aug 53, NIFTY 25 Aug 51). CE 708, PE 471.
* **Book state is not the cause:** before the missed orders the real short book has a median of 73 lots, the simulator's 75 (median absolute difference 9). Consistent with TF-E.

## What the ledger says about the mechanism (post hoc, descriptive only; Inferred)
1. **The real system fires more sells than the simulator in the same window.** Real body sells total **4,671 lots** (4,408 orders, 99.75% single-lot); the simulator **4,091** (all single-lot, so order granularity is *not* the issue for sells). Around an M1 order there are about **7.1 real** same-type sells within +/-60 s against **2.6 simulated**.
2. **Same-second multiples.** 27.8% of real body sells sit in same-second, same-type groups of two to six; the simulator's 15.4% are mostly the duplicated scheduled seconds. **316 of the 727 M1 orders (43.5%) are at the same second as another real same-type sell**, 287 within 1-60 s, 124 isolated. A trigger that sells several lots as several 1-lot orders would look like this; so would several near-simultaneous triggers. The log cannot say which.
3. **Finer spacing than the engine's ladder.** Consecutive real same-type sells within 60 s are separated by a median of **0.15** of the engine's ladder trigger distance (n = 1,604); the simulator's ladder sells by **0.98** (n = 739). The real solo rule does not fire on a spot ladder of 0.2 strike steps, or fires on another variable.
4. **The engine's gate is rarely what the real system respects.** At the 209 unmatched solo sells (M4) the engine's ladder is live in 100% of cases, but its "new 60-minute extreme" condition holds in only **8%**; the engine sits a median 15.6 (CE) / 19.5 (PE) points short of its trigger (trigger distance 10 points NIFTY, 20 SENSEX). *Unresolved:* whether the real gate is absent, shorter, or on futures (the frozen late-sale rule uses futures with a 5-minute gate).
5. The solo ladder **over-fires and under-fires at once** (730 extra, X4 337 with no real sell within 300 s), so the engine's timing and its trigger variable are both off, not only its count.

## Examples (real cycles; engine view at the order second)
| Cat | Cycle, time | Type, strike | Inferred module | Detail |
|---|---|---|---|---|
| M1 | NIFTY 30 Jun 09:34:06 | CE 24050 | solo | simulated ladder sell 32 s away already matched; engine 16.6 points short of its CE trigger; real shorts 10/5, simulated 7/5 |
| M1 | NIFTY 14 Jul 11:12:00 | PE 24100 | pair | simulated ladder sell 0 s away matched to another real sell: real fired two or more at that second |
| M2 | NIFTY 8 Sep 15:19:10 | CE 23700 | solo | opposite-type simulated sell 50 s away; late session |
| M3 | NIFTY 14 Jul 10:33:08 | PE 24150 | solo | simulated ladder sell 216 s away, unmatched |
| M4 | NIFTY 30 Jun 09:24:21 | CE 24050 | solo | no simulated sell within 399 s; engine 18.8 points short of the CE trigger |
| M4 | NIFTY 7 Jul 14:48:14 | PE 24350 | pair | no simulated sell within 217 s |
| X4 | NIFTY 7 Jul 09:18:36 | PE 24350 | ladder solo | no real sell within 149 s; both books at 3 lots |
| X1 | NIFTY 14 Jul 09:43:40 | PE 24050 | ladder solo | a real sell 41 s away, matched elsewhere |
More in `outputs/bodysell/examples_missing.csv` and `examples_extra.csv`.

## Proposed priority (proposal only; no fix is built)
| Rank | Target | Size | Why this order | What a fix would need |
|---|---|--:|---|---|
| **1** | **Solo trigger count and spacing** (M1, X1, and the M3/M4/X3/X4 that are the same disagreement seen from the other side) | M1 727 and X1 324 first; with M3, M4, X3, X4 up to 1,155 missing real and 792 extra simulated orders | the single largest block, concentrated in one component, all 32 cycles | a pre-registered hypothesis on what fires a solo sell (same-second multiples, finer trigger, another variable); testable on the existing log |
| 2 | Solo strike reference (wrong strike) | 407 of 547 matched ladder orders (74%) | clear and measurable; partly data-limited (decision-time premiums exist only for traded contracts; earlier lag finding) | strike reference and its lag; may end as *irreducible* for part |
| 3 | The 15:00+ block | 321 missing, 137 extra | systematically weakest block; overlaps with the frozen late-sale rule (futures ladder, gate 5) which the engine does not contain | decide whether the frozen late rule enters the engine as a module (it would not be changed) |
| 4 | Breakout/scheduled strike differences | 249 | small, smaller than the ladder effect | check after rank 1 |
The first fix should start from **rank 1 sub-class M1 same-second multiples (316 orders)** only if you agree, because it has the cleanest testable hypothesis; otherwise rank 1 as a whole.

## What is supported, suspicious, unknown
* **Supported (Observed):** the category counts; the misses are not book-driven; the scheduled clock reproduces; the engine's ladder does not match the real solo sells in count, spacing, strike or timing.
* **Inferred:** the real system uses a finer or different trigger and sizes some triggers as several 1-lot orders.
* **Unknown / possibly irreducible:** the real trigger variable and gate (no decision log, no tick data), the true decision times.

## Limits
Module labels are inferred. Categories describe how the simulator differs from the real log, not why the real system acted; M1 and X1 are two views of one disagreement and should not be added. Engine-view columns describe the current engine. Same development cycles; any fix will be evaluated on the same data first and must be labelled historical reproduction.

## Files
`src/bl_bodysell_ledger.py`, `src/bl_bodysell_run.py`, `tests/test_bodysell_ledger.py`, `tests/test_bodysell_breakdown_outputs.py`; `outputs/bodysell/{ledger_real.csv, ledger_sim.csv, breakdown.json, examples_missing.csv, examples_extra.csv}`.
