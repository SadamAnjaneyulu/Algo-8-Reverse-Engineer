# Testing the range, theta and IV explanation

**The explanation is partly supported.** The observed opening books have the
expected time-decay benefit and exposure to IV and sharp movement. Initial OTM
wings provide protection, but the later orders have different jobs: many add
premium-selling risk, while large late hedges usually reduce it. The evidence
does not identify a universal IV-triggered adjustment/exit rule or establish alpha.

These are **model estimates fitted to actual minute candles**, not exchange
Greeks, observed India VIX, synchronous bid/ask quotes or proof of the original
program's intent. The study specification is `IV_THETA_TEST_PLAN.md`.

## 1. Opening-book behavior matches the basic hypothesis

Reconstruct the complete opening-minute inventory, including multiple strikes,
then value its exposures at the completed 09:16 candle. All **31/31 ordinary
opening books** are successfully modeled and have:

| Exposure | Sign in the modeled opening books | Plain-language meaning |
| --- | --- | --- |
| Net theta | Positive, 31/31 | Time passing helps if forward and IV stay fixed |
| Net Vega | Negative, 31/31 | A parallel IV increase hurts the book, all else equal |
| Net gamma | Negative, 31/31 | A sharp move can hurt even if IV stays unchanged |

This supports a range-friendly premium-selling exposure. It does not prove that
the original strategy forecasts a range or uses a range indicator before entry.

The initial longs do not make the book IV-neutral. Their median offset of the
short core's modeled IV sensitivity is approximately **2.2% for NIFTY**, **2.8%
for the earlier SENSEX cohort**, and **15.3% for the later, closer-wing SENSEX
cohort**. These are local model sensitivities, not percentages of maximum-loss
protection. Far OTM wings can cap terminal tail losses in matched baskets while
leaving substantial nearby movement/IV risk.

The actual carried inventory at the prior option-session close is also net short
Vega in all **31/31** modeled carry books. Late hedging changes its magnitude;
it does not eliminate IV risk in these recorded end-of-day books.

## 2. IV is not the only risk

A fixed-IV model counterexample is useful because it separates the mechanisms.
This is an **illustration, not a recorded trade**:

- One unit short 24,000 CE and PE; long 26,000 CE and 22,000 PE.
- Forward moves from 24,000 to 24,240 (+1%).
- Time remaining falls from one calendar day to one-quarter day.
- IV remains exactly 20% at both endpoints.

The modeled basket loses approximately **₹42.32 per unit**, despite a positive
time component of about ₹71.82. Forward movement contributes about −₹114.14;
the IV component is zero. Consequently an IV rise is not necessary for a hedged
short straddle to lose. These factor allocations use the specified symmetric
pricing decomposition and are not directly observed separate cash flows.

Premium received at entry is also not immediate profit: it comes with the
short-option liability. For a fully closed basket, profit depends on short
buyback costs, long-option spending/recovery and charges as well as the credit.

## 3. New short allocations and defensive hedges behave differently

Group actual fills by event minute. Estimate the book immediately before and
after the whole minute's inventory change at the **same previous completed
market state**. This isolates the exposure change from a simultaneous IV move.
An event can contain shorts, buys and covers; these are minute batches, not
independent child orders or asserted strategy modules.

| Cohort | Fully modeled event minutes | More short Vega after the batch | Lower absolute Vega after the batch |
| --- | ---: | ---: | ---: |
| Pre-expiry paired short additions | 996 | 970 (97.4%) | 26 (2.6%) |
| Expiry paired short additions | 989 | 931 (94.1%) | 53 (5.4%) |
| Pre-expiry large late long-adjustment minutes | 37 | 3 | 34 (91.9%) |

Every modeled paired-addition batch starts net short Vega. Thus the predominant
effect of the first two cohorts is to **add IV exposure**, not reduce it. The
large-late cohort generally does reduce IV sensitivity. The 37 late minutes
cover 39 descriptive large long groups and are not a universal hedge schedule.

This result survives removing event cases with any zero-volume or <=0.10-price
active leg: 630/653 pre-expiry paired batches and 777/829 expiry paired batches
still add short Vega; 33/35 qualifying large late batches reduce absolute Vega.

Therefore “every extra order is there to manage an IV rise” does not describe
the observed exposure changes. A more plausible decomposition is additional
premium-selling allocations plus separate protective adjustments. The decision
logic behind either remains unresolved.

## 4. IV rises do not explain all additions

Use the current selected strike at both ends of the preceding 15-minute window,
so an ATM-strike switch is not automatically treated as an IV change. A one-point
rise means, for example, 20% to 21%; it is a descriptive threshold, not an
inferred parameter.

| Cohort | Usable preceding IV windows | IV flat/down | IV up at least one point |
| --- | ---: | ---: | ---: |
| Pre-expiry paired short-addition minutes | 990 | 611 (61.7%) | 10 (1.0%) |
| Expiry paired short-addition minutes | 976 | 437 (44.8%) | 157 (16.1%) |
| Large late hedge minutes | 37 | 25 (67.6%) | 0 |

The strategy therefore frequently adds shorts and buys large protection without
a preceding IV rise in this proxy. This rejects an IV-rise-only explanation;
it does not rule out a combined clock, risk-state, price, volatility or liquidity
decision. Repeated observations within cycles are not independent trials.

## 5. Loss exits: association requires a control

Eleven fully closed negative-cashflow carry cycles have a terminal material
short reduction before 15:00. Their estimated near-ATM IV is higher than at the
previous option close in all eleven cases. Eight use strictly preceding
completed candles; three 09:15 cases use opening-price proxies and do not prove
subminute chronology.

However, IV is also higher in **every one of the 134 matched still-active
same-index/same-clock control comparisons**. Those are repeated comparisons,
not 134 independent cycles. Some loss exits have unusually large rises relative
to controls, while others do not. “IV is up from yesterday” is not a sufficient
discriminator or an identified stop instruction.

Annualized model IV can rise overnight simply because the calendar time to
expiry shrinks faster than the option's remaining uncertainty is priced to
shrink. This is one reason to avoid calling every such rise an exogenous
volatility shock. Smile/moneyness, stale/asynchronous candles and forward
selection can also affect the proxy.

## 6. What the overnight price attribution can support

Freeze the **actual end-of-pre-expiry inventory**, comparing final option-session
closes with expiry opening prices before fills. Infer per-leg IVs under the
specified Black model, then average all six orderings of changes in time,
forward and IV. The fitted components reconcile to the endpoint price change.

All 31 carry books have endpoint prices; **24 have complete model fits**. Within
those 24 modeled cases:

| Estimated component | Total across the modeled subset |
| --- | ---: |
| Calendar-time effect | +₹24.14 lakh |
| Forward-movement effect | −₹1.51 lakh |
| Per-leg IV repricing effect | −₹11.56 lakh |
| Combined observed overnight marked change | +₹11.07 lakh |

Time contributes positively in 24/24 cases, and the modeled IV repricing effect
is negative in 21/24. Discount-rate and ±5-minute expiry-anchor sensitivities
leave those signs/counts unchanged. This is consistent with carry collection
being offset by movement and volatility/surface repricing.

**Do not treat that selected subtotal as strategy profit or proof of an edge.**
The seven incomplete model cases have −₹5.85 lakh combined observed overnight
price change, including important loss cases. Across all 31 endpoint-priced
carry books the observed overnight change is +₹5.22 lakh before costs. Failure
to model some adverse cases makes economic generalization from the 24-case
decomposition particularly unsafe. The entire active-cycle P&L is a different
quantity and includes intraday trades.

The attempted full-holding-period frozen-opening-basket decomposition is retained
as a **diagnostic only**. Expiry far-wing prices near the tick floor imply
unstable IV and very large counterfactual time/IV offsets; changing the assumed
expiry anchor changes those component totals substantially. Those figures must
not be used to claim a precise full-strategy theta contribution. Calendar-time
versus trading-time conventions also affect overnight allocations.

## 7. Corrected working explanation

The observed structure is compatible with **calendar-based near-expiry premium
selling, additional short allocations, protective changes and position/portfolio
exits**. Time decay is favorable locally; sharp movement, IV/surface repricing
and execution costs are material opposing risks. Buying OTM options reshapes
risk rather than making it disappear.

The exposure evidence supports that explanation. It does not prove a range
forecast, an IV-triggered state machine or repeatable alpha. Positive theta and
negative Vega are normal exposures of premium selling; they do not establish
that options were mispriced or that the adjustments outperform a risk-comparable
baseline. The previous benchmark's limited, index-dependent findings remain.

## Reproduce and inspect

```sh
python research/analyze_iv_theta_hypothesis.py --plot
python research/test_option_pricing_model.py
```

`research/outputs/` contains opening/carry exposures, every modeled event batch,
early-loss observations and matched controls, endpoint attribution with coverage
flags, model sensitivities, full summary and PNG/SVG plots. All required CSV quote
files are verified against their metadata hashes. Original data are unchanged.
