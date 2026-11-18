# market_data: NIFTY options history acquisition

* `audit/audit_existing.py`: independent audit of the existing Breeze files (`reports/existing_audit/`).
* `acquisition/`: resumable downloader (planner, runner, client, store, normalizer, QC). Standard library plus pandas for QC.
* `tests/`: 16 offline tests against a fake Breeze (`python3 -m pytest tests -q`).
* `config/validation_split.json`: proposed in-sample / out-of-sample dates and walk-forward folds.
* `reports/DATA_ACQUISITION_REPORT.md`: the full report, evidence labels and the run order.

Credentials: environment variables or hidden prompts only; nothing is written to disk. Data lives in `data_store/` (git-ignored).
