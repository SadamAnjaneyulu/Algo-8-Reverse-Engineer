# Why does the premium exist, and why this inventory architecture? — plan

*Written 2026-11-24 before any of the tests below. Follows `DESIGN_THESIS.md`. All cycles have been used before: **exploratory**. Tests, predictions and reading rules are fixed here.*

## Question A — why is near-expiry premium rich?
Four candidate mechanisms. Each predicts a different signature in the 3-year chain data (275 cycles; segments D-1 day, overnight, D0 day as in `DESIGN_THESIS_PLAN.md`; implied variance from the ATM straddle, clock-free; realised from index minute returns).

| # | Mechanism | Test | Signature if it is the main reason |
|---|---|---|---|
| A1 | **Jump / tail compensation**: sellers are paid for rare large moves | Split realised variance into a **continuous** part (bipower variation, BV = (π/2)·Σ\|r_t\|\|r_{t−1}\|) and a **jump** part (RV − BV, floored at 0; the overnight gap is all jump). Report BV ÷ implied and RV ÷ implied; the per-cycle ratio distribution (median vs mean, share of cycles with ratio > 1); the share of total realised variance from the top 10% of cycles; skewness of the segment short-straddle P&L | Continuous variance far below implied; a small share of cycles carries much of the realised variance; median ratio well below the mean ratio; negatively skewed P&L |
| A2 | **Closed-market (overnight) uncertainty / calendar-time pricing** | Overnight segment by calendar gap: 1 day (258 cycles) vs 2–4 days (18). Implied overnight variance consumed and realised gap variance in each group | Implied overnight variance rises with calendar days while realised does not ⇒ lower ratio over weekends/holidays (descriptive: 18 cycles) |
| A3 | **Demand pressure for options** (net buying by option buyers) | (i) **Natural experiment:** SEBI circular of 1 Oct 2024, effective **20 Nov 2024** (contract size ₹15 lakh, one weekly index per exchange, expiry-day ELM on shorts) — a known date, not chosen from data. Compare variance ratios and ATM option volume (D-1 09:15–10:15, in index units) before vs after, per segment and index. (ii) **Pre-determined demand proxy:** D-1 first-hour ATM option volume relative to the index's trailing 8-cycle median, against the later segments' ratio (overnight, D0), rank correlation with a week-block permutation p-value | Volume falls after 20 Nov 2024 and the ratio rises (premium shrinks); higher pre-determined volume → lower later ratio |
| A4 | **Time-varying risk premium** | Ratio by tercile of the D-1 opening ATM implied volatility (per index) | Descriptive only: whether the premium is larger in high- or low-volatility cycles |

Reading rules: a mechanism is **supported** if its signature appears with a 95% week-cluster bootstrap interval (2,000 draws, seed 20261124) on the right side and with the same sign in both indices; **weak** if the sign is right but the interval includes the null; **not supported** otherwise. A3(i) is a before/after comparison with confounds (volatility regime, NIFTY expiry weekday change, lot-size changes), reported as such. Mechanisms are not exclusive.

## Question B — why wings, the overnight lump, hedges and stops?
Uses the saved fills of the ablation variants (`ALPHA_SOURCE_PLAN.md`): **full**, **d1_no_wings** (all D-1 longs off: opening wings, controller wings, lump), **d1_no_lump**, **d0_no_hedge**, **d1_no_stops**, **d0_no_stop_tp**, **no_cycle_stop**. Constant lot size (NIFTY 65, SENSEX 20).

**Approximate exchange margin (SPAN-like)**, evaluated at every 15th minute of both days and at the D-1 close:
* 16 scenarios: index × (1 + k·PSR/3), k = −3…3, implied volatility ± VSR, plus two extreme moves ± 2·PSR weighted 35%. Repricing with Black (r = 0), each contract's own implied total standard deviation, trading-minute clock for the volatility shift.
* Risk margin = worst scenario loss of the whole book (floored at 0). **Exposure margin** = 2% of notional (index × units) of short options, plus 2% on D0 for cycles expiring on or after 20 Nov 2024. Premium is not netted.
* **The NSE price scan range could not be verified** (sources give 3.5σ-based and "6σ·√2, minimum 9.3%" bases). Grid **PSR ∈ {4%, 6%, 9.3%}**, VSR = 4 volatility points (sensitivity 0 and 8). No single value is chosen; conclusions must hold across the grid to be stated.

| # | Component | Tail it may protect against | Measures (each variant vs full, paired, week-cluster bootstrap) |
|---|---|---|---|
| B1 | Wings (all D-1 longs) | Overnight gap; margin | Peak margin; margin at the D-1 close; **gap stress** of the D-1 close book: index gap ±1, 2, 3, 5% and implied vol × 1 or × 1.25 (time value kept, i.e. conservative); net P&L, P&L ÷ peak margin, worst and 5th-percentile cycle ÷ peak margin |
| B2 | Overnight lump | Overnight gap on the heavier side | Same as B1 |
| B3 | D0 hedge controller | Intraday expiry-day move | Peak D0 margin; worst D0 SPAN scenario; realised tails |
| B4 | Per-lot stops (D-1), stop/take-profit (D0), cycle stop | Trending day (path risk, not gap) | Peak short lots, peak margin, realised tails (5th percentile, worst, mean of worst 5%) |

Reading rule: a component **pays for itself after margin** if its variant's P&L ÷ peak margin is lower than the full strategy's (removing it hurts the return on margin) with an interval excluding zero, across the whole PSR grid; it **protects a tail** if removing it worsens the gap-stress loss or the realised worst/5th-percentile cycle beyond bootstrap noise.

**Not testable:** the broker's actual margin, its intraday margin calls, the real PSR history, and the designer's intent.
