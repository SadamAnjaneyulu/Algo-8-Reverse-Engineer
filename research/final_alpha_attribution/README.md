# Final economic attribution and research closure

Start with `FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md` and `final_verdict.json`.
The conclusion is B: positive quoted results under some assumptions, without
established economic alpha. Original strategy reconstruction is a separate,
unresolved question. This study does not authorize another search phase.

Recreate the audit and all tables from the saved canonical inputs, from the
repository root (Python 3.12; existing research environment):

```bash
python -m pip install -r research/final_alpha_attribution/requirements.txt
OPENBLAS_NUM_THREADS=1 python research/final_alpha_attribution/run.py
```

The script runs, in order:

1. `audit.py`: independent Decimal positions/cash/realised accounting, raw quote
   marks and quality audit; fills `.cache/` from existing stored market files.
2. `economics.py`: direct role and phase P&L, costs, residual sensitivities,
   sampled exposure/drawdown, protection and management ledgers.
3. `benchmarks.py`: fixed opening-only / scheduled / common-clock comparisons.
4. `attribution.py`: own-option IV and symmetric Shapley estimates with residuals.
5. `summarize.py`: cost/cohort/index/phase statistics, paired/LOO evidence, verdict.
6. `report.py`: evidence-linked report plus standalone PNG/SVG figure.
7. `validate.py`: numeric reproduction, immutable input checks and full test suite.

No broker access, credentials, downloads or original-file writes are required.
The prior full test suite also needs its existing C++17 compiler/dependencies.
This folder's new economic analysis is Python only. `.cache/` is disposable and
ignored. Prior Strong Findings v6 is read at frozen git revision `f5b4ab8`; a normal
clone fetching both research branches retains that revision.

`REGISTERED_PLAN.md` freezes the hypotheses, costs, cohorts and comparisons.
`BENCHMARK_AND_MODEL_CLARIFICATIONS.md` resolves clock/parent/model implementation
choices before comparisons. Numeric outputs distinguish recorded prices, quoted
residuals and hypothetical benchmark closes. Every figure is marked P&L, not NAV.
Cycle/role, phase and modeled decompositions are alternative cuts of one economic
result and must never be added together. Local markouts are not a deployable
no-management strategy or additive profits. No account Sharpe/CAGR is computed.

The required top-level CSVs contain per-cycle results and cohort summaries.
Supplementary ledgers preserve source IDs, residuals, model fits/failures, missing
benchmark allocations, exposure differences and all counterexamples. Whole-cycle
bootstrap intervals use fixed seeds. All dates were previously inspected; no
internal chronology creates independent external validation.

`negative_call_tail_atomic_seconds` counts distinct received event timestamps
with a negative call tail, not elapsed exposure duration. Short-unit-minutes use
the sampled minute grid; FIFO/LIFO holding ages include calendar gaps.
