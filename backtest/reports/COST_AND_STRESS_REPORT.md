# Transaction-cost sensitivity and stress tests
Scenario definitions are in `PREREGISTRATION.md` (written before the in-sample grid). Combined NIFTY + SENSEX net P&L in rupees; `missing_20pct_bars` removes 20% of the bars fed to the engine (3 seeds): it cannot change a configuration with no plugin, so the baseline is identical by construction. Sizing scenarios rerun the engine with 1 and 6 lots per leg.
## All scenarios
| variant | config | scenario | in-sample net | out-of-sample net |
|---|---|---|---|---|
| FLATTEN_1525 | HOLD | base | 428,327 | 118,941 |
| FLATTEN_1525 | HOLD | costs_x2 | 386,294 | 91,177 |
| FLATTEN_1525 | HOLD | delay_1min | 499,536 | 138,631 |
| FLATTEN_1525 | HOLD | delay_3min | 469,234 | 124,937 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed1 | 428,327 | 118,941 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed2 | 428,327 | 118,941 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed3 | 428,327 | 118,941 |
| FLATTEN_1525 | HOLD | reduced_liquidity | 348,265 | 30,491 |
| FLATTEN_1525 | HOLD | size_1_lot | 120,749 | 27,060 |
| FLATTEN_1525 | HOLD | size_6_lots | 889,694 | 256,763 |
| FLATTEN_1525 | HOLD | slippage_x3 | 307,945 | 24,810 |
| FLATTEN_1525 | HOLD | slippage_x6 | 127,373 | -116,388 |
| HOLD_SETTLE | HOLD | base | 497,091 | 218,329 |
| HOLD_SETTLE | HOLD | costs_x2 | 473,625 | 201,721 |
| HOLD_SETTLE | HOLD | delay_1min | 568,989 | 232,023 |
| HOLD_SETTLE | HOLD | delay_3min | 538,607 | 237,389 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed1 | 497,091 | 218,329 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed2 | 497,091 | 218,329 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed3 | 497,091 | 218,329 |
| HOLD_SETTLE | HOLD | reduced_liquidity | 476,846 | 190,353 |
| HOLD_SETTLE | HOLD | size_1_lot | 154,684 | 66,483 |
| HOLD_SETTLE | HOLD | size_6_lots | 1,010,703 | 446,097 |
| HOLD_SETTLE | HOLD | slippage_x3 | 435,904 | 171,459 |
| HOLD_SETTLE | HOLD | slippage_x6 | 344,123 | 101,154 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | base | 520,143 | 67,163 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | costs_x2 | 489,348 | 43,912 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | delay_1min | 602,319 | 93,616 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | delay_3min | 580,964 | 85,734 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed1 | 507,504 | 69,872 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed2 | 520,886 | 107,845 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed3 | 514,848 | 70,831 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | reduced_liquidity | 466,096 | -9,533 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | size_1_lot | 160,448 | 14,836 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | size_6_lots | 1,059,685 | 145,654 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | slippage_x3 | 405,162 | -27,633 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | slippage_x6 | 232,690 | -169,828 |
## Clean out-of-sample (the 64 previously uninspected cycles), HOLD_SETTLE baseline
| scenario (HOLD_SETTLE baseline) | clean OOS net P&L (64 cycles) |
|---|---|
| base | 38,687 |
| slippage_x3 | 6,074 |
| slippage_x6 | -42,844 |
| costs_x2 | 27,835 |
## Per index
| variant | config | scenario | scope | in-sample net | out-of-sample net |
|---|---|---|---|---|---|
| FLATTEN_1525 | HOLD | base | NIFTY | 283,302 | 78,455 |
| FLATTEN_1525 | HOLD | base | SENSEX | 145,025 | 40,486 |
| FLATTEN_1525 | HOLD | costs_x2 | NIFTY | 258,271 | 64,661 |
| FLATTEN_1525 | HOLD | costs_x2 | SENSEX | 128,023 | 26,516 |
| FLATTEN_1525 | HOLD | delay_1min | NIFTY | 255,993 | 64,031 |
| FLATTEN_1525 | HOLD | delay_1min | SENSEX | 243,543 | 74,600 |
| FLATTEN_1525 | HOLD | delay_3min | NIFTY | 243,950 | 66,617 |
| FLATTEN_1525 | HOLD | delay_3min | SENSEX | 225,285 | 58,320 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed1 | NIFTY | 283,302 | 78,455 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed1 | SENSEX | 145,025 | 40,486 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed2 | NIFTY | 283,302 | 78,455 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed2 | SENSEX | 145,025 | 40,486 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed3 | NIFTY | 283,302 | 78,455 |
| FLATTEN_1525 | HOLD | missing_20pct_bars_seed3 | SENSEX | 145,025 | 40,486 |
| FLATTEN_1525 | HOLD | reduced_liquidity | NIFTY | 169,687 | 15,476 |
| FLATTEN_1525 | HOLD | reduced_liquidity | SENSEX | 178,578 | 15,014 |
| FLATTEN_1525 | HOLD | size_1_lot | NIFTY | 81,218 | 19,984 |
| FLATTEN_1525 | HOLD | size_1_lot | SENSEX | 39,531 | 7,076 |
| FLATTEN_1525 | HOLD | size_6_lots | NIFTY | 586,428 | 166,162 |
| FLATTEN_1525 | HOLD | size_6_lots | SENSEX | 303,265 | 90,601 |
| FLATTEN_1525 | HOLD | slippage_x3 | NIFTY | 208,644 | 27,267 |
| FLATTEN_1525 | HOLD | slippage_x3 | SENSEX | 99,301 | -2,458 |
| FLATTEN_1525 | HOLD | slippage_x6 | NIFTY | 96,657 | -49,515 |
| FLATTEN_1525 | HOLD | slippage_x6 | SENSEX | 30,716 | -66,873 |
| HOLD_SETTLE | HOLD | base | NIFTY | 320,150 | 146,664 |
| HOLD_SETTLE | HOLD | base | SENSEX | 176,941 | 71,665 |
| HOLD_SETTLE | HOLD | costs_x2 | NIFTY | 306,244 | 138,391 |
| HOLD_SETTLE | HOLD | costs_x2 | SENSEX | 167,381 | 63,330 |
| HOLD_SETTLE | HOLD | delay_1min | NIFTY | 292,317 | 137,627 |
| HOLD_SETTLE | HOLD | delay_1min | SENSEX | 276,671 | 94,396 |
| HOLD_SETTLE | HOLD | delay_3min | NIFTY | 281,586 | 137,196 |
| HOLD_SETTLE | HOLD | delay_3min | SENSEX | 257,021 | 100,193 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed1 | NIFTY | 320,150 | 146,664 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed1 | SENSEX | 176,941 | 71,665 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed2 | NIFTY | 320,150 | 146,664 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed2 | SENSEX | 176,941 | 71,665 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed3 | NIFTY | 320,150 | 146,664 |
| HOLD_SETTLE | HOLD | missing_20pct_bars_seed3 | SENSEX | 176,941 | 71,665 |
| HOLD_SETTLE | HOLD | reduced_liquidity | NIFTY | 244,540 | 111,968 |
| HOLD_SETTLE | HOLD | reduced_liquidity | SENSEX | 232,306 | 78,385 |
| HOLD_SETTLE | HOLD | size_1_lot | NIFTY | 100,109 | 45,804 |
| HOLD_SETTLE | HOLD | size_1_lot | SENSEX | 54,575 | 20,679 |
| HOLD_SETTLE | HOLD | size_6_lots | NIFTY | 650,212 | 297,953 |
| HOLD_SETTLE | HOLD | size_6_lots | SENSEX | 360,490 | 148,145 |
| HOLD_SETTLE | HOLD | slippage_x3 | NIFTY | 282,700 | 121,344 |
| HOLD_SETTLE | HOLD | slippage_x3 | SENSEX | 153,204 | 50,115 |
| HOLD_SETTLE | HOLD | slippage_x6 | NIFTY | 226,524 | 83,364 |
| HOLD_SETTLE | HOLD | slippage_x6 | SENSEX | 117,599 | 17,790 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | base | NIFTY | 378,461 | 97,083 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | base | SENSEX | 141,682 | -29,921 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | costs_x2 | NIFTY | 360,813 | 85,975 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | costs_x2 | SENSEX | 128,535 | -42,063 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | delay_1min | NIFTY | 357,161 | 71,320 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | delay_1min | SENSEX | 245,158 | 22,296 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | delay_3min | NIFTY | 328,766 | 73,733 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | delay_3min | SENSEX | 252,198 | 12,000 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed1 | NIFTY | 375,886 | 102,716 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed1 | SENSEX | 131,618 | -32,843 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed2 | NIFTY | 387,893 | 94,360 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed2 | SENSEX | 132,992 | 13,485 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed3 | NIFTY | 372,799 | 95,340 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | missing_20pct_bars_seed3 | SENSEX | 142,049 | -24,509 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | reduced_liquidity | NIFTY | 264,495 | 26,643 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | reduced_liquidity | SENSEX | 201,601 | -36,176 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | size_1_lot | NIFTY | 118,523 | 28,727 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | size_1_lot | SENSEX | 41,925 | -13,891 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | size_6_lots | NIFTY | 768,367 | 199,618 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | size_6_lots | SENSEX | 291,318 | -53,965 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | slippage_x3 | NIFTY | 313,834 | 50,395 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | slippage_x3 | SENSEX | 91,328 | -78,029 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | slippage_x6 | NIFTY | 216,893 | -19,637 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band | slippage_x6 | SENSEX | 15,797 | -150,191 |
## Reading
* The baseline stays positive under 3x and 6x slippage in the hold-to-expiry variant, but its clean out-of-sample result is Rs 6,074 at 3x and Rs -42,844 at 6x. The frozen plugin configuration turns negative out of sample at 3x slippage (Rs -27,633).
* The flatten variant is more cost-sensitive because it trades eight orders per cycle: out-of-sample net is Rs 24,810 at 3x and Rs -116,388 at 6x slippage.
* Execution delay did **not** hurt (it improved results by a few hundred rupees per cycle): the 09:16 bar open is not a favourable price, so the result does not depend on speed. I did not investigate why; it should not be read as a benefit.
* P&L scales almost linearly with size (1 lot Rs 154,684 vs 6 lots Rs 1,010,703 in sample) because costs are small relative to premium; a 6-lot position still uses only a fraction of the stated capital.
* Volatility regimes and worst cycles are in the index reports: the baseline lost money in the high-volatility tercile out of sample for both indices; the worst cycles are 2-4% index moves between entry and expiry.
