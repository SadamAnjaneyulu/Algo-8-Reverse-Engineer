# Rebuilding the post-auction behaviour, then re-running the battery — plan

*Written 2026-11-24 after the diagnosis below (which compared the simulator with the real log) and before any change to the simulator. Gates of `PREPAPER_PLAN.md` are kept unchanged.*

## Diagnosis (observed; `src/bl_pc_diag.py` → `outputs/postcas/`)
After the closing auction (D0 ≥ 3 Aug 2026; 23 cycles with a real log):
* The gap is on **expiry day**: real D0 P&L ₹56.0k per cycle vs simulator ₹24.5k (D-1: ₹12.9k vs ₹7.6k). Volumes traded are similar (D0 sold 587 vs 623 lots per cycle).
* The simulator's **cycle stop fires in 12 of 23 cycles; the real one in 9**. They agree on 7; the simulator stops **5 cycles the real system never stopped** (real worst running loss in those: −₹0.72 to −₹1.22 lakh). In stopped cycles the real system did ≈ ₹1 lakh better per cycle than the simulator; in the others ≈ ₹41k worse.
* Real stop triggers sit at ≈ −₹1.36 to −₹1.47 lakh (median −₹1.44 lakh, excluding opening-gap stops); the simulator uses **₹1.2 lakh, fitted earlier** (`BACKTEST3Y_PLAN.md`).
* Post-auction session details (lump bought after 15:30, final clearance a few minutes after 15:14, derivatives trading until 15:40) are real but small, and the option cache ends at 15:29: **not modelled** (stated limit).

## The single change (R1)
**Cycle stop = the real system's observed trigger level, estimated only from the development part of the real log** (real stops with D0 ≤ 15 Sep 2026, excluding stops in the first 5 minutes of D0, which are opening-gap stops): the stops of 30 Jun, 6 Aug and 1 Sep 2026 trigger at −₹1.533, −₹1.394 and −₹1.448 lakh → **median ₹1.448 lakh, used as ₹1.45 lakh**. No other parameter changes. This replaces a P&L-fitted constant with an observed one; it is not tuned on P&L.

## Validation of the rebuild (before the battery)
Real-log cycles split in time: **development** = D0 3 Aug – 15 Sep 2026 (used only to set R1 above), **validation** = D0 16 Sep – 22 Oct 2026 (also the new B/V2 timetable), plus the pre-auction live cycles (22 Jun – 2 Aug) as a "do no harm" check. Measures, old vs rebuilt simulator, per group: stop agreement with the real log (confusion table), mean simulator gross vs mean real gross, mean absolute error per cycle, Spearman rank correlation.
**Accept R1** if, on the **validation** cycles, the mean absolute error per cycle falls **and** stop agreement does not get worse, **and** on the pre-auction cycles the mean absolute error does not rise by more than 10%. Otherwise report the rebuild as failed and keep the old simulator for the verdict.

## Battery re-run
If R1 is accepted: re-run the full battery (`PREPAPER_PLAN.md`: all 61 variants re-centred on the rebuilt base, cost and execution grid, margin model on the rebuilt fills, overfitting statistics, path and tail, capacity, margin-capped sizing) **with the gates exactly as approved**. Report old and rebuilt verdicts side by side. The 5 most recent cycles (after the real log ends) and the post-auction era are reported separately.

## Limits stated in advance
Only 11 validation cycles; the real stop level comes from 3 development stops; the simulator still earns a different share of the real P&L outside stopped cycles; nothing here is new out-of-sample evidence for the strategy itself.
