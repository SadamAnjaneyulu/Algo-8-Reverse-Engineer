# Independent statistical validation and overfitting audit of the Algo 8 forward-test framework

*2026-11-24. Auditor stance: adversarial; a negative finding is preferred to an impressive but unreliable one. The frozen rule, its parameters, features, reference and execution logic, the frozen score, the hashes and the original pre-registration (`FORWARD_TEST.md`) were **not changed** (verified, section 8). Everything below concerns the validation method, the statistics and the tests.*
*Scripts: `src/bl_audit_pbo.py`, `bl_audit_stats.py`, `bl_audit_selection.py`, `bl_audit_power.py`, `bl_audit_power2.py`, `bl_audit_ledger.py`, `bl_validation.py`, `bl_fwd_eval_v2.py` → `outputs/audit/`. Companions: `EXPERIMENT_LEDGER.md`, `POWER_ANALYSIS.md`, `VALIDATION_PROTOCOL_AMENDMENT.md`, `AUDIT_CHANGELOG.md`; machine-readable `validation_config.json`.*

## Result first
| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | The primary features use the order's **own minute**, so they contain prices after the order. The same frozen score built from information strictly **before** the minute shows **no gain** (ΔAUC −0.028 [−0.068, +0.014]). For orders in the first 20 s of a minute: +0.189 with the whole minute, −0.004 with the previous minutes. The endpoint measures a **contemporaneous association, not a prediction**. | **High** | **Remains.** Endpoint not changed. Disclosure plus a causal secondary endpoint proposed (A6). |
| F2 | In regime B the clock baseline is estimated from 10 burn-in cycles, so features that merely correlate with minute-of-window can **beat a noisy baseline**: false-positive rate **21% at 30 cycles, 37% at 60** where features add nothing beyond the true clock (valid under *no information at all*: 0.4%). | **High** | **Remains** until the amendment is adopted. Cross-fitted baseline cuts it to 3–4% (A3). v2 reports both. |
| F3 | **No independent data exist.** The rule and score come from **126 distinct variants / 315 saved tests** on the same 18 cycles, plus an engine skeleton fitted on 32 cycles that contain them. | **High** | **Remains by construction.** Only the forward sample can fix it. |
| F4 | The v1 harness used a **95% interval at every look**; the protocol's stopping rule needs the Pocock level (97.06%). One-sided error 2.8–3.9% against 1.8–2.5%. | Medium | **Fixed** in v2. |
| F5 | v1 had **no cycle roles**: burn-in cycles in the log directory would enter the confirmatory test; the primary endpoint could be computed at any time (peeking). | Medium | **Fixed** in v2 (roles, no-peeking guard). |
| F6 | The pre-registration gives **no burn-in data-quality criteria** and states both "95% bootstrap" and "Pocock 97.06%". | Medium | **Amendment proposed** (A1, A4). Original untouched. |
| F7 | The original power numbers reproduce but describe a different design (single look, exact clock); they hide F2 and mis-state the K=2 power (42% vs 69–75% at half effect). | Medium | **Corrected** in `POWER_ANALYSIS.md`. |
| F8 | v1 dropped rows with missing bars silently and did not de-duplicate orders. | Low | **Fixed** in v2 (counted, de-duplicated). |
| F9 | The development estimate is leave-one-cycle-out, not chronological. The chronological walk-forward gives +0.151 on 10 test cycles, with a weaker baseline (0.663). | Low | Documented; not evidence of a larger effect. |
| F10 | The "0.60 overfitting probability" belongs to the **simulator-tuning** gate and is **uninformative**: pure noise of the same shape gives 0.53 [0.29, 0.88]. | Info | Explained (section 1). |
| F11 | Selection among the 3 underlyings and the nested feature choice does **not** explain the effect: best-of-3 under a margin-preserving null averages +0.009; observed +0.088, p = 0.003. | Info (favourable) | Measured (section 2). |

## 1. What the ≈0.60 is
* **Source:** gate G4 of the pre-paper battery (`PREPAPER_RESULT.md`): CSCV over **41 candidate columns** (the frozen simulator plus 36 ±20/40% parameter perturbations and 4 timing shifts) on **158 weeks**, 16 blocks, 12,870 splits. It asks whether **tuning the simulator** has out-of-sample value. It says nothing about the late-sale score.
* **Reproduced independently:** 0.602.
* **Why it is high:** the 41 columns are near copies (**mean pairwise correlation 0.97**; Sharpe spread across columns 0.22–0.32, standard deviation 0.018). Differences between them are mostly noise, so the in-sample winner is close to a random draw. **The winner was never the frozen configuration** (0 of 12,870 splits); one variant (`d1_stop_ratio −40%`) won 49% of them.
* **How to read it:** a matrix of the same shape with **no true differences** gives a mean PBO of **0.53** (5–95%: 0.29–0.88). The observed 0.60 sits at the **60th percentile of pure noise**. It is neither evidence of overfitting nor evidence against it; its sampling distribution is simply too wide. The sound conclusion is the one drawn then: **fine-tuning showed no demonstrable out-of-sample value**.
* **What it is not:** it is not an overfitting probability for the frozen late rule. No PBO exists for the late rule; sections 2–3 measure its selection bias directly.

## 2. Historical selection-bias assessment (late-sale rule)
**What was searched** (`EXPERIMENT_LEDGER.md`): **126 distinct variants** and **315 saved test numbers** in the lineage of the frozen rule, all on the **same 18 post-auction cycles** (plus 11 pre-auction cycles for the era comparison). The final three-feature score was chosen **after** seeing them (FUT from the underlying comparison, then `ext5` and `mv1`, then gate 5). The engine skeleton the rule extends was fitted on 32 observed cycles that include these 18. **The true number of looks is higher** (unrecoverable: fitting iterations of the engine; interactive exploration; 435 scripts with no hypothesis count).

**Decomposition of the reported +0.098** (stratified ΔAUC over the clock; 18 cycles; effective independent cycles 14.8; 48 events and 852 negatives):
| estimate | ΔAUC [95% cluster bootstrap] | what it tells |
|---|---|---|
| **Reported:** leave-one-cycle-out, 3 features pre-chosen on all cycles | **+0.098 [+0.023, +0.172]** | reproduced exactly |
| Nested: feature families chosen inside each fold | +0.088 [+0.015, +0.158] | the pre-chosen features leak about **+0.010** |
| Frozen coefficients (fitted on all 18) with leave-own-out clock | +0.117 [+0.069, +0.177] | coefficient fit on the same cycles adds about **+0.019** |
| Chronological walk-forward (8 warm-up, 10 test cycles) | +0.151 [+0.086, +0.241] | baseline is weaker (0.663 vs 0.711): **noise, not a larger effect** |
| **Features strictly before the order's minute** | **−0.028 [−0.068, +0.014]** | **no gain** (F1) |
| Frozen score vs the table that contains its own events | +0.027 [−0.007, +0.065] | baseline inflated to 0.864: diagnostic only |

**Selection among the 3 underlyings × 9 directional features × nested choice** (the reported pipeline re-run on permuted labels; the re-implementation reproduces the reported FEED −0.023, FUT +0.088, OPT −0.043 exactly; 300 permutations):
| null | mean of best-of-3 | 95th / 99th percentile | observed +0.088 |
|---|---|---|---|
| **Curveball swaps** (keeps every cycle's event count **and** every minute's frequency): the right null for "does the score add to the clock" | **+0.009** | 0.039 / 0.050 | **p = 0.0033** (0 of 300 reached it) |
| Cross-cycle permutation within each (minute, side) cell | +0.009 | 0.034 / 0.049 | p = 0.0033 |
| Within-block permutation (destroys the clock; **wrong null**, shown for contrast) | +0.050 | 0.208 / 0.329 | p = 0.30 |

* **Bias from choosing among the options we tried at the last stage: about +0.009.** The best-of-3 effect is **not** a selection artefact.
* **This covers only the last stage.** Earlier choices (window, gate, features entering the family) are not captured, so the true bias is larger by an unknown amount.

**Is +0.098 an unbiased estimate? No.** It carries about **+0.03** of measurable optimism (+0.019 coefficient fit, +0.010 feature choice, +0.009 final-stage selection; partly overlapping), plus unmeasured earlier selection. It is also a **contemporaneous** association (F1).

**Were the 18 cycles used for both selection and power?** Yes. The original power analysis took the effect **and** its variance from them, with the coefficients fitted on them.

**Do baseline and score use identical observations and labels?** Yes, in every analysis checked: one table, one set of rows, one denominator (`bl_validation.components`, tested). The only asymmetry is the clock's *source*: leave-own-cycle-out in development against a frozen table in the forward test.

**Credibility of +0.098.** Credible as the sign and rough size of a **contemporaneous association** in these cycles: removing any single cycle never makes the reported estimate non-positive (leave-one-cycle-out range +0.086 to +0.126); in the frozen-coefficient version 15 of 17 cycles with events contribute positively and the single largest cycle holds 12% of the numerator. **Not credible** as an estimate of predictive gain (F1) or as the effect to plan a forward test around without shrinking: a planning value of **+0.05 to +0.06** is closer to the evidence.

## 3. Leakage and sample-construction audit
| Check | Finding | Status |
|---|---|---|
| Features available before the order timestamp | **No.** `ext5` and `mv1` use the whole order minute (high, low, close). For orders in the first 20 s that is more than 40 s of future price. | F1: remains |
| Current-minute highs/lows include post-order information | **Yes**, by construction. Not a label-to-feature leak (a 1-lot sale cannot move the future), but it makes the endpoint contemporaneous. Order-second profile (against the frozen in-sample table, so levels are conservative): Δ +0.073 for orders in the first 20 s, −0.047 and −0.009 for orders in seconds 20–39 and 40–59 (9 and 14 positives: no detectable effect). Against the leave-own-out clock, the first-20-second orders give +0.189 with the whole minute and −0.004 with strictly-before features. | F1 |
| Orders carry a fill time, not a placement time | Labels use `t_last` (last fill), up to seconds after placement; boundary noise around minute edges. | Limitation |
| Future bars or future portfolio states in features | **None found** in the frozen features, tested by perturbing later bars (`test_features_use_no_future_bars`). `imb` and `prem_ratio` use only prior orders. | Clean |
| Same real order counted twice | Event labels are binary per (minute, side), so duplicates do not inflate events; **order-level** counts could (v1). | Fixed (v2 de-duplicates) |
| CE+PE pairs | Treated as two events (one per side block), clustered at cycle level; pair bursts are reported separately (6 events in development). | Clean |
| Quiet minutes as negatives | Development table is complete (900 = 18 × 2 × 25). Forward: one row per window minute and side **with or without an order**. | Clean |
| Missing bars / missing logs | v1 dropped rows silently (denominator and positives lost). v2 counts missing rows and **positives lost**, per cycle. | Fixed |
| Duplicate timestamps / overlapping events | Handled by the de-duplication key; same-minute orders collapse into one event. | Clean |
| Burn-in in the confirmatory test | v1: possible. v2: roles from D-1 date; primary on confirmatory cycles only; not computed before the look. | Fixed |
| Cycles kept intact, chronological split | v2 asserts roles are chronological and disjoint; development ends before the freeze date. The development analysis used **leave-one-cycle-out**, which trains on later cycles (F9). | Fixed for forward |

## 4. Statistical-methodology audit
* **The endpoint is computed correctly.** The v2 components equal the v1 numbers to machine precision; a one-block case with ties and a pooled multi-block case match `sklearn.roc_auc_score` (tested).
* **Cycle-level uncertainty.** The bootstrap resamples whole cycles; the effective number of cycles is 14.8 of 18 in development and about 23 of 30 in simulation. Minutes and orders are never treated as independent.
* **Calibration of the interval.** Size at a true Δ = 0 with an exact clock: **linearised 1.4–1.8%, percentile bootstrap 2.0–3.7%** (nominal one-sided 2.5%). The bootstrap is slightly anti-conservative at small N and K=3 (up to 7% with a cross-fitted clock); the linearised interval is conservative.
* **Pocock design.** Constants computed independently by numerical integration: K=2 → 2.178 (nominal **0.0294**), K=3 → 2.289 (**0.0221**); a Monte-Carlo check gives overall two-sided error 5.0% for K=2. **The design is valid as specified for an exact clock**, with these conditions: (1) the interval at each look must be at the Pocock level, which v1 did not do (F4, fixed in v2); (2) the futility rule (look 1, point estimate ≤ 0) is non-binding and only lowers error; (3) burn-in is not a look (enforced in v2); (4) Pocock presumes information proportional to cycles, which holds approximately here.
* **Not valid in regime B as specified** because of F2: with a burn-in-only clock the error is 31% for the K=2 design where features offset clock noise.
* **Peeking.** The pre-registration forbids unscheduled looks but nothing prevented them. v2 refuses to compute the primary endpoint before the cycle count for the look is reached.
* **Results by regime.** Development cycles are regime A only; the frozen (futures-based) score is not defined for pre-auction cycles. **No regime-B data exist.** Per-regime reporting is built into v2.

## 5. Power analysis: summary of the correction
Full tables in `POWER_ANALYSIS.md`.
* 94% at +0.098 and 42% at half **reproduce** for a single analysis at 30 cycles with an exact clock (91–93%, 42–49%).
* The pre-registered K=2 design has **69–75%** power at +0.050, **95%** at +0.075 and only **18–24%** at +0.025.
* **Cycles for 80 / 90 / 95% (one analysis):** +0.098 → 24 / 29 / 37; +0.075 → 35 / 47 / 56; +0.050 → 68 / 92 / 117; +0.025 → 253 / 330 / 414.
* **Assurance under skeptical priors: 26–50%**, not 94%. Power conditional on an effect does not fix selection bias, and nothing in this audit pretends it does.
* **30 cycles is not enough for any effect below about +0.075**, and the second look (60) is needed to reach 70% at +0.05.

## 6. What was fixed and what remains
**Fixed (validation infrastructure only):** the interval level at each look (F4); cycle roles and burn-in exclusion (F5); no-peeking guard (F5); order de-duplication and missing-data accounting (F8); frozen-hash verification before any evaluation; a machine-readable configuration; 19 audit tests with 5 injected bugs all caught.

**Remains:**
* **F1** (contemporaneous endpoint): the frozen endpoint is kept, as required. It can only be disclosed, mitigated by a secondary causal endpoint (A6) and addressed by a **separate future experiment**: a tick-resolution trigger test on the recorder's pre-order prices. That would be a change of the rule's input and is **not implemented**.
* **F2** until the amendment is adopted.
* **F3** permanently, for the development data.

## 7. Remaining limitations
* The null for selection covers only the last selection stage.
* Simulation assumes the frozen model describes the truth up to a scalar and regime-B event rate and clock shape equal to regime A.
* 18 development cycles, 17 with events, 48 events.
* Burn-in data-quality thresholds in the configuration are proposals; nothing has been recorded yet.
* Labels depend on fill timestamps.
* The audit saw no forward data and the recorder has not run.

## 8. Frozen objects: verified unchanged
* `LateRuleConfig().sha256` = `ca1306cf…8e03`; frozen score sha256 = `7788f739…d69c`: both unchanged.
* SHA-256 of `shadow.py`, `frozen_model.json`, `bl_fwd_freeze.py`, `FORWARD_TEST.md` and the registration plan file identical before and after (`outputs/audit/fingerprints_before.txt`, `fingerprints_after.txt`; also asserted in `test_frozen_hashes_verified_and_tampering_detected`).
* The development dry run reproduces its earlier output **byte for byte**; the live-form rule is still identical to the batch ladder on all 18 cycles (precision 0.4615, recall 0.4583).
* The v1 harness (`bl_fwd_eval.py`) and v1 power script (`bl_fwd_power.py`) are untouched; v2 sits beside them.
