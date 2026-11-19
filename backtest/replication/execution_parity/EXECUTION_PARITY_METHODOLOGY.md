# Execution parity — methodology, tolerances and acceptance criteria

**Pre-registration.** This file and `UNRESOLVED_EXECUTION_RULES.md` were written and committed **before any parity result was computed**. Thresholds were fixed here; they are not changed after results are seen. If a defect is found afterwards, the original run is preserved and the re-run is labelled revised/contaminated.
**What is being asked:** does our reconstructed execution engine produce the same *observable execution behaviour* as the original Algo 8 records (35 live cycles, 41,421 fills)? **Not asked:** profitability, Sharpe, Calmar, drawdown. P&L is a secondary diagnostic and never drives a decision.
**Evidence status of the data:** all 35 cycles were inspected repeatedly; every rule we implement was read from them. **Every agreement figure below is in-sample.** No random split of cycles or lots is used or claimed. Chronological blocks are labels only.

## 1. Three things that must not be confused
| Concept | What passing means | What it does not mean |
|---|---|---|
| Accounting reconciliation | cash and unit counts conserve | correct lot ownership; any behavioural similarity |
| Execution-behaviour similarity | our engine acts like the original (events, inventory) | profitability; that the *rule* is the original rule |
| Strategy profitability | made money | either of the above |

## 2. Operating modes (what each can and cannot prove)
| Mode | Procedure | Can show | Cannot show |
|---|---|---|---|
| **3 Accounting diagnostics** | replay all original fills through our engine | our book/ledger arithmetic is right; inventory path derivation is right | any behaviour parity, any rule |
| **1 Teacher-forced, component-isolated** | inject every original order **except those of one component under test**; our component generates its own decisions on the *actual* book/market; compare with the omitted original events | whether *that* component, in isolation, reproduces the original behaviour given the original context | the entry-generation rules; interactions that depend on the omitted events' feedback |
| **2 Fully simulated** | engine generates entries and exits from reconstructed rules (R1) | end-to-end behavioural similarity and where it first diverges | which component caused a divergence (use Mode 1); independence (rules were fitted on these cycles) |

Differences caused by entry generation (Mode 2) are separated from differences caused by management or accounting (Mode 1/3) by construction.

## 3. Reference (original) side
`lot_lifecycle/src/ledger.py::load_fills()` — fill-level, exact per-fill price, second timestamps, within-second order = file order. An **order** = column-163 tag (module from prefix: numeric = body, `h_` wing, `v_` lump, `s_` stop, `m_` manual). Quantities are whole lots (NIFTY 65, SENSEX 20 units). Inventory is computed **per contract** (net lots by underlying/expiry/right/strike), which is **ownership-independent**; lot-level statements are made only under each of the four conventions and are labelled.
Market data: per-cycle full-chain minute arrays (`replication/data.py`, open/close/volume); decisions at minute *j* use bars completed before *j*; minute index 0 = 09:15.

## 4. Matching, tolerances, and why
| Dimension | Matching | Tolerance (primary; sensitivity grid reported) | Basis |
|---|---|---|---|
| Entry events | one-to-one (Hungarian, unit lots) per (cycle, right[, strike]) using `lot_lifecycle/src/matching.py` | ±1 minute (grid 0, 1, 2, 5) | fills carry seconds, decisions are minute-resolution; 97.3 % of live fills lie inside their own-minute bar (REPORTED); ±1 min was the PR #3 convention — **provisional** |
| Exit events | same | ±2 minutes (grid 0, 1, 2, 5) | PR #3 convention — **provisional** |
| Strike | reported separately: exact, ±1 step, signed step error | none | exact identity where records permit |
| Quantity | reported separately: exact lots per slot-leg; MAE | none | exact |
| Inventory | contract-level net lots at **every original event time** and at every minute, both paths | none (compared, not matched) | ownership-free |
| Cycle-level events (cycle stop) | confusion matrix over the 35 cycles + timing error | timing ±2 min | small n: wide intervals stated |

Event *identity* (which instrument/time/quantity) and lot *allocation* (which lot closed) are kept separate: identity is judged by the table above; allocation is reported only as a range over four conventions.

## 5. Chance baselines (to stop high rates arising from the schedule alone)
Every event-agreement metric is accompanied by a **phase-preserving circular-shift null**: the simulated (or original) event times are shifted circularly inside the session window by a random multiple of 15 minutes (30–120 min, either direction), preserving clock phase, dropping no draw, matched one-to-one in the same way; 200 draws; lift = observed / null mean. A MATCH requires lift ≥ 1.5 (provisional; lift ≥ 1 is the logical floor, 1.5 prevents a schedule-trivial pass).

## 6. Component classification rules (fixed now)
Applied to each event-agreement component at its primary tolerance, with P = precision (matched / simulated), R = recall (matched / original):
| Class | Condition |
|---|---|
| **MATCH** | P ≥ 0.80, R ≥ 0.80, lift ≥ 1.5 on both |
| **PARTIAL MATCH** | not MATCH, and P ≥ 0.50 and R ≥ 0.20 |
| **MISMATCH** | P < 0.50 or R < 0.20 (the component reproduces less than a fifth of the original events of its class, or more than half of its actions are not original) |
| **UNRESOLVED** | the original behaviour cannot be established from the records (decided by evidence, not numbers) |
| **NOT TESTABLE** | required data absent (decided by evidence, not numbers) |
The 0.80 level follows the repository's earlier "80/80" convention (skeleton spec, TP-02); 0.50 and 0.20 are my provisional choices with no empirical basis beyond marking "more often right than wrong" and "explains at least a fifth". **All thresholds are PROVISIONAL.** Strike and quantity conditional on matched events: MATCH ≥ 0.80 exact, PARTIAL ≥ 0.50.
Inventory path (over *active* contract-minutes = either path non-zero; zero-zero minutes excluded so they cannot inflate agreement): **MATCH** exact share ≥ 0.90 and normalised MAE (MAE ÷ mean |original net lots|) ≤ 0.10; **PARTIAL** exact share ≥ 0.60 and normalised MAE ≤ 0.35; else **MISMATCH** (provisional).
Hard (non-statistical) criteria — evidence-based, no tolerance: cash/unit conservation to < ₹0.01; zero decision changes under future-data perturbation; deterministic event ordering.

## 7. Pre-registered hypotheses (all developed AFTER inspecting the 35 cycles)
Every constant below was read from the live window earlier; none is out-of-sample. They are tested, not assumed.
| ID | Component under test | Statement tested (given the actual book and actual market) | Falsifier |
|---|---|---|---|
| H-ENT | D-1 scheduled entries (Mode 2) | R1 ladder generates D-1 body sells at the 17 windows with the right count/strike/size | MISMATCH per §6 |
| H-STK | strike selection (Mode 1) | strike = nearest step to the previous completed minute's index close | exact rate < 0.50 |
| H-QTY | quantity per slot-leg (Mode 1) | modal ladder (R1 template) | exact rate < 0.50 (TP-03 already found it is not a fixed template) |
| H-WNG | wing selection (Mode 1) | OTM same-right strike whose price ≈ 2.45 % of the body price | strike exact < 0.50 |
| H-LEG | per-lot stop (Mode 1) | a body lot is bought back when LTP ≥ k × reference; k ∈ {1.55, 1.60, 1.65, 1.70}; reference ∈ {own entry, cheapest open entry}; exempt entry ≤ ₹4 | MISMATCH per §6 for every (k, reference) |
| H-CYC | cycle stop (Mode 1) | cumulative LTP MTM ≤ −L triggers a full liquidation; L ∈ {1.30, 1.35, 1.44} lakh | stop/no-stop P or R < 0.50 across all L |
| H-FLAT | final flatten (Mode 1) | the short book is flattened at 15:14 on D0, **after 2026-08-03 only** | actual shorts at 15:15 > 50 % of those at 15:13 in post-cutover cycles |
| H-CARRY | carry to settlement | deep-OTM shorts (> 6 steps) are left to expire, near-ATM are not | carried share not monotone in distance |
| H-INV | inventory path (Mode 2) | R1 inventory path follows the original | §6 inventory classes |
All (k, reference) and L alternatives are reported; none is selected by agreement. Unsuccessful results are preserved.

## 8. Historical mechanics robustness (Phase 5) — what it is and is not
Purpose: find **brittle execution assumptions** under different expiry structures and regimes. Not optimisation; no P&L comparison with the original (no original records exist for those periods).
* Segments by **expiry-calendar structure** (NIFTY: Thursday regime to 2025-08, Tuesday regime from 2025-09; SENSEX per its own weekday runs) and by index; regime description from the independent Yahoo daily series only (realised-volatility terciles, trend), never from option data.
* Eligibility: the strict set (FULLY_FEASIBLE) and the substituted set (declared wing substitution) are run **separately**; excluded sessions and reasons listed; no gap is filled silently.
* Mechanics checks per cycle and segment: cash/unit conservation; inventory never negative beyond rule; `NO_MARKET` rate; wing substitution rate; share of orders on zero-volume bars; stop/flatten/settlement reached; look-ahead perturbation test; engine determinism. P&L may be tabulated only as a secondary diagnostic.

## 9. Readiness decision rule (fixed now)
Core components: entries (timing + instrument), strike, quantity, exits (events), wings, inventory path, accounting, no-look-ahead, historical mechanics.
* **NOT READY** — any core component is MISMATCH, or accounting / look-ahead / determinism fails, or a core component is UNRESOLVED/NOT TESTABLE without a bounded impact.
* **CONDITIONALLY READY** — no core MISMATCH; core components are MATCH or PARTIAL; every PARTIAL/UNRESOLVED has a stated, bounded effect on inventory and execution.
* **READY FOR ALPHA RESEARCH** — all core components MATCH, hard criteria pass, historical mechanics pass in both expiry structures, and unresolved rules do not touch a core component.
Because every rule was fitted on these 35 cycles, a MATCH is recorded as **MATCH (in-sample)** and cannot be confirmed without new original records; this is stated in the decision, not hidden.
No single overall parity percentage is produced. Any composite would have to show its weights, missing-data treatment and sensitivity; none is planned.

## 10. Limits that apply to everything
Second-resolution fills; minute-resolution market data; no bid/ask or depth; no parent/allocation ids; unknown pre-log positions; settlement proxy; the 35 cycles are not a holdout; sub-minute ordering cannot be validated.
