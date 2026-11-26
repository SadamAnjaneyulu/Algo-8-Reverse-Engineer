# Phase 1, Gate 2C: the 15:00+ block. Result

*2026-11-25. Plan `PHASE1_GATE2C_PLAN.md` (with Addendum 1), written before the runs. Experiments `P1-2C-C0` (runner check), `C1`, `C2` (`outputs/phase1/2C/`). Existing data only; the frozen late-sale rule, score and hashes untouched. Evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 2C: late-session body sells (15:00 onwards; window = 15:15 onwards in the 21 post-auction cycles) |
| Status | **FAIL for both candidates; the 2C correction is rejected.** The finding about the data feed is kept as a documented, **not adopted** data-fidelity candidate. Gate 2C overall: **CONDITIONAL** (residual quantified) |
| Baseline | B1 window: 165 real late body sells, 241 simulated, recall 0.255, precision 0.166, F1 0.2009 (the 21 post-auction cycles) |
| Latest result | C1 (rebased futures series from 15:15): window sim 43, recall 0.115, precision **0.395**, F1 0.1784; overall body F1 **0.7712** (+0.0126), strict **0.6105** (+0.0151), legacy lot-level F1 **0.6994** (+0.0116). C2 (C1 + 5-minute late gate): window sim 61, recall 0.152, precision 0.393, F1 0.2188; overall body F1 0.7703, strict 0.6080, legacy 0.6990 |
| Criteria | L1 (window F1 >= 0.2509): C1 fail, C2 fail. L2 (recall >= 0.305, precision >= 0.146): both fail on recall. L3 (overall not worse): both PASS. L4 (pre-auction identical): C1 PASS; **C2 fail, a defect of my plan** (the late-gate override applies to pre-auction cycles too; C2 fails L1, L2, L7 regardless). L5 (scheduled): both PASS. L6 (classes, book L1, legacy): both PASS. L7 (window F1 better in >= 12 of 21 cycles): C1 4, C2 8, both fail. L8 (no look-ahead): rebased series equals the index series before minute 360 (asserted in the runner and tested) |
| Root causes | (1) **the index is frozen from 15:15 to 15:29 in post-auction cycles**, so the baseline ladder fired on a frozen price; (2) even on a moving (futures) price, the engine's rules reproduce only 11-15% of the real late body sells |
| Corrections | none accepted. `ladder_late_gate_min` / `late_start_min` exist (default off, tested) |
| Regression | none: pre-auction cycles replay identically in C1; scheduled straddles unchanged |
| Evidence | `outputs/phase1/2C/{C0,C1,C2,evaluation.json}`, `src/bl_p1_2c_*.py`, `d1_strategy/test_ladder_candidates.py` |
| Next action | Gate 2D |

## What the runs show (Observed)
* **The baseline's apparent late recall (0.255) was largely chance.** With the frozen index the engine emitted 241 late body sells for 165 real ones; with the moving futures series it emits **43**, of which 17 are right (precision 0.395 against 0.166). The 198 removed orders were mostly spurious, which is why overall precision, strict F1 and the legacy lot-level F1 all rise (+0.0116) as a by-product.
* **The real late sells are not reproduced by the engine's rules on the right price series.** Recall 0.115 (C1) and 0.152 (C2, the frozen 5-minute gate): about 140 of 165 real late body sells in the post-auction cycles remain unexplained. A shorter gate adds a little recall at no precision cost (0.395 to 0.393) but is far from the preregistered +0.05.
* The side and the closing-pair bursts (G1b candidate) are not in this test and stay candidates.

## Classification and open decision
Late-session body sells: **Partial for side and price series (feed fidelity identified); Unresolved for timing and trigger (about 85-88% of real late body sells unexplained)**; G1b stays a Candidate excluded from the baseline. **Open data-fidelity question (recorded for Gate 8, not a gate-blocking decision):** whether the rebased-futures series should become the engine's price input from 15:15 in post-auction cycles. It is an input convention, not a rule; it improves every overall measure and removes spurious fires, but it fails the preregistered late-window criteria, so it is **not adopted** here.

## Limits
Same development cycles; the basis median over 15:00-15:14 is the earlier work's choice; option bars after 15:29 clamp to the last bar; the rebased futures are a proxy for what the real system saw; two variants counted; plan defect noted (L4 vs C2).

## Addendum (Phase 1 final loop, 2026-11-25): G1b timestamp audit
7 of 8 closing bursts start before the 15:00-15:30 candle is complete, so the G1b condition (close of minute 374) is not causal for them. Causal analogue (close of minute 369): 6/8, p = 0.0089, precision 0.60 (passes the preregistered rule); fails at minute 373. Class: plausible but unconfirmed; excluded from the baseline; no engine change. `PHASE1_LOOP2_RESULT.md` section 4.
