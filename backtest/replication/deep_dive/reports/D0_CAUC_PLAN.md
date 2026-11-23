# D0 counter-sells: the AUC gate — plan

*Written before the run. Same convention as the D-1 work (`D1_FULL_AUC.md`): AUC on minute cells (cycle × minute × right), leave-one-cycle-out, 95% cycle-bootstrap CIs. Gate set by the user: **AUC at least 0.85** before moving on from counter-sells.*

## What is scored
* **Cell:** (cycle, minute j, right R′), D0, from 09:19 to the minute before the cycle's first stop-module order (or 15:10). Same panel as `D0_CTRIG.md` (14,762 cells, 24 cycles).
* **Outcome (primary): counter-sell cell** = at least one **counter-labelled** solo sale (the `D0_SELL_TYPES.md` label: a solo sale of R′ with a buy-back of the other right within ±60 s) in the cell.
* **Reference outcomes:** any solo sale in the cell (`D0_CTRIG.md`: 0.876); counter-labelled vs other solo sales (0.62).

## Three variants (reported separately, never merged)
* **V1 causal:** bars up to j−1 and orders strictly before minute j (spot, premium, book, past buy-backs, premium-low windows, ladder state). *This is the variant the gate is judged on.*
* **V2 + the minute's own bar** (spot and the sold option's bar j). Not knowable ahead; shows how much sits inside the minute.
* **V3 + buy-backs of the other right in the same minute.** The counter label itself is defined by such a buy-back, so V3 is **partly definitional** and is shown only to separate "where solo sales happen" from "where they happen next to a buy-back".

## Metrics
* Pooled LOCO AUC and PR-AUC with cycle-bootstrap CI (as in D-1).
* **Within-cycle AUC** (mean over cycles with at least 5 positives): removes the cycle-level base-rate effect that pooled AUC rewards (the cycle-shuffled placebo scored 0.685 in `D0_CTRIG.md`).
* Cycle-shuffled placebo; forward check (first 16 cycles by expiry → last 8).
* Fixed HistGradientBoosting settings as before (200 iterations, depth 3, learning rate 0.05, minimum leaf 50, L2 1.0). No tuning on test cycles.

## Acceptance
* **Gate met** if V1 pooled LOCO AUC ≥ 0.85 **and** its forward check ≥ 0.80.
* Always reported next to the gate: within-cycle AUC and the placebo. If the pooled AUC passes but the within-cycle AUC does not, that is stated: the ranking is partly cycle level.
* **A pass is a ranking statement** (which minutes will carry a counter-sell), not a recovered rule; exact-cell F1 of rules stays at `D0_CTRIG.md` (below 0.5).

## Not testable here
The order of events inside a second; tick prices.
