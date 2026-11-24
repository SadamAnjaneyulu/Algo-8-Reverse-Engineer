# Extended session to 15:39 and Fix A re-scored

*Follow-up to `LATE_D1_RULE.md`, next steps 1 and 2. Scripts: `src/bl_bt3x_data.py` (cache) → `bl_x_rescore.py`, `bl_x_settle.py` → `outputs/xs/`.*
*Engine change: `d1_strategy/algo8_d1.py` now takes the session length from the bar arrays instead of a fixed 375. With 375-minute data the behaviour is identical: 19/19 engine tests pass, and the old simulator results reproduce exactly.*

## Result first
| Question | Answer |
|---|---|
| Does the 15:30–15:39 data change the simulator? | Barely. After the auction: −₹2.0k per cycle (median −₹0.2k), no stop flips. Before the auction: identical. |
| Does it explain the late sales? | **No.** The index is **frozen at its close from 15:29 to 15:39** (zero range on almost every post-auction day), so no spot-driven rule can fire there. Real late selling after 15:30 is 0.8 lots per cycle. |
| Fix A | **Rejected, this time on decision evidence, not P&L.** Timing precision falls by 0.047 [−0.092, −0.006]; recall does not improve (+0.017 [−0.015, +0.054]); stop agreement drops from 12 to 11. |
| Settlement value | Before the auction, the 15:29 bar differs from the official close by 14.8 points on average. **This has no effect on any total:** the lots still open at expiry are far out of the money. |
| Post-15:30 protective buys | Fully explained by existing rules: wing buys match late short sales **one for one** (wing rule), and the lump is bought at 15:30–15:33 (lump clock). |

## 1. Data
* **What the raw data contains:**
  * After the auction, options trade every minute from 15:30 to 15:39. NIFTY shows about 160 strikes per minute with full volume. Before the auction there is only a 15:30 closing print.
  * The index after the auction sits flat at its official close from 15:29 onwards. It moved in only one post-auction session (SENSEX 8 Oct, 27 points).
* **New cache `outputs/bt3x/`:**
  * Trading days on or after 3 Aug 2026 keep 385 minutes (09:15–15:39); earlier days keep 375.
  * The first 375 minutes are identical to the old cache in every session. The only difference: one far-OTM strike that first trades after 15:29 appears in 2 sessions.
  * The cache also stores the last index close of each day.
* **Official close check, NIFTY, against NSE published closes:**

  | era | sessions | 15:29 bar exact | 15:29 bar mean abs. error | last bar exact |
  |---|---|---|---|---|
  | after | 14 | 100% | 0 points | 100% |
  | before | 112 | 0% | 14.8 points | 100% |

  The real-log cycle totals re-computed with the official settlement change by **₹0 in all 30 cycles**, because the positions left at expiry are far OTM. Nothing reported earlier changes. SENSEX could not be checked: there is no BSE source.

## 2. Simulator on extended data (variant X, no rule changed)
19 complete post-auction cycles; 11 pre-auction cycles as a "do no harm" check.

| era | variant | sim gross (₹) | real (₹) | mean abs. error | stops agree | late short lots (sim / real) | late timing precision / recall |
|---|---|---|---|---|---|---|---|
| after | base (15:29 data) | −24,804 | 25,968 | 131,087 | 12 / 19 | 5.3 / 28.0 | 0.62 / 0.46 |
| after | X (15:39 data) | −26,767 | 25,968 | 132,712 | 12 / 19 | 5.3 / 28.0 | 0.62 / 0.46 |
| after | XA (X + Fix A) | −65,067 | 25,968 | 152,721 | 11 / 19 | 11.5 / 28.0 | 0.57 / 0.48 |
| before | all three | 101,352 | 96,054 | 102,057 | 10 / 11 | identical | identical |

*"Late" = 15:00–15:40. Real late shorts excluding the 16 Oct call-ratio cycle: 15.8 per cycle; simulator 5.4 (base, X) and 11.3 (XA).*

What X changes after the auction:
* **Lump price:** the lump is now priced at its own 15:30 minute. Price error vs the real lump falls from 5.29 to 4.79 per unit. Size is unchanged (median sim/real ratio 0.96).
* **D-1 per-lot stops after 15:30:** the simulator now fires **25 lots in 4 cycles**; the real system covers **9 lots in 3 cycles**. They agree on one cycle (SENSEX 21 Oct, 7 vs 7). The others are simulator-only (SENSEX 26 Aug: 11 vs 0). This mismatch is open. Option prices during the closing session may be noisy, or the real system may not run its per-lot stops then. It is not tuned here.
* **P&L vs base:** mean −₹1,963, median −₹247, 0 stop flips.

## 3. Fix A re-scored (breakout window to the session end after the auction)
Because the index is frozen after 15:29, Fix A on extended data equals Fix A on the old data. The decision scores and P&L reproduce the earlier run.

**Decisions (scored first):**

| measure | X | XA | change [95% cycle bootstrap] |
|---|---|---|---|
| late-sale timing precision | 0.62 | 0.57 | **−0.047 [−0.092, −0.006]** |
| late-sale timing recall | 0.46 | 0.48 | +0.017 [−0.015, +0.054] |
| late short lots per cycle (real 15.8) | 5.4 | 11.3 | closer in volume |
| cycle-stop agreement with the real log | 12 | 11 | −1 |

**P&L (complete result first, then the stop-flip breakdown):**
* XA vs X: mean −₹38,300, median ₹0.
* One stop flip: SENSEX 8 Oct, −₹7.09 lakh.
* Excluding the flip: mean −₹1,020, median ₹0.

**The one flip is a decision error, not luck.** On SENSEX 8 Oct Fix A sells **15 late lots** where the real system sold **3**. The bigger book then hits the cycle stop on D0, which the real system did not hit (real +₹3.29 lakh, X +₹5.82 lakh, XA −₹1.27 lakh).

**Verdict: Fix A rejected.**
* It adds volume at the wrong minutes: precision gets worse and the interval excludes 0.
* It does not catch more of the real sales: recall is unchanged.
* It costs a stop disagreement.

This replaces the earlier "rejected on P&L" and the interim "unresolved".

## 4. Unexplained late sales vs protective activity (post-auction, 18 cycles, outlier excluded)
* **Wing buys after 15:15 equal late short lots in every cycle** (18 of 18). This is the engine's existing wing rule: keep long lots equal to short lots. The protection follows the sale; it does not trigger it.
* **Lump:** 58% of late lots are sold before the lump and 64% are on the lump's side. Late lots and lump size are weakly related (Spearman 0.51, p 0.03, one of several tests here, not corrected). That is expected mechanically: the lump rule sizes from the heavier short side.
* **No financing link:** late premium vs lump cost Spearman 0.21 (p 0.39); late premium is about 3.1× lump cost overall.
* **So the trigger of the unexplained 15:15–15:29 sales is still unknown.** It is not the closing-session data, not the protective buys, and not Fix A. No new timing parameter was added, as the protocol requires.

## 5. Decision
* **Extended cache:** kept as an opt-in data fix (`BT3_DIR=outputs/bt3x`), recommended as the base for future fidelity work. The pre-paper battery stays on the old cache, so its verdict is unchanged: **NO-GO**.
* **Fix A:** rejected (decision evidence).
* **Open:**
  * the 15:15–15:29 timing trigger (about 7.7 lots per cycle);
  * the D-1 stops in 15:30–15:39 (simulator 25 lots vs real 9);
  * the 16 Oct call ratio.
* **Hold-out:** future real cycles stay locked; nothing in this step was fitted on them.
