# Algo 8 exit engine — findings on the corrected data

Branch `research/algo8-exit-engine` (PR #3, stacked on PR #2). All new code is in `analysis/exit_engine/`; `alpha_freeze/`, its hashes, H1 and the OOS protocol are untouched.
Reproduce: `python3 analysis/exit_engine/run_all.py` (clean rebuild), or the split jobs `run_split.py` (models, section 3; it ran 253 minutes in total, 4 jobs at a time). The scheduler's last line lists three model jobs as failed: that is their first attempt, which crashed saving an unpicklable hazard closure; they were fixed and re-run by hand, and the merge uses the fixed re-runs. Numbers below are from the clean build on the
**UniqueOrderIdentifier** key. This document **replaces** the first version, whose numbers were invalid (see §1).

> **STATUS — read this first**
> | Item | Status |
> |---|---|
> | Sections 1–6 (taxonomy, trigger tests, first passage, side/basket, Clock B, carried positions) | **Final on the clean build** |
> | Section 7 ML models (11 jobs, 5 algorithms) | **Final**: VAL and TEST scored once |
> | Section 3 T4 feature-family ablation | **Final**: all nine categories (split jobs merged) |
> | Section 8 autonomous replay | **Final**: three fill assumptions (minute-open, one-minute delay, adverse) × three policies × two modes |
> | Section 9 robustness suite (segments, bootstrap CIs, feature ablation, missing-data stress) | **Final** (4 headline models) |
> | Automated tests on the clean build | **12 passed** (`python -m pytest analysis/exit_engine/tests`, 87 s) |
>
> No result below is a claim of recovered strategy. Unresolved rules are marked **UNKNOWN**.

## 1. What changed and why the first version was withdrawn

| Defect | Effect | Fix |
|---|---|---|
| Column 4 ("order id") is reused across days: 2,224 ids hide 4,840 real orders (2,200 groups span >1 cycle); `groupby(oid).first()` drops 2,616 orders (6.6 %) | First ledger had 15,450 closing orders and ghost lots | Orders keyed by column 163 (`UniqueOrderIdentifier`): 39,874 orders, each one date/underlying/expiry/contract/side/module ([`order_key_audit.csv`](results/order_key_audit.csv)) |
| Side-level and basket labels swapped (`len('CE') == 2`) | "Basket" results were really side-level | Fixed in `taxonomy.py`; unit test added |
| Contracts with no print yet were marked at 0 | Cycle MTM off by up to ₹2–4.5 L in some cycles | Marked at entry (zero unrealised); lot-book MTM now equals the independent fills-plus-candles MTM (median difference ₹0) |

The older base-branch scripts that also used the reused id were audited separately without touching them ([`legacy_oid_audit.csv`](results/legacy_oid_audit.csv)).

## 2. Data products (clean build)

* **Orders:** 39,874 (41,421 fills; 35 cycles). **Closing orders: 16,733** — 11,007 short buy-backs (15,327 lots) and 5,726 long closes.
* **Chronological whole-cycle split:** DEV 18 cycles (≤ 20 Aug), VAL 8 (≤ 22 Sep), TEST 9 (≥ 23 Sep). TEST is never used to fit or tune anything here, but it is **contaminated** for hand-derived constants (the ≈1.6–1.7× stop band, clock windows, the ₹1 / 5 % salvage definition), which were first seen on all 35 cycles.
* **Contract-minute panel:** 205,752 rows (DEV 106,389 / VAL 43,679 / TEST 55,684); any buy-back in 2.6 % of rows.
* **Lot identity is unobservable:** contracts are fungible in the export, so a buy-back's lot is a convention (cheapest-first here; FIFO/LIFO tested as sensitivity).

## 3. Exit taxonomy (a labelling, not a recovery of triggers)

Short buy-backs, share of 15,327 lots; every event keeps independent flags and an UNKNOWN class is preserved.

| # | Category | Lot share | Realised vs avg entry (₹ L) |
|---|---|---:|---:|
| 1 | Individual lot stop (quote ≥ 1.45× cheapest open entry) | 22.5 % | −64.1 |
| 2 | Same-contract partial buy-back | 5.3 % | +12.6 |
| 3 | Side-level reduction (≥2 contracts, one side, ≤10 s) | 5.7 % | +5.7 |
| 4 | Basket-level reduction (both sides) | 11.8 % | +25.3 |
| 5 | Cycle stop & liquidation | 13.8 % | +6.8 |
| 6 | Clock-based: final flatten (D0 ≥ 15:10) / Clock B without replacement | 13.1 % / 2.7 % | +44.2 / +6.9 |
| 7 | Expiry-day salvage (≤ ₹1 or ≤ 5 % of entry) | 13.5 % | +79.2 |
| 8 | Clock-B rebalance / grid rebalance | 4.9 % / 4.6 % | +11.5 / +6.8 |
| 9 | Trailing stop / target | **not assigned** — no rule found | |
| 10 | Platform / manual (AlgoId 152432, 2.18811E+15, `m_`) | 1.7 % | +2.1 |
| 11 | Unexplained | **0.6 %** | +0.1 |

Category 1's label uses a 1.45× threshold on the quote, so **its zero hazard below 1.45× is by construction**; the first-passage study (§5) is the independent test of where a stop starts.

## 4. Section 3 — are stop levels static, dynamic or trailing?

**Static in level, scope-dependent.** Lot-stop hazard per minute at fixed minute-high / cheapest-entry bins (entries above ₹25; [`stop_shape_report.txt`](results/stop_shape_report.txt)):

| Minute high ÷ cheapest entry | 1.45–1.55 | 1.55–1.7 | 1.7–2.0 | 2.0–3.0 |
|---|---:|---:|---:|---:|
| **D-1** | 1.5 % | 10.5 % | **52 %** | **75 %** |
| D0 | 2.7 % | 6.9 % | 12 % | 9 % |

The D-1 step sits between **1.55× and 1.7×**; on D0 it never becomes crisp. IV change and index do not visibly shift the curve (those two tables pool both days, so they cannot separate D-1 from D0). Younger lots stop more: at 1.7–2.0× the hazard is 28 % for lots ≤ 30 min old and 8 % for lots older than 2 h.

* **No points floor.** `entry + max(a·entry, b)` is no better than the pure ratio (best a = 0.55–0.60: precision 0.53–0.61, recall 0.58–0.61 within 2 min).
* **No trailing rule.** In-profit exits are flat in the bounce off the running low (≈1–1.7 %) and rise only gradually with drawdown from the contract's peak P&L (≈ 2 % → 5.8 % for losses > ₹20 K). No threshold.
* **Delay** from the first minute-high crossing of 1.55× to the exit: median 1 min, 75 % within 4 min, 90 % within 26 min; 9.5 % of exits had no earlier crossing.
* **Where does information come from?** AUC gain over a timing + inventory baseline, 3 chronological folds ([`t4_family_gains.csv`](results/t4_family_gains.csv) after merge, parts in [`t4_parts/`](results/t4_parts)):

| Category | Base AUC | Premium ratio | P&L | Drawdown / trailing | Spot move (ATR) | IV | Greeks | Since last trades | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Lot stop (1,398 events) | 0.669 | **+0.32** | +0.28 | +0.29 | +0.29 | +0.06 | +0.26 | +0.19 | +0.32 |
| Partial buy-back (454) | 0.738 | +0.07 | +0.01 | +0.04 | +0.07 | −0.01 | +0.02 | +0.05 | +0.13 |
| **Side-level (394)** | 0.660 | +0.20 | +0.07 | +0.20 | **+0.21** | +0.02 | +0.07 | +0.17 | +0.27 |
| Basket (960) | 0.844 | +0.04 | +0.02 | +0.02 | +0.03 | 0.00 | +0.01 | +0.04 | +0.07 |
| Clock-B rebalance (427) | 0.966 | +0.01 | 0.00 | +0.01 | +0.01 | 0.00 | 0.00 | +0.01 | +0.01 |
| Grid rebalance (322) | 0.937 | +0.01 | −0.01 | 0.00 | +0.01 | 0.00 | +0.01 | +0.01 | +0.01 |
| Clock B without replacement (185) | 0.950 | −0.01 | −0.02 | −0.10 | 0.00 | −0.01 | −0.01 | +0.02 | +0.02 |
| Expiry-day salvage (716) | 0.963 | +0.02 | +0.01 | +0.01 | +0.01 | 0.00 | +0.01 | +0.01 | +0.03 |
| Unexplained (48) | 0.922 | −0.08 | −0.21 | −0.02 | −0.20 | −0.09 | −0.04 | −0.03 | −0.47 |

Price ratio, P&L, drawdown, spot move and Greeks are proxies of the same price move, so their gains are not independent. IV adds almost nothing. Side-level exits are the group that responds to the adverse spot move (+0.21); basket exits barely do (+0.03). **Clock rebalances, Clock B without replacement and salvage are already predicted by timing and inventory alone (base AUC 0.94–0.97); no market feature adds more than +0.03.** The salvage label is price-defined (≤ ₹1 or ≤ 5 % of entry), so its predictability comes mostly from time to expiry rather than from a trigger. The unexplained class (48 events) gets worse with every added family, so nothing predicts it.

## 5. Section 4 — first-passage tests (contract level)

Per contract, the first minute whose high (or close) crosses a threshold vs each reference, compared with the actual exit's decision and first-fill times. Crossings are classed **definite / not crossed / intrabar-ambiguous** (the order inside a candle is never assumed). Two measures are kept apart: **exit-association rate** = a later buy-back of that contract (not a stop precision) and **stop-consistent rate** = the exit was not scheduled/clock-driven, its own quote was still beyond the threshold, and its size was ≤ the lots crossed.

D-1 fresh lots, minute high ÷ cheapest open entry ([`first_passage_response_curve.csv`](results/first_passage_response_curve.csv), DEV+VAL):

| k | crossings | any buy-back ≤ 1 min | ≤ 5 min | stop-consistent ≤ 1 min | ≤ 5 min |
|---|---:|---:|---:|---:|---:|
| 1.45 | 447 | 19 % | 31 % | 15 % | 27 % |
| 1.55 | 286 | 38 % | 49 % | 29 % | 41 % |
| 1.60 | 198 | 51 % | 61 % | 39 % | 54 % |
| **1.70** | 93 | **88 %** | **94 %** | 55 % | 59 % |
| 1.80 | 37 | 92 % | 95 % | 43 % | 46 % |

At 1.7×, 1-minute exit association is 0.88 / 0.88 / 0.76 on DEV / VAL / TEST (68 / 25 / 62 crossings).

* **One lot at a time.** When lots have crossed k × their own entry, the buy-back closes exactly one lot in 79–100 % of cases and never more than the crossed count; "all crossed lots" in 0–14 %.
* **Coverage is limited.** The best single threshold covers ≈ 45 % of stop-like exits on D-1 (missed-trigger rate ≈ 46–49 %), ≈ 55–63 % on D0 (missed 15–22 %). The rest happen without that threshold being crossed.
* **References tested:** own entry, cheapest open, average open, previous-session close, expiry-open, running low, running high, target vs average, portfolio MTM. For carried lots no reference gives a usable threshold: at each reference's best k the stop-consistent rate is, DEV / VAL / TEST, own cheapest entry 0.40 / 0.27 / 0.20, previous close 0.25 / 0.22 / 0.14, expiry open 0.17 / 0.16 / 0.07.
* **Cycle stop (portfolio LTP MTM).** Every minute-close crossing of −₹1.25 to −1.5 L ended in a stop (DEV 6, VAL 2, TEST 4 crossings at −₹1.25–1.3 L), so there are no false triggers at that level. But only 0–50 % of the stops are *definitely* crossed on minute closes; the rest are intrabar-ambiguous, because the trigger sits inside a minute.
* **Latency.** Trigger → decision: median upper bound ≈ 2 min (minute-resolution evidence only; the trigger time is bracketed, not known). Decision → first fill: ≈ 0.6 s for tagged orders (cycle-stop module), ≤ 14–30 s for body orders (upper bound; their decision time is stamped only to the minute). All fills of one order finish within 57 s.

## 6. Section 5 — side-level, basket and Clock-B management

**Episode dataset** ([`side_basket_episodes.csv`](results/side_basket_episodes.csv)): 3,014 buy-back episodes (2,430 unscheduled) — 23.6 % multi-strike one side, 25.6 % both sides, 50.8 % single contract; 54.6 % have a same-side sale within 60 s; 26.0 % have a same-contract sale within 60 s.

**What triggers them? UNKNOWN.** Book-minute LightGBM on 45 causal features, fitted on DEV: VAL AUC **0.87** (side-level; base-rate 3.5 %, AP 0.25) and **0.86** (basket; 2.2 %, AP 0.15), but a clock + inventory baseline already gives 0.80 / 0.85. Gains over it: spot move in ATR +0.055 (side) / +0.014 (basket), time since trades +0.055 / +0.024, side P&L +0.031 / 0.000, Greeks +0.001 / −0.020, cycle drawdown 0.000 / +0.012. Depth-3 trees on VAL: precision 0.11 / 0.05, recall 0.66 / 0.81. The strongest single signals are time-to-expiry and time since the last buy-back.

**Which contracts are closed? Partially understood.** Hit@1 on VAL (the criterion's top candidate is closed):

| Event | Random | Best criterion | Conditional logit |
|---|---:|---|---:|
| Side-level reduction | 0.47 | largest gamma / delta / vega exposure 0.77 | — |
| Basket reduction | 0.35 | largest delta exposure 0.58 | 0.58 |
| Single-contract unscheduled exit | 0.22 | largest delta exposure 0.32 | 0.30 |
| Rebalance with replacement | 0.31 | largest delta exposure 0.51 | — |

**How much?** Usually a fraction: median 20 % (side-level) / 11 % (basket) / 17 % (single) of the contract; one lot in 46 % / 56 % / 55 %; whole contract 11 % / 9 % / 11 %.

**Clock B** (D0, :14/:29/:44/:59 from 09:29; [`clock_b_selection_results.csv`](results/clock_b_selection_results.csv)):
* A tick acts in 46.5 % (DEV) / 42.3 % (VAL) of cases; why is partly predictable — LightGBM VAL AUC 0.78, depth-3 tree precision 0.77 / recall 0.55 (strongest: time to expiry, time since the last trade, theta exposure).
* It buys back **one lot** (89–99 %), then **re-sells the same lots** (99.7 %) a median **28 s** later, at a median 0 steps from ATM (|delta| 0.44 sold vs 0.27 bought back).
* Which contract: "most lots" 0.66, largest gamma / vega exposure 0.65, delta exposure 0.64 (random 0.41, VAL); conditional logit 0.52. The learned models give top-1 0.56 (LightGBM) / 0.48 (CatBoost) on TEST against a random baseline of 0.35 (59 tick-sides).

## 7. Section 6 — expiry-day stop scope and the "4 % carry-forward SL"

**D0 lots by class**, hazard of a stop-like exit per minute when the minute high is ≥ 1.5× cheapest entry ([`carried_position_results.csv`](results/carried_position_results.csv)):

| Class | Hazard | Class | Hazard |
|---|---:|---|---:|
| Carried only | 2.9 % | Mixed carried + fresh | 14.7 % |
| Fresh only | 5.4 % | Re-entered | 10.4 % |
| D-1 reference | 14.5 % | Single-lot contracts vs multi-lot | 1.9 % vs 9.7 % |

For carried lots the hazard is flat at ≈ 2–3 % per minute from 1.04× to 3× the D-1 close, against the D0 open, and against adverse spot moves up to 2 % — **no step, so no per-lot premium or spot stop for carried lots**. A depth-3 tree on conditions (age, premium, decay, TTE, spot, ATR, IV, previous-session ratio) reaches precision 0.23 / recall 0.88 on DEV and 0.16 / 0.80 on VAL: **no conditional rule accepted**.

**4 % carry-forward SL (Info.txt): UNKNOWN.** Share of carried lots bought back within 5 min of the trigger, against the base rate, on DEV / VAL / TEST:

| Interpretation | DEV | VAL | TEST |
|---|---|---|---|
| Carried premium ≥ 1.04× D-1 close | 0.09 vs 0.06 | no trigger | 0.53 vs 0.20 |
| Short book value ≥ 1.04× D-1 close value | 0.03 vs 0.03 | 0.00 vs 0.01 | 0.20 vs 0.22 |
| Carried loss ≥ 4 % of ₹2 Cr (or ₹1 Cr) | never triggers | never | never |
| D0 loss ≥ 4 % of \|MTM at D-1 close\| | 0.12 vs 0.08 | 0.00 vs 0.03 | 0.34 vs 0.22 |
| Spot move ≥ 4 % since D-1 close | never triggers | never | never |
| D0 drawdown ≥ 4 % of premium collected | 0.18 vs 0.07 | 0.00 vs 0.02 | 0.36 vs 0.07 |

No reading separates trigger from non-trigger cases on all three splits; each fails VAL. The 1 % expiry-day reading (₹2 L at ₹2 Cr) is not observed either: the cycle stop fires at ≈ −₹1.3 L, on D-1 as well.

## 8. Section 7 — machine-learning reconstruction (TEST scored once; thresholds chosen on VAL)

Logistic baseline, LightGBM, CatBoost, depth-3 tree and discrete-time hazard model (where a duration exists), plus a multi-class controller. Whole-cycle chronological split, no cross-cycle features, action columns excluded from features (unit-tested). Full table: [`exit_model_metrics.csv`](results/exit_model_metrics.csv); rules: [`exit_model_trees.txt`](results/exit_model_trees.txt).

| Model | TEST events (base rate) | LightGBM P / R | CatBoost P / R | AP (LGBM / Cat) | Quantity agreement |
|---|---|---|---|---|---|
| 1 Lot stop | 339 (0.6 %) | 0.27 / 0.68 | 0.37 / 0.52 | 0.41 / 0.44 | 0.59 |
| 1b Any unscheduled buy-back (label-free) | 788 (1.4 %) | 0.22 / 0.44 | 0.33 / 0.33 | 0.26 / 0.28 | — |
| 2 Side-level reduction | 122 (1.3 %) | 0.21 / 0.40 | 0.22 / 0.39 | 0.21 / 0.22 | — |
| 3 Basket reduction | 72 (1.5 %) | 0.19 / 0.28 | 0.14 / 0.38 | 0.14 / 0.17 | — |
| 4 Clock-B contract (candidates) | 165 (29 %) | 0.62 / 0.54 | 0.56 / 0.63 | 0.62 / 0.64 | — |
| 5 D0 carried-position exit | 228 (1.7 %) | 0.38 / 0.25 | 0.32 / 0.32 | 0.25 / 0.31 | — |
| 6 Salvage | 153 (0.6 %) | 0.18 / 0.74 | 0.12 / 0.80 | 0.26 / 0.23 | — |
| 6b Profit-taking (D0, in profit) | 227 (0.9 %) | 0.14 / 0.24 | 0.20 / 0.22 | 0.11 / 0.13 | — |
| 7 Re-entry after a buy-back | 192 (44 %) | 0.64 / 0.67 | 0.67 / 0.63 | 0.73 / 0.74 | — |
| 8 Final liquidation | **15** (12.5 %) | 0.75 / 1.00 | 0.75 / 1.00 | 0.84 / 0.82 | — |
| 0 Multi-class (contract-minute) | macro-F1 0.17 (TEST), 0.18 (VAL) | | | | |

* **No model reaches 80 % precision and recall** on VAL or TEST. The only "80/80" flag in the table is the trivial "no exit" class of the multi-class model.
* Final liquidation scores 0.75 / 1.00 on only 15 TEST events (inadequate coverage) and still misses 0.80 precision.
* Re-entry (0.64–0.67 against a 44 % base rate) and Clock-B contract choice are the only classes with a clear lift, and both are well below target.
* Calibration is good for the rare-event models (ECE ≤ 0.015) because they rarely fire; that is not discrimination.
* **Rule learning vs correlation:** the models rank mainly on time-to-expiry, time since the last trade, price ratio and exposure size. On the rare-event classes the depth-3 trees have TEST precision 0.04–0.25, and the hazard models are the weakest. None recovers a rule.

## 9. Section 8 — autonomous portfolio replay (three fill assumptions; main table below is minute-open fills, [`autonomous_replay_metrics_open.csv`](results/autonomous_replay_metrics_open.csv))

The replay keeps its own book and decides hold / partial buy-back / full exit / wing release / re-entry / final liquidation / cycle liquidation itself, without actual future orders or inventory, and abstains outside the DEV feature support. **Mode A:** actual base entries arrive at their own times, exits are the replay's. **Mode B:** fully autonomous, entries come from the decoded clone ladder. Exit match = same contract within ±2 minutes.

| Mode · policy | Split | Exit-match precision | recall | Qty agreement | P&L corr (cycles) | Replay vs actual P&L (₹ L) |
|---|---|---:|---:|---:|---:|---|
| A · ML controller | DEV | 0.46 | 0.20 | 0.46 | 0.53 | 2.5 vs 6.7 |
| A · ML controller | VAL | 0.39 | 0.25 | 0.36 | 0.95 | 11.3 vs 12.4 |
| **A · ML controller** | **TEST** | **0.40** | **0.24** | **0.51** | **0.87** | **4.6 vs 7.5** |
| A · decoded-rule clone | TEST | 0.63 | 0.18 | 0.31 | 0.73 | 1.5 vs 7.5 |
| A · hold only | TEST | 0.42 | 0.05 | 0.14 | 0.35 | −0.7 vs 7.5 |
| B · ML controller | DEV | 0.43 | 0.08 | 0.55 | 0.33 | 8.8 vs 6.7 |
| B · ML controller | VAL | 0.45 | 0.11 | 0.49 | −0.07 | 4.9 vs 12.4 |
| **B · ML controller** | **TEST** | **0.37** | **0.12** | **0.65** | **0.59** | **−3.5 vs 7.5** |
| B · decoded-rule clone | TEST | 0.57 | 0.09 | 0.15 | 0.51 | −0.8 vs 7.5 |

* Replay matches **a fifth to a quarter** of actual exits in Mode A and about **one in nine** in Mode B; precision stays at 0.37–0.40 for the ML controller.
* Mode A's high P&L correlation comes largely from the actual entries it is given. Mode B (nothing actual) is not even stable in sign on VAL (−0.07).
* TEST relative position divergence (|replay − actual| lots ÷ actual lots): 2.4 (A) and 6.4 (B), against 5.0 and 27.6 for hold-only. Values above 1 mean the positions differ by more than their own size.
* Abstention: 1–11 % of decisions.
* Teacher-forced replay (actual orders fed in) reproduces the panel features and cash-flow P&L; that validates the accounting, **not** any decision model.
**Execution and cost stress** (TEST, ML controller; minute-open = buys and sells at the minute's open, delay = next minute's open, adverse = buys at the minute high and sells at the minute low; [`autonomous_replay_metrics_*.csv`](results)):

| Mode | Fills | Exit-match precision | recall | P&L corr | Replay P&L (₹ L) | Net after conservative / adverse costs (₹ L) | Actual P&L / net conservative / net adverse (₹ L) |
|---|---|---:|---:|---:|---:|---|---|
| A | minute-open | 0.40 | 0.24 | 0.87 | +4.6 | +0.9 / −1.1 | +7.5 / +4.3 / +2.3 |
| A | one-minute delay | 0.40 | 0.22 | 0.85 | +5.7 | +2.0 / +0.1 | same |
| A | **adverse** | 0.47 | 0.16 | 0.85 | **−10.3** | −12.8 / −14.0 | same |
| B | minute-open | 0.37 | 0.12 | 0.59 | −3.5 | −4.6 / −5.1 | same |
| B | one-minute delay | 0.36 | 0.12 | 0.63 | −3.5 | −4.6 / −5.1 | same |
| B | **adverse** | 0.38 | 0.12 | 0.68 | **−6.1** | −7.1 / −7.7 | same |

* **Which exits match is almost insensitive to execution** (precision 0.36–0.47, recall 0.12–0.24 under all three fill assumptions), so the low fidelity is a decision problem, not a fill problem.
* **The money is very sensitive**: adverse fills cost the Mode-A controller about ₹15 L over 9 TEST cycles, because it buys back and re-sells many small lots. The actual book stays positive under the same cost scenarios (+₹4.3 L conservative, +₹2.3 L adverse), so the replay's trading pattern is not equivalent to the original.
* The conservative and adverse cost scenarios are the fixed turnover / per-order / per-unit schedules used in the earlier study, not verified broker charges.

## 10. Section 9 — validation and robustness ([`robustness_results.csv`](results/robustness_results.csv))

Headline models only (lot stop, label-free exit, D0 carried exit, salvage). The tables below show LightGBM; the CatBoost and logistic rows are in the CSV. Thresholds fixed on VAL and never re-tuned. No result is a pass of the 80 % standard.

**Cycle-level bootstrap, 90 % interval, resampling the TEST cycles (2,000 draws)**

| Model | Precision | Recall | Average precision | Cycles |
|---|---|---|---|---:|
| Lot stop | 0.25 – 0.30 | 0.63 – 0.74 | 0.37 – 0.49 | 9 |
| Label-free unscheduled buy-back | 0.21 – 0.24 | 0.42 – 0.47 | 0.24 – 0.30 | 9 |
| D0 carried-position exit | 0.25 – 0.50 | 0.19 – 0.33 | 0.18 – 0.31 | 7 |
| Salvage | 0.14 – 0.21 | 0.59 – 0.81 | 0.21 – 0.30 | 7 |

**Segments, lot-stop model on TEST (LightGBM precision / recall)**

| Segment | Events | Precision | Recall |
|---|---:|---:|---:|
| All | 339 | 0.27 | 0.68 |
| NIFTY / SENSEX | 71 / 268 | 0.30 / 0.26 | 0.66 / 0.68 |
| **D-1** | 127 | **0.34** | **0.84** |
| D0 | 212 | 0.23 | 0.58 |
| Fresh / carried contracts | 240 / 99 | 0.28 / 0.24 | 0.71 / 0.60 |
| Trend / sideways sessions | 122 / 217 | 0.28 / 0.26 | 0.66 / 0.68 |
| High-vol cycles / low-vol cycles | 326 / **13** | 0.26 / (0.41) | 0.67 / (0.92) |

D-1 has high recall (0.84) with low precision (0.34): the model over-fires where the stop is crisp. Most TEST cycles are high-volatility (the split uses the DEV median), so the low-volatility column has 13 events and means nothing. The label-free exit model shows the same pattern (D-1 0.33 / 0.49, D0 0.18 / 0.42).

**Feature ablation (LightGBM, refit on DEV without one family; average precision on TEST, full model 0.39)**

| Removed | Lot stop (VAL / TEST) | Label-free (VAL / TEST) |
|---|---|---|
| Premium ratio | 0.22 / **0.27** | 0.23 / 0.24 |
| Spot move / ATR / RV | 0.23 / **0.33** | 0.21 / 0.22 |
| P&L / drawdown | 0.34 / 0.36 | 0.24 / 0.25 |
| Greeks / IV | 0.36 / 0.36 | 0.26 / 0.26 |
| Inventory / concentration | 0.35 / 0.36 | 0.25 / 0.26 |
| Timing since trades / age | 0.33 / 0.37 | 0.23 / 0.24 |
| Clock / calendar | 0.31 / 0.40 | 0.21 / 0.25 |

The lot-stop model depends on the price ratio and the spot move; removing Greeks, IV, inventory, timing or clock costs nothing on TEST. That is the same price-move signal as everywhere else, not a hidden extra rule.

**Missing-data and incomplete-chain stress** (TEST; option bars removed, book-state features rebuilt from the damaged bars; stored models scored at their VAL thresholds). LightGBM lot stop, baseline 0.27 / 0.68:

| Damage | Precision | Recall | AP |
|---|---:|---:|---:|
| 10 % of bars at random | 0.26 | 0.60 | 0.37 |
| 25 % of bars at random | 0.26 | 0.50 | 0.33 |
| 10 % of 15-minute blocks | 0.26 | 0.61 | 0.37 |

Precision does not move; recall falls by 8–18 points. The model degrades gracefully, which is a property of a weak, price-driven classifier and not evidence that it has the right rule. The logistic baseline stays at precision ≈ 0.11.

**Other robustness checks, and where they are:** execution and transaction-cost stress is in the replay (§9); per-index, D-1 vs D0 and fresh vs carried splits are above; the chronological split is DEV 18 / VAL 8 / TEST 9 whole cycles with no cross-cycle features. TEST was scored once and not used to choose any threshold or hyperparameter here.

## 11. Verified, inferred and unresolved

**Verified (observed in this sample)**
* Orders are one column-163 tag each; the colour of an order's module is in its tag prefix.
* Orders are marketable limits at LTP × 1.15 / × 0.85; the algo's quote is recoverable.
* A cycle stop fires on cumulative LTP-MTM of about −₹1.3 L (D-1 and D0), ends the cycle, with 1–20 s check latency.
* A per-lot price stop exists on D-1: a contract whose minute high crosses ≈ 1.7× its cheapest open entry is bought back within a minute 88 % of the time (0.88 / 0.88 / 0.76 DEV / VAL / TEST); it closes **one lot at a time**.
* Clock B acts on 42–47 % of D0 ticks: one lot bought back, the same lot re-sold at ATM ≈ 28 s later.
* Carried lots show no per-lot premium or spot stop.
* No trailing stop, no points floor, no indicator-based exit is visible.

**Inferred (consistent with the data, not validated)**
* The ≈ 1.6–1.7× level is a per-allocation stop on a contract's own price; its reference (own lot, cheapest, quote vs minute high) is not identified.
* Side-level reductions respond to adverse spot moves (+0.21 AUC at the contract-minute level), as a proxy for price against the shorts.
* Contract choice in reductions follows exposure size (largest gamma / delta / vega, most lots).

**UNKNOWN**
* The exact stop constant, its reference price, and why it is crisp on D-1 and weak on D0.
* Triggers of side-level, basket and partial reductions; whether a Clock-B tick acts; which contract Clock B picks; the re-entry trigger.
* The meaning of the 4 % carry stop and the 1 % expiry-day stop; the origin of the −₹1.3 L constant.
* Quantity in reductions beyond "usually a fraction"; wing-release quantity; lump hedge size.
* Anything that needs decision logs, allocation ids or order lifecycle records.

## 12. The four conclusions, kept separate

| Question | Answer |
|---|---|
| **Individual exit-rule reconstruction** | **Partial.** A D-1 per-lot stop near 1.6–1.7× and the cycle stop are real and approximately located. Neither is exact: the stop covers ≈ 45 % of stop-like exits, D0 scope is unknown, and the cycle-stop constant is bracketed, not derived. |
| **Full exit-controller reconstruction** | **No.** No exit class reaches 80 % precision and 80 % recall on VAL or TEST; best TEST results are lot stop 0.27–0.37 / 0.52–0.68, side-level 0.21 / 0.40, basket 0.19 / 0.28, re-entry 0.64–0.67 / 0.63–0.67. |
| **Portfolio replay fidelity** | **Low.** TEST exit match 0.36–0.47 precision and 0.12–0.24 recall under every fill assumption (0.40 / 0.24 with actual entries, 0.37 / 0.12 fully autonomous at minute-open fills). P&L is very sensitive to fills (Mode A: +₹4.6 L at minute-open, −₹10.3 L adverse; actual +₹7.5 L). |
| **Economic profitability** | **Not assessed here** and not implied. The replay's P&L is a diagnostic of fidelity; earlier work finds no demonstrated alpha. |

A strong result in one row is not evidence for another.

## 13. Files

Results: `results/` — `robustness_results.csv`, `first_passage_*.csv`, `side_basket_*.csv`, `clock_b_selection_results.csv`, `carried_position_results.csv`, `newest_ref_results.csv`, `exit_model_metrics.csv`, `autonomous_replay_*_{open,adverse,delay1}.csv`, `order_key_audit.*`, `legacy_oid_audit*.{csv,txt}`, `stop_shape_report.txt`, `carry_stop_report.txt`, `triggers_t123_report.txt`, `t4_parts/`. Code: `common.py`, `ledger.py`, `taxonomy.py`, `bookstate.py`, `first_passage.py`, `side_basket.py`, `clock_b.py`, `carried.py`, `models.py`, `replay.py`, `robustness.py`, `run_all.py`, `run_split.py`, `tests/`.
