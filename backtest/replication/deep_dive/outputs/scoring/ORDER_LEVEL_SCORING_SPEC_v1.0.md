# Order-level scoring specification (version 1.0)

*Written 2026-11-25 for Phase A, step 2 of the closure standard (audit section 9). **This specification is written and frozen before the simulator is built and before any order-level scoring is run.** The freeze hash is in `outputs/scoring/spec_freeze.json`. Status: **frozen for review**: it binds from the first scoring run; until then the user's review may produce version 1.1 (recorded in the amendment log at the end). After the first scoring run, any change is a dated amendment under section 10.*

## 0. Purpose and what this is not
Measure **how faithfully a reconstruction reproduces the original system's orders**, one order at a time and state by state. It is **not** a measure of strategy profitability or deployment readiness, and it is **not** a tuning target for P&L.

## 1. Principles (binding)
1. **Decisions first.** The score is about which orders were sent: when, on what, which side, which strike, how many lots, of which type. P&L is a separate diagnostic computed afterwards (section 9) and **never** enters an objective, gate or selection.
2. **One fixed matching procedure** (section 4). A real order matches at most one simulated order and vice versa.
3. **Report the distribution, not only the aggregate.** Every headline number comes with its per-cycle distribution (section 7). Aggregate F1 alone is not an acceptable report.
4. **D-1, D0 and end-to-end are reported separately** (section 7).
5. **Labelled evidence.** Every result carries one of three labels: *historical reproduction* (parameters fitted on the scored cycles), *out-of-fold* (parameters fitted on other cycles), *independent* (cycles or logs not used in any design or fitting step; **empty until new real data exist**).
6. **No retrospective adjustment.** Tolerances, tiers, thresholds and metric definitions are not changed after seeing results; a rule's threshold is never moved to capture a missed case.

## 2. Data contract
### 2.1 Real side (the export `Trades_GKOHNP140.csv`, via `bl_d0x_diag.real_orders()`)
Unit = **order** (one row per order tag). Fields used: cycle (underlying, expiry), day (`dayno` 0 = D-1, 1 = D0), module (`num` body, `h_` wing, `v_` lump, `s_` stop, `m_` manual), role, option type (`cp`), side, strike, filled lots (`lots`; requested `lim_lots` is reported, not matched on), validity (DAY / IOC), limit price (`lim_px`), **time = first-fill second (`t_first`, integer second of day)**, export row (`row`, tie-break).
**Stated limits:** (a) the export has no decision time (`t_dec` empty) and no acknowledgements, so the first-fill second is the **only** time; it equals the placement time to within about one second (all sells are marketable limits that fill within about a second); (b) partial fills (2.7% of orders) are one order with its first-fill time and total filled lots; (c) orders in the same second are ordered by export row; (d) 18.1% of orders are multi-lot (hedge, lump, stop orders; freeze-quantity splits); (e) there are **no market orders** in the export: every order is a limit order, so "order type" can only mean the fields below.
### 2.2 Simulated side (contract the simulator must satisfy)
One record per order: cycle, day, **t (seconds of day, float)**, `t_resolution` (`second` if the rule fixes the second, e.g. a timetable; `minute` if it fires on a minute bar), underlying, expiry, option type, side, strike, lots, validity, module class, limit price, role (class label), and the **book after the order** (positions by contract). **If the simulator cannot supply validity, order-type scoring is reported as "not available" for that run; it is never assumed.** The current engine's `orders_frame()` lacks validity; adding it is a prerequisite for order-type scoring.
### 2.3 Classes (reporting only, never matching keys)
Body sell (scheduled pair / reactive pair / solo / other), body buy-back, wing buy, wing sell, opening wings, overnight lump, stop module, not modelled. Real classes come from `role` and the existing class rules (`bl_fr_score.py`); simulated classes from the engine role. Results are reported per class and for all.

## 3. Scope
Development cycles: D-1 of the 32 cycles with a D-1 log; D0 of the 30 cycles with both logs. **All cycles are scored and reported, including NIFTY 16 Oct and the stop-out cycles; the reports also give the results without the outlier cycle and with stop cycles separated** (a stop ends the day and changes every later number).

## 4. Matching procedure (frozen)
Keys that must be equal: **cycle, day, option type, side** (underlying and expiry are part of the cycle). Strike, lots and order type are **scored on matched pairs, not used to find them**, so a wrong strike is a mismatch rather than a missing order.
**Tiers** (cumulative, fixed): **T0** |Δt| = 0 s; **T1** |Δt| <= 5 s; **T2** |Δt| <= 60 s (the one-minute tolerance).
**Algorithm:** within each group of equal keys, tier by tier (T0, then T1, then T2), among the still-unmatched real and simulated orders solve a **minimum-cost one-to-one assignment** (`scipy.optimize.linear_sum_assignment`) restricted to pairs within the tier's time tolerance, with cost = |Δt| + 0.001 x |Δstrike in steps| + 0.000001 x |Δlots|, so time dominates, strike distance breaks time ties and lots breaks the rest; remaining ties break by (t, export row / simulation sequence). Orders unmatched after T2 are **missing** (real) or **extra** (simulated). Each order is used **at most once** (asserted by the scorer).
**Outputs of matching:** per pair the tier, Δt (signed, seconds), Δstrike (steps, signed), Δlots (signed), type agreement; per order its status (matched / missing / extra).
**Granularity-neutral secondary view:** orders in the same second, same cycle, day, option type, side are summed to a **burst** and burst lots are compared (so "1 order of 3 lots" and "3 orders of 1 lot" are not double-penalised). Reported separately from the order-level view.
**Bridge metric (continuity only):** the legacy lot-level F1 (+/-1 minute, same right and class) is computed on the same runs so new numbers can be related to the earlier 0.688 (D-1) and 0.41 (D0); it is **not** a headline metric.

## 5. Metrics (all reported at order level; lot-weighted versions alongside)
| Dimension | Metric |
|---|---|
| Timestamp | share of real orders matched at T0 (exact second), at T1 and at T2; separately the **one-minute-tolerance score** (T2 cumulative); matched Δt distribution (median, IQR, signed bias); broken out by simulated `t_resolution` |
| Instrument and side | key-level agreement: share of real orders with any simulated order of the same cycle and day within 60 s **regardless of option type and side** (to expose mis-keyed errors), versus the same share with the keys required |
| Strike | exact strike share among matched; distribution of |Δ steps|; share within +/-1 step |
| Quantity | exact lot match share; absolute lot-count error (mean, median, p90); signed bias; lot-weighted error; burst-level lot error |
| Order type | agreement on (validity, module class) among matched, where the simulator supplies it; limit-price offset class (marketable +/-15% or other) reported as a diagnostic |
| Joint | **full match** = matched at T0, T1 or T2 **and** strike exact **and** lots exact **and** type agrees; reported for each tier |
| Unmatched | **missing** and **extra** counts and lots, separately, by class, 30-minute block and cycle; precision = matched / simulated, recall = matched / real, F1, each at each tier and at each strictness level (keys only; + strike within one step; + strike exact; + lots exact; + type) |
| Null | the same metrics with the simulated times shifted by +15 minutes (same orders), as in the earlier work, so a number can be read against chance |

## 6. Portfolio state
**After each matched event**, compare the real and simulated books **immediately after** that event: real book = cumulative real orders up to and including the matched real order in (t, row) order; simulated book = cumulative simulated orders up to and including the matched simulated order. Per option type: short lots S and long lots L (signed and absolute difference); share of matched events with both S and L equal; per-contract L1 distance sum |pos_real - pos_sim| divided by gross real lots. **Checkpoints** every 15 minutes and at the end of the day (the carried book at the D-1 close is compared contract by contract, as in `D1_FREE_RUN`).
**Modes (always labelled):** **F** free-running (D-1 from a flat book; D0 from the **simulated** carried book); **T** teacher-forced start (D0 from the **real** carried book); **TF-E** event-level teacher forcing (the simulated book is replaced by the real book after every real order and only the next decision is scored; isolates rule errors from compounding). D-1 starts flat in all modes. End-to-end = F for D-1 then D0.

## 7. Aggregation and required report tables
For D-1, D0 and end-to-end **separately**: (1) pooled (micro) metrics with cycle-cluster bootstrap 95% intervals (4,000 draws); (2) the **per-cycle distribution** of F1, precision, recall, lot-count error and state error: median, IQR, 10th percentile, minimum, maximum, the **five worst cycles named**, the number of cycles with F1 < 0.5 and < 0.3, and the macro average; (3) by class; (4) by underlying, version (V1 before 16 Sep 2026, V2 after) and era (before / after the closing auction of 3 Aug 2026); (5) by 30-minute block; (6) the missing / extra tables. A report that gives only pooled F1 is incomplete under this specification.

## 8. Run record and leakage control
Every scoring run records: spec version and hash, simulator code hash, configuration hash, data (cache) hash, mode (F / T / TF-E), cycle set, and the **evidence label** (historical reproduction / out-of-fold / independent). Parameters may be fitted **only** on order-level decisions of training cycles (never on P&L); out-of-fold means by cycle halves (parity) as before. The simulator may read real orders at decision time **only** in labelled teacher-forced modes. Results scored under different spec versions are never mixed.

## 9. P&L reconciliation (separate diagnostic, afterwards)
After decision scoring is reported, P&L is reconciled per cycle as a **diagnostic**: real vs simulated P&L, **stop flips counted and reported separately** (a flip is worth Rs 4-7 lakh), decomposed into entry, exit, sizing and carried-book effects as in `RECONSTRUCTION_GAP`. It **must not** feed back into any parameter, rule or selection; a rule is never kept or dropped because of P&L.

## 10. Amendments
After the first scoring run, a change requires: a dated entry in the log below with the reason; a new version number; re-scoring of every earlier run under the new version; and reporting of both versions side by side. Before the first scoring run, review changes are recorded as version 1.x with the new hash in `spec_freeze.json`.

## 11. Verification of the scorer (to be built after review; each is a test)
One-to-one matching (no order used twice); determinism and permutation invariance (shuffling input order changes nothing); partition identities (matched + missing = real; matched + extra = simulated, per tier and class); perfect reproduction gives every metric = 1; a simulated copy shifted by k seconds matches exactly at the tier that contains k and not below it; tier cumulativeness (matches never decrease from T0 to T2); the null shift lowers every metric on a structured example; state metrics on a hand-built example with known answers; and the **bridge**: the legacy lot-level F1 recomputed on the engine replay reproduces the earlier published value (0.688), which validates the data plumbing before any new metric is trusted.

## 12. Limits stated in advance
The time axis is the first-fill second, so "exact second" measures agreement with the fill second (about the placement second), and many simulated orders (rules that fire on a bar) cannot be second-accurate by construction; the exact-second tier will mostly reward timetable rules. No decision time, order acknowledgement or cancellation exists, so order type is limited to validity, module and limit-price offset. Same-second order ties use the export row, which may not be the true sequence. Hidden or manual orders are not seen (`m_`: one day). All scored cycles are development cycles: until independent data exist, results carry the labels *historical reproduction* or *out-of-fold* only, and the *independent* label is stated as empty.

## Amendment log
| Version | Date | Change | Reason |
|---|---|---|---|
| 1.0 | 2026-11-25 | First version, frozen for review | Phase A step 2 |
