# D0 selling: one reconstruction of every selling type, scored on unseen cycles — plan

*Written before the run. In-sample discovery, **but every number reported comes from cycles the model never saw**: all learned parts (the clock timetables, the gradient-boosting model) are fitted on training cycles only. Target set by the user: **AUC at least 0.85 for the whole of D0 selling and for each selling type, and about the same (0.85–0.90) on unseen cycles.** Builds on `D0_SELL_TYPES.md`, `D0_CTRIG.md`, `D0_CAUC.md`, `D0_REPL.md`.*

## What is reconstructed
* **Cells:** (cycle, minute j, right), D0, from **09:15** to the minute before the cycle's first stop-module order (or 15:10), for every cycle with D0 sells (29). The opening minute (09:15) is included; its features are only the gap, the carried book and the clock.
* **Selling types (13):** scheduled pair, opening pair, re-centre pair, breakout pair, other pair; **strangle pair** (the SENSEX-before-16-Sep timetable of `D0_REPL.md`); opening solo, counter-sell solo, replacement solo, extreme solo, late solo, far-OTM solo, other solo. Each order has exactly one type, by the precedence of `D0_SELL_TYPES.md` with the strangle legs and the far-OTM type taken out of the solo chain first (as in `D0_REPL.md`). Outcome for a type = at least one lot of that type in the cell. **"Any D0 sell"** = at least one body sell lot in the cell.

## The model (the same for every type)
* **Causal market and book features** (V1 of `D0_CAUC.md`: bars to j−1, orders before minute j; spot, premium, book, past buy-backs, premium-low windows) plus the **overnight gap in the direction that favours the right's short** and the carried book.
* **Learned clock features:** for each of four kinds of sale (any sale, any pair, strangle, solo) the share of the *reference cycles* of the same underlying × version that sold in that minute on that right. Reference cycles are **training cycles only**; a training cell never uses its own cycle. This is the timetable a new cycle would inherit from old ones.
* Fixed HistGradientBoosting settings (200 iterations, depth 3, learning rate 0.05, minimum leaf 50, L2 1.0); one model per outcome. No tuning on test cycles.

## Four ways of running on unseen cycles
1. **S1 leave-one-cycle-out:** each cycle is predicted by a model that never saw it (29 folds).
2. **S2 forward in time:** first two thirds of the cycles by expiry → last third.
3. **S3 version change:** train on cycles before 16 Sep, test on cycles from 16 Sep (a new timetable version; expected to be harder).
4. **S4 random halves:** 30 random 50/50 splits of the cycles; mean and standard deviation of the test AUC.

## Metrics and acceptance
* Pooled AUC with cycle-bootstrap CI, within-cycle AUC (cycles with at least 5 positives), PR-AUC, per-cycle spread (minimum, median), cycle-shuffled placebo for "any sell".
* **Type assignment:** among cells with a sale, the type with the most lots is the true type; the predicted type is the one-vs-rest model with the highest probability. Top-1 accuracy and per-type recall (S1).
* **Accepted** if "any D0 sell" and every type with at least 150 positive cells reach AUC ≥ 0.85 under S1, S2 and the mean of S4. S3 is reported and not part of the acceptance. Types below 150 cells are reported and flagged "indicative".
* A pass is a ranking of minutes and a type label for them, **not** a rule that reproduces lots, strikes or seconds (those are in `D0_FREE_RUN.md`).

## Not testable here
Genuinely new cycles: all 29 were used to find the structure (types, strangle, features). The unseen-cycle numbers protect against fitting, not against the structure having been chosen after seeing all of them.

## Addendum — written after seeing results (post-hoc, labelled in the report)
1. **S2 was badly designed.** "First two thirds → last third by expiry" puts every cycle of the new timetable version in the test set, so S2 is identical to S3 (version change). **S2b** (first two thirds → last third *inside each timetable version*) is the forward test that matches the plan's intent, and S2 and S3 are kept only to show the version-change case. **S3b** (version change after adding the first three cycles of the new version) was added to show how fast the model recovers. The acceptance rule is read with S2b in place of S2.
2. **Two feature variants** are reported for every scheme: *causal* (bars to j−1, orders before minute j; the acceptance variant) and *plus the minute's own bar and same-minute buy-backs* (the D-1 "A" convention; partly definitional for types whose label is a buy-back within 60 s).
3. **Breakout-machine features** (a two-candle breakout fired in the previous one or two minutes, minutes since the last fire) were added after the first run showed breakout pairs at 0.77; they lifted it to 0.80.
4. **A group "event pairs"** (re-centre + breakout + other pair), because those three types are small and unstable on their own. It is reported next to them, not instead of them.
5. A first full run was started with all four worker processes using all cores each and never finished; it was stopped and rerun with one thread per worker. No result was taken from the stopped run.
