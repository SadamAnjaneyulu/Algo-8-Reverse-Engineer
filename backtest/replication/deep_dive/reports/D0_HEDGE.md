# Algo 8 — D0 chunk 3: hedge wings, lump salvage, body-stream longs

*Plan `D0_HEDGE_PLAN.md` (addendum 3b written after H1–H7, before its tests). In-sample: D0 of the 30 cycles with both logs. Positions include the book carried from D-1. Figure: `figures/bl_d0h_summary.png`.*

## 0. Result
* **The D-1 hedge controller runs unchanged on D0.**
  * Every long-buy wave equals the gap S − L on its right in **94%** of 4,597 waves; sell waves 89%.
  * It acts a median **3.9 s** after the body order (D-1: about 4 s).
  * Hedge AUC: **0.986** (buys) and **0.984** (sells) given the real body orders; **0.841 / 0.804** using only the previous minute.
* **One change from D-1: on D0 the overnight lump counts as hedge.**
  * The gap matches with the lump longs in L (94%), not without them (46%).
  * **The lump is sold off by the controller.** 99.9% of lump lots are sold while long lots exceed short lots on that right; 99% of lump sale waves are no larger than that excess.
  * It goes in 12 pieces per cycle (median), at a median 6% of its D-1 cost.
  * *When* a lump lot is released rather than a wing is **unresolved**: simple timing rules score F1 ≤ 0.05.
* **Wing strike:** the 2.5%-of-ATM rule still fits best, but less tightly than on D-1. Exact 38% and ±1 strike 69% (D-1: 65% / 93%; chance 10% / 30%).
* **Releases** prefer the outermost or cheapest wing (33% / 34% vs chance 17%), as on D-1.
* **Body-stream longs:**
  * D0 opens with pre-bought far wings, as D-1 does: 580 lots in 29 cycles, median 17 steps OTM;
  * body-stream long sales during the day: 982 lots (median 17 steps OTM);
  * 1,071 lots are sold at 15:09+ (chunk 4).

## 1. Controller (H1, H4)
| wave | waves | lots | = gap S − L | = gap, lump not in L | sign right |
|---|---|---|---|---|---|
| buy | 4,597 | 7,779 | 93.6% | 46.4% | 96.3% |
| sell | 2,701 | 8,430 | 88.7% | 52.3% | 98.6% |

* By hour, buy waves equal the gap in 90%–96% of cases.
* Delay after the body order (10/25/50/75/90%):
  * buys 2.9, 3.3, 3.9, 4.7, 6.2 s;
  * sells 2.8, 3.3, 3.8, 4.6, 6.3 s.

## 2. Wing strike (H2, addendum 3b-T2)
| X | exact | within1 |
|---|---|---|
| 0.005 | 0.000 | 0.001 |
| 0.01 | 0.001 | 0.005 |
| 0.015 | 0.009 | 0.044 |
| 0.02 | 0.070 | 0.358 |
| 0.025 | 0.378 | 0.694 |
| 0.03 | 0.166 | 0.574 |
| 0.04 | 0.126 | 0.342 |
| 0.05 | 0.032 | 0.213 |
| 0.075 | 0.008 | 0.071 |
| 0.1 | 0.002 | 0.024 |
| 0.025 (OOF half 0) | 0.466 | 0.780 |
| 0.025 (OOF half 1) | 0.298 | 0.615 |


**Other references** (refit on one half, exact share on the other):

| reference | chosen | exact_oof |
|---|---|---|
| pct_atm | 0.025 / 0.025 | 0.378 |
| fixed_rs | 1.5 / 4 | 0.096 |
| steps | 5 / 8 | 0.056 |
| pct_sold | 0.025 / 0.025 | 0.260 |


## 3. Releases (H3) and lump salvage (H6, 3b-T1)
* **Release choice** (3,087 sells with ≥ 2 long strikes held), share by rule:
  * outermost 33%, cheapest 34%;
  * oldest 20%, newest 18%;
  * nearest 2.5% 20%, innermost 4%, dearest 3%;
  * chance 17%.
* **Lump sales:**
  * 843 lots in 18 cycles, of 1,412 lump lots carried. The rest leave in the clearance or the stop (chunk 4).
  * First sale per cycle: 10/50/90% at 09:15, 10:40, 14:32.
  * Sale price / D-1 cost (10/50/90%): 2.5% / 5.9% / 38.8%.
* **Are lump sales controller releases?**

| module | sell waves | lots | wave = excess L − S | wave ≤ excess | lots sold while L > S |
|---|---|---|---|---|---|
| h_ (wings) | 2,695 | 8,130 | 89% | 98% | 98.4% |
| v_ (lump) | 304 | 843 | 78% | 99% | 99.9% |

**Lump timing rules:**

| rule | F1 | precision | recall | sim_lots | real_lots | null_shift30_F1 |
|---|---|---|---|---|---|---|
| fixed clock (training median first-sale minute), all lump lots | 0.000 | 0.000 | 0.000 | 1412 | 843 | 0.000 |
| sell when L > S on that right (event-level, real book) | 0.044 | 0.035 | 0.059 | 1412 | 843 | 0.004 |
| all lump lots at the end of body activity / the stop | 0.049 | 0.039 | 0.065 | 1412 | 843 | 0.000 |


* The rules fail because the controller releases wings **and** lump lots from the same excess. Which one it picks is the unresolved part.

## 4. `h_` shorts (H5) and body-stream longs (H7)
* **`h_` shorts and covers.** 302 short lots and 485 cover lots, in 17 cycles. The shorts are almost all in the 09:00 hour; the covers are at 09:xx and after 14:00. *Descriptive.*
* **Body-stream longs:**

| window | role | lots | orders | median steps OTM | cycles |
|---|---|---|---|---|---|
| 09:15-09:17 | sell | 48 | 37 | 37.8 | 10 |
| 09:15-09:17 | buy | 580 | 580 | 17.0 | 29 |
| 15:09+ | sell | 1071 | 127 | 8.3 | 12 |
| 15:09+ | buy | 144 | 144 | 4.3 | 10 |
| other | sell | 982 | 534 | 17.0 | 25 |
| other | buy | 257 | 215 | 9.0 | 23 |

## 5. Hedge AUC (H8)
| target | variant | AUC | ci_lo | ci_hi | cells | positives |
|---|---|---|---|---|---|---|
| h_ buy | teacher-forced: gap at minute start + same-minute body lots + clock | 0.986 | 0.981 | 0.990 | 22440 | 3357 |
| h_ buy | causal: gap and body lots of the previous minute + clock | 0.841 | 0.825 | 0.857 | 22440 | 3357 |
| h_ buy | clock only | 0.788 | 0.758 | 0.814 | 22440 | 3357 |
| h_ sell | teacher-forced: gap at minute start + same-minute body lots + clock | 0.984 | 0.977 | 0.989 | 22440 | 1778 |
| h_ sell | causal: gap and body lots of the previous minute + clock | 0.804 | 0.782 | 0.831 | 22440 | 1778 |
| h_ sell | clock only | 0.686 | 0.652 | 0.722 | 22440 | 1778 |


## 6. Kept and rejected
| rule | result | decision | evidence |
|---|---|---|---|
| Controller: buy the gap S − L per right (D-1 rule unchanged) | buy waves = gap 94%, sell waves 89%; sign 96% / 99% | kept | Observed |
| Lump longs count in L on D0 | 94% with the lump in L vs 46% without | kept (differs from D-1) | Observed |
| Controller delay | median 3.9 s after the body order (IQR 3.3–4.7) | kept | Observed |
| Wing strike: premium nearest 2.5% of ATM | exact 38%, ±1 69% (chance 10% / 30%); refit picks 2.5% in both halves | kept, weaker than D-1 (65% / 93%) | Observed |
| Wing strike: fixed ₹, fixed steps, % of last sold premium (post-hoc) | fixed_rs 10% / steps 6% / pct_sold 26% | rejected | Observed |
| Release: outermost or cheapest wing | 33% / 34% vs chance 17% | kept as preference | Observed |
| Lump sales are controller releases (post-hoc) | 99.9% of lump lots sold while L > S; waves ≤ excess 99% | kept | Observed |
| Lump timing rules (clock, first L > S, end of body) | F1 ≤ 0.05 | rejected: which long is released (wing vs lump) is unresolved | Observed |


## 7. Caveats
* **In-sample:** 30 cycles. Out-of-fold for the wing-strike refits.
* **Teacher-forced:** the H8 AUC uses the real gap and the real body orders.
* **Post-hoc:** addendum 3b (lump as release, other strike references) was written after H1–H7.

## Run order
`bl_d0h_tests.py` → `bl_d0h_more.py` (~2 min) → `make_d0h_report.py`. Outputs `outputs/bl_d0h_*`, `bl_summary_d0h1/2.json`.
