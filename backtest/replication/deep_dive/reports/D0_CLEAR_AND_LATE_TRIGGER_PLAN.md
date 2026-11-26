# Late D-1 sale trigger (15:15–15:40) — pre-registered plan

*Written 2026-11-24 before the first late-trigger test ran. The D0 clearance test ran before this file (its criterion was stated in the chat at the start of the turn: decision metric = share of real covers done by the clearance minute; P&L last; stop flips separate). It is reported in `D0_CLEAR_AND_LATE_TRIGGER.md`.*

## Question
What triggers the real system's short sales after 15:15 on D-1? Not what it sells (strike and side are explained), but **in which minute, on which side**.

## Unit and target
* Row = (cycle, minute j in the window, side CE/PE). y = 1 if the real log has an `open_short` on that side in that minute (j = t_last // 60 − 555).
* Window: j = 360 … 384 (15:15–15:39) after 3 Aug 2026; j = 360 … 374 before it (index options stopped at 15:30).
* Cycles are kept whole. **Post-auction and pre-auction are analysed separately.** Primary sample: the complete real-log cycles, excluding NIFTY D-1 16 Oct 2026 (a 240-lot call-ratio event); reported with it too.
* Secondary target: y_any (either side), for side-neutral features.

## Competing underlyings (none preferred in advance)
FEED = published index (indicative auction values after 15:15), FUT = index future minus its 15:00–15:14 basis (`bt3u`), OPT = option-implied index (`bt3s`). Before the auction the published index is a valid price: FEED only. FROZEN is already falsified.

## Feature families (each is a ranking score; no fitted threshold)
| id | feature | variants |
|---|---|---|
| F1 | favourable move over the last k minutes, in strike steps (CE: fall, PE: rise) | k ∈ {1, 3, 5, 10} × 3 underlyings |
| F2 | fresh favourable extreme over G minutes (binary) | G ∈ {5, 15, 30, 60} × 3 |
| F3 | favourable excursion since the underlying close before the last real sale on that side (ladder logic, teacher-forced reference) | × 3 |
| F7 | absolute move over k minutes (side-neutral volatility trigger) | k ∈ {1, 3, 5, 10} × 3 |
| F4 | premium of the last-sold strike on that side now ÷ its last sale price (both signs) | 1 (options only) |
| F5 | book imbalance: short lots same side − other side (both signs) | 1 |
| F6a | clock: LOCO cross-cycle frequency of real sales at that minute | 1 |
| F6b | minutes since the previous real short sale (any side) | 1 |
Not testable: option volume (not in the cache). Family size ≈ 46 scores.

## Statistics
* **Stratified AUC:** Mann-Whitney within each (cycle, side) block, aggregated with n₁·n₀ weights. This removes cycle-level confounding.
* **Null:** permutation of y within block (counts preserved), 2,000 draws. Two-sided p-values with **Benjamini-Hochberg at 10%** over the whole family (all sub-tests counted, not only the best).
* **Uncertainty:** cycle-cluster bootstrap, 1,000 draws.
* **Underlying comparison:** paired bootstrap of ΔAUC between underlyings for the same feature.
* **Combination:** one logistic regression (L2, fixed strength), 3 features chosen by in-fold AUC, **nested leave-one-cycle-out**; report out-of-fold stratified AUC and CI against the clock baseline (F6a).

## Acceptance
A trigger is "found" only if out-of-fold AUC has a bootstrap CI above 0.5 and above the clock baseline, in the post-auction sample, **and** the same direction holds on the other side. Otherwise the answer is "not found" and no timing rule is added. P&L is not used.

## Stated limits in advance
About 20 post-auction cycles and ~100 positive (minute, side) events: the test can only detect strong effects. A null result is "not detectable here", not "no trigger".
