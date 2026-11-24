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

## Addendum 1 — in-sample / out-of-sample division (your instruction; written before any combined run)
This **replaces the "S0 / S1 / S2" split above.** The boundary is the one of the earlier backtest (`bt/config.py`): **in-sample = D0 up to 2025-11-17**. `bl_bt3_split.py` writes the label `split3` into `outputs/bl_bt3_cycles.csv`.

| split3 | meaning | NIFTY | SENSEX | cycles | D0 range |
|---|---|---|---|---|---|
| **IS** | development: may be inspected and used for the choices listed below | 105 | 70 | **175** | 2023-11-09 – 2025-11-13 |
| **OOS** | locked: after the boundary, never used for the rule fit; **run once** after the freeze | 31 | 33 | **64** | 2025-11-20 – 2026-11-12 (the 5 cycles after the live window are included) |
| **LIVE_FITTED** | 2026-06-22 – 2026-10-22: the cycles the D-1 and D0 rules were fitted on. **In-sample for the rules, not out-of-sample**, although they are later than the boundary. Used as the reconstruction check against the real P&L | 18 | 18 | **36** | 2026-06-23 – 2026-10-22 |
| EMBARGO | D-1 in IS, D0 after the boundary | 1 | 0 | 1 | 2025-11-18 (excluded from both) |

* **What the in-sample part is for (and nothing else):** (1) debugging the pipeline and the checks V2–V3 below; (2) the **one** development choice left open: **which timetable version to use as the point line for dates before June 2026**, chosen by a rule fixed now: *the version (A/V1 or B/V2) with the higher mean net P&L per cycle on IS, both indices pooled*. The other version is still reported next to it as the band. Nothing else is tuned on IS.
* **Primary result = OOS (64 cycles), run once with the frozen configuration and the selected timetable version.** The IS result is reported as the development result. With 64 cycles the intervals will be wide; the report will say so.
* **If anything is changed after the OOS result is seen, OOS stops being independent and is labelled CONTAMINATED OOS.**
* The earlier sentence "S1 pre-live hold-out is the primary result" no longer applies: the pre-live cycles are split into IS (up to 2025-11-17) and OOS (after it).

## Addendum 2 — fill-pricing amendment found in the in-sample development run (written before the OOS run)
* **What I found.** The first in-sample run (IS, 175 cycles) gave profit factor 3.1 and a weekly Sharpe of 3.5 gross, far above what the real system's own cash P&L suggests. An audit of the pricing showed two look-ahead biases in the fills I had inherited from the research simulators (which were built to match *timing*, not to value fills):
  1. **Reactive sells** (spot ladder, breakout pairs, counter-sells in D0; breakout straddles, extras and ladder in D-1) are triggered by the current minute's high or low but were filled at the **previous** minute's close (D0) or the minute's open (D-1), i.e. before the move that triggered them.
  2. **Stop and take-profit buy-backs** are triggered by the minute's high or low but were filled at the minute's **close**, which can be far below the stop level.
* **Amendment (the fill model of the headline from now on, `causal=True`):** reactive sells at the **close of the trigger minute**; scheduled (timer) sells unchanged; **stop buy-backs at the stop level, or the minute's open if it gapped above, capped at the minute's high**; take-profit buy-backs at the take-profit level, or the open if lower, floored at the minute's low; everything else unchanged. Decisions (timing, strikes, sizes) are unchanged.
* **Effect on the in-sample result** (mean per cycle, version A/V1): gross ₹1.13 lakh → ₹0.87 lakh, net ₹68k → ₹42k; version B/V2: gross ₹1.39 lakh → ₹1.06 lakh, net ₹90k → ₹57k. **The first in-sample numbers are withdrawn;** the legacy-pricing files are kept as `*_LEGACY_PRICING.csv` for the comparison only.
* **Verification kept:** with `causal=False` the refactored D0 simulator is **identical to the earlier simulator on 49 of 49 live test cycles** (P&L difference ~1e-16, `outputs/bl_bt3_identity.csv`).
* **Version selection (the rule fixed in Addendum 1, applied to the amended model):** IS mean net per cycle A/V1 ₹42,430, B/V2 ₹57,403 → **B/V2 is the point line** for the OOS run; A/V1 is run and reported next to it as the band.
* **Frozen before the OOS run:** simulator code at the commit that contains this addendum, `bl_bt3_frozen.json` / `bl_bt3_frozen_waves.csv` (D0 parameters fitted on the 30 live cycles), the cost model of `bt/account.py`, the stress definitions above. **Not yet done:** the day-shifted placebo (needs sessions other than D-1 and D0, which the cycle cache does not hold); it is reported as outstanding.
* **OOS protocol:** `bl_bt3_run.py OOS B/V2` and `OOS A/V1`, `bl_bt3_stress.py`, `bl_bt3_metrics.py OOS`, each **once**. Any code or parameter change after the OOS result is seen makes the OOS **CONTAMINATED**.
