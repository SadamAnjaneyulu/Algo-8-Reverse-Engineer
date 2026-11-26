# First order-level scoring run, D-1, mode F (diagnostic)

*Spec `ORDER_LEVEL_SCORING_SPEC.md` v1.1 (hash `be1170ab...`), scorer `bl_oscore.py` (hash in `outputs/scoring/d1_F/run_record.json`), simulator = the D-1 engine replayed second by second on the real one-minute bars of the 32 cycles (`config_for(und, d1)`, parameters fitted on these cycles). **Evidence label: historical reproduction. Strictly diagnostic: its purpose is the mismatch profile, not a closure claim.** Mode F only: for D-1, mode T is **identical** to F (the real starting book is flat) and is not a second result; TF-E is not built. No P&L is used anywhere. The legacy lot-level F1 recomputed on this very replay is 0.6878 (guard passed), so the replay is the one behind the published 0.688.*

## Result first
**The simulator reproduces what the system does roughly (about three quarters of orders find a same-side partner within a minute) but not in detail (fewer than half of orders match jointly on time, strike and size), and its books drift far from the real ones.**

| Measure (32 cycles; 9,915 real orders, 8,735 simulated) | Result |
|---|---|
| **Order-level F1, keys only** (cycle, day, option type, side), cumulative at **0 s / 5 s / 60 s** | **0.215 / 0.498 / 0.736** (60 s: 95% interval 0.723-0.749) |
| Exclusive tiers, share of real orders | Exact 20.2%, Near 26.6%, Broad 22.4%, **unmatched 30.8%** (3,054 missing real orders; 1,874 extra simulated orders) |
| Strike among matched | exact **68.6%**; within one step 88.4% |
| Lots among matched | exact **88.1%**; mean absolute error 0.25 lots |
| Order type (validity and module) among matched | **96.0%** (validity supplied by the engine for every order) |
| **Full match** (keys + strike exact + lots exact + type) F1 at 0 / 5 / 60 s | **0.175 / 0.371 / 0.457** (60 s, strike and lots exact: 0.435-0.482) |
| Portfolio state right after matched events | short and long lots equal on both option types in **0.9%** of 6,861 events; median relative error 15% (shorts) and 16% (longs); contract-level L1 distance 51% of gross real lots (median) |
| Carried book at the D-1 close | contract-level L1 distance 79% of gross real lots (median; IQR 61-100%) |
| Per-cycle F1 (keys, 60 s) | median 0.738, IQR 0.715-0.763, minimum 0.662; **none below 0.5**. Strict (strike and lots exact) F1: median 0.456, **21 of 32 below 0.5**, minimum 0.329 (SENSEX 1 Oct) |
| Time-shift placebo (+15 min) | exact tier 3.6% (vs 20.2%); keys F1 at 60 s 0.330 (vs 0.736). A placebo, not a chance baseline: the fixed 15-minute grid maps onto itself |
| Ambiguity | 19.9% of real and 14.2% of simulated orders sit in same-second ambiguous groups; the two tie-break directions differ by at most 0.001 on every 60 s metric, so ambiguity does not move these numbers |
| Variants | without the outlier cycle 0.738; non-stop cycles 0.736; the single stop cycle 0.724 (no outlier dependence) |

Cycle spread is narrow and the weak points are systematic (below), not a few badly reconstructed cycles. Worst five by F1: SENSEX 22 Oct (0.662), NIFTY 19 Oct, SENSEX 10 Sep, SENSEX 1 Oct, NIFTY 6 Oct. By strict F1: SENSEX 1 Oct (0.329), 9 Jul, 25 Jun, 22 Oct, 16 Jul (all SENSEX; median strict F1 NIFTY 0.484 vs SENSEX 0.436).

## By rule class (two-sided: recall on the real side, precision on the simulated side)
| Class | Real | Simulated | Recall | Precision | F1 | Exact second | Strike exact | Lots exact | Median Δt (sim - real) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| body sells | 4,408 | 4,091 | 0.733 | 0.787 | 0.759 | 44% | 78% | 99% | 0 s |
| wing buys | 3,146 | 3,270 | 0.828 | 0.821 | 0.824 | 19% | 66% | 83% | +1 s |
| body buy-backs | 1,324 | 757 | 0.431 | 0.741 | 0.545 | 6% | 47% | 80% | **-15.5 s** |
| wing sells | 600 | 501 | 0.410 | 0.631 | 0.497 | 2% | 42% | 45% | -6.5 s |
| opening wings | 186 | 62 | 0.672 | 0.968 | 0.793 | 38% | 42% | 51% | +2 s |
| overnight lump | 73 (1,489 lots) | 54 (1,399 lots) | 0.274 | 0.407 | 0.328 | 5% | 25% | 30% | -24 s |
| not modelled (stop module, etc.) | 178 | 0 | 0.376 (cross-class) | n/a | n/a | | | | |
**Cross-class matches** (keys ignore class by design): 4.1% of matched pairs; only 5 of them also agree on strike and lots, so they barely inflate the strict levels. Largest: 65 real opening wings matched to simulated wing buys; 51 real not-modelled sells matched to simulated wing sells; 43 buy-backs to wing buys.

## Where the mismatches are
* **Missing real orders (3,054):** body sells 1,179; body buy-backs 754; wing buys 542; wing sells 354; not modelled 111; opening wings 61; lump 53 (**1,028 lots**).
* **Extra simulated orders (1,874):** solo ladder 730; protective wing buys 586; stop buy-backs 196; protective wing sells 185; breakout straddles 61; breakout extras 56; lump 32 (**832 lots**); scheduled straddles 26. The solo ladder both **over-fires (730 extra) and under-fires (body sells missing 1,179)**: its timing is wrong, not only its count.
* **By time of day (30-minute block F1):** strongest 10:30-12:00 (0.84-0.86); weaker 09:00-09:30 (0.66); mid-afternoon 0.68-0.76; **15:00-15:30: 0.36 (recall 0.31, precision 0.44)**; after 15:30: 0.18. From 15:00 on, 657 of 931 real orders (71%) have no partner and 361 of 633 simulated orders (57%) are extra (missing: body sells 321, wing buys 164, buy-backs 69, lump 53; extra: solo ladder 217, wing buys 80, lump 32).
* **Era and version (per-cycle medians):** F1 0.779 before and 0.737 after the closing auction; strict F1 0.446 (V1) and 0.511 (V2).
* **Rule-fixed seconds vs bar-triggered orders:** orders whose second a rule fixes (timetable, opening wings) match the exact second 67.2% of the time and the same minute 92.5%; bar-triggered orders 11.9% and 84.8%. The exact-second tier is therefore mostly a timetable result (spec principle 7).
* **Order granularity differs:** the engine buys the three opening wings as one 3-lot order where the real log sends 1-lot orders (62 vs 186 orders); simulated buy-backs are 18% multi-lot against 0% real; wing buys 14.6% vs 18.8% multi-lot. This affects order counts and per-order lots, not the burst-level lot totals the spec reports separately.

## Reconciliation by cause (spec step 3; categories only, nothing tuned)
| Mismatch | Category |
|---|---|
| Solo-sell timing and count (730 extra, 1,179 body sells missing); the 15:00+ block | **unidentified rule**, partly **data limit** (solo drips are set by the tick path) |
| Body buy-back recall 0.43 and timing 15 s early | **data limit** (intrabar stop touch at one-minute resolution) and **unidentified rule** for the half of buy-backs with no premium trigger |
| Wing buys and sells | **derived** from body mismatches (they inherit them); strike reference partly unidentified |
| Lump: 1,028 missing and 832 extra lots, 25% strike, 30% lots | **unidentified rule** (size), plus the engine's single clock regime per cycle |
| Opening-wing order counts | **execution assumption** (order-split convention differs from the log) |
| Stop module and body-stream closes (not modelled) | **unmodelled behaviour** |
| State drift (0.9% exact S and L; contract-level L1 about half of gross lots) | **compounding** of the above plus **strike-level** differences (a one-step strike difference counts twice at contract level) |

## What this run does not show
It does **not** show that the simulator reproduces Algo 8, nor that the new framework is correct in every respect (the legacy bridge is a necessary check only). It uses the same cycles that fitted the engine (label: historical reproduction). Free-running errors compound (the carried book is far from the real one), and TF-E, which separates rule errors from compounding, is not built. The keys-only F1 (0.736) is **not** comparable with the legacy lot-level F1 (0.688): it counts orders (a 20-lot lump is one order), ignores strike, and tolerates 60 s; the strict level (0.457) is the closer analogue.

## Process findings
* **Scorer defect found on the first execution and fixed:** the per-class table divided real-side matches by simulated counts and gave an impossible F1 of 1.008 for opening wings (class-blind keys let a real order of one class match a simulated order of another). The class table is now two-sided with a real x simulated confusion matrix, a test pins it, and the run was repeated. All non-class numbers were identical between the two executions (checked); the first execution is archived as `outputs/scoring/d1_F_first_execution_class_table_defect/`.
* **Engine change:** `ROLE_ORDER_TYPE` makes the engine emit `validity` (DAY/IOC) and `module` explicitly per role (raises on an unmapped role); the real D-1 log shows no exception (9,885 orders: body `num` all DAY, wings `h_` and lump `v_` all IOC), and a test pins the table to the log.

## Next (not started)
TF-E for D-1 as a diagnostic alongside F; the standalone D0 engine; then D0 and end-to-end. Candidate execution-assumption fix to discuss before anything is changed: the order-split convention for opening wings and buy-backs (it moves order counts, not rules). Everything stays uncommitted pending review.

Files: `src/bl_score_d1_F.py`, `src/bl_score_d1_F_profile.py`, outputs in `outputs/scoring/d1_F/` (`run_record.json`, `all/`, `without_outlier/`, `non_stop/`, `stop_only/`, `profile/`).
