# D0 step 1b: scheduled selling in depth — plan

*Written before the tests. In-sample: D0 of the 30 cycles with both logs. Builds on `D0_SELLS.md` §2 and `D0_SELL_TYPES.md`: scheduled pairs are 21% of D0 sell lots, and 96% are at the strike nearest the previous minute's close.*

## Questions
1. **When:** the timetable per underlying × version. When does scheduled selling start and end each day, and what ends it?
2. **Trigger:** is the clock the only trigger, or are some waves skipped? If skipped, what differs?
3. **Strike:** which strike is sold, and how it is chosen, among competing ATM definitions.
4. **Scheduler:** is it the same one as on D-1?

## Tests
**T1 — the timetable**
* Waves per underlying × version (greedy over pair starts, as in `bl_d0s_tt.py`), all cycles, descriptive. Listed with clock time, offset within the 15-minute slot, and attendance.
* Stability: the share of waves learned on one cycle half that are also learned on the other (±3 s).

**T2 — start and end**
* Per cycle: the first and last scheduled pair.
* Per group: the first and last wave.
* An early end is classified as:
  * (a) the cycle stop;
  * (b) the group's last wave;
  * (c) otherwise, which is examined case by case (MTM, book size, spot move).

**T3 — attendance (trigger)**
* For each out-of-fold wave of a cycle's group, while the cycle is active (before its stop): executed (a pair within ±3 s) or skipped.
* Skip rate by group and by hour.
* Single-variable AUC for skipping, each with a cycle-bootstrap CI. Variables:
  * cumulative cycle MTM;
  * body short lots on the book;
  * spot move since the previous wave;
  * |spot − ATM| / step (closeness to a strike midpoint);
  * the ATM straddle premium;
  * a body buy-back in the previous 5 minutes.

**T4 — strike choice.** For every scheduled pair, the exact-match share of each candidate:

| | candidate | timing |
|---|---|---|
| (a) | strike nearest the previous minute's spot close (the D-1 rule) | causal |
| (b) | nearest the sale minute's open | causal |
| (c) | nearest the sale minute's close | non-causal |
| (d) | any strike that was ATM during the sale minute (between its low and high) | feasibility bound |
| (e) | straddle ATM: the strike minimising \|CE − PE\| at the previous close | causal |
| (f) | synthetic-forward ATM: forward = K + CE − PE at strike (a); then the nearest strike | causal |
| (g) | the strike of the previous scheduled pair | — |

* **Disagreement test:** in pairs where (a) differs from (e) or (f), which one matches the real strike.
* **Misses:** the cases where no candidate matches are described.

**T5 — lots per wave.** Descriptive only; quantity is step 2.

**T6 — same scheduler as D-1?**
* D-1 waves are built the same way, per underlying × version, from D-1 scheduled pairs.
* Reported: the share of D0 waves whose second-of-day matches a D-1 wave of the same group (±3 s), and the reverse.

## Evidence rules
Observed / Inferred / Unresolved. No fitted parameters except the out-of-fold waves in T3. Thresholds come from the earlier work: ±3 s matches; acceptance for a variable: AUC ≥ 0.70 in both halves.
