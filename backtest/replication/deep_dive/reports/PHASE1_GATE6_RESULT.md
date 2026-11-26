# Phase 1, Gate 6: integrated D-1 + D0 engine. Result

*Components: frozen D-1 engine at B1 (`one_lot_v2`) and D0-C (Gate 5a engine + candidate X1), unchanged. **Mode F: no real order or position enters anywhere**; the D0 opening state is built from the simulated D-1 session only (`algo8_integrated/`). Evidence: **historical reproduction on development cycles; not independent**. Plan and criteria fixed before the run: `PHASE1_GATE6_PLAN.md`. Code executed, results observed (`outputs/phase1/6/`). Nothing committed.*

## Headline (RESULT)
**Gate 6 verdict under the preregistered criteria: PASS** (G6-1 to G6-9 all hold). Read it for what it is: **the integration is mechanically correct and does not degrade the components; it is not evidence that the reconstruction is accurate.** The D-1 part reproduces B1 exactly (keys F1 0.739, legacy lot-level 0.6878); the D0 part, free-running from the simulated carry, keeps 94% of its teacher-forced score; the continuous D-1 + D0 cycle scores keys F1 0.498 against a 0.255 shift placebo.

## Acceptance
| # | Check | Verdict |
|---|---|---|
| G6-1 | handoff identity (net positions, cash), reconciliation at the D0 end | **PASS** |
| G6-2 | no real input: runner signature, source tokens | **PASS** |
| G6-3 | carried contracts outside the D0 chain (rejected handoffs) | **PASS** |
| G6-4 | regression: mode T D0-C keys F1 / legacy; D-1 legacy lot-level F1 | **PASS** |
| G6-5 | determinism on rerun | **PASS** |
| G6-6 | mode F D0 keys F1 >= 0.8 x mode T and >= placebo + 0.10 | **PASS** |
| G6-7 | integrated D-1 + D0 keys F1 >= placebo + 0.10 (D-1 and D0 parts reported) | **PASS** |
| G6-8 | carry error at the D0 open (diagnostic, no threshold) | **PASS** |
| G6-9 | risk controls: refused orders, peak short lots per right (D-1 limit 400, D0 limit 306), peak sell decisions | **PASS** |

## Mode F versus mode T (60 s keys F1, `events`)
| Set | Cycles | D0 mode T (5d) | D0 mode F | D0 placebo | D-1 (B1 part) | D-1 + D0 | placebo | median carry distance at D0 open | simulated/real short lots (median) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| OOF | 30 | 0.422 | 0.397 (0.94x) | 0.224 | 0.739 | 0.498 | 0.255 | 0.790 | 0.95 |
| forwardA | 9 | 0.472 | 0.477 (1.01x) | 0.219 | 0.725 | 0.572 | 0.260 | 0.786 | 0.93 |
| forwardB | 10 | 0.392 | 0.269 (0.69x) | 0.127 | 0.715 | 0.441 | 0.205 | 0.886 | 1.20 |

## What the numbers say (adversarial reading)
* **Carry error is large but D0 order agreement barely depends on it** (the explanation that follows is an inference; no ablation by module was run). At the D0 open the simulated and real books differ by a median 0.790 (L1 / real gross lots; IQR 0.624-0.985), yet the short-lot count is close (ratio 0.95). Mode F keeps 94% of the mode T OOF score. This means the D0 order-level agreement is carried mostly by modules that do not need the exact carried lots (timetable waves, hedge clock, clearance clock, solo/ladder), and that the carried-lot-dependent classes (buy-backs, stop) are the ones that score poorly in both modes. **The mode T numbers therefore do not overstate D0 quality because of teacher forcing; they are limited by the decision rules.**
* **Forward B is weaker in mode F** (0.269 vs 0.392 in mode T; ratio 0.69, below the 0.80 bar if that bar were applied to this set; the preregistered bar applies to the OOF set). Forward A is equal (0.477).
* **Stops:** the integrated engine stops in 13 of 30 OOF cycles (real 11; mode T 11), using cumulative simulated cash including the simulated D-1 result.
* **Strict agreement is low** (D0 mode F strict F1 0.127; combined 0.228).

## Handoff contract and its limits
Short lots with the D-1 engine's entry prices; wing longs as `h_`, lump as `v_`; cash from simulated fills. **Labelled assumption:** the D-1 engine books its opening wings with the protective wings, so they carry as `h_` (real: `num`); quantities and contracts are unaffected, but they are cleared as wing sells rather than body longs. **Not modelled:** the `s_` stop module of D-1 sessions (the D-1 engine has none). Three D0 cycles without a D-1 cycle record are not integrated. One replay realisation per cycle (intrabar path order is a convention).

## Gate 6 status: **PASS** (integration criteria); quality remains **CONDITIONAL** at the component level (Gates 4 and 5d).
