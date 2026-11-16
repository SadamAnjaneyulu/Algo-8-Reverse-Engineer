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
| **Clean order-key rebuild** (col 163; all exit-engine caches regenerated; 12 tests pass) | DAT-02, DAT-04 | Y (PR #3) |
| **Model training and chronological evaluation** (11 jobs; DEV fit / VAL thresholds / TEST once) | ML-03 | Y (PR #3) |
| **Three-fill replay comparison** (minute-open / delay-1 / adverse; Mode A and B) | ML-06, ML-07 | Y (PR #3) |
| **Robustness and missing-data stress** (segments, bootstrap, ablation, bar removal) | ML-07 | Y (PR #3) |
| **Final PR #3 results and documents** (findings rewritten; PR description verified) | EXIT_ENGINE_FINDINGS.md | Y (PR #3) |
| **PR #1 artifact review** (0 / 20 tasks at 75 %; replay abstains) | ML-02 | X (PR #1) |
| **Conflict reconciliation** (six conflicts; two read-only evidence scripts) | REC-01 … REC-06 | audit |

## 2. Completed but requiring corrected-data revalidation

| Item | Why | Depends on | Branch | New data? | Acceptance criterion | Decision it enables |
|---|---|---|---|---|---|---|
| ~~Exit-engine sections 1–3 numbers~~ **DONE** | Rewritten on the clean build; section 3 complete | — | Y (PR #3) | No | Met | — |
| P4 strike-choice model (68.5 %) | Reused key in an un-re-runnable chain (DAT-03) | Writer of `p4_orders_feat/prem/cons` caches (not in repo) | Y (PR #2) | No | Re-run with col-163 key; report the new top-1 vs nearest-ATM | Whether STK-03 becomes STRONG or is retracted |
| `FINDINGS.md` per-lot stop statistics (74 % ≤ 2 min; 82 % ≤ 15 min) | **Reproduced 9 Nov** on the clean book with PR #2's own functions (74.1 % / 82.0 %) and shown next to the first-passage result (audit §7A); definition and population differences (pre-trigger exits, follow-on lots, closed-lot triggers) explain the gap; exact constant UNRESOLVED | `leg_stop.py`, clean lot book | Y (PR #2) | No | Met for the reproduction; the stop level is carried to priority task 1 below | The D-1 stop level (1.55× own vs 1.6–1.7× cheapest) |
| ~~Teacher-forced replay test~~ **DONE** | 12 tests pass on the clean build | — | Y | No | Met | — |

## 3. Partially completed

| Item | State | Next step | Depends on | Branch | Acceptance criterion |
|---|---|---|---|---|---|
| Clean exit engine sections 4–6 | Done (first passage, side/basket, Clock-B, carried) | Write-up in `EXIT_ENGINE_FINDINGS.md` | — | Y | Doc updated with DEV/VAL/TEST numbers |
| Section 7 models | **Done**: 11 jobs merged, TEST scored once, none reaches 80/80 | — | `models.py` | Y | Done (ML-03) |
| Section 3 trigger re-run | **Done**: T1–T3, stop shape, carry stop and the T4 ablation for all nine categories | — | `triggers.py` | Y | Done (`t4_family_gains.csv`) |
| Section 8 replay (Mode A actual entries; Mode B decoded entries) | **Done** for minute-open, one-minute-delay and adverse fills (ML-06, ML-07) | — | `replay.py` | Y | Metrics for 3 fills × 2 modes × 3 policies |
| Section 9 robustness | **Done** (4 headline models) | — | Section 7 models | Y | Done (ML-07) |
| PR #1 ML decision engine | **Done**: artifact reviewed 9 Nov; metrics entered in the audit (§7B) | — | Artifact (expires 30 Nov 2026) | X (PR #1) | Met |

## 4. Priority tasks, by information value

No general-purpose ML tuning is recommended: no model family reached 0.75 / 0.75 and the limiting factor is missing
information, not capacity.

| # | Task | Depends on | Branch | New data? | Acceptance criterion | Decision it enables |
|---|---|---|---|---|---|---|
| 1 | **DONE in PR #5 phase 2 — result: UNKNOWN retained.** Reconcile the exact per-lot stop reference using the recovered per-order quotes (limit ÷ 1.15 / ÷ 0.85); six references × *k* 1.40–2.00 × three conventions: no rule reaches 80 / 80; stable lower edge ≈ 1.50 × lowest individual entry. Follow-up: explain non-response (needs sub-minute timestamps or order-lifecycle logs) | Clean orders; `first_passage.py`; `audit/evidence/` | Y | No | A single *k* (± 0.05) and reference (own / cheapest / per-allocation) that answers ≥ 80 % of crossings within 1 min on DEV, VAL and TEST | Promote the per-lot stop to Approximate – high |
| 2 | **Reconstruct allocation ownership and per-allocation state** | `chains.py`, clean lot book | Y | No | Per-allocation stop explains ≥ 80 % of stop-like D-1 exits and separates D0 carried vs fresh | Whether D0's weak stop is a scope rule |
| 3 | **Investigate Clock-B selection and act / no-act** | `clock_b.py`, task 2 output | Y | No | VAL precision and recall ≥ 0.8 for act / no-act; hit@1 ≥ 0.8 for choice | Clock B from Approximate – low to high |
| 4 | **Reconcile extra-sale triggers across both lineages** | `p3_*`, lineage X `deep_extra_search.py` | X + Y | No | One definition scored by both lineages on the same later cycles | Whether ENT-04 is a timer rule |
| 5 | **Review the original configuration, risk settings and decision logs, if obtainable** | A privileged source | — | Yes (data request) | Source or logs reproduce recorded orders on the sample | Turns [U] rules into reads |
| 6 | **Obtain additional historical Algo 8 trade data** | New exports | — | Yes | ≥ 1 unseen month; every candidate rule validated there without re-fitting | Genuine out-of-sample validation |

Lower priority: D0 quantity templates; lump size vs a margin proxy; the P4 cache writer for STK-03.

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

1. Finish revalidation (section 2 above); the D-1 stop reference is priority task 1.
2. Freeze the [executable approximation](ALGO8_STRATEGY_SPECIFICATION.md#executable-approximation-for-a-first-replica--clearly-labelled)
   as a configuration, with every [U] component as an explicit, switchable placeholder.
3. Score it against the actual book with the existing replay metrics (position divergence, side exposure, Greeks, exit
   matching, P&L), per cycle, on all three splits, **without tuning on TEST**.

Acceptance: a reproducible run with published per-component fidelity. No "replica" claim beyond the measured fidelity.

## 7. Required before a high-fidelity replica

* Priority tasks 1–3 meeting their criteria (stop, allocation identity, Clock B), or the corresponding blocked data obtained.
* A side/basket reduction trigger that meets ≥ 80 % precision and recall out of sample, or decision logs that reveal it.
* Quantity agreement ≥ 80 % for scheduled slots on both days.
* Autonomous replay (Mode B, no actual orders) with exit-event matching ≥ 80 % precision and recall and position
  divergence below an agreed bound on later cycles.

## 8. Required before claiming successful reconstruction

* Every readiness component at **Exact**, validated on **new** Algo 8 trade data that no study has inspected.
* Or: the original source/configuration, with the replica reproducing recorded orders (contract, side, quantity, time
  within the poll interval) on that new data.

A behavioural replica with good P&L correlation does **not** meet this bar.
