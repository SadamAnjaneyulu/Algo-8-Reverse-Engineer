# Pre-registration (written before any in-sample grid result was looked at)

Engine under test: `portfolio_engine/construction` (Python reference + C++ runner), unmodified except for the added `capital_stop` plugin (Python + C++, 5 tests).
Data: dataset commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b` (`data/market_context_3yr_broad`), validation reports `data_validation/reports/`.
The only results seen before this file: a 2-configuration end-to-end check (HOLD and `cut_t5000_f10000_re_cd1800`) on in-sample cycles, used to verify that the pipeline runs and that Python and C++ agree. No out-of-sample number has been displayed; the pilot engine files were deleted.

## Decisions taken with the user (2026-11-18)
Basket construction = Algo 8 observed structure (rulebook v0.6); both expiry-day exits are reported; the stated 4 % / 1 % capital stops are implemented as the extra plugin and reported with and without.

## Cycles
One cycle = one weekly expiry: sessions D-1 and D0. Used if and only if the validation status is *Complete* (no missing/partial/outage/special-session cycles). Split by D0: **IS** D0 <= 2025-11-17, **OOS** 2025-11-18 .. 2026-11-17; a cycle whose D-1 is IS and D0 is OOS is dropped (embargo). IS starts at the first available session (NIFTY 2023-11-08, SENSEX 2024-05-30). OOS sub-sets: exposed (D0 2026-06-22..2026-10-22, inspected during Algo 8 reverse engineering), clean-before (D0 before 2026-06-22), clean-after (D0 after 2026-10-22).

## Basket construction (feeds the engine as seed fills; NOT part of the engine)
Decision 09:16 on D-1. K = step x floor(S/step + 0.5), S = close of the 09:15 spot bar (previous completed minute), step 50 (NIFTY) / 100 (SENSEX). Short CE and PE at K. Long wings at K + W (CE) and K - W (PE), W = 2,000 (NIFTY), 4,000 (SENSEX; 2,000 from 2026-09-16). 3 lots per leg, lot size inferred per session from the gcd of option volumes. Each leg is entered at the open of the first bar in 09:16..09:20 with volume > 0 (legs may enter at different minutes). A wing with no traded bar in that window is replaced by the nearest strike toward ATM that has one (recorded as `substituted`); a short leg without one makes the cycle infeasible. Marks fed to the engine = close of each completed 1-minute bar (timestamp = bar start + 60 s), so a plugin at tick t sees only bars completed by t. The engine evaluates plugins at every minute from 09:17 on D-1 to 15:30 on D0 (15:25 in the flatten variant).

## Exit variants (both reported)
HOLD_SETTLE: carry to expiry, cash-settle at the official close (15:30 spot bar; else Yahoo daily close; else 15:29 bar; source recorded per cycle). FLATTEN_1525: engine ticks stop at 15:25 and any open inventory is closed at the 15:25 mark with slippage and costs.

## Execution and costs (accounting layer; the engine has none)
Gross = engine reference prices (bar open for entry, last completed close for plugin actions) + settlement. Net = same trades at execution prices, minus costs. Base slippage per order = max(Rs 0.10, 0.5 % of price) against the order. Costs: Rs 20 brokerage per order, NSE 0.035 % / BSE 0.0325 % transaction charge, SEBI 0.0001 %, stamp 0.003 % on buys, GST 18 % on (brokerage + transaction + SEBI), STT on sells 0.0625 % (before 2024-10-01), 0.1 % (to 2026-03-31), 0.15 % (from 2026-04-01); exercise STT on long ITM at settlement 0.125 % / 0.15 % from 2026-04-01. Rates other than the 2026 STT change are quoted from memory and unverified. Margin = worst-case expiry loss of the open positions (premiums ignored): a proxy, not exchange SPAN. Capital for returns = Rs 2 crore (stated in Info.txt), constant, no compounding, risk-free rate 0.

## Configuration grid (26) and selection
`HOLD` (no plugin acts); 18 cut configurations `cut_t{5000,10000,20000}_f{10000,5000}_re_{none,cd1800,cd1800band}` (basket_cut MARK_ADVERSE_MOVE on SHORT legs, LEG scope, trigger = mark >= entry x (1 + trigger_bp/10000), cut fraction 100 % or 50 % of the leg, one cut per leg; basket_reentry cooldown 1800 s, price condition none or within 2000 bp of the cut price); `STOP_ONLY` and 6 `..._re_none_STOP` configurations (capital_stop: carry limit = 4 % of the basket margin proxy at entry, expiry-day limit = 1 % x Rs 2 crore; these readings of the stated percentages are UNRESOLVED and are a documented choice; stop is never combined with re-entry).
**Selection rule (per exit variant, in-sample only):** among the 26 configurations choose the one with the highest total in-sample NET P&L (NIFTY + SENSEX pooled, base costs). It replaces HOLD only if (a) its pooled net P&L exceeds HOLD's, and (b) it has positive pooled net P&L in at least 2 of the 3 chronological thirds of the in-sample period (by D0 date, equal numbers of cycles); otherwise HOLD is frozen. Ties: fewer engine orders. Walk-forward (reported, not used to choose): 4 expanding folds, validation blocks 2024-11-18..2025-02-17, 2025-02-18..2025-05-17, 2025-05-18..2025-08-17, 2025-08-18..2025-11-17, the rule applied to all earlier in-sample cycles.
The frozen configuration, parameters, code commit and data commit are written to `FROZEN_CONFIG.json` and committed before any out-of-sample accounting is run. The out-of-sample run has no tuning step.

## Stress scenarios (applied to the frozen configuration and HOLD; defined now)
Slippage x3 (max(Rs 0.30, 1.5 %)); slippage x6; costs x2; execution delay 1 and 3 minutes (re-priced at the mark that many minutes later); missing observations (20 % of bars removed at random from the marks fed to the engine, fixed seeds); reduced liquidity (slippage x3 plus 3-minute delay); position size 1 and 6 lots; volatility regimes (cycles split in terciles of the D-1 spot range); worst cycles and concentration (top-5 share of wins, P&L without the best 5 and worst 5 cycles).

## Python / C++ validation
Every engine run is executed by both implementations on the identical scenario text; parity = all seven output files byte-identical (decisions, actions, states, lineage, events, instruments, summary).
