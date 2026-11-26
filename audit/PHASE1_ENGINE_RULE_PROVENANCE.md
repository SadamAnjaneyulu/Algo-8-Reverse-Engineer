# Phase 1, Gate 1: provenance of every engine rule and parameter (what the D-1 engine assumes, and on what evidence)

*Purpose (Gate 1 criterion: no major rule silently represented by an unsupported assumption). Source: `d1_strategy/d1_algo/config.py` and `engine.py` at the Gate 0 baseline (snapshot `outputs/phase1/baseline_engine_B0/`). "Fitted" means a constant estimated on the 32 development cycles (so in-sample). Classes as in `PHASE1_RULE_CLASSIFICATION.md`.*

| Engine element | Value | Register row | Class | Basis | Honest note |
|---|---|---|---|---|---|
| Scheduled straddle timetable | SCHEDULE_A / SCHEDULE_B, 33 waves, version switch at D-1 >= 2026-09-16 | D1-03 | Confirmed | seconds repeat across cycles within 1-2 s | learned per version, not derived; a new version needs new data |
| Scheduled strike | ATM of previous completed close | D1-03/08 | Confirmed | 94% exact | |
| Opening wings | 3 lots per right, 39.8 strikes OTM (SENSEX 20 from 16 Sep) | D1-02 | Confirmed (form) | 31 of 32 cycles | closing moment is not modelled here |
| Breakout (reactive pairs) window | minute 75 to 360 (10:30-15:15) | D1-04 | Decoded | F1 0.82 | the 10:30 gate is a clock whose reason is unknown |
| Breakout channel / trigger | two previous completed 30-minute candles, once per side per candle | D1-04 | Decoded | first entry per candle-side 93% | repeat entries (49 of 274) not modelled |
| Breakout size | pairs = min(1 + depth // 0.4, 3); extra lots = clip(round(0.81 + 1.28 depth), 0, 7) | D1-04/09 | Partial | fitted (Spearman 0.42 for extras) | in-sample constants; note: in the replay all simulated breakout orders are 1-lot |
| Breakout sizing delay | 0 s | (convention) | Assumption | none | the real size is decided inside the minute |
| Solo ladder step | 0.2 strike steps | D1-05 | Partial | fitted on D-1 lots, F1 0.46-0.47 | P1-2A: finer steps 0.1 / 0.05 tested (V07, V08) and **rejected** (precision collapses); the engine value stands |
| Solo ladder gate | new 60-minute extreme | D1-05 | Partial | best of several windows | P1-2A: 15- and 5-minute windows tested (V02, V03) and **rejected**; the 60-minute gate stands (it holds at only 71% of real solo-sell minutes, but shorter gates over-fire) |
| Solo lots per trigger | 1 | D1-05/09 | Partial | assumption | P1-2A: lots = steps crossed tested (V04-V06) and **rejected**, T2 contradicts it (Spearman -0.03) |
| Solo strike | premium-nearest to last same-side sale, within +/-4 strikes | D1-08 | Partial | P1-2B: teacher-forced on real context exact 0.501, within one 0.881; ten alternatives tested, none supported | in F the matched ladder strike is 0.25 because the simulator's context diverges (about 0.23 lost to context); rule stands |
| Per-lot stop | 1.6x of own entry on the running minute high | D1-12 | Decoded | hazard 2% to 41% across 1.4-1.8x | half of buy-backs have no recoverable trigger |
| Wing controller | gap = shorts - wings per right, 4 s after the last body order, strike nearest 2.5% of ATM option | D1-10/11 | Confirmed (qty, timing) / Partial (strike) | quantity = gap in 98% | |
| Wing release | sell the excess, outermost first | D1-11 | Confirmed / Partial | outermost 44% vs chance 26% | |
| Overnight lump | clock regimes by date; heavier side; 2.2 sigma strike; size 0.827x (NIFTY) / 0.503x (SENSEX) of the heavy side | D1-13 | Confirmed (side, clock) / Partial / **Unresolved (size)** | size fitted per underlying | size error about +/-13 lots; not an identified rule |
| Marketable limit | LTP x (1 -/+ 0.15) | D1-16 | Confirmed | limit / first fill 0.852 | |
| Order type by role | DAY (num) / IOC (h_, v_) | D1-16 | Confirmed | 9,885 of 9,885 orders | pinned by test |
| Order split convention | `one_lot_v2` for opening wings and buy-backs (accepted); freeze quantity 27 / 50 otherwise | (convention) | Assumption (user-accepted) | real log is 100% 1-lot for those classes | granularity only; not evidence of better reproduction |
| Risk guard | 400 short lots per right, 40 decisions per minute | (engine safety) | Assumption | none from the original | **our engine's safety limits, not reconstructed rules**; the cap did bind in teacher-forced runs |
| Replay fills | at the feed's last price, high/low order inside a minute by convention | (replay) | Assumption | convention in `sim.py` | intrabar order is unknowable from bars |
| **Not in the engine** | stop module (s_), cycle stop, late-session rule (15:00 onwards), G1b closing pairs, deep-OTM batches, body-stream long closes | D1-06/07/14/15, G1b | Unresolved / Candidate | | the frozen late-sale rule exists as a separate shadow module, not in the engine |
| **Candidate, not adopted** | `ladder_book_condition` (default off) | D1-05 | Partial | P1-2A V01: precision +4.5 points, extras -27%, legacy lot F1 +0.010; fails preregistered A1/A3/A4 | archived near-miss; engine switch exists, off by default |

---

## Phase 1 closure addendum (Gate 8): provenance of the D0 engine (`d0_strategy/d0_algo`) and the integrated runner (`algo8_integrated`)

*Source: `d0_algo/config.py`, `engine.py`, `algo8_integrated/handoff.py`, frozen at Gate 8 (`outputs/phase1/8/freeze_manifest.json`). "Fitted" = estimated on the D0 cycles (frozen file: all 30 cycles, in-sample; scored runs use out-of-fold or leave-one-cycle-out fits). Classes as in `PHASE1_RULE_REGISTER_FINAL.md`.*

| Engine element | Value | Register row | Class | Basis | Honest note |
|---|---|---|---|---|---|
| Pair timetable (waves) | table per underlying and version, fitted | D0-01 | Decoded | repeated seconds across cycles | learned, not derived |
| Strangle timetable | SENSEX V1 | D0-02 | Confirmed | found post hoc, repeats | |
| Breakout pair window | minute 75-360, two-candle channel | D1-04 / D0-01 | Decoded | D-1 rule reused in D0 | |
| Solo ladder | step 0.05 strike steps, gate 60 min, multi-lot, lot cap 10 | D0-03 | Partial | identical in 30/30 LOCO folds | trigger and counts weak; ticks needed |
| Counter-sells | ratio 0.25 of simulated other-right buy-backs | D0-03 | Partial | identical in 30/30 LOCO folds | weak |
| Buy-back stop / take-profit | 1.4x minute high / 0.1x minute low | D0-04 | Decoded | identical in 30/30 LOCO folds | bursts and carried-lot buy-backs not modelled |
| Opening wings | 20 lots, offset 17 strike steps | D0-05 | Partial | median of training cycles; X3 clock alternative rejected | strike unresolved |
| Hedge controller | gap = shorts - longs per right, buy at 2.5% of ATM premium, release outermost first | D0-05 | Confirmed (quantity) | earlier chunk | wing vs lump release choice unresolved |
| Cycle stop | cumulative MTM (D-1 + D0, minute close) <= -1.20 lakh | D1-15 | Confirmed on real book | 11/11, 0 false alarms; constant 1.17-1.29 | minute-close marking: up to 60 s in-minute information; completed-bar timing not recoverable |
| Clearance clock | minute 359 (post-auction), 363 (pre-auction, candidate X1) | D0-06 | Decoded | 8 of 10 post-auction waves exactly at 359; pre-auction start median 363 | engine clears in one minute; real spreads to 15:34; regime B unobservable |
| Risk guard | 306 short lots per right, 90 sell decisions per minute | n/a | Safety limit | observed real envelope 278 / 90 plus 10% | not original controls |
| Event timestamps | minute start | n/a | Convention | minute-resolution bars | a +60 s shift scores higher (0.435 vs 0.422): live action on the completed bar loses no agreement |
| Handoff D-1 -> D0 | shorts with entry prices, wings as `h_`, lump as `v_`, cash from simulated fills | X-01 | Assumption | `PHASE1_GATE6_PLAN.md` section 2 | opening wings carried as `h_` (real: `num`); D-1 stop not modelled |

---

## Phase 1 final-loop addendum (2026-11-25): changes to provenance

| Engine element | Before | After | Basis |
|---|---|---|---|
| D0 cycle stop constant | 1.20 lakh (engine default, Gate 5a anchor) | **1.25 lakh in the frozen configurations** (engine default stays 1.20 so the Gate 5a reference regression holds) | real-book test on the full D-1 + D0 path: 1.20 gives 2 false alarms (D-1 sessions), interval (1.2177, 1.2902], 1.25 = midpoint: 12/12 stops, 0 false alarms (in-sample interval estimate) |
| D0 clearance clock | 363 pre-auction in the Gate 6/8 candidate | **359 in every cycle in the forward/production configuration**; 363 only in the labelled historical-reproduction configuration | X1 is in-sample on 8 cycles; future expiries are all post-auction (9 of 10 at 359) |
| D-1 cycle stop | not modelled | default-off switch `cycle_stop_rupees` exists; **rejected** (4 false stops in free-running) | `PHASE1_LOOP2_RESULT.md` section 2 |
| D0 staggered clearance | not modelled | default-off option `clearance_hazards`; **rejected** (near-miss) | `PHASE1_LOOP2_RESULT.md` section 3 |
