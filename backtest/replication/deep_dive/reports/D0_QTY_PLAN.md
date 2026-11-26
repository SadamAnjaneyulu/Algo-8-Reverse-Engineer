# D0 quantity: lot sizes, order execution, and position management — plan

*Written before the tests below. In-sample discovery on D0 (`dayno == 1` in `bl_all_orders`: 29,959 orders, 49,997 lots, 32 cycles; NIFTY and SENSEX; D0 minute bars from `bl_d0_spot/opt`). Builds on `D0_SELLS`, `D0_BUYBACKS`, `D0_HEDGE`, `D0_STOP_CLEAR`, `D1_LOTS`. D-1 (`dayno == 0`) is used only as a comparison column.*

## Requirement lock
* **Objective:** describe, and where possible predict, *how many lots* the system trades at each decision on D0, *how the orders are sent and filled*, and *how the open position (short and long lots per right) is managed*.
* **Out of scope (already done):** *whether/when* an order happens (selling AUC, buy-back AUC, stop, clearance). Here the event is **given** and the question is its **quantity and execution**.
* **Unit:** lots (NIFTY 65, SENSEX 20 contracts; gcd check repeated for D0). Prices in ₹ per contract.
* **Data limits:** one-minute bars only; the order log has second timestamps, limit price, validity, fills, partial fills. No ticks, no rejects, no account capital or margin.
* **Metrics (no others added):** exact-match rate of the lot count, mean absolute error (lots), within-±1 rate, Spearman ρ; lot-weighted shares; medians and quantiles. Baselines are stated per test. Cycle-bootstrap 95% CI where a rate is compared with a baseline.
* **No acceptance gate is set for quantity by you.** I report against baselines. A rule is called **"found"** only if the stated per-test criterion below holds out-of-fold; otherwise **"associated"** or **"unresolved"**.

## Part A — order execution (what the order looks like)
* **A1 Size and splitting.** Lots per order and per *event* (orders of the same class, right and strike within ±2 s) by class, underlying, month. Largest order quantity per underlying per month vs the exchange freeze quantity of 27 lots NIFTY / 50 lots SENSEX (D-1 engine assumption). *Question: is a large event cut into freeze-sized orders, and did the freeze change in October (order quantity 3,510 in D-1 October)?*
* **A2 Limit price rule.** For every order, `buf = lim_px / px_first − 1` (buys) and `1 − lim_px / px_first` (sells), where `px_first` is the first fill price. By class, side, validity, price level. Does one constant buffer fit (CV of buf, share within ±1 tick of `round(px_first × (1 ± b))`)? A pre-look at all orders shows a median buffer of about **15%** on every class and on both days, against the **1%** I put in the D-1 engine. A2 checks whether that holds per class and price level and whether it is **protective padding (fills at LTP, limit far from it)** or a real price decision. The result may require correcting the D-1 engine default; if so I will say so.
* **A3 Order type.** DAY vs IOC by module/class; whether every IOC fills in full; partial-fill rate and what the remainder does (next order? same second?).
* **A4 Fill quality against the bar.** Where `px_first` sits in the one-minute option bar (open/high/low/close position, share outside [low, high]), by class. Fill latency `fill_secs`. For the later backtest this answers: *which price to charge for each class* (bar close, open, mid, or a stress-shifted value).
* **A5 Dripping.** For multi-lot events: number of orders, gaps in seconds, lots per order, same-second share, by class. (D-1 found solo lots dripped over ~5 s.)

## Part B — lots per event (given the event)
Classes (D0): scheduled pair, strangle pair, other pairs (re-centre/breakout/opening), solo (opening, counter-sell, replacement, extreme, late, far-OTM, other) from `bl_d0y_types`/`bl_d0n_orders`; body buy-back events (stop-loss, take-profit, burst, clearance 15:09+ and stop module); hedge wing buy and sell waves; lump salvage; opening wings; stop liquidation.
* **B1 Descriptives:** lots per event by class: median, IQR, 90th/99th percentile, share of single-lot events.
* **B2 Fixed-size classes (test for a constant):** scheduled pair = 1 CE + 1 PE (share exactly 1+1 at the timetable cell); hedge wave = gap S−L (already 94%, re-measured here on D0 per underlying); clearance = all open shorts at that time; lump sale wave ≤ long excess (re-measured). *Found if ≥ 90% of events fit exactly.*
* **B3 Variable-size classes (solo, counter-sell, re-centre, buy-back burst, opening wings, lump release):** leave-one-cycle-out (LOCO) gradient boosting on **decision-time** features (bars to j−1 and orders strictly before the event): depth of break beyond the 60-min extreme, spot move, premium level, book (S, L, balance, per right), minutes since last event, clock, underlying/version, and for counter-sells the size of the other-right buy-back. Targets: lots (count), log lots. Metrics against three baselines: (i) class median, (ii) size of the previous event of the same class in the cycle, (iii) cycle-permuted placebo. **A size rule is "found" if out-of-fold MAE is ≥ 20% lower than the best baseline *and* ρ ≥ 0.5; otherwise "associated" (ρ ≥ 0.3) or "unresolved".**
* **B4 Size relative to the book.** For buy-backs and counter-sells: lots vs lots open on the right (share, 5/10/25%), vs lots stopped in the same second (ratio), vs lots sold in the previous 5/15 minutes. Does the buy-back burst take a fixed fraction of the right's lots? (D0_BUYBACKS: median 10%, IQR 6–22%, not a constant.)
* **B5 Premium-weighted size.** Whether lots scale inversely with premium or notional (e.g. constant ₹ premium per sale, or constant notional) within a class: Spearman of lots with premium and with notional, by class.

## Part C — position management (inventory)
Using the real order sequence: `S_after`, `L_after`, `net_after` per order per right, rebuilt by cycle and minute and cross-checked against `bl_d0b_book`.
* **C1 Level and shape:** per cycle, per right: shorts S, longs L, gross premium-weighted exposure; opening carry from D-1, peak, time of peak, end-of-session; distribution across cycles and underlyings.
* **C2 Ceiling test.** Is there a hard cap? Per cycle the peak S per right; the **normalised** peak (lots × premium, lots × notional); compare the spread across cycles with the spread across minutes. *A cap is "found" only if the peak S (or one normalised version) is within ±10% across ≥ 70% of non-stop cycles of one underlying and version, and the sale hazard drops by ≥ 50% when S is within 10% of it.* Otherwise: no cap observed.
* **C3 Inventory feedback on selling.** Hazard and size of body sells per minute versus S on the same right and versus the CE–PE lot imbalance, controlling the clock and spot move (LOCO model with and without book features: the family is "informative" if it adds ≥ 0.02 AUC with lower CI > 0.55, as in `D0_CTRIG`).
* **C4 Balance.** CE vs PE shorts: median ratio, time series, whether solo/counter sales move it toward balance (sign of change in |S_CE − S_PE| after each solo sale).
* **C5 Hedge ratio.** L/S per right over the day (D0: 95% of quiet moments L=S); where it deviates (lump, clearance) and for how long. Margin-benefit view: premium collected vs wing cost paid (wing cost as % of premium sold).
* **C6 Exposure at the stop and at the clearance.** Lots, premium and MTM at the stop minute (11 cycles) and at 15:09; what the stop liquidation sizes look like (orders, lots per order, seconds).

## Rules for reading results
* Fixed gradient-boosting settings as before (200 iters, depth 3, lr 0.05, min leaf 50, L2 1.0), out-of-fold by cycle, no tuning on test cycles.
* Any step added after seeing results goes in an **addendum, labelled post-hoc**.
* Evidence labels: Observed / Inferred / Unresolved / Not testable.
* **Not testable here:** the intra-minute path that sets drip counts, exchange freeze circulars (I will report observed maxima, not the rule), account capital or margin, broker rejects.
* **Backtest consequence to be stated at the end:** a table "what price and what quantity the free-run simulator should use per class", with the evidence level of each.
