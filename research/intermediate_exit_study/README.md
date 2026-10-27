# Intermediate exit controller event study

This adds one finite, registered study to the existing research. It does not
change the original 59 motifs, prior outputs or selected model-28 configuration.
It uses conditional historical-inventory discrimination, not autonomous replay.

From the repository root, with the existing research Python dependencies:

```bash
OPENBLAS_NUM_THREADS=1 python research/intermediate_exit_study/build.py
OPENBLAS_NUM_THREADS=1 python research/intermediate_exit_study/evaluate.py
python research/intermediate_exit_study/report.py
python -m unittest research.intermediate_exit_study.test_intermediate_exits
python research/intermediate_exit_study/validate.py
```

The existing `research/hypothesis_controller_search` requirements and disposable
market cache are reused. A missing cache can be rebuilt through the previous
module's read-only input adapter. No broker calls, authentication or downloads
are needed. Code never overwrites prior result files.

Start with `REGISTERED_PLAN.md` for the frozen 12 rules and outcome/control
protocol, then `INTERMEDIATE_EXIT_CONTROLLER.md` for results and limitations.
`exit_case_ledger.csv.gz` is the reduction-episode ledger, while atom/child maps
retain every observed Buy closing fill. `pre_event_risk_set.csv.gz` is the full
conditional scoring risk set; matched controls are explanatory only and do not
replace the denominator for precision. Whole-cycle validation folds and fitted
baseline parameters are explicit. All dates were already researched: neither
LOCO nor chronology creates a researcher-blind external sample.
