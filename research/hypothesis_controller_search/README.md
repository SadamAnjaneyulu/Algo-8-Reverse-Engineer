# Constrained controller reconstruction

This module simulates complete candidates against stored market candles. It does
not give a candidate the historical inventory, entry fills or covers as inputs.
The observed sessions and historically traded contract universe remain explicit
restrictions; this is not an independent full-chain backtest or original source
code recovery. Read SEARCH_SPEC.md for the frozen grammar and scoring rules.

From the repository root (Python 3.12, g++ with C++17):

```bash
python -m pip install -r research/hypothesis_controller_search/requirements.txt
OPENBLAS_NUM_THREADS=1 python research/hypothesis_controller_search/prepare.py
OPENBLAS_NUM_THREADS=1 python research/hypothesis_controller_search/search.py --workers 4
OPENBLAS_NUM_THREADS=1 python research/hypothesis_controller_search/evaluate.py
OPENBLAS_NUM_THREADS=1 python research/hypothesis_controller_search/robustness.py
python research/hypothesis_controller_search/write_report.py
python -m unittest discover -s research/hypothesis_controller_search -p 'test_*.py'
```

`.cache/` contains disposable versioned binary arrays and the compiled kernel;
these can be rebuilt from hashed repository inputs. Research results live in
`outputs/`. Do not run two search writers concurrently. Search runtime depends
on CPU/CSV compression; the 13,824 main simulations take several minutes on four
workers, followed by result export, local refinements and robustness.

To replay a saved JSON or YAML definition without selecting new parameters:

```bash
python research/hypothesis_controller_search/search.py \
  --replay-config research/hypothesis_controller_search/outputs/best_candidate.yaml \
  --replay-output /tmp/algo8-saved-controller
```

This writes `/tmp/algo8-saved-controller_{actions,inventory,scores}.csv` and
preserves the saved candidate ID. Rebuild cache with `prepare.py` first.

`canonical_events.csv.gz` preserves child fills and observed seconds; the
canonical atomic books retain simultaneous net transitions. Candidate scoring
clusters executions by contract/minute/action, rather than pretending the data
identify exact submission times or original allocation ownership. Required
controller inputs are strictly previous completed candles. Missing inputs
abstain from the relevant signal and remain in reconstruction denominators.

Risk Greeks in simulated paths use an explicitly assumed flat ATM-IV surface;
canonical book Greeks are retained separately. Actual margin and account NAV
are absent. Candle opens and order-fragment costs are assumptions. Accounting
checks and software tests do not establish that a candidate is the original
controller or has a repeatable economic edge.
