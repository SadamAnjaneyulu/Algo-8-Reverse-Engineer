# Algo 8 — D-1 selling: how much is reconstructed, all three sell types together

*Check requested before moving to the long side. All D-1 body sell orders of the 32 live cycles (4671 lots). The three decoded rules are run together and every real sold lot is matched one-to-one (same cycle, same right, within ±1 minute). Findings 4–7 (buy-backs) are checked against the earlier reports, not re-run. Figure: `figures/bl_all_sells.png`.*

## 0. Verdict

**D-1 selling is not 100% reconstructed.** All three rules together reproduce the real D-1 sold lots with **F1 0.64** (precision 59%, recall 71%). By type:

| Sell type | Share of D-1 sold lots | Lot-level F1 (±1 min) | Status |
|---|---|---|---|
| **1. Scheduled pairs** | 45% | **0.98** (precision 99%, recall 98%); strike exact 94% | **Solved** |
| **2. Reactive pairs** | 16% | **0.68** (precision 90%, recall 55%); strike exact 85% | **Timing solved, quantity not**: the first entry of each candle-side is reproduced 93% of the time, but repeat entries and the 2–3 lots in some entries are not, so only 55% of reactive *lots* are matched |
| **3. Solo sells** | 38% | **0.31** with the stated rule (precision 24%, recall 42%); best variant 0.46 | **Not solved** — the fresh-extreme rule fires far more often than the real system and misses half the real solo sells |

The scheduled and reactive rules alone are almost never wrong (precision 99%), but they cover only 54% of the lots sold on D-1. **The open piece is the solo sells — 38% of everything sold on D-1.**

## 1. Your eight findings, checked against the data
| # | Your statement | Verdict | What the data says (source) |
|---|---|---|---|
| 1 | Scheduled: ATM CE+PE every 15 min, no trigger | **Correct on "no trigger"; wrong on "every 15 min"** | A fixed timetable of **33 waves** per D-1 (two versions, V1 to D-1 2026-09-09, V2 from 2026-09-16), each wave = 1 CE + 1 PE lot at the strike nearest the previous minute's close. Waves sit at fixed seconds inside 15-minute blocks, **0–4 waves per block** (lot ladder 3, 2, 3, 1, 4, … per slot), dense in the morning (≈ 8 per hour) and sparse after 12:00 (≈ 2–3 per hour). Each cell fires in ≥ 95% of cycles; no market or book variable changes it (`BODY_SIZING_LOGIC.md`, `BODY_PAIRED_SELL_AND_CLOSE_LOGIC.md`). Reproduced here at F1 0.98. |
| 2 | Solo: every minute, fresh low/high of the previous 15 one-minute closes → add a single CE/PE; otherwise nothing | **Direction right, rule incomplete** | A solo **CE follows a fresh low** and a solo **PE a fresh high** (breakout over 5–60 min is the strongest single ingredient; rate 77 vs 9 per 1,000 minutes for 15 min; `BODY_SOLO_VARIABLE_SEARCH.md`), plus the own leg being in profit and the other leg losing (`BODY_SOLO_SELL_MOVE_TEST.md`). But **most fresh extremes get no solo sale**: as a rule it fires 3082 times against 1795 real solo lots (precision 24%) and still misses 58%. The strike is the premium of the previous sale on that right (48% exact), **not ATM** (strike exact here 25%). A quarter of solo lots come after 15:00 and 270 lots (15% of solo lots) are single orders of ≥ 3 lots (up to 54) — not covered by a per-minute rule. |
| 3 | Lot sizing: controlled in the first half, irregular in the second | **Partly** | Morning selling is the fixed timetable ladder (controlled). After about 12:30 the timetable thins out and reactive pairs (≈ 2.3 per hour) and solo sells (bursts, end-of-day batches) make up most of the volume, so total lots per cycle vary much more (solo 56 ± 40 lots per cycle vs scheduled 66 ± 3). "Irregular" is the solo stream, not the pairs (pairs are 1+1 lots in 95% of cases). |
| 4 | Buy-back individually, not as a pair; when premium rises to 1.5–1.7×; 1.7× is the peak | **Individually: correct. "Peak at 1.7": not quite** | Only 8.8% of buy-backs have a same-strike partner within 3 s; the leg's own premium ÷ its own entry decides. The buy-back rate first steps up at **1.4–1.5×** (3.1×) and 1.5–1.6× (4.3×) and **keeps rising** to 672 per 1,000 contract-minutes at 1.7–1.8× — a graded stop that is nearly certain by 1.7–1.8×, not a peak at 1.7 (`BODY_CLOSE_LOGIC.md`). |
| 5 | Positions that never reach 1.2× are mostly carried forward; 61% never reach it | **Correct** | 61% of D-1 sold lots never reach 1.2× on a minute close and 82% of those are carried overnight (`BODY_CLOSE_LOGIC.md`). |
| 6 | 33–40% of buy-backs are below 1.2×; ~36% of them within 3 s of a ≥ 1.5× buy-back, same side, nearby strikes | **Correct** | 33–40% depending on the lot convention; 36% within 3 s of a stop-like buy-back (chance 0.6%), 68% same right, median 2 strikes away (`BODY_CLOSE_LOGIC.md`). |
| 7 | The rest: a sudden adverse move in the previous 1–5 minutes | **Correct as an association, not a rule** | The residual buy-backs follow a fast rise of the lot's own premium / adverse spot move in the last 1–5 min (AUC 0.78–0.85, fading to 0.50 at 60 min); no loss level or % of capital works; 15–21% of all D-1 buy-backs still have **no identified rule** (`BODY_CLOSE_CAPITAL.md`). |
| 8 | Reactive pairs: two-candle breakout | **Correct, with three precisions** | (a) the 30-minute candles are **clock-aligned (hh:00–hh:30, hh:30–hh:00)**, not 09:15-aligned; (b) **once per side per candle** (both sides can fire in the same candle); (c) entries stop at about **15:15**. ATM = the strike nearest the **previous minute's close**. In your example the 11:07 break sells 22,200 CE + PE only if the previous close was nearer 22,150 than 22,200 (e.g. 22,170); with a previous close of 22,180 the ATM is 22,200 and the pair is 22,250. Reproduced: first entry per candle-side 93% (90% exact minute); repeat entries inside a candle (≈ 18% of reactive pair-minutes) and the lot count per entry are **not** decoded (`BODY_REACTIVE_DECODE.md`). |

## 2. Combined match, by type and tolerance
| tolerance (min) | sell type | real lots | model lots | matched | precision | recall | F1 | strike exact (matched) |
|---|---|---|---|---|---|---|---|---|
| 0 | scheduled | 2122 | 2112 | 1924 | 0.911 | 0.907 | 0.909 | 0.941 |
| 0 | reactive | 754 | 458 | 398 | 0.869 | 0.528 | 0.657 | 0.854 |
| 0 | solo | 1795 | 3082 | 420 | 0.136 | 0.234 | 0.172 | 0.226 |
| 1 | scheduled | 2122 | 2112 | 2084 | 0.987 | 0.982 | 0.984 | 0.943 |
| 1 | reactive | 754 | 458 | 412 | 0.9 | 0.546 | 0.68 | 0.85 |
| 1 | solo | 1795 | 3082 | 745 | 0.242 | 0.415 | 0.306 | 0.247 |
| 2 | scheduled | 2122 | 2112 | 2084 | 0.987 | 0.982 | 0.984 | 0.943 |
| 2 | reactive | 754 | 458 | 412 | 0.9 | 0.546 | 0.68 | 0.85 |
| 2 | solo | 1795 | 3082 | 831 | 0.27 | 0.463 | 0.341 | 0.254 |

| tolerance (min) | model | real lots | model lots | matched | precision | recall | F1 | strike exact (matched) |
|---|---|---|---|---|---|---|---|---|
| 0 | all three rules vs all D-1 sells | 4671 | 5652 | 2809 | 0.497 | 0.601 | 0.544 | 0.794 |
| 0 | scheduled + reactive only vs all D-1 sells | 4671 | 2570 | 2364 | 0.92 | 0.506 | 0.653 | 0.896 |
| 1 | all three rules vs all D-1 sells | 4671 | 5652 | 3310 | 0.586 | 0.709 | 0.641 | 0.744 |
| 1 | scheduled + reactive only vs all D-1 sells | 4671 | 2570 | 2534 | 0.986 | 0.542 | 0.7 | 0.894 |
| 2 | all three rules vs all D-1 sells | 4671 | 5652 | 3416 | 0.604 | 0.731 | 0.662 | 0.73 |
| 2 | scheduled + reactive only vs all D-1 sells | 4671 | 2570 | 2539 | 0.988 | 0.544 | 0.701 | 0.892 |

Lots per cycle, real vs model:

| sell type | real lots per cycle (mean ± sd) | model lots per cycle | Spearman across cycles |
|---|---|---|---|
| scheduled | 66.3 ± 2.7 | 66.0 ± 0.0 | n/a (model constant) |
| reactive | 23.6 ± 4.5 | 14.3 ± 3.5 | 0.41 |
| solo | 56.1 ± 40.2 | 96.3 ± 9.1 | 0.08 |


## 3. Why solo selling is not done
| time of day | real solo lots | share | CE share |
|---|---|---|---|
| 09:15-10:30 | 299 | 18% | 85% |
| 10:30-12:00 | 217 | 13% | 63% |
| 12:00-13:30 | 319 | 19% | 59% |
| 13:30-15:00 | 430 | 26% | 55% |
| 15:00-15:30 | 412 | 25% | 67% |

| price used | look-back (min) | window | real solo lots | model lots | matched | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|
| close | 5 | full day | 1676 | 5692 | 862 | 0.151 | 0.514 | 0.234 |
| close | 5 | until 15:00 | 1209 | 5290 | 742 | 0.14 | 0.614 | 0.228 |
| close | 15 | full day | 1676 | 3082 | 745 | 0.242 | 0.444 | 0.313 |
| close | 15 | until 15:00 | 1209 | 2850 | 646 | 0.227 | 0.534 | 0.318 |
| close | 30 | full day | 1676 | 2022 | 646 | 0.32 | 0.385 | 0.349 |
| close | 30 | until 15:00 | 1209 | 1855 | 565 | 0.305 | 0.467 | 0.369 |
| close | 60 | full day | 1676 | 1275 | 533 | 0.418 | 0.318 | 0.361 |
| close | 60 | until 15:00 | 1209 | 1159 | 470 | 0.406 | 0.389 | 0.397 |
| true high/low (intrabar) | 5 | full day | 1676 | 5920 | 914 | 0.154 | 0.545 | 0.241 |
| true high/low (intrabar) | 5 | until 15:00 | 1209 | 5496 | 787 | 0.143 | 0.651 | 0.235 |
| true high/low (intrabar) | 15 | full day | 1676 | 3293 | 830 | 0.252 | 0.495 | 0.334 |
| true high/low (intrabar) | 15 | until 15:00 | 1209 | 3033 | 717 | 0.236 | 0.593 | 0.338 |
| true high/low (intrabar) | 30 | full day | 1676 | 2154 | 745 | 0.346 | 0.444 | 0.389 |
| true high/low (intrabar) | 30 | until 15:00 | 1209 | 1965 | 651 | 0.331 | 0.538 | 0.41 |
| true high/low (intrabar) | 60 | full day | 1676 | 1367 | 636 | 0.465 | 0.38 | 0.418 |
| true high/low (intrabar) | 60 | until 15:00 | 1209 | 1237 | 565 | 0.457 | 0.467 | 0.462 |

* The fresh-extreme rule, on closes or on true one-minute highs/lows, at any look-back, stays at **F1 ≤ 0.46**: either it fires too often (short look-backs) or misses most sells (long look-backs). The earlier best *probabilistic* model reached AUC 0.86–0.90 — good at ranking minutes, but not a deterministic rule.
* What is missing (from the earlier reports): the own-leg-profit / other-leg-loss conditions, the strike rule (premium of the previous sale on that right), the end-of-day stream after 15:00 (25% of solo lots) and the large batches (up to 54 lots).

## 4. What "D-1 selling done" would need
1. **Solo sells** — a decoded trigger and strike rule (largest gap: 38% of lots).
2. **Reactive quantity** — repeat entries inside a candle and 2–3-lot entries.
3. Nothing further for the scheduled pairs.

## 5. Limits
In-sample; D-1 only; ±1-minute lot matching (exact-minute numbers in §2); lot ownership in a strike is not observable; the scheduled timetable is applied from the observed wave clock of each version (it is a fit of these cycles, not an external specification); findings 4–7 are quoted from earlier reports, not re-run here.

## 6. Files
`src/bl_all_sells.py` (combined simulator and matching) → `bl_all_solo.py` (solo variants, where solo lots sit) → `bl_all_fig.py` → `make_all_report.py`. Outputs `outputs/bl_all_*`, `bl_summary_all1…2.json`. Tests `tests/test_bl.py` (`test_all_*`).
