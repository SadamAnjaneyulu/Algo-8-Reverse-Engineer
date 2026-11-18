# Historical backtest of the portfolio-construction engine

Start with `reports/EXECUTIVE_REPORT.md`. Then METHODOLOGY, NIFTY / SENSEX / COMBINED reports, COST_AND_STRESS, PARITY, LIMITATIONS_AND_CONCLUSIONS (all in `reports/`).

| Deliverable | File |
|---|---|
| Methodology, split dates, data exclusions | `reports/METHODOLOGY.md`, `results/data_coverage_and_exclusions.csv`, `results/cycle_feasibility.csv` |
| Frozen configuration and code commit | `FROZEN_CONFIG.json`, `PREREGISTRATION.md` |
| Trade ledger (every order and settlement, all runs) | `results/trade_ledger.csv` |
| Equity curves, drawdowns, monthly P&L | `reports/figures/`, `results/monthly_performance.csv` |
| Performance by period / index / configuration | `results/performance_summary.csv`, `results/is_grid_*.csv`, `results/is_selection.json` |
| Cost sensitivity and stress tests | `results/stress_tests.csv`, `reports/COST_AND_STRESS_REPORT.md` |
| Python / C++ parity | `reports/PARITY_REPORT.md` |

Reproduce (from this folder; needs the pinned dataset commit in the local git objects and a built `portfolio_engine/construction/build/pc_run`):
```
python3 -m bt.cycles                 # per-cycle cache from the dataset commit
python3 -m bt.select_config          # pre-registered in-sample grid, both exit variants, Python + C++ on every run
python3 -m bt.final_run oos && python3 -m bt.final_run tables && python3 -m bt.final_run stress   # only after FROZEN_CONFIG.json is committed
python3 -m bt.report_gen && python3 -m bt.make_reports
python3 -m pytest tests -q
```
Engine runs (`results/engine/`) and the cycle cache (`cache/`) are regenerable and git-ignored.
