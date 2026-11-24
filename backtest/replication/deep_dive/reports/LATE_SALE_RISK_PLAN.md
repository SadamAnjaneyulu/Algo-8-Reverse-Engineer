# Are the late D-1 sales risk control for the D0 opening? Pre-registered investigation plan

*Written 2026-11-24 before any risk statistic was computed. **Exploratory**, on development cycles only; it cannot confirm anything and it does not change the frozen rule. All tests are counted below and corrected for multiplicity.*

## Question (from the user)
The late sales may exist to **control the risk of the D0 opening**: the system sells and balances the book using portfolio state (positions, Greeks, gap exposure) or a market indicator such as VWAP. Is there evidence, **cycle by cycle**, that a sale's side and timing follow the book's risk state?

## Data and construction
* **Book:** reconstructed from every real D-1 order (sells, covers, wings, lump), signed lots by (CE/PE, strike), updated at each fill time. Lot unit from the cycle table.
* **Prices and Greeks:** option minute closes of the **previous** completed minute (causal). Forward = median put-call-parity forward of the three strikes nearest the money. Implied vol per leg by bisection (Black-76, r = 0); missing/floor-priced legs take the interpolated vol of valid neighbours. Time to expiry = D-1 time to D0 15:30.
* **Book risk state** at a time: net delta (contracts, and ₹ per 1% move), gamma (change of delta per 1% move), vega (₹ per vol point), theta (₹/day), short and long lots per side, uncovered shorts per side, and **gap P&L at the D0 open** under spot gaps of ±1, ±2, ±3% (full revaluation at the D0-open time to expiry, implied vols held; additive across legs). `gap_worst` = the worst of the six. `asym` = P&L(+2%) − P&L(−2%).
* **Indicator:** near-month future VWAP from 09:15 and the deviation of the last close from it, in strike steps.
* **Window:** primary j ≥ 360 (15:15 onwards), the unexplained part. Secondary: 14:15–15:14. Outlier cycle NIFTY 16 Oct reported separately and excluded from pooled statistics. Post-auction and pre-auction cycles reported separately.

## Hypotheses (each defined now)
| ID | Hypothesis | Test |
|---|---|---|
| **H1** | **Delta balancing:** a sale is made on the side that reduces |net delta| of the whole book (longs included). | Order level. Observed share of delta-reducing sales vs the share expected if the side were chosen independently of the book at the cycle's own CE/PE mix. |
| **H2** | **Gap-asymmetry balancing:** the side reduces |asym| (equal loss to a gap up or down at the open). | Same. |
| **H3** | **Gap-loss reduction:** the sale improves `gap_worst` more than the mirror sale (other side, same distance from the forward). | Same; also the average change of `gap_worst` of actual vs mirror. |
| **H4** | **Risk-state timing (hazard):** the minute and side of a sale follow features of the book or of VWAP. | Stratified AUC within (cycle, side) blocks over the 25 window minutes; features oriented so that a larger value means more pressure to sell this side. **Curveball null** (keeps every cycle's event count and every minute's frequency), 2,000 swaps. |
| **H5** | **Target after the late phase:** the late sales leave the book more balanced than the book without them. | Cycle level. Final |delta|, |asym| and `gap_worst` with and without the late sales (prices fixed at the last minute), sign test across cycles. |
| **H6** | **Neutrality target:** the carried book's delta imbalance ratio (|delta| / gross |delta|) at the close is smaller than at 14:15. | Cycle level sign test. |

**H4 features (11):** oriented delta pressure (CE: +delta, PE: −delta); |delta|; short gamma size; vega; theta; `gap_worst`; oriented asymmetry (CE: +asym, PE: −asym); short-lot imbalance (other − same); uncovered same-side shorts; VWAP deviation oriented trend-following (CE: −dev, PE: +dev); cumulative short premium.

## Counting and decision rules
* **Primary tests: 15** = 11 hazard features (H4) + H1, H2, H3a (flag) and H3b (average gap-loss change). Benjamini-Hochberg at 10% over these 15. Secondary-window and per-era repeats are descriptive and counted in the ledger.
* **"Supported"** needs all three: (1) BH-significant; (2) a meaningful size (order-level: observed minus expected share at least **0.15**; hazard: AUC at least **0.60**); (3) the same direction in at least **60%** of cycles with three or more late orders.
* **"Explains"** a cycle: at least **70%** of its late orders (and at least 3) satisfy the flag and exceed the cycle's own chance expectation by at least 0.25. A cycle with no supported hypothesis is reported as **unexplained by book or VWAP state**.
* A hypothesis that is only *consistent* (the book ends balanced) but not *selective* (the flags do not beat chance given the side mix) is reported as consistent, not as a cause.

## Stated limits in advance
* Fewer than 20 cycles and roughly 150 late orders after 15:15: only strong effects are detectable.
* The system's own risk model is unknown; Black-76 with parity forwards is an approximation, margin and exchange limits are not modelled.
* Timestamps are fill times.
* The result is hypothesis-generating. A causal claim would need the forward recorder's pre-order state.
