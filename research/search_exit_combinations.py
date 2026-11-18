"""Mass OR exit programs, including gated stops and profit-activated trailing.

Conditions run on actual prior-known book state, not counterfactual inventory.
"""
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime

import numpy as np
from audit_strike_hedge_rules import OUT,write
from mass_match_strategy_rules import numeric
from combo_features import load_context


def minute(t):return t.hour*60+t.minute+t.second/60


def build_inputs():
    paths=defaultdict(list)
    with gzip.open(OUT/'rule_refine_role_ledger.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            p={k:(v=='True' if k=='opening_proxy' else numeric(v)) for k,v in r.items() if k not in ('underlying','expiry_date','available_at_ist')}
            p['t']=datetime.fromisoformat(r['available_at_ist']);paths[(r['underlying'],r['expiry_date'])].append(p)
    contexts={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in load_context()}
    cycles=[]
    for r in csv.DictReader((OUT/'rule_refine_exit_target_comparison.csv').open()):
        u,e=r['underlying'],r['expiry_date'];points=paths[(u,e)]
        for p in points:
            x=contexts.get((u,e,e,p['t'].strftime('%H:%M')),{});p.update({k:v for k,v in x.items() if k.startswith('x_') and not k.endswith('_ist')})
        cycles.append(dict(underlying=u,expiry_date=e,path=points,targets={k:minute(datetime.fromisoformat(r[k])) if r[k] else None for k in ('material_95pct','first_short_flat','final_short_flat')}))
    return cycles


def atom_catalog(cycles):
    fields=[k for k in cycles[0]['path'][0] if k.endswith('_pct_capital') and not k.startswith('x_')]
    atoms=[dict(kind='false',text='NO_PRICE_TRIGGER')]
    for field in fields:
        for threshold in (.1,.15,.2,.25,.3,.4,.5,.6,.75,1,1.25,1.5):
            for sign,op in ((-1,'le'),(1,'ge')):
                atoms.append(dict(kind='threshold',field=field,threshold=sign*threshold,operator=op,text=f'{field} {op} {sign*threshold:g}'))
    for threshold in (1,2,3,4,5,7.5,10,15,20,25,30,40,50):
        atoms.append(dict(kind='threshold',field='short_unrealized_pct_credit',threshold=-threshold,operator='le',text=f'OPEN_SHORT_CREDIT_LOSS >= {threshold:g}%'))
    for scope in ('net_equity','short_book_equity'):
        for activation in (.1,.2,.3,.5,.75,1):
            for trail in (.1,.2,.3,.4,.5,.75):
                atoms.append(dict(kind='activated_trail',scope=scope,activation=activation,trail=trail,
                    text=f'{scope} PEAK >= {activation:g}% AND DRAWDOWN <= -{trail:g}%'))
    for field in ('net_equity_pct_capital','short_book_equity_pct_capital','net_equity_change_previous_close_pct_capital','short_book_equity_change_previous_close_pct_capital'):
        for loss in (.25,.5,.75,1):
            for gate,threshold in [('x_max_short_loss_pct',4),('x_max_short_loss_pct',25),('x_max_trailing_rise_pct',10),('x_short_over4_fraction',.5)]:
                atoms.append(dict(kind='gated_loss',field=field,threshold=-loss,gate=gate,gate_threshold=threshold,
                    text=f'{field} <= -{loss:g}% AND {gate} >= {threshold:g}'))
    return atoms


def condition(atom,p):
    if atom['kind']=='false':return False
    if atom['kind']=='activated_trail':
        scope=atom['scope'];eq=p.get(scope+'_pct_capital');dd=p.get(scope+'_drawdown_pct_capital')
        return eq is not None and dd is not None and eq-dd>=atom['activation'] and dd<=-atom['trail']
    value=p.get(atom['field'])
    if value is None:return False
    if atom['kind']=='gated_loss':
        gate=p.get(atom['gate'])
        return value<=atom['threshold'] and gate is not None and gate>=atom['gate_threshold']
    return value<=atom['threshold'] if atom['operator']=='le' else value>=atom['threshold']


def first_crossings(cycles,atoms,completed_only=False):
    result=np.full((len(atoms),len(cycles)),np.inf)
    for j,c in enumerate(cycles):
        eligible=[p for p in c['path'] if p['short_quantity']>0 and (not completed_only or not p['opening_proxy'])]
        for i,atom in enumerate(atoms):
            for p in eligible:
                if condition(atom,p):result[i,j]=minute(p['t']);break
    return result


def stats(y,p):
    err=abs(p-y)
    return dict(cycles=len(y),matches_2m=int(np.sum(err<=2)),matches_5m=int(np.sum(err<=5)),mean_abs_error_minutes=float(err.mean()),
                early_observed=int(np.sum(y<885)),early_matches_2m=int(np.sum((y<885)&(err<=2))),false_early_signals=int(np.sum((y>=885)&(p<885))))


def search():
    cycles=build_inputs();atoms=atom_catalog(cycles);left,right=np.triu_indices(len(atoms));complexity=(left!=0).astype(int)+(right!=0).astype(int)
    complexity=np.where(left==right,(left!=0).astype(int),complexity)
    top_rows=[];evaluation=[];predictions=[];histograms=[];models={};comparisons=0
    for completed in (False,True):
        first=first_crossings(cycles,atoms,completed)
        pairs=np.minimum(first[left],first[right])
        for target in ('material_95pct','first_short_flat','final_short_flat'):
            usable=np.array([i for i,c in enumerate(cycles) if c['targets'][target] is not None]);train=np.array([i for i in usable if cycles[i]['expiry_date']<='2026-08-31']);test=np.array([i for i in usable if cycles[i]['expiry_date']>'2026-08-31'])
            truth=np.array([c['targets'][target] if c['targets'][target] is not None else np.nan for c in cycles])
            best=None;full_best=None;candidates=[]
            for early_cutoff in (915,920,925,929):
                for later_cutoff in (900,910,914,915,920):
                    fallback=np.array([early_cutoff if c['expiry_date']<'2026-08-03' else later_cutoff for c in cycles])
                    pred=np.minimum(pairs,fallback)
                    error=abs(pred[:,train]-truth[train]);hits=np.sum(error<=2,axis=1);means=error.mean(axis=1)
                    order=np.lexsort((np.arange(len(left)),complexity,means,-hits));comparisons+=len(left)
                    for k in order[:64]:
                        row=dict(target_kind=target,completed_only=completed,atom1=int(left[k]),atom2=int(right[k]),
                            before_aug3_cutoff=int(early_cutoff),after_aug3_cutoff=int(later_cutoff),atoms=int(complexity[k]),
                            calibration_cycles=len(train),calibration_matches_2m=int(hits[k]),calibration_mean_abs_error=float(means[k]))
                        candidates.append(row);top_rows.append(row)
                    key=(-int(hits[order[0]]),float(means[order[0]]),int(complexity[order[0]]),int(order[0]),early_cutoff,later_cutoff)
                    if best is None or key<best[0]:best=(key,int(order[0]),early_cutoff,later_cutoff)
                    full_error=abs(pred[:,usable]-truth[usable]);full_hits=np.sum(full_error<=2,axis=1);full_means=full_error.mean(axis=1)
                    idx=int(np.lexsort((np.arange(len(left)),complexity,full_means,-full_hits))[0])
                    fullkey=(-int(full_hits[idx]),float(full_means[idx]),int(complexity[idx]),idx,early_cutoff,later_cutoff)
                    if full_best is None or fullkey<full_best[0]:full_best=(fullkey,idx,early_cutoff,later_cutoff)
                    histograms.append(dict(target_kind=target,completed_only=completed,before_aug3_cutoff=early_cutoff,after_aug3_cutoff=later_cutoff,
                        programs=len(left),calibration_match_histogram=json.dumps(np.bincount(hits,minlength=len(train)+1).tolist())))
            name=target+'|'+('completed' if completed else 'opening_and_completed')
            models[name]=dict(atoms=atoms,selected={},top_calibration=sorted(candidates,key=lambda r:(-r['calibration_matches_2m'],r['calibration_mean_abs_error'],r['atoms']))[:32])
            for kind,chosen in [('calibration_selected',best),('all_observed_curve_fit',full_best)]:
                _,k,oldcut,newcut=chosen;fallback=np.array([oldcut if c['expiry_date']<'2026-08-03' else newcut for c in cycles]);pr=np.minimum(pairs[k],fallback)
                expression=f"({atoms[left[k]]['text']}) OR ({atoms[right[k]]['text']}) OR TIME[{oldcut}/{newcut}]"
                selected=dict(atom1=int(left[k]),atom2=int(right[k]),before_aug3_cutoff=oldcut,after_aug3_cutoff=newcut,text=expression)
                if kind=='calibration_selected':models[name]['selected']=selected
                evaluation.append(dict(target_kind=target,completed_only=completed,kind=kind,expression=expression,
                    calibration_matches_2m=stats(truth[train],pr[train])['matches_2m'],**stats(truth[test] if kind=='calibration_selected' else truth[usable],pr[test] if kind=='calibration_selected' else pr[usable])))
                for i in (test if kind=='calibration_selected' else usable):
                    predictions.append(dict(underlying=cycles[i]['underlying'],expiry_date=cycles[i]['expiry_date'],target_kind=target,completed_only=completed,kind=kind,
                        observed_minute=truth[i],predicted_minute=pr[i],error_minutes=float(pr[i]-truth[i])))
            print('Composite exits',name,'later',evaluation[-2]['matches_2m'],'/',len(test),'full fit',evaluation[-1]['matches_2m'],'/',len(usable),flush=True)
    write('combo_exit_calibration_top.csv',top_rows);write('combo_exit_search_histograms.csv',histograms)
    write('combo_exit_evaluation.csv',evaluation);write('combo_exit_predictions.csv',predictions)
    (OUT/'combo_exit_programs.json').write_text(json.dumps(models,indent=2)+'\n')
    summary=dict(atom_count=len(atoms),or_pairs_per_cutoff=len(left),calibration_comparisons=comparisons,evaluation=evaluation,
        note='Includes single rules and OR pairs plus pre/post-session-regime time cutoffs. All-observed fits explicitly use every label. First crossings condition on the actual evolving book, without autonomous cancellation or risk-reference resets.')
    (OUT/'combo_exit_summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':search()
