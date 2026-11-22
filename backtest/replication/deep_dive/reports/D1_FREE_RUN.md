# Algo 8 — complete D-1 reconstruction vs the original, free-running

*Plan `D1_FREE_RUN_PLAN.md`, written before running. In-sample (D-1 of 32 live cycles; parameters fitted on one cycle half and scored on the other). The simulator uses the market data only (spot and option one-minute OHLC); no real order is ever an input in the primary variant. Figure: `figures/bl_fr_summary.png`.*

## 0. How accurate is it?
| Measure | Result |
|---|---|
| **Lot-level, timing (±1 min, same right and class)** | **F1 0.68** (precision 78%, recall 61%). 8,368 of 13,655 real lots matched. |
| …and the strike within one step | F1 0.62 |
| …and the exact strike | F1 0.45 |
| Minute cells with any activity (same minute / ±1) | F1 0.75 / 0.89 |
| Per cycle | median F1 0.72, 75% of cycles at or above 0.65, range 0.33–0.82 |
| Book through the day (short and long lots per right) | correlation 0.83 / 0.89, median error about 18% |
| **Book carried into D0** | 67% of the real carried shorts and 52% of the real carried longs are reproduced as the same contracts |

**Reading:**
* Timing of what the system does is reproduced to about 0.7 F1, and in terms of *which minute and which side* to about 0.89 F1 (±1 minute cells).
* The exact strike is right in 42%–80% of matched lots depending on the class (lump lowest, body sells highest).
* The carried book agrees in total size to 87% (shorts) and 86% (longs), averaged over cycles, but the same contracts only 67% and 52% of the time.
* These are **free-running** numbers: errors compound (a missed sell changes the wings that follow, and a different buy-back changes the carried book). They are lower than the AUCs (0.96) because AUC scored each minute given the real book and ignored strikes and lot counts.

## 1. By class (free-running)
| class | real lots | simulated lots | precision | recall | F1 timing | F1 + strike within one | F1 + exact strike | exact strike among matched |
|---|---|---|---|---|---|---|---|---|
| Body sells | 4671 | 3799 | 84% | 69% | 0.76 | 0.72 | 0.60 | 80% |
| Body buy-backs | 1324 | 991 | 64% | 48% | 0.55 | 0.44 | 0.30 | 55% |
| Wing buys (`h_`) | 4336 | 3575 | 80% | 66% | 0.73 | 0.67 | 0.45 | 61% |
| Wing sells (`h_`) | 1192 | 959 | 60% | 49% | 0.54 | 0.43 | 0.27 | 51% |
| Opening wings (body stream) | 186 | 192 | 96% | 99% | 0.97 | 0.92 | 0.59 | 60% |
| Overnight lump (`v_`) | 1489 | 1278 | 70% | 60% | 0.64 | 0.53 | 0.27 | 42% |
| Not modelled | 457 | 0 | – | 0% | 0 | 0 | 0 | – |
| **All D-1 lots** | 13655 | 10794 | 78% | 61% | **0.68** | 0.62 | 0.45 | – |


* **Body sells** are the most accurate (0.76), then the **opening wings** (0.97, a fixed form).
* **Wing buys** follow the body sells: F1 0.73 free-running, **0.92 when the real body trades are given**. So the hedge module itself is reproduced at about 0.92–0.95, and its free-running score is mostly the body's error passed on.
* **Buy-backs are the weakest** (0.55). Only a graded stop on the lot's own premium is decoded (θ = 1.5 chosen on both folds), not the neighbouring-lot clusters or the 15–21% of buy-backs with no identified rule. The wing sells inherit this: 0.54.
* **Lump** (0.64): the clock and side are right; size is the unresolved part, so about 40% of its lots do not match.
* **Not modelled** (457 lots, 3% of D-1): the stop module's liquidation (one cycle), the body-stream wing closes and rebuys at 15:15, and one hedge cover. They stay in the recall denominator.

## 2. The hedge module on its own (given the real body orders)
| class | F1 timing, hedge on the real body | F1 + strike within one | F1 + exact strike | F1 timing, free-running |
|---|---|---|---|---|
| Wing buys (`h_`) | 0.92 | 0.82 | 0.50 | 0.73 |
| Wing sells (`h_`) | 0.95 | 0.82 | 0.56 | 0.54 |


## 3. Book
| variant | quantity (per right, hours 1–6.5) | mean real lots | mean abs error (lots) | median abs error | correlation |
|---|---|---|---|---|---|
| free-running | short lots S | 33.2 | 7.4 | 18% | 0.83 |
| free-running | long lots L | 36.0 | 8.4 | 19% | 0.89 |
| hedge on the real body | short lots S | 33.2 | 0.5 | 0% | 0.97 |
| hedge on the real body | long lots L | 36.0 | 2.3 | 0% | 0.96 |


| variant | carried shorts matched (same contract) | carried longs matched | short lots at the close: real / simulated (both rights) | long lots: real / simulated | correlation across cycles (S / L) |
|---|---|---|---|---|---|
| free-running | 67% | 52% | 101 / 88 | 148 / 128 | 0.37 / 0.38 |
| hedge on the real body | 100% | 60% | 101 / 106 | 148 / 151 | 0.94 / 0.89 |


* **Carried-book overlap** is the share of real carried lots that appear as the same contract on the same side in the simulation. It is lower than the size agreement because strikes differ by one step and the lump sits at a slightly different strike.
* In the hedge-on-real-body variant the carried **short** overlap is 100% by construction (the real body orders are the input).
* The correlation of the end-of-day totals across cycles is weak (0.37 / 0.38) because of two outliers. In cycle 14 (NIFTY, F1 0.33) there is a 240-lot deep-out-of-the-money batch sell (not modelled) and 128 body-stream long lots, and 328 shorts are carried. In cycle 8 (NIFTY, F1 0.53) the real stop module liquidated the book at 14:46 (not modelled). These are the two worst cycles by F1.

## 4. Cell level (cycle × minute × right)
| class | real cells | simulated cells | precision (same minute) | recall (same minute) | F1 same minute | F1 ±1 minute |
|---|---|---|---|---|---|---|
| Body sells | 2644 | 2745 | 0.78 | 0.81 | 0.8 | 0.91 |
| Body buy-backs | 483 | 267 | 0.58 | 0.32 | 0.42 | 0.6 |
| Wing buys (`h_`) | 2553 | 2656 | 0.76 | 0.79 | 0.77 | 0.9 |
| Wing sells (`h_`) | 438 | 256 | 0.57 | 0.34 | 0.42 | 0.59 |
| Opening wings (body stream) | 63 | 64 | 0.95 | 0.97 | 0.96 | 0.98 |
| Overnight lump (`v_`) | 47 | 32 | 0.09 | 0.06 | 0.08 | 0.48 |
| **Any activity** | 3365 | 3018 | 0.8 | 0.72 | 0.75 | 0.89 |


## 5. What drives the gap to 100%
| Missing piece | Lots affected | Effect |
|---|---|---|
| Solo sell timing (the open piece of the body) | about a third of body sells | recall of body sells 69% |
| Deep-OTM batch sells (287 lots) and after-15:00 solo sells (336 lots) | about 13% of body sells | the late rule R3 adds recall but costs precision: overall F1 0.684 vs 0.684 |
| Buy-back rule (graded stop only) | 1,324 lots | F1 0.55; passes to wing sells |
| Lump size | 1,489 lots | F1 0.64 |
| Stop module, 15:15 flatten, hedge cover | 457 lots (3%) | recall ceiling about 97% |
| Exact strike (minute data lag the live price) | all classes | F1 0.45 strict vs 0.69 timing |

## Parameters (out-of-fold)
| fold | tp | theta | a | b | lump_ratio | lump_t | open_off |
|---|---|---|---|---|---|---|---|
| 0 | 0.4 | 1.5 | 0.613 | 1.823 | {'NIFTY': 0.85, 'SENSEX': 0.42} | {'r1': 357, 'r2': 368, 'r3': 376} | {'NIFTY/V1': 39.8, 'NIFTY/V2': 40.0, 'SENSEX/V1': 39.9, 'SENSEX/V2': 20.0} |
| 1 | 0.4 | 1.5 | 0.981 | 0.979 | {'NIFTY': 0.816, 'SENSEX': 0.604} | {'r1': 355, 'r2': 369, 'r3': 375} | {'NIFTY/V1': 39.2, 'NIFTY/V2': 39.5, 'SENSEX/V1': 39.8, 'SENSEX/V2': 20.0} |

Fixed from earlier studies, not re-fitted here: solo ladder (0.2 step, 60-minute gate), wing premium target k = 2.5%, lump strike 2.2 σ√T. **The wing strike rule runs here on previous-minute closes. Its exact-strike share among matched wing buys is 61%.** `D1_LONG_SIDE.md` reported 65% using a "calibrated" analysis price that uses the true wing's own price, so the free-running figure is the honest one.

## Evidence labels
Observed: all numbers above (executed). Post-hoc: the late R3 variant. Not testable: exact fills and seconds, margin inputs, event order within a minute. In-sample: the rules were found on the same 32 cycles.
