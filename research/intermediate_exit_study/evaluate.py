"""Twelve frozen trigger hypotheses, cycle exclusion and chronological checks."""
from __future__ import annotations
import json
from collections import defaultdict
import numpy as np
import pandas as pd
from build import HERE,PRIOR,META,save,iso

RULES=[
 ('premium_loss50','premium_loss_pct','ge',50),('premium_profit50','premium_loss_pct','le',-50),
 ('trailing_rebound25','trailing_rebound_pct','ge',25),('side_loss1pct','side_equity_pct','le',-1),
 ('side_drawdown_halfpct','side_drawdown_pct','ge',.5),('adverse_spot5_quarterpct','adverse_spot5_pct','ge',.25),
 ('favourable_spot5_quarterpct','adverse_spot5_pct','le',-.25),('adverse_entry_halfpct','adverse_entry_pct','ge',.5),
 ('abs_delta75','contract_abs_delta','ge',.75),('iv_rise1point5','iv_change5_points','ge',1),
 ('protection_deficit','protection_deficit_units','ge',1),('allocation_profit25','premium_loss_pct','allocation',-25)]
BASES=['clock_only','inventory_only'];NAMES=[x[0] for x in RULES]

def complete_coverage(ranked,cov,folds):
    """Selection coverage follows the training-chosen rule on each test cycle."""
    out=ranked.copy()
    for i,r in out.iterrows():
        if r.hypothesis in BASES:out.loc[i,'event_feature_coverage']=1.
        elif r.hypothesis=='training_selected':
            selected=folds[folds['mode']==r['mode']]
            available=total=0
            for f in selected.itertuples():
                row=cov[(cov.cycle_id==f.test_cycle_id)&cov.hypothesis.eq(f.selected_hypothesis)].iloc[0]
                available+=int(row.events_feature_available);total+=int(row.events)
            out.loc[i,'event_feature_coverage']=available/total if total else np.nan
    return out

def masks(d,name):
    _,field,op,level=next(r for r in RULES if r[0]==name);v=d[field].to_numpy(float);valid=np.isfinite(v)
    state=(v>=level) if op=='ge' else (v<=level)
    if op=='allocation':
        a=d.last_side_add_seconds.to_numpy(float);valid&=np.isfinite(a);state&=(a>0)&(a<=120)
    return state&valid,valid

def signals(d,state):
    """Historical-state conditional predictions; no labels or future filters."""
    fires=[]
    # d may retain original global indices. Use position for arrays.
    work=d.reset_index(drop=True)
    for _,g in work.groupby(['cycle_id','strike','option_type'],sort=False):
        prior=False;last=-10**20;last_t=None;prior_epoch=None;prior_lastadd=None
        for r in g.itertuples():
            i=r.Index;t=r.second;value=bool(state[i]);newadd=t-r.last_contract_add_seconds if np.isfinite(r.last_contract_add_seconds) else None
            epoch=r.epoch_start_ist
            contiguous=last_t is not None and t-last_t==60 and epoch==prior_epoch
            newly_added=newadd is not None and prior_lastadd is not None and newadd>prior_lastadd
            if value and (not prior or not contiguous or newly_added) and t-last>=300:
                fires.append(i);last=t
            prior=value;last_t=t;prior_epoch=epoch;prior_lastadd=newadd
    cols=['cycle_id','underlying','expiry_date','date','phase','strike','option_type','second','short_units','known_initialization']
    return work.iloc[fires][cols].copy()

def fit_baselines(train_risk,train_events):
    params={}
    for name in BASES:
        if name=='clock_only':
            denom=train_risk.groupby('time_bin5').size();num=(train_events.clock_minute//5).value_counts()
            rates=num.reindex(denom.index,fill_value=0)/denom
            fallback=sorted(rates[rates>0].index,key=lambda b:(-rates.loc[b],b))[:3]
        else:fallback=float(train_events.short_units.median())
        p={('ALL','ALL','ALL'):fallback}
        for key,g in train_risk.groupby(['underlying','option_type','phase']):
            e=train_events[(train_events.underlying==key[0])&(train_events.option_type==key[1])&(train_events.phase==key[2])]
            if name=='clock_only':
                denom=g.groupby('time_bin5').size();num=(e.clock_minute//5).value_counts();rates=num.reindex(denom.index,fill_value=0)/denom
                bins=sorted(rates[rates>0].index,key=lambda b:(-rates.loc[b],b))[:3];p[key]=bins if len(e) else fallback
            else:p[key]=float(e.short_units.median()) if len(e) else float(train_events.short_units.median())
        params[name]=p
    return params

def baseline_predictions(d,params,name):
    fallback=params[name][('ALL','ALL','ALL')]
    if name=='clock_only':state=np.array([r.time_bin5 in params[name].get((r.underlying,r.option_type,r.phase),fallback) for r in d.itertuples()])
    else:state=np.array([r.short_units>=params[name].get((r.underlying,r.option_type,r.phase),fallback) for r in d.itertuples()])
    return signals(d,state)

def match(p,e,tolerance):
    """Maximum-cardinality chronological matching for same-contract intervals."""
    pairs=[];false=[];miss=[]
    pg={k:g for k,g in p.groupby(['cycle_id','strike','option_type'],sort=False)}
    eg={k:g for k,g in e.groupby(['cycle_id','strike','option_type'],sort=False)}
    for key in sorted(set(pg)|set(eg)):
        pp=pg.get(key,p.iloc[:0]).sort_values('second').to_dict('records');aa=eg.get(key,e.iloc[:0]).sort_values('second').to_dict('records');i=j=0
        while i<len(pp) and j<len(aa):
            if pp[i]['second']<aa[j]['second']-tolerance:false.append(pp[i]);i+=1
            elif pp[i]['second']>aa[j]['second']+tolerance:miss.append(aa[j]);j+=1
            else:pairs.append((pp[i],aa[j]));i+=1;j+=1
        false.extend(pp[i:]);miss.extend(aa[j:])
    return pairs,false,miss

def metrics(p,e,tolerance=120):
    pairs,false,miss=match(p,e,tolerance);n=len(pairs);pn=len(p);an=len(e)
    return dict(predicted=pn,observed=an,matched=n,false_positives=len(false),missed_exits=len(miss),
        precision=n/pn if pn else np.nan,recall=n/an if an else np.nan,f1=2*n/(pn+an) if pn+an else np.nan,
        median_signed_error_seconds=float(np.median([x['second']-y['second'] for x,y in pairs])) if n else np.nan)

def describe_controls(risk,events):
    pairs=pd.read_csv(HERE/'matched_nonexit_controls.csv');controls=risk.set_index('observation_id');cases=events.set_index('event_id');rows=[]
    fields=['premium_loss_pct','trailing_rebound_pct','side_equity_pct','side_drawdown_pct','adverse_spot5_pct','adverse_entry_pct','contract_abs_delta','iv_change5_points','protection_deficit_units','age_minutes']
    for tier,g in pairs.groupby('tier'):
        for field in fields:
            bycase=[]
            for eid,p in g.groupby('event_id'):
                cv=controls.loc[p.control_id,field].mean();ev=cases.loc[eid,field]
                if np.isfinite(cv) and np.isfinite(ev):bycase.append((int(cases.loc[eid,'cycle_id']),ev-cv))
            v=np.array([x[1] for x in bycase]);cy=sorted({x[0] for x in bycase})
            rows.append(dict(tier=tier,feature=field,paired_cases=len(v),cycles=len(cy),median_case_minus_control=float(np.median(v)) if len(v) else np.nan,
                positive_case_fraction=float(np.mean(v>0)) if len(v) else np.nan,interpretation='descriptive matched contrasts; no independent-row inference or causal effect'))
    save(pd.DataFrame(rows),'matched_feature_contrasts.csv')
    rulecontrasts=[]
    for tier,g in pairs.groupby('tier'):
        for name in NAMES:
            caseids=g.event_id.unique();cc=cases.loc[caseids];ct=controls.loc[g.control_id];a,av=masks(cc,name);b,bv=masks(ct,name)
            rulecontrasts.append(dict(tier=tier,hypothesis=name,case_available=int(av.sum()),cases=len(cc),case_satisfied=int(a.sum()),control_available=int(bv.sum()),controls=len(ct),control_satisfied=int(b.sum())))
    save(pd.DataFrame(rulecontrasts),'matched_condition_contrasts.csv')

def run():
    risk=pd.read_csv(HERE/'pre_event_risk_set.csv.gz');all_events=pd.read_csv(HERE/'exit_case_ledger.csv.gz');atoms=pd.read_csv(HERE/'short_cover_atoms.csv.gz')
    events=all_events[all_events.outcome_stratum=='intermediate'].copy();known=sorted(events.loc[events.known_initialization,'cycle_id'].unique())
    catalog=[dict(hypothesis=n,feature=f,operator=o,threshold=v,parameters_fixed=True) for n,f,o,v in RULES]
    save(pd.DataFrame(catalog),'trigger_hypotheses.csv')
    predicted={};coverage=[];allscore=[];counterexamples=[];matched=[]
    for name in NAMES:
        state,valid=masks(risk,name);p=signals(risk,state);p['hypothesis']=name;predicted[name]=p
        evstate,evvalid=masks(events,name)
        for cid in range(35):
            rr=risk.cycle_id.eq(cid).to_numpy();ee=events.cycle_id.eq(cid).to_numpy();coverage.append(dict(hypothesis=name,cycle_id=cid,
                risk_observations=int(rr.sum()),risk_feature_available=int(valid[rr].sum()),events=int(ee.sum()),events_feature_available=int(evvalid[ee].sum()),
                event_condition_satisfied=int(evstate[ee].sum())))
        for cid in range(35):
            pp=p[p.cycle_id==cid];ee=events[events.cycle_id==cid]
            for tol in [60,120,300]:allscore.append(dict(hypothesis=name,cycle_id=cid,tolerance_seconds=tol,**metrics(pp,ee,tol)))
            pairs,fp,miss=match(pp,ee,120)
            for x,y in pairs:matched.append(dict(hypothesis=name,cycle_id=cid,event_id=y['event_id'],predicted_second=x['second'],actual_second=y['second'],error_seconds=x['second']-y['second']))
            for x in fp:counterexamples.append(dict(hypothesis=name,cycle_id=cid,kind='false_signal',second=x['second'],event_id='',strike=x['strike'],option_type=x['option_type']))
            for x in miss:counterexamples.append(dict(hypothesis=name,cycle_id=cid,kind='missed_exit',second=x['second'],event_id=x['event_id'],strike=x['strike'],option_type=x['option_type']))
    fixed=pd.DataFrame(allscore);save(fixed,'fixed_trigger_cycle_scores.csv');save(pd.concat(predicted.values(),ignore_index=True),'fixed_trigger_predictions.csv.gz')
    save(pd.DataFrame(coverage),'feature_coverage_by_cycle.csv');save(pd.DataFrame(counterexamples),'trigger_counterexamples.csv.gz');save(pd.DataFrame(matched),'matched_exit_predictions.csv.gz')
    scores=[];folds=[];basepred=[];selectedpred=[];paramsrows=[];strata=[]
    # A cycle is the inferential unit. Fixed hypotheses have no learned levels.
    for mode in ['leave_one_cycle_out','expanding_chronological']:
        for cid in known:
            train=[k for k in known if k!=cid] if mode=='leave_one_cycle_out' else [k for k in known if META[k]['expiry_date']<META[cid]['expiry_date']]
            if mode=='expanding_chronological' and len(train)<8:continue
            test_r=risk[risk.cycle_id==cid];test_e=events[events.cycle_id==cid]
            train_r=risk[risk.cycle_id.isin(train)];train_e=events[events.cycle_id.isin(train)]
            params=fit_baselines(train_r,train_e)
            selection=fixed[(fixed.cycle_id.isin(train))&(fixed.tolerance_seconds==120)].groupby('hypothesis').f1.mean()
            winner=sorted(selection.index,key=lambda n:(-selection[n],NAMES.index(n)))[0]
            folds.append(dict(mode=mode,test_cycle_id=cid,test_expiry=META[cid]['expiry_date'],test_index=META[cid]['underlying'],training_cycles=';'.join(map(str,train)),
                n_train=len(train),last_training_expiry=max(META[k]['expiry_date'] for k in train),selected_hypothesis=winner,training_macro_f1=float(selection[winner])))
            for name in NAMES+BASES+['training_selected']:
                if name in BASES:
                    pp=baseline_predictions(test_r,params,name);pp['hypothesis']=name;pp['mode']=mode;basepred.append(pp)
                    for key,value in params[name].items():paramsrows.append(dict(mode=mode,test_cycle_id=cid,baseline=name,index=key[0],right=key[1],phase=key[2],parameters=json.dumps(value)))
                else:pp=predicted[winner if name=='training_selected' else name];pp=pp[pp.cycle_id==cid]
                if name=='training_selected':
                    cp=pp.copy();cp['hypothesis']=name;cp['mode']=mode;selectedpred.append(cp)
                for tol in [60,120,300]:scores.append(dict(mode=mode,hypothesis=name,cycle_id=cid,underlying=META[cid]['underlying'],expiry_date=META[cid]['expiry_date'],tolerance_seconds=tol,
                    **metrics(pp,test_e,tol)))
                for right in ['CE','PE']:
                    for phase in ['preexpiry','expiry']:
                        ee=test_e[(test_e.option_type==right)&(test_e.phase==phase)];pr=pp[(pp.option_type==right)&(pp.phase==phase)]
                        strata.append(dict(mode=mode,hypothesis=name,cycle_id=cid,underlying=META[cid]['underlying'],option_type=right,phase=phase,**metrics(pr,ee)))
        print('Evaluated',mode,flush=True)
    scores=pd.DataFrame(scores);folds=pd.DataFrame(folds);save(scores,'cycle_validation_scores.csv');save(folds,'validation_folds.csv');save(pd.DataFrame(paramsrows),'baseline_fold_parameters.csv')
    save(pd.concat(basepred,ignore_index=True),'baseline_predictions.csv.gz');save(pd.concat(selectedpred,ignore_index=True),'training_selected_predictions.csv.gz');save(pd.DataFrame(strata),'index_side_phase_scores.csv')
    ranked=[];cov=pd.DataFrame(coverage)
    for (mode,name,tol),g in scores.groupby(['mode','hypothesis','tolerance_seconds']):
        totals=g[['predicted','observed','matched','false_positives','missed_exits']].sum().to_dict();m=totals['matched'];pn=totals['predicted'];an=totals['observed']
        v=cov[cov.hypothesis.eq(name)&cov.cycle_id.isin(g.cycle_id)]
        coverage_value=v.events_feature_available.sum()/v.events.sum() if len(v) and v.events.sum() else np.nan
        ranked.append(dict(mode=mode,hypothesis=name,tolerance_seconds=tol,cycles=len(g),**totals,precision=m/pn if pn else np.nan,recall=m/an if an else np.nan,
            f1=2*m/(pn+an) if pn+an else np.nan,macro_cycle_f1=g.f1.mean(),event_feature_coverage=coverage_value))
    ranked=pd.DataFrame(ranked).sort_values(['mode','tolerance_seconds','macro_cycle_f1'],ascending=[True,True,False])
    ranked=complete_coverage(ranked,cov,folds);save(ranked,'ranked_trigger_hypotheses.csv')
    uncertainty=[];rng=np.random.default_rng(80159)
    for mode in scores['mode'].unique():
        ss=scores[(scores['mode']==mode)&(scores.tolerance_seconds==120)]
        for name in NAMES+['training_selected']:
            for baseline in BASES:
                x=ss[ss.hypothesis.isin([name,baseline])].pivot(index='cycle_id',columns='hypothesis',values='f1').dropna();diff=(x[name]-x[baseline]).to_numpy()
                boot=diff[rng.integers(0,len(diff),(2000,len(diff)))].mean(axis=1)
                uncertainty.append(dict(mode=mode,hypothesis=name,baseline=baseline,cycles=len(diff),mean_f1_difference=diff.mean(),low95=np.quantile(boot,.025),high95=np.quantile(boot,.975),
                    improved_cycles=int((diff>0).sum()),interpretation='paired whole-cycle bootstrap; related calendar/index shocks may remain'))
    save(pd.DataFrame(uncertainty),'cycle_bootstrap_comparisons.csv')
    describe_controls(risk,all_events)
    # Frozen prior model-28 covers, grouped into the same observed episode unit.
    pf_all=pd.read_csv(PRIOR/'detailed_fills.csv.gz');pf_all=pf_all[pf_all.model_id==28]
    pf=pf_all[(pf_all.side=='Buy')&pf_all.quantity_before.lt(0)]
    p=[]
    for (cid,k,right),g in pf.groupby(['cycle_id','strike','right']):
        additions=pf_all[(pf_all.cycle_id==cid)&(pf_all.strike==k)&(pf_all.right==right)&pf_all.side.eq('Sell')&pf_all.quantity_after.lt(0)].second.to_numpy()
        last=None
        for r in g.sort_values('second').itertuples():
            if last is None or r.second-last>120 or np.any((additions>last)&(additions<=r.second)):
                p.append(dict(cycle_id=cid,strike=k,option_type='PE' if right else 'CE',second=r.second))
            last=r.second
    p=pd.DataFrame(p);frozen=[];finals=[]
    for cid in range(35):
        ee=events[events.cycle_id==cid];pp=p[p.cycle_id==cid]
        frozen.append(dict(cycle_id=cid,known_initialization=cid in known,**metrics(pp,ee)))
        # Independent deadline-only diagnostic; no intermediate outcome labels
        # used to construct its predictions.
        r=risk[(risk.cycle_id==cid)&risk.phase.eq('expiry')];deadline=927 if META[cid]['expiry_date']<'2026-08-03' else 914
        dp=r[r.clock_minute==deadline];fe=all_events[(all_events.cycle_id==cid)&all_events.outcome_stratum.eq('final_liquidation')]
        finals.append(dict(cycle_id=cid,known_initialization=cid in known,deadline_clock=deadline,**metrics(dp,fe)))
    save(pd.DataFrame(frozen),'unchanged_model28_exit_scores.csv');save(pd.DataFrame(finals),'separate_final_liquidation_scores.csv')
    # Observable-condition contrasts in the retained group remain descriptive;
    # all 27 cases are retained, but only seven are actually short covers.
    mf=pd.read_csv(HERE/'motif_pre_event_features.csv');up=pd.read_csv(HERE/'upstream_32_27_audit.csv');diag=up.merge(mf.drop(columns=['cycle_id','expiry_date','strike']),on='motif_id',suffixes=('','_feature'))
    for name in NAMES:
        state,valid=masks(diag,name);diag[name+'_condition']=state;diag[name+'_available']=valid
    save(diag,'motif_27_pre_event_condition_audit.csv')
    chrono=ranked[(ranked['mode']=='expanding_chronological')&(ranked.tolerance_seconds==120)&ranked.hypothesis.isin(NAMES)]
    qualifying=chrono[(chrono.precision>=.8)&(chrono.recall>=.8)&(chrono.event_feature_coverage>=.8)&(chrono.cycles>=5)]
    (HERE/'evaluation_summary.json').write_text(json.dumps(dict(fixed_hypotheses=12,baselines=BASES,known_cycles=len(known),chronological_cycles=int((folds['mode']=='expanding_chronological').sum()),
        qualifies_precision_recall_coverage80=qualifying.hypothesis.tolist(),selection='mean training-cycle F1; tie original registered ordering',
        inference='conditional on actual pre-event inventory; not autonomous replay or external alpha validation'),indent=2))
    print('Evaluation complete; qualifying',qualifying.hypothesis.tolist(),flush=True)
if __name__=='__main__':run()
