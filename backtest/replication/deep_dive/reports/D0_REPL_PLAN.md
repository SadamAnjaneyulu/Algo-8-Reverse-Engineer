# D0 solo selling after the counter-sells: replacement, other solo, far-OTM roll-out — plan

*Written before the tests. In-sample discovery on D0 (24 cycles with minutes after the opening window; panel of `D0_CTRIG.md`). Counter-sells are set aside (`D0_CAUC.md`, gate met). The next biggest solo slices by lots are: **replacement solo** (14.5% of D0 sell lots with the far-OTM roll-out taken out; 21% before), **other solo** (13%) and the **far-OTM roll-out** (9%). Types are the labels of `D0_SELL_TYPES.md`; far-OTM = a solo sale at least 3 strike steps OTM (post-hoc type of that report).*

## Questions
1. **Is a replacement a replacement?** After a body buy-back on a right, does a sale on the **same** right follow, how soon, at what strike and size relative to what was bought back?
2. **Are these three slices separate mechanisms, or the same solo engine?**
3. **Can the minutes that carry each slice be ranked at AUC ≥ 0.85 using only past information?** (the same gate as counter-sells)

## Tests
**E1 — replacement mechanics (event level).** Events = body buy-back lots grouped by (cycle, right, second), with the reason of `D0_BB_TYPES.md`.
* Rate of a solo sale on the same right in (0, +60 s], by buy-back reason, against the same buy-back times shifted ±10 min and ±15 min (clock kept). A reason is kept if the rate is at least 1.5× **both** shifted levels.
* Lag histogram (5 s bins) after the buy-back for the reasons kept.
* For sales that follow: strike offset against the bought strike (steps, + = further OTM), premium sold ÷ premium bought, lots sold ÷ lots bought, same strike share. Against the same quantities for a random same-right solo sale in the same cycle (chance).

**E2 — distinct or the same engine.** Among all solo sale orders in the panel that are not counter-labelled, AUC of telling each slice (replacement, other solo, far-OTM) from the rest, leave-one-cycle-out, **using market and book state only** (no buy-back features). **A slice is a distinct mechanism if the CI lower bound is above 0.65.** Otherwise it is a label on the same engine.

**E3 — the AUC gate (cell level).** Cells (cycle, minute, right), outcome = a sale of that slice in the cell. Variants as for counter-sells:
* **V1 causal** (bars to j−1, orders before minute j; the gate is judged here);
* **V2** + the minute's own bar;
* **V3** + same-minute buy-backs on the same and the other right (partly definitional for the replacement label).
Pooled leave-one-cycle-out AUC with cycle-bootstrap CI, within-cycle AUC, a cycle-shuffled placebo, a forward check (first 16 cycles → last 8). Fixed gradient-boosting settings as before. **Gate met** if V1 AUC ≥ 0.85 and forward ≥ 0.80. A slice with fewer than 150 cells is reported but cannot meet the gate on its own.

## Rules for reading the results
* A pass is a ranking, not a rule. Evidence labels as before; post-hoc steps are labelled in an addendum.
* **Not testable here:** the order of events inside a second; tick prices.

## Addendum — written after seeing results (post-hoc steps, labelled in the report)
1. **Hours and conditions by slice, and a clock-recurrence test** were added after E2/E3 showed that time of day separates the slices (`bl_d0e_more.py`, `bl_d0e_clock.py`).
2. **The strangle finding.** "Other solo" sales recurred at the same seconds across cycles (6.9× chance) and 73% had an opposite-right sale within 3 s in the SENSEX version before 16 Sep. Looking at those pairs showed a call one step above ATM and a put one step below ATM. A strangle detector, an out-of-fold timetable, a relabel and a re-run of the gate followed (`bl_d0e_strangle.py`, `bl_d0e_final.py`).
3. **An error caught on the way:** a follow-up script overwrote its forward-test split, so the first forward AUCs it printed (0.99 and 0.95) were invalid and were discarded; the numbers reported are from the corrected runs. The clock feature of the forward check uses training cycles only. A bootstrap interval for the recurrence ratio was wrong (duplicated cycles leaked into the leave-one-out) and is replaced by a per-cycle sign test.
4. The "clock feature" is built from other cycles' sale times, leave-one-cycle-out; for the forward check from training cycles only.
