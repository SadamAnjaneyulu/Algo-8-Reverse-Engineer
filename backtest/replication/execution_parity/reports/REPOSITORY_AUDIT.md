# Execution parity — Phase 1 repository and evidence audit

**Purpose.** Establish what exists before building an execution-behaviour parity framework. Read-only. Labels: VERIFIED (read or executed in this session) · REPORTED (stated in an earlier report, not re-derived) · UNKNOWN.
**Direction (Rahul, verbatim in the brief):** match *execution behaviour*, not Sharpe/Calmar/DD; then build own alpha; do not treat the last three years as one sample because expiry days and market regime changed. Nothing in this milestone optimises P&L.

## 1. State (VERIFIED)
| Item | Value |
|---|---|
| Starting branch / HEAD | `research/algo8-mechanical-replica` @ `66df0b36` (PR #14, draft; stacked on PR #13 head `9e64fbad`) |
| Working tree at start | clean |
| New branch for this milestone | `research/execution-parity`, cut from `66df0b36`. **Why:** PR #14 is scoped to the earlier replica/backtest plan that Rahul's guidance has superseded; a separate branch keeps this milestone reviewable on its own and leaves PR #13 and PR #14 untouched. It reuses PR #14's cycle-eligibility register. No deletion, no force-push |
| PR #13 | draft; **no CI workflow exists in the repository** (no CI claim can be made); not merged, status unchanged |
| Pre-review outputs | `backtest/replication/lot_lifecycle/outputs/v1_pre_review/` (DO_NOT_CITE) — preserved, not read as evidence |

## 2. What already exists for each execution component
| Component | Existing implementation | Evidence of parity today | Verdict of this audit |
|---|---|---|---|
| Fill-level original records | `lot_lifecycle/src/ledger.py::load_fills` (exact per-fill prices; 41,421 fills, 35 cycles) | — | **Reuse** (authoritative) |
| Unit-lot accounting, 4 ownership conventions, D1 two readings | `lot_lifecycle/src/lots.py` + 28 tests | cash identity ₹0.000 (**tautological** for allocation) | **Reuse as accounting oracle (Mode 3)** |
| One-to-one event matching with tolerance | `lot_lifecycle/src/matching.py` (Hungarian, unit-lot) | defect C fixed | **Reuse** |
| Fully simulated D-1 ladder + wings + stops + flatten (Mode 2) | `replication/sim.py` (R1/R2), `rules.py`; stored `results/replay_sim_events.csv` | `decision_agreement.csv`: D-1 body entries slot×right precision/recall 0.82/0.67 (0.75/0.61 with strike); wings 0.78/0.66 (0.53/0.45 with strike); D-1 buy-backs 0.96/0.32 by count; D0 body buy-backs 0.92/0.095; **D0 body sells 0 of 12,675 lots** (R1 has no D0 entries) | **Under test, unchanged** |
| D0 simulator with teacher-forced start book | `d0_reconstruction/d0_sim.py` v1.1, `lot_lifecycle/src/d0_sim_v2.py` | scheduled-sale timing recall 0.19–0.55 (convention-dependent); simulated P&L unreliable | Reuse as evidence, not as an engine |
| Teacher-forced **management** (inject actual entries, simulate exits) | **none** (the skeleton spec §6 "Mode A" was never implemented) | none | **Gap G3** |
| Inventory-path comparison (event by event) | **none** — only end-of-cycle open lots and overnight net lots (`overnight_lots_R*.csv`) | none | **Gap G2** |
| Event-driven engine with MarketView / OrderIntent / Fill / PositionEvent | **none** — `sim.py` is a monolithic function; `analysis/engine.py` is a minute loop; `portfolio_engine` is event-driven but has no entry/settlement logic | — | **Gap G1** |
| Per-lot stop, cycle stop, flatten as swappable modules | constants and functions in `rules.py` (central 1.6×, −₹1.44 L, 15:14) | per-lot stop: `exit_engine` first-passage; "0 of 18 candidate rules at 80/80" (REPORTED) | Hypotheses; **not** facts |
| Null baselines for event agreement | **none** for the R1 agreement table; chance baselines exist only in the replacement analysis | — | **Gap G5** |
| Expiry-calendar / regime register | `data_validation` expiry coverage tables; PR #14 eligibility register (no regime fields) | — | **Gap G6** |

## 3. Why the existing agreement numbers cannot be used as parity evidence as they stand
1. **Count-based matching on coarse keys** (`decision_agreement.py::agree`): a simulated order counts as matched if *any* live order sits in the same (cycle, slot, right) key — no one-to-one pairing, no timing tolerance inside the slot, units mismatch (simulated orders vs live lots). It can overstate agreement.
2. **No chance baseline**: slot×right keys are dense (every slot acts in 544/544 windows), so a high match rate is partly guaranteed by the schedule itself.
3. **Ownership-dependent quantities** (lot-level closes) are compared without stating the convention.
4. **No inventory comparison**, so a high entry match cannot be checked against a divergent position path.
5. The stored R1/R2 rules were read from the same 35 cycles (REPORTED: "Rules were read from the 2026 live window"), so agreement there is **in-sample**.

## 4. Known defects carried into this milestone (VERIFIED in earlier reports)
Fixed-bin matching (C, fixed in `matching.py`); D0 09:15 look-ahead (D, fixed in new code only); start book (E); passive lots at a stop (A, **assumption**, two bounds); replacement wings (B, **unknown**); body-buy ambiguity (D1, two readings); lot ownership ambiguous for 89 % of body shorts; settlement is a proxy; legacy event table has minute-0 look-ahead (not to be used).

## 5. Facts that shape the historical part (VERIFIED from `data_validation` tables)
* **NIFTY expiry weekday changed:** Thursday for every expiry from 2023Q4 to 2025Q3 (a few Wednesday shifts around holidays), **Tuesday from 2025Q3 onward** (Monday around holidays). The live ledger (June–October 2026) lies entirely in the Tuesday regime. D-1/D0 are therefore Wed/Thu historically and Mon/Tue in the live ledger. This is exactly the structural break Rahul warned about; the historical test is segmented by it.
* NIFTY lot size changed over the period (inferred per session from volumes: 50/25/75/65); SENSEX 10/20; SENSEX history starts 2024-05-30 and has no open interest.
* Only D-1 and D0 sessions exist in the dataset; option universe ATM ± 45 around the D-2 close; no bid/ask.
* Yahoo daily index series (`data_validation/reference/yahoo_daily_*.csv`) is available for a regime description (volatility and trend) without using any option data.

## 6. Gap analysis → what this milestone builds
| Gap | Built | Mode |
|---|---|---|
| G1 no event-driven execution core | `execution_parity/src/exec_core.py` (MarketView, PortfolioState, OrderIntent, ExecutionModel, Fill, PositionEvent, EventLoop), small, tested | all |
| G2 no inventory path comparison | `compare.py`: contract-level net position at every event time, original vs reconstructed (ownership-independent) | 1, 2, 3 |
| G3 no teacher-forced management | `components.py` + `run_parity.py`: inject original orders, **leave one component out**, test whether our component reproduces the omitted original behaviour | 1 |
| G5 no null baselines | phase-preserving circular-shift null for every event-agreement metric | all |
| G6 no calendar/regime register | `HISTORICAL_REGIME_ROBUSTNESS.md` + table | 5 |
| unified scorecard | `PARITY_SCORECARD.md` generated from component results, no single score | 7 |

## 7. What I deliberately will not do
Change `sim.py`, `rules.py`, the lot engine, the C++ engine or any stored result; tune any threshold to improve agreement; reintroduce replacement logic; use the 35 cycles as an independent holdout; compare historical simulated P&L with original performance.
