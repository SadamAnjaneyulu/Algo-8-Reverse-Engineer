# Phase 1, Gate 2 summary: D-1 body-sell reconstruction

*2026-11-25. All four sub-gates were run to their preregistered stop rules on existing data. No variant met the preregistered acceptance criteria; nothing was added to the baseline. Everything is uncommitted.*

## Status: **CONDITIONAL** (not PASS)
The Gate 2 pass criteria ("missed and extra solo sells both addressed; strike, quantity, side and timing jointly; full-cycle results improve against the frozen baseline") are **not met by any rule correction**. The remaining errors are quantified and classified as data-limited. Gate 2 is closed as a **conditional** gate because the limitation, not the effort, ends the loop: 16 engine runs (13 candidate engine variants plus 3 baseline-reproduction checks), 10 teacher-forced strike rules and 3 analytic tests were run; the strict preregistered criteria were never relaxed.

| Sub-gate | Result | Runs | Outcome |
|---|---|--:|---|
| 2A solo trigger | FAIL, rejected | 9 variants + 3 analytic tests | book-state condition is the only partial signal (precision +4.5 points, extras -27%, fails A1/A3/A4); H1, H2, H3 contradicted at order level |
| 2B solo strike | CONDITIONAL | 10 rules (teacher-forced) | engine rule 0.50 exact / 0.88 within one with real context; no alternative supported; F loses 0.23 to inherited context |
| 2C 15:00+ | FAIL, rejected | 2 variants | index is frozen from 15:15 in post-auction cycles; rebased futures remove 198 of 241 spurious late fires (overall F1 +0.013, legacy lot F1 +0.012) but late recall is 0.12-0.15 of 165 real sells; feed convention left as an open decision |
| 2D breakout / pair sizing | FAIL, rejected | 4 variants | delayed depth sizing adds false orders as fast as true ones |

## Best measured state of body sells (B1 unless stated; historical reproduction)
Order-level F1 (keys, 60 s) **0.759**; strict (strike and lots exact) **0.595**; scheduled straddles 2,086 of 2,112 matched; **1,179 missing / 873 extra** real versus simulated body sells. Partial improvements that are **not adopted** because they failed registered criteria: V01 book condition (F1 0.770, strict 0.615, extras 639, legacy lot F1 0.698) and C1 rebased futures from 15:15 (F1 0.771, strict 0.611, legacy 0.699). **Their combination was not run** (it would be a new search on the same cycles; it is listed as an open candidate, not a result).

## Why the loop ends here (stated, quantified)
* Every order-level parameterisation of the solo ladder, the breakout size, the strike reference and the late gate was tested against fixed criteria; improvements in one measure were always paid for in another (recall versus precision), which is the signature of a decision variable the data do not contain (the tick path: earlier work found solo lots are dripped over about 5 s; `D1_LOTS.md`).
* The reproducible part is large: clock-driven straddles (94.5% strike, 66.9% exact second), pair timetable, wing controller quantity (98%), order mechanics. The irreducible part is the **timing and count of the reactive sells**.
* Not repeated: the Gate 2A parameter searches (per instruction).

## Open items carried forward (not blocking)
1. Candidate corrections that improve overall measures but fail the registered bars: V01 and C1 (above). Whether to adopt either as an **input/convention** is a separate decision (recorded in `phase1_gate_state.json`; Gate 8).
2. G1b closing pairs (candidate, excluded).
3. Re-measure wing, buy-back and lump errors (Gate 3) as inheritors of these residuals.
