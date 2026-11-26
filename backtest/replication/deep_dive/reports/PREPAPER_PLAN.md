# Pre-paper-trading validation battery — plan

*Written 2026-11-24 before any of the runs below. Decisions taken by you: sizing **both** constant-lot and margin-capped; costs **verified schedule + stress grid**; tests **parameter sensitivity, overfitting statistics, path & tail risk, liquidity & capacity**; gates **pre-registered by me, approved or changed by you before the runs**. Every cycle has been used before: this battery measures robustness of the reconstructed strategy, it is **not** new out-of-sample evidence.*

## Requirement lock
| Item | Locked value |
|---|---|
| Strategy | Combined D-1 + D0 simulator (`bl_bt3_sim.py`), timetable B/V2 point line, observed versions in the live window; frozen parameters `bl_bt3_frozen.json` (identical to `BACKTEST3Y_RESULT.md` and the ablation "full" run) |
| Data | 275 complete cycles, Nov 2023 – Nov 2026 (IS 175 / OOS 64 / rule-fitted live 36), one-minute D-1 and D0 option chains |
| Execution | Causal fill pricing as in `BACKTEST3Y_PLAN.md` Addendum 2 |
| Capital | ₹2 crore |
| Sizing S1 | Constant lot: NIFTY 65, SENSEX 20 units per lot (as in all earlier reports) |
| Sizing S2 (margin-capped, causal) | Cycle size multiplier s_t = min(1, ₹2 crore ÷ 90th percentile of the modelled peak margin of the **previous 8 cycles of the same index**) (s = 1 until 4 earlier cycles exist). P&L, costs and margin scale by s_t, except brokerage per order (fixed per order). Margin = the approximate SPAN model of `UNRESOLVED_THREE.md` (scan range 9.3% floor — unverified). This is a **new rule**, not something the real system is known to do |
| Costs (verified schedule) | Brokerage ₹20 per order; GST 18% on brokerage + exchange + SEBI fees; SEBI ₹10 per crore; stamp duty 0.003% on buys; **exchange charges NSE 0.0495% of premium before 1 Oct 2024, 0.03503% from then (sensitivity 0.03553%, the figure on Zerodha's current pricing page); BSE 0.0325%**; STT on option sales 0.0625% → 0.1% (1 Oct 2024) → 0.15% (1 Apr 2026). Sources: Zerodha charges / bulletins, HDFC Securities, Angel One, Business Standard, Business Today. **Change vs earlier runs:** NSE exchange charge before Oct 2024 was 0.035% in the code (understated) |
| Slippage | max(₹0.10, 0.5% of price) per side per fill (an assumption, not verified) |
| Funding | Not charged in the baseline; the opportunity cost of ₹2 crore at 6.5% a year (≈ ₹12.5k per cycle) is reported as a sensitivity |

## The battery
**B1 Costs and execution (re-pricing the saved fills; the path is not re-simulated):** costs × 1 / 1.5 / 2; slippage × 1 / 2 / 3 / 6; fills delayed by 1 and 2 minutes; fills at the realistic in-bar position (sells at 30%, buys at 62% of the minute range); joint break-even multiplier (costs and slippage scaled together until the mean net is 0) and break-even slippage per side.
**B2 Parameter sensitivity (full re-simulation, 275 cycles each):** one at a time, ±20% and ±40% of the excess over 1 for ratios and of the value otherwise:
| Parameter | Frozen value | Perturbed on |
|---|---|---|
| D-1 per-lot stop ratio | 1.6 | excess 0.6 |
| D-1 ladder step | 0.2 strike steps | value |
| D-1 wing budget | 2.5% of ATM premium | value |
| D-1 lump ratio | 0.827 | value |
| D0 stop ratio (θ) | 1.4 | excess 0.4 |
| D0 take-profit | 0.10 | value |
| D0 ladder step | 0.05 strike steps | value |
| D0 counter-sell ratio | 0.25 | value |
| Cycle stop | ₹1.2 lakh | value |
| Wave timing (D-1 timetable and D0 waves together) | as frozen | ±5, ±15 minutes |
**B3 Overfitting statistics:** (a) **Deflated Sharpe Ratio** of the weekly net series, with N = the number of distinct configurations run on these cycles in this project (counted from the outputs; N = 1,000 as a stress value) and the variance of Sharpe across the B2 variants; (b) **Probability of Backtest Overfitting** by combinatorially symmetric cross-validation over the B2 variants + the full strategy (weekly returns, 16 blocks, all 12,870 splits); (c) **random-timetable null:** 20 runs with the D-1 timetable and D0 wave times drawn at random (same counts, same session span), everything else unchanged — where does the real timetable's mean net fall in that distribution?
**B4 Path and tail risk:** weekly net series (both sizings): maximum drawdown and time to recover; stationary block bootstrap (4-week blocks, 10,000 one-year paths): distribution of one-year P&L and maximum drawdown, probability of losing ≥ 10 / 20 / 30% of ₹2 crore within a year; ten worst cycles (date, size, cause); scenario shocks on the carried overnight book: implied volatility × 1.5 and × 2 with no gap, and the ±3/5/10% gap grid from `UNRESOLVED_THREE.md`.
**B5 Liquidity and capacity:** for every simulated fill, lots × lot size ÷ that contract's traded volume in the same minute (raw volume from the chain files); share of fills above 5 / 10 / 25% participation; same at 2× size; P&L at 0.5× and 2× size with slippage scaled by size (proxy, labelled as such).

## Gates (pre-registered defaults — to be approved or changed before the runs)
| Gate | Pass condition |
|---|---|
| G1 Costs | Mean net per cycle > 0 under the verified schedule (all 275 cycles **and** the 64 OOS cycles), and > 0 under costs × 1.5 with slippage × 2 |
| G2 Execution | Mean net > 0 with fills delayed by 1 minute |
| G3 Parameter stability | No ±20% single-parameter change (or ±5-minute timing shift) turns the mean net negative or cuts it by more than half |
| G4 Overfitting | PBO < 0.5 **and** Deflated Sharpe ≥ 0.95 at the counted N |
| G5 Noise floor | The real timetable's mean net is above the 95th percentile of the random-timetable null |
| G6 Path / tail | One-year bootstrap: 95th-percentile maximum drawdown < 20% of ₹2 crore (₹40 lakh) **and** probability of a one-year loss > 10% of capital < 10% |
| G7 Capacity | ≥ 90% of fill volume at ≤ 10% of the contract's minute volume at baseline size |
| G8 Margin-capped book | Mean net > 0, and ≤ 5% of cycles still above ₹2 crore of modelled peak margin |

**Verdict rule:** all gates pass → **GO to paper trading** (with the forward-test design written into the report); any gate fails → **NO-GO** with the failing gates and what would have to change; the decision stays yours. A gate result is a statement about this simulator and these 3 years, not about the future.

## Honest limits stated in advance
* The simulator earns ≈ 36% of the real system's P&L on the 32 live cycles: the battery tests the **reconstruction**, not Algo 8 itself.
* B1 re-prices fills without re-simulating the path (stops would trigger differently under real slippage).
* Margin uses an unverified scan range; the gap tail beyond 3 calm years is not in the data.
