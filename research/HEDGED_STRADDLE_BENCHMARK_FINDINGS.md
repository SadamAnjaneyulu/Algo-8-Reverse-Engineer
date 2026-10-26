# First benchmark result: incremental edge is not established overall

The comparison is complete. **The recorded later trading is not shown to have a
repeatable incremental advantage overall.** SENSEX is a promising lead in this
sample; NIFTY's later trading underperforms the frozen opening-basket benchmark.
The later combined period improves, but uncertainty includes no advantage and
the earlier combined period reverses the result.

This tests the value of trading **after the shared opening selection**. It does
not test whether the opening calendar/strike selector itself has alpha.

## What was compared

Primary baseline: take the same initial short CE/PE and protective wing strikes,
enter equal quantities at the 09:16 candle opens, then leave them unchanged
until the expiry 15:14 candle opens. Compare with every recorded strategy trade
before that same cutoff, marking remaining holdings at the cutoff opens.

The strategy need not have closed at 15:14 in reality. This is a common-time
liquidation estimate so later trading is compared over the same horizon.
Residual positions are not dropped merely because the logs do not close them.

Thirty-one ordinary 09:16 cycles were eligible. Two lack exact baseline exit
wing quotes: NIFTY **29 September and 13 October**. They are excluded from both
sides of the primary comparison, leaving **29 paired cycles**. These exclusions
can matter materially and are not assigned zero wing value. Three cycles without
observed pre-expiry opening baskets and 5 October's delayed opening are outside
the defined cohort. All exclusions are exported.

## Size and risk: approximate, with quantities fixed before evaluation

Use **18 June–August cycles** to calibrate the baseline's outcome variability,
separately for each index. Do not fit its profit. Freeze quantities for
September–October:

| Baseline index | Calibration cycles | Fixed quantity per leg | Actual calibration P&L SD | Baseline calibration P&L SD |
| --- | ---: | ---: | ---: | ---: |
| NIFTY | 8 | 2,600 | ₹187,892 | ₹185,902 |
| SENSEX | 10 | 680 | ₹201,228 | ₹200,433 |

These quantities avoid comparing the entire growing strategy with just its tiny
initial allocation. They are rounded to observed quantity-GCD multiples, not
independently verified exchange lot rules.

On the **11 September–October evaluation cycles**, after the primary cost stress,
actual versus frozen-baseline cycle variability is also close: approximately
**₹224,535 versus ₹220,636**. But equal historical variability is not equal
historical margin, gamma or tail loss. Actual margin/funding records are absent.
For example, modeled baseline maximum expiry loss can reach about ₹48 lakh in
NIFTY at this size. The stated ₹2 crore is a nominal capital reference/gross-loss
cap, not proof that the two books consume equal risk capital. That cap never binds.

## Results under the predefined primary cost stress

All amounts below include hypothetical costs: **25 bps of premium turnover,
₹20 per distinct order, and ₹0.05 per transacted unit**. Actual fills already
contain their recorded execution prices; the per-unit term is additional stress
applied symmetrically. These are not reconstructed broker invoices or audited
historical net returns. Forced cutoff-liquidation turnover/orders are included.

| Period | Paired cycles | Recorded strategy | Frozen baseline | Recorded minus baseline |
| --- | ---: | ---: | ---: | ---: |
| June–August calibration | 18 | +₹2.70 lakh | +₹13.40 lakh | **−₹10.69 lakh** |
| September–October evaluation | 11 | +₹1.81 lakh | −₹5.40 lakh | **+₹7.21 lakh** |
| All usable cycles, descriptive only | 29 | +₹4.51 lakh | +₹8.00 lakh | **−₹3.49 lakh** |

The full-sample line includes calibration and must not be described as unseen
performance. The evaluation period has also been inspected in earlier research;
it is a chronological check, not a blinded holdout.

## The useful lead is the index split

| Index | June–August improvement | September–October improvement | Evaluation cycles where recorded strategy is better |
| --- | ---: | ---: | ---: |
| NIFTY | −₹18.10 lakh over 8 cycles | −₹4.49 lakh over 4 cycles | 1/4 |
| SENSEX | +₹7.41 lakh over 10 cycles | +₹11.70 lakh over 7 cycles | 6/7 |

The point estimates favor SENSEX in both periods and NIFTY in neither. This does
not establish that SENSEX has repeatable alpha or that NIFTY can never have it;
the samples, benchmark and risk assumptions are limited. Combining the indices
would conceal a useful distinction.

The evaluation's average combined advantage is **₹65,515 per cycle**, but a
10,000-resample bootstrap, clustered by expiry week, gives an approximate 95%
interval of **−₹132,268 to +₹282,419**. It crosses zero. There are only **eight
expiry-week clusters**. SENSEX alone also crosses zero: approximately −₹21,280
to +₹365,925 per cycle, over seven cycles.

Recent gains are concentrated: removing expiry week 37 makes the combined
evaluation advantage negative (about −₹1.25 lakh total). A favorable recent
aggregate is therefore insufficient to call this repeatable.

## Sensitivities

On the same 11-cycle evaluation cohort, recorded-minus-frozen advantage is:

| Cost assumption | Total advantage |
| --- | ---: |
| Gross, no modeled costs | +₹10.05 lakh |
| Low stress | +₹7.83 lakh |
| Primary stress | +₹7.21 lakh |
| High stress | +₹6.35 lakh |

All corresponding weekly uncertainty intervals include zero. Delaying the
baseline entry to 09:17 leaves a +₹6.42 lakh point estimate under primary costs;
uncertainty still includes zero. The disclosed historical late-exit-clock
sensitivity also does not establish an advantage.

The 22-addition averaging diagnostic has +₹4.90 lakh evaluation advantage under
primary costs over **nine** paired cycles, with uncertainty crossing zero.
Its cohort differs because additional entry quotes are required, and it uses
fractional per-slot quantities. It is not an executable lot schedule or a reason
to select a preferred benchmark after seeing outcomes.

## Additional simple-stop control

After inspecting the primary comparison, an exploratory frozen-basket control
was added with a **₹200,000 cycle-loss stop monitored on expiry day**. Quantities
were not refitted. It checks the 09:15 open and completed-minute marks, executing
at the next available minute boundary's open. It never fills at an invented
threshold price; gaps can cause overshoot. This is a specified candidate, not a
claim that it matches the original note's unspecified stop basis.

Six cycles fail required monitoring quotes, leaving a separate **14 calibration /
9 evaluation** cohort. On those nine evaluation cycles, under primary costs:

| Comparator | Total estimated outcome |
| --- | ---: |
| Recorded strategy at common cutoff | +₹5.37 lakh |
| Frozen baseline, no stop, identical nine-cycle cohort | −₹9.42 lakh |
| Frozen baseline with the simple expiry-day stop | −₹10.19 lakh |

Recorded-minus-stopped advantage is +₹15.56 lakh, but its weekly interval still
crosses zero (about **−₹57,769 to +₹351,668 per cycle**). The bigger point estimate
than the primary result largely reflects the changed cohort; it must not be
presented as a stronger result on the same eleven cycles. This post-inspection
control does not establish repeatability either.

## Interpretation for the alpha investigation

The logs show that both days contain additions and risk changes, not simply four
orders left untouched and four closing orders. This test measures the combined
effect of those later decisions, trading costs and exits. It does not prove the
intention behind each order or identify a unique trigger.

The strongest next hypothesis is that the later decision rules behave differently
across NIFTY and SENSEX. Decompose entry additions, short-strike changes, wing
changes and exit timing separately, and test the resulting rules on genuinely
unseen periods. Costs, option-depth/quote-side execution, historical margin and
residual inventory reconciliation remain necessary before a deployable alpha
claim. The supplied earlier-period backtest screenshot is not reproduced here.

## Reproduce and audit

```sh
python research/benchmark_hedged_straddle.py --plot
python research/test_hedged_straddle_benchmark.py
```

`BENCHMARK_TEST_PLAN.md` records the primary choices and identifies the later
supplemental stop test. Quote files are checked against their recorded hashes.
The underlying option dataset was independently reproduced from all 9,729 raw /
CSV / metadata paths in the preceding stage.

Outputs under `research/outputs/` contain every paired cycle/cost/timing outcome,
initial-size diagnostic, exclusions, simple-stop control, full machine-readable
summary and PNG/SVG charts. Tests cover strict cutoff accounting, order-versus-
fill counting, missing quotes, four-leg signs, size calibration, costs, weekly
sampling units and stop execution without threshold-price fabrication.
