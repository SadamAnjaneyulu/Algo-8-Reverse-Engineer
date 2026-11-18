# Replacement Analysis (Phase 4)

**Result:** a strict test finds **no confirmed replacement** (impossible by construction: no parent/allocation id exists) and **only 1.6 % of buy-backs qualify as STRONGLY SUPPORTED same-contract/same-right replacements**; 8.6 % are POSSIBLE, 23.6 % show a **cross-right** pattern, 28.6 % are COINCIDENTAL and 37.6 % UNRESOLVED. The sharpest finding is unexpected: **after a body buy-back, a sale on the *opposite* right within 30 s is 4.8× more frequent than chance — more than a same-right sale (2.0–2.9×) and far more than a same-contract sale (≤ 1.6×).** Whether this is "restoring a balanced position" is a **HYPOTHESIS**. Code: `replacement.py`; data: `replacement_cells.csv`, `replacement_pairs.csv.gz`, `lot_links.csv.gz`. Evidence: all cycles previously inspected.

## 1. Method (procedure, not an algorithm rule)
D0 body buy-back **orders** (8,611, 30 cycles with a known carry-in). Candidate = the first body opening-sale order at or after the buy-back within 300 s (6,887 have one). Each pair is described by: same right, same contract, strike distance (steps), lot equality/ratio, delay, whether the sale lies in a scheduled window, number of equal-quality candidates within 60 s. **Chance baseline:** the same pairing with every buy-back shifted by ±20–120 min inside the session (40 draws; the first run used 60 draws — see sensitivity). Excess = observed ÷ null for each (pair type × delay × scheduled) cell.

## 2. Excess over chance (selected cells, observed / null → ratio; `replacement_cells.csv`)
| Pair type | 0–30 s, unscheduled | 0–30 s, scheduled | 30–60 s, unscheduled | 60–120 s, unscheduled | 120–300 s, unscheduled |
|---|---|---|---|---|---|
| Opposite right | 1,706 / 352 → **4.84** | 684 / 203 → 3.36 | 510 / 235 → 2.17 | 451 / 337 → 1.34 | 402 / 564 → 0.71 |
| Same right, ≤ 1 step | 305 / 105 → **2.91** | 112 / 63 → 1.77 | 80 / 73 → 1.10 | 95 / 107 → 0.88 | 89 / 188 → 0.47 |
| Same right, far | 394 / 196 → 2.02 | 232 / 99 → 2.35 | 212 / 130 → 1.64 | 150 / 176 → 0.85 | 184 / 283 → 0.65 |
| **Same contract** | 110 / 67 → **1.64** | 43 / 43 → 0.99 | 58 / 48 → 1.22 | 55 / 73 → 0.76 | 59 / 134 → 0.44 |

Overall P(same-right opening sale ≤ 60 s after a buy-back): **19.6 % observed vs 11.3 % chance.** Beyond ~60 s there is no excess in any cell; for 120–300 s the rate is **below** chance (the algorithm sells *less* in that window). **Same-contract re-sale — the textbook "replacement" — is the weakest pattern.**

## 3. Classification (documented thresholds; `replacement_pairs.csv.gz`)
| Class | Rule | Pairs | Share | Lots (buy-back) |
|---|---|---:|---:|---:|
| CONFIRMED | requires an id link — not available | 0 | 0 % | 0 |
| STRONGLY_SUPPORTED | same right, equal lots, ≤ 60 s, not in a scheduled window, cell excess ≥ 2, single equal-quality candidate | 139 | 1.6 % | 139 |
| POSSIBLE | same right and (cell excess ≥ 1.2, or scheduled window with equal lots) | 740 | 8.6 % | 898 |
| POSSIBLE_CROSS_RIGHT | opposite right, ≤ 60 s, unscheduled, cell excess ≥ 2 | 2,030 | 23.6 % | 2,242 |
| COINCIDENTAL | excess < 1.2, or a scheduled sale with unequal lots, or opposite right without excess | 2,461 | 28.6 % | 2,493 |
| UNRESOLVED | no candidate ≤ 300 s, final liquidation (≥ 15:10), or several equal-quality candidates | 3,241 | 37.6 % | 4,178 |

**Sensitivity (disclosed):** the first run (60 null draws, before cross-right handling) gave 256 STRONGLY_SUPPORTED pairs; with 40 draws 139. Cells whose excess sits near the 2.0 threshold (same-right-far, 0–30 s unscheduled: 2.0–2.35) flip. **The STRONGLY_SUPPORTED count is not stable to a factor ~2 and should be read as "between ~140 and ~260 of 8,611", i.e. ≤ 3 %.**

## 4. Alternative explanations (brief's list)
| Explanation | Evidence | Status |
|---|---|---|
| Same-contract replacement | ratio ≤ 1.64 (0–30 s unscheduled), 0.99 in scheduled windows, < 1 beyond 60 s | **REJECTED as the general pattern** (weakly present at 0–30 s) |
| Nearby-strike replacement (≤ 1 step) | 2.91× at 0–30 s unscheduled | **POSSIBLE** (timing-limited) |
| Same-direction exposure restoration | not separable from the above; sizes equal in 92 % of followed pairs (earlier phase) | HYPOTHESIS |
| **Cross-right sale after a buy-back** | **4.84× (0–30 s), 2.17× (30–60 s)** | **HYPOTHESIS** — the strongest effect observed; needs an exposure-balance test (CE/PE symmetry) before any rule |
| Independent scheduled sale | within scheduled windows the excess is smaller (1.0–3.4×) and lots often differ | consistent with the sale being scheduled and merely near a buy-back |
| Coincidental temporal overlap | the time-shift null reproduces 58 % of the "within 60 s" mass (11.3 % of 19.6 %) | the default explanation for 29 % of pairs |

## 5. What this does *not* show
It does not show that Algo 8 "replaces" positions, nor that it does not: the evidence is a timing association, with no parent id, no order lifecycle messages and second-resolution timestamps. The earlier statement "43 % of sold lots occur within 60 s of a buy-back vs 29 % chance" is reproduced in kind here (19.6 % vs 11.3 % at order level, different denominators) and **refined**: most of the excess is a *cross-right* sale, not a replacement of the same position.
