# Reactive pairs (CE+PE sells outside the fixed timetable): what are they, when, and what triggers them — plan, written before the tests

**User questions.** (1) What is the orange "reactive pair" in the sizing figure? (2) Are CE+PE pairs sold outside the fixed timetable, and if yes what triggers them and why? (3) What triggers the waves, and how can one know how many waves execute at what time?

**Known before the plan (from `BODY_SIZING_LOGIC.md`).** Timetable waves = 1-lot CE+PE pairs at fixed in-block seconds, 33 per D-1 (V1 and V2), cells fire in ≥95% of cycles. A **reactive pair** is a CE and a PE body `open_short` at the same strike within ±3 s that is **not** inside a timetable cell (cell window ±3 s): ≈ 30 lots per cycle (≈ 15 pairs), mostly 11:00–15:30, spread over all seconds (median offset 434 s into the block, no peak at a fixed second).

## Locked definitions
* **Reactive pair event** = a D-1 pair (`bl_size_pairs.csv`) whose CE order time is outside every timetable cell window of its version (±3 s). Unit for hazard tests: **cycle-minute** (D-1, minute 5–373) **excluding minutes that contain a timetable wave**; target R = ≥ 1 reactive pair starts in the minute. Contrast targets: solo sell (S) and body buy-back (BB) in the minute.
* Causal features at the previous completed minute close: **clock** (minute, version, underlying, minutes since last body sell); **event history** (minutes since last pair / last reactive pair / last scheduled wave / last buy-back / last stop-like buy-back; lots sold and bought back in the last 5/15 min; waves done so far); **market** (spot change 1/3/5/15/30 min signed and absolute, distance from the day high/low and fresh-extreme flags, ATM drift vs the strike of the last pair/sell in steps, ATM straddle premium and its 5/15-min change); **book** (cumulative P&L, day P&L, drawdown, 5/15-min change); **inventory** (short lots per right, imbalance, total).

## Tests
1. **When:** distribution over clock hours and seconds-of-minute vs uniform; per version; per underlying.
2. **Timer-likeness:** gap to the previous body sell / pair (peak at ~14–15 min?) vs shifted-time null; hazard by minutes since last sell.
3. **Event-anchored:** share of reactive pairs within 60 s / 5 min after a body buy-back (any, stop-like) vs shifted-time null; relation of the number of reactive lots to lots bought back.
4. **Strike:** hit rate of the previous-minute ATM (reference: timetable pairs, solo sells); drift from the last pair's strike.
5. **Predictive:** univariate AUC (cluster bootstrap over cycles; within-cycle permutation null) for every feature; leave-one-cycle-out gradient boosting: clock-only baseline → + each block → all; within-cycle permutation of each block (3×).
6. **Quantity:** lots per reactive burst; dependence on bought-back lots, ATM drift, spot move.
7. **Replication:** chronological halves (cycles split at the median expiry); NIFTY vs SENSEX.

## Decision rules (fixed now)
* A block is called a **trigger family** only if adding it to the clock-only baseline raises leave-one-cycle-out AUC by ≥ 0.03 with the permutation maximum below the gain **and** its strongest single feature has a cluster-bootstrap CI above 0.55 (or below 0.45) in both chronological halves.
* "Timer" only if the gap distribution has a peak at a fixed lag with shifted-time null excluded.
* Otherwise: "no identified trigger" and the reactive pairs remain **Unresolved**. Labels: Observed / Inferred / Unresolved. In-sample, 32 D-1 cycles; features are minute-resolution; no causal claims.

## Limits (known in advance)
±3 s pair rule (two coincident solo sells at one strike would be called a pair); minute-resolution market data (no bid/ask, no sub-minute prices); cell windows chosen from a ≥0.5-pairs-per-cycle cut; the real trigger may use information not in the data (e.g. tick-level prices, order-book, internal state).
