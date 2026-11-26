# Algo 8 — D-1 long side (protective wings): what was decoded

*Plan `D1_LONG_SIDE_PLAN.md`, written before the tests. In-sample, D-1 of 32 live cycles. Builds on `BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md`. Steps marked post-hoc were added after seeing results. Figure: `figures/bl_hg_summary.png`.*

## 0. Result: four kinds of long orders on D-1
| # | Long order | Lots on D-1 | Rule | Accuracy | Status |
|---|---|---|---|---|---|
| 1 | **Controller wings** (`h_` buys) | 4,336 | After each body sale, buy **exactly the gap S − L** (short lots − long lots on that right, all strikes) about 4 s later. So long lots = short lots on each right all day. | Quantity = gap in **98%** of 3,141 buy decisions. Quiet-time L = S in **99%** of samples (100% from 09:15 to 13:00). | **Solved (quantity, timing)** |
| 1b | Wing **strike** | | The OTM strike whose premium is nearest **2.5% of the ATM option on the same right** (post-hoc). 2.5% of the sold option's price fits worse. | **65% exact, 93% within one strike** (null 52%). Sold-option reference: 53% exact. | **Mostly solved** |
| 2 | **Wing releases** (`h_` sells, D-1) | 1,192 | When shorts fall (buy-backs), sell exactly the excess longs: 96% of 500 sell decisions. The wing sold is the **outermost or cheapest** held. | Outermost 44%, cheapest 44%, against chance 26%. Innermost 2%. | Quantity solved; which wing is only a preference |
| 3 | **Pre-bought opening wings** (body stream, 09:16) | 186 | Before each of the first 3 scheduled straddles, the body stream buys 1 far CE + 1 far PE (median 39.5 strikes OTM, median premium ₹1.4, 10–90%: ₹0.45–8.6), then sells the straddle a second later. 6 lots per cycle (median 6, range 4–8). They are sold back during the day. | 31 of 32 cycles | **Solved (form)**. Purpose inferred: the hedge is in place before the first sale. |
| 4 | **Overnight lump** (`v_`) | 1,489 | Bought 15:09–15:32 (median first order 15:23:16), on the **heavier short side** only in 80% of cycles, 1.6% OTM (10–90%: 1.2–2.2%), median ₹6.2. At the D-1 close **L − S = lump lots** in 95% of cycle-rights: the controller leaves the lump alone. | Size: best candidate is the heavier side's short lots (Spearman 0.61), but the median ratio is 0.64 | **Form solved, size not** (details: `D1_LUMP.md`) |

**Protection logic (inferred from the observed rules):**
* Every short is matched one-for-one by a far-OTM long on the same right. The book is an iron butterfly pooled by right.
* The wings are about 15 (NIFTY) to 19 (SENSEX) strikes OTM, at about ₹4.5. That caps the tail loss of every short sold.
* Before the overnight carry, the heavier side gets an extra layer about 1.6% OTM: a gap move in the dangerous direction then turns the book net long beyond that strike.
* The lump is **not** a delta hedge. It always leans against the book delta (93% of cycles) but removes only about 5% of it (median |delta| 13.5 → 13.7 lots). It works as **gap (tail) protection**, not delta neutrality.

## 1. Inventory (D-1, all long-side orders)
| module | role | orders | lots | cycles |
|---|---|---|---|---|
| h_ | close_long | 600 | 1192 | 31 |
| h_ | open_long | 3146 | 4336 | 32 |
| num | close_long | 134 | 163 | 30 |
| num | open_long | 199 | 316 | 31 |
| s_ | close_long | 10 | 46 | 1 |
| v_ | open_long | 73 | 1489 | 30 |


## 2. Wing strike (L2)
Sample: 2,430 simple wing buys (one 1-lot body sale on the right in the previous 1.5–10 s, one 1-lot wing). Wing price ÷ body decision price: median 0.0247 (quartiles 0.0231–0.0259).

The "calibrated" price of a strike is its previous-minute close scaled by the chosen wing's decision price over that wing's own minute close. This removes the common staleness of far-OTM minute bars. k is chosen on one cycle half and scored on the other.

| reference price | k (fold 1/2) | exact strike | within one strike | null exact (reference shuffled in slot) |
|---|---|---|---|---|
| atm_px | 0.025/0.025 | 65% | 93% | 52% |
| body_fill | 0.025/0.025 | 53% | 78% | 41% |
| body_ref | 0.025/0.025 | 53% | 78% | 40% |
| body_open | 0.025/0.025 | 51% | 76% | 41% |
| body_now | 0.025/0.025 | 48% | 77% | 39% |
| half_straddle | 0.025/0.025 | 29% | 69% | 29% |


* The best rule using the sold option's price: nearest_log on calibrated prices, 53% exact (null 41%).
* σ-distance rules reach 12% exact, and a fixed offset from the sold strike 9%. **Rejected.**
* So the wing is chosen **by premium (about 2.5% of the ATM premium), not by distance**. The remaining misses are within one strike in most cases. They are probably due to stale minute prices of far-OTM strikes; the real rule likely uses live prices (not testable).

## 3. Releases (L4)
587 D-1 wing sells with at least 2 long strikes held:
| sold wing is the… | outermost | cheapest | newest | nearest 2.5% ATM | oldest | innermost | dearest | chance |
|---|---|---|---|---|---|---|---|---|
| share | 44% | 44% | 38% | 33% | 24% | 2% | 2% | 26% |

The algorithm releases from the far, cheap end of the wing stack and keeps the inner (more valuable) protection. The exact choice is not deterministic. *Unresolved.*

## 4. Body-stream wings (L5)
| role | window | orders | lots | otm_steps_median | L_ge_S_before |
|---|---|---|---|---|---|
| close_long | 09:15-09:17 | 2 | 2 | 17.4 | 100% |
| close_long | after 15:00 | 17 | 17 | 38.7 | 100% |
| close_long | other | 115 | 144 | 37.6 | 96% |
| open_long | 09:15-09:17 | 186 | 186 | 39.5 | 98% |
| open_long | after 15:00 | 6 | 123 | 17.6 | 67% |
| open_long | other | 7 | 7 | 37.8 | 100% |


## 5. Overnight lump size (L6)
| candidate size | lump ÷ candidate (median) | q25 | q75 | median abs error % (ratio 1) | exact | Spearman |
|---|---|---|---|---|---|---|
| S_heavy | 0.64 | 0.42 | 0.92 | 57.26 | 0.0 | 0.61 |
| S_heavy - S_light | 1.27 | 0.95 | 1.68 | 39.64 | 0.0 | 0.52 |
| S_heavy at 15:00 | 0.66 | 0.48 | 0.95 | 52.5 | 0.03 | 0.69 |
| S_heavy - S_light at 15:00 | 1.29 | 0.86 | 1.78 | 39.64 | 0.0 | 0.53 |


* Per cycle, lump ₹ cost: median ₹18,902 (10–90%: ₹6,766–₹30,988). The coefficient of variation is 0.50, so it is not a fixed rupee budget either (post-hoc).
* NIFTY lumps are often close to the heavier side's short lots; SENSEX lumps are smaller. *Size: unresolved.*
* Panel (d) of the figure leaves out one cycle with 278 heavier-side shorts and a lump of 0 on that side; that cycle's 40 lump lots went on the lighter side.

## 6. Open items
1. Lump size (and the two-sided lumps in 17% of cycles).
2. Which wing is released, beyond the outermost/cheapest preference.
3. The 35% of wing strikes that miss on minute data.
4. D-1 wing behaviour after 15:00, when the lump and the late buy-backs overlap: quiet-time balance drops to 71% in the 15:00 hour because of the intended over-hedge.

## Evidence labels
* **Observed:** inventory; quantity = gap; quiet balance; lump side and timing; L − S = lump at close; opening wings; release preferences.
* **Post-hoc / observed:** the ATM 2.5% reference; the lump delta and budget tests.
* **Inferred:** the protection logic and the purpose of the opening wings.
* **Not testable:** live prices of far-OTM strikes; broker margin.
