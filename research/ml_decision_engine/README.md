# ML decision engine

This extends the evidence at `dee2013` without changing any earlier reports,
selected models or numerical outputs. `protocol.json` is the frozen initial ML
protocol. All June-October observations have previously been inspected.

Run from the repository root on Linux with Python 3.11:

```bash
python -m pip install -r research/ml_decision_engine/requirements.txt
python -m pytest research/ml_decision_engine/test_engine.py -q
python -m research.ml_decision_engine.run --output /tmp/algo8-ml-results
```

The cloud workflow performs these steps and retains the complete result directory
as a downloadable artifact. The output option prevents mixing different runs.
Existing canonical market-cache preparation is redirected into this study's
disposable cache. Original raw files and outputs are hash-audited before/after.

Models predict **received execution actions in the next minute**. Controller
decision timestamps, unfilled requests and allocation IDs are unavailable. A
successful model would reconstruct an observable execution policy, not prove
original stop/target intent. Actions can coexist, so classifiers are multilabel.
Hold is the explicit negative label; long-wing sales never become short covers.

Every observed cycle-session receives a fixed one-minute opportunity grid,
including no-action, flat and post-close minutes. Contract candidates include
every contract with a completed preceding quote or an existing position. The
historically traded-only contract universe is a retrospective coverage limitation.
Eligible no-trade sessions outside the received-cycle sessions are unavailable.

The expansion folds train only on cycles ending strictly before the test block's
first session. Inner chronological cycles choose model thresholds, then refit.
Market features are compared with clock/inventory features on identical folds.
All regime quantiles, imputers, encoders and model transformations are fitted
within training data. No random row split, future close label or cycle ID is a
predictor. Causal direction/volatility variables remain distinct.

Metrics distinguish row classification, one-to-one timing matches, quantity and
inventory overlap. The target requires precision AND recall, coverage and support;
most-common Hold accuracy is never the target. Stop/target models are labelled
reduction-hazard surrogates because their causes are not observed. First-passage
diagnostics are fixed, not an expanded rule search. Missing marks and interval
timing ambiguity are preserved.

Autonomous replay uses its own book and confirmed simulated fills. Recorded
inventory is only a scoring target. Missing execution prices cause explicit
failures. One-minute timing, same-second ambiguity, approximate flat-ATM Greeks,
traded-only quotes, costs and residual liability marks remain disclosed.

See `ML_DECISION_ENGINE_RESEARCH_REPORT.md` in the run artifact for actual results,
module eligibility, unsupported tasks, false positives, missed events and all
sixteen research answers. An unrun source tree is not a completed study.
