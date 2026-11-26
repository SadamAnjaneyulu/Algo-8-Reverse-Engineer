# Algo 8 Phase 1: master gate register (living document)

*Created 2026-11-25 at Gate 0. Updated at the end of every execution session. Machine-readable state: `phase1_gate_state.json`. All work is uncommitted by instruction; nothing is pushed. OMS work is not started. Evidence discipline: Confirmed / Decoded / Partial / Candidate / Unresolved; observed facts, inferred mechanisms and assumptions are kept apart.*

## 1. Gate status

| Gate | Objective | Status | Report |
|---|---|---|---|
| 0 | Repository and baseline audit | **PASS** | section 3 |
| 1 | Rule reconstruction completion | **PASS** (re-evaluated after the Phase 1 final loop; was CONDITIONAL: criterion (d) met once U1-U4 were executed to their stop rules; 12 rules remain Unresolved, a finding not an obligation) | section 4, `PHASE1_RULE_REGISTER_FINAL.md` |
| 2 | D-1 body-sell reconstruction | **CONDITIONAL** (all sub-gates run to their stop rules; no rule met the registered criteria; see `reports/PHASE1_GATE2_SUMMARY.md`). Sub-gates: **2A FAIL** (solo-trigger correction rejected; trigger Partial, count/timing data-limited); **2B CONDITIONAL** (no alternative strike rule supported; engine rule stands; 0.50 exact with real context, 0.25 in F); 2C FAIL (rejected; rebased futures feed removes spurious late fires but late recall 0.12-0.15); 2D FAIL (rejected; delayed depth sizing) | `reports/PHASE1_GATE2{A,B,C,D}_*`, `PHASE1_GATE2_SUMMARY.md` |
| 3 | D-1 buy-back, wing, lump | **CONDITIONAL** (3a, 3b, 3c run to stop rules; none supported) | `reports/PHASE1_GATE3{A,BC}_*`, `PHASE1_GATE3_SUMMARY.md` |
| 4 | D-1 full-system validation | **CONDITIONAL** (7 of 10 standards pass; Q2, Q5, Q9 fail, data-limited) | `reports/PHASE1_GATE4_{STANDARDS,RESULT}.md` |
| 5 | D0 reconstruction | **CONDITIONAL** (5a PASS: standalone D0 engine = reference 49/49; 5b measured (first run archived after a scoring-layer fix); 5c CONDITIONAL: X1 era clearance clock accepted as candidate, X3 rejected, stop rule confirmed on real book 11/11; 5d CONDITIONAL: 7 of 13 standards pass) | `reports/PHASE1_GATE5{A,B,C,D}_*.md` |
| 6 | Integrated D-1 + D0 validation | **PASS** (integration criteria G6-1..G6-9; mode F D0 keys F1 0.397 = 94% of mode T; combined 0.498; component quality remains CONDITIONAL) | `reports/PHASE1_GATE6_{PLAN,RESULT}.md`, `algo8_integrated/` |
| 7 | Independence and robustness review | **CONDITIONAL** (R1-R6 pass; no independent data exists) | `reports/PHASE1_GATE7_{PLAN,RESULT}.md` |
| 8 | Freeze and Phase 1 closure | **DONE: Phase 1 CONDITIONAL** (configs and sources frozen and hashed; 544 tests pass; registers and reports written; user review pending) | `audit/PHASE1_CLOSURE_REPORT.md`, `outputs/phase1/8/` |

## 2. Baselines (verified in this session, not copied from earlier reports)

| ID | What | Where | Key measured values |
|---|---|---|---|
| **B0** | Original F-mode engine, `freeze_v1` (order split at the freeze quantity only), frozen configuration | `outputs/scoring/d1_F`; engine snapshot `outputs/phase1/baseline_engine_B0/` | 8,735 simulated orders (9,915 real); legacy lot-level F1 **0.6878**; keys F1 at 60 s 0.736; replay reproduced identically at Gate 0 (`freeze_integrity.json`, 0 rejected) |
| **B1** | Accepted F run under `one_lot_v2` (user decision 2026-11-25; execution convention) | `outputs/scoring/d1_F_v2_onelot` | 9,035 simulated orders; legacy lot-level F1 **0.6878 (identical)**; keys F1 at 60 s **0.739**; strike-and-lots-exact F1 at 60 s **0.472**; 0 rejected |
| B1-body | Body sells in B1 | `outputs/bodysell/` | 4,408 real, 4,091 simulated; 3,229 matched, **1,179 missing** (M1 727, M4 305, M3 123, M2 24), **873 extra**; scheduled straddles 2,086 of 2,112 simulated matched; inferred module of the misses: solo 675, pair 486, scheduled clock 18; ladder solo extras 730; matched strike exact 78.4% (ladder partners 25.6%) |
| TF-E | Per-event teacher-forced diagnostics (all orders, first decisions, memory variant) | `outputs/scoring/d1_TFE_*` | diagnostic only; lower than F in 32 of 32 cycles for reasons of the reset (pre-emption, re-decision loop) |
Every baseline artefact is hashed in `outputs/phase1/baseline_manifest.json` (601 files); `tests/test_phase1_baseline.py` fails if any changes and checks that the live engine at default configuration still replays identically to the B0 snapshot. **Candidate runs always go to new directories and new experiment IDs.**

## 3. Gate 0 report

| Field | Content |
|---|---|
| Gate | 0: repository and baseline audit |
| Status | **PASS** |
| Baseline | branch `research/algo8-body-lifecycle`, last commit `593a488e`; 63 uncommitted files (57 new, 6 modified) |
| Latest result | all test suites pass: deep_dive 288 (284 + 4 new baseline tests), d1_strategy 47, backtest 34, execution_parity 33, lot_lifecycle 28, algo8_replica 13, data_validation 27; B0 and B1 replays reproduce exactly |
| Criteria | (1) important work identified: **PASS** (registry in section 5); (2) baseline recoverable: **PASS** (manifest, snapshot, replay); (3) existing tests pass: **PASS**; (4) no experiment silently overwritten: **PASS** (the two re-runs, the class-table defect and the guard-blocked attempt are archived; logs of reruns are kept under the run directories); (5) dependency map and remaining-work register: **PASS** (sections 6 and 7) |
| Root causes | none (audit gate) |
| Corrections | none to the engine; the reference figure "adjusted pooled lot-level F1 approximately 0.472" in the brief is the **strict order-level F1** (strike and lots exact, 60 s); the lot-level F1 is **0.6878**, unchanged. Recorded in section 8 |
| Regression | none |
| Evidence | `outputs/phase1/baseline_manifest.json`, `baseline_engine_B0/`, `tests/test_phase1_baseline.py`, `src/phase1_baseline.py`, `outputs/scoring/split_comparison/freeze_integrity.json` |
| Remaining work | section 7 |
| Next action | Gate 1 conclusion, then Gate 2A |

## 4. Gate 1 report

| Field | Content |
|---|---|
| Gate | 1: rule reconstruction completion |
| Status | **CONDITIONAL** |
| Baseline | Phase A register: 26 rules plus candidate G1b, with the Phase A vocabulary |
| Latest result | `PHASE1_RULE_CLASSIFICATION.md/csv`: 27 rows, 49 components: Confirmed 13, Decoded 10, Partial 10, Candidate 1, Unresolved 15; by least certain component: Confirmed 3, Decoded 2, Partial 6, Candidate 1, Unresolved 15. `PHASE1_ENGINE_RULE_PROVENANCE.md`: every engine rule and parameter mapped to a register row, evidence class and note |
| Criteria | (a) every material rule classified with evidence and limitations: **PASS**; (b) no major rule silently represented by an unsupported assumption: **PASS** (provenance table lists assumptions, fitted constants, safety limits, and the rules the engine lacks); (c) candidate rules separate from the baseline: **PASS** (G1b only, excluded); (d) **all feasible no-new-data investigations completed: NOT MET** (22 of 27 rows still need investigation; the feasible ones are the work of gates 2 to 5) |
| Decision recorded | Gate 1 and gates 2 to 5 overlap (Gate 1 lists the investigations that gates 2 to 5 execute). I treat criterion (d) as **delegated, not waived**: each open row carries the gate that investigates it (`delegated_to_gate`), and Gate 1 is **re-evaluated and closed at Gate 8** when the register is updated from the results. Gate 1 is therefore CONDITIONAL, not PASS. If you read the gate order differently, say so |
| Irreducible without new data (carried, not hidden) | decision logs and configuration; tick or one-second data (solo drip lots, stop timing, late-sale tracker); margin and capital (lump size, sizing); no-trade days; trade exports after 22 Oct 2026 (the only route to independent validation); order lifecycle data; regime B (post-7 Dec) |
| Next action | Gate 2A |

## 5. Experiment registry

Existing (see `reports/EXPERIMENT_LEDGER.md` for E00-E23): E00 skeleton fit; E01-E12 late-sale rule development; E13 battery; E14 earlier history (unrecoverable count); E15-E19 late-sale risk, trigger, focused, re-centring, sequence; E20 Phase A G1-G6; E21 one-lot convention (+ guard rule accepted); E22 TF-E; E23 body-sell ledger. New Phase 1 experiments use IDs `P1-<gate>-<n>` and are recorded in section 9 with their plan, baseline, output directory and decision.

## 6. Dependency map

```
data (1-min bars, real fills 32 D-1 / 30 D0 cycles, 3-year cache)
  -> D-1 engine (d1_strategy/d1_algo)  [B0 snapshot, B1 = one_lot_v2]
       -> scorer v1.1 (bl_oscore.py, frozen spec)  -> F runs (B0, B1)
            -> TF-E harness (bl_tfe.py)            [diagnostic only]
            -> body-sell ledger (bl_bodysell_*.py) -> G2 (solo trigger, solo strike, late, rest)
                 -> G3 (buy-backs, wings, lump inherit body-sell errors: re-measure after G2)
                      -> G4 (D-1 full validation)
  D0 research simulator (bl_bt3_sim.py::sim_d0, bl_d0_fr.py)  -> G5 needs a STANDALONE D0 engine (does not exist)
       G4 + G5 -> G6 (integrated, position handoff) -> G7 (independence review) -> G8 (freeze)
frozen late-sale rule / score / shadow (hashes in bl_fwd_freeze.py): unchanged; relevant to G2C only as an optional module
```
Hard dependencies: G3 depends on G2 (wing and buy-back errors are partly inherited); G5 depends on a D0 engine to be built; G6 on G4 and G5; G7 on all development data being identified.

## 7. Remaining-work register (Gate 0 view)

| # | Item | Gate | Feasible with existing data? |
|---|---|---|---|
| 1 | Solo trigger count, spacing, same-second multiples | 2A | yes (hypotheses preregistered below) |
| 2 | Solo strike reference | 2B | partly (decision-time premiums exist only for traded contracts) |
| 3 | 15:00+ block | 2C | partly |
| 4 | Breakout and scheduled strike differences, repeat entries, deep-OTM batches | 2D | yes / rare |
| 5 | Buy-back second half, wing strike reference, wing release choice, lump size and strike | 3 | partly |
| 6 | Re-measure wing and buy-back errors after body-sell fixes | 3 | yes |
| 7 | D-1 full replay report with preregistered quality standards | 4 | yes |
| 8 | Standalone D0 engine and D0 rules (solo, counter-sells, bursts, carried lots, clearance) | 5 | partly |
| 9 | Handoff and accounting | 6 | yes |
| 10 | Independence review (no new data: state outstanding) | 7 | yes (documentation) |
| 11 | Freeze, closure report | 8 | yes |
| 12 | Quality standards for Gate 4 must be preregistered **before** the validation run | 4 | yes |

## 8. Contradictions and corrections found at Gate 0

| # | Finding | Resolution |
|---|---|---|
| C1 | The brief's "latest adjusted pooled lot-level F1 approximately 0.472" | 0.472 is the **strict order-level F1** (strike and lots exact, 60 s) of B1; the legacy lot-level F1 is 0.6878 and has not changed |
| C2 | Audit section 6 test counts (31 / 210) | stale; current counts in section 3 |
| C3 | Audit 9.4 cites scoring spec v1.0 | v1.1 is frozen; v1.0 archived with hash (`spec_freeze.json`) |
| C4 | First-run report quotes keys F1 0.736; B1 gives 0.739 | different baselines (B0 `freeze_v1` vs B1 `one_lot_v2`); both kept |
| C5 | Register D1-05 says solo lots per decision are set by a tick tracker; D0-03 says D0 solo lots = steps crossed; the D-1 engine sells 1 lot per trigger and real same-second multiples exist | competing explanations for Gate 2A |
| C6 | "675 missed solo orders" | "solo" is the **inferred** module of the missed real orders (the log has no module label) |
| C7 | Register vocabulary differs from the Phase 1 taxonomy | mapping in `PHASE1_RULE_CLASSIFICATION.md` |
| C8 | Gate 5 needs a D0 engine; none exists (audit section 6) | listed as work item 8 |
| C9 | **Risk:** the 63 uncommitted files exist only in this session's container, which is ephemeral | flagged to you; I do not commit without your instruction |

## 9. Phase 1 experiments (new IDs)

| ID | Gate | Plan | Baseline | Outputs | Decision |
|---|---|---|---|---|---|
| P1-2A-0 | 2A | `PHASE1_GATE2A_PLAN.md` T1-T3 | B1 | `outputs/phase1/2A/T1_T3_analytic.json` | H1 contradicted (T2); H3 coverage supportive but see V02/V03 |
| P1-2A-V00 | 2A | same | B1 | `outputs/phase1/2A/V00` | identical to B1 (regression pass) |
| P1-2A-V01 | 2A | same | B1 | `.../V01` | near miss: F1 0.7699, strict 0.6149, precision 0.831, extras 639; **rejected** (fails A1, A3, A4) |
| P1-2A-V02..V08 | 2A | same | B1 | `.../V02..V08` | all rejected (H1, H2, H3 contradicted at order level) |
| P1-2B-0/1/2 | 2B | `PHASE1_GATE2B_PLAN.md` | B1 | `outputs/phase1/2B_*` | no strike rule supported (S1 0.501 exact vs best alternative 0.536); F strike loss mostly inherited context |

## 10. Session log

**2026-11-25 (session 1):** Gate 0 PASS; Gate 1 CONDITIONAL; Gate 2A run to its stop rule: FAIL (correction rejected). Latest experiment ID `P1-2A-V08`. Files added: `reports/PHASE1_GATE2A_*`, `src/bl_p1_*`, `d1_strategy/test_ladder_candidates.py`, `audit/PHASE1_*`, `audit/build_phase1_classification.py`, `src/phase1_baseline.py`, `tests/test_phase1_baseline.py`, `outputs/phase1/`. Next exact action: **Gate 2B**: preregister the solo strike-reference experiment (competing references; teacher-forced evaluation on real solo sells; then engine candidates under fixed criteria), then 2C (15:00+), 2D (breakout/scheduled strikes, repeats), then Gate 3.

## 11. Gate 2 report and Gate 3 starting point (added session 1, later)

| Field | Gate 2 |
|---|---|
| Gate | 2: D-1 body-sell reconstruction (2A solo trigger, 2B solo strike, 2C 15:00+, 2D breakout/pair sizing) |
| Status | **CONDITIONAL** |
| Baseline | B1 body sells: F1 0.7586, strict 0.5954, 1,179 missing, 873 extra |
| Latest result | no accepted change; best partial signals not adopted: V01 (F1 0.770, strict 0.615, extras 639) and C1 (F1 0.771, strict 0.611, legacy lot F1 0.699) |
| Criteria | not met (A1-A9, L1-L8 as registered; never relaxed) |
| Root causes | solo/breakout timing and count set by a tick path (data-limited); index frozen 15:15-15:29 in post-auction cycles (feed fidelity, identified); strike rule is about as good as bars allow (0.50 exact with real context) |
| Corrections | none accepted; default-off switches in the engine: `ladder_lots_mode`, `ladder_book_condition`, `ladder_late_gate_min`/`late_start_min`, `breakout_one_lot` |
| Regression | engine at defaults replays identically to B0/B1 (`tests/test_phase1_baseline.py`, `P1-2A-V00`, `P1-2C-C0`, `P1-2D-BK0`) |
| Evidence | `reports/PHASE1_GATE2*`, `outputs/phase1/{2A,2B_*,2C,2D}` |
| Remaining | open decisions in `phase1_gate_state.json` (adopt V01 / C1 as input conventions; combination untested) |

**Gate 3 starting evidence (from the existing TF-E tables; not a new experiment).** Share of F's missed real orders that TF-E-m (book and fill memory corrected) recovers: wing buys 255 of 536 (48%), wing sells 171 of 354 (48%), buy-backs 42 of 675 (6%), lump 9 of 53 (17%). So about half of the wing errors are inherited from upstream state and timing, and buy-back and lump errors are mostly separate rules. Planned preregistered experiments, one at a time, none started: (3a) buy-back stop basis and clearing after body fidelity is fixed; (3b) wing release choice (outermost vs cheapest) teacher-forced; (3c) lump size and strike teacher-forced; (3d) re-measure all four after any adopted upstream convention.

## 12. Session log (end of session 1)
Latest experiment `P1-2D-BK3`. Gates: 0 PASS, 1 CONDITIONAL, 2 CONDITIONAL, 3 IN PROGRESS, 4-8 not started. Tests: deep_dive and d1_strategy suites pass (see the last run in the session). Files added: `reports/PHASE1_GATE2{A,B,C,D}_{PLAN,RESULT}.md`, `PHASE1_GATE2_SUMMARY.md`, `src/bl_p1_*`, `tests/test_phase1_*`, `d1_strategy/test_ladder_candidates.py`, `outputs/phase1/`. Next exact action: Gate 3a (preregister the buy-back stop experiment).

## 13. Decisions recorded (2026-11-25, user)
| Item | Decision |
|---|---|
| V01 (book condition) | **Rejected; archived** as a research candidate; not the default |
| C1 (rebased futures from 15:15, post-auction cycles) | **Diagnostic input convention only** (sensitivity analysis). Not a confirmed trading rule; not a replacement for the baseline; it does not reconstruct the original late-session trigger (about 12-15% of real late sells reproduced) |
| B1 | Remains the **official frozen baseline** |
| Gate 2 | **CONDITIONAL closure accepted**; not relabelled PASS (investigation complete; solo-sell, strike and late-session mechanisms not reconstructed) |
| Next | **Gate 3a** buy-back stop experiment |
| Commits and pushes | **Not authorised** |
Conditions for Gate 3a (user): separate buy-back errors inherited from upstream body-sell timing from independent trigger errors; reconstruct the real position before each buy-back; test the stop mechanism against observed buy-backs; check missing **and** extra; measure timing, strike, quantity and portfolio-state agreement; do not compensate for missing body sells by changing buy-back rules; preserve B1 and compare every variant with it; **quantify the remaining mismatches after upstream position differences before any engine change**.

## 14. Session log (session 1, final)
Latest experiment `P1-G4`. Gates: 0 PASS; 1 CONDITIONAL; 2 CONDITIONAL; 3 CONDITIONAL; 4 CONDITIONAL; 5 IN PROGRESS (plan; D0 engine not built); 6, 8 not started; 7 interim note only. Decisions of 2026-11-25 recorded in section 13. New experiments (IDs in `phase1_gate_state.json`): P1-2A (9 runs), P1-2B (10 strike rules), P1-2C (3), P1-2D (4), P1-3A (step1, step2, 3 latency runs), P1-3B/3C (teacher-forced), P1-G4 (validation report). Engine switches added (all default off, tested, mutation-checked): `ladder_lots_mode`, `ladder_book_condition`, `ladder_late_gate_min`/`late_start_min`, `breakout_one_lot`, `stop_latency_s`. B0 and B1 intact (manifest check passes). **Next exact action: Gate 5a (D0 engine port).**


## 15. Gates 5-8 report (session 2, 2026-11-25)

| Field | Content |
|---|---|
| Gates | 5a-5d, 6, 7, 8 |
| Status | 5 CONDITIONAL; 6 PASS (integration); 7 CONDITIONAL; 8 DONE; **Phase 1 CONDITIONAL** |
| Baseline | B1 (frozen D-1) unchanged; D0 engine = Gate 5a port of the research simulator (49/49 identical); candidates accepted: X1 only; rejected: X3 |
| Latest result | D-1 B1 keys F1 0.739 / strict 0.472; D0-C mode T 0.4217 / strict 0.143 (LOCO 0.428); integrated mode F combined 0.498 (D-1 0.739, D0 0.397) |
| Corrections | 5b scoring-layer fix (stop parts aggregated per contract and kind; first run archived: OOF 0.4176 -> 0.4198, stop class F1 0.254 -> 0.163); 5c plan Addendum 1 (K1 evaluated on `one_lot` after the baseline showed events cap clearance recall; made before any variant ran) |
| Regression | 544 tests pass, 0 fail (`outputs/phase1/8/regression_results.json`); default D0 = reference 49/49; B0/B1 immutable |
| Evidence | `reports/PHASE1_GATE5*_*.md`, `PHASE1_GATE6_*`, `PHASE1_GATE7_*`, `audit/PHASE1_CLOSURE_REPORT.md`, `PHASE1_RULE_REGISTER_FINAL.md`, `PHASE1_UNRESOLVED_RULES.md`, `outputs/phase1/{5b,5c,5d,6,7,8}/` |
| Open decisions for the user | adopt X1 and `one_lot_v2` into production configs; authorise U1-U3; commit and push (not authorised) |
| Honest limits | all evidence is development-cycle historical reproduction; ~45 ideas tested in Phase 1; D-1 stop absent; wings carried as `h_`; frozen D0 parameters are an in-sample all-cycle fit |

## 16. Session log (session 2, final)
Built and verified: `d0_strategy/` (standalone D0 engine, 15 tests incl. mutation-checked switches X3 and a risk guard), `algo8_integrated/` (handoff and runner, 4 tests), Phase 1 scripts `src/bl_p1_5{a,b,c,d}*.py`, `bl_p1_6*.py`, `bl_p1_7*.py`, `bl_p1_8_freeze.py`, output regression tests `tests/test_phase1_gate{5b,5c,5d,6,7,8}*.py`. **Recoverability:** all of it exists only in this container's working tree (163 uncommitted entries (git status --short, directories counted once) at the end of the final loop); nothing is committed, pushed or backed up externally.


## 17. Phase 1 final loop (2026-11-25): four investigations, population reconciliation, final validation

| Field | Content |
|---|---|
| Scope | A premium-triggered ladder (H6); B D-1 session stop; C D0 clearance spread 15:14-15:34; D 15:30 candle-close bursts; D0 population reconciliation; final combined validation; freeze v2 |
| Status | all four investigations have a recorded outcome; **Phase 1 verdict CONDITIONAL (unchanged)**; Gate 1 now PASS; other gates unchanged |
| Baseline | B1 and Gate 5a reference unchanged (49/49); D-1 B1 keys F1 0.739; frozen D0 configurations now two (forward, historical-reproduction) |
| Latest results | A rejected (decision level); B cycle stop confirmed on real book, constant corrected 1.20 -> 1.25, D-1 engine stop rejected; C CH1/CH2 rejected (CH2 near-miss), X1 demoted to experimental; D plausible but unconfirmed; D0 OOF 0.420/0.422 (LOCO 0.427/0.428); integrated 0.497/0.498 |
| Corrections | stop constant (accepted); X1 no longer a default; population statement on every D0 metric; test fix `test_order_type_matches_log`; Phase A rule register regenerated with the loop updates |
| Regression | 566 passed, 0 failed (`outputs/phase1/9/regression_results_final.json`) |
| Evidence | `reports/PHASE1_LOOP2_{A,B,C,D}_PLAN.md`, `PHASE1_LOOP2_RESULT.md`, `outputs/phase1/9/`, `freeze_v2/`, `audit/PHASE1_CLOSURE_REPORT.md` (updated), `PHASE1_RULE_REGISTER_FINAL.md/csv`, `PHASE1_UNRESOLVED_RULES.md`, `ALGO8_PHASE_A_RULE_REGISTER.md/csv` |
| Independent validation | none exists |
| Open decisions for the user | adopt the one-lot convention and the 1.25 stop constant in production configs (already in the frozen forward configuration); whether CH2 is worth an independent test later; commit and push (not authorised) |
