# Algo 8 — Performance diagnostics

Diagnostic investigation of the weak out-of-sample Sharpe. **No optimisation; the frozen baseline is unchanged; original results are not overwritten.**
Start with `reports/PERFORMANCE_DIAGNOSTIC_REPORT.md` (executive summary, failure mechanisms, ranked priorities).
Reproduce: `bash backtest/diagnostics/run_all.sh` (needs `backtest/cache/` and `backtest/results/engine/`, both local/git-ignored). Tables are in `results/`, charts in `reports/figures/`.
Test: `python -m pytest backtest/tests/test_diagnostics.py -q`.
