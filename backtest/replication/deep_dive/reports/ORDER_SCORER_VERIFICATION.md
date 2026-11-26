# Order-level scorer: verification (spec v1.1)

*Implementation of `ORDER_LEVEL_SCORING_SPEC.md` v1.1 in `src/bl_oscore.py`; tests in `tests/test_order_scorer.py` (24). **The scorer has not been run on any real simulator output.** The freeze record keeps `first_scoring_run = null`. Everything below is software verification on synthetic data plus the legacy bridge on the stored replays.*

## Gate: the legacy F1 is reproduced (spec 11.1)
The **original** lot-matching code (identical in `validate_engine.py`, `bl_d0_fr_score.py` and `bl_fr_score.py`; class maps and tolerances parsed from those scripts' source, not retyped) re-run on the stored replays reproduces the published figures:
| | Real lots | Simulated lots | Matched | Precision | Recall | F1 | Published |
|---|--:|--:|--:|--:|--:|--:|--:|
| **D-1** (engine replay, 32 sessions) | 13,655 | 11,553 | 8,669 | 0.7504 | 0.6349 | **0.6878** | 0.688 |
| **D0** (out-of-fold, 30 cycles) | 40,874 | 40,024 | | 0.4147 | 0.4060 | **0.4103** | 0.410 |
All six D-1 class F1 values also match `bl_d1eng_scores.csv`. **No new-framework number is to be compared with the old ones until this gate passes; it passes.** (The bridge reproduces the old lot-level, +/-1-minute, class-based definition; the new order-level, second-tiered numbers are a different quantity and will not be equal to these.)

## What is implemented
Order-level one-to-one matching with mutually exclusive **Exact / Near / Broad** tiers (0, 1-5, 6-60 s; simulated second = floor(t)) and cumulative agreement at 0/5/60 s; keys cycle, day, option type, side; minimum-cost assignment with strike distance and lots as tie-breaks; **same-second ambiguity** flagging with both tie-break directions and a reported range; strike, quantity, order-type (reported "not available" when the simulator supplies no validity), key-level agreement, same-minute agreement, burst-level lots; precision / recall / F1 at five strictness levels and three cumulative tolerances; missing and extra orders by class, 30-minute block and cycle; **portfolio state after each matched event** plus 15-minute and end-of-day checkpoints; per-cycle distributions (median, IQR, p10, min, max, five worst named, counts below 0.5 and 0.3, macro mean) and cycle-cluster bootstrap CI; the **time-shift placebo** (named as such); breakdowns by class, underlying, version and era; a mandatory mode (F / T / TF-E) and evidence label (historical reproduction / out-of-fold / independent) validated on entry; the frozen-spec hash checked before every run.

## Tests (24)
Legacy bridge D-1 and D0 (gate); spec hash; one-to-one and partition identities; determinism and permutation invariance; exclusive tiers and cumulative shares; perfect reproduction gives every metric 1 (and zero missing/extra, state equal); a copy shifted by k seconds lands in the tier that contains k (k = 0, 1, 3, 5, 6, 30, 60) and beyond 60 s is unmatched; cumulativeness; the placebo lowers time-specific agreement; same-second ambiguity flagged with a tie-break range (and a clean case not flagged); state metrics on a hand-built day; type availability; mandatory mode and label; per-cycle distribution names the worst cycle; fractional-second handling (floor) at the 0/1/5/6/60/61 s boundaries; the one-to-one guard fires if the solver ever returns a duplicate.

## What the verification found
* **A real scorer bug, fixed:** with zero matches the pairs table had non-integer dtypes and the unmatched report crashed (caught by the beyond-60-s test).
* **Two gaps in my own tests, found by mutation checking and closed:** widening the exact tier to 1 s and removing the one-to-one guard were both undetected until the k = 1 case and the guard test were added. After that, mutations of the tier bounds, the exact tier, the one-to-one guard, the floor-versus-round rule and the legacy tolerance are all caught.
* **A flaw in a synthetic test, not in the scorer:** orders closer than 60 s let a shifted copy legitimately match a neighbour; the shift tests now use orders spaced at least 300 s apart.
* **Performance:** about 98 s for a full-size synthetic run (about 40,000 real and 34,000 simulated orders) including both tie-break directions, the placebo and the state metrics.

## Limits and what is not built
* The simulator still has no validity field, so order-type scoring will be "not available" until the engine's `orders_frame()` supplies it.
* **TF-E** (per-event teacher-forced) is specified and the scorer accepts the mode label, but producing TF-E simulator output (reset to the real book after every real order) is simulator work and is **not built**.
* The ambiguity rule uses the same-second-and-differing-(strike, lots) criterion plus disagreement between the two tie-break directions; a uniqueness test of the optimum is not computed separately.
* The D0 engine does not exist; D0 scoring will use the research simulator's output.
* The bridge confirms plumbing and the legacy definition, not the new definition's meaning on real data; that needs the first scoring run, which is waiting for your review of the implementation.
