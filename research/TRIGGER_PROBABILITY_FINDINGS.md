# Algo 8: probabilities for the leading trigger hypotheses

**Interpretation correction:** this historical probability study's “entry”
labels require a qualifying same-strike CE/PE pair. The later audit finds new
short selling in 18 of its 27 missing-pair windows; only nine are truly empty.
Thus 157/184 is paired-entry precision, not any-entry precision (175/184).
Some old off-quarter physical-minute events also fall within two seconds of
the next timer. The corrected definitions and new tests are in
[ALLOCATION_SIDE_FINDINGS.md](ALLOCATION_SIDE_FINDINGS.md). Keep the historical
tables below as paired-label results, not evidence of a range-filter rejection.

**Scheduled entry reconstruction meets an 80–90% point-estimate target. Extra
entries and the complete exit controller do not.** The probabilities below are
observed matching/event rates, not the probability that a particular indicator
was used in the original code, and not probabilities of profitable trades.

This follows the 15.9-million-comparison search. It adds four probability models
per task: regularized logistic regression, a constrained random forest, gradient
boosting and a readable depth-4 tree. Seven tasks require 84 whole-cycle fold
fits and 28 earlier-data refits, plus sigmoid calibration on earlier out-of-fold
scores. Model/threshold choices use expiries through 31 August; September–October
are chronological checks already examined in previous research. These are not
independent or previously untouched validation dates.

## The hypotheses with the strongest support

| Candidate rule | Later correct / signaled | Signals that were wrong | Actual additions explained |
| --- | ---: | ---: | ---: |
| Pre-expiry: use the 17 established timer windows, with an active short book | **238/238 = 100%** | 0 | **238/245 = 97.1%** of tested quarter-window additions |
| Expiry: at each tested quarter opportunity, add if the prior short book remains active | **157/184 = 85.3%** | 27 | **157/157 = 100%** |
| Expiry: active book AND net cycle P&L above −0.4% of stated capital | **155/180 = 86.1%** | 25 | **155/157 = 98.7%** |
| Expiry: earlier-selected calibrated tree/threshold for an 80% precision target | **147/167 = 88.0%** | 20 | **147/157 = 93.6%** |
| Expiry: earlier-selected forest/threshold for a 90% precision target | **98/104 = 94.2%** | 6 | **98/157 = 62.4%** |

These results concern **entry presence in execution windows**, not exact seconds,
strike selection or quantity. They do not explain all entry minutes, particularly
off-quarter sales. The 17-window subset is the established schedule, not an
additional timer discovered by the probability model. The tree's later matching
counts also confirm the earlier combined-search result rather than constitute
independent new evidence for its mechanism.

The high-precision forest illustrates why precision and coverage must both be
reported: its 94.2% signal success rate still misses 59/157 actual additions.
Pre-expiry's explicitly established clock rule beats the fitted probability
models on precision and covers most quarter-window additions.

The −0.4% gate is especially weak evidence of an original stop. Compared with
the active-book baseline it only filters **four** later opportunities, **two of
which actually contain additions**. It cannot be promoted to a decoded ₹80,000
stop. Its apparent usefulness on all windows partly reflects sessions whose
books are already inactive. The documented 1% capital instruction remains a
separate unresolved rule.

## What these probabilities mean

For the active-book expiry hypothesis:

```
P(recorded paired addition in the tested execution window |
  quarter-hour opportunity and actual prior short book active)
= 157 / 184 = 85.3%
```

There are no recorded additions in the 89 tested opportunities whose prior
short book is inactive. This supports a scheduled accumulation controller with
an active-cycle condition. It does not establish why a cycle becomes inactive,
why the 27 active opportunities are skipped or whether inventory itself is the
original input rather than another common internal flag.

Uncertainty is material. The 85.3% rate's descriptive Wilson interval is
79.5–89.7%. Resampling whole cycles gives about **69.2–94.7%**, reflecting only
nine later cycles with signaled active opportunities. The selected 88.0% tree
has a cycle-resampled interval of about **69.8–97.3%**. An 80–90% point estimate
is therefore not an established minimum reliability on future cycles.
The pre-expiry perfect observed schedule also cannot guarantee future attendance;
its Wilson lower bound is about 98.4% under independent-opportunity assumptions,
and its perfect-cycle bootstrap is degenerate. Cycles share calendar/market
conditions, so even cycle intervals are descriptive research uncertainty.

## Extra-entry and exit-start probability models

Extra sales are evaluated outside quarter windows (minute offsets 0, 1 and 2
are excluded), in the 09:30–14:43 study band. Cover onset opportunities require
an existing short book and **no cover fills in the preceding five minutes**.
This separates initiating a covering burst from recognizing its continuation.
It does not identify the reason for each cover.

The calibration policy requires at least 20 predicted examples across three
earlier cycles and empirical precision of 80% or 90%, maximizing event coverage
among eligible thresholds. None of the four model families qualifies for those
targets for:

- Pre-expiry extra entries: 93 later event minutes.
- Expiry extra entries: 172 later event minutes.
- Pre-expiry cover onsets: 92 later event minutes.
- Expiry cover onsets: 138 later event minutes.
- First full short closure within the next three minutes: 12 later cycles,
  33 positive at-risk minute opportunities.

This is a failure of the tested models under the support requirement, not proof
that no predictive rule exists. Abstaining creates no matches; it does not count
as a successful 80% rule. The first-closure study ends the observed risk set at
first closure and tests the first predicted alert, never replacing a wrong early
alert with a convenient later one. It is not a counterfactual portfolio replay.

Model scores are not automatically trustworthy probabilities. For example, the
boosted expiry-extra model's **score ≥0.8** cohort contains 19 later signals,
only **7 correct (36.8%)**, catching 7/172 events. Calibration on earlier data
does not prevent deterioration after schedules or market conditions change.
`prob_reliability_bins.csv` shows estimated versus observed rates for every model.

Readable trees also split on missing option OI, which often distinguishes NIFTY
from SENSEX because supplied SENSEX OI is all zero/unavailable. That is a data
availability/instrument proxy, not evidence that unavailable OI triggers trades.

## Named exit hypotheses and their matching probabilities

The following use the actual evolving book and first price-condition crossing,
with a fallback at 15:15 after 3 August / 15:25 earlier. The adjacent 15:14
variant is also exported. A match means within two minutes of the observed
closure, not a profitable exit or causal identification of the stop.

| Hypothetical exit controller | Later first full short closure | Later final full short closure |
| --- | ---: | ---: |
| Time cutoff alone | 6/12 = 50.0% | 6/12 = 50.0% |
| Net cycle loss 0.5% OR time | **8/12 = 66.7%** | **7/12 = 58.3%** |
| Net cycle loss 1% OR time | 6/12 = 50.0% | 6/12 = 50.0% |
| Short-book loss 1% OR time | 7/12 = 58.3% | 7/12 = 58.3% |
| Net loss from previous close 1% OR time | 7/12 = 58.3% | 6/12 = 50.0% |
| Open-short-credit loss 4% OR time | 7/12 = 58.3% | 7/12 = 58.3% |

The 66.7% match estimate has a wide Wilson interval, roughly 39.1–86.2%. Its
upper bound is not evidence that the rule attains 80–90%. The 4% row tests one
specific denominator, not every possible original carry-stop interpretation.
Early/late outcome strata are descriptive; using an observed late exit to select
a time-only rule would use hindsight.

The best simple net-loss hypothesis has four particularly useful counterexamples:

| Cycle | Model's first-closure prediction | Observed first closure | What must be explained |
| --- | --- | --- | --- |
| NIFTY 19 October | 15:15 | 09:26:22 | Early closure without a net-cycle 0.5% crossing |
| SENSEX 10 September | 15:15 | 13:37:29 | Closure without that aggregate-loss crossing |
| SENSEX 1 October | 10:05 | 15:14:41 | Loss crosses but the whole book does not close then |
| SENSEX 22 October | 12:55 | 15:14:44 | Loss crosses but the whole book does not close then |

Those observations prioritize an **allocation-specific or carry/fresh-position
controller** over a single pooled net-P&L stop. This is a research hypothesis,
not proof of its implementation. A first short-book closure is also distinct
from the first covering action; multiple reductions and re-entries can intervene.

## Next reconstruction target and economic alpha

Use the saved casebook to reconstruct allocation-level state: pair short CE/PE
parents, associate fresh/previously held protection, and retain alternative
associations where timing/quantities cannot identify a unique allocation. Test
carry versus fresh allocations and per-leg versus combined-premium stops against
the first cover of each episode. Track requested versus filled quantities and
pending orders separately from exposure. Then compare the same controller at
the suppressed and executed quarter windows.

The immediate counterexamples are the **27 suppressed active-book expiry
windows**, **265 later extra-entry minutes**, and the four exit failures above.
`prob_trigger_casebook.csv` contains 2,152 retrospective event/control rows with
past-known market/book features. Controls use the same underlying/phase, a clock
within 15 minutes and another cycle, prioritizing time and prior short size;
they are exploratory comparisons, not independent validation or causal matches.

Do not optimize solely for an 80–90% win rate. The previous cost-stressed basket
study has not established economic alpha. Once a controller explains both
positive and negative opportunities, evaluate its executable replay's net
expectancy, drawdown and tail losses at comparable risk, then test on new data.
Fitted order matching cannot supply those missing economic results.

## Reproduction and artifacts

```bash
python research/rank_trigger_probabilities.py
python research/rank_exit_hypotheses.py
python research/build_trigger_casebook.py
python -m unittest discover -s research -p 'test_*.py'
```

Dependencies are in `requirements-combinations.txt`; existing combined-study
features/ledgers are prerequisites. `prob_summary.json` saves selection and later
rates; `prob_hypothesis_evidence.csv` gives conditional counts and uncertainty;
`prob_model_evaluation.csv` includes false signals and event coverage;
`prob_reliability_bins.csv` audits probability scores. `prob_tree_programs.json`
stores earlier-fitted trees, imputation and sigmoid parameters, executable with
`predict_tree_probability()`; the script verifies those probabilities against
the fitted estimator on every later row. Adjacent readable branches are research
candidates. Exit predictions and priority counterexamples are saved separately.

All **133 repository tests pass**, including eight probability-specific checks
for precision versus coverage, support requirements, first-alert handling,
target exclusion and executable calibrated tree probabilities. `prob_audit.json`
records artifact hashes and verifies later-date membership, tree-probability
replay, casebook cutoffs and all 27 suppressed-window examples.
