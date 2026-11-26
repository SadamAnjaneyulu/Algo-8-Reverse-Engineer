# D0: what else decides the counter-sale, and what triggers the buy-back — plan

*Written before the tests below. In-sample discovery on D0 (24 cycles with minutes after the opening window; solo sales from `bl_d0n_orders`, stop-loss events from `bl_d0y_lots`, lot book from `bl_d0b_book`). Builds on `D0_CTRIG.md`, `D0_BB_TYPES.md`, `D0_BUYBACKS.md`.*

## Why this step
* In `D0_CTRIG.md` the share of stop-loss buy-backs with a sale on the other right rose with the window: 29% within 2 s, 42% within 5 s, 54% within 10 s, 83% within ±60 s. Those four windows are **my cumulative choices**, not clusters in the data. Part of the growth is the chance rate of solo sales (chance 2.8% at 2 s, 5.6% at 5 s, 29% at 60 s). **The question is whether another condition decides if and when the sale happens.**
* A counter-sale only follows a buy-back, so the **trigger of the buy-back** is the other half. Known so far: stop-loss lots are bought back at a median 1.64× their entry (threshold fitted at 1.4× on the minute high, out-of-fold lot F1 0.39), and the hazard rises smoothly (1.4% per minute at 1.3–1.4×, 11% at 1.7–1.8×). A smooth hazard says the per-lot price is not the whole trigger.

## Part A — what else decides the sale after a stop-loss buy-back
Events: stop-loss buy-back events (one per cycle, right, second), minute j ≥ 4, before 15:10 and before the cycle's stop. Outcome: a solo sale of the other right R′ within ±W seconds, W = 2, 10, 60.
* **A0 — excess over chance.** For each W the real share minus the share with the buy-back times shifted ±15 min (clock kept). Lag histogram of the nearest sale in log-spaced bins (0–1, 1–2, 2–5, 5–10, 10–30, 30–60, 60–120 s, both signs).
* **A1 — candidate factors** (decision-time, from bars up to j−1 and orders strictly before the event second):
  * F1 R′ ATM premium at its 60-minute low;
  * F2 **ladder step:** R′ ATM premium now ÷ price of the last R′ body sale (any sale, solo or pair); and the same against the last R′ solo sale;
  * F3 R′ sales in the previous 60 s (a burst already running) and minutes since the last R′ sale;
  * F4 lots open on R′ and on R, and the lot balance;
  * F5 lots bought back in the event;
  * F6 spot move over 1, 5, 15 minutes against the stopped right;
  * F7 clock: minute within the 15-minute block, hour;
  * F8 cycle level: underlying, version.
* **A2 — model.** Leave-one-cycle-out (LOCO) gradient boosting (same fixed settings as before), AUC with cycle-bootstrap CI, for W = 2, 10, 60, with all factors, each family alone, and each family dropped; permutation importance.
* **A3 — gate test.** For the top factor (and the top pair), the sale rate with the factor on and off, within 10 s. **A factor is accepted as a "gate" if P(sale within 10 s | on) ≥ 0.60 and P(sale within 10 s | off) ≤ 0.20.** Otherwise it is an associated factor.
* **A4 — late sales.** Among events with no sale within ±60 s, the time to the next R′ solo sale (minutes) and whether the ladder step condition (F2) is first met at that sale.

## Part B — what triggers the buy-back
**Population and the circularity guard.** The "stop-loss" label is defined by "minute high ≥ 1.4× entry", so predicting it with that quantity proves nothing. The outcome here is **any body buy-back lot** on the right in the minute (excluding the 15:10+ clearance and the cycle-stop window), whatever its label.
* **B1 — crossing → buy-back conversion (per lot).** For every short lot, the first minute its contract's high is at least θ × its entry (θ = 1.2, 1.4, 1.6). The share of those lots bought back within 0, 1, 5, 15 minutes of the first crossing, and never before 15:10 or the stop. By lot origin (carried / D0) and hour.
* **B2 — reference price.** Flag a right-minute when some open lot satisfies `contract high in minute j ≥ θ × reference`, with the reference one of: (a) the lot's own entry, (b) the average entry of the lots at that strike, (c) the average entry of the right's lots as a mark ratio (Σ lots × close ÷ Σ lots × entry, bar j). θ from {1.1 … 2.0, step 0.1}, chosen on the training cycles. Scored out-of-fold by exact-cell F1 against the cell outcome, with a flag-everything floor and a ±15-minute shifted placebo. Bar j is used on purpose, since a stop trigger is a price crossing inside the minute. A version on bar j−1 shows what is knowable ahead.
* **B3 — conditional model (the main test).** Restrict to right-minutes where at least one open lot has bar-j high ≥ 1.4× its entry ("crossing present"). Outcome: any in-scope body buy-back on the right in the minute. LOCO gradient boosting AUC by feature family:
  * G0 baseline: hour, minute in the 15-minute block, right, underlying, version;
  * G1 lot state: maximum ratio, number and share of lots crossing, age of the crossing lots, carried share;
  * G2 spot against the right: moves over 1, 5, 15, 30, 60 minutes, spot at a fresh 60-minute extreme against the right, distance from the day extreme;
  * G3 premium of the right: at a 60-minute high, changes over 1, 3, 5, 15 minutes;
  * G4 side loss: unrealised loss of the right's lots in ₹ and as a share of the premium collected, lots at risk, exposure share;
  * G5 book: cumulative MTM, distance to the cycle stop, lots on the other right;
  * G6 other right: R′ premium at a low, sales on R′ in the previous 5 minutes.
  A family is **an additional condition** if it adds at least 0.03 AUC over G0 + G1 with a CI lower bound above 0.55. Also a forward check (first 16 cycles → last 8) and a cycle-permuted placebo.
* **B4 — delay.** For lots bought back at 1.4× or more, the minutes between the first crossing and the buy-back.
* **B5 — rule.** A depth-3 tree on the families above inside crossing-present right-minutes, out-of-fold exact-cell F1 against the same placebo. **A trigger is accepted only if out-of-fold exact-cell F1 ≥ 0.50 and the precision inside crossing-present minutes beats the crossing-only precision by at least 1.5×.**

## Rules for reading the results
* Fixed gradient-boosting settings (200 iterations, depth 3, learning rate 0.05, minimum leaf 50, L2 1.0). No tuning on the test cycle.
* No new metrics beyond AUC, F1 and the stated rates and ratios.
* If no factor passes, the answer is "associated factors, no gate recovered".
* Any step added after seeing results is labelled **post-hoc** in an addendum.
* **Not testable here:** order of events inside one second, tick-level price crossings, the vendor's live feed.

## Addendum — written after the first results (not pre-registered)
* **Leak fixed in Part A.** The first run used the outcome "sale within ±W s" with the feature "seconds since the last solo sale on R′", so a sale just before the buy-back gave the outcome away (AUC 0.86, a spurious 100% gate). The model outcome is now "sale at or after the buy-back second". The ±W shares stay as descriptive numbers (A0) only.
* **Post-hoc, after seeing results:** the arrival-rate table and the minute-j bar check (A5), the lookback-window comparison for premium breakouts (B6) and its decision-time version, added to rule out the algo's own fill printing the new high or low.
* **B1 buckets** were made mutually exclusive after the first figure showed shares adding to more than 1.
* **Secondary cell outcome** `y_loss` (a buy-back lot with decision ratio ≥1.2) added next to `y_bb` in B2.
* Events are grouped by lots flagged stop-loss, so counts differ slightly from `D0_COUNTER.md`.
