# Demonstration-cycle selection — criteria (FROZEN before the selection script is run)

Purpose: choose **one NIFTY and one SENSEX** cycle for the M2 demonstration without looking at any grouping output, profit, charts or apparent strategy clarity.

## Eligibility (inclusion rule)
A cycle must have fills on **both** its pre-expiry session (D-1) and its expiry day (D0).

## Completeness score = unweighted mean of six components, each in [0, 1]
| # | Component | Definition (computed only from source availability and reconstruction quality) |
|---|---|---|
| C1 | Fill coverage | 1 − (fills with any data-quality flag or in a tie-order-ambiguous contract-second) / fills |
| C2 | Parent-order metadata completeness | share of the cycle's parent orders with non-missing order-entry minute, full app key and order number |
| C3 | TP-01 reconciliation completeness | 1 − (units left in expired contracts without settlement) / (units opened); an unclosed cycle scores lower because P&L is incomplete |
| C4 | Option-mark availability | share of the cycle's fills whose contract has an option 1-minute bar at the fill's minute (raw bars, `ALGO8_MARKET_DIR`) |
| C5 | Entry / exit classification coverage | mean of (a) share of the cycle's closing fills present in TP-02 `exit_event_mechanisms` with a non-null mechanism, (b) share of the 44 TP-03 window slots (21 pre-expiry + 23 expiry-day) present in the TP-03 Phase 1 window dataset |
| C6 | D-1 / D0 source availability | 1 if both sessions have fills (always true for eligible cycles; kept so the score is complete) |
Equal weights are used because no basis exists for unequal weights. **Tie-break:** earlier expiry date. **Not used:** P&L, win rate, drawdown, number or size of groups, cycle stops, visual clarity.

## Procedure
Run `portfolio_engine/tools/select_demo_cycles.py` once; it writes `reports/DEMO_CYCLE_SELECTION_NOTE.md` (selected cycle per underlying + the next three candidates) and the per-cycle component table. The selection is then **frozen**; it is not rerun after grouping exists.
