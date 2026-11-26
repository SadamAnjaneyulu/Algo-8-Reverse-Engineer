# Phase 1, Gate 5a: standalone D0 engine. Result

*2026-11-25. Experiments `P1-5A-ref` (reference determinism), `P1-5A-port` (engine versus reference), `P1-5A-env` (real D0 envelope). Engine: `d0_strategy/d0_algo/` (new package). The research simulator (`bl_d0_fr.py` and its parts) is **unchanged** (hashes in `outputs/phase1/5a/reference_hashes.json`, tested). Mode T (teacher-forced start: the real carried book is an explicit opening-state input). Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 5a: build the standalone D0 engine (port, no strategy change) |
| Status | **PASS** |
| Baseline | research simulator `bl_d0_fr.py::sim`; saved outputs `outputs/bl_d0_fr_orders.pkl.gz`; legacy D0 lot-level F1 0.410 out-of-fold |
| Latest result | the engine reproduces **49 of 49** saved test-cycle outputs **event for event** (four splits: OOF halves 15 + 15, forward A 9, forward B 10); legacy lot-level D0 F1 **0.410294 = reference 0.410294** (40,874 real lots, 40,024 simulated, 16,596 matched); 49 of 49 reconcile; 49 of 49 deterministic on rerun; 20 cycles end in a cycle stop, 29 in the 15:14 clearance |
| Criteria | reference unchanged **PASS** (hash test); engine reproduces reference **PASS**; legacy F1 within tolerance **PASS** (difference 0.0); position accounting reconciles **PASS** (opening position plus signed event lots equals the engine's end position, contract by contract); contract identities and quantities **PASS**; decision keys and order classes **PASS** (events identical); risk constraints enforced **PASS** (guard below); deterministic **PASS**; unit, integration, regression tests **PASS** (10 engine tests, 3 port contract tests, mutation-checked) |
| Root causes | none (port) |
| Corrections | none to strategy behaviour |
| Regression | none; D-1 engine and B0/B1 untouched |
| Evidence | `outputs/phase1/5a/{ref_determinism.json, port_check.json, ref_params.pkl, engine_events_mode_T.pkl.gz, real_d0_envelope.json, reference_hashes.json}`, `src/bl_p1_5a_*.py`, `d0_strategy/test_d0_engine.py`, `tests/test_phase1_gate5a_port.py` |
| Next action | Gate 5b |

## What was built
* `D0Engine` with explicit state (carried short lots with entry prices, other-module longs and shorts, cash), the reference's per-minute rule order (cycle stop, 15:14 clearance, buy-backs on the minute high and take-profit on the low, timetable waves, breakout pairs, solo ladder, counter-sells, opening wings, hedge controller) and **one switch per rule**. Inputs are the market arrays, the configuration and the opening state; **the engine has no real-order input** (tested by signature and by a source check).
* Configuration holds the per-split fitted parts (timetable waves, stop and take-profit ratios, ladder step, gate and multiplier, counter-sell ratio, opening-wing lots) captured from the **unchanged** reference fit; they are inputs, not re-fitted.
* Validation: quantities positive, carried contracts inside the chain, opening positions positive; deterministic event order; position accounting (`position()`, `reconcile()`).

## Findings recorded during the port (not behaviour changes)
1. **Reference determinism:** all 49 saved outputs recompute identically from the reference code.
2. **Real D0 envelope (observed):** at most **90 orders per minute**, **488 lots per minute**, **278 net short lots per right**. The D-1 engine's 40 decisions per minute and 400-lot limits do not fit D0.
3. **Risk guard:** the research simulator had none. The D0 guard applies to risk-adding sells with limits equal to the **observed real envelope** (278 net short lots per right, plus a 10% margin = 306, because the envelope was measured netted per contract; 90 sell decisions per minute). With these limits the reference replay is **never refused** (0 rejections in 49 cycles, both modes). A first attempt with the D-1 limits refused 137 sells (they do not apply to D0); one at the exact 278 refused 3 single lots, two of them at minute 0 on the carried book, which showed the definition gap and led to the stated margin. `risk_mode='monitor'` records breaches without refusing.
4. **Clearance:** the research simulator clears the whole book in **one minute (359)**, up to 241 events in a minute, whereas the real D0 log never exceeds 90 orders per minute: the real clearance is spread over several minutes. This is a **finding for Gate 5c**, not corrected here.

## Limits
Time resolution is one minute (the reference's); the opening state in mode T is the real carried book (the D-1 simulator's carry enters in Gate 6); fitted parameters are in-sample (training splits of the same development cycles); the engine mirrors, not improves, the reference.
