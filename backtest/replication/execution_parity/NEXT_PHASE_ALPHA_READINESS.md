# Next phase — what must be frozen before independent alpha research

**Decision of this milestone (rule fixed in advance, `EXECUTION_PARITY_METHODOLOGY.md` section 9): NOT READY** — core components are MISMATCH (D0 entries, D0 buy-backs, strike over all sells, per-lot stop, causal cycle stop, wing strike, inventory trajectory). The decision survived an independent adversarial review that corrected several numbers (`INDEPENDENT_REVIEW.md`). See `PARITY_SCORECARD.md` and `EXECUTIVE_SUMMARY.md`. Nothing in this file overrides that decision; it says what would change it and what can safely be reused meanwhile. No alpha research was started.

## 1. What can be frozen now (as a research harness, not as a replica)
| Layer | Status | Why it is safe |
|---|---|---|
| Event-driven core (`exec_core.py`): causal `MarketView`, `OrderIntent`, `ExecutionModel`, `PortfolioState`, `EventLoop` | freeze (permissive policy) | no-look-ahead perturbation tests pass, including the decision-minute bar; deterministic; equals the legacy simulator event-for-event on 70 cycle x variant runs. **Caveats:** the strict execution policy reads the decision minute's volume (hindsight filter); the exit modules (`LegStop`, `CycleStop`, `Flatten`) have evidence only from Mode 2 and the historical runs, because Mode 1 used stand-alone re-implementations |
| Accounting and contract-level inventory (`PortfolioState`, `compare.path_from_events`) | freeze | Mode 3 replay: path/cash/net exact; gross equals the lot engine to 1e-11. **This only proves bookkeeping** |
| Comparison engine (`compare.py`) with phase-preserving null and pre-registered classes | freeze | unit-tested; the same tooling can score any new entry module against the original ledger |
| Eligibility register and expiry-structure segmentation | freeze | availability-based, fixed before use |

## 2. What may be used only as a labelled scenario
D-1 scheduled ladder (PARTIAL MATCH, in-sample), nearest-step strike in scheduled windows (60 % exact), 2.45 % wing budget (wing strike exact 32 %), 15:14 flatten conditioned on date (79 % of short lots; 10 of 12 post-cutover cycles). Each carries its evidence label from `algo8_replica/config/rule_evidence.yaml`.

## 3. What must NOT be treated as execution truth
D0 entries and buy-backs (engine reproduces ~0 % / ~5 %), per-lot stop (explains ≤ 17 % of buy-backs), cycle stop (1 / 0 / 0 of 11 reproduced at L = 1.30 / 1.35 / 1.44 lakh with causal marks; 10 / 9 / 8 with the decision-minute close, a non-causal diagnostic that points to a data-resolution limit at the D0 open), wing association, lot ownership, body-buy interpretation, the carry-to-settlement relationship (basis-dependent), settlement valuation.

## 4. What would move the decision
* **CONDITIONALLY READY** needs no core MISMATCH. The shortest path is data, not code: parent-order ids and sub-second timestamps would let the D0 sales, stops and wing association be identified or rejected; without them a D0 behaviour model cannot be validated.
* A **research choice for Rahul**: alpha research needs an execution *policy* to be tested against. If the D0 expiry-day behaviour of the original is out of scope for the alpha study (e.g. alpha is built only on D-1 entries with own exits), the relevant components are S5/S8/S9/S11/S17 (PARTIAL/MISMATCH) and S1–S3 (MATCH); this milestone does not make that scoping decision and does not claim parity for the part left out.
* Rahul's caution is built into the harness: any alpha result must be reported per expiry structure (`HISTORICAL_REGIME_ROBUSTNESS.md`), never pooled over three years.

## 5. Priority data requests (each tied to the question it answers)
| # | Field | Question it answers (`UNRESOLVED_EXECUTION_RULES.md`) | What changes if we get it |
|---|---|---|---|
| 1 | **Parent-order / strategy-basket ids** on every order | U6, U10, U11, U3: which orders belong to one decision; whether D0 sales are replacements, scheduled actions or reductions; which wing belongs to which body | S7, S10, S11, S13, S14 become testable; defines the unit of an "event" |
| 2 | **Child-fill allocation linkage** (which entry lot each closing fill closed) | U1: lot ownership (89 % ambiguous today) | removes the allocation range; makes per-lot stop reference (own vs cheapest) testable (S15) |
| 3 | **Sub-second (ms/µs) timestamps** on fills, and order-acknowledge times | U13, U8, S4, S16: ordering inside a second; whether stop decisions at the open precede the first bar | makes within-poll module order and the 8-of-11 stops at the open testable |
| 4 | **Pre-log opening positions** for the 5 cycles with a missing D-1 or D0 log | U2, U5: body-buy interpretation (long vs close of an unrecorded short); start inventory | inventory path becomes testable for all 35 cycles |
| 5 | **Order status and modification history** (new/replace/cancel/reject, limit price, validity) | U4, U10: rejected/cancelled intents, retries, marketable-limit behaviour in illiquid minutes | separates "no decision" from "decision that did not fill"; informs the NO_MARKET policy (DR-X5) |
| 6 | **Risk-engine configuration and trigger log** (stop type, reference, threshold, poll) | U7, U8, U9: per-lot and cycle stop definitions; flatten cut-over date | settles S15/S16/S17 directly |
| 7 | **Wing/hedge association identifiers** | U3 | bounds replaced by a relation |
| 8 | **Exchange settlement prices** for expiry days | U12 | settlement row becomes testable |
| 9 | **Original records for earlier years** (even one expiry-structure block) | U14, historical parity | only then can "behaviour was the same in 2024-25" be tested instead of assumed |
