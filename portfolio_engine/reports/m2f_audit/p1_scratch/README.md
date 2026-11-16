# Phase-One scratch tooling (as run on 2026-11-16) — kept for provenance, superseded by repo-native code

These are the exact scripts used for the first hybrid M2-D/M2-E comparison. They are **superseded** by `pe.scenario`, `tools/r1c_scenario_run.py` and `tools/r1c_inventory.py`
(see `reports/r1c_dual_scenario/N2_PROVENANCE_AND_RECONCILIATION.md`). Known limitations of this scratch method, found when the numbers were reconciled:
* `make_mirror.py` copied every tracked file into the mirror, so the delivered `m2c_figures` / `m2d_figures` files (11 files) were present although the chain never regenerated them; `diff_outputs.py` then reported them as identical. That inflated the "identical" count.
* The `scratch_diff_*_as_reported.json` files are the outputs of that method, unchanged. Do not quote their totals.
