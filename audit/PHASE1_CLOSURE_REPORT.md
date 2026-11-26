# Algo 8, Phase 1: closure report (Gate 8, updated after the Phase 1 final loop)

> ## UPDATE 2026-11-25 (Phase 1 final loop): what changed, and what supersedes the text below
> **Final Phase 1 verdict: CONDITIONAL (unchanged).** Decision record: `backtest/replication/deep_dive/reports/PHASE1_LOOP2_RESULT.md` (plans and preregistered criteria: `PHASE1_LOOP2_{A,B,C,D}_PLAN.md`). Where the text below disagrees with this box, **this box wins**.
> | Item | Outcome |
> |---|---|
> | Population reconciliation | D0 log 29,959 orders / 33 cycles = evaluated 26,430 / 30 + excluded 3,529 / 3 (no D-1 record). **Every D0 and integrated number covers 30 of 33 cycles (88.2% of D0 orders)**; D-1 numbers cover 32 cycles. |
> | A. Premium-triggered ladder (H6) | **Rejected at the decision level**: F1 0.460 vs spot 0.437, gain +0.023, interval lower bound -0.002. No engine variant. |
> | B. D-1 session stop | Cycle-stop rule **confirmed on the real book** in D-1 and D0 (12/12 stops, 0 false alarms) after correcting the constant 1.20 -> **1.25 lakh** (interval (1.2177, 1.2902]; 1.20 false-alarmed on two D-1 sessions). Free-running D-1 stop in the engine **rejected** (4 false stops, scheduled straddles 2,046 < 2,076). Session vs cycle scope not separable in D-1. |
> | C. D0 clearance spread | The 15:30+ block is **one cycle** (SENSEX 2026-08-13, 15:33). Post-auction 15:14 in 9 of 10 cycles; pre-auction = flow + sweep at 364. CH1/CH2 **rejected** (CH2 near-miss), CH3 not supported. **X1 (15:18) demoted to an experimental in-sample candidate; production/forward default stays 15:14 (minute 359).** |
> | D. 15:30 candle-close bursts | 7 of 8 bursts start **before** the candle completes: the original condition is not causal. Causal analogue (minute 369): 6/8, p 0.0089, precision 0.60: **plausible but unconfirmed**; no engine change, session not extended. |
> | Gate 1 | PASS (was CONDITIONAL): criterion (d) met. All other gate statuses unchanged. |
> | Final metrics (OOF, keys F1 60 s) | D-1 **0.739** (strict 0.472, lot-level 0.6878); D0 mode T **0.420** forward / 0.422 historical (LOCO 0.427 / 0.428); integrated mode F combined **0.497 / 0.498** (D-1 0.739, D0 0.395 / 0.397; placebo 0.256). Headline keys F1 moved by at most 0.002. |
> | Frozen configuration | **freeze v2** `outputs/phase1/9/freeze_v2/freeze_manifest_v2.json` (v1 untouched); two D0 configurations (forward, historical-reproduction); sources changed only by default-off switches (listed with reasons). |
> | Regression | see section 7 below (re-run at the end of the loop). |
> | Independent validation | **none exists**. |


*2026-11-25. Everything is **uncommitted and unpushed** (no instruction to commit was given). Evidence label throughout: **historical reproduction on development cycles; no independent validation exists**. All numbers below are read from the output files named; none is typed from memory. The OMS was not touched.*

## 0. Verdict
**PHASE 1: CONDITIONAL.** The reconstruction is built, frozen, regression-tested and honest about its limits; it is **not** a proven or independently validated replica. The D-1 engine reproduces the real D-1 order stream at keys F1 0.739 (60 s) and strict F1 0.472; the D0 engine at 0.422 / 0.143 (teacher-forced) and the integrated D-1 + D0 cycle at 0.498 (free-running); all well above shift placebos, none at the order-by-order level the quality standards asked for. Phase 1 closes with open items that are data-limited or still feasible-but-untested (`PHASE1_UNRESOLVED_RULES.md`).

## 1. Gate-by-gate
| Gate | Verdict | One-line reason | Report |
|---|---|---|---|
| 0 | **PASS** | baselines B0/B1 verified, hashed, replay identical | register section 3 |
| 1 | **PASS** (re-evaluated in the final loop; was CONDITIONAL) | classification, provenance and final register done; criterion (d) met after U1-U4 (H6, G1b, D-1 stop, clearance spread) were executed to their stop rules (all rejected or classified). 12 rules remain Unresolved: a finding, not an open obligation | `PHASE1_RULE_REGISTER_FINAL.md`, `PHASE1_UNRESOLVED_RULES.md` |
| 2 | **CONDITIONAL** | 2A FAIL (10 variants rejected), 2B CONDITIONAL, 2C FAIL (C1 diagnostic only), 2D FAIL | `PHASE1_GATE2_SUMMARY.md` |
| 3 | **CONDITIONAL** | 3a, 3b, 3c run to stop rules; none supported (54.5% of missing buy-backs are upstream) | `PHASE1_GATE3_SUMMARY.md` |
| 4 | **CONDITIONAL** | 7 of 10 D-1 standards pass; Q2 strict 0.472 < 0.55, Q5 wing sell 0.497 < 0.50, Q9 book distance 0.508 > 0.35 fail (data-limited) | `PHASE1_GATE4_RESULT.md` |
| 5 | **CONDITIONAL** | 5a PASS (engine = reference 49/49); 5b measured; 5c CONDITIONAL (X1 accepted candidate, X3 rejected, stop rule confirmed on real book); 5d CONDITIONAL (7 of 13 standards pass) | `PHASE1_GATE5{A,B,C,D}_*.md` |
| 6 | **PASS** (integration criteria) | handoff identity 49/49, determinism, no real input, mode F D0 = 94% of mode T | `PHASE1_GATE6_RESULT.md` |
| 7 | **CONDITIONAL** | LOCO, parameter stability, causality (18/18), timing-specificity all pass; no independent data | `PHASE1_GATE7_RESULT.md` |
| 8 | **DONE** (freeze and closure) | configs frozen and hashed, full regression green, registers and reports written; Phase 1 CONDITIONAL | this report |

## 2. Final D-1 order matching (B1 = frozen engine, `one_lot_v2`, mode F, 32 cycles, 9,915 real vs 9,035 simulated orders)
| Tolerance | keys | strike within 1 | strike exact | strike and lots exact |
|---|---:|---:|---:|---:|
| 0 s | 0.213 | 0.207 | 0.178 | 0.178 |
| 5 s | 0.498 | 0.465 | 0.387 | 0.376 |
| 60 s | **0.739** (recall 0.706, precision 0.775) | 0.653 | 0.506 | **0.472** |
Legacy lot-level F1 **0.6878** (unchanged since Gate 0); shift placebo 0.326; per-cycle F1 median 0.742, minimum 0.661 (all 32 cycles >= 0.60); 0 refused orders.
| Class | Real | Sim | Recall | Precision | F1 |
|---|---:|---:|---:|---:|---:|
| body_buyback | 1,324 | 933 | 0.490 | 0.689 | 0.573 |
| body_sell | 4,408 | 4,091 | 0.733 | 0.787 | 0.759 |
| lump | 73 | 54 | 0.274 | 0.407 | 0.328 |
| not_modelled | 178 | 0 | 0.382 | n/a | n/a |
| opening_wings | 186 | 186 | 0.978 | 0.758 | 0.854 |
| wing_buy | 3,146 | 3,270 | 0.830 | 0.815 | 0.822 |
| wing_sell | 600 | 501 | 0.410 | 0.631 | 0.497 |

## 3. Final D0 (D0-C = Gate 5a engine + candidate X1; mode T, OOF 30 cycles, `events`, 60 s)
Real 26,430 vs simulated 17,906 orders; keys F1 **0.422** (CI 0.384-0.457); strict F1 0.143; legacy lot-level 0.414; shift placebo 0.238; forward A 0.472, forward B 0.392; true leave-one-cycle-out 0.428. D0 standards: 7 of 13 pass (D6, D7, D8, D10, D11, D12, D13); D1, D2, D3, D4, D5, D9 fail.
| Class | Real | Sim | Recall | Precision | F1 |
|---|---:|---:|---:|---:|---:|
| body_buyback | 8,350 | 9,269 | 0.319 | 0.349 | 0.333 |
| body_long | 1,637 | 113 | 0.244 | 0.655 | 0.355 |
| body_sell | 7,905 | 3,974 | 0.396 | 0.756 | 0.520 |
| not_modelled | 164 | 0 | 0.652 | n/a | n/a |
| stop | 387 | 260 | 0.093 | 0.650 | 0.163 |
| wing_buy | 4,515 | 2,384 | 0.470 | 0.739 | 0.574 |
| wing_sell | 3,472 | 1,906 | 0.256 | 0.581 | 0.356 |

## 4. Integrated D-1 + D0 (mode F, no real input anywhere; OOF 30 cycles)
D-1 part 0.739 (= B1); D0 part 0.397 (mode T 0.422); combined 0.498 against placebo 0.255; strict combined 0.228. Forward A D0 0.477, forward B D0 0.269 (0.69 of mode T: the weakest set). The engine stops in 13 of 30 cycles (real 11).

## 5. Portfolio-state reconciliation
* **Handoff identity:** D0 opening net position and cash equal the D-1 simulated broker state in 49 of 49 runs (cash difference < 1e-9 Rs); `reconcile` holds at the end of every D0 run (49/49).
* **Engine vs real book:** at the D0 open the simulated and real books differ by a median 0.790 (L1 / real gross lots), short-lot count ratio 0.95. In mode T the opening mark-to-market equals the real book in 29 of 30 cycles. D-1 median normalised book distance at matched events 0.508 (Gate 4, Q9 fail).

## 6. Risk-control verification
D-1: 0 refused orders, peak short lots per right 130 (limit 400). D0 (enforce, 49 runs): 0 refused, 0 violations, peak short lots per right 279 (limit 306; real envelope 278), peak sell decisions per minute 19 (limit 90). The limits are observed envelopes, not original controls.

## 7. Regression results (run at closure; `outputs/phase1/8/regression_results.json`)
| Suite | Result |
|---|---|
| `d1_strategy` | 56 passed, 0 failed |
| `d0_strategy` | 15 passed, 0 failed |
| `algo8_integrated` | 4 passed, 0 failed |
| `backtest/tests` | 34 passed, 0 failed |
| `backtest/replication/execution_parity/tests` | 33 passed, 0 failed |
| `backtest/replication/lot_lifecycle/tests` | 28 passed, 0 failed |
| `algo8_replica/tests` | 13 passed, 0 failed |
| `data_validation/tests` | 27 passed, 0 failed |
| `backtest/replication/deep_dive/tests` | 334 passed, 0 failed |
| **Total** | **544 passed, 0 failed** |

Also verified: default D0 configuration reproduces the Gate 5a reference in 49 of 49 split-cycle runs (re-executed by the freeze script, not read from a stored file); B0/B1 baseline immutability and live-engine-equals-B0 replay (`tests/test_phase1_baseline.py`); D-1 legacy lot-level F1 0.6878 on the integrated replay; frozen sources, configurations and artefacts keep their hashes (`tests/test_phase1_gate8_freeze.py`). Gate 0 had deep_dive 288 and d1_strategy 47 tests; they are now 334 and 56 (new gate tests and switch tests, mutation-checked).

## 8. Accepted corrections and rejected variants
| Item | Status |
|---|---|
| `one_lot_v2` execution convention (opening wings and stop buy-backs sent as single lots; guard counts decisions) | **Accepted** (user, 2026-11-25), baseline B1 |
| D0 X1: pre-auction clearance at minute 363 | **Experimental in-sample candidate; NOT a production default** (kept only in the historical-reproduction configuration) |
| D0 / frozen stop constant 1.20 -> 1.25 lakh | **Accepted** (measured contradiction on the real book: 1.20 gives 2 false alarms in D-1 sessions) |
| 5b scoring-layer fix (stop parts aggregated per contract and kind) | Accepted (first run archived) |
| 2A: V01 book condition, V02-V09 | **Rejected** (V01 F1 0.770 but extras 639, fails A1/A3/A4) |
| 2B: S2, S4, S5, S8, S9 alternative strike rules | Rejected (engine rule stands) |
| 2C: C1 rebased futures feed / C2 late gate | C1 **diagnostic input convention only**; both rejected as rules |
| 2D: delayed breakout depth sizing (4 runs) | Rejected |
| 3a: K1-K6 buy-back stops and latency | None supported |
| 3b/3c: ten wing/lump rules | None supported |
| 5c: X3 opening-long clock | **Rejected** (O1, O2 fail) |
All rejected runs are archived under `outputs/phase1/`; B0/B1 are immutable (`tests/test_phase1_baseline.py`).

## 9. Unresolved rules
`PHASE1_UNRESOLVED_RULES.md` (A: U1-U4 executed in the final loop; B: data-limited; C: decisions for the user). Final class counts: `PHASE1_RULE_REGISTER_FINAL.md` (Unresolved 15 to 12, three rows moved: D1-15, D0-06, X-01).

## 10. Data limitations
No tick or one-second data (solo counts, stop timing, late-sale tracker, burst membership); no decision logs, margin or capital (sizing, lump size); no post-22-Oct exports; no regime B (after 7 Dec 2026) logs; no-trade days not exported; 3 D0 cycles without D-1 logs excluded (3,529 orders); minute-resolution simulated times; D-1 stop module absent.

## 11. Independent-validation status
**None.** Every cycle is a development cycle. D0 constants are out-of-fold and LOCO-stable, but structures were chosen with all cycles visible, about 45 ideas were tested in Phase 1 alone on the same data, and the pseudo-forward splits share structure. Closing it needs post-freeze expiries with order logs (or live paper trading with the frozen configuration) scored once with spec v1.1.

## 12. Frozen files and hashes (`outputs/phase1/8/freeze_manifest.json`; pinned by `tests/test_phase1_gate8_freeze.py`)
| Source | sha256 (prefix) |
|---|---|
| `algo8_integrated/__init__.py` | `a62453231dcee7db…` |
| `algo8_integrated/handoff.py` | `e701a925dabb5029…` |
| `algo8_integrated/runner.py` | `cd6a97506e3678c6…` |
| `algo8_integrated/test_integrated.py` | `99efd0bf0341751f…` |
| `d0_strategy/d0_algo/__init__.py` | `29134337ea5d8847…` |
| `d0_strategy/d0_algo/config.py` | `2eece8564b10efe1…` |
| `d0_strategy/d0_algo/engine.py` | `2bbcb16880082bca…` |
| `d0_strategy/test_d0_engine.py` | `3a95b2f9844258ad…` |
| `d1_strategy/d1_algo/__init__.py` | `30f772fe78f71503…` |
| `d1_strategy/d1_algo/bars.py` | `e944032682e61929…` |
| `d1_strategy/d1_algo/book.py` | `5da44214ac1c354a…` |
| `d1_strategy/d1_algo/config.py` | `df06fc93b1d0c72a…` |
| `d1_strategy/d1_algo/engine.py` | `8940fb2a1083fb2b…` |
| `d1_strategy/d1_algo/interfaces.py` | `2c1f6691d9daab81…` |
| `d1_strategy/d1_algo/live_template.py` | `8407f2eafffe5b85…` |
| `d1_strategy/d1_algo/models.py` | `31a6cd1085ada4ba…` |
| `d1_strategy/d1_algo/risk.py` | `d7648f72ad7099bf…` |
| `d1_strategy/d1_algo/shadow.py` | `6d4b860853f88fc0…` |
| `d1_strategy/d1_algo/shadow_state.py` | `6c1efa766c32a08b…` |
| `d1_strategy/d1_algo/sim.py` | `8f51d215611da4d3…` |

| Artefact | sha256 (prefix) |
|---|---|
| `phase1/baseline_manifest.json` | `f46d2efd92a810d8…` |
| `phase1/5d/summary.json` | `400ac7f0e7afa1b2…` |
| `phase1/5d/standards.json` | `86fc810dfd4b6873…` |
| `phase1/6/summary.json` | `5688897e51a8e74b…` |
| `phase1/6/acceptance.json` | `a36d8701981a830c…` |
| `phase1/7/tests.json` | `b10f331d3bf984c1…` |
| `phase1/5c/acceptance.json` | `7f6fd7a8aed6cb18…` |
| `scoring/spec_freeze.json` | `aa39172ae663f77b…` |
| `scoring/execution_convention.json` | `b6a05d39b89aa306…` |

Frozen configurations: `frozen_d0_params.json` (`234d2902e10ad76d…`), `frozen_d0_configs_per_cycle.json` (`b71e83d00d9f4a8d…`), `frozen_d1_configs_per_cycle.json` (`b5f98e549673ca86…`). The frozen D0 parameters are an **all-cycle fit (in-sample)**; scored evidence in this report comes from out-of-fold and LOCO runs only. The late-sale rule, score, hashes and shadow are untouched (identical to git HEAD). Baselines: B0 and B1 hashed in `outputs/phase1/baseline_manifest.json`.

## 13. Phase 1 verdict
**CONDITIONAL.** What can be relied on: the engines run, are deterministic, causal (18/18 perturbation tests), risk-guarded, stable under leave-one-cycle-out, and beat time-shift placebos clearly. What cannot be claimed: that they replicate the original system order by order, that any rule beyond the decoded timetable, stop and hedge mechanics is understood, or that any of it holds out of sample. Next decisions are the user's (`PHASE1_UNRESOLVED_RULES.md`, section C).

## 14. Final-loop regression (2026-11-25; `outputs/phase1/9/regression_results_final.json`) - supersedes section 7
| Suite | Result (final loop) |
|---|---|
| `d1_strategy` | 60 passed, 0 failed |
| `d0_strategy` | 17 passed, 0 failed |
| `algo8_integrated` | 4 passed, 0 failed |
| `backtest/tests` | 34 passed, 0 failed |
| `backtest/replication/execution_parity/tests` | 33 passed, 0 failed |
| `backtest/replication/lot_lifecycle/tests` | 28 passed, 0 failed |
| `algo8_replica/tests` | 13 passed, 0 failed |
| `data_validation/tests` | 27 passed, 0 failed |
| `backtest/replication/deep_dive/tests` | 350 passed, 0 failed |
| **Total** | **566 passed, 0 failed** |

Includes: all unit, deep-dive, D-1, D0, integration, mutation-checked switch tests, the causality (future-bar perturbation) tests, the freeze-v1 and freeze-v2 hash tests, determinism and risk checks, the population reconciliation test, and the final-validation pin tests. The default D0 configuration reproduces the Gate 5a reference in **49 of 49** runs (re-executed by the freeze-v2 script); B0/B1 immutability and the live-engine-equals-B0 replay hold; the D-1 replay with all defaults gives legacy lot-level F1 0.6878 and keys F1 0.7392 (B1). One test (`test_order_type_matches_log`) failed after the new default-off roles were added and was corrected (the new `cycle_stop` roles belong to the `s_` module, outside the 9,885 orders it compares); nothing else failed at any point.

## 15. Frozen configuration v2 and hashes (supersedes section 12; v1 is kept unchanged)
`outputs/phase1/9/freeze_v2/freeze_manifest_v2.json` (sha256 of v1 manifest `d36e2a4a7aa0a05f...` pinned inside). D0 parameters: unchanged all-cycle fit (`outputs/phase1/8/frozen_d0_params.json`, `234d2902e10ad76d...`, in-sample).
| Artefact | sha256 (prefix) | Meaning |
|---|---|---|
| `frozen_d0_configs_forward.json` | `705e05dc59288ab4...` | **production/forward**: clearance 359 everywhere, stop 1.25 lakh, enforce guard, all candidates off |
| `frozen_d0_configs_historical_reproduction.json` | `3d2f619b85af4336...` | forward + EXPERIMENTAL in-sample pre-auction clearance 363 (X1) |
| `frozen_d1_configs_per_cycle.json` | `e3d206cac38b1a56...` | D-1 B1 (`one_lot_v2`); rejected stop off |
Source files changed since v1 (all default-off switches, reasons recorded, none unexplained): `d0_strategy/d0_algo/config.py`, `d0_strategy/d0_algo/engine.py`, `d0_strategy/test_d0_engine.py`, `d1_strategy/d1_algo/config.py`, `d1_strategy/d1_algo/engine.py`, `d1_strategy/d1_algo/risk.py`, `d1_strategy/test_cycle_stop.py`. All other source hashes equal v1; the late-sale rule, score, hashes and shadow are untouched.

## 16. Remaining unresolved rules and limitations (after the final loop)
Rule classes: `PHASE1_RULE_REGISTER_FINAL.md` (Unresolved 15 to 12). Data-limited: solo counts and timing, sizing, buy-back burst membership, opening solo sells, long strikes, lump size, late-sale tracker, no-trade filter, regime B (after 7 Dec 2026), decision times of body orders. Limits: development cycles only; about 56 ideas tested in Phase 1; D-1 session stop absent from the engine (rejected); wings carried as `h_`; D0 evaluation covers 30 of 33 cycles; frozen D0 parameters are an in-sample fit; X1 is in-sample on 8 cycles. **Independent validation: none exists** (needs new expiries with order logs or live paper trading with the frozen forward configuration).
