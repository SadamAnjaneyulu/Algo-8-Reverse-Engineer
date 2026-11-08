# Algo 8 — Reconstruction Roadmap

Part of the [complete reconstruction audit](ALGO8_COMPLETE_RECONSTRUCTION_AUDIT.md) ·
[findings register](ALGO8_MASTER_FINDINGS_REGISTER.md) · [strategy specification](ALGO8_STRATEGY_SPECIFICATION.md) ·
[readiness](ALGO8_RECONSTRUCTION_READINESS.md) · [data gaps](ALGO8_DATA_GAPS_AND_REQUIREMENTS.md)

Priority is set by **how much a task reduces uncertainty about the original strategy**, not by ease. "Lineage X" =
`data/local-breeze-fetch` → `research/strong-findings` → `research/ml-decision-engine` (PR #1). "Lineage Y" =
`claude/friendly-galileo-r3zezw` (PR #2) → `research/algo8-exit-engine` (PR #3).

## 1. Completed and validated

| Item | Evidence | Branch |
|---|---|---|
| Order identity (col 163) and reconstruction; lineage X's parent ledger | DAT-01, DAT-09 | both |
| Recovered decision quote (limit band); module tags; AlgoId meaning | DAT-05–DAT-07 | Y |
| Opening structure (09:16, ATM, four roles, 195/60, seed wings) | ENT-01, STK-01, SIZ-02, HDG-01 | X (Y agrees) |
| 17 pre-expiry windows; accumulation without re-centring | ENT-02, MGT-01 | X (Y agrees) |
| Child-order base unit 65 / 20 | SIZ-01 | X |
| No classical indicator identifiable | STR-03 | Y |
| No demonstrated economic alpha (both lineages) | ALP-01 | X, Y |
| Legacy order-id impact audit (six scripts) | DAT-03 | Y (audit) |

## 2. Completed but requiring corrected-data revalidation

| Item | Why | Depends on | Branch | New data? | Acceptance criterion | Decision it enables |
|---|---|---|---|---|---|---|
| Exit-engine sections 1–3 numbers in `EXIT_ENGINE_FINDINGS.md` and the PR #3 description | Built on the reused order key with swapped side/basket labels (DAT-04) | Clean rebuild (`run_all.py`); section 3 re-run in progress | Y (PR #3) | No | Section 3 re-run finishes; findings doc and PR description rewritten with clean numbers | Whether any section-3 claim survives |
| P4 strike-choice model (68.5 %) | Reused key in an un-re-runnable chain (DAT-03) | Writer of `p4_orders_feat/prem/cons` caches (not in repo) | Y (PR #2) | No | Re-run with col-163 key; report the new top-1 vs nearest-ATM | Whether STK-03 becomes STRONG or is retracted |
| `FINDINGS.md` per-lot stop statistics (74 % ≤ 2 min; P1 82 % ≤ 15 min) | Contradicted by two clean measurements (EXT-02) | `leg_stop.py`, clean lot book | Y (PR #2) | No | Same definition reproduced on the clean book, shown next to the first-passage result | The D-1 stop level (1.55× own vs 1.6–1.7× cheapest) |
| Teacher-forced replay test | Last run on pre-clean caches | Clean caches | Y | No | `pytest analysis/exit_engine/tests` passes on the clean build | Trust in the replay engine |

## 3. Partially completed

| Item | State | Next step | Depends on | Branch | Acceptance criterion |
|---|---|---|---|---|---|
| Clean exit engine sections 4–6 | Done (first passage, side/basket, Clock-B, carried) | Write-up in `EXIT_ENGINE_FINDINGS.md` | — | Y | Doc updated with DEV/VAL/TEST numbers |
| Section 7 models | Stopped at the 2-hour background limit (no results) | Re-run as separate per-model jobs; score TEST once | `models.py` | Y | All model rows present with VAL and TEST metrics; none tuned on TEST |
| Section 3 trigger re-run | Stopped at the 2-hour background limit | Re-run on the clean build | `triggers.py`, `stop_shape.py`, `carry_stop.py` | Y | Reports regenerated |
| Section 8 replay (Mode A actual entries; Mode B decoded entries) | Open-fill run complete (ML-06) | Adverse / delay-1 fills | `replay.py` | Y | Metrics for 3 fills × 2 modes × 3 policies |
| Section 9 robustness | Not started | Run `robustness.py` | Section 7 models | Y | Segment, bootstrap, ablation and missing-data tables |
| PR #1 ML decision engine | Cloud run finished; results unreviewed | Download and review `algo8-research-report` | Artifact (expires 30 Nov 2026) | X (PR #1) | Report metrics entered in the ML audit |

## 4. Still under investigation (existing data)

| # | Task | Depends on | Branch | New data? | Acceptance criterion | Decision it enables |
|---|---|---|---|---|---|---|
| 1 | Stop timing with the algo's own recovered quotes (sparse tick feed) | Clean orders; `first_passage.py` | Y | No | A single k (± 0.05) and reference that answers ≥ 80 % of crossings within 1 min on DEV, VAL and TEST | Promote the per-lot stop to Approximate-high |
| 2 | Allocation identity via slot/clock chains; per-allocation stop and D0 scope | `chains.py`, clean lot book | Y | No | Per-allocation stop explains ≥ 80 % of stop-like D-1 exits and separates D0 carried vs fresh | Whether D0's weak stop is a scope rule |
| 3 | Clock-B act/no-act and contract choice | `clock_b.py` | Y | No | VAL precision and recall ≥ 0.8 for act/no-act; hit@1 ≥ 0.8 for choice | Clock B from Approximate-low to high |
| 4 | Extra-sale trigger (reconcile lineage Y's timer model with lineage X's 13/93) | `p3_*`, lineage X `deep_extra_search.py` | X + Y | No | One definition scored by both lineages on the same later cycles | Whether ENT-04 is a timer rule |
| 5 | D0 quantity templates and ladder | lineage X window labels; clean book | X + Y | No | Exact quantity match ≥ 80 % on later windows | Dynamic quantity from Approximate-low |
| 6 | Lump size vs margin proxy | `p5_*` | Y | No (proxy) | LOO error below the naive median | Whether SIZ-04 is margin-driven |

## 5. Blocked by missing data

| Unknown | Needed data | Register |
|---|---|---|
| Exact constants (stop multiple, cycle-stop level origin, ladder sizes) | Source code / configuration | EXT-02, RSK-01, SIZ-03 |
| Side-level / basket / partial reduction triggers | Decision logs, allocation ids | MGT-05, MGT-06 |
| 4 % carry SL and 1 % expiry-day stop semantics | Risk settings; NAV/margin | RSK-02, RSK-03 |
| Sizing formula, exposure ceiling, lump size | NAV / margin / capital allocation | SIZ-03–SIZ-05 |
| Pending-order handling, reversal motifs | Submit / ack / cancel logs | MGT-08, EXT-11 |
| Entry eligibility | Eligible-session calendar with no-trade days | STR-01, ENT-05 |
| Genuine out-of-sample validation of any decision rule | More months of Algo 8 trade exports | all |

## 6. Required before a first approximate replica

1. Finish revalidation (section 2 above), especially the D-1 stop level (task 2.3).
2. Freeze the [executable approximation](ALGO8_STRATEGY_SPECIFICATION.md#executable-approximation-for-a-first-replica--clearly-labelled)
   as a configuration, with every [U] component as an explicit, switchable placeholder.
3. Score it against the actual book with the existing replay metrics (position divergence, side exposure, Greeks, exit
   matching, P&L), per cycle, on all three splits, **without tuning on TEST**.

Acceptance: a reproducible run with published per-component fidelity. No "replica" claim beyond the measured fidelity.

## 7. Required before a high-fidelity replica

* Tasks 4.1–4.3 meeting their criteria (stop, allocation identity, Clock B), or the corresponding blocked data obtained.
* A side/basket reduction trigger that meets ≥ 80 % precision and recall out of sample, or decision logs that reveal it.
* Quantity agreement ≥ 80 % for scheduled slots on both days.
* Autonomous replay (Mode B, no actual orders) with exit-event matching ≥ 80 % precision and recall and position
  divergence below an agreed bound on later cycles.

## 8. Required before claiming successful reconstruction

* Every readiness component at **Exact**, validated on **new** Algo 8 trade data that no study has inspected.
* Or: the original source/configuration, with the replica reproducing recorded orders (contract, side, quantity, time
  within the poll interval) on that new data.

A behavioural replica with good P&L correlation does **not** meet this bar.
