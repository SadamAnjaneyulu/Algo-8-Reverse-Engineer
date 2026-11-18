"""Fixed cohort/cost robustness, paired evidence and research-closure verdict."""
import json
import numpy as np
import pandas as pd
from inputs import HERE,COSTS,save
from economics import drawdown

def cohorts(e):
    return {'primary_32':e[e.known_initialization],'all_35_sensitivity':e,'closed_primary':e[e.known_initialization&e.flat_received_endpoint],
            'residual_primary':e[e.known_initialization&~e.flat_received_endpoint]}

def run():
    e=pd.read_csv(HERE/'cycle_economic_results.csv');risk=pd.read_csv(HERE/'cycle_risk_results.csv');decomp=pd.read_csv(HERE/'cycle_pnl_decomposition.csv');ph=pd.read_csv(HERE/'phase_economic_results.csv');pairs=pd.read_csv(HERE/'paired_benchmark_differences.csv')
    stress=[];summary=[];loo=[];concentration=[];rng=np.random.default_rng(803532)
    for cohort,d in cohorts(e).items():
        for index in ['pooled','NIFTY','SENSEX']:
            sub=d if index=='pooled' else d[d.underlying==index];sub=sub.sort_values(['expiry_date','underlying'])
            if not len(sub):continue
            for scenario in COSTS:
                v=sub[scenario+'_marked_net'].to_numpy();n=len(v);boots=v[rng.integers(0,n,(5000,n))].mean(axis=1);low,high=np.quantile(boots,[.025,.975]);positive=v[v>0];negative=-v[v<0]
                stress.append(dict(cohort=cohort,index=index,cost_scenario=scenario,cycles=n,fill_cashflow=sub.fill_cashflow.sum(),gross_realised=sub.gross_realised_pnl.sum(),marked_unrealised=sub.marked_unrealised_pnl.sum(),gross_marked_pnl=sub.marked_economic_pnl.sum(),
                    estimated_cost=sub[scenario+'_cost'].sum(),net_marked_pnl=v.sum(),residual_stress_net=sub[scenario+'_residual_stress_net'].sum(),
                    net_cashflow=sub[scenario+'_cashflow_net'].sum(),win_cycles=int((v>0).sum()),loss_cycles=int((v<0).sum()),zero_cycles=int((v==0).sum()),
                    uncertain_execution_extra_slip_net=sub.uncertain_fill_extra_slippage_net.sum() if scenario=='conservative' else np.nan))
                rr=risk[risk.cycle_id.isin(sub.cycle_id)]
                summary.append(dict(cohort=cohort,index=index,cost_scenario=scenario,cycles=n,net_pnl=v.sum(),win_rate=float(np.mean(v>0)),loss_rate=float(np.mean(v<0)),mean_cycle_pnl=v.mean(),median_cycle_pnl=float(np.median(v)),
                    sample_std=float(np.std(v,ddof=1)) if n>1 else np.nan,worst_cycle=float(v.min()),best_cycle=float(v.max()),mean_worst5_observed=float(np.sort(v)[:min(5,n)].mean()),
                    bootstrap_mean_low95=low,bootstrap_mean_high95=high,closed_cycle_pnl_curve_drawdown=drawdown(np.cumsum(v)),max_sampled_cycle_drawdown=rr[scenario+'_sampled_drawdown'].max(),
                    max_sampled_cycle_mae=rr[scenario+'_sampled_mae'].max(),max_short_base_units=rr.max_short_base_units.max(),total_short_base_unit_minutes=rr.short_base_unit_minutes.sum(),
                    net_per1000_short_unit_minutes=v.sum()/rr.short_base_unit_minutes.sum()*1000,
                    net_without_largest_winner=float(v.sum()-v.max()),net_without_largest_loser=float(v.sum()-v.min()),net_without_top2_winners=float(v.sum()-np.sort(v)[-2:].sum()),
                    top1_share_of_gross_wins=float(positive.max()/positive.sum()) if len(positive) else np.nan,top2_share_of_gross_wins=float(np.sort(positive)[-2:].sum()/positive.sum()) if len(positive) else np.nan,
                    top1_share_of_gross_losses=float(negative.max()/negative.sum()) if len(negative) else np.nan,
                    largest_win_fraction_of_net=float(v.max()/v.sum()) if v.sum()!=0 else np.nan,
                    break_even_total_turnover_rate_at20parent_005unit=float((sub.marked_economic_pnl.sum()-20*sub.parent_orders.sum()-.05*sub.executed_quantity.sum())/sub.turnover.sum()),
                    extra_turnover_rate_beyond_moderate=float(sub.moderate_marked_net.sum()/sub.turnover.sum()),risk_denominator='currency/exposure proxy, not account NAV or broker margin'))
                if index=='pooled':
                    for x in sub.itertuples():
                        value=getattr(x,scenario+'_marked_net');remaining=float(v.sum()-value);loo.append(dict(cohort=cohort,cost_scenario=scenario,excluded_cycle_id=x.cycle_id,excluded_index=x.underlying,excluded_expiry=x.expiry_date,remaining_cycles=n-1,remaining_net=remaining,remaining_positive=remaining>0))
                    for x in sub.itertuples():concentration.append(dict(cohort=cohort,cost_scenario=scenario,cycle_id=x.cycle_id,underlying=x.underlying,expiry_date=x.expiry_date,cycle_net=getattr(x,scenario+'_marked_net')))
    stress=pd.DataFrame(stress);summary=pd.DataFrame(summary);loo=pd.DataFrame(loo)
    save(stress,'cost_stress_results.csv');save(summary,'risk_and_drawdown_summary.csv');save(loo,'leave_one_cycle_out.csv');save(pd.DataFrame(concentration),'cycle_concentration.csv')
    # Fixed descriptive management markouts: aggregate whole cycles, never child
    # p-values or a synthetic additive no-management profit.
    mo=pd.read_csv(HERE/'management_fixed_markouts.csv.gz');management=[]
    for cohort,ids in [('primary_32',set(e.loc[e.known_initialization,'cycle_id'])),('all_35_sensitivity',set(e.cycle_id))]:
      for (index,category),g in mo[mo.cycle_id.isin(ids)].groupby(['underlying','category']):
        valid=g[g.eligible_before_deadline&g.gross_local_markout_benefit.notna()];cycles=valid.groupby('cycle_id').gross_local_markout_benefit.sum();v=cycles.to_numpy()
        if len(v):b=v[rng.integers(0,len(v),(5000,len(v)))].mean(axis=1);low,high=np.quantile(b,[.025,.975])
        else:low=high=np.nan
        management.append(dict(cohort=cohort,index=index,category=category,closing_components=len(g),eligible_priced_components=len(valid),cycles=len(cycles),aggregate_local_markout=valid.gross_local_markout_benefit.sum(),
            mean_cycle_markout=float(v.mean()) if len(v) else np.nan,bootstrap_mean_low95=low,bootstrap_mean_high95=high,positive_cycles=int((v>0).sum()),
            additive_to_strategy_profit=False,deployable_counterfactual=False))
    save(pd.DataFrame(management),'management_markout_summary.csv')
    phase_summary=[]
    for index in ['pooled','NIFTY','SENSEX']:
        pp=ph[ph.known_initialization]
        if index!='pooled':pp=pp[pp.underlying==index]
        for phase,g in pp.groupby('phase'):
            for scenario in COSTS:
                v=g[scenario+'_net'].dropna().to_numpy()
                if len(v):
                    b=v[rng.integers(0,len(v),(5000,len(v)))].mean(axis=1);low,high=np.quantile(b,[.025,.975])
                else:low=high=np.nan
                phase_summary.append(dict(index=index,phase=phase,cost_scenario=scenario,available_cycles=len(v),missing_cycles=len(g)-len(v),net_pnl=float(v.sum()),
                    mean_cycle_pnl=float(v.mean()) if len(v) else np.nan,bootstrap_mean_low95=low,bootstrap_mean_high95=high))
    save(pd.DataFrame(phase_summary),'phase_distribution_summary.csv')
    bench=pd.read_csv(HERE/'benchmark_comparison.csv');ratios=[]
    for name in ['B_initial_basket','C_scheduled_accumulation']:
        a=bench[bench.benchmark.eq('D_common_clock')&bench.known_initialization&bench.complete_quotes].set_index('cycle_id')
        b=bench[bench.benchmark.eq(name)&bench.known_initialization&bench.complete_quotes].set_index('cycle_id')
        for cid in a.index.intersection(b.index):
            x,y=a.loc[cid],b.loc[cid]
            ratios.append(dict(benchmark=name,cycle_id=cid,index=x.underlying,expiry_date=x.expiry_date,
                actual_max_short_units=x.max_short_base_units,benchmark_max_short_units=y.max_short_base_units,
                peak_quantity_ratio=x.max_short_base_units/y.max_short_base_units if y.max_short_base_units else np.nan,
                actual_short_unit_minutes=x.short_base_unit_minutes,benchmark_short_unit_minutes=y.short_base_unit_minutes,
                unit_minutes_ratio=x.short_base_unit_minutes/y.short_base_unit_minutes if y.short_base_unit_minutes else np.nan,
                actual_finite_frozen_bound=x.max_finite_frozen_expiry_loss_bound,benchmark_finite_frozen_bound=y.max_finite_frozen_expiry_loss_bound,
                actual_unbounded_sampled_call_tail_minutes=x.negative_call_tail_minutes,benchmark_unbounded_sampled_call_tail_minutes=y.negative_call_tail_minutes,
                verified_equal_risk=False))
    save(pd.DataFrame(ratios),'benchmark_exposure_ratios.csv')
    exceptions=[]
    primary=decomp[decomp.model.eq('primary')&decomp.coverage.eq('variant_valid')].groupby('cycle_id')[['modeled_direction_pnl','modeled_time_pnl','modeled_iv_surface_pnl','unexplained_residual']].sum()
    for x in e.itertuples():
        def add(kind,description,value):exceptions.append(dict(cycle_id=x.cycle_id,index=x.underlying,expiry_date=x.expiry_date,counterexample=kind,value=value,description=description))
        if x.marked_economic_pnl>0 and x.conservative_marked_net<0:add('positive_gross_negative_after_costs','Positive marked gross does not survive conservative charges',x.conservative_marked_net)
        if primary.loc[x.cycle_id,'modeled_time_pnl']>0 and x.conservative_marked_net<0:add('positive_modeled_time_negative_net','Positive fitted time component coexists with net loss',x.conservative_marked_net)
        if x.short_CE_pnl+x.short_PE_pnl>0 and x.conservative_marked_net<0:add('short_profit_offset_by_wings_and_costs','Positive short-leg P&L does not establish net profitability',x.conservative_marked_net)
        if not x.flat_received_endpoint:add('residual_book_not_settlement','Marked endpoint includes received residual exposure',x.marked_unrealised_pnl)
        if not x.known_initialization:add('unknown_initialization','Expiry-only received start, sensitivity cohort',x.marked_economic_pnl)
        if x.conservative_marked_net>0 and x.adverse_execution_marked_net<0:add('execution_cost_fragility','Conservative positive becomes negative at adverse cost assumptions',x.adverse_execution_marked_net)
    save(pd.DataFrame(exceptions),'attribution_counterexamples.csv')
    p=stress[(stress.cohort=='primary_32')&stress['index'].eq('pooled')];r=summary[(summary.cohort=='primary_32')&summary['index'].eq('pooled')];closed=stress[(stress.cohort=='closed_primary')&stress['index'].eq('pooled')]
    net={x.cost_scenario:float(x.net_marked_pnl) for x in p.itertuples()};survives={name:bool(loo[(loo.cohort=='primary_32')&loo.cost_scenario.eq(name)].remaining_positive.all()) for name in COSTS}
    verdict='B' if net['moderate']>0 or net['conservative']>0 else 'C'
    # All primary endpoints are quoted, but residuals/completeness remain explicit.
    label={'B':'Positive marked results under some assumptions, but no demonstrated alpha','C':'No credible economic edge in the available sample'}[verdict]
    c=r[r.cost_scenario=='conservative'].iloc[0]
    verdict_json=dict(outcome=verdict,plain_language_outcome=label,research_closed=True,follow_up_search_authorized_by_this_report=False,
        best_supported_observed_measure=dict(primary_cohort_cycles=32,fill_cashflow=float(p.iloc[0].fill_cashflow),gross_realised=float(p.iloc[0].gross_realised),marked_unrealised=float(p.iloc[0].marked_unrealised),
            combined_quoted_endpoint_pnl=float(p.iloc[0].gross_marked_pnl),meaning='received cash plus stored residual quote marks; not verified account return or settlement'),
        primary_net_by_cost_scenario=net,all35_sensitivity_net={x.cost_scenario:float(x.net_marked_pnl) for x in stress[(stress.cohort=='all_35_sensitivity')&stress['index'].eq('pooled')].itertuples()},
        fully_flat_primary_cycles=22,fully_flat_primary_net={x.cost_scenario:float(x.net_marked_pnl) for x in closed.itertuples()},
        defensible_equal_risk_benchmark_available=False,paired_common_clock_benchmark_available=True,benchmark_alpha_comparison='inconclusive: risk/exposure differences and no verified ex-ante margin/NAV budget',
        survives_primary_leave_one_cycle_out=survives,primary_conservative_net_without_top2_winners=float(c.net_without_top2_winners),
        primary_conservative_top2_share_gross_winning_pnl=float(c.top2_share_of_gross_wins),profits_concentrated_or_fragile=bool(c.net_without_top2_winners<=0),
        data_support_absolute_profitability='conditional marked profitability under moderate/conservative scenarios; adverse execution scenario and fully flat subset are negative',
        data_support_verified_complete_account_profit=False,data_support_economic_alpha=False,
        conservative_mean_cycle_bootstrap95=[float(c.bootstrap_mean_low95),float(c.bootstrap_mean_high95)],
        confidence_and_coverage_limitations=['35 previously inspected cycles; 32 initialized primary cycles; no blind external validation',
            '11 residual books overall; 10 in primary; no verified settlement or post-export positions',
            '3 expiry-only starts excluded from primary; zero before first received fill remains an assumption',
            'Quote marks and minute sampling, sparse/zero-volume bars and incomplete received-contract chain',
            'Transaction-cost/slippage scenarios are estimates; authenticated charges, account NAV and margin absent',
            'Own-IV Shapley attribution is model-dependent and descriptive, with unfitted residuals',
            'Paired benchmarks share a clock but not a defensible equal dynamic risk budget'],
        reasons_no_alpha=['Positive cash/premium/theta is not alpha','P&L is sensitive to costs, endpoint/residual treatment and exceptional cycles',
            'No persistent advantage is established at comparable risk','Original intermediate decisions remain unidentified; economic test does not depend on recovering them'],
        stopping_decision='Deliver final report and reproduction checks; no further controller, threshold or indicator bank')
    (HERE/'final_verdict.json').write_text(json.dumps(verdict_json,indent=2,allow_nan=False));print(json.dumps(dict(outcome=verdict,primary_net=net,survives_loo=survives),indent=2),flush=True)
if __name__=='__main__':run()
