# Stage 2: independent alpha research

Question: does repeatable, statistically defensible and economically meaningful predictive information exist in the
available market data? A negative answer is a valid result. This stage is independent of Algo 8's own trading logic.

**Status: Milestone 1 (data and leakage audit) complete. No model has been trained and no signal has been evaluated.**
Milestone 2 starts only after review.

| File | Content |
|---|---|
| [`DATA_AUDIT.md`](DATA_AUDIT.md) | Milestone 1 result: data quality, feature availability, leakage audit, dataset manifest |
| [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md) | Milestones, hypotheses, proposed targets and validation design, decisions needed |
| [`EXPERIMENT_REGISTER.csv`](EXPERIMENT_REGISTER.csv) | One row per experiment; nothing is deleted |
| [`configs/stage2.yaml`](configs/stage2.yaml) | Paths, session constants, candidate horizons, seed, excluded inputs |
| [`s2common.py`](s2common.py) | Loaders: raw market files only, no fallback to caches |
| [`targets/alignment.py`](targets/alignment.py) | Label-window definitions (no target evaluated yet) |
| [`audit/data_leakage_audit.py`](audit/data_leakage_audit.py) | The reproducible audit → [`results/`](results/) |
| [`tests/test_data_integrity.py`](tests/test_data_integrity.py) | 16 tests of the critical data-integrity assumptions |

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
python3 -m pytest stage2_alpha_research/tests ohlcv_research/tests -q
```

## Input rules

* **Authoritative:** raw index and option bars, raw broker fills, the PR #6 feature library (code, unchanged).
* **Never read:** PR #3 panels and lot caches, model stores, robustness results, PR #6 caches (they are only compared against).
* Algo 8's ledger is not an input to any Stage 2 feature. If a later experiment needs position data it must use
  `risk_rule_validation/rr_common.py::ledger` (session-aware) and be registered first.
* Generated tables go to `stage2_alpha_research/_cache/` (git-ignored); reports and CSVs to `results/`.
