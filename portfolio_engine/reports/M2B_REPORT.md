# M2-B report — position lineage engine

Branch `engineering/position-lifecycle-basket-reconstruction` (base: engineering `621e11e8` + TP-03 Phase 1 `502bfbed`, merged as `afad6361`). **Decision: PASS for the M2-B gate, with the documented limits below. Models A/B/C, wing/body, cut/re-entry and alpha were NOT started.**

## Executed evidence
| Command | Result |
|---|---|
| `cmake --build portfolio_engine/build && portfolio_engine/build/pe_core_tests` | **24/24** C++ checks (adds lineage, reversal, int64-overflow guard); no compiler warnings |
| `python3 -m pytest portfolio_engine/tests -q` | **127 passed** = M1 41 (accounting 23, TP-01 reconciliation 13, parity 5) + M2-B 86 (lineage 19, mutation regressions 16, independent-reference differential 40, real-ledger 9, lineage parity 2) |
| `python3 -m pytest portfolio_engine/tests -q -m "not slow"` | 98 passed, 29 deselected (fast set; the slow set needs the real ledger / C++ build) |
| `python3 portfolio_engine/tools/parity_lineage.py --real-full` | **225/225** cases byte-identical (25 fixtures incl. the full 41,421-fill ledger × 3 conventions × 3 tie orders) |
| `python3 portfolio_engine/tools/m2b_reconcile.py` | all four reference counts reproduced (below) |
| M1 artifacts / old research | `git diff 3a7f1cad` on M1 fixtures, M1 parity reports, `tp_reconstruction/`, raw CSV: empty |

## Acceptance gate
| Gate item | Evidence | Result |
|---|---|---|
| M0/M1 tests still pass | 41 M1 tests incl. M1 parity (117 + 9 cases) | PASS |
| TP-01 totals preserved | opened 1,414,545 / closed 1,377,065 / remaining 37,480; realized ₹ FIFO 2,100,552.00, LIFO 2,096,874.50, AVG 2,100,111.63 from the **sum of closing allocations** | PASS |
| OA / CP reconcile | 23,684 OA (Σ 1,414,545 units), 17,760 CP (Σ 1,377,065); CP rows and quantities equal TP-02 `exit_event_timelines` (17,760) without relying on its semantics | PASS |
| Conventions differ only analytically | observed-layer hash identical for FIFO/LIFO/AVG; engine **refuses to build** if it differs (leak counter-example test); 15,889 of 17,760 CPs attribute differently under FIFO vs LIFO (descriptive) | PASS |
| Reversals | 100 short + buy 130 → CP 100 (`REVERSED`) + OA 30 (new episode, `started_by_reversal`); 23 real reversal fills each one CP + one OA | PASS |
| AVG claims no ownership | every AVG allocation is `POOL:<episode>` / `NOT_IDENTIFIABLE`; pool = quantity-weighted average | PASS |
| Identities stable across conventions | 2,667 episode ids and fields equal TP-01 for all three; **conditional on tie order** (limit below) | PASS (with limit) |
| 26 mixed parents | 26 = 23 containing a reversal fill + 3 multi-fill parents without one; OA + CP units equal the parents' fill units | PASS |
| Python/C++ parity | 225/225 byte-identical lineage cases | PASS |
| Synthetic edge cases | partial fills, multiple openings, partial and full closes, reversals (incl. double), expired-unclosed (+ exact expiry boundary), duplicate-flagged fills, missing metadata (`NA` stays `NA`), mixed parents | PASS |

## Independent challenge review (separate agent, read-only)
No contract-breaking defect. It re-derived the lineage with its own per-unit matcher: 300 seeded sequences and **all 41,421 real fills** for the three conventions matched; C++ byte-identical on adversarial and random inputs. It found **weaknesses, all fixed and kept as regression tests** (`test_lineage_mutations.py`):
1. `check()` was partly tautological (duplicate OA row, a REVERSED event carrying the whole fill quantity, I10 unconditional, P&L compared with itself) → rewritten to re-derive every identity from emitted rows, lifecycle events and input fills; unique-id, row-vs-fill, price/sign/ownership-label checks added.
2. In-memory API accepted zero/negative quantity → rejected in Python and C++ `replay()`.
3. C++ P&L could wrap int64 silently → overflow now throws.
4. M1 hardening: strict-mode AVG cash identity used an absolute tolerance only → relative term added (Python and C++); no output changes, real data unaffected.
5. Surviving mutations (CA price off by one tick, flipped OA side, dropped `started_by_reversal`, wrong slice price, expiry `<=` vs `<`, duplicate CA ids, wrong ownership label, episode `last_ts` / `n_close_fills`): **16 mutation tests now reject each**.
Also found by my own tests: the FIFO/LIFO P&L signs in `POSITION_LINEAGE_RULES.md` were reversed (corrected).
Remaining weakness: a bug present identically in both languages and in the independent matcher would not be seen; real-ledger tests are slow and need a C++ build (marked `slow`).

## Limits stated, not hidden
* **Identity is invariant to FIFO/LIFO/AVG but conditional on the tie-order convention:** under `sells_first` / `buys_first`, 20 fills (42 rows) in 5 instruments change episode / portion rows — all within the 46 instruments with mixed-side same-second fills, a superset of TP-01's 3 close-quantity-ambiguous instruments. Differences include downstream fills of those instruments. The primary `src` order stays authoritative.
* `INCOMPLETE_SOURCE_HISTORY` is reserved and never produced without external evidence.
* Slices are end-of-replay only; per-event slice history is not stored.
* int64 limits: C++ throws beyond 9.2e18 paise·units (Python is unbounded); irrelevant to this data (max ≈ 1e10).
* Open item for M2-C: the registered **number-block** semantics (gap 500 vs 20, closing-only vs all orders, time limit) are ambiguous — documented in `BASKET_GROUPING_METHODOLOGY.md`; implementation stops for review.

## Changed files (this stage; all under `portfolio_engine/` unless noted)
Docs: `docs/{BASKET_GROUPING_METHODOLOGY,EVIDENCE_REGISTRY,POSITION_LINEAGE_RULES,SCHEMAS}.md`, `docs/DEMO_CYCLE_SELECTION.md`, `IMPLEMENTATION_PLAN.md`. Selection (frozen before any grouping): `reports/DEMO_CYCLE_SELECTION_NOTE.md`, `reports/demo_cycle_scores.csv` → **NIFTY `2026-06-30`, SENSEX `2026-07-16`**. Code: `python/pe/{lineage,lineage_set,parents,ledger,replay,invariants}.py`, `python/pe/generators/{synthetic_m2,historical}.py`, `cpp/include/pe/{lineage,lineage_recorder,ledger,replay,types}.hpp`, `cpp/src/pe_replay.cpp`. Tools: `tools/{select_demo_cycles,make_fixtures_m2,parity_lineage,m2b_reconcile,position_query}.py`. Tests: `tests/test_lineage*.py`, `cpp/tests/test_core.cpp`, `pytest.ini`. Fixtures: `fixtures/synthetic_m2/`. Reports: `reports/{M2B_REPORT,M2B_RECONCILIATION_REPORT,M2_DATA_DICTIONARY}.md`, `reports/{m2b_reconciliation,parity_lineage_report}.json`. Nothing under `tp_reconstruction/`, no M1 fixture or parity artifact, and not `stage2_alpha_research/` sources were modified.

## Go / No-Go
M2-B is safe to accept. **M2-C may begin only after your review and authorization**, and the number-block variant needs your answer on its semantics first.
