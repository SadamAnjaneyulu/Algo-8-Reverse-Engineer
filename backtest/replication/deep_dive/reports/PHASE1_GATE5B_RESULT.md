# Phase 1, Gate 5b: D0 order-level reconstruction. Result

*Evidence: **historical reproduction, development cycles, teacher-forced start from the real carried book (mode T)**. Not independent evidence. Code executed, results observed (`outputs/phase1/5b/summary.json`, `ledger_summary.json`). Nothing committed.*

## Headline (RESULT)
**The D0 engine reproduces the real order stream only partially.** OOF, primary convention (`events`), 30 cycles, 26,430 real vs 19,198 simulated orders:

| Metric | OOF events | OOF one_lot | Fwd A events | Fwd B events |
|---|---:|---:|---:|---:|
| keys F1, 60 s | **0.420** [CI 0.382-0.455] | 0.398 | 0.472 | 0.392 |
| keys F1, 5 s | 0.165 | 0.127 | 0.203 | 0.139 |
| keys F1, 0 s | 0.043 | 0.030 | 0.064 | 0.031 |
| strict F1 (strike+lots), 60 s | 0.142 | 0.131 | 0.175 | 0.106 |
| strike-exact F1, 60 s | 0.175 | 0.151 | 0.218 | 0.158 |
| shift placebo keys F1 60 s | 0.238 | 0.192 | 0.212 | 0.194 |
| median normalised book L1 | 0.733 | 0.742 | 0.586 | 0.693 |

Per cycle (OOF events): median 0.409, IQR 0.304-0.485, 24/30 below 0.5, 8/30 below 0.3; worst cycles NIFTY|2026-10-13 (0.123), SENSEX|2026-07-16 (0.191), SENSEX|2026-10-15 (0.198). Block F1 falls from 0.54 (12:30) to 0.28 (15:00) and 0.0 (15:30+) (first-run block table; stop correction does not touch these blocks).
**The placebo (time-shifted sim) is 0.23: the engine beats chance (0.420 vs 0.238) but by a modest margin; the legacy lot-level bridge (0.410) says the same thing.**

## Class table (OOF events, orders)
| Class | Real | Sim | Recall | Precision | F1 |
|---|---:|---:|---:|---:|---:|
| body_buyback | 8,350 | 9,207 | 0.315 | 0.347 | 0.330 |
| body_long | 1,637 | 113 | 0.241 | 0.575 | 0.340 |
| body_sell | 7,905 | 3,962 | 0.396 | 0.757 | 0.520 |
| not_modelled | 164 | 0 | 0.652 | n/a | n/a |
| stop | 387 | 260 | 0.093 | 0.650 | 0.163 |
| wing_buy | 4,515 | 2,376 | 0.469 | 0.739 | 0.574 |
| wing_sell | 3,472 | 1,898 | 0.252 | 0.582 | 0.351 |

(Order counts differ in definition from lots: real lots 9,656 buy-back / 8,336 body sells vs sim 10,498 / 8,865. Real orders are many single-lot orders, the engine emits aggregated events, which is why recall is low on sells while lot totals are close.)

## Mismatch ledger (16,902 missing real, 9,670 extra sim; S supply / W wrong strike-lots / T timing / A absent)
* **Missing real by class (S/A/T):** body_buyback S 2,089 A 2,268 T 1,264; body_sell S 2,863 A 1,518 T 394; wing_sell A 1,082 S 1,069 T 444; wing_buy A 1,076 S 920 T 398; body_long A 514 S 508; stop S 126 A 66 T 95.
* **Missing real by window:** intraday body buy-backs 3,809 and body sells 3,614 dominate; **opening (to 09:17): 691 body sells, 332 longs, 238 buy-backs, 132 wing sells**; clearance (15:14 on): buy-backs 1,006, wing sells 163, longs 193; 15:00-15:13: buy-backs 569, wing sells 245, body sells 448.
* **Extra sim:** body buy-backs 6,014 (S 3,869: simulated one event vs several real orders; intraday 4,604, 15:00-15:13 1,066), body sells 962, **stop 91 (after the correction below; 1,232 in the archived first run)**.

## Root-cause classification (what the data support)
| Cause | Evidence | Label |
|---|---|---|
| **Order splitting / event aggregation** (execution layer) | S category (counterpart within 60 s but count differs) is the largest block in body sells, buy-backs, stops; lot totals are near real | Confirmed (execution convention, not strategy) |
| **Stop module: timing and scope, not over-firing** | after the correction: sim 260 stop orders vs real 387, precision 0.65, **recall 0.093**; the engine stops in 11 cycles, real in 11, both in 8 (see below) | Confirmed mismatch, rule unresolved (5c) |
| **Body-stream longs not modelled as real** | real 1,637 orders vs sim 113 | Confirmed gap (5c) |
| **Opening window gap** | 691 missing real body sells within 3 minutes of open | Confirmed gap (5c) |
| **Clearance** | real clearance is **era dependent** (measured below); engine clears everything at minute 359 | Confirmed mismatch (5c) |
| 15:30+ block | 138 real orders, 0 simulated | Confirmed gap (post-clearance residual) |
| Inherited D-1 book error | not applicable in mode T (real book is used); carry-state L1 0.73 measures per-minute divergence after the cycle diverges | Not isolated here |

## Real clearance profile (measured on real logs; `outputs/phase1/5b/real_clearance_profile.csv`)
Start = minute with the largest buy-back wave after 15:00; cumulative share of clearance lots by minute after start:
| Era | n | start minute (median / min / max) | within 0 min | 1 | 2 | 5 | 10 |
|---|---:|---|---:|---:|---:|---:|---:|
| post-auction (D0 ≥ 3 Aug 2026) | 10 | 359 / 358 / 378 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| pre-auction | 8 | 363.5 / 349 / 364 | 0.60 | 0.81 | 0.88 | 0.95 | 1.00 |
So post-auction clearance is a single-minute wave at minute 359 (15:14) in 8 of 10 cycles, which matches the engine; **pre-auction clearance is later (≈15:17-15:19) and spread over several minutes**, and two SENSEX cycles started clearing around 15:09-15:12 (349, 352). Post-auction exceptions: NIFTY 2026-08-04 (358), SENSEX 2026-08-13 (378).

## Honest limits
* Conventions fixed before the first run (see PLAN). Mode T. The three excluded cycles are not scored. Dev cycles only: no independent evidence.
* `events` vs `one_lot` are scoring-layer conventions; neither is an engine change.
* Minute resolution of simulated times caps exact-second F1 (0.04) by construction; the 60 s tier is the meaningful one.

## Gate 5b status: **MEASUREMENT COMPLETE** (no acceptance thresholds applied; thresholds for D0 quality are preregistered in 5c/5d before any validation run).

## Addendum 1: scoring-layer correction (found after the first run; first run archived)
The first 5b run turned every per-lot tuple in an engine stop event's `parts` into its own order (1,642 simulated stop orders from 225 events). That contradicted the plan's own stated convention (one order per contract and component **kind**: short buy-back for body/other shorts, sell for longs). `AGG_STOP_PARTS = True` now aggregates parts by kind within an event; the old behaviour is kept behind the flag only to reproduce the archived first run (`outputs/phase1/5b_first_run_per_lot_stop_parts/`). No engine change, no real-order input, no parameter changed. Effect: OOF keys F1 60 s 0.4176 → 0.420; stop class F1 0.254 → 0.163 (the earlier stop precision/recall were an artefact of the split convention). This correction was found by inspecting stop events, not by tuning to a score.

## Stop module diagnostic (OOF, 30 cycles; `real` = `s_` module orders)
Real stop: 11 cycles; engine stop: 11 cycles; **both: 8**. Engine-only: SENSEX 2026-09-17 (minute 335), NIFTY 2026-08-04 (305), SENSEX 2026-10-22 (251). Real-only: NIFTY 2026-09-22 (299), SENSEX 2026-07-16 (105), NIFTY 2026-10-13 (3-8). In stopped cycles both fire at similar minutes in 5 of 8 (NIFTY 07-14 j=0 vs 0,1; 08-18 0 vs 0; SENSEX 09-24 0 vs 0; 10-15 0 vs 1; 10-19 10 vs 11) and differ in NIFTY 06-30 (128 vs 310) and SENSEX 08-06 (6 vs 9). Real stops are staged over several minutes (NIFTY 06-30: 37 orders at minute 310 for 428 lots); the engine closes everything in one minute.
