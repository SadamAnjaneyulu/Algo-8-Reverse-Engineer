# Position and Leg Attribution

Source: `leg_attribution.py` → `leg_attribution_cycles.csv`, `leg_attribution_summary.csv`, `wing_cycles.csv`, `wing_summary.csv`, `worst10_leg_view.csv`; `mechanism.py` → `pnl_time_decomposition*.csv`, `cut_timing.csv`; `entry_outliers.py`, `entry_print_check.csv`. Baseline = HOLD_SETTLE, base costs, original settlement proxy. **Integrity check:** per-leg net rebuilt from trades + settlement + cost functions sums to the engine/accounting cycle net with max error 1.5e-11 across all 275 cycles. Code executed, outputs observed.

## 1. Leg attribution (₹, combined NIFTY+SENSEX)

| Sample | Leg | Premium cash flow | Gross P&L | Slippage | Costs | **Net P&L** | % cycles positive | mean leg MAE | mean leg MFE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IS | Short CE | +2,752,556 | −34,558 | 13,832 | 7,732 | **−56,122** | 61 % | −18.6k | +11.2k |
| IS | Short PE | +2,535,355 | +656,430 | 12,740 | 7,443 | **+636,247** | 73 % | −13.5k | +11.4k |
| IS | Long CE wing | −25,105 | −23,123 | 1,982 | 4,141 | **−29,246** | 0 % | −130 | +46 |
| IS | Long PE wing | −49,636 | −47,564 | 2,072 | 4,151 | **−53,787** | 0 % | −278 | +112 |
| OOS | Short CE | +2,189,383 | +282,301 | 11,002 | 6,104 | **+265,195** | 72 % | −20.8k | +16.7k |
| OOS | Short PE | +1,961,600 | +15,784 | 9,857 | 5,719 | **+208** | 66 % | −25.0k | +14.8k |
| OOS | Long CE wing | −30,124 | −4,217 | 1,307 | 2,410 | −7,934 | 1 % | −288 | +439 |
| OOS | Long PE wing | −36,765 | −35,462 | 1,303 | 2,376 | −39,141 | 0 % | −361 | +173 |
| Exposed | Short CE / PE | | +324.7k / −118.1k | | | +319.3k / −122.9k | 83 % / 61 % | | |
| Clean | Short CE / PE | | −42.4k / +133.9k | | | −54.1k / +123.2k | 66 % / 69 % | | |
| Clean | Wings CE / PE | | +1.7k / −27.3k | | | −0.7k / −29.7k | 2 % / 0 % | | |

(Full per-index tables: `leg_attribution_summary.csv`. Premium cash flow is the entry premium, not P&L. "Max adverse/favourable" is the minute-mark path of each leg's own mark-to-market from its fill. All legs in the HOLD baseline are held from the D-1 09:16 entry to settlement ≈ 30 clock hours / 12.5 market hours, one overnight.)

**Findings**
1. The book is two short options earning premium; **which side earns flips by window**: IS +₹636k on the short put vs −₹56k on the short call (rising market); full OOS the reverse (+₹265k call, ≈0 put); exposed call +₹319k/put −₹123k; clean call −₹54k/put +₹123k. A side that makes ₹600k in one window and ≈0 in the next is path luck of the underlying, not a leg-level edge.
2. Total short-leg gross = ₹621.9k IS, ₹298.1k OOS. Wings subtract ₹70.7k (IS) / ₹39.7k (OOS) gross; with their own friction −₹83.0k / −₹47.1k net.

## 2. Why the wings cost money without reducing the worst cycle

| Item | NIFTY | SENSEX |
|---|---:|---:|
| Wing distance (rule) | 2,000 pts | 4,000 pts (2,000 from 2026-09-16) |
| Average actual distance after substitution | 1,916 CE / 1,969 PE | 3,756 / 3,776 |
| Largest \|close − K\| in 275 cycles | **963 pts** | 2,410 pts |
| 99th percentile \|close − K\| | 732 | 2,073 |
| Cycles where the wing finished in the money | **0 / 154** | 1 / 121 (CE, 2026-11-05) |
| Premium paid for wings, all cycles | ₹23.5k CE + ₹30.1k PE | ₹31.8k CE + ₹56.3k PE |
| Wing net P&L, all cycles | −₹60.8k | −₹69.3k |

The wings sit **2–4× farther away than any move that actually happened**, so they are pure carrying cost with essentially no payoff. The worst cycle (NIFTY 2026-02-03, −₹124.2k) was a +963-pt move; the call wing at K+2,000 was 1,037 pts away from paying and contributed −₹302. In 9 of the 10 worst cycles the wings' gross P&L was negative (between −₹19.9k and −₹0.3k); the only material pay-off was SENSEX 2026-11-05 (+₹23.3k, wing at 2,000 after the width change; the cycle still lost ₹73.7k). One anomalous cycle (SENSEX 2025-04-08) shows −₹19.3k on a substituted put wing: that is the first-print artefact in §4.

Answers to the brief: *too far?* **Yes, relative to the realised distribution.** *Poorly positioned?* Same thing. *Expensive insurance?* Cheap per cycle (₹0.35k NIFTY / ₹0.73k SENSEX) but ~17 % of IS net P&L (₹83k of ₹497k), and it buys no observed protection. *Tail reduction in some cycles?* Yes, in 1 of 275 (and only partly). *What the wings might be for* (margin relief under SPAN, protection against a >2,000-pt crash that did not occur in this sample) **cannot be measured here**: the engine has no margin model and 275 cycles cannot test a >4σ event. I have not changed or optimised the wings.

## 3. Entry structure and what the substitution does
In 54 % of NIFTY and 31 % of SENSEX cycles at least one wing was substituted toward ATM (the rule's wing never traded in 09:16–09:20). Mean P&L when a wing was substituted is lower (NIFTY ₹1.9k vs ₹4.4k per cycle; SENSEX ₹1.4k vs ₹2.3k), but wing substitution coincides with high-premium/high-volatility days; I do not claim causality.

## 4. A data-quality finding: first-print entry (SENSEX 2025-04-08)
The SENSEX 72,700 CE on 2025-04-07 (D-1) had **its first trade of the day at 09:16 at ₹38.30**; the next bar opened ₹1,535.55 (spot at the time had gapped from a stale 71,450 to 72,678 at 09:15). The model sells at ₹38.30 and loses ₹78.1k. One cycle accounts for ~₹90k of the +₹100k SENSEX-IS improvement under the 1-minute-delay stress (this resolves the earlier "delay improves P&L" puzzle: it is **one outlier**, not a systematic effect). Count of such first-print entries: 1 short leg in IS, 0 in OOS; and a ≥50 % one-minute jump after entry in 2 short legs total (that one, plus OOS 2026-10-15, +69 %, a real spike, not a data error). **Impact on the question asked:** IS only, and it makes IS *worse* — excluding this cycle IS net would be ₹575k, not ₹497k. It does not explain the OOS weakness.

## 5. When is P&L made? (HOLD baseline, net, ₹)

| Sample | Net | D-1 session | **Overnight gap** (D-1 15:29 → D0 09:16) | D0 09:16–15:29 | Settlement step |
|---|---:|---:|---:|---:|---:|
| IS | 497,091 | +86,531 | **−106,079** | +495,652 | +20,988 |
| OOS | 218,329 | +54,054 | **−39,399** | +157,970 | +45,703 |
| OOS exposed | 179,642 | −12,903 | +71,327 | +101,086 | +20,132 |
| OOS clean | 38,687 | +66,957 | **−110,726** | +56,885 | +25,571 |
| IS worst 10 % cycles | −829,150 | −108,931 | −135,548 | −614,535 | +29,865 |
| OOS worst 10 % cycles | −594,000 | +5,396 | **−285,520** | −323,283 | +9,406 |
| OOS clean worst 10 % | −483,579 | −4,490 | **−298,669** | −189,522 | +9,102 |

(The settlement step is the difference between the 15:29 mark and the settlement value, which is the net of settlement-proxy P&L and exercise costs.)

**Findings.** The strategy collects its P&L in the D0 session (theta decay into expiry: +₹496k IS) and **pays for it overnight**: the overnight leg lost ₹106k IS and ₹111k on the clean OOS — more than the entire clean net (₹38.7k). In the worst decile of OOS cycles, **48 % of the loss (−₹286k of −₹594k) is already realised by the 09:16 mark on D0**, before any in-session rule has had a chance to act. This is the central mechanism behind the plugin results in `PLUGIN_EFFECTIVENESS_REPORT.md`. Status: **established** as a description (the decomposition is exact); the interpretation that overnight gap risk is un-hedgeable by the current rules follows directly but I have not tested alternatives.

Figures: `figures/leg_attribution.png`, `figures/pnl_time_segments.png`.
