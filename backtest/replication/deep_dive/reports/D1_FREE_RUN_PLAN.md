# Complete D-1 reconstruction vs the real ledger — free-running accuracy: plan

*Written before running. In-sample (D-1 of 32 live cycles). The earlier AUCs scored minutes given the real book. This study **simulates D-1 order by order from the market data alone** (spot and option one-minute OHLC) and compares the simulated orders with the real ledger.*

## What is simulated (only decoded rules; the real orders are never used in free-running mode)
| Class | Rule used |
|---|---|
| Scheduled pairs | The version timetable (33 waves), 1 CE + 1 PE at ATM of the previous close |
| Reactive pairs | Break of the previous two clock-aligned 30-minute candles (true high/low), 10:30–15:15; pair size from the break depth; attached favourable-side extras (`D1_SELLING_RECONSTRUCTION` §0B) |
| Stand-alone solo | Spot ladder 0.2 step with a fresh 60-minute extreme gate (fixed at the config chosen earlier); strike = premium nearest the previous sale on that right |
| Body buy-back | Each sold lot is bought back in the first minute whose **previous completed close** is ≥ θ × its own entry price (D-1 buy-backs are minute-clocked). θ from {1.3, …, 2.0} chosen on the other cycle half (decoded only as a graded stop in `BODY_CLOSE_LOGIC`: this is the weakest module) |
| Hedge wings | After the minute's body orders, buy the gap S − L (short lots − non-lump long lots, per right) in one order at the OTM strike whose previous-minute close is nearest **2.5%** of the ATM same-right previous-minute close (k fixed from `D1_LONG_SIDE`); if L > S, sell the excess from the outermost wing |
| Opening wings | 3 CE + 3 PE in the first three scheduled-wave minutes, at the median real offset (steps from ATM, per underlying, other cycle half) |
| Overnight lump | Time = the date regime's median minute; heavier short side (simulated book); lots = ratio × heavy-side shorts (median ratio per underlying, other half); strike 2.2 σ√T OTM |

**Not modelled (kept in the recall denominators):** deep-OTM batch sells, after-15:00 solo sells (an optional post-hoc variant adds the R3 rule), body-stream wing closes (`num` close_long), the stop (`s_`) and manual (`m_`) modules, hedge `cover_short`.

## Matching and metrics
* Real and simulated orders are split into lots. One-to-one matching per cycle, class and right; same minute first, then ±1 minute (lump: up to ±3 minutes, as its time is a window).
* **Timing score:** precision, recall, F1 per class and overall (micro over all real D-1 lots: every class, including the not-modelled ones).
* **Strict score:** a match counts only if the strike is also exact. A **within-one-strike** score is also reported.
* **Book score:** at each full hour and at the D-1 close, simulated vs real short lots S and long lots L per right (MAE in lots and correlation across cycles); at the close, the contract-level overlap of the carried book (shared lots ÷ real lots, same contract and sign). This is the book carried into D0.

## Parameters and variants
* Parameters (reactive size, extras, θ, lump ratio, opening offset) are fitted on one cycle half and scored on the other (two folds).
* **FR (primary):** everything free-running.
* **TF-hedge:** the hedge classes run on the **real** body orders, which isolates the hedge module's own accuracy.
* **FR + late R3 (post-hoc):** adds the after-15:00 rule (spot or premium fresh 15-minute low → 1 ITM lot).

## Not testable
The exact fills and seconds, the original margin and risk inputs, and the order of events inside a minute.
