# Phase 1, Gate 5: D0 reconstruction. Audit and plan

*2026-11-25. **Status: IN PROGRESS (audit and plan only; no D0 engine built this session).** Nothing here is a D0 result at order level. Existing data only. Nothing committed.*

## 1. Audit of what exists for D0
| Asset | What it is | Limit |
|---|---|---|
| `bl_d0_fr.py` + `bl_d0s_*`, `bl_d0b_*` | the free-running D0 **research simulator**: per minute, from the real carried book, refit on each split's training cycles; parts: cycle stop, body buy-backs, timetable waves, D-1 breakout pair, D0 solo ladder, counter-sells, opening wings, hedge controller, 15:14 clearance | minute-resolution lot events (no seconds, no order type, no price); parts are loaded by `exec` of other scripts' source (no clean interface); starts from the **real** carried book (teacher-forced start); not an order-level engine |
| `bl_d0_fr_score.py` and the scorer's legacy bridge | lot-level F1: **0.410** out-of-fold (0.452 / 0.390 on unseen splits), reproduced by `tests/test_order_scorer.py` | the lot-level matching of the original work, not the order-level spec v1.1 |
| Register rows D0-01..D0-07 | timetable (Confirmed/Decoded), SENSEX V1 strangle (Confirmed), solo and counter-sells (Partial, weak), buy-backs stop 1.4x and take-profit 0.1x (Decoded) with bursts and carried lots Unresolved, hedge controller (Confirmed quantity), clearance (pre-auction era Decoded; post-auction Unresolved), sizing (Unresolved) | see `PHASE1_RULE_CLASSIFICATION.md` |
| Real D0 log | about 29,000 body, wing and lump orders in 30 cycles (body sells 8,955, body buy-backs 9,335, body long closes 831, `s_` stop module 387, lump closes 304); **21% of D0 orders are multi-lot** | three times the D-1 log; clearance and stop module dominate the tail |
| Engine | **no standalone D0 engine exists** (audit section 6) | the largest open work item of Phase 1 |

## 2. Dependencies and constraints
* The opening D0 book is the D-1 close: in mode F it is the **simulated** carried book (B1's), in mode T the **real** one. The D-1 carry error (book distance 79% of gross lots at the close; median L1 0.51 during the day) therefore propagates into D0 in mode F; T and F must be reported separately.
* Regime facts: clearance clock 15:14 (post-auction era) versus 15:18-15:19 (pre-auction); post-auction D0 clearance has only 3 D-1 sessions before the 7 Dec 2026 change and no real log of the new regime.
* The cycle stop (s_ module) acts across D-1 and D0 (Rs 1.2-1.36 lakh MTM threshold; decoded range only).

## 3. Plan (each stage preregistered before it is built or run; baseline = the research simulator's lot-level numbers and, once built, the first order-level run)
| Stage | Deliverable | Stop rule |
|---|---|---|
| 5a | a clean `D0Engine` in the D-1 architecture (feed, book, risk guard, replay), reusing the verified D-1 book, wing controller and mechanics; D0 rules ported as explicit modules with one switch each (timetable waves and strangle, D0 solo ladder, counter-sells, stop 1.4x and take-profit 0.1x, hedge with lump salvage, clearance by era, cycle stop) | order-level F reproduces the research simulator's lot-level figure (0.410) within a stated tolerance before any new rule |
| 5b | opening book handoff test: D-1 simulated carry versus real carry at the first D0 second; T and F | no unexplained difference beyond the D-1 carry error |
| 5c | order-level scoring of D0 under spec v1.1 (F and T, TF-E diagnostic), same ledger discipline as D-1 | quality standards fixed **before** the first scoring run |
| 5d | mismatch ledger and classification by module (solo, counter-sells, buy-back bursts, carried lots, clearance, wings, stop module); inherited versus independent as in Gate 3a | each experiment preregistered with fixed criteria |
| 5e | one correction at a time, each with regression over all cycles | evidence exhausted or criteria met |
Expected outcome, stated in advance from the register: D0 solo sells (70% of D0 sell lots, F1 0.38-0.40), buy-back bursts (64% of buy-back lots) and the post-auction clearance clock are data-limited; Gate 5 is therefore expected to end **CONDITIONAL**.

## 4. Why this session stops at the plan
The engine port, a D0 order-level scorer run and the D0 experiments are a multi-session build; doing them half-way would produce numbers without the regression and preregistration discipline the gates require. Next exact action: stage 5a (port the D0 modules behind switches; reproduce the research simulator).
