# Algo 8 — body buy-backs: single vs combined, positions below 1.2×, and buy-backs below 1.2×

*Investigation only (no simulator change, no alpha). In-sample, observational: 31 cycles with a D-1 log; the 35 live cycles are not a holdout. Plan: `BODY_CLOSE_LOGIC_PLAN.md` (written before the tests). Every number is read from `outputs/bl_summary_close*.json` / `bl_close_*.csv`. Figure: `figures/bl_close_logic.png`.*

## 0. Answers (D-1)

| Your question | Answer | Evidence level |
|---|---|---|
| Are CE and PE bought back **together** when premium is 1.2–1.7×? | **No — individually.** Only 8.8% of the 1,324 buy-back orders have a CE/PE counterpart at the same strike within ±3 s (chance: 0.1%); 17.8% have one at any strike. In the 1.2–1.7× average-ratio bins the paired share is 5%–10%. | Observed |
| Is the trigger **single-leg or combined**? | **Single-leg: the leg's own premium ÷ its own entry.** When only one leg is bought back it is the higher-ratio leg 86.6% of the time (cluster CI 83.6%–89.1%; 50% = indifferent). The other leg's ratio and the straddle ratio add nothing (leave-one-cycle-out AUC gain ≤ 0.0065). On the *both-legs* events the max-leg ratio does not beat a single leg (ΔAUC +0.17, CI -0.02 to +0.35) → combined trigger **not supported** under the pre-registered rule. Both legs ≥ 1.2× at the same strike **never** occurs (40,565 strike-minutes). | Observed |
| Is **1.2×** a threshold? | **No.** Against the cheapest open entry the buy-back hazard is flat (≈5–7 per 1000 contract-minutes) from 1.0× to 1.4×; the hazard first steps up ≥3× on entering the **1.4–1.5** bin (3.1×) and again on entering 1.5–1.6× (4.3×); it keeps rising to 672/1000 at 1.7–1.8×. | Observed (reference is a convention) |
| Positions that **never reach 1.2×** — closed on D-1 or carried? | **Mostly carried overnight.** 61% of D-1 sold lots never reach 1.2× on a minute close; 82% of them are carried (81% FIFO, 79% HIGH). Strike-level (ownership-free): 140 of 441 positions never reach 1.2×; 86% carried. Overall 69.3% of lots are carried. | Observed |
| Do buy-backs happen **below 1.2×**? On what basis? | **Yes: 33%–40% of orders (depending on the lot convention); 31% under all three.** About a third of them (36%) fall within 3 s of a stop-like (≥1.5×) buy-back (chance 0.6%), mostly the **same right but a different strike** (68% same right, 10% same strike, median 2 strikes away): one lot's stop pulls neighbouring same-side lots out with it. The rest has **no identified rule**: 205–282 orders = 15%–21% of all D-1 buy-backs (two yardsticks, §5). | Inferred (cluster) / Unresolved (rest) |

## 1. Data and method (short)
* Order-level table of every D-1 body buy-back (1,324 orders, each 1 lot). **Decision price = limit ÷ 1.15** (all orders are marketable limits ≈ 15% beyond the live price; check: decision price ÷ previous-minute close has median 1.002).
* **Entry references** (lot ownership inside a strike is unobserved, so three conventions are shown): *average* open body entry (pro-rata removal), *cheapest open entry* (LOW: buy-backs remove the lowest-entry lot first — the lot with the highest ratio, i.e. what a per-lot stop would hit), *oldest open entry* (FIFO). `HIGH` is used only in the carry test. Each convention keeps its own open set, so the references can differ for the same order.
* **Paired** = other-right body buy-back at the same strike within ±3 s; **partnered** = other-right buy-back at any strike within ±3 s. Chance level from circularly shifting the other right's order times inside the cycle-day (strike kept).
* Hazard = buy-backs per 1000 contract-minutes (contract = a strike/right with body shorts open; ratio = previous-minute close ÷ entry). Minute data only (no bid/ask, no high/low).

## 2. CE and PE: together or individually?
| premium ÷ average entry | orders | paired (same strike, ±3 s) | partnered (other right, any strike, ±3 s) |
|---|---|---|---|
| (0.0, 0.8] | 104 | 38.5% | 45.2% |
| (0.8, 1.0] | 160 | 8.8% | 11.9% |
| (1.0, 1.2] | 217 | 3.7% | 9.2% |
| (1.2, 1.4] | 189 | 9.5% | 22.8% |
| (1.4, 1.55] | 247 | 5.7% | 11.7% |
| (1.55, 1.7] | 246 | 5.3% | 17.9% |
| (1.7, 2.0] | 157 | 5.7% | 21.0% |
| (2.0, 99.0] | 4 | 25.0% | 25.0% |

* Paired legs (n = 117): the high leg has median ratio 1.53, the other 0.69. One ≥1.2× and the other <1.2×: 79%; both <1.2×: 21%; both ≥1.2×: 0%. A pair is therefore a stop-like leg plus a partner that is **not** at the stop level — not two legs hitting a level together.
* Pairing is much more common at ≤0.8× (38%), which is where simultaneous clean-up closes sit; it is not a feature of the 1.2–1.7× band.
* Strike-minutes with both legs short (40,565): CE bought back 312, PE 348, both in the same minute 36 (5.8% of all buy-back strike-minutes).

**What predicts which leg is bought back (D-1, AUC with cluster-bootstrap CI over cycles; permutation null ≈ 0.5):**
| target | variable | events | AUC | CI low | CI high | permutation max |
|---|---|---|---|---|---|---|
| both | r_max | 36 | 0.702 | 0.584 | 0.82 | 0.62 |
| both | r_min | 36 | 0.364 | 0.271 | 0.468 | 0.572 |
| both | straddle_r | 36 | 0.684 | 0.544 | 0.803 | 0.594 |
| both | r_ce | 36 | 0.535 | 0.35 | 0.722 | 0.58 |
| both | r_pe | 36 | 0.5 | 0.344 | 0.684 | 0.643 |
| ce_only | r_ce | 276 | 0.805 | 0.754 | 0.841 | 0.574 |
| ce_only | r_pe | 276 | 0.224 | 0.194 | 0.282 | 0.496 |
| ce_only | r_max | 276 | 0.719 | 0.641 | 0.782 | 0.552 |
| ce_only | straddle_r | 276 | 0.726 | 0.654 | 0.791 | 0.558 |
| pe_only | r_pe | 312 | 0.807 | 0.756 | 0.856 | 0.568 |
| pe_only | r_ce | 312 | 0.238 | 0.201 | 0.282 | 0.465 |
| pe_only | r_max | 312 | 0.728 | 0.671 | 0.807 | 0.537 |
| pe_only | straddle_r | 312 | 0.656 | 0.586 | 0.722 | 0.516 |

* Own-leg ratio AUC ≈ 0.80 for single-leg events; max-leg ≈ 0.72; straddle ratio 0.66–0.73; **other-leg ratio < 0.5** (a higher other-leg ratio goes with this leg being bought back *less* often; plausibly because the other leg is the one under stress — an inference).
* Leave-one-cycle-out logistic: own ratio alone CE 0.771 → +other leg 0.770 (permuted-other max gain +0.0079); PE 0.771 → 0.777 (permuted max +0.0030). The PE gain +0.0065 is statistically above the permuted maximum but economically negligible.

## 3. Is 1.2× a threshold? (hazard, D-1)
| premium ÷ entry | average entry: per 1000 contract-min | cheapest open entry: per 1000 contract-min | oldest open entry: per 1000 contract-min | cheapest-entry events / minutes |
|---|---|---|---|---|
| ≤0.8 | 2.4 | 2.1 | 2.8 | 51/24287 |
| 0.8–1.0 | 4.1 | 3.2 | 4.9 | 74/23455 |
| 1.0–1.1 | 6.2 | 5.3 | 6.1 | 115/21642 |
| 1.1–1.2 | 5.7 | 5.2 | 7.2 | 66/12679 |
| 1.2–1.3 | 7.4 | 6.5 | 7.1 | 53/8102 |
| 1.3–1.4 | 19.2 | 6.5 | 10.9 | 34/5215 |
| 1.4–1.5 | 39.8 | 20.4 | 25.4 | 66/3229 |
| 1.5–1.6 | 59.5 | 87.5 | 55.4 | 132/1508 |
| 1.6–1.7 | 112.2 | 248.8 | 110.0 | 101/406 |
| 1.7–1.8 | 175.4 | 671.9 | 298.7 | 43/64 |
| >1.8 | 171.8 | 535.7 | 269.7 | 15/28 |

Adjacent-bin steps (pre-registered rule: call a level a threshold only if the hazard steps ≥3× between adjacent bins under the cheapest-entry reference):
| bin → next bin | hazard step (cheapest-entry ref) | hazard step (average-entry ref) |
|---|---|---|
| ≤0.8 → 0.8–1.0 | 1.5× | 1.7× |
| 0.8–1.0 → 1.0–1.1 | 1.7× | 1.5× |
| 1.0–1.1 → 1.1–1.2 | 1.0× | 0.9× |
| 1.1–1.2 → 1.2–1.3 | 1.3× | 1.3× |
| 1.2–1.3 → 1.3–1.4 | 1.0× | 2.6× |
| 1.3–1.4 → 1.4–1.5 | 3.1× | 2.1× |
| 1.4–1.5 → 1.5–1.6 | 4.3× | 1.5× |
| 1.5–1.6 → 1.6–1.7 | 2.8× | 1.9× |
| 1.6–1.7 → 1.7–1.8 | 2.7× | 1.6× |
| 1.7–1.8 → >1.8 | 0.8× | 1.0× |

* **1.2× fails the rule** (step 1.3× into 1.2–1.3, 1.0× into 1.3–1.4). The first ≥3× step is on entering 1.4–1.5. Under the average-entry reference the rise is graded (largest step 2.6×); the oldest-entry reference lies in between (largest step 2.7×). The hazard is flat from 1.0× to 1.4× — a buy-back is not "slowly started at 1.2×".
* **The sharpness depends on the reference.** Against the cheapest open entry the hazard at 1.7–1.8× is 672/1000 (about 2 in 3 minutes); against the average entry only 175/1000. A per-lot premium stop near 1.5–1.7× of the lot's own entry would look like this under LOW and blunter under the others. **That is a consistent reading, not a proof** (ownership is unobserved).
* Distribution of the ratio at the buy-back (figure panel A, cheapest-entry ref): a large mode at 1.5–1.8× and a second mode at 1.0–1.2×. The second mode is what the user sees as "buy-backs below 1.2×".

## 4. Positions that never reach 1.2× — closed or carried?
| lot convention | lots that never reach 1.2× | …of those carried overnight | lots reaching ≥1.2×: carried | reaching ≥1.5×: closed on D-1 | reaching ≥1.7×: closed on D-1 | never-1.2× carried (sold before 12:00 only) |
|---|---|---|---|---|---|---|
| LOW | 61.4% | 81.7% | 49.6% | 82.8% | 96.0% | 78.0% |
| FIFO | 60.9% | 81.2% | 50.7% | 74.7% | 85.2% | 69.7% |
| HIGH | 61.4% | 79.4% | 53.2% | 66.1% | 77.5% | 68.4% |

| highest ratio reached (cheapest open entry) | strike positions | carried (some lot) | carried share |
|---|---|---|---|
| (0.0, 1.0] | 11 | 5 | 45.5% |
| (1.0, 1.2] | 129 | 115 | 89.1% |
| (1.2, 1.4] | 119 | 110 | 92.4% |
| (1.4, 1.5] | 36 | 33 | 91.7% |
| (1.5, 1.6] | 39 | 32 | 82.1% |
| (1.6, 1.7] | 60 | 34 | 56.7% |
| (1.7, 99.0] | 47 | 25 | 53.2% |

* The carried share falls with the highest ratio reached (figure panel C; LOW convention): 82% carried (n=2869) up to 1.2×, 54% carried (n=280) at 1.4–1.5×, 23% carried (n=349) at 1.5–1.6×, 4% carried (n=100) at 1.7–2.0×. Lots that stay below ~1.4× are mostly kept overnight; FIFO/HIGH curves are higher above 1.5× (panel C).
* **Mechanical-carry check:** lots sold late have little time to reach a ratio. Restricting to lots sold before 12:00 IST leaves 78%–68% of never-1.2× lots carried (LOW–HIGH), against 58% / 52% / 55% carried among all early lots.
* Strike-level "carried (some lot)" stays high even when the highest ratio is high because a strike holds several lots and only the stressed ones are closed; the lot-level table is the better reading of the stop behaviour.
* The earlier finding stands: there is no closing time and no selling cut-off on D-1; closes are driven by premium ratio (and the unexplained residual below), not the clock.

## 5. Buy-backs below 1.2× — what are they?
Share of D-1 buy-back orders below 1.2×: average-entry 36.3%, cheapest 33.1%, oldest 39.8%, all three 31.5%. Switching reference removes only a part, so the sub-1.2× mode is real.

**Mutually exclusive classification (average-entry ratio < 1.2×, 481 orders; first match wins; the order of classes was fixed in the code, not tuned):**
| class (first match in this order) | orders | share of the below-1.2× orders |
|---|---|---|
| 1 same-strike partner leg >=1.2x (paired) | 38 | 7.9% |
| 2 other-strike partner leg >=1.2x | 19 | 4.0% |
| 3 a lot-level reference (LOW/FIFO) >=1.2x | 64 | 13.3% |
| 4 end of day (>=15:10) | 27 | 5.6% |
| 5 other leg of the strike >=1.2x, not bought back | 24 | 5.0% |
| 7 re-sold within 60 s (same right) | 60 | 12.5% |
| 8 empties the strike | 44 | 9.1% |
| other | 205 | 42.6% |

* Classes 1–2 (a ≥1.2× partner leg within 3 s) = 12%; class 3 (a lot-level reference ≥1.2×, i.e. the order is a stop under another convention) = 13%; **205 orders (43% of the below-1.2× orders, 15% of all D-1 buy-backs) stay unexplained** by this yardstick. The cluster test below uses the cheapest-entry yardstick and leaves 282 (21% of all). So the unexplained share is **15%–21% of all D-1 buy-backs**, depending on the yardstick.

**Clusters (post-hoc, added after the first classification left a large residual and a first look showed sub-1.2× buy-backs next to stop-like ones).** Using the cheapest-entry ratio (stop-like = ≥1.5×; this cut-off was chosen after the hazard table, see §8): 508 clusters (gap ≤ 3 s); 51% are single orders; 69% of all orders sit in a cluster with a stop-like member. Of the 438 sub-1.2× orders **36% are within 3 s of a stop-like order (shifted-time chance 0.6%)**. Joiners: same right 68%, same strike 10%, distance median 2 / 75th pct 3 / 90th pct 4 strikes. Widening the clustering window to 10 / 30 / 60 s raises the share of sub-1.2× orders whose cluster has a ≥1.5× member to 39% / 40% / 52% (and to 66% with a ≥1.2× member at 60 s); 27% of the sub-1.2× orders are isolated single orders at 3 s.

**Residual: 282 sub-1.2× orders in no stop-like cluster (21% of all D-1 buy-backs).** Tests on **all** D-1 contract-minutes with cheapest-entry ratio < 1.2× — not only the residual — (82,055 rows, 306 buy-back minutes):
| variable | AUC | lo | hi | null_max |
|---|---|---|---|---|
| r_low | 0.618 | 0.58 | 0.655 | 0.506 |
| price | 0.633 | 0.574 | 0.681 | 0.6 |
| abs_itm | 0.406 | 0.375 | 0.434 | 0.528 |
| itm_steps | 0.564 | 0.528 | 0.595 | 0.529 |
| hold_min | 0.461 | 0.407 | 0.524 | 0.499 |
| n_open | 0.496 | 0.444 | 0.526 | 0.491 |
| o_n_open | 0.465 | 0.416 | 0.505 | 0.498 |
| o_r | 0.436 | 0.382 | 0.498 | 0.549 |
| straddle_r | 0.524 | 0.462 | 0.581 | 0.56 |
| tod_min | 0.506 | 0.47 | 0.557 | 0.515 |

* No single variable passes 0.65 AUC. A leave-one-cycle-out gradient-boosting model on all 12 variables reaches AUC 0.763 — a diffuse multivariable signal (largest drops when removing the other leg's open lots, holding time, ITM distance, price):
| model | LOCO AUC |
|---|---|
| all 12 variables | 0.763 |
| drop o_n_open | 0.735 |
| drop hold_min | 0.741 |
| drop itm_steps | 0.744 |
| drop price | 0.748 |
| drop straddle_r | 0.753 |

  This is not a rule; it shows the residual is not pure noise, and it is in-sample.
* **Balance-control hypothesis (rejected).** By analogy with the hedge I tested whether the right bought back is the right with more short lots. For sub-1.2× orders it is (69%), but that is exactly what random choice of lots would give (69% expected). Stop-like orders hit the right with **fewer** short lots (9% vs 70% expected) — the stopped side is the one with fewer lots (descriptive; plausibly earlier stops already reduced it — an inference).
| buy-back class (cheapest-entry ratio) | orders | bought-back right has more short lots | cluster CI | expected if lots drawn at random |
|---|---|---|---|---|
| middle (1.2-1.5x) | 234 | 56.8% | 49.0%–63.0% | 65.3% |
| stop-like (>=1.5x) | 634 | 8.8% | 4.1%–14.6% | 70.1% |
| sub-1.2x | 432 | 69.0% | 63.1%–76.7% | 68.9% |


## 6. D0 (secondary, for contrast)
* D0 buy-backs are **not** premium-ratio driven: own-leg ratio AUC 0.48 (CE) / 0.48 (PE) (≈ chance; D-1 ≈ 0.77); among sub-1.2× contract-minutes the minute of day alone has AUC 0.78 (clock-driven bulk closing, as found in the lifecycle study).
* Pairing is much more common (20% of orders paired vs chance 0.7%; 20% of buy-back strike-minutes close both legs) and 69% of orders are below 1.2× (average ref; 53% under all three). Only 14% of sub-1.2× orders sit within 3 s of a stop-like order (chance 1.5%). D0 needs its own schedule analysis; it is not answered here.

## 7. Evidence register
| Claim | Label | n / basis |
|---|---|---|
| D-1 buy-backs are single-leg; pairing 8.8% vs chance 0.1% | **Observed** | 1,324 orders, 31 cycles |
| Own-leg premium ratio is the trigger; other-leg / straddle ratio add nothing | **Observed** (predictive, not causal) | 40,565 strike-minutes, LOCO, permutation null |
| No step at 1.2×; hazard rises steeply between 1.4× and 1.8× against the cheapest open entry | **Observed** (reference-dependent) | 750 buy-back minutes |
| Consistent with a per-lot premium stop of ≈1.5–1.7× the lot's own entry | **Inferred** | hazard shape under LOW only; ownership unobserved |
| Lots below ~1.4× are mostly carried overnight; ≥1.7× mostly closed | **Observed** | 4,671 lots; robust to lot convention and late sales (ranges shown) |
| ≈36% of sub-1.2× buy-backs are co-closed with a stop-like buy-back, same right, nearby strikes | **Inferred** (cluster; post-hoc threshold) | 438 orders, shifted-time null |
| 15%–21% of D-1 buy-backs (sub-1.2×, not co-closed) have no identified basis | **Unresolved** | 205–282 orders (two yardsticks) |
| Balance control of CE/PE short lots | **Rejected** | lot-proportional null reproduces it |

## 8. Limits, post-hoc items and how this could be wrong
* **Reference dependence.** Entry reference per order is a convention (ownership unobserved); the LOW view is the sharpest and is the one I read as "per-lot". Under average/oldest-entry references the structure is the same but blunter.
* **Minute data.** Ratios use the previous-minute close; intra-minute spikes are invisible. A lot that breached 1.5× inside a minute and was closed will appear as closed at a lower close ratio. This may account for part of the 1.2–1.5× class and some sub-1.2× closes; it cannot be tested without tick data.
* **Post-hoc items** (labelled in the text): the cluster analysis and the stop-like cut-off of 1.5× (chosen after seeing the hazard table; window sensitivity is in §5); the balance test; the gradient-boosting drop-one run; the early-lot robustness check; the pairing window (3 s) is an analysis choice (±10/30/60 s only checked for the cluster share).
* **Plan deviation:** the plan named `bl_close_orders.py` and `bl_close_panel.py`; the code is `bl_close_build.py` (order table, strike-level panel, lot table in one replay) and `bl_close_logic1–7`. The earlier `bl_close_panel.py` is unchanged; both panels agree on the 750 buy-back contract-minutes.
* **What I did not test:** why stop-like closes are not certain once the ratio is high (hazard 672 per 1000 minutes at 1.7–1.8× is not 1000); the residual's rule; D0 schedule slot by slot; any link to hedge/lump events at the moment of a buy-back.
* **In-sample.** All 31 cycles were used for exploration and checks; none is held out.

## 9. Files
`src/bl_close_build.py` → `bl_close_logic1.py` (order-level, pairing, below-1.2× classes, episodes) → `bl_close_logic2.py` / `2b` (single vs combined) → `bl_close_logic3.py` / `4` (sub-1.2× signal) → `bl_close_logic5.py` (carry) → `bl_close_logic6.py` (clusters) → `bl_close_logic7.py` (balance) → `bl_close_fig.py` → `make_close_report.py`. Outputs: `outputs/bl_close_orders*.csv`, `bl_close_panel2.csv.gz`, `bl_close_lots.csv`, `bl_close_C_*`, `bl_close_D_*`, `bl_close_E_*`, `bl_summary_close*.json`. Tests: `tests/test_bl.py` (`test_close_*`).
