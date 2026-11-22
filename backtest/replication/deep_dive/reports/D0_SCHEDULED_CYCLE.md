# Algo 8 — D0 scheduled selling, one cycle at a time: is it the same as D-1?

*Plots one real cycle with D-1 and D0 scheduled selling on the same axes. Script `src/bl_d0q_cycle.py <cid>`; figures `figures/bl_d0q_cycle4.png` (main), `bl_d0q_cycle15.png`, `bl_d0q_cycle26.png`. Descriptive: one cycle each, no fitting.*

## What "V1" and "V2" mean
They are not two systems. The D-1 scheduled timetable (the fixed seconds at which the system sells) is one set of clock times for cycles up to 2026-09-09 (**V1**) and a slightly different set from 2026-09-16 onward (**V2**). It is a date split found in the D-1 work. This page uses real cycles and does not need it.

## Result
**NIFTY cycle (expiry 2026-07-28), the main plot: D0 is D-1's clock plus extra waves.**
* **What matches.**
  * Every wave is 1 CE + 1 PE lot at the ATM strike: D-1 97%, D0 96% at the strike nearest the previous minute's close.
  * The day runs from about 09:16 to 14:30 on both days.
  * 29 of the 33 D-1 pairs repeat on D0 at the same second.
* **What differs.**
  * D0 has **83 pairs against 33**: 53 extra pairs. Most of them fall one to two minutes after a 15-minute boundary (block minutes 1–2: 31 of 53). The other 22 sit at other fixed points in the block (the largest group, 9, is 11 minutes after a boundary).
  * Four D-1 pairs do not repeat on D0: 09:16:07, 11:01:00, 11:46:00, 13:16:00.
* **So for NIFTY it is not exactly like D-1.** D0 repeats the D-1 clock and adds roughly twice as many waves. The added waves are fixed clock times too: the same seconds appear on the other NIFTY V1 cycles (`D0_SCHEDULED.md`).

**SENSEX is a different story.** On the two SENSEX cycles plotted:
* Expiring 2026-06-25 (V1): D-1 has 33 pairs, **D0 only 11**, and only 2 repeat. D0 sells once per 15 minutes at about +60 s, from 09:32 to 13:49.
* Expiring 2026-09-17 (V2): D-1 has 34 pairs, D0 has 71, and only 12 repeat.
* So for SENSEX the D0 scheduled selling is **not** the D-1 clock.

| cycle | timetable version | D-1 pairs | D0 pairs | D-1 pairs repeated on D0 (same second ±3 s) | D0 pairs not on D-1 | D-1 window | D0 window | strike = ATM of previous close, D-1 / D0 |
|---|---|---|---|---|---|---|---|---|
| NIFTY expiring 2026-07-28 (D-1 2026-07-27) | V1 | 33 | 83 | 29 of 33 | 53 | 09:16:01 → 14:30:00 | 09:15:59 → 14:30:00 | 97% / 96% |
| SENSEX expiring 2026-06-25 (D-1 2026-06-24) | V1 | 33 | 11 | 2 of 33 | 9 | 09:16:02 → 14:30:00 | 09:32:00 → 13:49:01 | 88% / 100% |
| SENSEX expiring 2026-09-17 (D-1 2026-09-16) | V2 | 34 | 71 | 12 of 34 | 48 | 09:16:01 → 14:45:00 | 09:16:02 → 14:44:00 | 100% / 99% |


## Caveats
* One cycle per group; the patterns hold across the other cycles of the group (`D0_SCHEDULED.md` §1, §5).
* "Same clock time" means within ±3 s of a D-1 pair of the same cycle.
