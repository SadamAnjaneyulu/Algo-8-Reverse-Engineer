# Algo 8 — D-1 buy-backs, third pass: why some exit at 1.1× and others at 1.7×

*Follow-up to `BUYBACK_DECODE.md` and `BUYBACK_STOP2.md` at the user's request ("they don't choose randomly between 1.2× and 1.7×"). Descriptive and post-hoc, in-sample, D-1 of 32 cycles. Lot ownership: a buy-back removes the open lot with the highest own ratio on that contract. Figure: `figures/bl_bt_summary.png`.*

## 0. Result: the 1.1×–1.7× spread is not random, it is a mix of different exits
1. **Not points but ratio.** The points lost at the buy-back scale with the entry price: log-slope 1.05 (SENSEX) and 0.73 (NIFTY); a fixed-points stop would give about 0. There is no clear time-of-day pattern in the ratio.
2. **Holding time separates them** (ρ 0.30 / 0.46). Lots bought back within 10 minutes of their sale exit at about **1.1×**; lots held more than 30 minutes at about **1.55–1.6×**.
3. **The fresh, low-ratio exits are directional lots.** Of buy-backs within 5 minutes, about 55% are reactive lots (they are 17% of all sells). Each sell type has its own exit behaviour:
   * **Scheduled straddle lots: a premium stop.** The hazard is about 0 below 1.5×, then 4% → 15% → 47% per minute above 1.5 / 1.6 / 1.7×. Out-of-fold the threshold is **1.6–1.65× of the lot's own entry** (minute high).
   * **Reactive lots: cut when the breakout continues.** The leg on the break side is bought back while the spot keeps going in the break direction: hazard 2.9% vs 0.3%, and 7.9% per minute at 1–2 steps of continuation. Most of these exits happen within 5 minutes of the sale.
   * **Solo lots: cut when the market reverses.** Hazard 4.8% at 2+ steps of reversal, and 2.0% after an opposite two-candle break, against 0.24%.
4. **Buy-backs are rebalancing events, not isolated stops.**
   * 67–77% come with buy-backs on other strikes of the same right within 5 s.
   * About 30% of the older-lot buy-backs come with a **new solo sell on the other right** within 5 s (base rate 3%): when calls are cut in a rally, puts are sold.
   * About 53–63% are at second :00 (minute-clocked).
5. **In-profit buy-backs (129 lots, about 10%)** are mostly the **partner leg**:
   * 34% are the same-strike partner on the other right (in-loss buy-backs: 6%);
   * 29% happen at the same moment as a stop on the other right, i.e. the straddle is closed together;
   * 18% come with a stop on the same right (cluster);
   * 45% have no coincident event.

**What this does to accuracy (honest):**
* Separate rules per type, out-of-fold, at lot level:
  * scheduled premium stop F1 0.48;
  * solo 0.35 (premium) and 0.10 (spot steps);
  * reactive 0.17 / 0.15.
* The continuation and reversal exits raise the hazard 5–25× but do not turn into a sharp threshold on steps or ratio. Their exact trigger, probably checked on live prices within the minute, is not recoverable from one-minute bars.
* So the decoded structure explains *why* ratios differ, but the lot-level buy-back accuracy stays at the premium-stop level (about 0.59 on the real book).

## 1. Ratio at buy-back by holding time (lots in loss)
| held_bin | buy_backs | median_ratio | reactive share | scheduled share |
|---|---|---|---|---|
| (0, 5] | 117 | 1.109 | 56% | 10% |
| (5, 10] | 50 | 1.109 | 50% | 24% |
| (10, 15] | 44 | 1.241 | 30% | 50% |
| (15, 30] | 126 | 1.365 | 17% | 38% |
| (30, 60] | 225 | 1.538 | 16% | 55% |
| (60, 120] | 248 | 1.57 | 12% | 69% |
| (120, 400] | 337 | 1.582 | 7% | 66% |


## 2. Hazard per lot-minute (%) by sell type
| minute high ÷ entry | reactive | scheduled | solo |
|---|---|---|---|
| (0.0, 1.0] | 0.03 | 0.03 | 0.03 |
| (1.0, 1.1] | 0.28 | 0.04 | 0.17 |
| (1.1, 1.2] | 1.17 | 0.05 | 0.15 |
| (1.2, 1.3] | 1.26 | 0.11 | 0.6 |
| (1.3, 1.4] | 0.71 | 0.12 | 1.29 |
| (1.4, 1.5] | 1.31 | 0.32 | 1.76 |
| (1.5, 1.6] | 2.48 | 4.12 | 5.02 |
| (1.6, 1.7] | 14.96 | 14.81 | 31.87 |
| (1.7, 9.0] | 32.0 | 46.98 | 57.47 |


## 3. Context at the buy-back second
| type | holding | at second :00 | other strike same right ±5 s | buy-back other right ±5 s | new sell ±5 s | new sell same right ±5 s | n |
|---|---|---|---|---|---|---|---|
| late | held > 10 min | 100% | 0% | 0% | 100% | 0% | 27 |
| late | held ≤ 10 min | 19% | 93% | 4% | 0% | 0% | 1 |
| reactive | held > 10 min | 55% | 77% | 12% | 28% | 8% | 99 |
| reactive | held ≤ 10 min | 41% | 48% | 11% | 16% | 2% | 128 |
| scheduled | held > 10 min | 56% | 67% | 17% | 35% | 8% | 30 |
| scheduled | held ≤ 10 min | 63% | 27% | 13% | 10% | 0% | 671 |
| solo | held > 10 min | 53% | 68% | 22% | 28% | 11% | 61 |
| solo | held ≤ 10 min | 51% | 33% | 38% | 13% | 13% | 288 |


## 4. Buy-backs in profit vs in loss (coincident events within 5 s)
| state | partner_same_strike_other_right | stop_like_same_right | stop_like_other_right | sell_same_right | sell_other_right | sec0 |
|---|---|---|---|---|---|---|
| in loss | 6% | 68% | 1% | 7% | 29% | 53% |
| in profit | 34% | 18% | 29% | 19% | 17% | 57% |


## 5. Lot-level rules per type (out-of-fold)
| type | family | params | F1 | precision | recall |
|---|---|---|---|---|---|
| scheduled | premium only | [(np.float64(1.65),), (np.float64(1.6),)] | 0.479 | 0.696 | 0.369 |
| scheduled | adverse steps only | [(np.float64(1.5),), (np.float64(2.75),)] | 0.1 | 0.181 | 0.083 |
| scheduled | steps OR premium | [(np.float64(1.6), np.float64(3.75)), (np.float64(1.6), np.float64(4.0))] | 0.492 | 0.593 | 0.421 |
| reactive | premium only | [(np.float64(1.6),), (np.float64(1.7),)] | 0.174 | 0.673 | 0.103 |
| reactive | adverse steps only | [(np.float64(0.75),), (np.float64(0.5),)] | 0.147 | 0.123 | 0.181 |
| reactive | steps OR premium | [(np.float64(1.6), np.float64(3.25)), (np.float64(1.7), np.float64(3.5))] | 0.162 | 0.43 | 0.103 |
| solo | premium only | [(np.float64(1.6),), (np.float64(1.65),)] | 0.348 | 0.749 | 0.228 |
| solo | adverse steps only | [(np.float64(0.75),), (np.float64(2.0),)] | 0.098 | 0.133 | 0.114 |
| solo | steps OR premium | [(np.float64(1.6), np.float64(3.5)), (np.float64(1.6), np.float64(4.0))] | 0.335 | 0.579 | 0.24 |


## Evidence labels
* **Observed:** §0–5.
* **Inferred:** "sub-strategy stops"; the rebalancing reading; the live-price explanation.
* **Unresolved:** the exact trigger of the reactive continuation and solo reversal exits, and 45% of in-profit buy-backs.
* All post-hoc on the same 32 cycles.
