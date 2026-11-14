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


## Milestone 2 breakdown
| Step | Scope | Gate |
|---|---|---|
| M2-A | ontology, lineage rules, grouping methodology, schema additions, branch reconciliation, decisions to approve | **review before any code** (this commit) |
| M2-B | OA/CP/CA/slice/lifecycle in Python + C++, FIFO/LIFO/AVG, reversal handling, position query, I1–I7, I10–I11, parity | accounting tests + byte parity |
| M2-C | Model A (both languages), Models B and C (Python), reconciliation I8/I9 | partition tests |
| M2-D | wing/body methods W1–W5, unmatched/ambiguous quantification | uncertainty retained |
| M2-E | forensics on one NIFTY and one SENSEX cycle, six chart families with saved data | charts reproduce from CSV |
| M2-F | independent adversarial audit, regression counterexamples, final reports | PASS / PARTIAL |
Not in M2: cut/re-entry policies, alpha, new dependencies.


### M2 status
M2-A approved (D1–D7). Demonstration cycles frozen: NIFTY 2026-06-30, SENSEX 2026-07-16. **M2-B complete and independently reviewed (`reports/M2B_REPORT.md`): PASS.** M2-C (Models A/B/C) awaits authorization; the number-block semantics need a decision first.

M2-C (closing batches) executed for C1 and C2; number-block variant audited and left `UNRESOLVED — REVIEW REQUIRED`. Stopped for review; Models A and B, wing/body and later stages are not started.

M2-D (wing/body associations) executed and independently reviewed (`reports/M2D_WING_BODY_REPORT.md`). Stopped for review; M2-E and M3 not started.

M2-E (historical position forensics and portfolio visualization) executed for the two frozen cycles and independently reviewed in two rounds (`reports/M2E_HISTORICAL_FORENSICS_REPORT.md`; gate 10/10 PASS with disclosed limitations: historical option marks absent in this environment, expired-unclosed case UNAVAILABLE in both cycles, reversal UNAVAILABLE for SENSEX). Assembled datasets `reports/m2e_data/`, figures V1–V6 `reports/m2e_figures/`, case studies, coverage report and visualization catalog delivered; no new grouping, no change to W1/W2/W3, no accounting change. Stopped for review; M3 not started.
