# algo8_cpp — Algo 8 complete algorithm in C++17

Full implementation of the reconstructed Algo 8 weekly option-selling cycle (NIFTY / SENSEX): **D-1 engine → carried book → D0 engine**, with the **Rs 2,00,000 cumulative cycle hard stop**, order/risk handling, cost model and a multi-threaded backtest runner with metrics.

**Start with `docs/ALGO8_COMPLETE_ALGORITHM.md` (or the PDF next to it): the full algorithm, findings and metrics.**

## Build (g++ ≥ 9 or clang, C++17, pthreads; no other dependencies)
```bash
cmake -S . -B build && cmake --build build -j       # or:  make
ctest --test-dir build                               # or:  make test
```
Tests: `test_util` (numeric helpers against NumPy/CPython reference values) and `parity` (10 shipped cycles, including cycles stopped on D-1 and on D0, against the Python reference ledger, tolerance Rs 0.001).

## Run
```bash
build/algo8_backtest --cycles data/sample/cycles.csv --data data/sample \
     --waves data/frozen_d0_waves.csv --stop 200000 --out out --threads 4
```
| Option | Meaning |
|---|---|
| `--cycles` | CSV `und,expiry,d1,d0,lot` (one row per weekly cycle; `lot` = units per lot of that session) |
| `--data DIR` | folder with `<UND>_<expiry>_<day>.a8s` session files (format below) |
| `--waves` | frozen D0 timetable (`und,version,t,lots`) |
| `--stop RUPEES` | cumulative cycle hard stop; `0` disables it (default in the documented results: 200000) |
| `--cost-mult X`, `--slip-mult X` | scale costs / slippage (sensitivity runs) |
| `--out DIR` | writes `ledger.csv` (per cycle) and `metrics.csv` (win rate, Sharpe, Sortino, max drawdown, profit factor … for ALL / NIFTY / SENSEX × ALL_PERIODS / PRE / DEV / POST / USER_IS / USER_OOS) |

## Session file format `A8S1` (little-endian)
`"A8S1"`, `int32 nK`, `int32 n=375`, `float64 K[nK]`, spot `open,high,low,close` (4 × `float64[375]`), then for CE and PE (in that order) `open,high,low,close` each `float64[nK × 375]` (strike-major). Missing candles are NaN. `tools/export_sessions.py` writes this format from the research dataset (it needs the dataset in the repository checkout; the shipped sample is already exported).

## Layout
```
include/algo8/   util.hpp (Python-exact numerics)  session.hpp  d1_engine.hpp  d0_engine.hpp  backtest.hpp
src/             d1_engine.cpp  d0_engine.cpp  backtest.cpp  main_backtest.cpp
tools/           export_sessions.py  sweep_parity.py  dump_cycle.cpp / .py
tests/           test_util.cpp  run_parity.sh  compare_ledgers.py
data/            frozen_d0_waves.csv  sample/ (10 cycles + expected_ledger_S200.csv)
docs/            ALGO8_COMPLETE_ALGORITHM.md / .pdf, figures/, results/ (all result tables)
reference_python/  Python reference engines the C++ was ported from and checked against
```

## Exactness
Results equal the Python reference to the last digit that matters: 825 of 825 runs (275 cycles × 3 stop settings) have identical order counts, fills, stop flags and stop minutes, net P&L within Rs 0.0005 (`docs/results/parity_sweep.json`). This relies on `-ffp-contract=off` and **no fast-math** (already set in `CMakeLists.txt` / `Makefile`); keep those flags.

## Using the engines in your own program
`D1Engine(cfg, session).run()` replays a D-1 session second by second and returns the fills and the carried book; `D0Engine(cfg, session, unit, step, opening).run()` continues from the carried book at one-minute resolution; `run_cycle()` in `backtest.cpp` shows the whole chain (handoff, hard stop, accounting). `d1_config_for(und, d1_date, lot, has_stop, stop_rupees)` builds the D-1 configuration for a date. For live use, drive the same decision functions from a live feed and broker adapter (the Python `d1_algo` package in `reference_python/` shows the event-driven loop, risk guard, state file and broker interface).
