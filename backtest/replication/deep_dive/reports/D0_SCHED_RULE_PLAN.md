# How was D0 scheduled selling scheduled? Plan: timers, not a grid

*Written before the validation tests. The two decomposition runs (`bl_d0r_chains.py`, `bl_d0r_ilp.py`) were exploratory discovery on the consensus times of each group; their numbers are not evidence. The tests below are the evidence.*

## Question
On D-1 the scheduled straddles look like "every 15 minutes". On D0 they look unorganised. What generates the D0 clock times?

## Starting point (exploratory, labelled as discovery)
* The consensus clock times are **deterministic**: 87% recur at the same second in other cycles (`D0_SCHEDULED_WHY.md`).
* Even D-1 is **not one 15-minute grid**. It decomposes into several **timers** with different periods (15, 30, 45, 60 minutes), each with its own second offset: for example a 30-minute timer at :09–:10 s, a 45-minute timer at :00, a 60-minute timer at :30.
* Read by clock minute within the hour, the times look like hourly cron entries ("xx:01:10 in hours 10–12").

## Hypothesis H-T
The scheduled times are the union of a small set of **independent timers**. Each timer fires at start + n × period, at a fixed second offset, between a start and an end. D0 uses the D-1 timers (same periods and second offsets) plus extra ones.

## Decomposition (fixed before the tests)
* Candidate timer = a chain of at least 3 clock times with spacing a **multiple of 5 minutes** (5–90 min), each member within ±2 s of the expected time.
* An integer program picks the chains that maximise (clock times covered) − 1.5 × (timers used), with each clock time covered once.
* Null: the same program on clock times shifted independently by ±150 s.

## Tests
**T1 — forward extrapolation (the key test).**
* Fit the timers using only clock times before 12:00. Extend each timer forward for up to 6 more members.
* Statistic: the share of the **after-12:00** clock times that fall within ±2 s of a predicted member.
* Null: the same timers with each phase moved by a random amount (at least 4 s, up to the period); 500 draws.
* Run for D-1 and D0 of each group with enough waves.

**T2 — D-1 timers explain D0.**
* The D-1 timers of a group, extended over the whole day (both directions), against the **D0 clock times of the same group**.
* Statistic: the share of D0 clock times covered, against the phase-shifted null.
* The same for the reverse direction (D0 timers → D-1 times).

**T3 — across groups.**
* The NIFTY V1 D0 timers extended over the day, against the D0 times of NIFTY V2 and SENSEX V2.
* The same phase-shifted null.

**T4 — what each timer looks like.** A table of the D-1 and D0 timers: period, start, last, count, second offset. Then a chart (one row per timer).

## Acceptance
* **Timers are real** if the real share is above the 95th percentile of the null in T1, and at least 3× its mean.
* **"D0 reuses D-1's scheduler"** if the same holds in T2.
* Anything else is reported as not supported. The share of D0 times not explained by any timer is reported plainly.

## Not tested here
Why a timer has its particular period, offset and window. That would need the configuration.

## Addendum A (post-hoc, written after the gapped-timer run, before its re-run)
* **Gapped timers.** A timer may skip a slot, as long as at least 60% of the slots in its span fire. These were added after the strict timers left about 35% of D0 times unexplained.
* **Skip penalty.** The first gapped run picked a 15-minute timer with 2 skipped slots for 12:31:28, 13:01:28, 13:31:28, where a 30-minute timer with no skips explains the same members. Fix: the cost of a timer becomes 1.5 + 0.3 × (skipped slots), so a timer prefers the largest period that explains its members.
* **Re-run.** The gapped decomposition, its coverage against the null and its forward test are re-run with the penalty. Numbers from the run without the penalty are not reported.
* **The "timers running" table.** It is descriptive. No claim is made about a trend through the day.
