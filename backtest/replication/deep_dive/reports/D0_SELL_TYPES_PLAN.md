# D0 step 1: sell types and strikes, 09:15 to close — plan

*Written before the tests. In-sample: D0 of the 30 cycles with both logs (29 with D0 sells; 8,336 body sell lots). Builds on `D0_SELLS.md`.*

## Taxonomy
Every D0 body sell order gets exactly one type, by the precedence below. The order is fixed before running. A multi-label overlap table is also reported, so the precedence choice is visible.

**Pairs** (CE + PE at the same strike within 3 s):
1. **Scheduled pair:** within ±3 s of a timetable wave of its underlying × version, learned on the other cycle half (out-of-fold).
2. **Opening pair:** starts before 09:18:00.
3. **Re-centre pair:** a body buy-back on either right in the 60 s before.
4. **Breakout pair:** within ±1 minute of a D-1 two-candle breakout fire (10:30–15:15).
5. **Other pair.**

**Solo** (unpaired):
6. **Opening solo:** before 09:18:00.
7. **Replacement:** a body buy-back on the same right in the 60 s before.
8. **Counter-sell:** a body buy-back on the other right within ±60 s.
9. **Extreme solo:** the sale minute makes a fresh 60-minute favourable extreme (CE: new low; PE: new high).
10. **Late solo:** from 15:00.
11. **Other solo.**

**Chance level for the trigger-based types (3, 7, 8, 9).**
* For 3, 7 and 8: the same rule with buy-back times shifted ±10 minutes.
* For 9: the share of random minutes, in the same cycle and hour, that make a fresh extreme.
* Each type is reported with its share **in excess of chance**.

## For each type
* Lots, orders, cycles, lots per order.
* Time-of-day profile.
* Side (CE / PE share).

**Strike:**
* Signed offset from ATM, in steps (positive = OTM for the sold right). ATM = the strike nearest the previous minute's close.
* Exact-ATM share and ±1-step share.
* Strike status:
  * already short from D-1 (carried);
  * already short from earlier on D0;
  * new.
* Same strike as the last sale on that right.
* The D-1 solo rule: the premium nearest the last sale's premium on that right.
* For replacement: same strike as the bought-back lot.
* For counter-sell: same strike as the other right's bought-back lot.
* Premium sold, and premium / ATM premium.

**Chance for exact-strike rules:** 1/7, a random strike within ±3 steps of ATM.

## Opening (09:15–09:30), with the carried book in view
* Sells by type.
* Share at carried strikes vs new strikes.
* CE vs PE share against the opening gap direction (D0 open vs D-1 close).
* Whether opening sells follow the carried book's imbalance (heavier side vs lighter side).
* Descriptive, with sign tests where a direction is claimed.

## Evidence rules
Observed / Inferred / Unresolved. Shares come with cycle-bootstrap CIs where a claim depends on them. No parameters are fitted except the out-of-fold timetable.

## Addendum (post-hoc), written after the first run, before the test below
**Context.**
* "Replacement solo" is only slightly above chance: 34% of lots flagged, against 25% with buy-back times shifted.
* It contains a far-OTM population: 770 lots sold ≥ 3 steps OTM, in 14 cycles, mostly 6 of them.

**Refinement.** A new solo type, **far-OTM solo** (≥ 3 steps OTM), placed right after opening solo. The pre-registered taxonomy stays the primary table; the refinement is shown next to it.

**Roll-out test for far-OTM lots.**
* Share with a same-right body buy-back in the 60 s before, at a strike nearer the money, against buy-back times shifted ±10 minutes.
* Premium sold / premium of that bought-back lot.
* Cycles and underlying.
