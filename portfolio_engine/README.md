# portfolio_engine

Modular portfolio-construction research engine (Python research layer + C++ deterministic core) for the Algo 8 reverse-engineering project.
Design: [`ARCHITECTURE_DESIGN.md`](ARCHITECTURE_DESIGN.md) · plan: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) · schemas: [`docs/SCHEMAS.md`](docs/SCHEMAS.md) · evidence: [`docs/EVIDENCE_REGISTRY.md`](docs/EVIDENCE_REGISTRY.md) · Milestone 1 report: [`reports/M1_REPORT.md`](reports/M1_REPORT.md)

**Status (2026-11-16): Milestone 1 (shared model, deterministic replay, accounting invariants, Python/C++ parity) is complete. Milestone 2 (historical position reconstruction M2-A..M2-F, fill-order policies R1, dual-scenario decision R1-C) is IMPLEMENTED, independently audited (M2-F: CONDITIONAL PASS) and CLOSED OUT (`reports/M2_CLOSURE_FINAL_REPORT.md`: proposed final decision CONDITIONAL PASS) but NOT YET ACCEPTED: it awaits the owner's approval (see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md), "M2 closure status"). M3-M6 are not started. No entry/exit/basket *behaviour* (cuts, re-entry, execution states, plugins) is implemented; M2 produces analytical views only.**

Baseline fill-order convention: `SOURCE_ROW_ORDER_CONVENTION` (deterministic, not verified chronology). Alternative scenario: `PER_CONTRACT_ID_SEQUENCE` ([`reports/R1C_DUAL_SCENARIO_COMPARISON.md`](reports/R1C_DUAL_SCENARIO_COMPARISON.md), [`docs/ORDERING_SEMANTICS.md`](docs/ORDERING_SEMANTICS.md)). Historical outputs: `reports/m2c_data`, `m2d_data`, `m2e_data`, figures `m2c_figures`, `m2d_figures`, `m2e_figures`; audit: [`reports/M2F_FINAL_AUDIT_REPORT.md`](reports/M2F_FINAL_AUDIT_REPORT.md); fill-order evidence: [`reports/R1_TIE_ORDER_CONVENTION.md`](reports/R1_TIE_ORDER_CONVENTION.md).

```bash
# reproduce the historical outputs of a scenario into an EMPTY directory (never into reports/): baseline reproduces the delivered files
python3 portfolio_engine/tools/r1c_scenario_run.py --scenario=baseline --out-root=/tmp/baseline_out
python3 portfolio_engine/tools/r1c_scenario_run.py --scenario=per_contract_id_sequence --out-root=/tmp/hybrid_out
# build the C++ core and its unit tests
cmake -S portfolio_engine/cpp -B portfolio_engine/build -DCMAKE_BUILD_TYPE=Release && cmake --build portfolio_engine/build
portfolio_engine/build/pe_core_tests
# regenerate fixtures (read-only access to tp_reconstruction/)
python3 portfolio_engine/tools/make_fixtures.py
# all Python tests (accounting, TP-01 reconciliation on the real ledger, Python/C++ parity)
python3 -m pytest portfolio_engine/tests -q
# parity report incl. the full 41,421-fill ledger (needs data_generated/, see below)
python3 portfolio_engine/tools/parity.py --real-full
# one replay with a manifest (mode-separated output directory)
cd portfolio_engine/python && python3 -m pe.cli replay --events ../data_generated/historical_events.tsv --instruments ../data_generated/historical_instruments.tsv \
   --mode HISTORICAL_OBSERVED_REPLAY --method FIFO --tie src --snapshot-interval 5000 --engine cpp --out-dir ../runs
```
`data_generated/` (git-ignored) is produced by `python3 -c "import sys; sys.path.insert(0,'portfolio_engine/python'); from pe.generators import historical as H; H.write('.', 'portfolio_engine/data_generated')"`.
Execution modes never share a directory: `runs/<MODE>/<run_id>/`.
