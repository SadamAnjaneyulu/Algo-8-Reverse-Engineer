# TP-03 Phase 1: operational test specification (written BEFORE any hypothesis test was run)

Configuration `tp03/config.yaml` is unchanged (frozen sha256 `942e36d8…c2f8`). This file fixes the **implementation details** of the pre-registered tests E1–E8, which the frozen configuration names but does not spell out to code level. Nothing here changes a registered threshold, window, feature, view, gate or family size. It is committed before the tests are run.

## 1. Opportunity dataset
* One row per (cycle, day type, window): pre-expiry 21 candidate windows (17 registered + 4 control) × cycles with a pre-expiry session; expiry day 23 windows × cycles with an expiry-day session.
* Window `[T−2 s, T+3 min)`; common primary snapshot `floor_minute(T−2 s)`; S1 snapshot = `floor_minute(first fill of the earliest attributed order)` for actions, `floor_minute(T)` for no-action windows.
* Three views side by side (config `reporting_views`): V1 fill-time structural, V2 submission-attributed including boundary-ambiguous, V3 submission-attributed excluding boundary-ambiguous (window classed `AMBIGUOUS_ACTION` and dropped from V3 when its only attributed orders are ambiguous).
* Quantity outcome `Q` = new body-short units ÷ base unit (65 NIFTY / 20 SENSEX), CE + PE together (as in Phase 0 table 4); `Q_CE`, `Q_PE` reported alongside. V1: units of fills inside the window; V2/V3: full units of the attributed parent orders.
* Entry reference for `spot_ret_since_entry_bp` / `atm_straddle_premium_change_since_entry`: the order-entry minute of the cycle's first body-short opening; the value is NaN before it.
* `spot_ret_prev_window_bp`: log-return between the last completed bars before the previous window of the same session and before the snapshot; NaN for the first window of a session.
* NaN cells (bars not yet available, e.g. 60-minute return at 09:30) are dropped for that window only; a feature that is constant within a window is not testable in it. `minutes_to_expiry` is constant within every window by construction and is reported NOT_TESTABLE.

## 2. E2 statistic and permutation (as registered, `permutation_design`)
* Per underlying and day type, arrays `X[cycle, window]` (feature) and `Y[cycle, window]` (outcome); cells that are NOT_APPLICABLE / dropped in either cycle of a pair are masked.
* Per window `w` (≥ 8 usable cycles; for binary `Y` ≥ 2 of each class): binary `Y` → pooled-variance t of the feature between action and no-action cells; quantity `Y` → Fisher-z of the Spearman correlation × √(n−3). Window statistics are standardised by construction and **combined** as `S = Σ_w s_w / √(#windows used)`; the two underlyings are combined by the same sum (one pooled statistic per test). The test is two-sided: statistic `|S|`.
* Primary permutation: cycle-block (rows of `X` permuted among cycles of the same underlying and day type). Sensitivity: within-window shuffle across cycles. p-values via the registered sequential rule (`seqperm.run_test`), seed `SeedSequence([20261114, crc32(test_id)])`.
* Holm: family size is the registered upper bound 120 (first-step threshold 0.000417); a test is "Holm-significant" if its sequential p ≤ `0.05 / (120 − rank + 1)` in ascending p order across all entry tests run. Sign consistency across underlyings and across the two designs, and in ≥ 60 % of cycles, are reported separately as criteria for STRONGLY_SUPPORTED.
* Testability: `tp03_common.testability()` (E2 action: N ≥ 100 observations AND minority class ≥ 30 pooled AND ≥ 10 per underlying AND ≥ 10 cycles per underlying; quantity and the other tests: N ≥ 100 and ≥ 10 cycles per underlying). Evidence ceiling: `e2_evidence_ceiling()`.
* Binary outcomes are always run on the 21 candidate windows (pre-expiry) and the applicable expiry-day windows, never on the 17 registered windows alone (all 544 act).

## 3. Other registered tests (operational form)
| Test | Statistic | Null | Count in family |
|---|---|---|---:|
| E1 | per-window action rate with Wilson 95 % interval; unconditional rate over the 21 windows; every `NO_ACTION_ACTIVE` window listed | descriptive, no p-value | 1 |
| E3a / E3b | share of window quantities equal to the window's modal quantity, pre-expiry (17 registered windows) and expiry day (23 windows); per-underlying shares and cross-underlying transfer of the mode | permutation of the window label within each cycle (the ladder is destroyed, the cycle's own quantities kept), sequential p | 3 (E3a, E3b, E3c: NIFTY mode applied to SENSEX and vice versa) |
| E4 | NOT_TESTABLE (no margin / capital data); `gross_short_notional` association reported as a labelled proxy only, outside the family | — | 0 |
| E5 | exact-match rate of the traded strike with `K = step · floor(S/step + 0.5)` under R1 (last completed close before the order-entry minute), R2 (before the first fill), R3 (09:15 close, opening orders only); tilt = sign of (K_traded − K_ref) agrees with the sign of the preceding 15-minute spot return among non-exact orders | exact match: random-session-minute reference null (same session, uniform minute, the order's strike held fixed), sequential p; tilt: permutation of the return signs across orders of the same underlying | 6 (3 references × {exact, tilt}); R3 only on opening orders |
| E6 | wing strike reproduces "highest OTM strike with premium ≤ 2.5 % of the ATM leg": exact and within-one-step match under three premium references (algo quote from the order's own limit, last completed bar close, fill price); budget 2.5 % fixed, 1.5 % and 4 % shown only as a sensitivity set | ATM-reference premium taken from a random other minute of the same session | 6 (3 references × {exact, within one}) |
| E7 | wing / body unit ratio under three matching conventions: C1 same window and right, C2 cycle-cumulative per right, C3 per attributed parent order pair (wing parent next after body parent of the same right in the same minute); share at the modal ratio | permutation of wing quantities across windows within the cycle | 3 |
| E8 | share of body-short opening parent orders entered within 10 minutes after a closing fill of the same cycle | time-shift null: circular shift of the session's opening times | 1 |
| E2 | 25 features × {action, quantity} × {pre-expiry, expiry day} | cycle-block permutation | 100 |
| Family | | | 1 + 100 + 3 + 6 + 6 + 3 + 1 = 120 |

E1 counts as one family member although it carries no p-value (the registered count is kept unchanged).

## 4. Reproducibility and logging
Every sequential test writes (test id, seed entropy, observed statistic, draws, exceedances, stopping reason, extension flag, p) to `tp03/analysis/p1_permutation_log.csv`. The whole Phase 1 chain is run twice and all CSV outputs are compared bytewise.
