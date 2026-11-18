# Why Algo 8 repeatedly builds positions

**The strongest explanation is a planned ladder of protected short-premium
allocations, spread across entry times and refreshed strikes.** The repeated
entries mostly add exposure. They are not simply replacing stopped positions
or neutralizing the existing portfolio. This describes the observable mechanism;
it cannot establish the original author's intent or that 15 minutes is optimal.

## Direct tests of the competing explanations

The sample contains 544 recurring pre-expiry windows: 17 windows on each of
32 observed sessions. Windows run from two seconds before the nominal time to
three minutes after it, allowing for execution timing. They are not every
quarter hour throughout the session: for example, 12:15, 12:45 and 13:00 are
usually absent. Other additions occur outside these recurring windows.

| Observation | Result | Implication |
| --- | ---: | --- |
| No short covers or long sales in the preceding 15 minutes | 400/544 (73.5%) | Most additions do not require a recent reduction to replace. This does not exclude older exits. |
| Total short quantity grows across the window | 530/544 (97.4%) | Exposure generally accumulates. |
| Earlier short and long exposure necessarily survives | 544/544 each | A scheduled entry is not a universal close-and-reopen of the earlier basket. |
| New outward protection is bought within the window | 543/544 (99.8%) | Fresh selling is normally accompanied by protection; this alone does not prove equal hedge quantities or fixed basket identities. |
| Modeled theta increases | 531/543 (97.8%) | Additions usually increase exposure to time decay. |
| Modeled Vega becomes more negative | 533/543 (98.2%) | They usually increase exposure to rising IV. |
| Modeled Gamma becomes more negative | 533/543 (98.2%) | They usually increase sensitivity to large underlying moves. |
| Absolute modeled portfolio Delta decreases | 178/543 (32.8%) | Most windows are not simple portfolio Delta neutralization. |

Greek comparisons freeze the same pre-window prices, forward and time for the
before/after inventories. The quote bar starts two minutes before the clock
time and completes a minute before it. This isolates the effect of trades from
concurrent market movement. Each risk change is checked against the modeled
risk of the signed trade vector. One window lacks full model coverage. Greeks
are estimates from minute trade candles, not contemporaneous executable quotes;
low premiums and stale/zero-volume bars can affect them. Theta exposure is not
a guaranteed realized profit, and protection does not eliminate these risks.

## Why use fresh strikes repeatedly?

At each window we compare matched new same-strike CE/PE short quantities with
the initial session strike, using the same preceding market snapshot:

- The weighted new strike is closer to the then-current modeled forward in
  **364/544 windows (66.9%)**; equally distant in 82 and farther away in 98.
- The new pair has more remaining time value than the original-strike pair in
  **366/544 windows (67.3%)**. Time value here is CE + PE minus the absolute
  difference between the forward and strike, using the primary zero-rate model.
  This compares short pairs, not net protected-basket profits or hedge costs.
- These quantities concern matched CE/PE pairs; unmatched additions and
  different-strike CE/PE allocations are outside that pair comparison.

This supports **replenishing near-ATM time-value exposure as spot moves**, while
spreading entry prices over time. It does not mean repeatedly selling the
original ATM strike or closing every earlier allocation. It also does not mean
that all new baskets are exactly ATM or that every window improves positioning.

For example, on 13 July, NIFTY initially shorts 195 units each of 24000 CE/PE,
protected by 195 units each of 26000 CE and 22000 PE. At the 09:30 window it adds
130 units each of **24050 CE/PE**. At 09:33 all four original holdings still
exist, and total short quantity has risen from 390 to 650. The next window
raises total short quantity further to 1,105; side-specific closures follow.
The initial CE cover sequence and surviving PE are documented separately in
`POSITION_LIFECYCLE_CLARIFICATION.md`.

## What actually gates these recurring additions?

Pre-window conditions vary substantially:

| Feature | Positive | Negative | Zero | Available |
| --- | ---: | ---: | ---: | ---: |
| Spot return over preceding five minutes | 273 | 271 | 0 | 544 |
| Reference straddle premium change over preceding five minutes | 227 | 309 | 6 | 542 |
| Estimated IV change over preceding 15 minutes | 184 | 328 | 0 | 512 |
| Whole-book equity before costs | 304 | 239 | 0 | 543 |

Thus these recurring windows fire after rises and falls, premium increases and
decreases, IV increases and decreases, and while the book is in profit or loss.
Simple directional or sign-only gates cannot explain them. This does not rule
out an untested eligibility threshold that every observed session happens to
satisfy; no-trade calendar days remain incompletely labeled.

The common normalized size schedule on NIFTY and SENSEX further supports a
preconfigured allocation mechanism. Individual windows can contain multiple
orders and additional state-dependent flow. A timer could drive one controller
or several overlapping timed modules; the logs cannot uniquely distinguish them.
Expiry-day entries have different active-book dependence, so the 544-window
pre-expiry result should not be generalized to unconditional expiry-day selling.

## Does the ladder itself create alpha?

The existing controlled experiment compares repeated fresh-ATM entries against
repeated entries in the original contracts, with equal intended total quantity
and consistent child-order fee assumptions. In the later common quote-complete
sample, fresh ATM improves NIFTY results but worsens SENSEX results. Weekly
intervals for the difference include zero for both indices and exit horizons.
These strategies do not have equal dynamic risk or margin. Only six later
cycles per index are common, and the NIFTY common cohort omits the largest
overnight opening-basket loser in the broader sample. See
`ALPHA_CANDIDATE_FINDINGS.md` and `alpha_staggered_recentering_comparison.csv`.

**The most defensible reason for the repeated entries is gradual construction
of a protected short-volatility book, with fresh time-value exposure at updated
strikes.** Fifteen minutes is an observed scheduling choice. Its superiority
over ten or thirty minutes, the exact allocation controller, and excess returns
after comparable risk remain unproven.

Reproduce the focused descriptive checks with:
`python research/analyze_building_rationale.py`.
Outputs: `building_rationale_windows.csv`, `building_rationale_summary.csv` and
`building_rationale_conditions.csv` in `research/outputs/`.
