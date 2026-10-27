"""Fixed structural benchmarks; no return-based fitting or controller search."""
import json,math
import numpy as np
import pandas as pd
from inputs import HERE,ROOT,META,COSTS,fills,cycle_data,actual_path,save,iso
from economics import frozen_risk

def cost(turn,parents,qty,name):
    a,b,c=COSTS[name];return a*turn+b*parents+c*qty

def path_summary(q,cash,z,base):
    sh=np.maximum(-q,0).sum(axis=1);bound,tail=frozen_risk(q,cash,z)
    return dict(max_short_base_units=float(sh.max(initial=0)/base),short_base_unit_minutes=float(sh.sum()/base),
        max_finite_frozen_expiry_loss_bound=float(np.nanmax(bound)) if np.isfinite(bound).any() else np.nan,negative_call_tail_minutes=int(tail.sum()))

def run():
    f=fills();cal=json.loads((ROOT/'research/hypothesis_controller_search/outputs/calibration.json').read_text());coverage=pd.read_csv(HERE/'data_quality_and_coverage.csv');economic=pd.read_csv(HERE/'cycle_economic_results.csv');risk=pd.read_csv(HERE/'cycle_risk_results.csv')
    rows=[];trades=[];allocation_audit=[]
    for cid,fs in f.groupby('cycle_id',sort=True):
        meta=META[cid];u,e=meta['underlying'],meta['expiry_date'];base=meta['base_unit'];z=cycle_data(cid);a=actual_path(fs,z);T,C=z['close'].shape;cov=coverage[coverage.cycle_id==cid].iloc[0]
        deadline=927 if e<'2026-08-03' else 914;ds=int(pd.Timestamp(e+f' {deadline//60:02}:{deadline%60:02}',tz='Asia/Kolkata').timestamp());dm=ds//60;di=np.flatnonzero(z['minutes']==dm);di=int(di[0]) if len(di) else None
        common=dict(cycle_id=cid,underlying=u,expiry_date=e,known_initialization=bool(cov.known_initialization),comparison_split='fit_only_JunJul' if e<='2026-07-31' else 'AugOct_fixed_check',
            full_chain_verified=False,risk_equalized=False)
        er=economic[economic.cycle_id==cid].iloc[0];rr=risk[risk.cycle_id==cid].iloc[0]
        actualrow=dict(common,benchmark='D_observed_endpoint',complete_quotes=bool(cov.endpoint_quote_mark_available),eligible=True,scope='actual received sequence; endpoint residuals marked',
            gross_pnl=er.marked_economic_pnl,turnover=er.turnover,parent_orders=er.parent_orders,executed_quantity=er.executed_quantity,exit_ist=er.endpoint_ist,
            fill_volume_strict=False,max_short_base_units=rr.max_short_base_units,short_base_unit_minutes=rr.short_base_unit_minutes,max_finite_frozen_expiry_loss_bound=rr.max_finite_frozen_expiry_loss_bound)
        for name in COSTS:actualrow[name+'_net']=er[name+'_marked_net']
        rows.append(actualrow);none=dict(common,benchmark='A_no_trading',complete_quotes=True,eligible=True,scope='zero exposure',gross_pnl=0,turnover=0,parent_orders=0,executed_quantity=0,exit_ist=er.endpoint_ist,fill_volume_strict=True,max_short_base_units=0,short_base_unit_minutes=0,max_finite_frozen_expiry_loss_bound=0)
        none.update({n+'_net':0 for n in COSTS});rows.append(none)
        unavailable=dict(common,benchmark='E_equal_risk_unavailable',complete_quotes=False,eligible=False,scope='No verified ex-ante common dynamic risk/margin budget; no fitted hindsight scaling',gross_pnl=np.nan)
        unavailable.update({n+'_net':np.nan for n in COSTS});rows.append(unavailable)
        for name in ['B_initial_basket','C_scheduled_accumulation','D_common_clock']:
            delta=np.zeros((T,C),int);cf=np.zeros(T);turn=parents=qty=0.;known_cost={n:0. for n in COSTS};allprices=True;strictvolume=True;eligible=bool(cov.known_initialization);why=[]
            def execute(i,j,signed,price,origin,actual_parent_count=None):
                nonlocal turn,parents,qty,strictvolume
                delta[i,j]+=signed;cf[i]-=signed*price;turn+=abs(signed)*price;qty+=abs(signed)
                req=math.ceil(abs(signed)/base) if actual_parent_count is None else actual_parent_count;parents+=req
                strictvolume&=bool(z['volume'][i,j]>0)
                trades.append(dict(cycle_id=cid,benchmark=name,second=int(z['minutes'][i]*60),strike=int(z['strikes'][j]),right='PE' if z['rights'][j] else 'CE',
                    signed_quantity=int(signed),price=float(price),hypothetical_parents=req,origin=origin,execution='model at candle open' if origin!='observed_opening_prefix' else 'recorded price'))
            if not eligible:why.append('unknown_initialization')
            if name=='B_initial_basket':
                day=meta['dates'][0];cut=int(pd.Timestamp(day+' 09:18',tz='Asia/Kolkata').timestamp());prefix=fs[fs.second<cut]
                # A documented delayed start has no normal four-role initial book.
                if day>=e or len(prefix)==0:eligible=False;why.append('no_ordinary_opening_prefix')
                if len(prefix):
                    ti=int(np.searchsorted(z['minutes'],cut//60)-1);position=a['q'][ti]
                    hasroles=all(np.any((z['rights']==r)&(position*s>0)) for r in [0,1] for s in [-1,1])
                    if not hasroles:eligible=False;why.append('not_four_role_ordinary_prefix')
                    if eligible:
                        delta[:ti+1]=a['delta'][:ti+1];cf[:ti+1]=np.diff(np.r_[0.,a['cash'][:ti+1]])
                        turn=float(a['turn'][:ti+1].sum());parents=float(a['parent'][:ti+1].sum());qty=float(a['units'][:ti+1].sum())
                        for n in COSTS:known_cost[n]=cost(turn,parents,qty,n)
                        # Record original prefix as source-linked economic input;
                        # its entry prices are never replaced by model quotes.
                        for x in prefix.itertuples():
                            trades.append(dict(cycle_id=cid,benchmark=name,second=x.second,strike=x.strike,right=x.option_type,signed_quantity=x.incremental_quantity*(1 if x.side=='Buy' else -1),price=x.execution_price,hypothetical_parents=np.nan,origin='observed_opening_prefix',execution='recorded price'))
                        for x in prefix.itertuples():
                            ix=int(np.searchsorted(z['minutes'],x.second//60));j=int(np.flatnonzero((z['strikes']==x.strike)&(z['rights']==int(x.option_type=='PE')))[0])
                            strictvolume&=bool(z['volume'][ix,j]>0)
            elif name=='D_common_clock':
                if di is not None:
                    delta[:di]=a['delta'][:di];cf[:di]=np.diff(np.r_[0.,a['cash'][:di]])
                    turn=float(a['turn'][:di].sum());parents=float(a['parent'][:di].sum());qty=float(a['units'][:di].sum())
                    # Full source-price comparison against OHLC is available in
                    # audit; zero volume at recorded fills is not modeled away.
                    for x in fs[fs.second<ds].itertuples():
                        ix=int(np.searchsorted(z['minutes'],x.second//60));j=int(np.flatnonzero((z['strikes']==x.strike)&(z['rights']==int(x.option_type=='PE')))[0]);strictvolume&=bool(z['volume'][ix,j]>0)
            else:
                if eligible:
                    day=meta['dates'][0];lookup={(int(k),int(r)):j for j,(k,r) in enumerate(zip(z['strikes'],z['rights']))};grid=meta['strike_grid']
                    for slot,clock in enumerate(cal['slots']):
                        ss=int(pd.Timestamp(day+' '+clock,tz='Asia/Kolkata').timestamp());signal=ss//60;prior=np.flatnonzero(z['minutes']==signal-1);fill=np.flatnonzero(z['minutes']==signal+1)
                        units=[3,3,3,3] if slot==0 else cal['pooled_clock'][int(u=='SENSEX')][0][slot]
                        intended=any(v>0 for v in units)
                        if not intended:continue
                        fail=[];orders=[]
                        if len(prior)==0 or len(fill)==0:fail.append('missing_signal_or_execution_bar')
                        else:
                            pi,fi=int(prior[0]),int(fill[0]);spot=z['spot_close'][pi]
                            if not np.isfinite(spot):fail.append('missing_completed_index_reference')
                            else:
                                atm=int(np.floor(spot/grid+.5))*grid
                                for right in [0,1]:
                                    s=lookup.get((atm,right));wing=None
                                    if s is None or not np.isfinite(z['close'][pi,s]) or z['close'][pi,s]<=0:fail.append('unquoted_ATM');continue
                                    budget=.025*z['close'][pi,s]
                                    if u=='SENSEX':budget=np.floor(budget*10+.5)/10
                                    js=[j for j in range(C) if z['rights'][j]==right and (z['strikes'][j]>atm if right==0 else z['strikes'][j]<atm) and
                                        np.isfinite(z['close'][pi,j]) and z['close'][pi,j]>0 and z['close'][pi,j]<=budget+1e-9 and z['volume'][pi,j]>0]
                                    if js:wing=min(js,key=lambda j:(budget-z['close'][pi,j],abs(z['strikes'][j]-atm)))
                                    if units[right]>0:orders.append((s,-int(round(units[right]))*base))
                                    if units[right+2]>0:
                                        if wing is None:fail.append('missing_eligible_hedge')
                                        else:orders.append((wing,int(round(units[right+2]))*base))
                                if any(not np.isfinite(z['open'][fi,j]) for j,q in orders):fail.append('missing_entry_open')
                        if fail:allprices=False;why.extend(fail)
                        else:
                            for j,q in orders:execute(fi,j,q,float(z['open'][fi,j]),'scheduled_model_entry')
                        allocation_audit.append(dict(cycle_id=cid,slot=clock,signal_ist=iso(ss),intended_nonzero=True,priced_allocation=not fail,reason=';'.join(fail),
                            feature_available_at_ist=iso(ss),modeled_execution_ist=iso(ss+60),quantity_schedule='frozen JunJul pooled modes; seed three bases'))
            if eligible:
                q=np.cumsum(delta,axis=0)[-1]
                if di is None:allprices=False;why.append('missing_exit_clock')
                elif any(not np.isfinite(z['open'][di,j]) for j in np.flatnonzero(q)):
                    allprices=False;why.append('missing_exit_price')
                else:
                    for j in np.flatnonzero(q):execute(di,j,-int(q[j]),float(z['open'][di,j]),'hypothetical_fixed_clock_exit')
            else:allprices=False
            qpath=np.cumsum(delta,axis=0);cashpath=np.cumsum(cf);gross=float(cashpath[-1]) if eligible and allprices and not np.any(qpath[-1]) else np.nan
            pr=path_summary(qpath,cashpath,z,base)
            row=dict(common,benchmark=name,complete_quotes=bool(allprices),eligible=eligible,scope=';'.join(sorted(set(why))) if why else 'complete conditional/candle-open benchmark',gross_pnl=gross,
                diagnostic_partial_cashflow=float(cashpath[-1]),turnover=turn,parent_orders=parents,executed_quantity=qty,exit_ist=iso(ds),fill_volume_strict=bool(strictvolume),**pr)
            for n in COSTS:row[n+'_net']=gross-cost(turn,parents,qty,n)
            rows.append(row)
        print('Benchmarks',cid,flush=True)
    result=pd.DataFrame(rows);save(result,'benchmark_comparison.csv');save(pd.DataFrame(trades),'benchmark_trade_ledger.csv.gz');save(pd.DataFrame(allocation_audit),'scheduled_benchmark_coverage.csv')
    # Same expiry-clock endpoint and charges, with explicitly unequal dynamic risk.
    paired=[];loo=[];rng=np.random.default_rng(8035)
    for name in ['B_initial_basket','C_scheduled_accumulation']:
        for strict in [False,True]:
            for index in ['pooled','NIFTY','SENSEX']:
                d=result[result.known_initialization&result.eligible&result.complete_quotes&result.benchmark.isin([name,'D_common_clock'])]
                if name=='C_scheduled_accumulation':d=d[d.comparison_split=='AugOct_fixed_check']
                if strict:d=d[d.fill_volume_strict]
                if index!='pooled':d=d[d.underlying==index]
                for scenario in COSTS:
                    p=d.pivot(index='cycle_id',columns='benchmark',values=scenario+'_net').dropna()
                    if name not in p.columns or 'D_common_clock' not in p.columns:p=p.iloc[:0]
                    diff=(p['D_common_clock']-p[name]).to_numpy() if len(p) else np.array([])
                    if len(diff):boot=diff[rng.integers(0,len(diff),(5000,len(diff)))].mean(axis=1);low,high=np.quantile(boot,[.025,.975])
                    else:low=high=np.nan
                    paired.append(dict(benchmark=name,quality='nonzero_execution_volume' if strict else 'quoted_endpoints',index=index,cost_scenario=scenario,common_cycles=len(diff),
                        mean_actual_minus_benchmark=float(diff.mean()) if len(diff) else np.nan,paired_total_difference=float(diff.sum()) if len(diff) else np.nan,
                        bootstrap_mean_low95=low,bootstrap_mean_high95=high,cycles_actual_better=int((diff>0).sum()),comparable_risk_budget=False,alpha_inference='inconclusive: dynamic risk not equalized'))
                    if not strict and index=='pooled':
                        for j,cid in enumerate(p.index):loo.append(dict(benchmark=name,cost_scenario=scenario,excluded_cycle_id=cid,remaining_cycles=len(diff)-1,remaining_total_difference=float(diff.sum()-diff[j]),equal_risk=False))
    save(pd.DataFrame(paired),'paired_benchmark_differences.csv');save(pd.DataFrame(loo),'benchmark_leave_one_cycle_out.csv')
    print('Fixed benchmark comparison complete',flush=True)
if __name__=='__main__':run()
