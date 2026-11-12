# Stage 2: independent alpha research

Question: does repeatable, statistically defensible and economically meaningful predictive information exist in the
available market data? A negative answer is a valid result. This stage is independent of Algo 8's own trading logic.

**Status: Milestones 1 (data and leakage audit) and 2 (targets, baselines, validation design) complete. No model has been trained and no alpha family has been tested.**
Milestone 3 starts only after review and explicit authorisation.

| File | Content |
|---|---|
| [`DATA_AUDIT.md`](DATA_AUDIT.md) | Milestone 1 result: data quality, feature availability, leakage audit, dataset manifest (+ addendum: frozen closing minutes) |
| [`MILESTONE2_REPORT.md`](MILESTONE2_REPORT.md) | Milestone 2 result: locked targets and validation, five baselines, costs, limitations, open decisions |
| [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md) | Milestones, hypotheses, proposed targets and validation design, decisions needed |
| [`EXPERIMENT_REGISTER.csv`](EXPERIMENT_REGISTER.csv) | One row per experiment; nothing is deleted |
| [`configs/stage2.yaml`](configs/stage2.yaml) | Paths, session constants, candidate horizons, seed, excluded inputs |
| [`s2common.py`](s2common.py) | Loaders: raw market files only, no fallback to caches |
| [`targets/alignment.py`](targets/alignment.py), [`targets/targets.py`](targets/targets.py) | Label windows; locked target definitions |
| [`baselines/`](baselines/), [`validation/`](validation/) | Predictors and the five baselines; folds, purging, bootstrap, permutation, Holm/BH, cost scenarios |
| [`audit/data_leakage_audit.py`](audit/data_leakage_audit.py) | The reproducible audit → [`results/`](results/) |
| [`tests/`](tests/) | 16 data-integrity tests (Milestone 1) + 34 Milestone 2 tests |
| [`audit/closing_zone_check.py`](audit/closing_zone_check.py) | Frozen / missing closing minutes and their effect on the sensitivities |

## Reproduce

The raw Breeze 1-minute files are not in this branch. They are on branch `research/ml-decision-engine` under
`data/breeze/normalized`. Point the environment variable at that folder; the loaders raise if it is missing.

```bash
export ALGO8_MARKET_DIR=/path/to/data/breeze/normalized
```

```bash
python3 stage2_alpha_research/audit/data_leakage_audit.py --force
```

```bash
python3 stage2_alpha_research/baselines/run_baselines.py
python3 stage2_alpha_research/audit/closing_zone_check.py
```

```bash
python3 -m pytest stage2_alpha_research/tests ohlcv_research/tests -q
```

## Input rules

* **Authoritative:** raw index and option bars, raw broker fills, the PR #6 feature library (code, unchanged).
* **Never read:** PR #3 panels and lot caches, model stores, robustness results, PR #6 caches (they are only compared against).
* Algo 8's ledger is not an input to any Stage 2 feature. If a later experiment needs position data it must use
  `risk_rule_validation/rr_common.py::ledger` (session-aware) and be registered first.
* Generated tables go to `stage2_alpha_research/_cache/` (git-ignored); reports and CSVs to `results/`.
