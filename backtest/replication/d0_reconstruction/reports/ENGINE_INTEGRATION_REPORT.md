# Engine Integration Report (Phase I, Gate 7) and Independent Review (Gate 6)

**Result: no D0 rule has been ported into the Python/C++ engine, by design.** Gate 7 requires evidence, replay and holdout gates plus independent review; none of the D0 buy-back, replacement or off-schedule rules passed, and the two that did (15:14 final-liquidation timing; the cycle stop) are not new to the engine. The existing portfolio engine is **untouched; its 180 tests still pass** (`portfolio_engine/construction/tests`, run in this phase). The separate D0 simulator remains available for comparison.

## 1. Gate status
| Gate | Status |
|---|---|
| 1 Data reconstruction | **Passed with documented exceptions** (33/35 cycles with D0, 30 with carry-in) |
| 2 Rule evidence | **Passed** (register lists supporting examples and counterexamples for every rule) |
| 3 Holdout | **Passed procedurally** (frozen and committed before evaluation; exposure disclosed; addendum 1 disclosed) |
| 4 Replay | **Passed** (chronological, perturbation-tested, no look-ahead) |
| 5 Behavioural agreement | **Evaluated; most categories fail** (holdout report) |
| 6 Independent review | **Completed — see §3** |
| 7 Engine integration | **Not entered** (no rule meets the pre-registered criteria except final-liquidation timing, with a wide interval) |

## 2. What porting would require (specification only; not implemented)
1. **Final-liquidation plugin (S4):** the engine already has an end-of-session flatten in scenario generators and `capital_stop` for the cycle stop. A D0 flatten at 15:14 would be a `scripted_actions`-style scheduled CUT of all legs plus wings; it needs no new decision logic. Preconditions: validation on an independent D0 sample (none exists) and the 15:14 minute being stable across periods (EXT-08: after 3 August only).
2. **Cycle-stop definition:** the existing `capital_stop` evaluates open-leg MTM loss from *seed entry prices*; the evidence says **cumulative cycle MTM including realised P&L** (RSK-01/09/11). A phase-aware variant would be a separate plugin with Python/C++ parity tests before use.
3. **Not portable yet:** Clock-B tick, replacement, off-schedule sale, price-stop-on-D0 plugins (triggers unknown). Porting hypotheses as production rules is prohibited by the brief.
Every future plugin must have unit, integration, historical-replay (`compare_events.py` reused as the replay test), counterexample and regression tests, and Python/C++ parity runs.

## 3. Independent review (Gate 6)
A separate reviewer agent (no edits to tracked files) audited `build_events.py`, `d0_sim.py`, `compare_events.py`, `d0common.py`, the freeze hashes and the tests. **Its findings and my responses are recorded in `INDEPENDENT_REVIEW_D0.md`** (written after the review completed).

## 4. Tests added in this phase (`backtest/tests/test_d0_reconstruction.py`, 8 tests; all passing with the earlier 16: 24)
Event table reconciles with the ledger (orders, lots, all 1,674 contract nets); every order has one class and the split boundary is respected; holdout guard raises before freeze; frozen files unchanged (with addendum); simulated start book equals ledger; D0-open decisions independent of the 09:15 bar's close/spot; flatten and stop semantics; frozen holdout results regression; lineage reconciles with live P&L.
