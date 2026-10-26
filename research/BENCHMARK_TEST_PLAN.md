# Freeze the first strategy-versus-baseline test

This specification is written before computing the benchmark outcomes. Earlier
strategy outcomes have already been inspected. No claim of a blinded holdout.

## Question and cohort

Do the recorded subsequent trades improve outcomes over a timed frozen opening
hedged straddle, after explicit cost stress and a size-calibration check?

Use all 31 ordinary pre-expiry 09:16 opening cycles with both initial protective
wings. Include residual-position and loss cycles; do not select only fully flat
cycles. Exclude the three cycles without observed pre-expiry opening baskets and
5 October's delayed opening, and list them. Missing required quotes exclude the
paired cycle and remain visible. Never fill missing prices.

## Baselines, fixed now

Primary: use the same observed first sold strike and initial bought wing strikes;
buy/sell equal quantity in the four legs at the 09:16 option candle opens. Freeze
them, then mark/liquidate at the expiry 15:14 candle opens. It shares the observed
opening selector and tests the value of later trading, not the opening signal.
Wing selection was recorded seconds after 09:16; test 09:17 entry separately to
show sensitivity to that boundary and simulated execution. No future quote is
used as an entry feature.

Secondary: accumulate equal quantities of those same initial four contracts at
09:16, 09:31, ... 14:31 on the pre-expiry day (22 additions), then exit at the
same expiry time. The total final quantity equals the primary baseline's unit
quantity. This controls simple timed averaging without rolling the strike or
introducing hidden market signals. It is not a claim about the original schedule.

The actual-book comparator includes all recorded fills strictly before the same
expiry 15:14 cutoff, plus exact current-minute opening marks on residual holdings.
This is a common-time forced-liquidation estimate, not an assertion that the
actual strategy always closes then. Also test 15:25 before 3 August / 15:14 from
3 August as a disclosed, previously observed clock sensitivity. No settlement
price, missing exit or unrecorded fill is invented.

## Position size and capital

Show the frozen opening basket at its observed initial common quantity as an
unscaled diagnostic; its size does not match the growing actual book.

Primary comparative sizing: use outcomes through 31 August to match each index's
baseline cycle-P&L standard deviation to the actual book's cycle-P&L standard
deviation. Round quantities to observed quantity-GCD multiples (65 NIFTY, 20
SENSEX), which are not independently verified exchange lot sizes. Freeze those
quantities for September–October evaluation. Fit both baselines separately.
Calibration uses gross outcomes only; do not refit by cost scenario or later
profit. Report training and evaluation variability and maximum theoretical
baseline expiry losses.

The primary frozen basket uses quantity-GCD multiples. The secondary 22-addition
benchmark divides its calibrated total quantity equally across slots; those
fractions may be below a tradable lot. It is explicitly an idealized averaging
diagnostic, not a deployable independent strategy or the primary edge test.

Use the stated ₹2 crore only as a nominal common capital reference and a
baseline maximum-theoretical-loss cap. Actual historical SPAN/exposure margin,
account funding, portfolio gamma and tail capital are not supplied. Therefore
this is an approximate historical-variability match, not verified equal margin,
equal tail risk or proof of risk-adjusted alpha.

## Costs and execution assumptions

Primary stress: 25 basis points of premium turnover, ₹20 per distinct recorded
order (or simulated leg order), plus ₹0.05 per transacted option unit. Apply
the per-unit term symmetrically as extra execution stress; actual fills already
contain their realized execution prices. Count hypothetical cutoff-liquidation
orders/units/turnover too. Baselines assume no depth/size impact.

Also show gross; low stress (10 bps, ₹20/order, no extra per-unit stress); and
high stress (50 bps, ₹20/order, ₹0.10 per unit). These are disclosed hypothetical
all-in proportional-fee stresses plus brokerage and extra execution stress,
not reconstructed tax rates, broker invoices or verified historical net P&L.
Do not select the cost scenario producing the preferred conclusion.

## Evaluation and uncertainty

September–October is chronological evaluation after calibration, but has been
seen in earlier research. Report paired P&L differences, cycle counts, losses,
turnover, order counts and dispersion. Cluster both indices by expiry ISO week
for a fixed-seed 10,000-resample paired bootstrap of mean improvement; do not
treat child orders or minute bars as independent observations. Show excluded
cycles and sensitivity outcomes. Small samples, shared selectors, possible
execution-time errors and unverified costs limit repeatability claims.

## Supplemental control, added after inspecting the first comparison

Also test the frozen basket with an explicit ₹200,000 cycle-loss stop monitored
on expiry day only. This is an exploratory additional control, not a promoted
primary hypothesis or a claim about the note's unspecified loss reference.
Use the already calibrated frozen quantities without refitting. Check the 09:15
open and then completed minute closes; act at the following minute open. Close
the basket at 15:14 if no stop fires. Never fill at an intraminute threshold price.
Reject a cycle when a required monitoring/execution quote is absent. Compare
against the same recorded-book outcome at 15:14, and disclose this control's
separate cohort. Costs use the same predefined scenarios. Stops cannot guarantee
tail loss or compensate for unobserved quotes/depth.
