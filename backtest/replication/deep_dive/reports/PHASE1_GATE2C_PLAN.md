# Phase 1, Gate 2C: the 15:00+ block. Preregistration

*Written 2026-11-25 **before** any Gate 2C run. Experiments `P1-2C-*`. Baseline B1. Existing data only. Evidence: historical reproduction on the 32 development cycles. The frozen late-sale rule, score and hashes are **not touched** (this gate uses neither the frozen score nor its shadow module; it tests whether the engine's own rules explain the late window once the engine reads the right price series). Nothing committed.*

## 1. Problem
From 15:00 the body sells are the weakest block: 321 of the 1,179 missing real body sells (27%) and 137 of the 873 extra simulated ones (M4 153, M1 106, M3 48, M2 14). 30-minute block F1: 15:00 block 0.37, 15:30 block 0.18.

## 2. Evidence already in the repository (not re-run)
* `D1_CLOSING_TIME.md`: from the closing-auction era (D-1 sessions from 3 Aug 2026) the **index is frozen or indicative from 15:15 to 15:29**; the near-month future trades to 15:40. `bl_bt3u_data.py` already builds a rebased series for those sessions (futures OHLC minus the median basis to the index over 15:00-15:14; "no fitted parameter"), saved in `outputs/bt3u/`.
* **New fact established here:** the F replay reads the **index** series. In post-auction cycles the index close is constant from minute 360 (checked: 24,573.4 for minutes 361-364 in NIFTY 4 Aug), while the rebased futures series moves (24,575.6, 24,580.4, 24,579.7 ...). So **the engine's ladder cannot see any price move in the 15:15-15:29 window of 21 of the 32 cycles**, whatever its rule. 11 cycles are pre-auction and unaffected.
* The late-sale work (E07-E09) found the late sells follow the **future**, and chose a gate of 5 minutes in 17 of 18 leave-one-cycle-out folds (frozen constant, not re-fitted here). The side is "the option that just became cheaper" (78%/85%).

## 3. Competing hypotheses
| ID | Hypothesis | Test |
|---|---|---|
| L1 | **Feed fidelity:** the late misses are partly caused by the engine reading a frozen index; with the rebased-futures series from minute 360 in post-auction cycles, the unchanged ladder (gate 60, step 0.2) reproduces more of them | experiment C1 (feed only; no parameter, no rule change) |
| L2 | **Regime gate:** from 15:15 the ladder's fresh-extreme window is the frozen 5 minutes (E09), not 60 | experiment C2 (C1 plus `ladder_late_gate_min = 5` from minute 360; the constant is the frozen one) |
| L3 | The closing pair bursts follow the 15:30 candle-end close (G1b candidate) | **not implemented**: stays a candidate excluded from the baseline; reported only as a remaining residual |
| L4 | No mechanism recoverable from these data (decision times, hidden input) | the residual after C1/C2 |
C2 is run once, after C1, and only on top of C1's feed (a gate change on a frozen price series is meaningless). Both runs are counted (selection risk: 2 variants).

## 4. Implementation (default off)
* Engine: `ladder_late_gate_min` (default `None` = baseline) and `late_start_min` (default 360); in `_ladder` the gate window is `ladder_late_gate_min` once `j >= late_start_min`. Tests: defaults replay identically to B1/B0; the late gate switches exactly at the start minute.
* Replay: for post-auction cycles (D-1 >= 2026-08-03; 21 of 32) the spot series is the `bt3u` series; option bars are padded to the longer series with the last bar (option bars end at 15:29; later prices clamp, as the replay already does). Pre-auction cycles are untouched (must replay **identically** to B1).
* The basis is the median over 15:00-15:14 (minutes 345-359), so the series from minute 360 uses no later data (test).

## 5. Acceptance criteria (fixed now)
Late window = orders from 15:15 (minute >= 360) in the 21 post-auction cycles. B1 window values are computed by the evaluator before the candidate runs and recorded in the result.
| # | Criterion |
|---|---|
| L1 | window body-sell F1 (keys, 60 s) >= B1 + 0.05 |
| L2 | window recall >= B1 + 0.05 **and** precision >= B1 - 0.02 |
| L3 | overall body-sell F1 >= B1 0.7586 - 0.005 and strict F1 >= 0.5954 - 0.005 (no damage elsewhere) |
| L4 | the 11 pre-auction cycles replay **identically** to B1 (orders equal) |
| L5 | scheduled straddles: matched >= 2,076 and exact-second share >= 0.659 |
| L6 | every other class F1 >= B1 - 0.02; median book L1 <= 0.508 + 0.02; legacy lot-level F1 >= 0.6878 - 0.005 |
| L7 | window F1 improves in >= 12 of the 21 post-auction cycles |
| L8 | no look-ahead: the rebased series equals the index series before minute 360 and its basis uses minutes <= 359 only (test) |
A variant failing any criterion is rejected and archived; criteria are not relaxed.

## 6. Stop rule
If neither C1 nor C2 passes, the 15:00+ residual is classified (feed fidelity tested; regime gate tested; G1b candidate untested) as **Partial / Unresolved**, with the quantified remaining misses, and Gate 2C is CONDITIONAL. If C1 passes, it is frozen as a candidate correction and then C2 is judged on its own criteria.

## 7. Limits stated in advance
Same development cycles; the basis is a median over 15 minutes (the earlier work's choice); option bars after 15:29 are clamped; module labels of real orders are inferred; the rebased futures are a proxy for what the real system saw.

## Addendum 1 (before C1/C2 ran): B1 window baseline
`P1-2C-C0` (the runner with no change) reproduces B1 exactly (9,035 identical orders). **B1 late window (orders from 15:15 in the 21 post-auction cycles):** real body sells 165, simulated 241, recall 0.255, precision 0.166, **F1 0.2009**. Thresholds from section 5 therefore read: L1 window F1 >= 0.2509; L2 recall >= 0.305 and precision >= 0.146.
