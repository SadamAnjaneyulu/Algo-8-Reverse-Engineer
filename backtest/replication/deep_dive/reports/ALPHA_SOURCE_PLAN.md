# Where does the edge come from? — plan

*Written before any of the tests below. Builds on `BACKTEST3Y_RESULT.md` (combined D-1 + D0 backtest) and `BACKTEST3Y_REGIME.md`. Exploratory with respect to the data (every cycle was already used); the questions and the list of variants are fixed here so that the answer is not chosen afterwards.*

## The question and the standard of evidence
**What generates the profit: (a) the volatility risk premium and time decay of short options, (b) a directional or short-horizon trend alignment of the reactive sales, (c) the management rules (stops, wings, clearance, cycle stop) that cut the left tail, (d) the timetable, or (e) my fill assumptions?** Each answer predicts a specific signature; each is tested by physics (decomposition) and by causality (remove it, or break it).

## Method 1 — physical decomposition of the P&L (no re-simulation)
For every cycle, every contract and every minute from D-1 09:15 to the D0 clearance:
`MtM change = position(t−1) × (mark(t) − mark(t−1)) + signed lots bought at t × (mark(t) − fill price)`.
The first term is the **holding P&L**, the second the **execution P&L** (fill versus the minute's close mark; it measures how much of the result depends on my fill model). The two sum exactly to the cycle's gross cash P&L (a reconciliation check).
* The holding term is split with Black–Scholes sensitivities at the previous minute (implied volatility inverted from each contract's own price; r = 6.5%, no dividend; **calendar-time** to expiry including the overnight and weekends): **delta** (Δ·dS), **gamma** (½Γ·dS²), **theta** (Θ·dt), **vega** (V·dσ), and a **residual** (what the model does not explain; its size is reported).
* Reported: totals by component; by session (D-1 day, **overnight step**, D0 day); by position type (short body lots, long wings and lump); by split (IS, OOS, rule-fitted live window); per ₹ of premium sold.
* **Reading rule:** the "alpha" is called **theta/vega (volatility premium)** if theta + vega is the largest positive component and delta + gamma net to a loss or zero; **directional** if delta is the main positive component; **execution** if the execution term is more than a quarter of the gross. The decomposition is model-based and approximate; the ablations below are the causal check.

## Method 2 — ablation (remove one rule, re-run the whole chain)
All 275 cycles (B/V2 point line, observed versions in the live window), gross and net, restated at a constant lot size. Paired difference to the full strategy with a week-cluster bootstrap 95% interval.

| # | variant | what it removes |
|---|---|---|
| 0 | full | reference |
| 1 | no D-1 timetable | scheduled D-1 straddles |
| 2 | no D-1 breakout straddles | reactive pairs on D-1 |
| 3 | no D-1 solo ladder | reactive solo sales on D-1 |
| 4 | no D-1 per-lot stops | 1.6× stop on D-1 |
| 5 | no D-1 wings | opening wings, controller wings, lump |
| 6 | no overnight lump only | the lump |
| 7 | no D0 new sells | D0 selling (carried book managed only) |
| 8 | no D0 timetable waves | scheduled D0 waves |
| 9 | no D0 breakout pairs | |
| 10 | no D0 solo ladder | |
| 11 | no D0 counter-sells | |
| 12 | no D0 per-lot stop and take-profit | |
| 13 | no D0 hedge controller | D0 wings |
| 14 | no cycle stop | the ₹1.2 lakh stop |

## Method 3 — placebos (break a rule instead of removing it)
* **P1 direction:** the D-1 and D0 **solo ladder sells the opposite right** (calls on rises, puts on falls). If the edge is trend alignment, this should turn it into a loss.
* **P2 timing:** all scheduled waves (D-1 and D0) **shifted by 37 minutes**. If the timetable is the edge, this should hurt; if the edge is "sell ATM premium all day", it should not.

## Method 4 — naive benchmark
Sell **one ATM straddle** at D-1 09:16 (strike nearest the 09:15 close, at the 09:16 open) and hold it to the D0 15:14 clearance, no management; and the same with **protective wings** at the strategy's own rule (2.5% of ATM premium). Compared per straddle with the strategy's P&L per ₹ of premium sold and per lot sold. This says how much of the edge is "being short volatility over this window" and how much is the management.

## Rules for reading the results
* A component is **"carrying the edge"** if removing it lowers the net P&L per cycle by more than its bootstrap noise; **"hurting"** if removing it raises it; otherwise **"not needed"**.
* Everything is reported gross and net; any component whose contribution only exists gross is called out.
* **Not testable here:** why the volatility premium exists, whether it persists, or anything about the real system's intent.
