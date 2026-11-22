# Algo 8 — D0 chunk 4: cycle stop and 15:14 clearance

*Plan `D0_STOP_CLEAR_PLAN.md`, written before the tests. In-sample: D0 of the 30 cycles with both logs, 11 of them with a stop. Figure: `figures/bl_d0x_summary.png`.*

## 0. Result
* **The cycle stop is a cumulative mark-to-market stop on the whole cycle (D-1 + D0, all modules).** It is checked on live prices within the minute.
  * Marked at the close of the minute, a threshold of **L = 1.20 lakh** reproduces **all 11 stops** in the stop minute or the minute before, with **no false alarm** in the 19 cycles without a stop.
  * Chosen on one half and scored on the other: 11 hits, 0 false alarms, 0 misses. *Observed.*
  * **The constant lies between 1.17 and 1.29 lakh on minute-close marks.** No cycle without a stop went below −1.17 lakh, and every stop cycle was at −1.29 lakh or worse when it stopped. The earlier work's −1.30 to −1.44 lakh is the upper part of the range minute data allow. Ticks would pin it.
* **The stop cannot be timed from completed bars.**
  * With the previous minute's close, it is caught 4/11 times at 1.20 lakh; with the minute's open, 5/11.
  * Marking at the adverse intrabar extreme raises false alarms.
  * Loss measured from the D0 open fails (F1 ≤ 0.27): the stop counts the D-1 loss too.
* **4 of the 11 stops fire before 09:16** (the gap at the open). 8 of 11 are in the first 15 minutes. The `s_` module liquidates the book in a median 40 s; three stops took 2–5 minutes. After it, body selling stops for the day. During the liquidation, though, the body keeps selling in 9 of 11 cycles (523 lots, mostly inside the `s_` window).
* **15:14 clearance: every short open at 15:09 is bought back before the close** (100% of 2,218 lots in non-stop cycles), nothing is left to expire.
  * The big wave is at 15:14; the rest follow 15:15–15:34.
  * The 15:14 lots are somewhat dearer: premium AUC 0.66 against later buy-backs.
* **Longs:** 87% of long lots are sold; the rest are kept to expiry. No premium or moneyness rule beats "sell all" (58% vs 87%). The kept ones are the cheap ones (premium AUC 0.70).

## 1. Stop: which mark and threshold (S2)
Cycle-level F1: a hit is a predicted crossing in the real stop minute or the minute before.

**Cumulative MTM (since the D-1 open):**

| L_lakh | adverse_intrabar | close | open | prev_close |
|---|---|---|---|---|
| 1.20 | 0.64 | 1.00 | 0.62 | 0.53 |
| 1.30 | 0.72 | 0.90 | 0.31 | 0.31 |
| 1.35 | 0.80 | 0.90 | 0.31 | 0.31 |
| 1.40 | 0.83 | 0.90 | 0.31 | 0.31 |
| 1.44 | 0.83 | 0.84 | 0.31 | 0.31 |
| 1.50 | 0.87 | 0.84 | 0.31 | 0.31 |


**D0-only MTM (minus the 09:15 open mark):**

| L_lakh | adverse_intrabar | close | open | prev_close |
|---|---|---|---|---|
| 1.20 | 0.17 | 0.19 | 0.20 | 0.11 |
| 1.30 | 0.17 | 0.19 | 0.11 | 0.11 |
| 1.35 | 0.17 | 0.19 | 0.11 | 0.11 |
| 1.40 | 0.17 | 0.19 | 0.11 | 0.11 |
| 1.44 | 0.17 | 0.19 | 0.11 | 0.11 |
| 1.50 | 0.27 | 0.20 | 0.11 | 0.22 |


**Out-of-fold (mark fixed, L and scope chosen on the other half):**

| half | mark | L_lakh | scope | TP | FP | FN | early | F1 |
|---|---|---|---|---|---|---|---|---|
| 0 | prev_close | 1.200 | cumulative | 1 | 0 | 6 | 0 | 0.250 |
| 0 | open | 1.200 | cumulative | 1 | 0 | 6 | 0 | 0.250 |
| 0 | adverse_intrabar | 1.300 | cumulative | 5 | 3 | 2 | 3 | 0.667 |
| 0 | close | 1.200 | cumulative | 7 | 0 | 0 | 0 | 1.000 |
| 1 | prev_close | 1.200 | cumulative | 3 | 0 | 1 | 0 | 0.857 |
| 1 | open | 1.200 | cumulative | 4 | 0 | 0 | 0 | 1.000 |
| 1 | adverse_intrabar | 1.500 | cumulative | 3 | 2 | 1 | 2 | 0.667 |
| 1 | close | 1.200 | cumulative | 4 | 0 | 0 | 0 | 1.000 |


**MTM at the stop (lakh ₹, minute close)** for each stop cycle: -3.07, -2.50, -2.14, -2.10, -1.86, -1.84, -1.59, -1.58, -1.42, -1.30, -1.29. Lowest MTM of the cycles without a stop (before 15:14), most negative first: -1.17, -1.15, -1.10, -0.72, -0.70 …

* **Correction during this chunk.** A first run let predictions fall up to 5 minutes after the real stop. That made causal marks look perfect, because the stop's own liquidation locked in the loss one minute later. Predictions are now limited to the stop minute and earlier.
* Contracts with no D0 price at the open: 0.7% of positions (marked 0).

## 2. What the stop does (S3)
| cid | und | expiry | stop_time | s_lots | s_orders | s_span_s | s_cover_short | s_close_long | other_orders_after | other_lots_after | body_sell_lots_after | body_cover_lots_after | last_body_sell_after_s | other_modules_after | mtm_close_lakh |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | NIFTY | 2026-06-30 | 14:25:13 | 428 | 37 | 39.73 | 279 | 149 | 43 | 184 | 151 | 13 | 18.29 | num | -1.84 |
| 2 | NIFTY | 2026-07-14 | 09:15:17 | 296 | 39 | 55.29 | 176 | 120 | 43 | 180 | 16 | 11 | 41.90 | h_/num/v_ | -1.42 |
| 6 | NIFTY | 2026-08-18 | 09:15:07 | 458 | 53 | 20.55 | 227 | 168 | 19 | 105 | 0 | 0 | — | h_/num/v_ | -2.14 |
| 10 | NIFTY | 2026-09-22 | 14:14:29 | 188 | 13 | 0.00 | 91 | 97 | 20 | 247 | 0 | 119 | — | h_/num | -3.07 |
| 13 | NIFTY | 2026-10-13 | 09:18:01 | 233 | 47 | 306.80 | 107 | 126 | 31 | 35 | 4 | 1 | 304.88 | h_/num | -0.70 |
| 14 | NIFTY | 2026-10-19 | 09:26:19 | 608 | 31 | 10.82 | 299 | 309 | 18 | 278 | 169 | 32 | 6.59 | num | -1.86 |
| 18 | SENSEX | 2026-07-16 | 11:00:46 | 220 | 26 | 30.46 | 122 | 98 | 27 | 220 | 98 | 74 | 14.70 | num | -1.29 |
| 21 | SENSEX | 2026-08-06 | 09:22:40 | 219 | 35 | 129.93 | 128 | 91 | 20 | 101 | 58 | 4 | 497.08 | num | -1.29 |
| 23 | SENSEX | 2026-08-20 | 09:14:13 | 510 | 57 | 204.06 | 280 | 230 | 115 | 257 | 19 | 3 | 202.34 | h_/num/v_ | -2.50 |
| 27 | SENSEX | 2026-09-24 | 09:15:00 | 226 | 23 | 44.83 | 133 | 93 | 77 | 199 | 4 | 60 | 43.44 | h_/num/v_ | -1.58 |
| 30 | SENSEX | 2026-10-15 | 09:16:28 | 129 | 26 | 8.75 | 62 | 67 | 7 | 8 | 4 | 2 | 11.50 | num | -1.59 |


* `s_` closes both sides, buying back the shorts and selling the longs. Median 40 s; three stops took 2–5 minutes.
* **Body sells still occur after the stop** in 9 of 11 cycles: 523 lots, the last one at most 8 minutes after the stop. The earlier register noted these post-stop short fills (U8). Whether they are late fills of pending orders or new decisions is **unresolved**.

## 3. Clearance (C1–C3)
**Which open lots at 15:09 are closed later** (cycles without a stop; rules fitted on one half):

| lots | rule | chosen | accuracy_oof | majority_class | AUC_all | n_lots | closed_share |
|---|---|---|---|---|---|---|---|
| long | premium >= p* | 0.5 / 0.5 | 0.585 | 0.867 | 0.702 | 2232 | 0.867 |
| long | steps OTM <= k* | 3 / 3 | 0.152 | 0.867 | 0.365 | 2232 | 0.867 |
| short | premium >= p* | 0.5 / 0.5 | 0.927 | 1.000 | 0.915 | 2218 | 1.000 |
| short | steps OTM <= k* | 3 / 3 | 0.899 | 1.000 | 0.743 | 2218 | 1.000 |


**15:14 against later buy-backs** (premium at the 15:13 close):

| window | lots | px_median | px_q90 | otm_median | share_itm |
|---|---|---|---|---|---|
| 15:10-15:13 | 378.00 | 19.90 | 112.00 | 0.67 | 0.39 |
| 15:14 | 1101.00 | 34.45 | 155.65 | 0.27 | 0.35 |
| 15:15+ | 800.00 | 14.15 | 97.75 | 0.25 | 0.45 |


* All shorts are bought back by the close. Longs are sold except the cheapest.
* The split between the 15:14 wave and the 15:15–15:34 tail is only weakly linked to price (premium AUC 0.66; moneyness 0.44). It looks like order pacing. *Inferred.*

## 4. Kept and rejected
| rule | result | decision | evidence |
|---|---|---|---|
| Cycle stop: cumulative MTM (D-1 + D0, all modules) ≤ −L, live within the minute | 11/11, no false alarm, at L = 1.20 lakh with minute-close marks; out-of-fold the same | kept | Observed |
| Constant L | between 1.17 and 1.29 lakh on minute closes | bounded, not pinned | Observed |
| Stop timed from completed bars (previous close / open) | at most 5/11 | rejected (the stop is intrabar) | Observed |
| D0-only loss | F1 ≤ 0.27 | rejected | Observed |
| Clearance: buy back every short by the close | 100% of lots | kept | Observed |
| Clearance: sell longs except the cheapest | 87% sold; no threshold beats "sell all" | kept as "sell all" | Observed |

## 5. Caveats
* **In-sample:** 11 stop cycles. Out-of-fold over halves.
* **LTP MTM without costs.** Marks are minute bars, so the true intraminute trigger price is not observed.
* **The stop decides on live prices.** A minute-bar simulator has to use the close of the minute (a small look-ahead inside the minute) or accept late stops.

## Run order
`bl_d0x_stop.py` → `make_d0x_report.py`. Outputs `outputs/bl_d0x_*`, `bl_summary_d0x1.json`.
