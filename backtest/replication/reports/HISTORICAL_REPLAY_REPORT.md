# Historical Replay Report: simulated vs actual Algo 8 decisions

**Result:** on the 35 live cycles, the reconstructed D-1 **entry** decisions agree with the real ones at **82 % precision / 67 % recall** (slot × right) and **75 % / 61 %** when the strike must also match; **exit** decisions agree much less (leg-stop buy-backs: 96 % precision but **32 % recall** by count, 58 % / 20 % when time-matched), and **D0 selling is not reproduced at all** by R1 (0 of 12,675 lots) and only 23 % by R2. The replay judges **decisions**, not P&L. **This is an in-sample fit**: the window is the one the rules were decoded from. Code executed: `replay.py`, `decision_agreement.py`, `phase3_checks.py`; tables `decision_agreement.csv`, `ladder_d1_agreement_by_window.csv`, `strike_rule_agreement.csv`, `replay_cycle_pnl.csv`.

## 1. Setup
* Market data: the Breeze 1-minute full chain for each cycle's D-1 and D0 (87–91 strikes). Real fills: `Trades_GKOHNP140.csv` (40,996 of 41,421 fills fall in 09:15–15:29; the other 425 are in the 15:30–15:39 session and are excluded from decision tables).
* Simulator inputs at each decision minute j use only data up to minute j−1. R1 = D-1 ladder + wings + 1.6× leg stop + −₹1.44 L cycle stop + carry + D0 management + 15:14 flatten. R2 = R1 + D0 sales at the per-slot **median** lots observed in this same window (hypothesis-level, fitted).
* Matching is count-based: a simulated order is matched if the live ledger holds an unmatched order of the same category in the same key (cycle × slot × right [× strike]). Precision = matched ÷ simulated; recall = matched ÷ live lots.

## 2. Agreement table (R1; R2 identical for D-1 rows)

| Decision | Simulated | Live lots | Matched | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| D-1 body entries, slot × right (timing + quantity) | 1,820 | 2,234 | 1,491 | **0.82** | **0.67** |
| D-1 body entries, slot × right × **strike** | 1,820 | 2,234 | 1,366 | 0.75 | 0.61 |
| D-1 wing entries, slot × right | 1,820 | 2,139 | 1,416 | 0.78 | 0.66 |
| D-1 wing entries, slot × right × **strike** | 1,820 | 2,139 | 962 | 0.53 | 0.45 |
| D-1 body buy-backs, cycle × right (count only) | 527 | 1,577 | 506 | 0.96 | 0.32 |
| D-1 body buy-backs, cycle × right × strike × 5-min bucket | 527 | 1,577 | 308 | 0.58 | 0.20 |
| D0 body buy-backs, cycle × right (count only) — R1 / R2 | 1,293 / 4,799 | 12,484 | 1,190 / 4,053 | 0.92 / 0.85 | 0.10 / 0.33 |
| D0 body buy-backs, + strike — R1 / R2 | | | 991 / 3,502 | 0.77 / 0.73 | 0.08 / 0.28 |
| D0 body buy-backs, + 5-min bucket — R1 / R2 | | | 678 / 2,129 | 0.52 / 0.44 | 0.05 / 0.17 |
| D0 body sells, cycle × right (count only) — R1 / R2 | 0 / 3,506 | 12,675 | 0 / 2,927 | n/a / 0.84 | **0.00 / 0.23** |

Timing agreement: simulated entries are placed at the first minute of each slot; live orders spread over the first ~3 minutes (`first 4 min of slot: 51 % of lots`); the **other ~50 % of D-1 body lots are off-schedule** and are not matched by construction. Strike agreement given a slot match is **91.6 %** (1,366/1,491). Position quantity: the live D-1 close carries **89.5** net short body lots on average vs **36.9** simulated (correlation 0.11 across cycles).

## 3. Ladder agreement in detail (live first 3 minutes of each slot; `ladder_d1_agreement_by_window.csv`)
* P(CE lots = modal) averaged over 17 slots: 1-min window 0.62, 2-min 0.70, **3-min 0.66**, 4-min 0.64, whole 15-min slot 0.39. P(CE = PE): 0.88 / 0.85 / 0.81 / 0.78 / 0.52.
* High agreement: 09:16 (88 % / 88 %), 10:01 (88 % / 100 %), 10:46 (91 % / 91 %), 12:16 and 12:46 (≈ 80–88 %), 13:01 (88 % / 84 %). Low: **10:16 (22 % CE / 34 % PE)**, 09:31 CE 47 %, 11:01 (47 % / 56 %), 11:46 (44 % / 56 %), 13:16 (44–53 %). So the modal ladder is a good description at some slots and weak at others; "ladder" is a baseline with event-driven deviations (earlier audit REC-04 resolved the 10:15/10:16 boundary issue as a window edge).

## 4. Cycle-level agreement

| | Live | R1 | R2 |
|---|---:|---:|---:|
| Total gross P&L, 35 cycles | ₹26.2 L | ₹4.4 L | ₹4.3 L |
| Per-cycle gross correlation with live | — | 0.35 | 0.40 |
| Per-cycle net correlation (cost model) | — | 0.32 | 0.39 |
| Stop cycles reproduced (12 live stops) | 12 | TP 1 / FP 0 / FN 11 | TP 4 / FP 1 / FN 8 |
| Mean gross on live stop cycles | −₹1.56 L | −₹49 k | −₹55 k |
| Mean gross on live non-stop cycles | +₹1.95 L | +₹45 k | +₹47 k |

The earlier 4-leg baseline had correlation **−0.21** on the same cycles and +₹8.3 k on stop cycles (wrong sign).

## 5. Discrepancies and what they tell us
| Discrepancy | Interpretation (status) |
|---|---|
| Entry recall 0.67 (not 1.0) | Off-schedule entries and ladder quantity deviations. (Established: 45–55 % of D-1 lots are off-schedule.) |
| Strike precision 0.75 vs slot precision 0.82 | The strike rule picks the same strike 91.6 % of the time when the slot matches; the residual is the ±1-step direction bias (STK-03/04). |
| Wing strike 45–53 % | Premium-ratio rule is right on average but the exact strike choice (rounding, per-side budgets, SENSEX ₹0.10 rounding: HDG-02) is not recovered. |
| D-1 buy-back recall 0.32 | 68 % of D-1 buy-backs are not leg stops at 1.6× (price ÷ entry < 1.2 for 51 % of D-1 exits). |
| D0: R1 captures 10 % of buy-backs, 0 % of sells | The D0 book is an active rebalancing machine (Clock-B, replacements, off-schedule sales) that R1 lacks. R2 adds timing-only sales; it still reproduces just 23 % of sold lots. |
| Cycle stop 1/12 | Not a rule failure: the −₹1.44 L level is reached when the live book is 2.4× larger and 12.5 k D0 lots turn over. In R2, 4/12 fire. |

## 6. What the replay can and cannot support
* It **supports**: the D-1 ladder, strike-near-ATM, wing-premium and leg-stop-band rules as *descriptions* of the live window.
* It **does not support** any claim about D0 behaviour, off-schedule sales, replacements, the settlement-hold decision, or the cycle stop *as a trigger for the simulated book size*.
* It cannot validate generalisation: no independent live ledger exists. P&L similarity is **not** used as evidence.
