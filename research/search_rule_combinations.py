"""AND/OR, temporal and tree combinations for conditional execution matching."""
import csv
import argparse
import json
from collections import Counter,defaultdict
from datetime import datetime

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier,export_text

from combo_features import datasets,load_context,context_grid
from audit_strike_hedge_rules import OUT,logs,write
from mass_match_strategy_rules import score,cycle_weights,predicate,clock_predictions,tolerant_event_score
from strategy_rule_features import predicate_grid
from combo_option_flow import flow_grid


def previous_indices(rows):
    result=np.full(len(rows),-1,dtype=int)
    for i in range(1,len(rows)):
        a,b=rows[i-1],rows[i]
        if a['cycle']==b['cycle'] and a['date']==b['date'] and minutes(b)-minutes(a)==1:result[i]=i-1
    return result


def minutes(r):
    return int(r['clock'][:2])*60+int(r['clock'][3:5])


def decorate(rows):
    for r in rows:
        r['clock_mod15']=minutes(r)%15;r['clock_minute']=minutes(r)-555
        r['is_sensex']=int(r['underlying']=='SENSEX');r['is_expiry']=int(r['phase']=='expiry')
    return rows


def late_dataset():
    targets=defaultdict(int)
    for r in logs.read_fills():
        if r['side']=='Buy' and r['opening']>0 and r['opening']==r['reverse_opening']:
            targets[(r['u'],str(r['expiry']),str(r['t'].date()),r['t'].strftime('%H:%M'))]+=r['opening']
    rows=[]
    for r in load_context():
        if not('14:44'<=r['clock']<('15:40' if r['date']>='2026-08-03' else '15:30')):continue
        q=targets[(r['underlying'],r['expiry_date'],r['date'],r['clock'])]
        rows.append(dict(r,cycle=r['underlying']+'|'+r['expiry_date'],phase='preexpiry' if r['date']<r['expiry_date'] else 'expiry',
            split='calibration' if r['expiry_date']<='2026-08-31' else 'evaluation',large_long=int(q>=10*logs.UNIT[r['underlying']])))
    return rows


def temporal_filter(rows,raw,cooldown=0,maximum=0,require_book=False,position_cap=0):
    """Own predicted-signal state resets each session; book state is observed past."""
    result=np.zeros(len(rows),dtype=bool);state={}
    for i in np.flatnonzero(raw):
        r=rows[i];key=(r['cycle'],r['date']);clock=minutes(r)
        last,count=state.get(key,(-10**9,0))
        if cooldown and clock-last<cooldown:continue
        if maximum and count>=maximum:continue
        short=r.get('x_short_units',r.get('short_ce_units',0)+r.get('short_pe_units',0))
        if require_book and not(short is not None and short>0):continue
        if position_cap and (short is None or short>=position_cap):continue
        result[i]=True;state[key]=(clock,count+1)
    return result


def metric_key(metric,complexity=1):
    return (metric['cycle_weighted_f1'],metric['f1'],-metric['false_positives'],-complexity)


def beam_search(rows,y,train,clock,atomic_masks,catalog,trial_rows,task,phase,pool_size=64,width=16):
    weights=cycle_weights(rows,train);rank=[]
    def evaluate(mask,expression,atoms,kind):
        stat=score(y[train],mask[train],weights)
        trial_rows.append(dict(task=task,phase=phase,kind=kind,expression=expression,atoms=atoms,
            cooldown=0,maximum=0,require_book=False,position_cap=0,**stat))
        return stat
    baseline=dict(mask=clock,expr=('clock',),atoms=frozenset(),text='CLOCK_ATTENDANCE_AND_BOOK',depth=1)
    baseline['score']=evaluate(clock,baseline['text'],1,'baseline');rank.append(baseline)
    for j,mask in enumerate(atomic_masks):
        text=catalog[j]['text'];stat=evaluate(mask,text,1,'atom')
        rank.append(dict(mask=mask,expr=('atom',j),atoms=frozenset([j]),text=text,depth=1,score=stat))
    ranked=sorted(rank,key=lambda n:metric_key(n['score'],n['depth']),reverse=True)
    seeds=[];seen=set();perfield=Counter()
    for n in ranked:
        fingerprint=np.packbits(n['mask'][train]).tobytes()
        if fingerprint in seen:continue
        field=catalog[next(iter(n['atoms']))]['field'] if n['atoms'] else 'clock'
        if perfield[field]>=4:continue
        support={rows[i]['cycle'] for i in train if n['mask'][i]}
        if n['depth'] and len(support)<3:continue
        seeds.append(n);seen.add(fingerprint);perfield[field]+=1
        if len(seeds)>=pool_size:break
    if not any(n['expr'][0]=='clock' for n in seeds):seeds.append(baseline)
    allnodes=list(seeds);beam=seeds[:width];seen={np.packbits(n['mask'][train]).tobytes() for n in allnodes}
    for depth in (2,3):
        expanded=[]
        for left in beam:
            for right in seeds:
                if left['atoms']&right['atoms']:continue
                if left['depth']+right['depth']!=depth:continue
                for operator in ('and','or'):
                    mask=left['mask']&right['mask'] if operator=='and' else left['mask']|right['mask']
                    fingerprint=np.packbits(mask[train]).tobytes()
                    if fingerprint in seen:continue
                    seen.add(fingerprint)
                    text=f"({left['text']} {operator.upper()} {right['text']})"
                    stat=evaluate(mask,text,depth,'boolean_combination')
                    expanded.append(dict(mask=mask,expr=(operator,left['expr'],right['expr']),atoms=left['atoms']|right['atoms'],text=text,depth=depth,score=stat))
        beam=sorted(expanded,key=lambda n:metric_key(n['score'],n['depth']),reverse=True)[:width]
        allnodes.extend(beam)
    ranked=sorted(allnodes,key=lambda n:metric_key(n['score'],n['depth']),reverse=True)
    candidates=[];seen=set()
    for n in [baseline]+ranked:
        fingerprint=np.packbits(n['mask'][train]).tobytes()
        if fingerprint not in seen:candidates.append(n);seen.add(fingerprint)
        if len(candidates)>=8:break
    best=None
    for n in candidates:
        for cooldown in (0,1,2,3,5,10,15):
            for maximum in (0,1,3,5,10,20,40):
                for require_book in (False,True):
                    for cap in (0,10,20,40,80):
                        pr=temporal_filter(rows,n['mask'],cooldown,maximum,require_book,cap)
                        stat=score(y[train],pr[train],weights)
                        trial_rows.append(dict(task=task,phase=phase,kind='temporal_combination',expression=n['text'],atoms=n['depth'],
                            cooldown=cooldown,maximum=maximum,require_book=require_book,position_cap=cap,**stat))
                        complexity=n['depth']+bool(cooldown)+bool(maximum)+require_book+bool(cap)
                        if best is None or metric_key(stat,complexity)>metric_key(best['score'],best['complexity']):
                            best=dict(node=n,mask=pr,score=stat,complexity=complexity,cooldown=cooldown,maximum=maximum,require_book=require_book,position_cap=cap)
    return baseline,best,candidates


def tree_structure(tree,names):
    return dict(feature_names=names,feature=tree.tree_.feature.tolist(),threshold=tree.tree_.threshold.tolist(),
        children_left=tree.tree_.children_left.tolist(),children_right=tree.tree_.children_right.tolist(),
        classes=tree.classes_.tolist(),values=tree.tree_.value.tolist())


def fit_trees(rows,y,train,test,features,trial_rows,task,phase):
    x=np.array([[np.nan if r.get(k) is None else r[k] for k in features] for r in rows],dtype=float)
    groups=np.array([rows[i]['cycle'] for i in train]);splitter=GroupKFold(n_splits=3);rank=[]
    for depth in (3,5,8):
        for leaf in (5,20):
            for balance in (None,'balanced'):
                pred=np.zeros(len(train),dtype=bool)
                for a,b in splitter.split(train,groups=groups):
                    imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)
                    ax=imputer.fit_transform(x[train[a]]);bx=imputer.transform(x[train[b]])
                    tree=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=leaf,class_weight=balance,random_state=20261026)
                    tree.fit(ax,y[train[a]]);pred[b]=tree.predict(bx)
                stat=score(y[train],pred,cycle_weights(rows,train))
                rank.append((stat,depth,leaf,balance))
                trial_rows.append(dict(task=task,phase=phase,kind='tree_cycle_cv',expression=f'depth={depth}; leaf={leaf}; balance={balance}',
                    atoms=depth,cooldown=0,maximum=0,require_book=False,position_cap=0,**stat))
    chosen=max(rank,key=lambda v:metric_key(v[0],v[1]))
    imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True);ax=imputer.fit_transform(x[train]);bx=imputer.transform(x[test])
    tree=DecisionTreeClassifier(max_depth=chosen[1],min_samples_leaf=chosen[2],class_weight=chosen[3],random_state=20261026)
    tree.fit(ax,y[train]);names=imputer.get_feature_names_out(features).tolist();pr=tree.predict(bx).astype(bool)
    result=dict(cv=chosen[0],fit=score(y[train],tree.predict(ax),cycle_weights(rows,train)),test=score(y[test],pr,cycle_weights(rows,test)),
        parameters=dict(depth=chosen[1],minimum_leaf=chosen[2],class_weight=chosen[3]),
        rules=export_text(tree,feature_names=names,decimals=4),structure=tree_structure(tree,names))
    # Deliberately unrestricted, all-observation curve fit. No held-out claim.
    full_imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True);full=full_imputer.fit_transform(x)
    memorizer=DecisionTreeClassifier(min_samples_leaf=1,random_state=20261026);memorizer.fit(full,y)
    result['all_observed_curve_fit']=dict(**score(y,memorizer.predict(full)),leaves=int(memorizer.get_n_leaves()),
        node_count=int(memorizer.tree_.node_count),note='Resubstitution after fitting every observed label; not an independent test or the original code.')
    return result,pr


def run(flow_only=False):
    slow,fast=datasets(include_flow=flow_only);all_trials=[];evaluations=[];predictions=[];programs={};rules=[]
    suites=[(fast,[('fresh_pairs','paired_sale'),('extra_pairs','paired_sale'),('covers','short_cover')])] if flow_only else [
        (fast,[('fresh_pairs','paired_sale'),('extra_pairs','paired_sale'),('covers','short_cover'),('protection','new_long')]),
        (slow,[('quarter_pairs','quarter_target')]),(late_dataset(),[('large_late_protection','large_long')])]
    for dataset,types in suites:
        decorate(dataset);previous=previous_indices(dataset)
        columns=[k for k in dataset[0] if predicate_grid([k]) or context_grid([k]) or flow_grid([k])]
        grid=predicate_grid(columns)+context_grid(columns)+flow_grid(columns)
        grid.extend((k,op,v,'state') for k,levels in [('clock_mod15',(0,1,2,3,5,10,12,13)),('clock_minute',(15,30,60,120,180,240,300))] for v in levels for op in ('le','gt'))
        arrays={k:np.array([np.nan if r.get(k) is None else r[k] for r in dataset],dtype=float) for k in {g[0] for g in grid}}
        all_masks=[predicate(arrays[k],op,v,mode,previous) for k,op,v,mode in grid]
        catalog=[dict(field=k,operator=op,threshold=v,mode=mode,text=f'{k} {op} {v:g} [{mode}]') for k,op,v,mode in grid]
        features=sorted(set(columns+['clock_mod15','clock_minute','is_sensex','is_expiry']))
        for task,target in types:
            for phase in ('preexpiry','expiry'):
                ix=np.array([i for i,r in enumerate(dataset) if r['phase']==phase and
                    (r[target] is not None if task=='quarter_pairs' else bool(r['off_quarter']) if task=='extra_pairs' else r['clock']>='14:45' if task=='large_late_protection' else True)],dtype=int)
                rows=[dataset[i] for i in ix];y=np.array([bool(r[target]) for r in rows]);train=np.array([i for i,r in enumerate(rows) if r['split']=='calibration']);test=np.array([i for i,r in enumerate(rows) if r['split']=='evaluation'])
                global_clock=clock_predictions(dataset,ix,target);clock=global_clock[ix]
                if task not in ('protection','large_late_protection'):clock&=np.array([r.get('x_short_units',0)>0 for r in rows])
                masks=[mask[ix] for mask in all_masks]
                baseline,best,candidates=beam_search(rows,y,train,clock,masks,catalog,all_trials,task,phase)
                name=phase+'|'+task
                programs[name]=dict(catalog=catalog,selected=dict(expression=best['node']['expr'],text=best['node']['text'],
                    **{k:best[k] for k in ('cooldown','maximum','require_book','position_cap')}),
                    candidates=[dict(expression=n['expr'],text=n['text'],training=n['score']) for n in candidates])
                for kind,pr,calibration in [('clock',baseline['mask'],baseline['score']),('boolean_temporal',best['mask'],best['score'])]:
                    evaluations.append(dict(task=task,phase=phase,kind=kind,calibration_f1=calibration['f1'],calibration_cycle_weighted_f1=calibration['cycle_weighted_f1'],
                        **score(y[test],pr[test],cycle_weights(rows,test))))
                    for i in test:predictions.append(dict(task=task,phase=phase,kind=kind,underlying=rows[i]['underlying'],expiry_date=rows[i]['expiry_date'],date=rows[i]['date'],clock=rows[i]['clock'],target=int(y[i]),predicted=int(pr[i])))
                fitted,tree_pr=fit_trees(rows,y,train,test,features,all_trials,task,phase)
                programs[name]['tree']=fitted
                evaluations.append(dict(task=task,phase=phase,kind='tree_combinations',calibration_f1=fitted['cv']['f1'],calibration_cycle_weighted_f1=fitted['cv']['cycle_weighted_f1'],**fitted['test']))
                for i,p in zip(test,tree_pr):predictions.append(dict(task=task,phase=phase,kind='tree_combinations',underlying=rows[i]['underlying'],expiry_date=rows[i]['expiry_date'],date=rows[i]['date'],clock=rows[i]['clock'],target=int(y[i]),predicted=int(p)))
                rules.append(name+'\nBOOLEAN: '+json.dumps(programs[name]['selected'])+'\nTREE:\n'+fitted['rules'])
                print('Combined search',name,'train',round(best['score']['f1'],3),'later',round(score(y[test],best['mask'][test])['f1'],3),flush=True)
        del all_masks
    prefix='combo_flow_action' if flow_only else 'combo_action'
    write(prefix+'_search_scores.csv.gz',all_trials);write(prefix+'_evaluation.csv',evaluations)
    write(prefix+'_predictions.csv.gz',predictions)
    (OUT/(prefix+'_programs.json')).write_text(json.dumps(programs,indent=2)+'\n')
    (OUT/(prefix+'_rules.txt')).write_text('\n\n'.join(rules).rstrip()+'\n')
    summary=dict(calibration_comparisons=len(all_trials),evaluation=evaluations,
        historical_curve_fits={k:v['tree']['all_observed_curve_fit'] for k,v in programs.items()},
        note='Boolean/temporal selection fits earlier labels. Tree parameters use whole-cycle calibration CV. Full-observed curve fits are separate resubstitution diagnostics. Portfolio/order-history inputs condition on the actual past book, not an autonomous counterfactual replay.')
    (OUT/(prefix+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--flow-only',action='store_true');args=parser.parse_args();run(args.flow_only)
