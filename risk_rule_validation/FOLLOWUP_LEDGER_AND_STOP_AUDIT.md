# Follow-up audit: corrected carried inventory and the cycle-stop controller

PR #8, head after `8f085677`. Nothing in PR #3, PR #5 or earlier `risk_rule_validation/` outputs is modified; existing
register rows are unchanged; Stage 2 has not started. Every number below is from executed code (scripts in this folder,
results in [`results/`](results/)).

## 1. Result in four classes

### Validated data-accounting facts
1. **Session-allocation defect in PR #3 (DAT-10), now reproduced and isolated.** PR #3's `minute_index` clips a time to the
   whole two-day grid, so the **77 orders / 1,024 lots** placed after the last D-1 bar land on the first D0 minute. A sandbox
   copy of PR #3 with only that function made session-aware was re-run in full. An **unpatched control** sandbox reproduces
   PR #3's lot ledgers and contract/book-minute panels **exactly**, so every difference in those layers is the patch.
2. **What the patch changes:** 945 lot carried-flags (cheapest-first, FIFO; 943 LIFO) and 927 entry-day flags in **17 cycles**;
   786 of 205,752 contract-minute rows (0.38 %, 7 cycles); 38 of 20,886 book-minute rows (16 cycles). The closing-order
   ledger, the exit taxonomy, the order table, the market grids and the exit panel are **identical** (verified).
3. **Corrected carried inventory = fills-based net position at the D-1 close in all 32 carry cycles,** except NIFTY 29 Sep,
   which PR #3's definition cannot count as carried because the export has no D0 fills for it (definitional; 109 short / 186 long lots).
4. **Order numbers are a submission sequence, but only inside a number block.** Column 4 is unique per date. Inside one
   dashboard app key it forms concurrent **blocks** (602 blocks; e.g. on 31 Aug one block holds the body orders and some `s_`
   orders, another the `h_` wing orders and the other `s_` orders, with numbers that interleave in time). Inside a block the
   number is monotone in fill time (0.74 % adjacent inversions) and in order-entry minute (0.07 %). Numbers are therefore
   compared only inside one block. Tag times of `s_` / `h_` orders are decision times: on stop days the `s_` wing sales are
   decided at the trigger but submitted after the body's sales ([`order_number_stream_validation.csv`](results/order_number_stream_validation.csv)).
5. **Ordering convention matters around stops.** PR #3's closing-order ledger processes orders by decision time; at the stops,
   fill-time order assigns some "closing" and "opening" roles the other way round (e.g. 31 Aug: body sells close the wings,
   the later-filled `s_` sells open shorts). Totals are unaffected; only the role split is.
6. **Earlier claim corrected:** the Phase 4 quote-marked share at the trigger is **0.62–1.00 (median 1.00)**, not 100 % as
   written in the first report and in RSK-09 (SENSEX 6 Aug 0.62, NIFTY 22 Sep 0.90).
7. **Earlier claim corrected:** the "116 post-stop short-opening orders, 67 in flight" in RSK-09 used the taxonomy's `open`
   label and order-entry minutes. With fill-time roles and within-block order numbers: **60 non-`s_` short-opening orders
   (253 lots) in 8 of 12 stops; 5 (5 lots, 2 stops) were submitted just before the first `s_` order of their block (in
   flight); 46 single-lot sales (7 stops) and 9 wing double-liquidations (202 lots, 3 stops) were submitted after it** (§3).

### Strongly supported algorithm behaviour
* **Cycle stop on cumulative D-1 + D0 MTM** (RSK-01, RSK-09): with the algorithm's own near-trigger quotes, median
  −₹1.38 to −1.43 L and SD ₹5.4–6.3 K across three quote variants; NIFTY and SENSEX alike; fires on D-1 too.
* **Two liquidators act at once after a stop:** the `s_` module and the body module's ordinary machinery (hedge release,
  buybacks, new sales). In 8 of 12 stops the `s_` module sells wings that body orders had already sold, opening **823 short
  lots**, and a later `s_` wave buys them back. The short book is flat a median **10 s** after the stop (max 119 s), and no
  position is left at the end of any stop session.
* **No post-stop short sale survives:** the 46 new single-lot sales are reversed after a median 2 s (max 272 s), the 5 in-flight
  ones within 2 s and the 9 wing double-liquidations (202 lots) after 2–5 s.

### Hypotheses (not established)
* The body module does not know the cycle has stopped: its post-stop sales sit at the D0 opening slots (09:15–09:17) or
  near ATM right after buybacks (30 Jun 14:25), i.e. scheduled or replacement re-sales.
* The `s_` over-sale is a race with the body's hedge release (HDG-06): both sell the same wings.

### Unresolved implementation details
* The exact stop constant: between the deepest non-stop minute-close MTM (−₹1.218 L) and the smallest liquidation-quote MTM
  (−₹1.356 L). Minute-close and intraminute bounds cannot narrow it (§4).
* Check cadence and decision-to-submission latency of the `s_` module (tag time vs order number); how the `s_` module
  chooses wave order; why it sells wings the body has already sold.
* Whether post-stop body sales are suppressed by any lock at all (they are reversed, not prevented).

## 2. PR #3 re-run: old vs corrected

Dependency inventory: [`pr3_dependency_inventory.csv`](results/pr3_dependency_inventory.csv). File-level diff:
[`pr3_rerun_file_diff.csv`](results/pr3_rerun_file_diff.csv); lot-level changes: [`pr3_rerun_lot_changes.csv`](results/pr3_rerun_lot_changes.csv);
re-run outputs kept in [`results/pr3_rerun_outputs/`](results/pr3_rerun_outputs/).

| PR #3 output (register rows) | Patch-sensitive? | Old → corrected | Conclusion |
|---|---|---|---|
| Lot ledgers (DAT-08, EXT-03, EXT-05) | direct | carried short lots (cheapest-first) 3,021 → 3,129; per-cycle counts now = fills | **corrected data**; DAT-08 reconciliation still exact |
| Exit ledger, taxonomy, exit panel (EXT-01) | no | identical | unchanged |
| Triggers / stop shape / carry-stop report (EXT-04, EXT-06) | no | identical (T4 gains differ by ≤ 0.146 = run-to-run noise in a panel-only stage) | unchanged |
| First passage, D-1 response curve (EXT-02) | direct | **identical** (88 % at 1.7× etc.) | unchanged |
| First passage, D0 segments (EXT-05) | direct | 13 of 126 D0 rows change; stop-consistent rate max ±0.016; carried own-cheapest 0.40 / 0.27 / 0.20 unchanged | unchanged |
| First-passage latency / quantity (EXT-03, EXT-11) | direct | one-lot share ±0.017; latency p75 +4 s in one row | unchanged |
| Carried hazards (EXT-05) | direct | carried-only hazard 2.88 % → 2.88 %; mixed 14.65 % unchanged | unchanged |
| Carry-SL readings (RSK-02) | direct | 1 direction flip: "D0 loss ≥ 4 % of \|D-1 MTM\|" TEST lift 1.54 → 0.83 (it already failed VAL) | **UNKNOWN unchanged**, slightly more negative ([`rerun_rsk02_carry_sl_old_vs_new.csv`](results/rerun_rsk02_carry_sl_old_vs_new.csv)) |
| Side / basket selection (MGT-05, MGT-06) | indirect | 3,014 → 3,015 episodes; side-level hit@1 0.772 vs 0.471, basket 0.576 vs 0.351 unchanged; clogit coefficients ±0.03 | unchanged |
| Clock-B selection (MGT-03, MGT-04) | indirect | exact-set share ±0.011 | unchanged |
| Newest-reference hazards | direct | ±1 event, hazard ±0.00004 | unchanged |
| Exit models, TEST (ML-03) | indirect | Control reproduces every headline TEST row exactly (run-to-run noise only in the multi-class per-class rows and logistic baselines). Patch effect: **carried-position exit** LightGBM P/R 0.38 / 0.25 → **0.26 / 0.31**, CatBoost 0.32 / 0.32 → 0.36 / 0.29; profit-taking (6b) CatBoost 0.20 / 0.22 → 0.13 / 0.18; any unscheduled buy-back ±0.06; lot stop, side-level ≤ 0.012, re-entry ≤ 0.03; basket, Clock-B, salvage, final liquidation identical. No model reaches 80 / 80 ([`rerun_model_TEST_headline_three_way.csv`](results/rerun_model_TEST_headline_three_way.csv)) | **conclusion unchanged** (none reaches 80 / 80); the ML-03 values for carried-position exit and profit-taking are superseded |
| Autonomous replay (ML-06) | direct (Mode A injects late D-1 orders) | Control reproduces PR #3 exactly (deterministic). TEST, ML controller: Mode A minute-open P/R 0.40 / 0.24 → 0.40 / 0.22, replay P&L ₹4.6 L → ₹5.7 L (actual ₹7.5 L), cycle corr 0.87 → 0.82; Mode B 0.37 / 0.12 → 0.36 / 0.12, P&L −₹3.5 L → −₹4.2 L; adverse Mode A −₹10.3 L → −₹12.2 L; delay-1 Mode A ₹5.7 L → ₹8.5 L ([`rerun_replay_TEST_ml_controller_old_vs_new.csv`](results/rerun_replay_TEST_ml_controller_old_vs_new.csv)) | **match-rate conclusions unchanged**; replay **P&L sums are fragile** (move ₹0.7–2.8 L with a 1,024-lot timing correction) |
| Robustness suite (ML-07) | indirect | **Not reconciled**: the patched run did not finish within the session's 2-hour job limit and the control run was stopped at that limit | unchanged, not re-verified |

Deterministic layers were checked against an unpatched control: it reproduces PR #3's lot ledgers, contract/book-minute panels, `carried.py`, `newest_ref.py` and `clock_b.py` outputs exactly, so every change listed above for those files is the session-mapping correction alone.

## 3. The 12 cycle-stop events, order by order

Full sequences: [`stop_event_order_sequence.csv`](results/stop_event_order_sequence.csv) (every order from 2 min before each
stop, with order number, app key, `s_` wave, fill-time position role); classification of every post-stop short-opening
order: [`post_stop_short_fills_classified.csv`](results/post_stop_short_fills_classified.csv); per-stop summary:
[`stop_event_summary.csv`](results/stop_event_summary.csv). A "wave" is a run of consecutive `s_` order numbers in the stop's stream.

| Stop (expiry, und, decision time) | s_ orders | s_ waves | s_ buy lots | s_ sell lots | s_ over-sale (short-opening) lots | Open short / long lots at stop | Post-stop non-s_ short-opening orders | their lots | Seconds until short book flat |
|---|---|---|---|---|---|---|---|---|---|
| 06-30 N 14:25:13 (D0) | 37 | 4 | 279 | 149 | 141 | 141 / 141 | 10 | 10 | 14 |
| 07-14 N 09:15:17 (D0) | 39 | 5 | 176 | 120 | 117 | 56 / 56 | 12 | 14 | 45 |
| 08-18 N 09:15:07 (D0) | 53 | 2 | 227 | 231 | 164 | 63 / 113 | 0 | 0 | 5 |
| 09-01 N 14:46:25 (D-1) | 30 | 3 | 117 | 46 | 27 | 71 / 65 | 0 | 0 | 3 |
| 09-22 N 14:14:29 (D0) | 13 | 2 | 91 | 97 | 0 | 209 / 210 | 0 | 0 | 5 |
| 10-13 N 09:18:01 (D0) | 47 | 2 | 107 | 126 | 0 | 104 / 98 | 4 | 4 | 10 |
| 10-19 N 09:26:19 (D0) | 31 | 3 | 299 | 309 | 0 | 120 / 344 | 8 | 199 | 3 |
| 07-16 S 11:00:46 (D0) | 26 | 5 | 122 | 98 | 98 | 98 / 98 | 0 | 0 | 10 |
| 08-06 S 09:22:40 (D0) | 35 | 4 | 128 | 91 | 64 | 66 / 66 | 2 | 2 | 119 |
| 08-20 S 09:14:13 (D0) | 57 | 2 | 280 | 230 | 147 | 120 / 157 | 16 | 16 | 80 |
| 09-24 S 09:15:00 (D0) | 23 | 2 | 133 | 93 | 65 | 124 / 159 | 4 | 4 | 26 |
| 10-15 S 09:16:28 (D0) | 26 | 3 | 62 | 67 | 0 | 60 / 65 | 4 | 4 | 8 |

**Classification of non-`s_` short-opening orders filled after the stop** (order number vs the first `s_` order of the same
app key; contract position at the stop from fills):

| Class | Orders | Lots | Cycles | Next buy of that contract |
|---|---:|---:|---:|---|
| In flight (number just below the first `s_` order of its block; filled 1–2 s after the decision) | 5 | 5 | 2 (30 Jun, 19 Oct) | `s_` 4, body 1; ≤ 2 s |
| Wing double-liquidation (contract long at the stop; `s_` also sold it) | 9 | 202 | 3 (14 Jul, 13 Oct, 19 Oct) | `s_`, after 2–5 s |
| New short in a contract flat or short at the stop | 46 | 46 | 7 | `s_` 24, body 21, not found 1; median 2 s, max 272 s |
| Unresolved (no `s_` in its block and entered in the stop minute) | 0 | 0 | 0 | — |

58 of the 60 classifications rest on within-block order numbers; 2 (SENSEX 6 Aug, entered at 09:30, 8 min after the stop) on order-entry minutes.

Typical sequence (31 Aug, D-1 stop): 14:46:25.05 `s_` decision → wave 1 buys back all shorts (fills 14:46:28) → body orders
sell the far wings (14:46:29–31) → wave 2 (`s_`) sells the same wings, opening 27 short lots (14:46:31–32) → wave 3 (`s_`,
from the second number block) buys them back (14:46:36). Book flat after 3 s.

## 4. Re-assessing the ≈ ₹1.4 L stop

Cumulative MTM at the first `s_` decision = cash of all fills before it + open positions at the stated marks
([`stop_mtm_sensitivity_summary.csv`](results/stop_mtm_sensitivity_summary.csv), [`stop_mtm_sensitivity_by_stop.csv`](results/stop_mtm_sensitivity_by_stop.csv)).
10 stops, excluding the two whose trigger-time MTM is beyond −₹1.8 L (both at a session open):

| Marks | Median (₹ L) | SD (₹ K) | Range (₹ L) | NIFTY / SENSEX median |
|---|---:|---:|---|---|
| V1 base: `s_` recovered quotes (≤ 60 s), else other orders' quotes (≤ 60 s), else previous-minute close | −1.419 | 5.5 | −1.53 to −1.36 | −1.428 / −1.412 |
| V3 quote window 300 s | −1.429 | 5.4 | −1.53 to −1.36 | −1.423 / −1.429 |
| V4 `s_` fill VWAP instead of the recovered quote | −1.383 | 6.3 | −1.55 to −1.36 | −1.375 / −1.397 |
| V2 quotes of the first decision instant only, rest previous-minute close | −1.394 | 93.7 | −1.53 to +1.54 | — |
| V5 all at previous-minute close | −1.155 | 48.3 | −1.29 to +0.27 | — |
| V6 all at stop-minute close | −1.480 | 55.2 | −2.90 to −0.70 | — |
| V7 adverse intraminute bound | −1.986 | 69.6 | — | — |
| V8 favourable intraminute bound | −0.758 | 37.3 | — | — |

* **Robust:** the level and the tightness hold whenever positions are marked with the algorithm's own trigger-time prices
  (V1, V3, V4). The `s_` limit band is confirmed: fill ÷ recovered quote = 0.99 for buys and sells ([`s_order_band_check.csv`](results/s_order_band_check.csv)).
* **Depends on the reconstruction:** with minute-bar marks alone (V5, V6) the spread is ₹48–55 K and the level is only
  bracketed. The "no false trigger" evidence rests on minute closes: non-stop cycles reach −₹1.218 L on closes, but their
  adverse intraminute bounds reach −₹1.42 to −1.95 L in 6 cycles ([`non_stop_cycles_deepest_mtm.csv`](results/non_stop_cycles_deepest_mtm.csv)).
  The bound is not a real MTM (contract highs are not simultaneous), so it neither confirms nor refutes.
* **D-1 closing mark:** irrelevant for the cumulative stop (it uses cash, not the D-1 mark). For the expiry-day-only MTM at
  the 9 non-gap D0 stops, the post-close print reference moves it by ₹0–21.5 K (median ₹11.7 K); the range stays
  −₹0.69 L to −₹2.98 L, so RSK-08's conclusion (the stop is not keyed to expiry-day P&L) is unchanged
  ([`stop_d0_only_mtm_d1_mark_sensitivity.csv`](results/stop_d0_only_mtm_d1_mark_sensitivity.csv)).

## 5. What is robust and what depends on reconstruction

| Conclusion | Robust to | Depends on |
|---|---|---|
| Stop is on cumulative cycle MTM, not expiry-day P&L | quote variants V1/V3/V4, D-1 mark, ownership convention | — |
| Stop level ≈ −₹1.38 to −1.43 L, SD ≈ ₹5–6 K | V1/V3/V4 | using the algorithm's own trigger-time prices; minute bars alone cannot show it |
| Exact stop constant | — | not identifiable (between −₹1.22 L and −₹1.36 L) |
| No stop without crossing / no crossing without stop | minute-close MTM | intraminute path (unobservable) |
| Most post-stop short sales are new submissions (55 of 60), not in flight | within-block order numbers (validated: 0.74 % fill-time inversions) | the block split (jump > 500) and the number being assigned at submission (not documented) |
| Carried inventory per cycle | — (now equals fills) | NIFTY 29 Sep definition |
| PR #3 headline exit findings (EXT-02 to EXT-06, MGT-05/06, RSK-02) | the session-mapping correction | — |
| Carried / fresh split of D0 buybacks | — | ownership convention (2,903 lots differ) |
| ML conclusions (no model at 80 / 80; replay matches a fifth to a quarter of exits) | the correction and run-to-run noise | — |
| Replay P&L sums and the carried-exit model values | — | the session mapping (they move materially) |

## 6. Files

| File | Content |
|---|---|
| `stop_sequence.py` | Order-number stream validation; per-stop order sequences, `s_` waves, fill-time roles; post-stop short classification |
| `stop_mtm_sensitivity.py` | Eight mark variants at the trigger; D-1 mark sensitivity; non-stop deepest MTM; `s_` band check |
| `reconcile_pr3_rerun.py` | PR #3 committed vs patched re-run (files, lots); re-run ledger vs `rr_common.ledger` |
| `ml_noise_vs_patch.py` | Three-way comparison (PR #3 / unpatched control / patched) for models, replay, robustness |
| `results/pr3_rerun_patch.diff` | The only code change used in the re-run |

Re-run procedure: copy `analysis/` to a scratch sandbox (no links), apply `pr3_rerun_patch.diff`, run
`analysis/exit_engine/run_all.py`, then `models.py --merge` and `robustness.py`; the control sandbox runs the same stages without the patch.

## 7. Register and limits of this audit

New register rows only: **DAT-11** (re-run reconciliation), **DAT-12** (order-number blocks; decision vs fill ordering),
**DAT-13** (corrections to RSK-09 as first written), **RSK-10** (post-stop behaviour), **RSK-11** (stop-level sensitivity),
**ML-08** (corrected ML values). Existing rows, client statements and classifications are unchanged.

Not done in this audit: the PR #3 robustness suite (ML-07) was not reconciled. The patched run did not finish and the
control run was stopped at the session's 2-hour background-job limit. PR #5 (allocation) also uses the PR #3 lot ledger
and was not re-run. All data remain in-sample.
