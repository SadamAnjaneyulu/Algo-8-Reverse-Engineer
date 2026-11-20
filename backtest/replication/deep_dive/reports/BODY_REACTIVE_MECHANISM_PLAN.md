# Reactive pairs in depth, and a census of every D-1 sell — plan, written before the tests

**User questions.** (1) Why do reactive pairs start "after 11:00" and not before — London open / volume, or some other trigger? (2) How do they happen, when do they stop — by time, by spot move %, or like the 1-minute solo-sell logic? (3) Is there any selling on D-1 other than the three types (timetable pairs, reactive pairs, solo)?

**Corrections / context from the previous study (`BODY_REACTIVE_PAIRS.md`, read-only).** The hour table said 0.2 / 0.7 / 2.2 reactive pairs per cycle in 9:xx / 10:xx / 11:xx; the per-cycle onset is **not** a sharp 11:00 (a first look at the per-cycle first reactive pair gave a median near 10:40 with a spread of about 09:35–11:55); this study measures it properly. Reactive pairs sit one strike off the ATM, on the side of the recent move (96%); trigger not identified; weak tilt from market-move and event-history features.

## Locked definitions
* Same pair / reactive / timetable definitions as before (±3 s; timetable cells of the sizing study). D-1 only, 32 cycles, panel of cycle-minutes without a timetable wave (`bl_react_panel.csv.gz`) plus new features. Option volume = body-relevant strikes' CE+PE minute volume (ATM ±3 strikes) from the chain; realised volatility = sum of |1-minute spot returns| over the block; range-from-open = |spot − opening ATM| in strike steps.

## Tests
**A. Onset and stop.** Per-cycle first / last reactive pair time (distribution); hazard per 15-minute block per cycle; for each cycle the time the spot first moves ≥ 1, 1.5, 2 strike steps from the opening ATM and the cumulative day range first reaches 0.2%/0.3% — rank correlation with the first reactive pair; London-open hypothesis (12:30 IST while UK is on summer time, UK clocks change on 2026-10-25 after the last D-1 date used → 13:30 IST afterwards): step in option volume / in the reactive-pair rate at 12:30; option volume and realised volatility by 15-minute block.
**B. Is the clock (≥ 11:00) real or a proxy?** Logistic/GB leave-one-cycle-out with and without the clock, volume, realised volatility, range-from-open, timetable waves done, short lots held; stratified hazard by clock hour within strata of range-from-open and volume terciles.
**C. Mechanism per event.** Strike rule candidates (pre-registered list): nearest strike to the previous close; floor/ceil of the spot in the direction of the move; ATM of a lagged spot (1–15 min); ATM projected with momentum (spot + λ·move); synthetic ATM (min |CE−PE|) at the previous close; delta-0.5 strike; strike of the last reactive pair ±1. Inter-arrival times between successive reactive pairs and between reactive pairs and the previous sell; strike repetition; spot move since the previous reactive pair (steps and %), distance of spot to the strike; refractory behaviour.
**D. Census of D-1 sells.** All D-1 sell orders of every module, mutually exclusive classes in fixed priority: timetable pair, reactive pair, near-pair (CE and PE within ±3 s at *different* strikes), batch (≥ 3 lots at one strike within 3 s, one right), end-of-day solo (≥ 15:00), single solo, sells that close longs (body wings, hedge module), stop/lump/manual module sells, residual. Lots per cycle per class; the residual is reported as such.

## Decision rules (fixed now)
* A candidate explanation of the onset is "supported" only if (i) it removes the time-of-day effect (the clock's leave-one-cycle-out gain falls below 0.01 AUC when the candidate is in the model) **and** (ii) its own leave-one-cycle-out gain ≥ 0.03 over clock-only with the within-cycle permutation maximum below the gain.
* A strike rule is "supported" only if its hit rate ≥ 80% on reactive pairs, CI above the best simpler rival, and ≥ 70% in both chronological halves and both underlyings.
* A new sell type is called a type only if it holds ≥ 3% of D-1 sold lots or ≥ 1 lot per cycle with a stable signature (time, strike, size); otherwise "minor".
* Otherwise "not identified". Labels: Observed / Inferred / Unresolved. In-sample; minute-resolution market data; second-resolution fills.

## Limits (known in advance)
No tick/bid-ask; the clock-vs-volume question is observational with 32 cycles; London open and option volume are not independent of the clock (a time-of-day proxy cannot be separated from a calendar trigger without variation in the calendar); the UK clock change (2026-10-25) falls after the last D-1 cycle, so only the summer-time open (12:30 IST) is testable.
