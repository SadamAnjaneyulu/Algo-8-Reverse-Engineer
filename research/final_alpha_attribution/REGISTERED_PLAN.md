# Final economic study — fixed protocol

Base research revision: `12dc6af`. Strong register: version 6 at `f5b4ab8`.
Registered before the new economic comparisons and cost calculations. All dates
have already been researched; there is no researcher-blind historical sample.
This is attribution/falsification, not a controller or threshold search.

## Evidence and economic views

Independently reapply each canonical fill with Decimal arithmetic, checking cash,
position, pooled cost, open/close attribution and realised P&L against the ledger;
check every atomic book and minute marked equity against available raw quotes.
Write `DATA_QUALITY_AUDIT.md` and coverage CSV before producing economic results.
Zero before the first received fill is a reconstruction assumption. Three
expiry-only starts remain sensitivity-only; their past holdings are unknown.
Recorded fills, quote marks, model components and unpriced/residual positions
are distinct. No modeled settlement or account NAV/margin is invented.

Views: (1) received fill cash flow; (2) cash + actual stored end-candle quote marks
for residuals, with realised/unrealised distinct; (3) the same view after fixed
cost/stress assumptions. A flat received endpoint supports closed-book P&L under
initialization/completeness assumptions. A residual endpoint supports only marked,
partial observed-history economics. No complete-cycle profit is inferred from it.
Both primary 32 and all 35 are reported; primary fully flat subset is separate.

## Fixed costs and sensitivities

Currency is rupees; turnover = sum recorded quantity * price. Costs are estimates,
not an authenticated tax/broker schedule. Recorded fill prices already include
whatever spread/slippage occurred in the export. Incremental slippage below is
an explicit adverse sensitivity, not a claim the original fill was different.

| Scenario | Premium turnover | Per received parent | Per executed unit |
|---|---:|---:|---:|
| zero_diagnostic | 0 | 0 | 0 |
| moderate | 0.25% | 20 | 0.05 |
| conservative | 0.50% | 20 | 0.10 |
| adverse_execution | 0.50% | 40 | 0.20 |

Additional fixed sensitivities: incremental 0.20 per unit only on fills outside
the corresponding full minute OHLC (ex-post uncertainty flag); residual long
marks set to zero and residual short mark debits doubled, separately from base
cost stress; unknown initialization excluded or separately included. Unpriced
shorts never become zero liabilities. Exclude the largest winner / loser and
leave every cycle out. Break-even extra turnover cost is reported only for the
specified cohort/endpoint view, with parent/unit charges fixed and negative
headroom retained. No sensitivity is tuned to obtain a preferred sign.

## Attribution and risk

Role cash/realised/marked P&L: short CE, short PE, long CE, long PE; quantities
that reverse role are split at canonical closed/open amounts. Pooled attribution
is not original allocation ownership. Costs are allocated by traded quantity and
parent-first-fill fees; protectors are not automatically economically worthwhile.

Minute identity: beginning quantity * quote change plus signed trade quantity *
(end mark - recorded fill) reconciles observed equity changes where marks exist.
Split overnight previous-close -> next-open from intraday open/close changes.
Classify observed trades by opening/closing role and fixed timing, not inferred
intent. Use intermediate-exit episode labels as descriptive outcomes only.

For a limited model decomposition, fit each observed option's own implied
volatility, not a constant surface. Use the existing Black-76 model with the
same-strike CE/PE parity forward where quoted and otherwise the available spot
proxy (explicit quality flag). Symmetric three-factor Shapley changes in forward,
time and fitted IV allocate quoted movement. Primary rate zero; sensitivity rate
6%, expiry clock +/-5 minutes around the inherited convention. Retain fitting
failures, low-premium/zero-volume legs and unexplained residual. Direction's
linear delta and quadratic gamma are diagnostics within its exact nonlinear
contribution, not extra additive profits. Missing intervals are not extrapolated.
Model attribution uses endpoint information descriptively, not as trading signals.

Risk: currency P&L, complete-quote sampled intracycle drawdown/MAE, closed-cycle
cumulative-P&L drawdown in expiry order, gross short/protective quantities,
short-unit-minutes, premium exposure, and bounded frozen expiry-payoff stress
where finite. Report unbounded call-tail intervals. No verified capital return,
Sharpe/CAGR, ruin probability or extreme-tail quantile is manufactured. Report
mean of the worst five observed cycles as a small-sample descriptive tail measure.

## Benchmarks fixed before comparison

A: no trading, zero P&L/cost/exposure on each cycle.

B: observed initial basket only, a conditional benchmark. On ordinary pre-expiry
starts take the actual cash/book strictly before 09:18 (the received opening
sequence, including any earlier opening management); freeze that inventory and
perform no later allocations/management. Liquidate at expiry 15:27 for expiries
before 3 August, 15:14 afterward, at stored candle opens. Known delayed start is
excluded, not reclassified as an ordinary zero basket. Missing exit prices stay
missing. Actual opening prices/quantities are preserved; this does not test an
independent deployable strike selector. Any opening residual must be valued.

C: scheduled accumulation, a structural approximation. Three base quantities in
each role at the opening; later pre-expiry 17 recurring slots use only the pooled
modal four-role sizes frozen on June–July in the prior calibration. ATM uses the
completed reference close on 50/100 grids; each wing is selected from prior
fresh, positive-volume quotes with 2.5% leg-premium budget (SENSEX rounded to
nearest 0.10 before ceiling selection). All entries execute at the following
minute's open (09:17 after the 09:16 signal). No expiry-day additions. Exit all
at the same dated expiry deadline as B. No stops, selection on returns or
quantity changes. Quote universe is the received-contract subset. If any intended
nonzero allocation/exit cannot be priced, retain partial diagnostics and exclude
the whole cycle from a complete economic comparison; do not skip missing trades
and call the resulting thinned strategy complete. June–July cycles calibrate
sizes; only August–October test C comparisons. No incomplete-chain price is made up.

D: actual observed sequence, with descriptive role/phase/management attribution.
Two prespecified local, nondeployable counterfactuals: for each recorded
intermediate short cover / long sale before deadline, compare that executed
quantity at its fill to the same contract's price at the fixed deadline. Include
all eligible closing components, keep missing quotes/after-deadline cases, and
aggregate by cycle. This is a fixed future-mark markout, NOT a no-management
strategy: later actual entries depend on management and inferred lots overlap.
Do not add markout totals to actual P&L or claim unique causal benefit.

E: assess whether B or C admits a defensible comparable risk budget against the
actual dynamic path. Report exposure/finite-payoff ratios on common cycles, but
neither hindsight per-cycle scaling nor margin invented from premium receipts.
If risk ownership, finite tail limits or a common predetermined risk budget are
insufficient, mark E unavailable/inconclusive rather than claim equal-risk alpha.

## Inference and stopping rule

All cost comparisons use consistent formulas and common-cycle paired samples.
Report per index, phase and primary/all/flat cohorts. Whole-cycle bootstrap of
mean currency P&L and paired differences (5,000 fixed-seed draws), cycle counts,
missing cohorts, leave-one-cycle-out, winner/loser removal and profit concentration.
Trading records/contracts/windows are never independent inferential units.
Prior inspected dates, selection history and possibly shared calendar shocks
are explicit limits. Do not choose the best benchmark after observing returns.

Choose A/B/C/D research-closure verdict as requested, distinguish absolute
profitability from risk adjustment and alpha. Preserve all original findings and
selected baselines. Deliver the registered files, executable reproduction, tests
and uncertainties; then stop. No follow-up rule/controller search.
