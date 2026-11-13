# Milestone 1 report — shared model, deterministic replay, parity

Branch `engineering/portfolio-construction-engine-skeleton` (base TP-02 head `a5feffaf…`). Status: **M1 PASS for its own scope; the overall project is PARTIAL (M2–M6 not started).**

## Executed commands and results
| Command | Result |
|---|---|
| `cmake -S portfolio_engine/cpp -B portfolio_engine/build && cmake --build portfolio_engine/build` | built `pe_replay`, `pe_core_tests`; no compiler warnings with `-Wall -Wextra -Wpedantic` |
| `portfolio_engine/build/pe_core_tests` | **15/15** core checks passed |
| `python3 -m pytest portfolio_engine/tests -q` | **41 passed** (accounting 23, TP-01 reconciliation 13, parity 5) |
| `python3 portfolio_engine/tools/parity.py --real-full` | **126/126** valid cases dump-identical **and bit-identical**, roles identical, worst decimal diff 0; **8/8** invalid fixtures rejected by both |

## What the tests establish
* **Accounting (synthetic, hand-computed):** FIFO 260,000 / LIFO 520,000 / AVG 390,000 paise on the same fills; reversal; flagged duplicates; partial fills; expired inventory (65 units, no settlement P&L invented); `unrealized = NA` (never 0); fill applied exactly once; invariants after **every** fill on 5,000-event seeded stress.
* **Mode isolation:** mixed or wrong-mode events raise `ModeContaminationError` before anything is applied (Python and C++); outputs live in `runs/<MODE>/<run_id>/`.
* **Real data (41,421 fills, raw sha256 `86e65ab6…f528`) vs TP-01 outputs, all three conventions:** opened 1,414,545 / closed 1,377,065 / remaining 37,480 (all `EXPIRED_UNCLOSED`, 81 instruments); 23 reversal fills; realized gross ₹2,100,552 (FIFO), cash flow, remaining book value; **all 2,667 episodes per convention** (direction, units, fills, end reason, realized P&L); **every one of 41,421 per-fill roles**; the **6 tie-order-ambiguous fills** equal TP-01's `role_ambiguity_fills.csv`. The engine re-implements the documented TP-01 rule; it does not import TP-01 code, so this is an independent reproduction of TP-01's accounting, not of Algo 8's decisions.
* **Cross-language:** Python and C++ dumps are byte-identical for 14 fixtures (11 synthetic, 2 real cycles, the full ledger) × 3 conventions × 3 tie orders. Bit-identity of the AVG floating-point path is a measured result under `-ffp-contract=off` and explicit Python summation loops (Python ≥ 3.12 `sum()` compensates; the loops avoid that), not a guaranteed property across compilers.
* Full-ledger replay time (one convention): Python ≈ 0.31 s, C++ ≈ 0.20 s (includes process start and file parse for C++).

## Not implemented / mocked / synthetic
Position lifecycle API, baskets, plugins, generators beyond event generators, risk manager, execution states, charts, forensics, marks / unrealized P&L (`NA`), pybind11 (absent, not needed yet). Synthetic fixtures are `SYNTHETIC_TEST_ONLY`. The 195-unit cut/re-entry scenario is an accounting test of fills only; no cut or re-entry policy exists yet.

## Algo 8 behavior reproduced
Only **fill-level accounting** (TP-01 conventions): CONFIRMED_OBSERVATION. No entry, strike, sizing, hedge, exit, basket or re-entry behavior is implemented, so no TRIGGER claim exists. See `docs/EVIDENCE_REGISTRY.md`.

## Known limits
Charges, margin, Greeks, IV, capital are absent from the data (NOT_TESTABLE). Lot size 65/20 and tick 0.05 are data-verified (every quantity a multiple), not exchange-sourced. Integer parsing in C++ is stricter than Python's `int()` (no `+`, spaces, underscores); the shared writers never produce those.
