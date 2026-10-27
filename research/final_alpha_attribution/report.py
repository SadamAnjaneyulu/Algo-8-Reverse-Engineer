"""Final evidence-linked economic closure report and standalone figure."""
import json
import numpy as np
import pandas as pd
from inputs import HERE,COSTS,ROLES

def money(x):return f'{x:,.2f}'
def table(d,cols=None):
    d=d[cols] if cols else d
    def cell(x):
        if pd.isna(x):return '—'
        if isinstance(x,(float,np.floating)):return f'{x:,.2f}'
        return str(x).replace('|','/')
    return '| '+' | '.join(d.columns)+' |\n| '+' | '.join(['---']*len(d.columns))+' |\n'+'\n'.join('| '+' | '.join(cell(v) for v in row)+' |' for row in d.itertuples(index=False,name=None))

def run():
    e=pd.read_csv(HERE/'cycle_economic_results.csv');p=e[e.known_initialization];ids=set(p.cycle_id);v=json.loads((HERE/'final_verdict.json').read_text())
    quality=pd.read_csv(HERE/'data_quality_and_coverage.csv');stress=pd.read_csv(HERE/'cost_stress_results.csv');risk=pd.read_csv(HERE/'risk_and_drawdown_summary.csv');role=pd.read_csv(HERE/'role_economic_results.csv');phase=pd.read_csv(HERE/'phase_economic_results.csv');dec=pd.read_csv(HERE/'cycle_pnl_decomposition.csv');paired=pd.read_csv(HERE/'paired_benchmark_differences.csv')
    primary=risk[(risk.cohort=='primary_32')&risk['index'].eq('pooled')];cons=primary[primary.cost_scenario.eq('conservative')].iloc[0];flat=e[e.known_initialization&e.flat_received_endpoint]
    ct=[]
    for scenario,(a,b,c) in COSTS.items():
        ss=stress[stress.cost_scenario.eq(scenario)&stress['index'].eq('pooled')].set_index('cohort')
        ct.append(dict(scenario=scenario,turnover_pct=a*100,parent_fee=b,per_unit=c,primary32_net=ss.loc['primary_32','net_marked_pnl'],all35_sensitivity=ss.loc['all_35_sensitivity','net_marked_pnl'],flat22_net=ss.loc['closed_primary','net_marked_pnl']))
    roles=role[role.cycle_id.isin(ids)].groupby('role')[['fill_cashflow','realised_pnl','marked_unrealised_pnl','economic_pnl','moderate_cost']].sum().reset_index();roles['moderate_net']=roles.economic_pnl-roles.moderate_cost
    phases=phase[phase.known_initialization].groupby('phase')[['gross_pnl','moderate_net','conservative_net']].sum().reset_index()
    d=dec[dec.cycle_id.isin(ids)&dec.model.eq('primary')&dec.coverage.eq('variant_valid')];parts=d[['modeled_direction_pnl','modeled_time_pnl','modeled_iv_surface_pnl','trade_to_bar_mark_bridge','unexplained_residual']].sum();coverage=d.fitted_intervals.sum()/d.active_contract_intervals.sum();abscover=d.fitted_absolute_quoted_movement.sum()/d.total_absolute_quoted_movement.sum()
    model=dec[dec.cycle_id.isin(ids)&dec.coverage.eq('common_all_models')].groupby('model')[['modeled_direction_pnl','modeled_time_pnl','modeled_iv_surface_pnl']].sum().reset_index()
    idx=risk[(risk.cohort=='primary_32')&risk.cost_scenario.eq('conservative')&~risk['index'].eq('pooled')].copy();idx['win_pct']=idx.win_rate*100
    comparison=paired[paired['index'].eq('pooled')&paired.cost_scenario.eq('conservative')]
    mg=pd.read_csv(HERE/'management_markout_summary.csv');mg=mg[mg.cohort.eq('primary_32')]
    winner=p.nlargest(1,'conservative_marked_net').iloc[0];phasecounts=phase[phase.known_initialization].groupby('phase').gross_pnl.count()
    actualrisk=pd.read_csv(HERE/'cycle_risk_results.csv');actualrisk=actualrisk[actualrisk.known_initialization]
    ratio=pd.read_csv(HERE/'benchmark_exposure_ratios.csv');ratios=ratio.groupby('benchmark')[['peak_quantity_ratio','unit_minutes_ratio']].median().reset_index()
    rawbridge=parts.trade_to_bar_mark_bridge;unexplained=parts.unexplained_residual
    diagnostic=d[['delta_linear_diagnostic','gamma_quadratic_diagnostic','direction_higher_and_interaction']].sum()
    residualstress=p.conservative_residual_stress_net.sum();uncertain=p.uncertain_fill_extra_slippage_net.sum()
    text=f'''# Algo 8 — final alpha attribution, economic falsification and research closure

**Closure outcome B: positive raw/marked results under some assumptions, but no
demonstrated economic alpha.** The initialized 32-cycle sample has gross quoted
endpoint P&L of **₹{money(p.marked_economic_pnl.sum())}**. It remains positive after
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
| Received fill cash flow | {money(p.fill_cashflow.sum())} | Receipts less purchases; includes open liabilities |
| Gross realised P&L | {money(p.gross_realised_pnl.sum())} | Canonical pooled-cost closing attribution |
| Marked unrealised P&L | {money(p.marked_unrealised_pnl.sum())} | Residual mark minus reconstructed remaining cost |
| Combined quoted endpoint P&L | {money(p.marked_economic_pnl.sum())} | Realised + unrealised = cash + residual market value |

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

{table(pd.DataFrame(ct))}

The **22 initialized books that actually end flat** have gross P&L of
₹{money(flat.marked_economic_pnl.sum())}, and are negative after moderate/conservative
costs. This is an important sensitivity, not an unbiased alternative sample:
leaving residual options is related to the strategy's trading outcome, and the
subset discards profitable residual books too. Conversely, positive marked
results on residual books are not verified closed-cycle profits.

Setting residual long marks to zero and doubling short mark debits leaves primary
conservative net **₹{money(residualstress)}**. This is a fixed quote/liability stress,
not a worst-case bound or actual settlement. Adding ₹0.20/unit only to fills
outside/without their candle OHLC leaves conservative net **₹{money(uncertain)}**;
that ex-post discrepancy flag does not prove a recorded fill was impossible.

With parent fees fixed at ₹20 and unit allowance at ₹0.05, primary quoted P&L
breaks even at **{100*cons.break_even_total_turnover_rate_at20parent_005unit:.3f}%** of premium
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

{table(roles,['role','economic_pnl','moderate_cost','moderate_net'])}

Short CE contributes ₹{money(p.short_CE_pnl.sum())}; short PE contributes
₹{money(p.short_PE_pnl.sum())}. Long-call and long-put protection together contribute
**₹{money(p.long_CE_pnl.sum()+p.long_PE_pnl.sum())} gross**, before their allocated fees.
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

{table(phases)}

All {int(phasecounts.get('overnight',0))} primary phase rows are retained; each cycle's
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

For the primary 32-cycle attribution, **{100*coverage:.1f}%** of active contract intervals
fit, covering **{100*abscover:.1f}%** of absolute quoted price movement. These percentages
are not percentages of net profit explained. On the full primary model-valid cut:

| Additive component | Rupees |
| --- | ---: |
| Forward/directional repricing, nonlinear | {money(parts.modeled_direction_pnl)} |
| Time change | {money(parts.modeled_time_pnl)} |
| Own-IV / surface repricing | {money(parts.modeled_iv_surface_pnl)} |
| Trade price to bar-end mark bridge | {money(rawbridge)} |
| Unexplained/unfitted/gap residual | {money(unexplained)} |
| Total observed marked gross | {money(p.marked_economic_pnl.sum())} |

The bridge includes within-minute movement and marking differences, **not**
identified execution alpha. The residual is material and is not renamed alpha.
Within direction, the linear delta diagnostic is ₹{money(diagnostic.delta_linear_diagnostic)}
and quadratic gamma is ₹{money(diagnostic.gamma_quadratic_diagnostic)}; the remaining
higher-order/interaction term is ₹{money(diagnostic.direction_higher_and_interaction)}.
These sum to direction and must not be added again to the table. Estimated time
carry is strongly offset by convexity/directional losses and IV repricing; positive
theta alone does not establish a profitable signal or risk-adjusted excess return.

Model sensitivity on **identical common fitted intervals**, without selecting a
preferred variant on returns:

{table(model)}

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

{table(mg,['index','category','cycles','eligible_priced_components','mean_cycle_markout','bootstrap_mean_low95','bootstrap_mean_high95'])}

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

{table(comparison,['benchmark','quality','common_cycles','mean_actual_minus_benchmark','bootstrap_mean_low95','bootstrap_mean_high95','cycles_actual_better'])}

Both comparison intervals include zero, and the exposure budgets differ. Median
actual/benchmark exposure ratios on available common cycles illustrate the gap:

{table(ratios)}

Ratios are diagnostics, not hindsight size multipliers. Finite frozen payoff
bounds do not cap a dynamic strategy, and observed atomic call-tail mismatches
remain distinct from minute risk. No comparison establishes economic alpha at
comparable risk. Missing cohorts are listed rather than silently dropped.

[Benchmark assumptions/results](benchmark_comparison.csv), [trade ledger](benchmark_trade_ledger.csv.gz),
[scheduled quote failures](scheduled_benchmark_coverage.csv), [paired tests](paired_benchmark_differences.csv),
[exposure ratios](benchmark_exposure_ratios.csv), [paired leave-one-out](benchmark_leave_one_cycle_out.csv).

## 7. Risk, concentration and statistical robustness

Conservative primary net is ₹{money(cons.net_pnl)}, with **{100*cons.win_rate:.1f}%** winning
cycles. Mean cycle P&L is ₹{money(cons.mean_cycle_pnl)}; the whole-cycle bootstrap
95% interval is **[₹{money(cons.bootstrap_mean_low95)}, ₹{money(cons.bootstrap_mean_high95)}]**.
These are 32 related, already-inspected cycles, not thousands of independent
fills/windows. Shared calendar shocks, prior research selection and tail
underrepresentation remain limits. There is no blind external validation.

| Conservative risk / concentration measure | Rupees or stated units |
| --- | ---: |
| Worst / best cycle | {money(cons.worst_cycle)} / {money(cons.best_cycle)} |
| Mean of five worst observed cycles | {money(cons.mean_worst5_observed)} |
| Largest sampled intracycle drawdown | {money(cons.max_sampled_cycle_drawdown)} |
| Largest sampled adverse P&L from cycle start | {money(cons.max_sampled_cycle_mae)} |
| Expiry-ordered cumulative-cycle-P&L drawdown | {money(cons.closed_cycle_pnl_curve_drawdown)} |
| Net excluding largest winner | {money(cons.net_without_largest_winner)} |
| Net excluding largest loser | {money(cons.net_without_largest_loser)} |
| Net excluding two largest winners | {money(cons.net_without_top2_winners)} |

The cumulative curve is an ordered P&L diagnostic, **not account NAV**. Intracycle
marks are sampled, with gaps disclosed; no continuous tick drawdown, reliable
ruin probability or extreme-tail quantile is claimed. The worst-five mean is a
descriptive tail statistic, not a calibrated rare-event expected shortfall.

Conservative leave-one-cycle-out totals remain positive, but the weakest is only
₹{money(cons.net_without_largest_winner)}. The largest winner is **{winner.underlying}
{winner.expiry_date}**: realised ₹{money(winner.gross_realised_pnl)}, unrealised
**₹{money(winner.marked_unrealised_pnl)}**, conservative net ₹{money(winner.conservative_marked_net)}.
Its received log has no expiry-day fills. It is a quote-marked residual result,
not verified expiry execution profit. The two top wins represent
{100*cons.top2_share_of_gross_wins:.1f}% of gross winning P&L but more than erase the
aggregate net when removed. Passing single-cycle removal is not robust alpha.

Index separation under conservative costs:

{table(idx,['index','cycles','net_pnl','win_pct','bootstrap_mean_low95','bootstrap_mean_high95'])}

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
'''
    (HERE/'FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md').write_text(text)
    plot(e,p,ct)
    print('Final report and standalone figure written.',flush=True)

def plot(e,p,cost_rows):
    import os
    config=HERE/'.cache/matplotlib';config.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(config))
    os.environ.setdefault('XDG_CACHE_HOME',str(HERE/'.cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    d=p.sort_values(['expiry_date','underlying']);fig,axes=plt.subplots(1,2,figsize=(13,4.5),constrained_layout=True)
    x=np.arange(len(d));y=d.conservative_marked_net.to_numpy()/100000
    axes[0].bar(x,y,color=np.where(y>=0,'#137f72','#c34b4b'));axes[0].axhline(0,color='black',lw=.6);axes[0].set_title('32 initialized cycles: conservative marked net');axes[0].set_ylabel('INR lakh');axes[0].set_xlabel('Cycles ordered by expiry; residual books included')
    axes[0].set_xticks(x[::4],d.expiry_date.str[5:].iloc[::4],rotation=35)
    values=np.array([r['primary32_net'] for r in cost_rows])/100000;axes[1].bar(np.arange(4),values,color=['#8498a7','#137f72','#b89235','#c34b4b']);axes[1].axhline(0,color='black',lw=.6)
    axes[1].set_xticks(np.arange(4),['Zero\ndiagnostic','Moderate','Conservative','Adverse\nexecution']);axes[1].set_ylabel('INR lakh');axes[1].set_title('Net depends on declared cost assumptions')
    fig.suptitle('Algo 8 economic falsification — quoted P&L, not verified account returns',fontsize=12)
    fig.savefig(HERE/'economic_falsification.png',dpi=160);fig.savefig(HERE/'economic_falsification.svg',metadata={'Date':None});plt.close(fig)
    svg=HERE/'economic_falsification.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
if __name__=='__main__':run()
