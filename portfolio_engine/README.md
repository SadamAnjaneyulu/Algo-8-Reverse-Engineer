# portfolio_engine

Modular portfolio-construction research engine (Python research layer + C++ deterministic core) for the Algo 8 reverse-engineering project.
Design: [`ARCHITECTURE_DESIGN.md`](ARCHITECTURE_DESIGN.md) · plan: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) · schemas: [`docs/SCHEMAS.md`](docs/SCHEMAS.md) · evidence: [`docs/EVIDENCE_REGISTRY.md`](docs/EVIDENCE_REGISTRY.md) · Milestone 1 report: [`reports/M1_REPORT.md`](reports/M1_REPORT.md)

**Status: Milestone 1 (shared model, deterministic replay, accounting invariants, Python/C++ parity) only. No entry/exit/basket behavior is implemented.**

```bash
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
