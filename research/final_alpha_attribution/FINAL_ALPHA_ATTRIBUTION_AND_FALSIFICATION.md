# Algo 8 — final alpha attribution, economic falsification and research closure

**Closure outcome B: positive raw/marked results under some assumptions, but no
demonstrated economic alpha.** The initialized 32-cycle sample has gross quoted
endpoint P&L of **₹1,894,355.50**. It remains positive after
moderate and conservative estimated costs, but is negative under the adverse
execution-cost scenario. The mean-cycle uncertainty includes zero, the conservative
profit almost disappears without the largest winner, and comparable-risk alpha
cannot be established. This is not a verified account return or a recovered rule set.

**Research is closed.** This finite study adds no controller, indicator bank or
threshold search. Existing findings, experiment counts and selected models remain
unchanged. The data do not reproduce the screenshot's March 2025–May 2026 backtest.

## 1. Accounting boundary and the three economic views

The [quality audit](DATA_QUALITY_AUDIT.md) was written before new economic comparisons.
Independent Decimal arithmetic verifies **41,421 children / 39,874 parents** and
**21,882 atomic books**; raw quotes independently reconcile all available canonical
minute marks. All 35 endpoint books can be priced with stored quotes; **none uses
modeled liquidation prices**. There are 24 flat received books and 11 residual
books. Primary inference uses the 32 pre-expiry starts; the three expiry-only
starts remain a sensitivity cohort. Even the primary reconstruction assumes zero
before each contract's first fill and cannot certify export completeness.

Primary 32-cycle accounting, in rupees:

| View / component | Amount | Interpretation |
| --- | ---: | --- |
| Received fill cash flow | 2,065,205.25 | Receipts less purchases; includes open liabilities |
| Gross realised P&L | 1,371,078.56 | Canonical pooled-cost closing attribution |
| Marked unrealised P&L | 523,276.94 | Residual mark minus reconstructed remaining cost |
| Combined quoted endpoint P&L | 1,894,355.50 | Realised + unrealised = cash + residual market value |

These are alternative/reconciling views, not amounts to add together. Observed
prices include whatever execution occurred; quote marks do not certify liquidation,
settlement or post-export holdings. Two cycles lack expiry-day fills. Zero-volume
candles, missing intermediate marks and the traded-contract-only chain remain
explicit in [coverage](data_quality_and_coverage.csv) and [residual positions](residual_position_ledger.csv).
No verified NAV, margin, broker charges or full bid/ask history is available.

[Per-cycle economics](cycle_economic_results.csv), [immutable audit](input_audit.json).
Reverse same-second ordering can alter realised/unrealised attribution, as the
prior audit documented, while preserving cash and net economic value. Original
allocation ownership is not inferred from pooled costs.

## 2. Fixed costs, residual stress and absolute profitability

The [registered protocol](REGISTERED_PLAN.md) and [implementation clarifications](BENCHMARK_AND_MODEL_CLARIFICATIONS.md)
precede comparisons. Turnover charges apply to option premium turnover, **not**
underlying notional; parent/unit charges apply to executed requests/units. They
are estimated all-in charges plus explicitly adverse incremental execution
allowances, not an authenticated historical tax/broker schedule. Additional
slippage is a sensitivity on top of recorded prices, not a rewritten fill.

| scenario | turnover_pct | parent_fee | per_unit | primary32_net | all35_sensitivity | flat22_net |
| --- | --- | --- | --- | --- | --- | --- |
| zero_diagnostic | 0.00 | 0.00 | 0.00 | 1,894,355.50 | 2,616,928.00 | 207,230.50 |
| moderate | 0.25 | 20.00 | 0.05 | 821,401.08 | 1,421,781.94 | -437,695.96 |
| conservative | 0.50 | 20.00 | 0.10 | 475,346.65 | 1,024,115.89 | -673,382.41 |
| adverse_execution | 0.50 | 40.00 | 0.20 | -477,316.85 | -52,525.11 | -1,237,749.41 |

The **22 initialized books that actually end flat** have gross P&L of
₹207,230.50, and are negative after moderate/conservative
costs. This is an important sensitivity, not an unbiased alternative sample:
leaving residual options is related to the strategy's trading outcome, and the
subset discards profitable residual books too. Conversely, positive marked
results on residual books are not verified closed-cycle profits.

Setting residual long marks to zero and doubling short mark debits leaves primary
conservative net **₹301,908.90**. This is a fixed quote/liability stress,
not a worst-case bound or actual settlement. Adding ₹0.20/unit only to fills
outside/without their candle OHLC leaves conservative net **₹467,365.65**;
that ex-post discrepancy flag does not prove a recorded fill was impossible.

With parent fees fixed at ₹20 and unit allowance at ₹0.05, primary quoted P&L
breaks even at **1.131%** of premium
turnover. That threshold is conditional on those fixed charges and endpoints;
it is not a fee schedule or a universal capacity estimate. Doubling parent fees
and raising unit allowances changes the result materially.

[All cost views](cost_stress_results.csv), [risk/robustness statistics](risk_and_drawdown_summary.csv).
There is no financing/margin record; overnight funding and opportunity costs are
not silently assumed known. No precise CAGR, Sharpe or verified capital return
is calculated from the supplied ₹2 crore reference.

## 3. Direct contributions: rights, protection and phase

These role contributions reconcile to the same gross endpoint result. Positive
option receipts alone are not counted as profit; repurchases, wing purchases,
closing proceeds and residual liabilities are included.

[Initial-prefix, later-allocation and closing cash-flow cuts](flow_and_holding_attribution.csv)
also report quantity-weighted FIFO/LIFO holding ages, including overnight calendar
time. They are book-matching sensitivities, not recovered allocation ownership;
inventory-opening flow is not automatically an intended new basket.

| role | economic_pnl | moderate_cost | moderate_net |
| --- | --- | --- | --- |
| long_CE | -485,371.50 | 187,182.39 | -672,553.89 |
| long_PE | -351,389.50 | 162,835.64 | -514,225.14 |
| short_CE | 3,618,523.50 | 390,389.11 | 3,228,134.39 |
| short_PE | -887,407.00 | 332,547.28 | -1,219,954.28 |

Short CE contributes ₹3,618,523.50; short PE contributes
₹-887,407.00. Long-call and long-put protection together contribute
**₹-836,761.00 gross**, before their allocated fees.
This measures the price of the protection that was actually traded. It does not
show that removing it was feasible, prudent or equally risky. A bounded frozen
payoff is not proof that wings paid for themselves economically, and this small
sample cannot value insurance against unobserved tails.

[Protection by strike/right/cycle](protection_contract_contributions.csv) separates
received long closures from quoted residual protection. Residuals are never
labeled “held through verified settlement.” Original basket ownership remains
unknown; original allocation-level profits cannot be recovered reliably.

Phase accounting uses pre-expiry end quotes, actual carry quantity marked from
previous close to expiry open, then the expiry-day remainder:

| phase | gross_pnl | moderate_net | conservative_net |
| --- | --- | --- | --- |
| expiry | 395,985.50 | -359,677.17 | -586,739.84 |
| overnight | 522,049.25 | 522,049.25 | 522,049.25 |
| preexpiry | 976,320.75 | 659,029.00 | 540,037.25 |

All 32 primary phase rows are retained; each cycle's
three phases reconcile to its marked endpoint. Overnight has no assigned
transaction charge, not a verified zero funding cost. Costs are charged when
received trades occur. Expiry-day gross gains become negative after estimated
costs in this sample. This is descriptive accounting, not a hindsight decision
to avoid the entire expiry phase.

[Phase distributions and cycle bootstrap intervals](phase_distribution_summary.csv).

## 4. Direction, convexity, time and IV: model estimates with residuals

The limited model fits each option's **own endpoint IV** using the existing
European Black framework. It does not assume a constant surface. Primary forwards
use a same-strike parity proxy when adequate paired quotes exist, otherwise a
flagged spot proxy. Surface movements, basis, synchronization and model error can
therefore enter the fitted IV term; this is not an independently observed causal
volatility shock. Nonpositive time, intrinsic/low-premium failures, missing prices
and zero-volume endpoints are not silently fitted.

For the primary 32-cycle attribution, **94.4%** of active contract intervals
fit, covering **95.9%** of absolute quoted price movement. These percentages
are not percentages of net profit explained. On the full primary model-valid cut:

| Additive component | Rupees |
| --- | ---: |
| Forward/directional repricing, nonlinear | -5,899,047.52 |
| Time change | 8,765,043.42 |
| Own-IV / surface repricing | -1,923,276.90 |
| Trade price to bar-end mark bridge | 110,284.50 |
| Unexplained/unfitted/gap residual | 841,352.00 |
| Total observed marked gross | 1,894,355.50 |

The bridge includes within-minute movement and marking differences, **not**
identified execution alpha. The residual is material and is not renamed alpha.
Within direction, the linear delta diagnostic is ₹426,317.96
and quadratic gamma is ₹-6,279,137.82; the remaining
higher-order/interaction term is ₹-46,227.66.
These sum to direction and must not be added again to the table. Estimated time
carry is strongly offset by convexity/directional losses and IV repricing; positive
theta alone does not establish a profitable signal or risk-adjusted excess return.

Model sensitivity on **identical common fitted intervals**, without selecting a
preferred variant on returns:

| model | modeled_direction_pnl | modeled_time_pnl | modeled_iv_surface_pnl |
| --- | --- | --- | --- |
| expiry_5min_earlier | -5,277,172.95 | 8,846,652.70 | -2,231,071.76 |
| expiry_5min_later | -5,277,144.82 | 8,076,925.70 | -1,461,372.87 |
| primary | -5,277,134.93 | 8,427,807.09 | -1,812,264.16 |
| rate_6pct | -5,277,115.79 | 8,426,891.78 | -1,811,367.99 |
| spot_only_forward | -4,467,599.79 | 8,688,376.90 | -2,882,369.11 |

The rate, expiry-clock and spot-only-forward changes materially reallocate
components. Common-fit sensitivity and primary-own coverage are different cuts;
neither is extrapolated to unfitted periods. All variants preserve unexplained
residuals and reconcile to the same observed economic endpoint. [Cycle/role
components](cycle_pnl_decomposition.csv), [interval ledger](attribution_interval_ledger.csv.gz),
[phase components](model_phase_components.csv). Direct role, phase and modeled
contributions are alternative cuts of one P&L, not independent profits.

## 5. Intraday management: observed effects versus counterfactuals

[Observed closing components](management_realised_components.csv.gz) attribute
pooled realised cash/P&L to intermediate short covers, long sales and final/late
flow. These outcomes do not identify a stop or prove management added value.

The prespecified local counterfactual compares each eligible intermediate closing
quantity with a close at the **fixed expiry deadline**, retaining missing quotes
and after-deadline exclusions. Primary-cycle gross markout results:

| index | category | cycles | eligible_priced_components | mean_cycle_markout | bootstrap_mean_low95 | bootstrap_mean_high95 |
| --- | --- | --- | --- | --- | --- | --- |
| NIFTY | intermediate | 15 | 3737 | -65,523.25 | -290,443.96 | 197,251.29 |
| NIFTY | intermediate_long_sale | 15 | 1939 | 4,691.05 | -31,171.85 | 28,204.61 |
| SENSEX | intermediate | 17 | 5422 | 66,407.12 | -175,384.95 | 318,164.41 |
| SENSEX | intermediate_long_sale | 17 | 2674 | 5,167.24 | -21,572.05 | 23,552.13 |

Their cycle intervals include zero. They are **not** an additive no-management
backtest: later entries depend on earlier reductions, the same pooled exposure
can be recycled, and original allocation ownership is unknown. The future
reference clock is fixed, not hindsight-chosen, but these are still nondeployable
local comparisons. No markout is added to actual profit. Replacements/re-entries
cannot be assigned a unique causal profit without their missing decision IDs.

[Complete markouts](management_fixed_markouts.csv.gz), [all counterexamples](attribution_counterexamples.csv).

## 6. Fixed benchmarks and why alpha comparison remains inconclusive

- **A — no trading:** zero cash, costs and risk; tests absolute profit only.
- **B — initial basket:** preserve the actual ordinary opening sequence strictly
  before 09:18, then freeze it until the fixed expiry exit. This conditions on
  observed opening choices; it is not an independently recovered selector.
- **C — scheduled accumulation:** three-base opening, the frozen June–July modal
  17-slot pre-expiry sizing schedule, prior-reference ATM and routine 2.5%-budget
  wings, following-minute-open fills. No expiry additions or stops. Only August–
  October compares its fixed schedule; missing intended trades invalidate a
  complete cycle rather than create a profitable skipped trade.
- **D — observed sequence:** principal results retain all received trades and
  residual endpoint marks. Paired B/C comparisons instead use **D_common_clock**,
  actual cash/book strictly before the common deadline, hypothetically closed at
  that candle open. This is modeled execution, not a recorded final fill.
- **E — equal risk:** unavailable as a defensible alpha test. Starting capital,
  margin, dynamic limits and original risk ownership are unverified; common
  contract universe or clock does not create a common risk budget.

B/C exits are fixed at 15:27 for expiries before 3 August, 15:14 afterward.
Simulated entry/exit requests pay one parent per base unit, with an irregular
remainder rounded up. Actual prefixes keep actual parent charges. No benchmark
parameter is optimized on returns. Actual fills retain their own execution
prices; candle-open benchmark fills and zero-volume diagnostics are explicit.

Conservative-cost paired results, **actual common-clock minus benchmark**, on
exactly shared cycles:

| benchmark | quality | common_cycles | mean_actual_minus_benchmark | bootstrap_mean_low95 | bootstrap_mean_high95 | cycles_actual_better |
| --- | --- | --- | --- | --- | --- | --- |
| B_initial_basket | quoted_endpoints | 25 | -7,973.49 | -85,810.00 | 74,961.03 | 10 |
| B_initial_basket | nonzero_execution_volume | 12 | 7,115.91 | -103,622.97 | 127,940.85 | 5 |
| C_scheduled_accumulation | quoted_endpoints | 20 | 50,264.03 | -84,527.80 | 194,279.21 | 10 |
| C_scheduled_accumulation | nonzero_execution_volume | 14 | 30,641.41 | -138,587.13 | 214,568.90 | 7 |

Both comparison intervals include zero, and the exposure budgets differ. Median
actual/benchmark exposure ratios on available common cycles illustrate the gap:

| benchmark | peak_quantity_ratio | unit_minutes_ratio |
| --- | --- | --- |
| B_initial_basket | 31.83 | 15.78 |
| C_scheduled_accumulation | 3.34 | 1.80 |

Ratios are diagnostics, not hindsight size multipliers. Finite frozen payoff
bounds do not cap a dynamic strategy, and observed atomic call-tail mismatches
remain distinct from minute risk. No comparison establishes economic alpha at
comparable risk. Missing cohorts are listed rather than silently dropped.

[Benchmark assumptions/results](benchmark_comparison.csv), [trade ledger](benchmark_trade_ledger.csv.gz),
[scheduled quote failures](scheduled_benchmark_coverage.csv), [paired tests](paired_benchmark_differences.csv),
[exposure ratios](benchmark_exposure_ratios.csv), [paired leave-one-out](benchmark_leave_one_cycle_out.csv).

## 7. Risk, concentration and statistical robustness

Conservative primary net is ₹475,346.65, with **46.9%** winning
cycles. Mean cycle P&L is ₹14,854.58; the whole-cycle bootstrap
95% interval is **[₹-55,260.39, ₹87,259.06]**.
These are 32 related, already-inspected cycles, not thousands of independent
fills/windows. Shared calendar shocks, prior research selection and tail
underrepresentation remain limits. There is no blind external validation.

| Conservative risk / concentration measure | Rupees or stated units |
| --- | ---: |
| Worst / best cycle | -248,559.88 / 473,625.07 |
| Mean of five worst observed cycles | -212,205.47 |
| Largest sampled intracycle drawdown | 417,144.82 |
| Largest sampled adverse P&L from cycle start | 248,559.88 |
| Expiry-ordered cumulative-cycle-P&L drawdown | 934,755.86 |
| Net excluding largest winner | 1,721.58 |
| Net excluding largest loser | 723,906.54 |
| Net excluding two largest winners | -423,305.62 |

The cumulative curve is an ordered P&L diagnostic, **not account NAV**. Intracycle
marks are sampled, with gaps disclosed; no continuous tick drawdown, reliable
ruin probability or extreme-tail quantile is claimed. The worst-five mean is a
descriptive tail statistic, not a calibrated rare-event expected shortfall.

Conservative leave-one-cycle-out totals remain positive, but the weakest is only
₹1,721.58. The largest winner is **NIFTY
2026-09-29**: realised ₹-52,161.17, unrealised
**₹540,801.92**, conservative net ₹473,625.07.
Its received log has no expiry-day fills. It is a quote-marked residual result,
not verified expiry execution profit. The two top wins represent
28.5% of gross winning P&L but more than erase the
aggregate net when removed. Passing single-cycle removal is not robust alpha.

Index separation under conservative costs:

| index | cycles | net_pnl | win_pct | bootstrap_mean_low95 | bootstrap_mean_high95 |
| --- | --- | --- | --- | --- | --- |
| NIFTY | 15 | -57,254.51 | 40.00 | -112,434.26 | 118,885.89 |
| SENSEX | 17 | 532,601.16 | 52.94 | -49,988.14 | 116,144.85 |

[Cycle risks](cycle_risk_results.csv), [sampled paths](sampled_equity_paths.csv.gz),
[cost/LOO tables](leave_one_cycle_out.csv), [concentration](cycle_concentration.csv),
[standalone figure](economic_falsification.png). Neither index establishes a
persistent equal-risk advantage; uncertainty is not pooled away.

## Final conclusion and closure

**B — Positive raw results, but no demonstrated alpha.** The best-supported
interpretation is short-option carry exposed to convexity, direction and volatility
repricing, with protection and considerable trading costs. That is consistent
with the records, not proof of the proprietary alpha or a uniquely causal model.
Conditional endpoint gains survive some cost assumptions; adverse execution
costs, marked residual dependence, concentration and absent comparable-risk
support prevent a robust-edge claim. The fully closed subset is negative after
costs, while its selection prevents treating that fact as a complete rejection
of the strategy either.

Absolute marked profitability, risk-adjusted performance and economic alpha stay
separate. The low accuracy of controller/exit reconstruction neither proves nor
refutes an economic edge; the economic comparisons themselves do not demonstrate
one. The recurring accumulation, opening exceptions, approximate hedges, unknown
stops/re-entry and missing NAV/margin findings are preserved.

[Machine-readable verdict](final_verdict.json), [reproduction](README.md),
[software/evidence validation](validation_audit.json). **Stop here:** the repository
is ready for a final external research report; no further controller, indicator,
threshold or follow-up hypothesis phase is launched by this investigation.
