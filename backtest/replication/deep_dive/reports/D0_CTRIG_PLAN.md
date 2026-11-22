# D0 counter-sells: how, when, and what triggers them — plan

*Written before the tests below. In-sample discovery on D0 of the 30 cycles with both logs (no untouched data; every result is labelled in-sample, out-of-fold where stated). Builds on `D0_COUNTER.md` and `D0_SELL_TYPES.md`.*

## What is already known (not re-tested)
* A "counter-sell" in `D0_SELL_TYPES.md` = a **solo** sale (not part of a CE+PE pair) on right R′ with a buy-back of the other right R within ±60 s: 1,788 lots, 20% of D0 sell lots.
* Stop-loss buy-backs go with R′ sales, but the sales are as common before the buy-back as after. A fresh 60-minute spot extreme lifts R′ sales on its own. The solo ladder (0.05-step spot ladder, fresh 60-minute extreme gate) fits lot F1 0.377 against a placebo 0.095.
* What is missing: **what actually triggers the sale, and whether "counter-sell" is a separate rule at all.**

## Definitions (locked)
* **Decision-time features** use only market bars up to the **previous minute's close** (j−1) and orders strictly before the sale. Bars of the sale's own minute (j) are **contemporaneous** and are kept separate (diagnostic only; one-minute bars cannot say what came first inside the minute).
* **Panel:** one cell = (cycle, minute j, right R′), from 09:16 to the minute before the cycle's first stop-module order or 15:10, whichever is first. **Outcome y** = solo lots sold on R′ in the minute (binary "any" for AUC; count for size).
* **Counter label** = the `D0_SELL_TYPES` definition above. Population for H1 = all solo sale orders after removing opening solo and the replacement label (same precedence as before), split into counter-labelled and other.

## Hypotheses (each can be killed)
* **H1 — The label is an artifact.** Counter-labelled solo sales cannot be told apart from other solo sales using market and book state (no buy-back features).
  *Test:* leave-one-cycle-out (LOCO) gradient-boosting AUC, counter vs other, cycle-bootstrap CI. *Kill H1 if the CI lower bound is above 0.55.*
* **H2 — Spot move.** R′ is sold when the spot has just moved in R′'s favour (CE short: spot falling; PE short: spot rising): returns over 1/3/5/15/30/60 minutes, fresh extremes over 15/30/60/120 minutes and the day, distance from the day's extreme and from the open.
* **H3 — Premium state.** R′'s own ATM premium: change over 1/3/5/15 minutes, ratio to its day high and low, and the mark-to-entry ratio of the open R′ lots.
* **H4 — Book state.** Open short lots on R′ versus R, premium-weighted exposure, recent buy-backs on R and R′ (last 1/5/15 minutes, stop-loss only), recent sales on R′ and R, minutes since the last R′ sale, cumulative MTM relative to the −₹1.2 lakh stop.
* **H5 — Loss recovery.** The premium sold in the 60 s after a stop-loss buy-back is proportional to the realised loss of the stopped lots.
* **H6 — Same-instant coupling.** A tight (≤2 s) coupling between a buy-back and a sale that is distinct from the spot-driven background.
  *Test:* signed time differences at 1 s resolution, solo sales on R′ against stop-loss buy-backs on R, against a ±15 min shifted null (clock kept). *Accept if the 0–2 s bin holds ≥3× the null with a cycle-bootstrap CI above 1×.*
* **H7 — Clock.** The sale times follow the timer clock (the recurring-second timers found for scheduled selling). *Test:* LOCO share of counter-labelled sale times within ±2 s of a time seen at the same underlying/version in other cycles, against a ±150 s shifted null. *Accept at ≥3× null.*

## Tests
**N1 — Label vs population (H1).** AUC as above; also the share of counter-labelled lots by hour, underlying and version against other solo.

**N2 — Trigger search on the panel (H2–H4).**
* LOCO gradient boosting (fixed hyper-parameters, no tuning), AUC and PR-AUC per feature group (time of day and underlying only = baseline; + spot; + premium; + book; + all) and group ablation (all minus one). Cycle-bootstrap CIs.
* A group is **informative** if its LOCO AUC lower CI is above 0.55 and it adds ≥0.02 AUC over the baseline.
* **Contemporaneous check:** add bar j (minute's own high/low/close). A large jump means the trigger is inside the minute and not recoverable from minute bars.
* **Forward check:** train on the first 20 cycles by expiry date, test on the last 10.
* **Shuffle placebo:** the same model on cycle-permuted features.

**N3 — From predictors to a rule.** Only for informative groups: a depth-limited tree (depth ≤3) fitted LOCO on the top features, scored at lot level (±1 minute) as before. A **trigger rule is accepted** only if out-of-fold lot F1 ≥ 0.50 **and** ≥ 3× its cycle-permuted placebo. Otherwise the result is "associated predictors, trigger not recovered".

**N4 — Tight coupling (H6) and timing profile.** 1 s lag histogram; excess mass over the null per bin; the share of counter-labelled lots that sit in the tight bin versus the broad background; hour-of-day profile of counter-labelled sales against the hour-of-day panel rate.

**N5 — Size and loss recovery (H5).** Per stop-loss event: premium value sold on R′ in the next 60 s (lots × price) against the realised loss of the stopped lots (lots × (buy-back price − entry)); Spearman, slope, and the same against a shifted null. Lots per burst against the spot move over the burst. *H5 accepted if the Spearman correlation lower CI is above 0.3 and it beats the shifted null.*

**N6 — Order mechanics.** Orders per burst, gaps inside bursts, lots per order, limit-price distance to the fill, strike offset, share at a strike already short, order-tag distance to the nearest same-second buy-back (descriptive; tags are exchange ids, not a clock).

## Rules for reading the results
* **No fitted parameter is chosen on the test cycle.** Gradient-boosting settings are fixed before the run (200 trees, depth 3, learning rate 0.05, subsample 0.8).
* **No new metrics** beyond AUC, PR-AUC, lot F1 and the stated ratios.
* **If the best predictor family is the spot move,** the answer is "counter-sell is the solo ladder seen next to a stop-loss", and the next step is the ladder's exact rule, not a new counter rule.
* **Evidence labels** as before (Observed / Inferred / Unresolved / Not testable). Any step added after seeing results is labelled **post-hoc**.
* **Not testable here:** the intra-minute order of spot moves and orders (one-minute bars); anything that depends on the vendor's live data feed.

## Addendum — written after the first results (these changes were not pre-registered)
* **Panel starts at minute 4 (09:19)**, not 09:16. Opening solo is its own type, and the feature windows are incomplete before then. 24 of the 30 cycles have minutes left before their stop.
* **Gradient boosting** is the histogram implementation, which has no row subsampling. The 0.8 in the plan could not be used. Other settings as planned.
* **N3 metric.** The plan said lot-level F1. A cell-level F1 with ±1-minute tolerance was run first. Its floor is high (flagging every cell gives 0.45), so the **exact-cell F1 is the reported metric** and the tree threshold is chosen on it. Lot-level F1 needs a size rule and is not computed.
* **Post-hoc, after N2:** the premium-low features (`phx_*`), two hand rules, the same-second follow-up (N4b, `bl_d0n_tight.py`) and the condition decomposition (N7, `bl_d0n_decomp.py`).
* **Placebo caveat.** The cycle-permuted placebo keeps cycle-level features (underlying, version), so it is above 0.5. Gains are read against the baseline and the placebo.
