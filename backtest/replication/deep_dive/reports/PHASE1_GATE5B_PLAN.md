# Phase 1, Gate 5b: D0 order-level reconstruction. Plan and conventions

*Written 2026-11-25. **Honest status: the scoring conventions below were fixed in code (`src/bl_p1_5b.py`) before the first scoring run; this file records them after the fact, before any result was interpreted.** Measurement gate: no engine change, no acceptance threshold beyond the Gate 5a identity (already PASS). Experiments `P1-5B-*`. Nothing committed.*

## 1. Objective
Score the standalone D0 engine (Gate 5a, identical to the research simulator) against the real D0 order log **at order level** with the frozen scoring spec v1.1, and classify every mismatch. Teacher-forced mode T: each cycle starts from the **real carried D-1 book**; free-running D-1→D0 handoff is Gate 6.

## 2. Conventions (fixed in code before first scoring run)
| Item | Convention |
|---|---|
| Simulated timestamps | engine events are lot-event, minute-level: placed at minute start (33300 + 60·j); `t_resolution = 'minute'` |
| Real time | `t_first` of each real order |
| Primary orders convention | `events`: one simulated event = one order split at the contract freeze (27 NIFTY / 50 SENSEX) |
| Sensitivity | `one_lot`: scoring-layer split of every event into single-lot orders (not an engine change) |
| Real validity | from the log (day orders `num`; `h_`/`v_`/`m_` IOC; `s_` mixed → blank) |
| Real class map | legacy CLS map; `s_` module → `stop`; unmapped → `not_modelled` |
| Stop events | split into per-component orders (buy for body_short/oshort, sell for long) |
| Splits | OOF (leave-one-cycle-out fitted parts), forward A, forward B (as the research simulator) |
| Scorer | `Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=True, bootstrap=1000)` |
| Mismatch ledger | cascade S (supply/count: counterpart of same type within 60 s) / W (wrong strike/lots) / T (timing beyond tier) / A (absent) per class, window and category |

## 3. Coverage (stated before results)
33 D0 cycles in the log (29,959 orders); **30 replayable** (26,430 orders). Three D0 cycles (NIFTY 2026-06-23, 2026-08-11, 2026-09-15; 3,529 orders) have no D-1 logs, so no real carried book: **excluded and reported, not replaced.**

## 4. What 5b may not do
No parameter is changed; no result is used to change a rule inside this gate; classes are not dropped. Rule corrections belong to 5c under their own preregistration.
