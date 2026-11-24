# Focused late-sale tests: straddle, side, pair window, profit booking (pre-registration)

*Written 2026-11-24 **before** any test below was run. Follows `LATE_SALE_TRIGGER.md` (37 tests, one weak lead). This plan deliberately **adds no new indicator screen**: it tests the three leads with one pre-specified statistic each, plus the profit-booking idea in four fixed forms. The frozen rule, score and hashes stay untouched.*

## Facts recorded before testing (descriptive, not tests)
* **No untouched labelled future cycles exist.** Order logs end at the 22 Oct 2026 expiry. Cycles from 26 Oct to 11 Nov have market data but no orders, so no late sale can be labelled there. "Validate on untouched future cycles" is impossible today; it needs the forward recorder.
* **The only held-out data is the pre-auction era** (before 3 Aug 2026): 7 cycles with late open-short orders (28 orders; window 15:15–15:29 because the session ended at 15:30), never used to screen the state features (the screen used post-auction cycles only). It is a different market structure and small, so it can **support or contradict** but rarely settle. Power is estimated below.
* Late-window **sell orders include 34 `close_long` orders** (sell-to-close of long hedge wings/body longs) besides 193 `open_short`. These are the only sales that can book a profit on a position.

## Definitions (fixed)
* **Decision minute** j (09:15 + j); every feature uses information **strictly before** the minute (book at the start of the minute, prices through the previous minute).
* **Straddle change (STR15)** = ATM straddle (parity forward, nearest strike) at j divided by its value at j−15, minus 1. Same for CE and PE rows.
* **Oriented futures move (FUT5L)** = (close[j−1] − close[j−6]) of the futures (post-auction cycles) or the published index (pre-auction cycles, where it is clean). A **contrarian** sale is a put after a rise or a call after a fall.
* **Profit % (PP)** = book mark-to-market P&L ÷ premium collected by open-short orders so far. **Give-back (GB)** = MTM now − running maximum of MTM at earlier minute starts (≤ 0).
* Sample: post-auction development cycles (NIFTY 16 Oct excluded), window 15:15–15:39, as before. Hazard statistic: stratified AUC within (cycle, side) blocks, curveball null, 1,000 permutations.

## Tests (one statistic each; family of 9 for BH 10%)
| ID | Question | Statistic and rule |
|---|---|---|
| **F1** | **Does the straddle decline predict a sale in cycles not used to find it?** | Hazard AUC of STR15 on the **pre-auction** cycles. Direction fixed in advance: lower → more sales (AUC < 0.5). **Supported** if AUC ≤ 0.40 and one-sided p ≤ 0.05; **contradicted** if AUC ≥ 0.50; otherwise **inconclusive**. Power estimated by sub-sampling 7 random post-auction cycles over 15 minutes (optimistic: the post effect is the best of 12) |
| **F1p** | **Is STR15 just the clock / time-of-window decay?** | Placebo: permute STR15 series across cycles (same side, same minute) 1,000 times and recompute the post-auction AUC. The observed 0.318 must lie below the 5th percentile of the placebo AUCs |
| **F2a** | **Does futures direction pick the side?** | Among minutes where **exactly one side** was sold: share of contrarian sales using FUT5L, pooled by cycle (cycle-cluster bootstrap CI, 4,000 draws). **Supported** if share ≥ 0.65, CI lower bound > 0.50, and ≥ 60% of cycles with ≥ 2 such minutes lean contrarian. Also run on the **pre-auction** cycles (**F2a-held-out**; same rule, direction fixed) |
| **F3** | **Do timing and side form one model?** | Leave-one-cycle-out logistic on rows (cycle, minute, side). Model T = clock + STR15; model J = T + oriented FUT5L. ΔAUC(J − T) with linearised cluster-robust 95% CI and cycle bootstrap. STR15 is side-agnostic by construction, so it **cannot** explain the side; this test asks whether a two-part rule (timing from STR15, side from FUT5L) fits better than timing alone |
| **PB2** | **Do profit-booking sells coincide with the late short sales?** | Share of `close_long` orders (≥ 15:15, post-auction) that fall within 60 s of an open-short burst in the same cycle, vs circular-shift null (5,000 draws). Meaningful if excess ≥ 0.15 |
| **PB3** | **Is a sale more likely when the book holds a large profit?** | Hazard AUC of PP. Meaningful if AUC ≥ 0.60 or ≤ 0.40 and same direction in ≥ 60% of cycles |
| **PB4** | **Is a sale more likely after a give-back from the P&L peak?** | Hazard AUC of GB. Same rule as PB3 |
| **PB5** | **Do any-side covers (profit-taking buy-backs) precede the sale?** | Share of late open-short orders with a cover of **either** side in the previous 10 minutes, vs circular-shift null of covers (2,000 draws). Meaningful if excess ≥ 0.15 (the earlier same-side test found 1 of 148 vs 11% expected) |

**Descriptive, no p-value (reported, not in the family):**
* **PB1**: profitability of the 34 `close_long` orders: FIFO-match each to the long buys of the same cycle, cp and strike; report the share sold above entry and the exit/entry ratio. "Consistent with profit booking" only if ≥ 70% were sold above entry **and** the median exit/entry ratio is ≥ 1.5.
* **F4 (pair window)**: the six two-leg bursts are treated as a separate event. Report which cycles have one, the state at 15:27 (sold-lot deficit, net deficit, MTM, premium sold) for pair vs non-pair cycles, the legs' strikes relative to the forward, and whether the **pre-auction** cycles show any two-leg bursts in 15:28–15:30. No inference from 6 events.
* **F2b**: side chosen by the larger fall in the ATM option premium over the previous 5 minutes (the "cheaper option" wording), compared with F2a.

## Decision rules
A claim is **supported** only if the test passes BH at 10% **and** the size rule **and** (for F1 and F2a) the held-out version does not contradict it. Anything else is **not supported** (not detectable here ≠ absent) or **inconclusive** (power below 80%).

## Stated limits in advance
* Same development cycles as every earlier test. The pre-auction held-out set is small and a different regime.
* The straddle feature is the best of 12 screened; F1p and the held-out set are the guards, not a proof.
* If F1 is inconclusive, only the forward recorder can settle it; the recorder fields needed are STR15 and the per-side sold-lot count (not added here).

## Addendum (after the run; descriptive, not in the family)
Three diagnoses added after seeing the results, all descriptive: (i) the straddle AUC split at 15:30 (`focused_extra.json`), because the held-out AUC contradicted the lead; (ii) the pre-auction two-leg bursts (computed directly from the orders because `events.csv` holds post-auction bursts only); (iii) the nearest-burst relation of the 34 sell-to-close orders. The pre-registered rule for F1 ("AUC ≥ 0.50 means contradicted") is reported as written, with the power caveat.
