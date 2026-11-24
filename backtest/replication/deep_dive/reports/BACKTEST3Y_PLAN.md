# Combined D-1 + D0 backtest on the 3-year data — pre-registration

*Written before any combined simulation has been run. Nothing below has been tuned on a cycle outside the 32 live cycles. Builds on `d1_strategy/` (D-1 rules and engine), `D0_FREE_RUN.md` / `D0_SIZING.md` (D0 simulator and sizing), `D0_QTY.md` (execution), the validated dataset (`data_validation/reports/B_COVERAGE_REPORT.md`) and the accounting layer of the earlier `backtest/` (`bt/account.py`).*

## What this backtest is, and is not
* **Is:** a test of whether the **reconstructed** rules, run as one strategy per weekly expiry (D-1 session, overnight carry, D0 session), make money on 3 years of one-minute option data, how stable that is, and how sensitive it is to costs and fills.
* **Is not:** (a) a test that the reconstruction matches what the real system did in earlier years (there are no real orders before June 2026); (b) evidence that the 2026 system existed, or ran these rules, earlier; (c) a deployment decision.
* **The real system's own result is the benchmark where it exists:** on the 32 live cycles the real cash P&L before costs is ₹20.7 lakh (mean ₹0.65 lakh per cycle); the real order count is about 1,136 per cycle, which at the earlier cost model costs ₹9.7 lakh (46% of that gross) before slippage.

## Strategy definition (frozen before the run)
| part | specification | source |
|---|---|---|
| D-1 | `d1_strategy.algo8_d1.D1Strategy` with `config_for(underlying, d1_date)`: scheduled straddle waves (33), clock-aligned breakout straddles, solo ladder, per-lot stop (1.6× minute high), controller wings, opening wings, overnight lump | `D1_*` reports; validated 32/32 against the research simulator |
| D0 | `bl_d0v_sizing.sim2` in mode **M0** (the simulator as in `D0_FREE_RUN`): timetable waves per underlying × version, D-1-style breakout pairs, spot ladder (0.05 step, 60-min gate), counter-sell accumulator, per-lot stop 1.4× on the minute high, take-profit 0.1×, hedge controller (2.5%-of-ATM wing), 15:14 clearance, cycle stop on cumulative MTM ≤ −₹1.20 lakh | `D0_FREE_RUN`, `D0_STOP_CLEAR` |
| Parameters | fitted **once on all 30 live cycles with both logs** (the same `fit` as `D0_FREE_RUN`, training = all), saved to `BACKTEST3Y_FROZEN.json` with the code commit **before** any run on another cycle | |
| Hand-off | D-1 orders (simulated) → carried book: short lots with entry prices, longs by module and strike, cash → D0. Module mapping: controller wings `h_`, overnight lump `v_`, opening/body longs `num`. | new adapter |
| Sizing | **M0 at the real scale** (constant lots per decision, as the real system trades) as the point result; **A (10 draws per cycle)** as the sizing-uncertainty band | `D0_SIZING` |
| Stops stated by the owner | `Info.txt`: 4% carry stop on carried positions, 1% of ₹2 crore capital on expiry day. Primary run uses the fitted ₹1.20 lakh cycle stop (`D0_STOP_CLEAR`); the stated 1% (₹2 lakh) is a sensitivity run | |

## Cycles and splits
* One cycle = one weekly expiry of one index: sessions D-1 and D0. **Used only if the validation status is Complete** (`bt.cycles.cycle_list`): about 155 NIFTY and 121 SENSEX cycles, 2023-11 to 2026-11. SENSEX starts 2024-05-31 (earlier SENSEX data are missing). No cycle is dropped after seeing a result.
* **S0 live window** (D0 from 2026-06-22 to 2026-10-22): the 32 cycles the rules were fitted on. **In-sample.** Used for the pipeline check only.
* **S1 pre-live hold-out:** every Complete cycle with D0 before 2026-06-22 (about 240). The rules were not fitted on these. **This is the primary result.**
* **S2 after the live window** (D0 after 2026-10-22, a few cycles): reported with S1 as "post".
* The earlier project's convention marks 2026-06-22..2026-10-22 as the exposed window (`bt/config.py`); the same window is used here.

## What is assumed, and how the assumption is bracketed (no silent choices)
1. **The timetables.** The scheduled-wave clocks (D-1: versions A until 2026-09-09 and B from 2026-09-16; D0: V1/V2 per underlying) were observed only in June–October 2026. **Before 2026-06-22 their schedule is unknown.** Two complete runs: (i) version A/V1 for every earlier date, (ii) version B/V2 for every earlier date. Both are reported side by side as a band; **neither is claimed to be what the system did.** S0 uses the observed version.
2. **Lot size.** The unit per session comes from the data (gcd of option volumes; the value 1 is a data artefact and is replaced by the unit of the neighbouring session). **Lots per decision are held constant** (the system's rules are in lots: one lot per wave and order). P&L is reported in ₹ and in unit-free "points × lots" so that exchange lot-size changes (NIFTY 50 → 25 → 75 → 65; SENSEX 10 → 20) do not drive the comparison.
3. **Strike step 50 (NIFTY), 100 (SENSEX)**; missing option prices at a minute are forward-filled as in the live-cycle builder; an order whose strike has no price at all is skipped and counted.
4. **Capital ₹2 crore** (stated in `Info.txt`, not verified) for return on capital; margin proxy from `bt/account.py` reported next to it.
5. **Rules found on 2026 behaviour apply to earlier markets** (volatility regimes, wing premiums, liquidity differ). Not testable; the S1 result is the evidence.

## Execution and costs (inherited, flagged)
* Fills at the simulator's prices (previous-minute close for sells, minute prices for the rest, as in `D0_FREE_RUN`), **then** the accounting layer of `bt/account.py`: slippage max(₹0.10, 0.5% of price) against every order, dated statutory costs (STT, exchange, SEBI, stamp, GST) and ₹20 brokerage **per order**. **These rates are the earlier project's, marked UNVERIFIED there** (from memory; the owner's broker terms unknown).
* **Orders are counted as the real system sends them:** body orders are single lots, hedge, lump and stop orders are sized orders (`D0_QTY.md`).
* Reported: **gross** (simulator prices, no slippage or costs), **net**.
* **Stress (defined now):** slippage ×3 and ×6; costs ×2; execution delay 1 and 3 minutes; **fills at the real position in the bar** (sells at 0.30, buys at 0.62 of the option's minute range, from `D0_QTY.md` A4) instead of flat slippage.

## Metrics (as your standing list; nothing added)
Total trades (orders), win rate (by cycle), profit factor (by cycle), Sharpe ratio (by cycle and annualised with the number of cycles per year), return (on ₹2 crore), maximum drawdown (cumulative cycle P&L), trades per day. In ₹ and in points × lots. By index, by split, by month. Cycle-bootstrap and month-block-bootstrap 95% intervals for mean cycle P&L. **No other metric is added to the headline.**

## Checks before the result is read
* **V1 pipeline check on S0:** the fully simulated D-1 → D0 chain on the 32 live cycles against the real P&L (Spearman, median error, sum) and the lot match; the separate D-1 (F1 0.63) and D0 (F1 0.41) numbers are the reference. Compounding error is expected and is reported, not hidden.
* **V2 data checks:** bars per session, strike coverage within ±10 steps of the money, missing-price counts, orders skipped.
* **V3 identity checks:** the D-1 batch run on the live cycles reproduces the earlier validation (F1 0.69 in-sample); M0 on the live cycles reproduces `bl_d0_fr_orders.pkl.gz` when fed the real D-1 book.
* **Placebo:** the same pipeline with the **day shifted** (D-1 = the session two days before expiry, D0 = the session one before) on S1 cycles: any edge that survives in that placebo is not tied to the expiry structure.

## Rules for reading the result
* **One frozen run.** No tuning on S1. Anything changed after S1 results are seen is **contamination** and is labelled; S1 then stops being an independent result.
* The point result is **M0, S1, both timetable runs, net of the inherited costs**, next to gross and the stress table. A headline that needs a favourable timetable run is reported as the band, not as the better end.
* A positive result is **performance, not robustness or a deployment case**; the research states (performance → statistical quality → robustness → paper candidate) are kept apart.
* **Not testable here:** the real broker's costs and fills, whether the 2026 system traded this way earlier, capital or margin at the real broker.
