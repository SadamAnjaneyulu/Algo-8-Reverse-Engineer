# Implementation plan

| Milestone | Scope | Exit criterion | Status |
|---|---|---|---|
| M0 | audit, architecture, plan, dependency audit, component inventory, schemas, risk register | documents exist and match the repo | this commit |
| M1 | shared schemas, Python + C++ event model and replay, deterministic ordering, snapshots, accounting invariants, mode isolation, synthetic fixtures, real-data replay, parity, reconciliation to TP-01 | all tests executed; parity dumps identical; TP-01 totals/episodes/roles reproduced | in progress → report |
| M2 | Position manager (lifecycle query), Basket manager, membership provenance, grouping conventions | basket/portfolio totals reconcile to positions | planned |
| M3 | plugin interfaces + registry + no-op/default/synthetic plugins; generators framework | plugins cannot mutate state (tested) | planned |
| M4 | basket cut (full/partial/side/position/wing-aware) and re-entry; execution states; reconciliation after every fill | synthetic 195/195 scenario + historical basket replay | planned |
| M5 | 27 required charts with data export and mode stamps | charts from real or explicitly synthetic data | planned |
| M6 | one historical cycle end to end | parity + reconciliation + charts | planned |

Rules kept in every milestone: stage only listed files; no `git add .`; never write to `tp_reconstruction/`, `Trades_GKOHNP140.csv` or other research outputs; do not touch PRs #8–#12; no TP-03 experiment; `stage2_alpha_research/` untouched; draft PR only after M1 tests pass and only on this branch.

## Directory structure
```
portfolio_engine/
  ARCHITECTURE_DESIGN.md  IMPLEMENTATION_PLAN.md  README.md
  docs/        SCHEMAS.md  EVIDENCE_REGISTRY.md  DEPENDENCY_AUDIT.md  REUSABLE_COMPONENTS.md  RISK_LIMITATION_REGISTER.md
  python/pe/   schema.py events.py ledger.py snapshot.py invariants.py replay.py provenance.py tsvio.py cli.py generators/
  cpp/         CMakeLists.txt include/pe/*.hpp src/pe_replay.cpp tests/
  fixtures/    synthetic event files (generated, seeded, committed)
  tests/       python tests incl. parity and TP-01 reconciliation
  tools/       build + parity scripts
  runs/        (git-ignored) outputs by execution mode
```
