# Take-profit research methodology (Stage 3 design; nothing below has been run)

## 1. Question and hypotheses

**Question.** Does Algo 8 buy back short options because they have reached a profit level, as opposed to the clock,
the expiry, a reduction or a stop?

* **H_TP (to be falsified):** a rule of the form "buy back a short lot (or allocation) when its price ≤ (1 − x) × reference,
  or ≤ ₹a" causes a material share of the unscheduled profitable buy-backs.
* **H0:** profitable buy-backs are explained by premium decay toward expiry together with the scheduled, clock,
  reduction and liquidation mechanisms. The exit hazard does not step at any profit level.

A cluster of exit prices near some fraction of entry is **not** evidence of H_TP by itself. On D0 every short decays
toward zero, so profitable exits must cluster at low ratios whatever the exit trigger is.

## 2. What earlier work already found (to be re-checked, not assumed)

| Source | Finding | Caveat |
|---|---|---|
| EXT-06 (PR #3) | Target and drop-from-running-high references fail out of sample (VAL stop-consistent 0.00–0.08); no trailing rule | Tested as stop-style references, not as a dedicated TP study |
| ML-03 class 6b (PR #3) | D0 in-profit unscheduled exit model: TEST P / R 0.14 / 0.24 (LightGBM), 0.20 / 0.22 (CatBoost) | A model result, not a rule test |
| `FINDINGS.md` L276 | D0 profit-target fraction / absolute price: "mixed 0.05×–2.5×, no cluster" | Predates the column-163 ledger |
| `FINDINGS.md` L150 | At Clock-B ticks, profit-target conditions ≤ 10 % precision at every threshold | Lot identity unobservable |
| Lineage X `ALGO8_RULEBOOK.md` X5 | Profit-taking / trailing unresolved; "do not invent a take-profit percentage" | — |

The prior is therefore **against** a simple TP rule. Stage 3 is a dedicated, pre-registered test of it.

## 3. Descriptive starting point (Stage 1 audit, executed)

Share of closed short lots bought back below their **assigned** entry ([`results/stage1_short_exit_segments.csv`](results/stage1_short_exit_segments.csv)):

| Segment | Lots | Cheapest-first | FIFO | LIFO |
|---|---:|---:|---:|---:|
| D-1 entry, D-1 exit | 1,442 | 14.8 % | 24.8 % | 15.4 % |
| D-1 entry carried, D0 exit | 3,011 | 62.8 % | 64.6 % | 63.2 % |
| D0 entry, D0 exit | 10,845 | 46.0 % | 56.1 % | 46.2 % |

Two consequences for the design:

1. **The ownership convention changes the answer.** Cheapest-first assigns the lowest entry to each buy-back, which
   mechanically makes exits look less profitable. So results must be reported per convention, together with a
   convention-free contract-average reference and the PR #5 slot / chain allocations.
2. **The existing labels carry built-in profit signs.** The lot-stop label requires quote ≥ 1.45 × cheapest entry, so 0 %
   of its lots are profitable by construction. Salvage (≤ ₹1 or ≤ 5 % of entry) is profitable by construction
   ([`results/stage1_short_exits_by_existing_label_cheap.csv`](results/stage1_short_exits_by_existing_label_cheap.csv)).
   Labels can only be used to remove mechanisms from the TP population, never as evidence for one.

## 4. Populations and accounting

* **Primary population:** short lots opened by the body module (sign −1, numeric tag), 14,744 closed unit lots.
  Non-body shorts (554 lots) and long hedges (16,788 lots) are analysed separately. Wing sales are hedge releases, not TP.
* **Ownership:** cheapest-first, FIFO, LIFO (lot ledgers), contract average (convention-free), slot and chain
  allocations (PR #5). Every result is reported per ownership model; none is pooled.
* **Realised P&L per lot** = (entry fill − exit fill) × lot size, from the actual fill prices.
  **Return on entry premium** = 1 − exit ÷ entry. Lots still open at the end of the export (110 short) settle at
  intrinsic value from the last index close (flagged).
* **Costs:** applied per order from a cost model the user selects (question Q1). Gross and net are always shown side by side.
* **Fills:** realised exits use actual fills, so execution is already in them. Counterfactual TP exits (§6, T5) use the
  three fill models (`open`, `delay1`, `adverse`).

## 5. Exit categories

Mechanism is labelled first, using the PR #3 taxonomy precedence. Profit or loss is then a second, independent dimension,
so every table is a mechanism × outcome cross-tab.

| Requested category | Built from (PR #3 labels) |
|---|---|
| Stop-losses | 1 individual lot stop |
| Side and basket reductions | 3 side-level, 4 basket-level |
| Clock-B rebalances | 8 Clock-B rebalance, 6 Clock B without replacement, 8b grid rebalance |
| Expiry-day liquidation | 6 final flatten, 7 expiry-day salvage (**see Q3**) |
| Cycle-level liquidation | 5 cycle stop & liquidation |
| **Profitable discretionary exits** (the TP candidates) | 2 same-contract partial and 11 unexplained with exit < reference; plus any side / basket / clock exit with exit < reference reported **separately** as "profitable, other mechanism" |
| Other / unresolved | 10 platform / manual; remaining 11 unexplained |

## 6. Tests (pre-registered)

**T1 — Distributions.** Return on entry premium and ₹ P&L per category × segment (D-1 fresh, D0 carried, D0 fresh) ×
ownership model × underlying, with cycle-bootstrap 95 % CIs (resampling whole cycles) and sample sizes.

**T2 — Clustering against nulls.** For the profitable discretionary population, compare the exit-ratio density with:
(a) a **holding-period null**: the ratio at random eligible minutes of the same lot's own holding period;
(b) a **time-shifted null**: same clock time and segment in other cycles;
(c) an **occupancy null**: the ratios the price path visited while the lot was open.
A TP rule predicts excess mass just past a threshold relative to all three. Clustering alone is never sufficient.

**T3 — Downside first-passage response curve (the discriminating test).** This mirrors the stop study that found the
D-1 step between 1.55× and 1.7×. For each open short lot and threshold, take the first minute whose **low** reaches
≤ (1 − x) × reference (also on the close, as a stricter variant). Measure the share of crossings followed by a buy-back of
that contract within 1 and 5 minutes, and divide it by a matched baseline hazard (same segment, time-of-day bin,
lot-age bin, no crossing). A TP rule predicts a sharp rise in this lift at its threshold; decay alone predicts a smooth curve.
Intrabar ambiguity is reported, never resolved by assumption.

Bounded grid (**360 cells**, to be approved, Q7):

| Factor | Values | Count |
|---|---|---:|
| Relative threshold x (profit as a share of entry) | 0.10, 0.20, …, 0.90 | 9 |
| Reference | own entry (cheapest, FIFO, LIFO), contract average | 4 |
| Segment | D-1 fresh, D0 carried, D0 fresh | 3 |
| Response window | 1 min, 5 min | 2 |
| Relative subtotal | 9 × 4 × 3 × 2 | **216** |
| Absolute premium level a (₹) | 0.5, 1, 2, 3, 5, 10 | 6 |
| Absolute subtotal | 6 × 4 × 3 × 2 | **144** |

Selection: the best cell per segment is chosen on **DEV only**, by a pre-stated criterion (maximum lift with ≥ 30
crossings and ≥ 5 cycles). It is confirmed on VAL, and TEST is scored once. Multiple testing: Holm and BH across all
360 cells, plus a best-of-N permutation null (exit times shifted within contract-day, 1,000 draws) for the selected lift.

**T4 — What profit-taking depends on.** Discrete-time hazard (logistic) for a profitable discretionary exit among in-profit
lot-minutes. Covariates: time of day and minutes to close, causal volatility (ATR / RV from PR #6), CE / PE, strike
distance (steps and bp), signed spot move since entry (in ATR), lot age, current return on entry. Fit on DEV, evaluate on
VAL and TEST, and compare with a time-to-expiry-only baseline. Coefficients get cycle-bootstrap CIs. This is a
descriptive model, not an ML controller.

**T5 — Counterfactual economics (interpretation only).** Only rules that pass T3 on DEV and VAL are applied to the
actual lots: same entries, TP exit at the first crossing under the three fill models, with costs. P&L is compared with the
actual result. Nothing is selected on this result.

## 7. Alternative explanations each test must rule out

Decay toward expiry · clock coincidence (Clock B, grid A, 15:14) · reductions that happen to follow favourable moves ·
Clock-B choosing the contract with the most lots · ATM drift leaving old strikes far OTM and cheap · the salvage
definition · ownership-convention artefacts · cycle-stop liquidations of in-profit lots.

## 8. Decision standard (to be approved, Q8)

| Verdict | Requirement |
|---|---|
| **TP rule identified** | One rule reaches ≥ 0.80 precision and recall on VAL and TEST (the standard used for stops) |
| **TP mechanism supported** | Lift step reproduced on DEV, VAL and TEST, cycle-bootstrap CI excluding 1, surviving the best-of-N permutation null at 5 % and Holm correction |
| **Not identified** | Otherwise. The class stays UNKNOWN |

All 35 cycles have been inspected before, so even a supported mechanism is exploratory until it is tested on new data.
