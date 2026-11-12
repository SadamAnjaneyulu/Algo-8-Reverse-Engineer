# Stage 2 · Milestone 2 report: targets, baselines, validation design

**Verdict: PASS, with one late-found data defect disclosed (§9).**
Targets, validation and the five baselines are built, tested and reproducible. No alpha family was tested, no model was
trained, no parameter was searched. **Everything is exploratory and in-sample: all 85 dates were inspected before.**
Milestone 3 has not started and waits for your review.

## 1. Result in five lines

| # | Finding | Read it as |
|---|---|---|
| 1 | **Momentum baseline has no skill** at 15 / 30 / 60 min: rank IC −0.005 / +0.014 / +0.014, all CIs include 0, permutation p 0.83 / 0.67 / 0.77, hit rate 0.476 / 0.493 / 0.508 | The bar for family B/C is zero edge, not a positive one |
| 2 | **Index drifted down in this sample**: mean return −0.54 / −1.15 / −2.54 bp per 15 / 30 / 60 min (CI excludes 0) | Any "short" signal looks good unless compared with this drift (BL1) |
| 3 | **Volatility persistence is the only strong structure**: rank IC with future RV 0.63 / 0.65 / 0.63 and with future range 0.49 / 0.43 / 0.38; permutation p = 0.0005 (the minimum attainable), Holm 0.0045 | Real but expected (volatility clusters). It ranks well, it is badly calibrated: MSE skill vs the train mean is positive only for RV at 15 min |
| 4 | **Time of day** adds nothing for direction; a small volatility effect at 15 min only (RV skill +0.028, CI [0.006, 0.053] on validation + test) | Not a stable baseline at 30 / 60 min |
| 5 | **Option cost scenarios cannot be applied to an index-only prediction**; one-lot ATM straddle round trip at the median D-1 premium costs 1.3–3.1 % of premium | Predictive and tradable results stay separate (D6) |

## 2. Locked decisions (your authorisation)

| # | Decision | Where it is enforced |
|---|---|---|
| D1 | Horizons 15, 30, 60 min; 5 min is sensitivity only | `configs/stage2.yaml` (`targets`), test `test_locked_decisions` |
| D2 | Entry reference = open of the decision bar | `targets/targets.py`, `test_entry_is_decision_bar_open` |
| D3 | Folds 43 / 22 / 20 dates plus a four-block expanding stability check | `validation/splits.py` |
| D4 | D0 options reported separately; verdict capped at INCONCLUSIVE | `m2_straddle_baselines.csv` (`max_verdict`) |
| D5 | The four `alpha_freeze` cost scenarios, definitions unchanged | `validation/costs.py` imports `analysis/engine.py::COSTS`; `test_costs_unchanged` |
| D6 | Index predictiveness evaluated on index data; tradability unresolved | no strategy P&L is computed anywhere |

## 3. Exact target definitions and indexing

Session bars k = 0 … 374 (bar k starts at 09:15 + k minutes). Decision bar index **kd**; the decision is taken at the
start of bar kd, so features use completed bars ≤ kd−1 (PR #6 key `m`, bars starting ≤ m−1). Label bars are kd … kd+h−1.
A label is valid only if **kd + h ≤ 375**, so no label crosses the close. Prices: O, H, L, C of the 1-minute bar.

| Target | Formula | Note |
|---|---|---|
| Return *r* | 10⁴ · ln( C[kd+h−1] / O[kd] ) | entry at the open of the decision bar: no gap from C[kd−1] is included |
| Realised vol *RV* | 10⁴ · √( ln(C[kd]/O[kd])² + Σ_{k=kd+1..kd+h−1} ln(C[k]/C[k−1])² ) | first increment is measured from the entry open, so the window contains no overnight-style gap |
| Range *RG* | 10⁴ · ( max H − min L over kd … kd+h−1 ) / O[kd] | |
| Range expansion *REX* | ( max H − min L over label ) / ( max H − min L over bars kd−h … kd−1 ) | needs kd ≥ h; mechanically related to RG |
| Reversal | 1 if sign(*r*) ≠ sign(trailing return), both non-zero | dead band 0, **not locked** (open item) |
| Straddle change | 100 · ( P_out / P_in − 1 ), P_in = open(CE)+open(PE) at bar kd, P_out = close(CE)+close(PE) at bar kd+h−1, ATM strike fixed at the decision minute | D-1 and D0 reported separately |

Missing-bar rule: any missing bar inside a label window sets all targets of that window to NaN (16 five-minute rows).

**Look-ahead check (proved by tests, not only argued).** Trailing predictors use C[kd−1−h … kd−1] and H/L of bars kd−h … kd−1.
Every label bar index is ≥ kd, so the two windows share no bar. The entry price O[kd] is the first price after the
last feature bar, so there is no one-minute look-ahead and no unintended gap.

## 4. Sample, grid and purging

Non-overlapping decision grid kd = h + 1 + phase + j·h (the +1 guarantees a full trailing window; label windows are
disjoint inside a session). Observations are never shuffled.

| Horizon | Obs on grid | Removed by purging | TRAIN / VAL / TEST obs | Dates (clusters) TRAIN / VAL / TEST | Decisions per session |
|---|---:|---:|---|---|---:|
| 15 min | 3,910 | 54,740 | 1,978 / 1,012 / 920 | 43 / 22 / 20 | 23 |
| 30 min | 1,870 | 51,680 | 946 / 484 / 440 | 43 / 22 / 20 | 11 |
| 60 min | 850 | 42,500 | 430 / 220 / 200 | 43 / 22 / 20 | 5 |
| 5 min (sensitivity) | 12,410 (12,394 complete) | 49,640 | 6,278 / 3,212 / 2,904 | 43 / 22 / 20 | 73 |

"Removed" = candidate decisions (all 375 − h + 1 starts per session, both indices) that overlap a kept window. Independent date clusters: **85**
(NIFTY and SENSEX share a date and stay in the same cluster, correlation 0.95), so the effective sample is far smaller than the row counts.

## 5. Validation methodology

| Item | Rule |
|---|---|
| Primary folds | TRAIN 22 Jun – 20 Aug 2026 (43 dates) · VAL 21 Aug – 22 Sep (22) · TEST 23 Sep – 22 Oct (20). Chronological, by date |
| Stability | 4 contiguous blocks (22 / 21 / 21 / 21 dates: 22 Jun–22 Jul, 23 Jul–20 Aug, 21 Aug–21 Sep, 22 Sep–22 Oct), expanding fit on blocks 1…k, evaluated on block k+1 for k = 1…3; non-fitted baselines are shown on all four blocks |
| Fitted baselines | Only BL1 (mean) and BL2 (30-minute bucket means) are fitted, on TRAIN only, both indices pooled; skill is measured out of fit on VAL, TEST and VAL+TEST |
| Intervals | Date-cluster bootstrap, 2,000 resamples, 95 %; whole dates resampled (both indices together). Sensitivity: blocks of 5 consecutive dates |
| Null / multiple testing | Date-permutation null (2,000 permutations; the date mapping is shared across indices); the smallest attainable p is 1/2001 ≈ 0.0005. Holm and Benjamini–Hochberg over the 9 registered baseline tests of this milestone |
| Phase sensitivity | The whole evaluation repeated for every grid phase (15, 30, 60 phases) |
| Not claimed | No external validation; no untouched holdout; no claim that in-sample numbers generalise |

## 6. Baselines

| # | Baseline | Definition | Evaluated by |
|---|---|---|---|
| BL1 | No signal | Mean of the target (zero for direction) | Mean with CI; train-mean vs zero skill |
| BL2 | Time of day | Mean target by 30-minute bucket, fitted on TRAIN | Skill vs BL1 / zero (1 − MSE ratio) |
| BL3 | Momentum | Trailing h-minute log return (PR #6 `ret_{h}m_bp`) as the forecast of *r* | IC, rank IC, hit rate, signed mean return |
| BL4 | Mean reversion | Negative of BL3 (the same test read from the other side; counted once in the multiple-testing family) | Sign-flipped BL3 |
| BL5 | Volatility only | Trailing RV over the previous h minutes → RV; trailing range → RG | Rank IC, MSE skill vs BL1 / BL2 |

Full per-scope tables (combined, NIFTY, SENSEX; ALL / TRAIN / VAL / TEST / VAL+TEST): `results/m2_baseline_metrics.csv`.

## 7. Evidence (all dates inspected before; exploratory)

**Momentum (BL3, combined, ALL).**

| h | Rank IC [95 % CI] | Hit rate | NIFTY / SENSEX rank IC | Permutation p (Holm) |
|---|---|---|---|---|
| 15 | −0.005 [−0.050, 0.043] | 0.476 [0.456, 0.496] | −0.002 / −0.007 | 0.83 (1.0) |
| 30 | +0.014 [−0.054, 0.086] | 0.493 [0.466, 0.522] | +0.015 / +0.012 | 0.67 (1.0) |
| 60 | +0.014 [−0.093, 0.123] | 0.508 [0.462, 0.558] | +0.022 / +0.006 | 0.77 (1.0) |

Four-block rank IC (h = 15): −0.027, −0.003, −0.053, +0.059; (h = 30): −0.010, −0.088, +0.059, +0.074; (h = 60): −0.028, +0.003, −0.059, +0.070. The sign flips between blocks: no stable direction. The later blocks are positive, which is only an observation, not a finding.
Phase sensitivity (rank IC, 15 / 30 / 60 min): ranges −0.037…0.003, −0.007…0.058, −0.054…0.134. The primary phase sits inside the range; the 60-minute range shows how little 5 observations per session pin down.

**Volatility persistence (BL5).** Rank IC stays positive in every block (RV 0.37–0.65, RG 0.19–0.49) and across indices. MSE skill is not: on VAL+TEST RV +0.25 [0.01, 0.42] at 15 min, +0.09 [−0.32, 0.37] at 30, −0.12 [−0.74, 0.31] at 60; range −0.57…+0.02 (negative at 60 min). Ranking works; the raw trailing level is a poorly calibrated forecast. A family-A model must beat a *recalibrated* persistence baseline, which Milestone 3 will have to register first.

**Time of day (BL2).** Direction skill vs zero ≈ 0 (−0.004…+0.008). Volatility skill is positive at 15 min (RV 0.028, RG 0.030 on VAL+TEST) and non-positive at 30 / 60 min. Block 1 cannot be scored (nothing to fit on).

**Isolated straddle baselines (`m2_straddle_baselines.csv`).** D-1: mean premium change −0.10 % (15 min), +0.18 % (30), +0.22 % (60), all CIs include 0; time-of-day skill is negative. D0: reported separately, flagged **INCONCLUSIVE by decision D4** (selection-biased sample; target available for only 89 % of grid decisions, 33–34 of 35 dates).

## 8. Costs (D5): what applies

| Scenario | Premium turnover | ₹ per order | ₹ per unit | Index-only prediction | One-lot ATM straddle round trip, % of premium (NIFTY / SENSEX, median D-1 premium 155.1 / 539.4 pts) |
|---|---:|---:|---:|---|---|
| zero | 0 | 0 | 0 | trivially | 0 / 0 |
| moderate | 0.25 % | 20 | 0.05 | **no** | 1.42 % / 1.28 % |
| conservative | 0.50 % | 20 | 0.10 | **no** | 2.05 % / 1.82 % |
| adverse | 0.50 % | 40 | 0.20 | **no** | 3.10 % / 2.63 % |

Why not: an index level has no premium turnover, no parent order and no traded unit, so the three non-zero scenarios have nothing to act on. They apply only to option trades (4 orders, 4 × lot units, turnover 2 × premium × lot). Cost definitions are unchanged (verified by test).

## 9. Late-found data defect (not in the Milestone 1 audit)

While checking why the 5-minute momentum Pearson IC was −0.30, I found that on **every NIFTY and SENSEX session from 3 Aug to 9 Oct 2026 (48 + 48)** the bars from about 15:15–15:17 to 15:19 are flat carried prices and the 15:20 bar jumps to the real level. On 12–22 Oct (8 dates) the same minutes are missing (Milestone 1 check B5). June and July are clean. Cause: not established.

| Effect | Size |
|---|---|
| Primary grid (phase 0) observations whose label window reaches a stale bar | 11 of 3,910 / 1,870 / 850 |
| Primary result with those rows removed | momentum rank IC −0.0044 / +0.0143 / +0.0185 (vs −0.0046 / +0.0138 / +0.0138); mean return −0.54 / −1.17 / −2.65 bp (vs −0.54 / −1.15 / −2.54): **no conclusion changes** |
| 5-minute sensitivity | 235 of 12,410 rows touch the stale zone; Pearson IC −0.298 → **−0.012** when removed (rank IC −0.052 → −0.042). **The 5-minute Pearson IC was an artefact; ignore it** |
| Other phases at 15 / 30 / 60 min | 1,578 rows per horizon (all phases together) touch it; ranges barely move (§7) |
| Option bars | **Not checked** for the same defect |

I did not change any locked definition. The primary numbers above stay as locked; the exclusion is reported as a sensitivity (`results/m2_closing_zone_*.csv`, `audit/closing_zone_check.py`, register row DAT-15). The decision "exclude every window reaching 15:15 or later in Milestone 3" is yours (open item 5).

## 10. Tests

| Suite | Result |
|---|---|
| New `tests/test_milestone2.py` | 34 passed (locked decisions; brute-force target formulas; entry open, no gap, no look-ahead; session end and missing bars; straddle target; predictors causal; library equality; folds chronological; blocks contiguous; purged grid; bootstrap keeps whole dates; permutation planted vs null; Holm / BH; costs unchanged; no excluded or universe input; saved results reproduce from the saved config; closing-zone classification) |
| Milestone 1 `tests/test_data_integrity.py` | 16 passed |
| PR #6 `ohlcv_research/tests` | 25 passed |
| Reproducibility | A re-run from `m2_config_snapshot.yaml` (seeded) reproduces the saved baseline table (test); the runner takes about 90 s |

All tests executed against the raw Breeze files; nothing was run on cached or provisional panels.

## 11. Known limitations

1. **No untouched data.** Every number is in-sample; the best conceivable verdict is PROMISING pending new data.
2. **Effective sample is small:** 85 date clusters; 5 observations per session at 60 min. Confidence intervals are wide.
3. **Negative drift (−0.5 to −2.5 bp per window)** inflates any short-biased signal; compare with BL1 always.
4. **Index is not tradable; no futures, no bid/ask.** Predictive value ≠ executable return (D6).
5. **Option universe is selected by Algo 8's trading** (Milestone 1 §5); D0 is biased; no true IV.
6. **Stale closing minutes** (§9) and 2.35 % carried option prices.
7. REX is mechanically related to RG; BL3 and BL4 are one two-sided test, not two independent ones.
8. The persistence baseline is uncalibrated; it is a reference for ranking only.

## 12. Unresolved decisions (need your answer; none blocks this verdict)

| # | Question | Options (first = my recommendation) |
|---|---|---|
| 1 | Reversal dead band (left at 0, not locked) | **A)** lock 0 · B) a bp threshold you supply · C) drop the reversal target |
| 2 | "Four-block expanding" read as 4 contiguous blocks → 3 expanding test steps | **A)** keep · B) four test folds on a different cut |
| 3 | Time-of-day bucket width (set to 30 min) | **A)** keep 30 · B) other |
| 4 | RV first increment measured from the entry open (refines RESEARCH_PLAN §3) | **A)** keep · B) from C[kd−1] (introduces a gap) |
| 5 | Treatment of the stale closing minutes in Milestone 3 | **A)** exclude every label or feature window that reaches 15:15 or later on all sessions · B) exclude only on affected sessions · C) keep and test both |
| 6 | Persistence baseline for family A | **A)** require beating a recalibrated persistence forecast · B) raw persistence only |

## 13. Files

`configs/stage2.yaml` (v2, locked sections) · `targets/targets.py` · `baselines/predictors.py`, `baselines/run_baselines.py` ·
`validation/splits.py`, `inference.py`, `costs.py` · `audit/closing_zone_check.py` · `tests/test_milestone2.py` ·
`results/m2_*.csv` (folds, sample counts, baseline metrics, stability blocks, phase sensitivity, permutation tests, straddle baselines, costs, closing-zone sessions and sensitivity, config snapshot, run log) · `RESEARCH_PLAN.md`, `EXPERIMENT_REGISTER.csv`, `README.md`, `DATA_AUDIT.md` (addendum) · register row DAT-15.
