# Order-level scoring specification (version 1.1)

*Written 2026-11-25 for Phase A, step 2 of the closure standard (audit section 9). **Written and frozen before the simulator is built and before any order-level scoring is run.** Version 1.0 (hash `4abd0d22...`, archived as `outputs/scoring/ORDER_LEVEL_SCORING_SPEC_v1.0.md`) was amended to 1.1 on the user's review (amendment log at the end); the 1.1 hash is in `outputs/scoring/spec_freeze.json`. Status: **frozen**; it binds from the first scoring run on real data. After that run, any change is a dated amendment under section 10.*

## 0. Purpose and what this is not
Measure **how faithfully a reconstruction reproduces the original system's orders**, one order at a time and state by state. It is **not** a measure of strategy profitability or deployment readiness, and **not** a tuning target for P&L.

## 1. Principles (binding)
1. **Decisions first.** The score is about which orders were sent: when, on what, which side, which strike, how many lots, of which type. P&L is a separate diagnostic computed afterwards (section 9) and **never** enters an objective, gate or selection.
2. **One fixed matching procedure** (section 4). A real order matches at most one simulated order and vice versa.
3. **Report the distribution, not only the aggregate.** Every headline number comes with its per-cycle distribution (section 7). Aggregate F1 alone is not an acceptable report.
4. **D-1, D0 and end-to-end are reported separately** (section 7).
5. **Labelled evidence.** Every result carries one of three labels: *historical reproduction* (parameters fitted on the scored cycles), *out-of-fold* (parameters fitted on other cycles), *independent* (cycles or logs not used in any design or fitting step; **empty until new real data exist**).
6. **No retrospective adjustment.** Tolerances, tiers, thresholds and metric definitions are not changed after seeing results; a rule's threshold is never moved to capture a missed case.
7. **Decision timing is not execution timing.** The log holds fill timestamps, not decision timestamps. Agreement at the exact second is therefore **never a universal pass/fail criterion** and never a closure gate: a rule triggered by a completed one-minute candle cannot be expected to reproduce the original fill second.

## 2. Data contract
### 2.1 Real side (the export `Trades_GKOHNP140.csv`, via `bl_d0x_diag.real_orders()`)
Unit = **order** (one row per order tag). Fields used: cycle (underlying, expiry), day (`dayno` 0 = D-1, 1 = D0), module (`num` body, `h_` wing, `v_` lump, `s_` stop, `m_` manual), role, option type (`cp`), side, strike, filled lots (`lots`; requested `lim_lots` is reported, not matched on), validity (DAY / IOC), limit price (`lim_px`), **time = first-fill second (`t_first`, integer second of day)**, export row (`row`, tie-break only).
**Stated limits:** (a) the export has no decision time (`t_dec` empty) and no acknowledgements, so the first-fill second is the **only** time; it equals the placement time to within about one second (all sells are marketable limits that fill within about a second); (b) partial fills (2.7% of orders) are one order with its first-fill time and total filled lots; (c) orders in the same second are ordered by export row, **which is not known to be the true execution sequence** (section 4, ambiguity); (d) 18.1% of orders are multi-lot (hedge, lump, stop orders; freeze-quantity splits); (e) there are **no market orders** in the export: every order is a limit order.
### 2.2 Simulated side (contract the simulator must satisfy)
One record per order: cycle, day, **t (seconds of day, float; the simulated second is floor(t))**, `t_resolution` (`second` if the rule fixes the second, e.g. a timetable; `minute` if it fires on a bar), underlying, expiry, option type, side, strike, lots, validity, module class, limit price, role (class label), and the **book after the order** (positions by contract). **If the simulator cannot supply validity, order-type scoring is reported as "not available" for that run; it is never assumed.** The current engine's `orders_frame()` lacks validity; adding it is a prerequisite for order-type scoring.
### 2.3 Classes (reporting only, never matching keys)
Body sell (scheduled pair / reactive pair / solo / other), body buy-back, wing buy, wing sell, opening wings, overnight lump, stop module, not modelled. Real classes come from `role` and the existing class rules (`bl_fr_score.py`); simulated classes from the engine role.

## 3. Scope
Development cycles: D-1 of the 32 cycles with a D-1 log; D0 of the 30 cycles with both logs. **All cycles are scored and reported, including NIFTY 16 Oct and the stop-out cycles; reports also give the results without the outlier cycle and with stop cycles separated.**

## 4. Matching procedure (frozen)
Keys that must be equal: **cycle, day, option type, side** (underlying and expiry are part of the cycle). Strike, lots and order type are **scored on matched pairs, not used to find them**.
**Mutually exclusive tiers** (by |Δt| in whole seconds, simulated second = floor(t)):
| Tier | Definition | Interpretation |
|---|---|---|
| **Exact** | Δ = 0 s (same second) | strong timestamp agreement |
| **Near** | 0 < |Δ| <= 5 s | close execution agreement |
| **Broad** | 5 < |Δ| <= 60 s | one-minute agreement |
| **Unmatched** | no valid pair within 60 s | **missing** (real) or **extra** (simulated) |
**Cumulative agreement** at 0, 5 and 60 s is reported **in addition** (Exact; Exact + Near; Exact + Near + Broad).
**Algorithm:** within each group of equal keys, tier by tier (Exact, then Near, then Broad), among the still-unmatched real and simulated orders solve a **minimum-cost one-to-one assignment** (`scipy.optimize.linear_sum_assignment`) restricted to pairs whose |Δ| lies in that tier, with cost = |Δ| + 0.001 x |Δstrike in steps| + 0.000001 x |Δlots|, so time dominates, strike distance breaks time ties and lots breaks the rest; remaining ties break by (t, export row / simulation sequence). Each order is used **at most once** (asserted by the scorer).
**Same-second ambiguity (safeguard).** Export row order is kept only as a deterministic tie-break and **is not read as execution sequence**. A group is flagged **ambiguous** if, within (cycle, day, option type, side, second), there are two or more real or two or more simulated orders whose (strike, lots) differ, or if the optimum assignment is not unique. The scorer reports the **share of orders in ambiguous groups**, and computes every strike, lot and full-match metric under **both** tie-break directions (ascending and descending row / sequence), reporting the **range**. A metric whose range exceeds 0.01 is reported with that range and is not interpreted to its last digit.
**Outputs of matching:** per pair the tier, Δt (signed), Δstrike (steps, signed), Δlots (signed), type agreement, ambiguity flag; per order its status (matched / missing / extra).
**Granularity-neutral secondary view:** orders in the same second, same cycle, day, option type, side are summed to a **burst** and burst lots are compared. Reported separately from the order-level view.
**Legacy bridge:** the legacy lot-level F1 (+/-1 minute, same right and class, the original matching code) is recomputed on the same runs. **It must reproduce the published figures before any new metric is reported (section 11).**

## 5. Metrics (all at order level; lot-weighted versions alongside)
| Dimension | Metric |
|---|---|
| Timestamp | exclusive tier shares (Exact, Near, Broad, Unmatched) and cumulative shares at 0, 5, 60 s; matched signed Δt distribution (median, IQR, bias); same-**minute** agreement (floor(t/60) equal) as the decision-timing proxy; everything broken out by simulated `t_resolution` and by rule family. **The exact-second share is descriptive only (principle 7).** |
| Instrument and side | key-level agreement: share of real orders with any simulated order of the same cycle and day within 60 s **regardless of option type and side**, versus the same share with the keys required |
| Strike | exact share among matched; distribution of |Δ steps|; share within +/-1 step |
| Quantity | exact lot match share; absolute lot-count error (mean, median, p90); signed bias; lot-weighted error; burst-level lot error |
| Order type | agreement on (validity, module class) among matched, where supplied; limit-price offset class as a diagnostic |
| Joint | **full match** = matched **and** strike exact **and** lots exact **and** type agrees; reported per tier and cumulatively |
| Unmatched | **missing** and **extra** counts and lots, separately, by class, 30-minute block and cycle; precision = matched / simulated, recall = matched / real, F1, at each cumulative tolerance and each strictness level (keys only; + strike within one step; + strike exact; + lots exact; + type) |
| Time-shift placebo | the same metrics with the simulated times shifted by +15 minutes (same orders). **This is a time-shift placebo, not a universal random-chance baseline:** it can preserve or disrupt timetable patterns (a fixed 15-minute grid maps onto itself), so it is read as a reference for time-specific agreement only |

## 6. Portfolio state and modes
**After each matched event**, compare the real and simulated books **immediately after** that event: real book = cumulative real orders up to and including the matched real order in (t, row) order; simulated book = cumulative simulated orders up to and including the matched simulated order. Per option type: short lots S and long lots L (signed and absolute difference); share of matched events with both S and L equal; per-contract L1 distance sum |pos_real - pos_sim| divided by gross real lots. **Checkpoints** every 15 minutes and at the end of the day (carried book compared contract by contract, as in `D1_FREE_RUN`). State metrics inside ambiguous groups are flagged.
**Three modes, all reported for D-1:**
| Mode | Definition | Status |
|---|---|---|
| **F** free-running | the simulator maintains its own book throughout the session (D0: starting from the **simulated** carried book) | **primary**: the test of whether the complete strategy reproduces itself |
| **T** teacher-forced start | initialise from the real starting book, then run independently (D0: the **real** carried book; **D-1: the real starting book is flat, so T is identical to F for D-1 and is reported once with that note**) | secondary |
| **TF-E** per-event teacher-forced | reset or reconcile the simulated book to the real book after every real order, then evaluate the simulated decisions up to the next real order, so mismatches are isolated to the decision rule rather than to accumulated state divergence | **required for D-1 as a diagnostic; optional for D0. It is never a primary reconstruction score, never a closure gate, and never evidence that the complete strategy is reproduced**, because it receives information from the real system throughout the session and is inherently an easier test |
End-to-end = F for D-1 then D0.

## 7. Aggregation and required report tables
For D-1, D0 and end-to-end **separately**: (1) pooled (micro) metrics with cycle-cluster bootstrap 95% intervals (4,000 draws); (2) the **per-cycle distribution** of F1, precision, recall, lot-count error and state error: median, IQR, 10th percentile, minimum, maximum, the **five worst cycles named**, the number of cycles with F1 < 0.5 and < 0.3, and the macro average; (3) by class; (4) by underlying, version (V1 before 16 Sep 2026, V2 after) and era (before / after the closing auction of 3 Aug 2026); (5) by 30-minute block; (6) the missing / extra tables; (7) the ambiguity share and tie-break ranges. A report that gives only pooled F1 is incomplete under this specification. **F, T and TF-E results are always shown side by side and labelled; TF-E is never combined with or substituted for F.**

## 8. Run record and leakage control
Every scoring run records: spec version and hash, scorer and simulator code hashes, configuration hash, data (cache) hash, mode (F / T / TF-E), cycle set, tie-break direction(s), and the **evidence label** (historical reproduction / out-of-fold / independent). Parameters may be fitted **only** on order-level decisions of training cycles (never on P&L); out-of-fold means by cycle halves (parity). The simulator may read real orders at decision time **only** in labelled teacher-forced modes (T, TF-E). Results scored under different spec versions are never mixed.

## 9. P&L reconciliation (separate diagnostic, afterwards)
After decision scoring is reported, P&L is reconciled per cycle as a **diagnostic**: real vs simulated P&L, **stop flips counted and reported separately**, decomposed into entry, exit, sizing and carried-book effects as in `RECONSTRUCTION_GAP`. It **must not** feed back into any parameter, rule or selection; a rule is never kept or dropped because of P&L.

## 10. Amendments
After the first scoring run, a change requires: a dated entry in the log below with the reason; a new version number; re-scoring of every earlier run under the new version; and reporting of both versions side by side. Before the first scoring run, review changes are recorded as version 1.x with the new hash in `spec_freeze.json`.

## 11. Verification of the scorer (each is a test; the first is a gate)
1. **Legacy bridge (gate).** The legacy lot-level F1, computed with the **original matching definition** on the stored engine replay, reproduces the published **0.688** (D-1: 0.6878, precision 0.7504, recall 0.6349) and on the stored D0 free-running orders the published **0.410**. If either does not reproduce, the discrepancy is investigated and explained **before** any new metric is compared or reported; no new-framework result is trusted until this passes.
2. One-to-one matching (no order used twice); determinism and permutation invariance (shuffling the input order changes nothing).
3. Partition identities (matched + missing = real; matched + extra = simulated), per tier and class; exclusive tiers partition the matched set; cumulative shares equal the sum of exclusive shares.
4. Perfect reproduction gives every metric = 1; a simulated copy shifted by k seconds is matched in the tier that contains k and not in lower tiers.
5. Tier cumulativeness (matches never decrease from Exact to Broad); the time-shift placebo lowers time-specific metrics on a structured example.
6. Ambiguity: same-second groups with differing strikes are flagged; both tie-break directions are computed and the range reported.
7. State metrics on a hand-built example with known answers; TF-E and F/T runs are labelled and never merged.
8. Boundary cases: |Δ| exactly 5 s and exactly 60 s fall in Near and Broad respectively; 60.4 s does not match; floor(t) handling for fractional simulated times.

## 12. Limits stated in advance
The time axis is the first-fill second; many simulated orders (rules that fire on a bar) cannot be second-accurate by construction, so the Exact tier mostly reflects timetable rules, and decision timing is judged by the Broad cumulative tier and by same-minute agreement. No decision time, order acknowledgement or cancellation exists, so order type is limited to validity, module and limit-price offset. Same-second ties use the export row, which may not be the true sequence. Hidden or manual orders are not seen (`m_`: one day). All scored cycles are development cycles: until independent data exist, results carry the labels *historical reproduction* or *out-of-fold* only, and the *independent* label is stated as empty.

## Amendment log
| Version | Date | Change | Reason |
|---|---|---|---|
| 1.0 | 2026-11-25 | First version, frozen for review (hash 4abd0d22...) | Phase A step 2 |
| 1.1 | 2026-11-25 | Tiers made mutually exclusive (Exact / Near / Broad / Unmatched) with cumulative 0/5/60 s reported in addition; principle 7 (decision vs execution timing; exact second never a universal pass/fail or closure gate); same-minute agreement added as decision-timing proxy; three modes F / T / TF-E with TF-E required for D-1 as a **diagnostic only**, and the note that T = F for D-1 (flat start); same-second ambiguity flagging with both tie-break directions and a reported range; the 15-minute shift renamed a time-shift placebo; legacy-F1 reproduction made an explicit gate (section 11.1); boundary tests added | User review of v1.0 (2026-11-25), before any scoring run |
