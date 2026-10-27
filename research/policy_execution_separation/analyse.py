"""Matched policy/execution comparisons and fixed-cohort identification audits."""
from __future__ import annotations
import gzip,itertools,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from replay_inputs import market_cache
from model_runner import HERE,ROOT,PRIOR,policies,mechanics
sys.path.insert(0,str(PRIOR))
from evaluate import matched_actions,timestamp

ACTIONS=['new_short','short_cover','wing_buy','wing_sell']


def match_score(p,a,base):
    pp=p.sort_values(['minute','strike','right','action']).to_dict('records');aa=a.sort_values(['minute','strike','right','action']).to_dict('records')
    pairs,extras,misses=matched_actions(pp,aa,2);row={};f=[]
    for role in range(4):
        pn=sum(x['action']==role for x in pp);an=sum(x['action']==role for x in aa);ma=sum(pp[i]['action']==role for i,j in pairs)
        row.update({f'pred{role}':pn,f'actual{role}':an,f'match{role}':ma,f'precision{role}':ma/pn if pn else np.nan,f'recall{role}':ma/an if an else np.nan})
        f.append(2*ma/(pn+an) if pn+an else np.nan)
    denom=(p.quantity.sum()+a.quantity.sum())/base
    overlap=sum(2*min(pp[i]['quantity'],aa[j]['quantity'])/base for i,j in pairs)
    row.update(event_macro_f1=float(np.nanmean(f)),quantity_score=overlap/denom if denom else 1.,false_actions=len(extras),missed_actions=len(misses))
    return row,pp,aa,pairs,extras,misses


def first_execution_signature(child,side,right):
    q=child[child.side.eq(side)&child.option_type.eq(right)&child.opening_quantity.gt(0)].sort_values(['second','source_row'])
    if q.empty:return dict(strike=np.nan,source=np.nan,tied_strikes=0)
    return dict(strike=int(q.iloc[0].strike),source=int(q.iloc[0].source_row),tied_strikes=len(q[q.second.eq(q.second.min())].strike.unique()))


def run():
    config=yaml.safe_load((HERE/'selected_model_config.yaml').read_text());selected=config['selected_model'];policy=selected['policy_id'];baseline=policy*7
    meta=json.loads((PRIOR/'outputs/cycle_metadata.json').read_text());indexmap={(c['underlying'],c['expiry_date']):c['cycle_id'] for c in meta}
    models=pd.read_csv(HERE/'model_registry.csv');cohort=json.loads((HERE/'trace_cohort.json').read_text())['model_ids']
    canonical_fills=pd.read_csv(ROOT/'research/outputs/playbook_fill_ledger.csv.gz')
    canonical_fills['second']=pd.to_datetime(canonical_fills.timestamp_ist).map(lambda t:int(t.timestamp()))
    canonical_groups={k:g for k,g in canonical_fills.groupby(['underlying','expiry_date'])}
    actual=pd.read_csv(PRIOR/'outputs/observed_action_targets.csv.gz');actual_groups={int(cid):g for cid,g in actual.groupby('cycle_id')}
    raw=pd.read_csv(HERE/'closed_loop_cycle_scores.csv.gz',dtype={'prediction_hash':str});rawfull=raw[raw.phase.eq(2)]
    predicted=pd.read_csv(HERE/'closed_loop_coarse.csv.gz');pg={k:g for k,g in predicted.groupby(['model_id','cycle_id'])}
    cases=pd.read_csv(HERE/'reversal_motif_ledger.csv');masks={};sourceids=set()
    for radius,label in [(5,'non_motif'),(125,'non_motif_halo')]:
        mask=set()
        for m in cases.itertuples():
            cid=indexmap[(m.underlying,m.expiry_date)];lo=int(pd.Timestamp(m.first_close_to_zero_ist).timestamp())-radius;hi=int(pd.Timestamp(m.neutralized_ist).timestamp())+radius
            for minute in range(lo//60,hi//60+1):mask.add((cid,minute,m.strike,int(m.option_type=='PE')))
        masks[label]=mask
    cache={};rows=[];mismatches=[];initial=[];intermediate=[];carry=[]
    for cid in range(len(meta)):
        z=np.load(market_cache()/f'cycle_{cid:02}.npz');cache[cid]={key:z[key] for key in ['minutes','clock','strikes','rights','observed','base','feature','open']};z.close()
    for model,cid in itertools.product(cohort,range(len(meta))):
        d=cache[cid];base=int(d['base']);p=pg.get((model,cid),predicted.iloc[:0]);a=actual_groups[cid]
        T,C=d['observed'].shape;lookup={(int(k),int(r)):j for j,(k,r) in enumerate(zip(d['strikes'],d['rights']))};times={t:i for i,t in enumerate(d['minutes'])}
        delta=np.zeros((T,C),np.int64)
        if len(p):
            ti=np.array([times[t] for t in p.minute]);ci=np.array([lookup[(k,r)] for k,r in zip(p.strike,p.right)]);sign=np.where(p.action.isin([0,3]),-1,1)
            np.add.at(delta,(ti,ci),p.quantity.to_numpy()*sign)
        sim=np.cumsum(delta,axis=0);obs=d['observed'];inv_error=np.abs(sim-obs);inv_denom=np.abs(sim)+np.abs(obs)
        original=rawfull[rawfull.model_id.eq(model)&rawfull.cycle_id.eq(cid)].iloc[0]
        known=meta[cid]['dates'][0]<meta[cid]['expiry_date']
        for scope in ['full','non_motif','non_motif_halo']:
            if scope=='full':pp=p;aa=a;allowed=np.ones((T,C),bool)
            else:
                remove=masks[scope];pp=p.loc[[ (cid,int(r.minute),int(r.strike),int(r.right)) not in remove for r in p.itertuples()]];aa=a.loc[[(cid,int(r.minute),int(r.strike),int(r.right)) not in remove for r in a.itertuples()]]
                allowed=np.ones((T,C),bool)
                for cc,t,k,right in remove:
                    if cc==cid and t in times and (k,right) in lookup:allowed[times[t],lookup[(k,right)]]=False
            metric,pl,al,pairs,extras,misses=match_score(pp,aa,base)
            denominator=inv_denom[allowed].sum();metric['inventory_score']=1-inv_error[allowed].sum()/denominator if denominator else 1.
            final=original.final_score
            v=np.array([metric['event_macro_f1'],metric['quantity_score'],metric['inventory_score'],final]);w=np.array([.4,.2,.3,.1]);good=np.isfinite(v)
            metric.update(primary_raw=float((v[good]*w[good]).sum()/w[good].sum()),final_score=final)
            row=dict(model_id=model,cycle_id=cid,index=meta[cid]['underlying'],expiry_date=meta[cid]['expiry_date'],split=original.split,scope=scope,initialization_known=known,**metric);rows.append(row)
            if scope=='full':
                assert abs(metric['event_macro_f1']-original.event_macro_f1)<1e-8
                assert abs(metric['quantity_score']-original.quantity_score)<1e-8
                assert abs(metric['inventory_score']-original.inventory_score)<1e-8
                for pi,ai in pairs:
                    x,y=pl[pi],al[ai]
                    if x['quantity']!=y['quantity'] or x['minute']!=y['minute']:
                        mismatches.append(dict(model_id=model,cycle_id=cid,kind='mis_sized' if x['quantity']!=y['quantity'] else 'mis_timed',strike=x['strike'],right=x['right'],action=ACTIONS[x['action']],predicted_time_ist=timestamp(x['minute']),observed_time_ist=timestamp(y['minute']),predicted_quantity=x['quantity'],observed_quantity=y['quantity']))
                for pi in extras:
                    x=pl[pi];mismatches.append(dict(model_id=model,cycle_id=cid,kind='extra_action',strike=x['strike'],right=x['right'],action=ACTIONS[x['action']],predicted_time_ist=timestamp(x['minute']),observed_time_ist='',predicted_quantity=x['quantity'],observed_quantity=0))
                for ai in misses:
                    x=al[ai];mismatches.append(dict(model_id=model,cycle_id=cid,kind='missed_action',strike=x['strike'],right=x['right'],action=ACTIONS[x['action']],predicted_time_ist='',observed_time_ist=timestamp(x['minute']),predicted_quantity=0,observed_quantity=x['quantity']))
        if known:
            starts=np.flatnonzero(d['clock']==555);endpre=int(starts[1]-1) if len(starts)>1 else T-1
            values={}
            for right,label in [(0,'CE'),(1,'PE')]:
                columns=d['rights']==right
                values['pred_'+label+'_short']=int(np.maximum(-sim[endpre,columns],0).sum());values['pred_'+label+'_long']=int(np.maximum(sim[endpre,columns],0).sum())
                values['observed_'+label+'_short']=int(np.maximum(-obs[endpre,columns],0).sum());values['observed_'+label+'_long']=int(np.maximum(obs[endpre,columns],0).sum())
            carry.append(dict(model_id=model,cycle_id=cid,index=meta[cid]['underlying'],expiry_date=meta[cid]['expiry_date'],long_quantity_covers_shorts=values['pred_CE_long']>=values['pred_CE_short'] and values['pred_PE_long']>=values['pred_PE_short'],**values))
            firstday=meta[cid]['dates'][0];start=int(pd.Timestamp(firstday+' 09:15',tz='Asia/Kolkata').timestamp()//60)
            op=p[p.minute.between(start,start+2)];oa=a[a.minute.between(start,start+2)]
            child=canonical_groups[(meta[cid]['underlying'],meta[cid]['expiry_date'])]
            child=child[child.second.ge(start*60)&child.second.lt((start+3)*60)&child.opening_quantity.gt(0)]
            first={}
            for role,label in [(0,'short'),(2,'wing')]:
                for right,rlabel in [(0,'CE'),(1,'PE')]:
                    pred=op[op.action.eq(role)&op.right.eq(right)].sort_values(['first_second','strike'])
                    first_actual=first_execution_signature(child,'Sell' if role==0 else 'Buy',rlabel)
                    act=oa[oa.action.eq(role)&oa.right.eq(right)]
                    first[f'pred_first_{rlabel}_{label}']=int(pred.iloc[0].strike) if len(pred) else np.nan
                    first[f'act_first_{rlabel}_{label}']=first_actual['strike']
                    first[f'act_first_{rlabel}_{label}_source']=first_actual['source']
                    first[f'act_first_{rlabel}_{label}_tied_strikes']=first_actual['tied_strikes']
                    first[f'pred_{rlabel}_{label}_gross']=int(pred.quantity.sum());first[f'act_{rlabel}_{label}_gross']=int(act.quantity.sum())
            snapshot=times[start+1];net={}
            for label,sign in [('short',-1),('long',1)]:
                for right,rlabel in [(0,'CE'),(1,'PE')]:
                    cols=d['rights']==right;net[f'pred_{rlabel}_{label}_net0917']=int(np.maximum(sign*sim[snapshot,cols],0).sum());net[f'act_{rlabel}_{label}_net0917']=int(np.maximum(sign*obs[snapshot,cols],0).sum())
            first['both_short_gross_exact']=first['pred_CE_short_gross']==first['act_CE_short_gross'] and first['pred_PE_short_gross']==first['act_PE_short_gross']
            first['both_first_wings_exact']=first['pred_first_CE_wing']==first['act_first_CE_wing'] and first['pred_first_PE_wing']==first['act_first_PE_wing']
            first['both_first_shorts_exact']=first['pred_first_CE_short']==first['act_first_CE_short'] and first['pred_first_PE_short']==first['act_first_PE_short']
            first['four_role_net_exact']=all(net[f'pred_{right}_{role}_net0917']==net[f'act_{right}_{role}_net0917'] for right in ['CE','PE'] for role in ['short','long'])
            initial.append(dict(model_id=model,cycle_id=cid,index=meta[cid]['underlying'],entry_date=firstday,split=original.split,
                documented_delayed_exception=firstday=='2026-10-05' and meta[cid]['underlying']=='NIFTY',**first,**net))
        clockmap={t:int(d['clock'][i]) for t,i in times.items()}
        for right in [0,1]:
            pp=p[p.action.eq(1)&p.right.eq(right)&p.minute.map(clockmap).lt(900)];aa=a[a.action.eq(1)&a.right.eq(right)&a.minute.map(clockmap).lt(900)]
            _,pl,al,match,ex,mi=match_score(pp,aa,base)
            intermediate.append(dict(model_id=model,cycle_id=cid,index=meta[cid]['underlying'],right=right,split=original.split,initialization_known=known,predicted=len(pp),observed=len(aa),matched=len(match),false_actions=len(ex),missed_actions=len(mi)))
    masked=pd.DataFrame(rows);masked.to_csv(HERE/'component_cycle_scores.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3})
    pd.DataFrame(mismatches).to_csv(HERE/'policy_execution_mismatch_ledger.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3})
    pd.DataFrame(carry).to_csv(HERE/'carry_snapshot_scores.csv',index=False)
    initial=pd.DataFrame(initial);initial.to_csv(HERE/'opening_initialisation_scores.csv',index=False)
    pd.DataFrame(intermediate).to_csv(HERE/'intermediate_exit_scores.csv',index=False)
    # Full84 policy comparisons are unchanged; paired mechanistic comparisons use
    # selected-policy cohort, both outside selected motif minutes and with halo.
    rng=np.random.default_rng(59084);uncertainty=[]
    for scope in ['full','non_motif','non_motif_halo']:
        for split in [0,1,2]:
            q=masked[masked.scope.eq(scope)&masked.split.eq(split)&masked.initialization_known]
            for mech in range(1,7):
                cid=policy*7+mech
                for metric in ['event_macro_f1','quantity_score','inventory_score','primary_raw']:
                    p=q[q.model_id.isin([baseline,cid])].pivot(index='cycle_id',columns='model_id',values=metric).dropna()
                    diff=(p[cid]-p[baseline]).to_numpy();boot=diff[rng.integers(0,len(diff),(2000,len(diff)))].mean(axis=1)
                    uncertainty.append(dict(model_id=cid,baseline=baseline,mechanics_id=mech,split=split,scope=scope,metric=metric,cycles=len(diff),mean_difference=diff.mean(),low95=np.quantile(boot,.025),high95=np.quantile(boot,.975),improved_cycles=int((diff>1e-12).sum())))
    pd.DataFrame(uncertainty).to_csv(HERE/'paired_cycle_uncertainty.csv',index=False)
    # Every simulator closure (including no reversal) is a negative opportunity.
    closures=pd.read_csv(HERE/'closed_loop_closures.csv.gz');reversals=[];matched_motifs=[]
    targets=[]
    for r in cases.itertuples():targets.append(dict(motif_id=r.motif_id,cycle_id=indexmap[(r.underlying,r.expiry_date)],strike=r.strike,right=int(r.option_type=='PE'),second=int(pd.Timestamp(r.first_close_to_zero_ist).timestamp()),quantity=r.prior_atomic_quantity))
    for model in models.model_id:
        p=closures[closures.model_id.eq(model)&closures.conservative_motif.eq(1)].sort_values(['close_second','strike','right']);used=set();ma=0;strict=0
        for r in p.itertuples():
            choices=[a for a in targets if a['motif_id'] not in used and a['cycle_id']==r.cycle_id and a['strike']==r.strike and a['right']==r.right and abs(a['second']-r.close_second)<=120]
            if choices:
                a=min(choices,key=lambda a:abs(a['second']-r.close_second));used.add(a['motif_id']);ma+=1;exact=a['quantity']==r.prior_quantity;strict+=exact
                matched_motifs.append(dict(model_id=model,motif_id=a['motif_id'],simulated_close_ist=timestamp(r.close_second//60),close_error_seconds=r.close_second-a['second'],exact_prior_quantity=exact))
        reversals.append(dict(model_id=model,predicted_motifs=len(p),fixed_observed_motifs=59,matched_contract_time=ma,matched_exact_prior_quantity=strict,precision=ma/len(p) if len(p) else np.nan,recall=ma/59,false_motifs=len(p)-ma,missed_motifs=59-ma,aged_closure_opportunities=int(closures.model_id.eq(model).sum())))
    pd.DataFrame(reversals).to_csv(HERE/'reversal_pattern_coverage.csv',index=False);pd.DataFrame(matched_motifs,columns=['model_id','motif_id','simulated_close_ist','close_error_seconds','exact_prior_quantity']).to_csv(HERE/'matched_reversal_predictions.csv',index=False)
    # Quantities are assessed against strict same-sign controls as well as wider
    # non-motif controls; the original size cap makes one-base equality inevitable.
    controls=pd.read_csv(HERE/'all_closure_controls.csv');control_intervals=[]
    for bounded in [False,True]:
        for mult in [False,True]:
            q=controls[controls.reopen_within10]
            if bounded:q=q[q.bounded_peak.eq(True)]
            if mult:q=q[q.closed_base_units.gt(1)]
            cycles=sorted(set(zip(q.underlying,q.expiry_date)));case_count=[];ctrl_count=[]
            for u,e in cycles:
                g=q[q.underlying.eq(u)&q.expiry_date.eq(e)];c=g[g.motif_id.notna()];n=g[g.motif_id.isna()&g.reopening_opposite.eq(False)]
                case_count.append([c.quantity_equal.eq(True).sum(),len(c)]);ctrl_count.append([n.quantity_equal.eq(True).sum(),len(n)])
            a=np.array(case_count);b=np.array(ctrl_count);draw=rng.integers(0,len(cycles),(3000,len(cycles)));aa=a[draw].sum(axis=1);bb=b[draw].sum(axis=1);valid=(aa[:,1]>0)&(bb[:,1]>0);dif=aa[valid,0]/aa[valid,1]-bb[valid,0]/bb[valid,1]
            control_intervals.append(dict(bounded_peak=bounded,multiple_base_only=mult,case_count=int(a[:,1].sum()),control_count=int(b[:,1].sum()),cycles=len(cycles),difference=float(a[:,0].sum()/a[:,1].sum()-b[:,0].sum()/b[:,1].sum()) if b[:,1].sum() else np.nan,low95=float(np.quantile(dif,.025)) if len(dif) else np.nan,high95=float(np.quantile(dif,.975)) if len(dif) else np.nan,interpretation='unadjusted dependent-cycle contrast; inadequate exact matching/common support'))
    pd.DataFrame(control_intervals).to_csv(HERE/'control_cycle_uncertainty.csv',index=False)
    # Geometric intent compatibility is separate from actual executable quote
    # coverage and executed first-wing matching. This does not change the module.
    seed_rows=[]
    for r in initial[initial.model_id.eq(baseline)].itertuples():
        d=cache[r.cycle_id];meta_row=meta[r.cycle_id];where=int(np.flatnonzero(d['clock'].eq(556) if hasattr(d['clock'],'eq') else d['clock']==556)[0]);spot=d['feature'][where,0];grid=meta_row['strike_grid'];center=int(np.floor(spot/grid+.5))*grid;distance=2000 if meta_row['underlying']=='NIFTY' or meta_row['expiry_date']>='2026-09-16' else 4000
        for right,label in [(0,'CE'),(1,'PE')]:
            strike=center+(distance if right==0 else -distance);observed=getattr(r,'act_first_'+label+'_wing');matches=np.flatnonzero((d['strikes']==strike)&(d['rights']==right));j=int(matches[0]) if len(matches) else None
            seed_rows.append(dict(cycle_id=r.cycle_id,index=r.index,entry_date=r.entry_date,right=label,intended_strike=strike,observed_first_wing=observed,intent_exact=strike==observed,intent_within_two_grids=abs(strike-observed)<=2*grid,stored_contract=j is not None,positive_0916_open=bool(j is not None and np.isfinite(d['open'][where,j]) and d['open'][where,j]>0),meaning='intent compatibility is not execution prediction'))
    pd.DataFrame(seed_rows).to_csv(HERE/'seed_geometry_and_quote_audit.csv',index=False)
    # Prior controller contradiction remains a separate, unchanged benchmark.
    old=pd.read_csv(PRIOR/'outputs/initial_entry_reconstruction.csv');old=old[old.candidate_id.eq(13845)&old.first_received_phase.eq('preexpiry')]
    assert len(old)==32
    old_wings=(old.predicted_first_CE_wing_strike.eq(old.observed_first_CE_wing_strike)&old.predicted_first_PE_wing_strike.eq(old.observed_first_PE_wing_strike)).sum()
    old_qty=(old.predicted_CE_short_quantity.eq(old.observed_CE_short_quantity)&old.predicted_PE_short_quantity.eq(old.observed_PE_short_quantity)).sum()
    assert old_wings==0 and old_qty==0
    audited_old=[]
    for r in old.itertuples():
        source=initial[initial.model_id.eq(baseline)&initial.cycle_id.eq(r.cycle_id)].iloc[0]
        wings=(r.predicted_first_CE_wing_strike==source.act_first_CE_wing and r.predicted_first_PE_wing_strike==source.act_first_PE_wing)
        audited_old.append(wings)
    comparison=[dict(model='prior selected13845',sessions=32,both_first_wings_exact=0,both_short_gross_exact=0,four_role_net_exact=np.nan,scope='unchanged prior first-three-minute benchmark')]
    comparison.append(dict(model='prior13845 child-second re-audit',sessions=32,both_first_wings_exact=int(sum(audited_old)),both_short_gross_exact=0,four_role_net_exact=np.nan,scope='actual first child sorted by event second and source row; prior predicted first-contract convention unchanged'))
    for model,g in initial.groupby('model_id'):
        comparison.append(dict(model=str(model),sessions=len(g),both_first_wings_exact=int(g.both_first_wings_exact.sum()),both_short_gross_exact=int(g.both_short_gross_exact.sum()),four_role_net_exact=int(g.four_role_net_exact.sum()),scope='actual first child ordered by event second/source row; received32 starts including delayed exception'))
    pd.DataFrame(comparison).to_csv(HERE/'opening_vs_prior_contradiction.csv',index=False)
    # Discriminating witnesses: same latent goal stream, different execution paths.
    fills=pd.read_csv(HERE/'detailed_fills.csv.gz');goals=pd.read_csv(HERE/'frozen_targets_goals.csv.gz');different=[]
    for other in [baseline+1,baseline+4,baseline+5]:
        a=fills[fills.model_id.eq(baseline)];b=fills[fills.model_id.eq(other)]
        aset=set(a[['cycle_id','second','strike','right','side','incremental_quantity']].itertuples(index=False,name=None));bset=set(b[['cycle_id','second','strike','right','side','incremental_quantity']].itertuples(index=False,name=None))
        samples=sorted(aset^bset)[:8]
        for cid,sec,k,right,side,qty in samples:
            def show(model):
                f=fills[fills.model_id.eq(model)&fills.cycle_id.eq(cid)&fills.second.eq(sec)&fills.strike.eq(k)&fills.right.eq(right)]
                return '; '.join(f'{r.side} {r.incremental_quantity} [{r.origin}] request {r.request_id}' for r in f.itertuples()) or 'no fill'
            original_fills=pd.read_csv(ROOT/'research/outputs/playbook_fill_ledger.csv.gz',usecols=['underlying','expiry_date','timestamp_ist','source_row','parent_id','strike','option_type','side','incremental_quantity']) if not different else original_fills
            f=original_fills[original_fills.underlying.eq(meta[cid]['underlying'])&original_fills.expiry_date.eq(meta[cid]['expiry_date'])&original_fills.strike.eq(k)&original_fills.option_type.eq(['CE','PE'][right])]
            ss=pd.to_datetime(f.timestamp_ist).map(lambda t:int(t.timestamp()));f=f[(ss-sec).abs()<=5]
            different.append(dict(model_a=baseline,model_b=other,index=meta[cid]['underlying'],expiry_date=meta[cid]['expiry_date'],timestamp_ist=pd.Timestamp(sec,unit='s',tz='UTC').tz_convert('Asia/Kolkata').isoformat(),strike=k,right=['CE','PE'][right],a_action=show(baseline),b_action=show(other),observed_within5sec='; '.join(f'{r.side} {r.incremental_quantity} at {r.timestamp_ist} source {r.source_row} parent {r.parent_id}' for r in f.itertuples()) or 'none',distinction='executed sequence observable, intended decisions and submissions unobserved; no tick fill-price verification'))
    pd.DataFrame(different).to_csv(HERE/'candidate_discriminating_events.csv',index=False)
    # At actual episode times, localize discrepancies without asserting that the
    # original desired target was zero. These observations never drive a model.
    target_stream=pd.read_csv(HERE/'closed_loop_goals.csv.gz');target_stream=target_stream[target_stream.model_id.eq(baseline)]
    from evaluate import decode_book
    localisation=[]
    for case in cases.itertuples():
        cid=indexmap[(case.underlying,case.expiry_date)];sec=int(pd.Timestamp(case.first_close_to_zero_ist).timestamp());right=int(case.option_type=='PE');contract=(case.strike,right)
        g=target_stream[target_stream.cycle_id.eq(cid)&target_stream.second.le(sec)].sort_values('second').tail(1)
        target=decode_book(g.desired_book.iloc[0]).get(contract,0) if len(g) else 0
        pf=fills[fills.model_id.eq(baseline)&fills.cycle_id.eq(cid)&fills.strike.eq(case.strike)&fills.right.eq(right)&fills.second.lt(sec)].sort_values('second')
        confirmed=int(pf.quantity_after.iloc[-1]) if len(pf) else 0
        kind='model_contract_absent' if not target and not confirmed else 'target_retained_at_recorded_flat' if target else 'zero_model_target_inventory_remaining'
        localisation.append(dict(motif_id=case.motif_id,cycle_id=cid,model_id=baseline,index=case.underlying,expiry_date=case.expiry_date,strike=case.strike,right=case.option_type,observed_close_ist=case.first_close_to_zero_ist,observed_prior_quantity=case.prior_atomic_quantity,observed_after_close=0,model_confirmed_before_close=confirmed,model_desired_at_close=target,classification=kind,last_model_goal_second=int(g.second.iloc[0]) if len(g) else np.nan,interpretation='comparison to simulated target only; original desired target and decision remain unobserved'))
    pd.DataFrame(localisation).to_csv(HERE/'case_policy_execution_localisation.csv',index=False)
    # Time-context negative controls are descriptive proxies, not inferred causes.
    actual_controls=pd.read_csv(HERE/'all_closure_controls.csv');actual_controls['clock']=pd.to_datetime(actual_controls.close_ist).dt.hour*60+pd.to_datetime(actual_controls.close_ist).dt.minute
    actual_controls['context']=np.where(actual_controls.phase.eq('expiry')&actual_controls.clock.ge(900),'expiry_after1500',np.where(actual_controls.phase.eq('expiry'),'expiry_before1500','preexpiry'))
    actual_controls['fixed_case']=actual_controls.motif_id.notna()
    actual_controls.groupby('context').agg(aged_closures=('sequence_id','size'),motifs=('fixed_case','sum'),reopenings10=('reopen_within10','sum')).reset_index().to_csv(HERE/'closure_context_controls.csv',index=False)
    # Exact minute-level equivalence (not second-level OMS identification).
    signatures=[]
    for (model,cid),g in predicted.groupby(['model_id','cycle_id']):
        signatures.append((model,cid,tuple(g[['minute','strike','right','action','quantity']].itertuples(index=False,name=None))))
    sig={model:tuple((cid,events) for mid,cid,events in signatures if mid==model) for model in cohort}
    equivalent=[dict(model_a=a,model_b=b,same_minute_action_trace=sig[a]==sig[b]) for a,b in itertools.combinations(cohort,2)]
    pd.DataFrame(equivalent).to_csv(HERE/'observable_equivalence.csv',index=False)
    # Exact recurring-window quantities use detailed child seconds for the six
    # non-explosive mechanics, not first/last-time guesses from minute aggregates.
    detailed_fills=fills.copy();sg=np.where(detailed_fills.side.eq('Buy'),1,-1);before=detailed_fills.quantity_before.to_numpy();qty=detailed_fills.incremental_quantity.to_numpy()
    cl=np.where(before*sg<0,np.minimum(np.abs(before),qty),0);detailed_fills['opening_quantity']=qty-cl
    detailed_fills['opening_role']=np.where(detailed_fills.side.eq('Sell'),detailed_fills.right,detailed_fills.right+2)
    windows=pd.read_csv(ROOT/'research/outputs/playbook_allocation_windows.csv');windows=windows[windows.phase.eq('preexpiry')&windows.clock_type.eq('recurring17')]
    window_rows=[];roles=['CE_short','PE_short','CE_long','PE_long']
    for model in detailed_fills.model_id.unique():
        m=detailed_fills[detailed_fills.model_id.eq(model)]
        for w in windows.itertuples():
            cid=indexmap[(w.underlying,w.expiry_date)];start=int(pd.Timestamp(w.window_start_ist).timestamp());end=int(pd.Timestamp(w.window_end_exclusive_ist).timestamp())
            q=m[m.cycle_id.eq(cid)&m.second.ge(start)&m.second.lt(end)];values=[int(q[q.opening_role.eq(r)].opening_quantity.sum()) for r in range(4)];actual_values=[int(getattr(w,'add_'+role)) for role in roles]
            window_rows.append(dict(model_id=model,cycle_id=cid,index=w.underlying,date=w.date,expiry=w.expiry_date,clock=w.clock,split='fit' if w.expiry_date<='2026-07-31' else 'validation' if w.expiry_date<='2026-08-31' else 'later',short_pair_exact=values[:2]==actual_values[:2],four_roles_exact=values==actual_values,absolute_error_base_units=sum(abs(x-y) for x,y in zip(values,actual_values))/(65 if w.underlying=='NIFTY' else 20),predicted_quantities='/'.join(map(str,values)),observed_quantities='/'.join(map(str,actual_values))))
    pd.DataFrame(window_rows).to_csv(HERE/'recurring_allocation_scores.csv',index=False)
    parent_rows=[]
    # Parent-request size and child fragmentation are different observable units.
    original_parents=pd.read_csv(ROOT/'research/outputs/allocation_parent_inventory.csv')
    for (index,phase),g in original_parents[original_parents.role.eq('new_short')].assign(phase=lambda x:np.where(x['first'].str[:10]<x.expiry_date,'preexpiry','expiry')).groupby(['underlying','phase']):
        unit=65 if index=='NIFTY' else 20;parent_rows.append(dict(model='observed',index=index,phase=phase,new_short_parents=len(g),single_base_requests=int(g.requested_quantity.eq(unit).sum()),single_base_rate=float(g.requested_quantity.eq(unit).mean())))
    detailed_fills['pure_open']=detailed_fills.opening_quantity.eq(detailed_fills.incremental_quantity)
    for (model,cid,request),g in detailed_fills.groupby(['model_id','cycle_id','request_id']):
        if not g.side.eq('Sell').all() or not g.pure_open.all():continue
        first=int(g.second.min());day=pd.Timestamp(first,unit='s',tz='UTC').tz_convert('Asia/Kolkata').date().isoformat();unit=65 if meta[cid]['underlying']=='NIFTY' else 20
        parent_rows.append(dict(model=str(model),index=meta[cid]['underlying'],phase='preexpiry' if day<meta[cid]['expiry_date'] else 'expiry',new_short_parents=1,single_base_requests=int(abs(g.requested_signed_quantity.iloc[0])==unit)))
    parent=pd.DataFrame(parent_rows);grouped=parent.groupby(['model','index','phase'])[['new_short_parents','single_base_requests']].sum().reset_index();grouped['single_base_rate']=grouped.single_base_requests/grouped.new_short_parents;grouped.to_csv(HERE/'parent_order_granularity.csv',index=False)
    # Detailed traces must agree with the already scored all-model run.
    detailed=pd.read_csv(HERE/'detailed_scores.csv.gz',dtype={'prediction_hash':str}).rename(columns={'candidate_id':'model_id'})
    check=detailed.merge(raw[['model_id','cycle_id','phase','prediction_hash']],on=['model_id','cycle_id','phase'],suffixes=('_repeat','_main'),validate='one_to_one')
    assert check.prediction_hash_repeat.eq(check.prediction_hash_main).all()
    audit=pd.read_csv(HERE/'closed_loop_request_audit.csv.gz')
    assert (audit.requested_quantity==audit.executed_quantity+audit.cancelled_quantity+audit.failed_quantity+audit.pending_quantity).all()
    pd.DataFrame([dict(model_id=model,cycles=len(g),latent_requests=int(g.requests.sum()),executed_child_fills=int(g.child_fills.sum()),unfilled_quantity=int(g.failed_quantity.sum()),duplicate_requests=int(g.duplicate_requests.sum()),correction_requests=int(g.correction_requests.sum())) for model,g in audit.groupby('model_id')]).to_csv(HERE/'execution_audit_summary.csv',index=False)
    print('Analysis complete:',len(cohort),'trace models,',len(mismatches),'mismatches; old0/32 benchmark retained; all request quantities conserved.')

if __name__=='__main__':run()
