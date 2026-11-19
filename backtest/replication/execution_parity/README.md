# Execution behavioural parity (Algo 8)

Start with `EXECUTIVE_SUMMARY.md`, then `PARITY_SCORECARD.md`. Direction from Rahul: validate execution behaviour; do **not** match Sharpe/Calmar/drawdown; do not treat three years as one regime.

| File | Content |
|---|---|
| `EXECUTIVE_SUMMARY.md` | what was tested, what matches, readiness decision, next data requirement |
| `PARITY_SCORECARD.md` | 21 rows (3 hard criteria + 18 behavioural parity components): MATCH / PARTIAL MATCH / MISMATCH / UNRESOLVED / NOT TESTABLE with all required fields (no overall percentage) |
| `EXECUTION_PARITY_METHODOLOGY.md` | pre-registered tolerances, classes, hypotheses, readiness rule (written before any result) |
| `UNRESOLVED_EXECUTION_RULES.md` | living register of unknown rules (U1-U14) |
| `DISCREPANCY_REGISTER.md` | every material difference with severity and root-cause status |
| `HISTORICAL_REGIME_ROBUSTNESS.md` | expiry-structure and regime segmentation, mechanics checks, brittle assumptions |
| `INDEPENDENT_REVIEW.md` | adversarial review findings, fixes and the contamination label |
| `NEXT_PHASE_ALPHA_READINESS.md` | what can be frozen, what cannot, prioritised data requests |
| `ALGO8_V1_BACKTEST_REPORT.md` | **Algo 8 decision engine v1** built from the 35 cycles (entry schedule, strikes, wings, per-lot/cycle stops, flatten) and its 2-year IS / 1-year OOS backtest, with fidelity vs the live cycles, tiers, structures, sensitivities and caveats |
| `config/algo8_v1_params.json` | decision parameters extracted from the 35 cycles (ledger hash, evidence labels) |
| `reports/REPOSITORY_AUDIT.md` | Phase 1 audit and gap analysis |
| `src/`, `tests/`, `outputs/` | code, tests, event-level tables |

## Reproduce (from this folder; needs the live ledger, the pinned dataset commit and the per-cycle cache of `replication/data.py`)
```
python3 src/check_equivalence_all.py      # core == legacy R1/R2 simulator on all live cycles
python3 src/run_mode3.py                  # Mode 3 accounting replay (4 allocation conventions)
python3 src/run_mode2.py                  # Mode 2 fully simulated: event agreement + inventory path
python3 src/run_mode1.py                  # Mode 1 component-isolated: strike, quantity, wings, cycle stop, flatten, carry
python3 src/run_mode1_leg.py              # Mode 1 per-lot stop grid (32 cells)   (~3 min)
python3 src/run_historical.py             # Phase 5 mechanics on 274 eligible historical cycles (~30 s)
python3 src/make_scorecard.py && python3 src/make_historical_md.py
python3 src/params_from_35.py && python3 src/run_v1_parity.py && python3 src/run_v1_backtest.py && python3 src/make_v1_report.py   # Algo 8 v1 + IS/OOS backtest (~5 min)
python3 -m pytest tests -q -p no:cacheprovider
```
Nothing here modifies `replication/sim.py`, the lot engine, the C++ engine, PR #13 outputs or the frozen alpha research. All results are **in-sample** (the 35 cycles are not a holdout). There is no CI workflow in the repository; "tests passed" means the commands above were run locally.
