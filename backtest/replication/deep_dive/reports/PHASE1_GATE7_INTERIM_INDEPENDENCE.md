# Phase 1, Gate 7 (interim, D-1 only): independence and robustness status

*2026-11-25. **Interim:** Gate 7 formally follows Gates 5 and 6 and is not closed here. This records what is already determinable for the D-1 reconstruction. Nothing committed.*

| Question | Answer |
|---|---|
| Which data developed the rules? | all 32 D-1 cycles of the real log (22/23 Jun - 22 Oct 2026) and the three-year market cache; the structure was designed after viewing all 32 cycles |
| Which data validated them? | **the same cycles.** Every figure in Gates 0-4 is **historical reproduction**. "Unseen" splits in earlier work (even/odd halves, forward A/B, 16 Sep - 22 Oct) are inside the same log; the 16 Sep - 22 Oct cycles are contaminated as validation data |
| Independent validation? | **None exists.** No orders after 22 Oct 2026, no decision logs, no ticks. Independent validation is **outstanding**, not failed |
| Leave-one-cycle-out | applied to every constant fitted in Phase 1 (strike fraction S5, stop ratio K2/K4/K5, lump constants, variant selection in 2A, 2D, K6): chosen values were stable (e.g. stop ratio 1.6 in 32 of 32 folds; late/solo variants V01 in 32 of 32) and **none improved on the baseline**; earlier-fitted constants (timetables, ladder step 0.2, gate 60, stop 1.6, pair sizing, lump ratios) were **not refitted** and remain in-sample |
| Parameter stability | the baseline constants were re-tested against alternatives (gate 5/15, step 0.1/0.05, stop 1.4-1.8, delay 10-60 s) and the baseline was never beaten under the registered criteria: stable, but that also means the constants are not shown to be anything beyond locally optimal on these cycles |
| Overfitting / hindsight | the engine's rule structure and constants were set with the 32 cycles in view (hindsight); the Phase 1 selection risk is counted per gate (about 19 engine runs (16 candidates and 3 baseline-reproduction checks), 10 strike rules, and about 16 stop, wing and lump rules); the rejected variants show no search-based gain, but absolute accuracy figures are optimistic for new data |
| Missing original data preventing independent confirmation | decision or signal logs and configuration; tick or one-second data; margin and capital records; order lifecycle data; trade exports after 22 Oct 2026 |
| Leakage checks | rebased futures feed uses minutes <= 359 for the basis (tested); TF-E applies real orders only strictly before the decision second (tested); strike evaluations use information strictly before each order; no P&L in any selection |
**Status:** interim **CONDITIONAL**: reproducible, limitations explicit, **no in-sample result is presented as independent validation**. An independent hold-out (new real cycles or a forward log from the shadow recorder) would be the only route to a PASS; per the instruction, it is not made a dependency.
