# Reconstruction Implementation Report

**Result:** the recovered rules are implemented as **separate, tested Python components** (`backtest/replication/rules.py`, `sim.py`, `data.py`). They are **not** yet integrated into the existing Python/C++ portfolio-construction engine, and there is **no C++ port and no Python/C++ parity** for them. The earlier engine, plugins, tests, data contracts and all prior results are **unmodified**. This is a deliberate scope decision, explained below, and it is the main item left against the brief's engine requirement.

## 1. What was implemented (all new files; nothing existing edited)

| Component | File | Rule IDs | Status |
|---|---|---|---|
| Full-chain per-cycle minute arrays (D-1, D0) from the pinned dataset commit | `data.py` | — | Executed; cached locally (git-ignored) |
| Pure decision rules: ladder table, nearest-strike, wing-strike by price ratio, leg-stop test, cycle-stop test, flatten minute | `rules.py` | RR-LAD, RR-STRK, RR-WING, RR-LEGSTOP, RR-CYCSTOP, RR-FLAT | Executed, 9 unit/counterexample tests |
| Cycle simulator (variants R1, R2) with fills at the bar open of minute j using decisions from minute j−1, slippage and statutory costs from the existing `bt.account.order_costs` | `sim.py` | all above | Executed on 275 cycles |
| Live-ledger decision-event extraction, position transitions, agreement metrics | `live_events.py`, `position_transitions.py`, `decision_agreement.py` | — | Executed |

Modifications to existing code: **none**. Dependencies reused read-only: `bt.cycles`, `bt.gitdata`, `bt.account.order_costs`, `analysis/load.py`.

## 2. Why the existing engine was not used (and what it needs)
The engine (`portfolio_engine/construction`) evaluates plugins at TICK times against baskets seeded by `LEG` fills, with a risk validator that treats atomic groups; the backtest drove it with **4 seed legs per cycle**. The recovered behaviour needs, per cycle, ~200–1,200 one-lot orders on a 15-minute schedule across many strikes, one wing per body lot, per-lot (not per-basket) stops, and a cycle-level liquidation. Minimum changes to integrate it:
1. a **schedule generator** producing LEG seed fills from the ladder/strike/wing rules (generators exist; new rule set required);
2. a **per-lot stop plugin** (the existing `basket_cut` acts on legs/baskets; per-lot reference to the lot's own entry needs lot-level lineage, which the engine records);
3. the existing `capital_stop` plugin already liquidates a cycle on adverse MTM — it would be configured with the LTP-MTM definition (current definition uses open-leg loss from seed entry prices; the evidence says cumulative cycle MTM including realised P&L);
4. a C++ implementation of (1)–(3) plus Python/C++ parity tests (the existing parity harness is reusable).
I judged it unsafe to port rules to C++ before their behaviour is validated; the Python reference is the place to learn which rules survive. **Parity status: not achieved for new rules.** Existing engine parity (13,525 runs) is unaffected.

## 3. Tests (`backtest/tests/test_replication.py`, 9 tests, all passing; plus 6 diagnostics tests)
* **Unit:** ladder totals (17 slots, 26 lots/leg), nearest-strike grid and half-step rounding, leg-stop boundaries, cycle-stop threshold, wing selection targeting the price ratio and staying OTM.
* **Counterexample:** leg stop does **not** fire at 1.59×; does **not** fire for entry ≤ ₹4 even at 2×; does not fire at 1.6× only for entry 4.00; cycle stop does not fire at −₹143,999.
* **Integration (real cycle, skipped if cache absent):** simulation ends flat, enters only at ladder minutes on D-1, 2 × 26 body lots, shorts sell at or below the reference, accounting identity net = gross − costs − slippage.
* **No look-ahead:** the opening strike equals the nearest strike to the **previous** minute's spot close.
* **Stop:** after a cycle stop there are no new entries and only closing actions.
* **Regression/reconciliation:** replay totals fixed (R1 gross ₹444,173 over 35 cycles); the **cash-based** gross equals the **FIFO-based** gross from an independent code path (`pnl_streams.py`); live gross ₹2,618,423.
* **Historical replay tests** are the agreement metrics in `HISTORICAL_REPLAY_REPORT.md` (they depend on the ledger, which is in the repo).

## 4. Defects found and fixed in this programme
| Defect | Effect | Fix |
|---|---|---|
| 3 simulated cycles had an unpriced first-minute fill (no trade and no prior close at the ATM strike) → NaN P&L | removed from sums by pandas; sensitivity tables skewed slightly | such orders are now skipped and counted (`skipped`) |
| First-pass test for stop-ends-entries contained an `or True` that made it vacuous | weak test | replaced with a real assertion |
| Replay event table dropped 425 fills outside 09:15–15:29 | ₹62.6 k (2.5 %) difference between FIFO and cash gross | documented; all dropped fills are 15:30–15:39 |
| **D0-open look-ahead (found by the independent review)**: at D0 minute 0 the leg-stop test and cycle-stop mark used the close of the 09:15 bar, which is the same bar the fill price (its open) comes from | R1 results were **upward-biased**: net all-cycle total ₹41.4 L → ₹28.0 L, IS net Sharpe 1.67 → 1.47, OOS net Sharpe 1.06 → 0.22; live-window gross ₹5.8 L → ₹4.4 L | fixed (`prev_px` returns the last D-1 bar close at D0 minute 0); regression test `test_causality_d0_open_decisions_ignore_same_bar_close`; the pre-fix outputs are preserved, labelled, in `results/v1_lookahead_biased/` and **must not be cited** |

## 5. Independent review
An independent reviewer (a separate agent, no edits) audited `rules.py`, `sim.py`, `data.py`. **Findings:** (1) one confirmed look-ahead (above, now fixed; the reviewer's patched re-run gave IS net Sharpe 1.468 and OOS 0.217, which my fixed code reproduces: 1.47 / 0.22); (2) it re-derived NIFTY 2026-07-14 gross (−₹24,511.50) and net (−₹34,093.51) exactly from the event list; strikes derive from the previous minute's close; fills use the bar open; leg-stop and cycle-stop use minute j−1 only after the fix; a perturbation-causality test over 11 minute offsets and 11 cycles had zero violations after the patch; (3) suspected issues recorded below. Cross-checks of my own (cash vs FIFO P&L; the earlier clone's ρ = 0.48) were **not** independent and, notably, **missed the look-ahead**.

## 6. Reviewer's lesser observations (not defects of the rule set)
* The leg-stop threshold is taken from the **slipped** entry price (slightly lower threshold → marginally more stops: mildly pessimistic).
* ₹20 brokerage per lot-order (~₹4 k per cycle): conservative if live orders aggregate lots.
* A NaN mark would silently disable the cycle stop; checked on 4,160 entries across 40 cycles with 0 occurrences (latent).
* **Calibration overlap:** the wing ratio (2.44 %), the ladder, the leg-stop band and the cycle-stop level were read from the live ledger, which overlaps the "OOS exposed" window, so that window is **not** clean for R1 either (it is clean only for the D-1/IS parts).
* Settlement uses the Yahoo close (irrelevant for R1: no lots are held).

## 7. Known simplifications in the implementation (each is a modelling choice, not an observation)
* Fill price = bar open of the decision minute ± 0.5 % slippage (min ₹0.10); real fills are marketable limits at ±15 % of LTP with unknown depth.
* One order per lot (as live); no partial fills; no latency; no market impact.
* Leg stop references the lot's **own** entry (evidence supports a 1.55–1.7× band and an unresolved reference).
* Cycle stop uses ₹1.44 L irrespective of lot size or year (constant not shown to scale).
* No lump hedge, no Clock-B, no replacement, no off-schedule sales, no D0 ladder (R1).
