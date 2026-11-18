"""Joint signal/cooldown/exit-lock combinations, plus stronger active-book controls."""
import csv
import json
from collections import Counter,defaultdict

import numpy as np
from combo_features import datasets
from audit_strike_hedge_rules import OUT,write
from mass_match_strategy_rules import score,cycle_weights,predicate,clock_predictions
from search_rule_combinations import previous_indices,decorate,temporal_filter
from search_exit_combinations import build_inputs,condition,minute


def active_clock(rows,indices,target):
    counts=defaultdict(lambda:[0,0]);own=defaultdict(lambda:[0,0]);result=np.zeros(len(rows),dtype=bool)
    for i in indices:
        r=rows[i]
        if r['split']!='calibration' or r['x_short_units']<=0:continue
        key=(r['underlying'],r['phase'],r['clock']);y=int(r[target]);counts[key][0]+=y;counts[key][1]+=1
        own[(key,r['cycle'])][0]+=y;own[(key,r['cycle'])][1]+=1
    for i in indices:
        r=rows[i];key=(r['underlying'],r['phase'],r['clock']);a,n=counts[key]
        if r['split']=='calibration':
            b,m=own[(key,r['cycle'])];a-=b;n-=m
        result[i]=r['x_short_units']>0 and (a+1)/(n+2)>=.5
    return result


def evaluate_expression(expr,catalog,dataset,previous,clock,cache):
    op=expr[0]
    if op=='clock':return clock
    if op=='atom':
        j=expr[1]
        if j not in cache:
            a=catalog[j];values=np.array([np.nan if r.get(a['field']) is None else r[a['field']] for r in dataset],dtype=float)
            cache[j]=predicate(values,a['operator'],a['threshold'],a['mode'],previous)
        return cache[j]
    left=evaluate_expression(expr[1],catalog,dataset,previous,clock,cache);right=evaluate_expression(expr[2],catalog,dataset,previous,clock,cache)
    return left&right if op=='and' else left|right


def apply_exit_lock(rows,mask,stop_times,policy):
    if policy=='none':return mask.copy()
    result=mask.copy()
    for i in np.flatnonzero(mask):
        r=rows[i];stop=stop_times.get((r['underlying'],r['expiry_date']))
        if stop is None:continue
        t=int(r['clock'][:2])*60+int(r['clock'][3:])
        if t>=stop and (policy=='day_lock' or t<stop+int(policy)):result[i]=False
    return result


def stronger_quarter_baselines(slow):
    evaluations=[];predictions=[];calibration=[]
    for phase in ('preexpiry','expiry'):
        ix=np.array([i for i,r in enumerate(slow) if r['phase']==phase and r['quarter_target'] is not None]);rows=[slow[i] for i in ix]
        train=np.array([i for i,r in enumerate(rows) if r['split']=='calibration']);test=np.array([i for i,r in enumerate(rows) if r['split']=='evaluation'])
        y=np.array([bool(r['quarter_target']) for r in rows]);book=np.array([r['x_short_units']>0 for r in rows]);clock=clock_predictions(slow,ix,'quarter_target')[ix]&book;conditional=active_clock(slow,ix,'quarter_target')[ix]
        times=np.array([int(r['clock'][:2])*60+int(r['clock'][3:]) for r in rows]);sensex=np.array([r['underlying']=='SENSEX' for r in rows]);weights=cycle_weights(rows,train)
        best=None
        for nifty_cut in range(720,871,15):
            for sensex_cut in range(720,871,15):
                for limit in (None,-.1,-.25,-.4,-.5,-.75,-1,-1.5):
                    pr=book&(times<=np.where(sensex,sensex_cut,nifty_cut))
                    if limit is not None:pr&=np.array([r.get('x_net_equity_pct_capital') is not None and r['x_net_equity_pct_capital']>limit for r in rows])
                    stat=score(y[train],pr[train],weights);key=(stat['cycle_weighted_f1'],stat['f1'],-stat['false_positives'],limit is None)
                    calibration.append(dict(phase=phase,nifty_cutoff=nifty_cut,sensex_cutoff=sensex_cut,loss_limit=limit,**stat))
                    if best is None or key>best[0]:best=(key,pr,nifty_cut,sensex_cut,limit,stat)
        for kind,pr in [('clock_unconditional_attendance',clock),('active_book_only',book),('clock_given_active_book',conditional),('fitted_active_book_program',best[1])]:
            evaluations.append(dict(phase=phase,kind=kind,**score(y[test],pr[test],cycle_weights(rows,test))))
            for i in test:predictions.append(dict(underlying=rows[i]['underlying'],expiry_date=rows[i]['expiry_date'],date=rows[i]['date'],phase=phase,clock=rows[i]['clock'],kind=kind,target=int(y[i]),predicted=int(pr[i])))
        print('Active-book baseline',phase,evaluations[-3]['f1'],'fitted',evaluations[-1]['f1'],flush=True)
    write('combo_active_book_calibration.csv',calibration);write('combo_active_book_evaluation.csv',evaluations);write('combo_active_book_predictions.csv',predictions)
    return dict(calibration_comparisons=len(calibration),evaluation=evaluations)


def main():
    slow,fast=datasets();decorate(slow);decorate(fast);programs=json.loads((OUT/'combo_action_programs.json').read_text())
    exits=json.loads((OUT/'combo_exit_programs.json').read_text())['first_short_flat|opening_and_completed'];cycles=build_inputs()
    risk_candidates=[];seen=set();bank=exits['atoms']
    def find_atom(field,threshold):
        return next(i for i,a in enumerate(bank) if a.get('kind')=='threshold' and a.get('field')==field and a.get('threshold')==threshold and a.get('operator')=='le')
    explicit=[dict(atom1=0,atom2=0,before_aug3_cutoff=929,after_aug3_cutoff=914)]
    for field,threshold in [('net_equity_pct_capital',-.5),('net_equity_pct_capital',-1),('short_book_equity_pct_capital',-1),
                            ('short_unrealized_pct_credit',-4),('net_equity_change_previous_close_pct_capital',-1)]:
        explicit.append(dict(atom1=0,atom2=find_atom(field,threshold),before_aug3_cutoff=929,after_aug3_cutoff=914))
    for r in explicit+exits['top_calibration']:
        atoms=[exits['atoms'][r['atom1']],exits['atoms'][r['atom2']]];times={}
        for c in cycles:
            fallback=r['before_aug3_cutoff'] if c['expiry_date']<'2026-08-03' else r['after_aug3_cutoff'];hit=fallback
            for p in c['path']:
                if minute(p['t'])>=fallback:break
                if p['short_quantity']>0 and any(condition(a,p) for a in atoms):hit=minute(p['t']);break
            times[(c['underlying'],c['expiry_date'])]=hit
        fingerprint=tuple((k,v) for k,v in sorted(times.items()) if k[1]<='2026-08-31')
        if fingerprint in seen:continue
        seen.add(fingerprint);risk_candidates.append(dict(rule=r,times=times))
        if len(risk_candidates)>=8:break
    trials=[];evaluation=[];predictions=[];selected={}
    for task,dataset,target in [('fresh_pairs',fast,'paired_sale'),('extra_pairs',fast,'paired_sale'),('quarter_pairs',slow,'quarter_target')]:
        ix=np.array([i for i,r in enumerate(dataset) if r['phase']=='expiry' and (r[target] is not None if task=='quarter_pairs' else bool(r['off_quarter']) if task=='extra_pairs' else True)])
        rows=[dataset[i] for i in ix];y=np.array([bool(r[target]) for r in rows]);train=np.array([i for i,r in enumerate(rows) if r['split']=='calibration']);test=np.array([i for i,r in enumerate(rows) if r['split']=='evaluation']);weights=cycle_weights(rows,train)
        previous=previous_indices(dataset);clock=clock_predictions(dataset,ix,target);clock[ix]&=np.array([r['x_short_units']>0 for r in rows])
        program=programs['expiry|'+task];cache={};best=None
        entries=program['candidates'][:8]
        for j,entry in enumerate(entries):
            raw=evaluate_expression(entry['expression'],program['catalog'],dataset,previous,clock,cache)[ix]
            for k,risk in enumerate(risk_candidates):
                for policy in ('none','day_lock','1','5','15','30'):
                    eligible=apply_exit_lock(rows,raw,risk['times'],policy)
                    for cooldown in (0,1,3,5,10,15):
                        for maximum in (0,3,5,10,20,40):
                            for require_book in (False,True):
                                pr=temporal_filter(rows,eligible,cooldown,maximum,require_book)
                                stat=score(y[train],pr[train],weights)
                                trials.append(dict(task=task,entry_candidate=j,exit_candidate=k,lock_policy=policy,cooldown=cooldown,maximum=maximum,require_book=require_book,**stat))
                                key=(stat['cycle_weighted_f1'],stat['f1'],-stat['false_positives'],policy=='none',cooldown==0,maximum==0)
                                if best is None or key>best[0]:best=(key,pr,j,k,policy,cooldown,maximum,require_book,stat)
        _,pr,j,k,policy,cooldown,maximum,require_book,stat=best
        selected[task]=dict(entry=entries[j],exit=risk_candidates[k]['rule'],lock_policy=policy,cooldown=cooldown,maximum=maximum,require_book=require_book)
        evaluation.append(dict(task=task,calibration_f1=stat['f1'],calibration_cycle_weighted_f1=stat['cycle_weighted_f1'],lock_policy=policy,**score(y[test],pr[test],cycle_weights(rows,test))))
        for i in test:predictions.append(dict(task=task,underlying=rows[i]['underlying'],expiry_date=rows[i]['expiry_date'],date=rows[i]['date'],clock=rows[i]['clock'],target=int(y[i]),predicted=int(pr[i])))
        print('Joint entry/exit',task,'later',evaluation[-1]['f1'],'lock',policy,flush=True)
    baselines=stronger_quarter_baselines(slow)
    write('combo_joint_calibration_scores.csv.gz',trials);write('combo_joint_evaluation.csv',evaluation);write('combo_joint_predictions.csv',predictions)
    (OUT/'combo_joint_programs.json').write_text(json.dumps(selected,indent=2)+'\n')
    (OUT/'combo_joint_summary.json').write_text(json.dumps(dict(calibration_comparisons=len(trials),risk_programs=len(risk_candidates),evaluation=evaluation,
        stronger_baselines=baselines,note='Joint rules condition on actual prior P&L/inventory. Exit policies and signal cooldowns are searched combinations, not an autonomous portfolio replay. Active-book baselines prevent confusing already-stopped sessions with a new risk trigger.'),indent=2)+'\n')


if __name__=='__main__':main()
