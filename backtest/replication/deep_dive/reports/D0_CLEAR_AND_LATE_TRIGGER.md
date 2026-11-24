# D0 clearance timing and the late D-1 sale trigger

*Plan (trigger part): `D0_CLEAR_AND_LATE_TRIGGER_PLAN.md`, written before the trigger tests ran. The clearance test's criterion (decision metric first, P&L last, stop flips separate) was stated in the chat at the start of the turn and is applied here.*
*Scripts: `src/bl_clr_test.py`, `bl_clr_full.py`, `bl_trig_table.py`, `bl_trig_test.py`, `bl_trig_followup.py`, `bl_trig_ladder.py` → `outputs/clr/`, `outputs/trig/`.*

> **Unit correction (`FORWARD_TEST.md`):** "about 58% of real late sales unmatched" is the **event-level** figure (unique minute × side: recall 0.46). All 148 real late sales are single-lot orders, and at **order level 34% are unmatched** (recall 0.66). Also, strike agreement in the last 25 minutes (15:15+) is 0.31 exact / 0.67 within one step, lower than the 0.54 of the 14:15–15:40 window in `LATE_D1_RULE.md`.

## Result first
| Question | Answer | Evidence label |
|---|---|---|
| Did the real system clear D0 at 15:14 in every era? | **No. Before 3 Aug it cleared at 15:18–15:19.** After 3 Aug it clears at 15:14 (two early cycles, 11 and 13 Aug, at 15:33–15:34). | Observed |
| Does the simulator fix (era clearance clock) help? | Yes, modestly: decision match 52% → 97%, mean absolute error −8%, no stop flips. Falsified on post-auction cycles (fit gets worse there). **Adopted as an opt-in dated regime.** | Observed |
| Is the real post-15:15 sale trigger the published index? | **No.** Published index: weak and side-inconsistent (CE 1-minute move AUC 0.36, wrong direction). | Observed, weak power |
| Is it a live futures-like price? | **Marginally yes (FUT only).** Out-of-fold AUC 0.80 vs clock 0.71 (Δ +0.088 [0.015, 0.158]); both sides agree. Not distinguishable from the option-implied index except on 1-minute moves. | Weak |
| Is there a new timing rule? | **No.** Shortening the ladder gate does not beat the engine at the decision level (ΔF1 +0.03 [−0.06, +0.16]). About 55–60% of real late sales are still unmatched. | Unresolved |

## 1. D0 clearance
**Real clearance clock (D0 covers after 15:00 in the real log; minute by which 90% of covers are done):**
| era | cycles | 90% of covers done by | notes |
|---|---|---|---|
| before 3 Aug | 9 | 15:18–15:19 (j = 363–364) in **all 9** | tail of wing and hedge closures to 15:26 |
| 4 Aug | 1 | 15:14 | |
| 11 Aug (NIFTY), 13 Aug (SENSEX) | 2 | 15:33–15:34 | early in the auction regime |
| 25 Aug onwards | 10 | 15:14 (j = 359) | |

The simulator clears at 15:14 in every era. New parameter (one, era-valued): `clear_era` → 364 before 3 Aug, 359 after (`clear_j` is the generic override; defaults unchanged).

**Teacher-forced from the real carried book (D0 only):**
| era | n | real covers done by 15:14 / by 15:19 | mean abs. error 15:14 → 15:19 | median abs. error | mean P&L change | stop flips |
|---|---|---|---|---|---|---|
| before | 11 | **52% / 97%** | **65.4k → 59.9k** | 47.4k → 37.6k | +₹6.0k (median +₹0.6k) | 0 |
| after (falsification) | 19 | 90% / 90% | **85.0k → 88.3k (worse)** | 68.7k → 69.9k | +₹10.5k | 0 |

* After the auction, clearing later would raise simulated P&L by ₹10.5k per cycle but moves the fit away from the real clock. **This is why the minute is set from the observed clock and never from P&L.**
* Leave-one-cycle-out constant (median of the other cycles' 90% minute): mean absolute error 62.6k, within a minute of the in-sample constant. A one-minute change of the clearance minute moves the error by about ₹2.6k, so the minute is well identified.
* Free-run (D-1 + D0), 11 pre-auction cycles: mean absolute error 102.1k → 97.9k, mean gross +₹5.1k per cycle (net +₹5.0k), median +₹0.5k, 0 flips.
* Limit: the clock comes only from the Jun–Oct 2026 real log. It is not extrapolated to the earlier backtest years, and the 11/13 Aug cycles (15:33) are not modelled.

## 2. Late D-1 sale trigger (15:15–15:40)
*Setup per plan: 900 rows (cycle × minute × side), 48 events, 18 post-auction cycles (excluding the 16 Oct call-ratio cycle); pre-auction 330 rows, 17 events, 11 cycles.*

**(a) Pre-registered family: 43 scores, BH 10%.** After the auction 39 of 43 pass. **That count is not informative:** sales are concentrated before 15:30, and the published index is flat from 15:30, so side-neutral |move| scores and the clock score capture time of day. The acceptance test is therefore the combination vs the clock baseline (nested leave-one-cycle-out, 3 features, L2 logistic):

| underlying | out-of-fold AUC [95%] | clock baseline | difference [95%] |
|---|---|---|---|
| FEED (published index) | 0.690 [0.609, 0.761] | 0.711 | −0.022 [−0.062, +0.020] |
| **FUT (future − basis)** | **0.779 [0.726, 0.827]** | 0.711 | **+0.067 [+0.002, +0.131]** |
| OPT (option-implied) | 0.681 [0.580, 0.765] | 0.711 | −0.031 [−0.128, +0.044] |
| *before 3 Aug, FEED (valid index)* | *0.825 [0.733, 0.923]* | *0.620* | *+0.205 [+0.095, +0.297]* |

**(b) Post-hoc follow-up, counted:**
* **Directional features only, clock forced in** (no side-neutral features). FUT: AUC 0.800 [0.743, 0.856], Δ vs clock **+0.088 [0.015, 0.158]**. FEED: −0.023 [−0.063, +0.022]. OPT: −0.043 [−0.125, +0.034].
* **Only 15:15–15:29** (removes the 15:30+ confound). FUT: 0.837 [0.785, 0.897], Δ **+0.113 [0.014, 0.207]**. FEED: +0.005 [−0.070, +0.069]. OPT: −0.041 [−0.129, +0.030].
* **Side split, FUT:** 1-minute favourable-move AUC CE 0.72 / PE 0.71; 5-minute fresh-extreme AUC CE 0.73 / PE 0.71. FEED CE is **0.36** (wrong direction) and PE 0.59. OPT 0.60 / 0.61.
* **Paired underlying comparison, 27 comparisons:** one survives BH: FUT − FEED on 1-minute moves, +0.24 [0.14, 0.37] (BH p 0.03). FUT − OPT is not resolved (1-minute: +0.11 [−0.00, +0.24]).
* **Book imbalance** (single score, pre-registered): AUC 0.35 [0.30, 0.41], i.e. 0.65 inverted: **sales go to the lighter side** (consistent with delta re-balancing). **Last-strike premium vs its sale price:** AUC 0.35 [0.27, 0.44]: sells after the premium has fallen. It is correlated with the favourable move.
* **Alignment:** with features through the previous minute (not the minute's own bar) nothing passes BH, before or after (best OPT 1-minute move AUC 0.62, BH 0.13). The signal needs the minute's own bar, as the engine's fill-at-minute-close convention assumes.

**(c) Decision-level check** (engine ladder, reference = underlying before the latest real sale on that side; precision/recall of (minute, side) ±1 minute):
| era | underlying | gate chosen leave-one-cycle-out | precision / recall | F1 | engine gate (60) F1 | ΔF1 [95%] | random precision / recall |
|---|---|---|---|---|---|---|---|
| after | FEED | 5 (17 of 18 folds) | 0.37 / 0.33 | 0.35 | 0.31 | +0.04 [−0.02, +0.14] | 0.16 / 0.13 |
| after | FUT | 5 (17 of 18 folds) | 0.45 / 0.42 | 0.43 | 0.40 | +0.03 [−0.06, +0.16] | 0.16 / 0.11 |
| after | OPT | 10 (15 of 18 folds) | 0.50 / 0.33 | 0.40 | 0.36 | +0.04 [−0.04, +0.16] | 0.18 / 0.09 |
| before | FEED | 30 (11 of 11 folds) | 0.71 / 0.59 | 0.64 | 0.40 | +0.24 [−0.04, +0.67] | 0.23 / 0.13 |

* The ladder on any underlying beats random timing about threefold. The gate length is not identified: every ΔF1 interval includes 0.
* Even in the best case about 58% of real late sales have no matching ladder fire.

## 3. Interpretation (adversarial)
* **Supported:**
  * the real D0 clearance clock before 3 Aug is 15:19, not 15:14;
  * after 15:15, the real late sales follow favourable moves of a live price, not the published index;
  * the sale side tends to be the lighter one.
* **Weak:**
  * futures over option-implied: only one comparison out of 27 resolves, and the lower bounds of the key intervals are 0.002–0.015 with 48 events. Choosing among three underlyings costs power, so this does not survive a strict multiplicity correction;
  * shorter gate: the AUC ranks short windows (5–30) above 60 in both eras, but the decision-level check cannot separate them.
* **Could be luck or structure not related to the real rule:**
  * 48 events in 18 cycles (17 events in 11 cycles before the auction): a null result means "not detectable here";
  * futures aligned with a median basis is a measurement choice, not a fitted parameter.
* **Not tested:** option volume (not in the cache) and anything tick-level; the 7 Dec regime; BSE-specific rules.

## 4. Test ledger (all counted)
| block | variants |
|---|---|
| Clearance | 2 clearance minutes teacher-forced × 30 cycles; LOCO constant; free-run era regime |
| Trigger, pre-registered | 43 scores (post), 17-event pre-auction run, 4 nested LOCO models, with and without the outlier cycle, lag-1 robustness |
| Trigger, post-hoc | 27 paired underlying comparisons; 6 directional models (3 underlyings × 2 windows); ladder gate G ∈ {5, 10, 15, 30, 60} × 4 underlying-era combinations with LOCO |
| Earlier, same data | the late-rule work (`LATE_D1_RULE.md`), the Fix A re-scores, the extended-session and underlying variants |

## 5. Decision
* **Adopted:** the era clearance regime `clear_era` (opt-in; default unchanged, so the pre-paper battery is untouched). Reason: a directly observed clock, with a falsification check on the other era.
* **Not adopted:** any new late-sale timing rule. The best candidate (ladder on futures with a short gate) is a hypothesis to confirm, not a result.
* **Verdicts unchanged:** NO-GO; Fix A not adopted.
* **Next, forward only:**
  1. record futures and option-implied minute bars live next to every real order, so the underlying can be identified directly;
  2. pre-register this single rule for the next real cycles: ladder on futures, gate 5, reference = last real sale, minute-level match;
  3. report by regime: pre-3 Aug, 3 Aug – 6 Dec, from 7 Dec.
