"""Observed role cashflows, marked economic endpoints, costs, phases and risk."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from inputs import HERE,SOURCE,META,ROLES,COSTS,fills,cycle_data,actual_path,role,iso,save,sha

def drawdown(v):
    v=np.asarray(v,float);v=v[np.isfinite(v)];return float(np.max(np.maximum.accumulate(np.r_[0.,v])[1:]-v,initial=0))
def frozen_risk(q,cash,z):
    strike=z['strikes'];right=z['rights'];levels=np.r_[0.,np.unique(strike)]
    payoff=np.where(right[:,None]==0,np.maximum(levels[None,:]-strike[:,None],0),np.maximum(strike[:,None]-levels[None,:],0))
    tail=q[:,right==0].sum(axis=1)<0;worst=cash+np.min(q@payoff,axis=1);bound=np.maximum(-worst,0.);bound[tail]=np.nan
    return bound,tail

def flow_and_holding(f,labels):
    """Disjoint cash-flow timing cuts and FIFO/LIFO holding-age sensitivities."""
    components=[]
    for cid,fs in f.groupby('cycle_id',sort=True):
        lots={mode:{} for mode in ['fifo','lifo']};firstday=META[cid]['dates'][0];expiry=META[cid]['expiry_date']
        for x in fs.itertuples():
            key=(x.strike,x.option_type);ages={}
            for mode in lots:
                queue=lots[mode].setdefault(key,[]);remaining=int(x.closing_quantity);weighted=0.
                while remaining:
                    index=0 if mode=='fifo' else -1;lot=queue[index];part=min(remaining,lot[0]);weighted+=part*(x.second-lot[1])/60
                    lot[0]-=part;remaining-=part
                    if not lot[0]:queue.pop(index)
                ages[mode]=weighted
                if x.opening_quantity:queue.append([int(x.opening_quantity),int(x.second)])
                assert sum(q for q,t in queue)==abs(x.quantity_after)
            for qty,sign,closing in [(x.closing_quantity,np.sign(x.quantity_before),True),(x.opening_quantity,1 if x.side=='Buy' else -1,False)]:
                if not qty:continue
                rr=role(x.option_type,sign);phase='expiry' if x.date==expiry else 'preexpiry'
                if closing:category=labels.get(x.source_row,'unclassified_short_cover') if x.side=='Buy' else ('late_long_sale' if phase=='expiry' and x.timestamp_ist[11:16]>='15:00' else 'intermediate_long_sale')
                else:category='observed_opening_prefix' if x.date==firstday and x.date<expiry and x.timestamp_ist[11:16]<'09:18' else 'later_preexpiry_inventory_opening' if phase=='preexpiry' else 'expiry_inventory_opening'
                components.append(dict(cycle_id=cid,underlying=META[cid]['underlying'],expiry_date=expiry,source_row=x.source_row,role=ROLES[rr],phase=phase,category=category,
                    quantity=qty,is_closing=closing,cashflow=qty*x.execution_price*(1 if x.side=='Sell' else -1),realised_pnl=x.realized_pnl_change if closing else 0.,
                    turnover=qty*x.execution_price,closed_quantity=qty if closing else 0,
                    fifo_quantity_minutes=ages['fifo'] if closing else 0.,lifo_quantity_minutes=ages['lifo'] if closing else 0.))
    d=pd.DataFrame(components);g=d.groupby(['cycle_id','underlying','expiry_date','role','phase','category'],sort=True)[['quantity','cashflow','realised_pnl','turnover','closed_quantity','fifo_quantity_minutes','lifo_quantity_minutes']].sum().reset_index()
    for mode in ['fifo','lifo']:g[mode+'_mean_closed_holding_minutes']=g[mode+'_quantity_minutes']/g.closed_quantity.replace(0,np.nan)
    g['ownership']='book matching sensitivities; inventory opening is not certified original allocation intent'
    save(g,'flow_and_holding_attribution.csv')

def run():
    assert (HERE/'DATA_QUALITY_AUDIT.md').exists(),'Audit before economics'
    f=fills();coverage=pd.read_csv(HERE/'data_quality_and_coverage.csv');rows=[];roles=[];phases=[];risks=[];paths=[];contracts=[];categories=[];markouts=[]
    labels=pd.read_csv(HERE.parents[0]/'intermediate_exit_study/short_cover_children.csv.gz')[['source_row','outcome_stratum']].set_index('source_row').outcome_stratum.to_dict()
    eventbooks=pd.read_csv(SOURCE/'playbook_event_book.csv.gz')
    for cid,fs in f.groupby('cycle_id',sort=True):
        m=META[cid];z=cycle_data(cid);a=actual_path(fs,z);u,e=m['underlying'],m['expiry_date'];base=m['base_unit'];q=a['q'][-1];live=q!=0;end=z['close'][-1];last=fs.groupby(['strike','option_type'],sort=False).tail(1)
        lookup={(int(k),'PE' if r else 'CE'):j for j,(k,r) in enumerate(zip(z['strikes'],z['rights']))};cov=coverage[coverage.cycle_id==cid].iloc[0]
        real=a['real'].sum(axis=0);rc=a['rolecash'].sum(axis=0);endvalue=np.zeros(4);unreal=np.zeros(4)
        for x in last.itertuples():
            if not x.quantity_after:continue
            j=lookup[(x.strike,x.option_type)];rr=role(x.option_type,np.sign(x.quantity_after));endvalue[rr]+=x.quantity_after*end[j];unreal[rr]+=x.quantity_after*(end[j]-x.average_cost_after)
        assert np.allclose(real+unreal,rc+endvalue,rtol=0,atol=1e-5)
        gross=float(a['equity'][-1]);assert abs(gross-(real+unreal).sum())<1e-5
        turnover=float(a['turn'].sum());qty=float(a['units'].sum());parent=float(a['parent'].sum());assert abs(parent-fs.parent_id.nunique())<1e-8
        shortq=np.maximum(-a['q'],0).sum(axis=1);longq=np.maximum(a['q'],0).sum(axis=1);bound,tail=frozen_risk(a['q'],a['cash'],z)
        risk=dict(cycle_id=cid,underlying=u,expiry_date=e,known_initialization=bool(cov.known_initialization),flat_received_endpoint=bool(cov.flat_received_endpoint),
            gross_sampled_drawdown=drawdown(a['equity']),gross_sampled_mae=max(0,-float(np.nanmin(np.r_[0,a['equity']]))),missing_mark_minutes=int(np.isnan(a['equity']).sum()),
            max_short_quantity=int(shortq.max()),max_protective_quantity=int(longq.max()),max_short_base_units=float(shortq.max()/base),short_base_unit_minutes=float(shortq.sum()/base),
            max_finite_frozen_expiry_loss_bound=float(np.nanmax(bound)) if np.isfinite(bound).any() else np.nan,negative_call_tail_sampled_minutes=int(tail.sum()),
            negative_call_tail_atomic_seconds=int(((eventbooks.underlying==u)&(eventbooks.expiry_date==e)&eventbooks.after_call_tail_quantity.lt(0)).sum()),
            max_gross_short_mark_value=float(np.nanmax(np.sum(np.maximum(-a['q'],0)*np.nan_to_num(z['close']),axis=1))),
            account_nav_verified=False,actual_margin_verified=False,risk_measure='sampled, quote-marked; frozen payoff is not margin or dynamic loss cap')
        for name in COSTS:risk[name+'_sampled_drawdown']=drawdown(a['equity']-a['cost'][name]);risk[name+'_sampled_mae']=max(0,-float(np.nanmin(np.r_[0,a['equity']-a['cost'][name]])))
        risks.append(risk)
        stress_value=float(np.sum(np.where(q<0,2*q*end,0))) # residual longs zero; residual short debits doubled
        r=dict(cycle_id=cid,underlying=u,expiry_date=e,known_initialization=bool(cov.known_initialization),flat_received_endpoint=bool(cov.flat_received_endpoint),
            valuation_status=cov.economic_status,endpoint_ist=cov.quote_endpoint,fill_cashflow=float(a['cash'][-1]),gross_realised_pnl=float(real.sum()),marked_unrealised_pnl=float(unreal.sum()),
            residual_marked_value=float(endvalue.sum()),marked_economic_pnl=gross,turnover=turnover,executed_quantity=qty,parent_orders=int(round(parent)),child_fills=len(fs),
            residual_contracts=int(live.sum()),residual_short_quantity=int(np.maximum(-q,0).sum()),residual_long_quantity=int(np.maximum(q,0).sum()),
            unpriced_residuals=int(np.sum(live&~np.isfinite(end))),modeled_endpoint_prices=0,
            stress_residual_value=stress_value,residual_stress_gross=float(a['cash'][-1]+stress_value),uncertain_ohlc_units=float(a['uncertain_units'].sum()))
        for name in COSTS:
            cost=float(a['cost'][name][-1]);r[name+'_cost']=cost;r[name+'_marked_net']=gross-cost;r[name+'_cashflow_net']=float(a['cash'][-1]-cost)
            r[name+'_residual_stress_net']=float(a['cash'][-1]+stress_value-cost)
        r['uncertain_fill_extra_slippage_net']=r['conservative_marked_net']-.20*r['uncertain_ohlc_units']
        r['moderate_net_per1000_short_unit_minutes']=1000*r['moderate_marked_net']/risk['short_base_unit_minutes'] if risk['short_base_unit_minutes'] else np.nan
        for rr,label in enumerate(ROLES):
            r[label+'_pnl']=float(real[rr]+unreal[rr]);roles.append(dict(cycle_id=cid,underlying=u,expiry_date=e,role=label,fill_cashflow=rc[rr],realised_pnl=real[rr],marked_unrealised_pnl=unreal[rr],
                endpoint_marked_value=endvalue[rr],economic_pnl=real[rr]+unreal[rr],turnover=a['turn'][:,rr].sum(),executed_quantity=a['units'][:,rr].sum(),parent_fee_weight=a['parent'][:,rr].sum(),
                moderate_cost=.0025*a['turn'][:,rr].sum()+20*a['parent'][:,rr].sum()+.05*a['units'][:,rr].sum(),
                attribution='observed direction/right pooling, not original allocation identity'))
        rows.append(r)
        # Exact phase endpoints: pre-expiry close; fixed carry to expiry open;
        # all later price/trade effects in the expiry remainder.
        dates=np.array([iso(int(t)*60)[:10] for t in z['minutes']]);pre=np.flatnonzero(dates<e);exp=np.flatnonzero(dates==e)
        pre_pnl=float(a['equity'][pre[-1]]) if len(pre) else 0.;overnight=0.
        if len(pre) and len(exp):
            carry=a['q'][pre[-1]];mask=carry!=0;pp=z['close'][pre[-1]];op=z['open'][exp[0]]
            overnight=float(np.dot(carry[mask],op[mask]-pp[mask])) if np.isfinite(op[mask]).all() and np.isfinite(pp[mask]).all() else np.nan
        amounts={'preexpiry':pre_pnl,'overnight':overnight,'expiry':gross-pre_pnl-overnight}
        for phase,gp in amounts.items():
            pr=dict(cycle_id=cid,underlying=u,expiry_date=e,known_initialization=bool(cov.known_initialization),phase=phase,gross_pnl=gp,endpoint_marks_complete=np.isfinite(gp))
            for name in COSTS:
                pre_cost=float(a['cost'][name][pre[-1]]) if len(pre) else 0.;total=float(a['cost'][name][-1]);cost=pre_cost if phase=='preexpiry' else 0 if phase=='overnight' else total-pre_cost
                pr[name+'_cost']=cost;pr[name+'_net']=gp-cost
            phases.append(pr)
        for i in range(len(z['minutes'])):paths.append(dict(cycle_id=cid,second=int((z['minutes'][i]+1)*60),equity=a['equity'][i],moderate_cost=a['cost']['moderate'][i],conservative_cost=a['cost']['conservative'][i],short_quantity=int(shortq[i]),long_quantity=int(longq[i]),finite_frozen_loss=bound[i],negative_call_tail=bool(tail[i])))
        # Exact protection contribution by contract, including residual quotes.
        for (k,right),g in fs.groupby(['strike','option_type']):
            cash=realized=buys=sells=turn=0.
            for x in g.itertuples():
                opening=x.opening_quantity if x.side=='Buy' else 0;closing=x.closing_quantity if x.side=='Sell' else 0
                cash+=closing*x.execution_price-opening*x.execution_price;buys+=opening;sells+=closing;turn+=(opening+closing)*x.execution_price
                if closing:realized+=x.realized_pnl_change
            if not buys and not sells:continue
            j=lookup[(k,right)];qend=max(int(q[j]),0);value=qend*end[j]
            contracts.append(dict(cycle_id=cid,underlying=u,expiry_date=e,strike=k,right=right,bought_quantity=buys,sold_quantity=sells,fill_cashflow=cash,
                realised_pnl=realized,residual_long_quantity=qend,residual_marked_value=value,protection_economic_pnl=cash+value,turnover=turn,
                recorded_settlement=False,remaining_protection='quoted_residual' if qend else 'received_long_book_closed'))
        # Observed management cashflows and fixed-deadline local markouts.
        deadline=927 if e<'2026-08-03' else 914;deadline_sec=int(pd.Timestamp(e+' '+f'{deadline//60:02}:{deadline%60:02}',tz='Asia/Kolkata').timestamp());tidx=np.flatnonzero(z['minutes']==deadline_sec//60)
        for x in fs.itertuples():
            if x.closing_quantity:
                rr=role(x.option_type,np.sign(x.quantity_before));kind=labels.get(x.source_row,'short_cover_unclassified') if x.side=='Buy' else ('late_long_sale' if x.date==e and x.timestamp_ist[11:16]>='15:00' else 'intermediate_long_sale')
                categories.append(dict(cycle_id=cid,underlying=u,expiry_date=e,category=kind,role=ROLES[rr],source_row=x.source_row,closing_quantity=x.closing_quantity,
                    closing_cashflow=x.closing_quantity*x.execution_price*(1 if x.side=='Sell' else -1),realised_pnl=x.realized_pnl_change,
                    label='observed pooled closing result; not incremental management alpha'))
                if kind not in ['final_liquidation','late_long_sale']:
                    j=lookup[(x.strike,x.option_type)];p=float(z['open'][tidx[0],j]) if len(tidx) else np.nan;eligible=x.second<deadline_sec
                    benefit=x.closing_quantity*(p-x.execution_price)*(1 if x.side=='Buy' else -1) if eligible and np.isfinite(p) else np.nan
                    markouts.append(dict(cycle_id=cid,underlying=u,expiry_date=e,source_row=x.source_row,category=kind,role=ROLES[rr],strike=x.strike,right=x.option_type,
                        closing_quantity=x.closing_quantity,fill_ist=x.timestamp_ist,fill_price=x.execution_price,deadline_ist=iso(deadline_sec),deadline_quote=p,
                        eligible_before_deadline=eligible,quote_volume=float(z['volume'][tidx[0],j]) if len(tidx) else np.nan,gross_local_markout_benefit=benefit,
                        interpretation='nondeployable local fixed-future-mark comparison; not an additive no-management backtest'))
    save(pd.DataFrame(rows),'cycle_economic_results.csv');save(pd.DataFrame(roles),'role_economic_results.csv');save(pd.DataFrame(phases),'phase_economic_results.csv');save(pd.DataFrame(risks),'cycle_risk_results.csv')
    save(pd.DataFrame(paths),'sampled_equity_paths.csv.gz');save(pd.DataFrame(contracts),'protection_contract_contributions.csv');save(pd.DataFrame(categories),'management_realised_components.csv.gz');save(pd.DataFrame(markouts),'management_fixed_markouts.csv.gz')
    flow_and_holding(f,labels)
    (HERE/'economic_input_manifest.json').write_text(json.dumps(dict(registered_plan_sha256=sha(HERE/'REGISTERED_PLAN.md'),clarifications_sha256=sha(HERE/'BENCHMARK_AND_MODEL_CLARIFICATIONS.md'),
        cost_scenarios=COSTS,source_audit_sha256=sha(HERE/'input_audit.json'),no_model_liquidation_in_observed_pnl=True),indent=2))
    print('Observed economics and cost views written',flush=True)
if __name__=='__main__':run()
