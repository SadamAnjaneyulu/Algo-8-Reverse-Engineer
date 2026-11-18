# Python / C++ parity report
Every engine run in this study was executed by the Python reference and by the C++ runner on the same scenario text and compared file by file (decisions, actions, states, lineage, events, instruments, summary).
* Engine runs: **13,525**; byte-identical: **13,525**; differences: **0**.
| result set | runs |
|---|---|
| FLATTEN_1525 | 4650 |
| FLATTEN_1525_L1 | 275 |
| FLATTEN_1525_L6 | 275 |
| FLATTEN_1525_M20s1 | 275 |
| FLATTEN_1525_M20s2 | 275 |
| FLATTEN_1525_M20s3 | 275 |
| HOLD_SETTLE | 4750 |
| HOLD_SETTLE_L1 | 550 |
| HOLD_SETTLE_L6 | 550 |
| HOLD_SETTLE_M20s1 | 550 |
| HOLD_SETTLE_M20s2 | 550 |
| HOLD_SETTLE_M20s3 | 550 |
The 26-configuration in-sample grid x 2 exit variants x 175 cycles, the out-of-sample runs of the frozen configurations, the 1 lot / 6 lot reruns and the missing-bars reruns are all included. Plugins exercised on real data: basket_cut (side-aware, partial and full cuts), basket_reentry (cooldown and price-band conditions), capital_stop, risk validator (atomic groups).
Beyond fixture parity: the real-data runs include partial fills at different entry minutes, stale marks, carried prices, price jumps, multi-lot quantity rounding and one-per-leg cut limits, none of which the fixtures contained. No disagreement was found, so there was nothing to investigate. A byte-identical result proves the two implementations agree; it does not prove the logic is right. Correctness of the logic was checked separately: in the 38 cycles where the capital stop closed every position, the engine's own FIFO realised P&L equals the accounting layer's gross P&L to the paisa (`tests/test_backtest.py`).
