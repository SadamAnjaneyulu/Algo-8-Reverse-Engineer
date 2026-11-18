# Replacement Analysis (Phase 4)

**Result (rewritten after review):** a strict, one-to-one test finds **no confirmed replacement** (impossible by construction: no parent/allocation id exists), **no pair that is STRONGLY SUPPORTED at the primary thresholds** (0 of 8,056 buy-back orders; 88 only if the excess threshold is relaxed from 2 to 1.5), and an **overall same-right sale-within-60-s rate that is not distinguishable from chance** (observed 6.7 % vs 5.3 % null, ratio 1.25, 95 % cycle-bootstrap CI [0.91, 1.56]). The remaining signal is a modest excess of **opposite-right** (2.8× at 0–30 s unscheduled) and same-contract/near-strike sales (1.9×) immediately after a buy-back, in a handful of cells of a 32-cell table. **The first draft's headline — "opposite right within 30 s is 4.8× chance; 139 STRONGLY SUPPORTED" — came from a biased null and many-to-one pairing, and is withdrawn** (`INDEPENDENT_REVIEW.md` D5; v1 files in `outputs/v1_pre_review/`). Code: `replacement.py`; data: `replacement_cells.csv`, `replacement_headline.csv`, `replacement_threshold_grid.csv`, `replacement_pairs.csv.gz`. All cycles previously inspected; everything here is EXPLORATORY.

## 1. Method (procedure, not an algorithm rule)
D0 body buy-back **orders** in the 30 complete cycles: 8,605; **8,056** fall inside 09:16–15:29 and enter the analysis. Candidate = the earliest still-unassigned body opening-sale order at or after the buy-back within 300 s; **assignment is one-to-one** (an opening-sale order serves at most one buy-back; processed chronologically) in the observed data and in every null draw. 3,100 buy-backs have a candidate (the first draft's 6,887 counted the same sale for several buy-backs).
**Chance baseline (v2):** each buy-back time is shifted **circularly** inside the 09:16–15:29 window by a random multiple of 15 minutes (30–120 min, either direction), preserving the clock phase relative to scheduled sale windows and dropping no draw; 200 draws. v1 shifted by arbitrary 20–120 min and silently dropped draws that left the session, which biased the null low in exactly the early/late minutes where buy-backs and scheduled sales concentrate.

## 2. Excess over chance (cells with ≥ 20 observed; observed / null mean [null 2.5–97.5 %]; `replacement_cells.csv`)
| Pair type | 0–30 s unscheduled | 0–30 s scheduled | 30–60 s unscheduled | 60–120 s unscheduled | 120–300 s unscheduled |
|---|---|---|---|---|---|
| Opposite right | 325 / 114 [90–139] → **2.84** | 198 / 111 [90–133] → 1.78 | 171 / 86 [66–104] → 1.99 | 227 / 161 [137–188] → 1.41 | 429 / 605 → 0.71 |
| Same right, ≤ 1 step | 74 / 40 [26–51] → 1.86 | 35 / 34 → 1.03 | 32 / 29 → 1.11 | 42 / 50 → 0.85 | 92 / 193 → 0.48 |
| Same right, far | 105 / 63 [46–81] → 1.68 | 63 / 51 → 1.24 | 47 / 44 → 1.06 | 66 / 85 → 0.77 | 171 / 327 → 0.52 |
| **Same contract** | 42 / 22 [13–31] → 1.90 | — | — | 33 / 32 → 1.03 | 42 / 129 → 0.33 |

* **Headline rate** (`replacement_headline.csv`): P(same-right opening sale ≤ 60 s after a buy-back) = 6.7 % observed vs 5.3 % null → ratio **1.25, cycle-bootstrap 95 % CI [0.91, 1.56]** — **consistent with chance**.
* Observed counts exceed the null's 97.5th percentile in the 0–30 s opposite-right cells, in the 0–30 s same-contract / near-strike / far-same-right unscheduled cells and in the opposite-right unscheduled cells out to 120 s (30–60 s 1.99×, 60–120 s 1.41×); for same-right sales there is no excess beyond 60 s, and 120–300 s is **below** chance in every type (partly an artefact of one-to-one consumption of sales by earlier pairings, which applies to observed and null alike).
* 32 cells were inspected without multiplicity correction: **treat every cell as HYPOTHESIS-generating**.

## 3. Classification (documented thresholds; `replacement_pairs.csv.gz`; thresholds are author-chosen, not derived)
Primary thresholds (cell excess ≥ 2, delay ≤ 60 s):

| Class | Rule | Pairs | Share | Buy-back lots |
|---|---|---:|---:|---:|
| CONFIRMED | requires an id link — not available | 0 | 0 % | 0 |
| STRONGLY_SUPPORTED | same right, equal lots, ≤ 60 s, not in a scheduled window, cell excess ≥ 2, one equal-quality candidate | **0** | 0 % | 0 |
| POSSIBLE | same right and (cell excess ≥ 1.2, or scheduled window with equal lots) | 460 | 5.7 % | 653 |
| POSSIBLE_CROSS_RIGHT | opposite right, ≤ 60 s, unscheduled, cell excess ≥ 2 | 324 | 4.0 % | 362 |
| COINCIDENTAL | excess < 1.2, or scheduled with unequal lots, or opposite right without excess | 1,989 | 24.7 % | 1,989 |
| UNRESOLVED | no candidate ≤ 300 s, final liquidation (≥ 15:10), or several equal-quality candidates | 5,283 | 65.6 % | 6,382 |

**Threshold sensitivity (`replacement_threshold_grid.csv`):** STRONGLY_SUPPORTED = 88 at (excess ≥ 1.5, any delay cap) and **0** at excess ≥ 2 or 3; POSSIBLE_CROSS_RIGHT = 324–494 at ≥ 1.5, 324 at ≥ 2, 0 at ≥ 3 (cliff). The earlier "139 (or 256)" counts are replaced by this range: **0–88 of 8,056, i.e. ≤ 1.1 %**, and the count flips with a single threshold.

## 4. Alternative explanations (brief's list)
| Explanation | Evidence | Status |
|---|---|---|
| Same-contract replacement | 1.90× at 0–30 s unscheduled (42 vs 22), ≈ 1 or below elsewhere | **not supported as a general pattern**; weak short-delay hint (HYPOTHESIS) |
| Nearby-strike replacement (≤ 1 step) | 1.86× at 0–30 s unscheduled | HYPOTHESIS (timing-limited) |
| Same-direction exposure restoration | not separable from the above | HYPOTHESIS |
| Cross-right sale after a buy-back | 2.84× (0–30 s), 1.99× (30–60 s) unscheduled; headline same-right rate at chance | HYPOTHESIS; the largest excess seen but a smaller one than first reported; needs a CE/PE exposure-balance test on new data |
| Independent scheduled sale | within scheduled windows excess is 1.0–1.8× and lots often differ | consistent with scheduled sales merely near a buy-back |
| Coincidental temporal overlap | the circular-shift null reproduces 79 % of the same-right ≤ 60 s mass (5.3 of 6.7 %) | the default explanation |

## 5. What this does *not* show
It does not show that Algo 8 "replaces" positions, nor that it does not: the evidence is a timing association with no parent id, no order lifecycle messages and second-resolution timestamps. The previous milestone's "43 % of sold lots occur within 60 s of a buy-back vs 29 % chance" is **not reproduced** at order level under the corrected null (6.7 % vs 5.3 %, different denominators).
