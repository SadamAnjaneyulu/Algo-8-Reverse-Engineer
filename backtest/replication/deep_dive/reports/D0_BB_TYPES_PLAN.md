# D0 buy-backs: every reason, open to close — plan

*Written before the classification is run. In-sample: D0 of the 30 cycles with both logs, 9,656 body buy-back lots (2,126 on lots carried from D-1). Builds on `D0_BUYBACKS.md` (stop 1.4×, take-profit 0.1×, bursts, carried lots) and `D0_SELL_TYPES.md`.*

## Question
For each D0 buy-back lot, what was the reason? On D-1 it was a stop at about 1.6× the lot's own entry premium. What are the reasons on D0, from open to close?

## Lot ledger
* One row per bought-back lot (`bl_d0b_removed.pkl.gz`): time, strike, right, entry premium, decision price, ratio = decision price ÷ entry, the sell type of the lot's entry (scheduled pair, grid pair, solo …), carried from D-1 or sold on D0.
* The lot removed on a buy-back is the highest-ratio open lot on the contract (as in chunk 2).

## Types (fixed precedence; the first that applies wins)
1. **Cycle-stop window:** the buy-back is at or after the cycle's first `s_` order.
2. **Clearance:** from 15:10 on. Split into 15:10–15:13, the 15:14 minute, and 15:15 on.
3. **Stop-loss:** the minute high of the lot's own contract is at least **1.4×** its entry. The 1.4 is the value fitted in chunk 2. 1.2 and 1.6 are reported as sensitivity.
4. **Take-profit:** the minute low of the lot's own contract is at most **0.1×** its entry.
5. **Partner:** a stop-loss buy-back of the **other right at the same strike** within ±60 s. Chance level: the same rule with the partner times shifted ±10 minutes.
6. **Roll-out:** a body sale on the same right within 60 s **after** the buy-back. Same chance level.
7. **Burst member:** the lot is in a burst (same right, gaps of at most 30 s) of at least 5 lots.
8. **Other.**

A multi-label overlap table is also reported so the precedence choice is visible.

## For each type
* Lots, share, cycles.
* Ratio quantiles (10 / 25 / 50 / 75 / 90%), share in loss (ratio above 1).
* Holding time quantiles (D0-entered lots).
* Share carried from D-1.
* Entry type mix.
* Time of day (by hour).
* CE share.

## Extra questions
* **Q1 — ratio.** The share of lots at or above 1.2, 1.4 and 1.6, by type, and the hazard curve (chunk 2) for the lots of scheduled straddles only.
* **Q2 — holding time of scheduled straddles.** Is there a fixed holding time? Test: the histogram of (buy-back time − entry time) for lots that entered in a scheduled pair, against the same histogram with the buy-back times shifted by a random 1–15 minutes (500 draws). A fixed hold shows as a peak above the null.
* **Q3 — buy-backs on the clock.** The share of buy-back lots in the 133 s after a 5-minute mark, and at second :00, against uniform time.
* **Q4 — what is left.** The size of "Other", with its ratio and hour profile, and which scheduled / solo entries it belongs to.

## Acceptance
* A trigger-based type (partner, roll-out) is kept if its share is at least 1.5× the shifted chance share.
* Q2 is positive if a holding-time bin exceeds the null's 95th percentile by at least a factor of 2.
* Everything else is descriptive. Evidence labels as before; post-hoc steps are labelled.

## Addendum (post-hoc, after the first run)
* 32% of roll-out lots fall in block minute 0. A buy-back right before a 15-minute mark is followed by the scheduled sale, so the ±10-minute shifted chance level (which breaks the clock alignment) may flatter the roll-out type.
* **Clock-preserving chance level.** The partner and roll-out chance shares are also computed with the times shifted by ±15 minutes, which keeps the alignment with the marks. A type is kept only if it beats **both** chance levels by at least 1.5×.
* **Roll-out without scheduled sales.** The roll-out share is also computed counting only the sales that are not scheduled pairs.
