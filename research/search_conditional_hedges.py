"""Piecewise hedge-budget programs with calibrated market/book-state branches."""
import csv
import gzip
import json
from collections import defaultdict,Counter
from datetime import datetime

import numpy as np
from audit_strike_hedge_rules import OUT,logs,write
from combo_features import datasets,load_context
from refine_hedge_budget import rounded_budget,scores
from scan_hedge_leg_ratios import key


def select(chain,target,selector,spot,fresh):
    if target is None:return None
    eligible=[c for c in chain if (not fresh or c['volume']>0) and (selector!='ceiling' or c['price']<=target) and (selector!='floor' or c['price']>=target)]
    return min(eligible,key=lambda c:(abs(c['price']-target),abs(c['strike']-spot),c['strike']))['strike'] if eligible else None


def fit_piecewise(events,hits,features,train,weights,thresholds,max_depth=2,min_events=30,min_cycles=3):
    """Each leaf chooses a budget rule. Missing split inputs use parent rule."""
    candidates_checked=0
    def best_rule(ix):return int(np.argmax(hits[:,ix]@weights[ix]))
    def fit(ix,depth):
        nonlocal candidates_checked
        default=best_rule(ix);node=dict(default_rule=default,events=len(ix),cycles=len({events[i]['expiry_date'] for i in ix}))
        if depth>=max_depth:return node
        original=float(hits[default,ix]@weights[ix]);total=float(weights[ix].sum());best=None
        for field,levels in thresholds.items():
            values=features[field]
            for threshold in levels:
                left=ix[np.isfinite(values[ix])&(values[ix]<=threshold)];right=ix[np.isfinite(values[ix])&(values[ix]>threshold)]
                if min(len(left),len(right))<min_events:continue
                if min(len({events[i]['expiry_date'] for i in left}),len({events[i]['expiry_date'] for i in right}))<min_cycles:continue
                a=best_rule(left);b=best_rule(right);missing=ix[~np.isfinite(values[ix])]
                gain=(float(hits[a,left]@weights[left])+float(hits[b,right]@weights[right])+float(hits[default,missing]@weights[missing])-original)/total
                candidates_checked+=1
                if best is None or gain>best[0]:best=(gain,field,threshold,left,right)
        if best is not None and best[0]>=.01:
            gain,field,threshold,left,right=best
            node.update(field=field,threshold=threshold,calibration_gain=gain,left=fit(left,depth+1),right=fit(right,depth+1))
        return node
    tree=fit(np.asarray(train,dtype=int),0)
    return tree,candidates_checked


def predict_piecewise(tree,features,n):
    result=np.empty(n,dtype=int)
    for i in range(n):
        node=tree
        while 'field' in node:
            value=features[node['field']][i]
            if not np.isfinite(value):break
            node=node['left'] if value<=node['threshold'] else node['right']
        result[i]=node['default_rule']
    return result


def main():
    _,fast=datasets();fmap={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in fast}
    ctx={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in load_context()}
    spots={key(r):float(r['spot']) if r['spot'] else None for r in csv.DictReader((OUT/'rule_match_hedge_events.csv').open())}
    events=[];quotes=defaultdict(list)
    for r in csv.DictReader((OUT/'rule_match_leg_ratio_event_inputs.csv').open()):
        r['strike']=int(r['bought_strike']);r['reference']=float(r['atm_leg_prior_premium']) if r['atm_leg_prior_premium'] else None;r['spot']=spots[key(r)];events.append(r)
    keys={key(r) for r in events}
    with gzip.open(OUT/'rule_match_hedge_candidate_quotes.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            if key(r) in keys:quotes[key(r)].append(dict(strike=int(r['strike']),price=float(r['price']),volume=float(r['volume'])))
    bank=[dict(fraction=fraction,tick=tick,rounding=rounding,selector=selector,fresh_volume=fresh)
          for fraction in (.01,.015,.02,.0225,.025,.0275,.03,.04,.05,.075)
          for tick,rounding in [(0,'none'),(.05,'nearest'),(.1,'nearest'),(.1,'floor'),(.1,'ceil'),(.5,'nearest')]
          for selector in ('nearest','ceiling','floor') for fresh in (True,False)]
    models={};evaluation=[];predictions=[];oracle=[];comparisons=0
    thresholds=dict(right_pe=(.5,),clock=(30,60,90,120,180,240,270),atm_premium=(50,75,100,150,200,300,500),
        reference_iv_pct=(12,15,18,20,25),spot_abs_return5_pct=(.025,.05,.1,.2),
        x_short_units=(5,10,20,30,40,60),x_max_short_loss_pct=(4,10,25,50),x_hedge_coverage=(.75,1,1.25,1.5,2))
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            es=[e for e in events if e['underlying']==u and e['phase']==phase];train=np.array([i for i,e in enumerate(es) if e['expiry_date']<='2026-08-31']);test=np.array([i for i,e in enumerate(es) if e['expiry_date']>'2026-08-31'])
            counts=Counter(e['expiry_date'] for e in es);weights=np.array([1/counts[e['expiry_date']] for e in es])
            features={field:np.full(len(es),np.nan) for field in thresholds}
            for i,e in enumerate(es):
                t=datetime.fromisoformat(e['event_time_ist']);k=(u,e['expiry_date'],str(t.date()),t.strftime('%H:%M'));known={**fmap.get(k,{}),**ctx.get(k,{})}
                known.update(right_pe=int(e['option_type']=='PE'),clock=t.hour*60+t.minute-555,atm_premium=e['reference'])
                for field in features:
                    value=known.get(field);features[field][i]=value if value is not None else np.nan
            matrix=np.full((len(bank),len(es)),-1,dtype=int)
            for j,rule in enumerate(bank):
                for i,e in enumerate(es):
                    budget=rounded_budget(e['reference']*rule['fraction'],rule['tick'],rule['rounding']) if e['reference'] is not None else None
                    k=select(quotes[key(e)],budget,rule['selector'],e['spot'],rule['fresh_volume'])
                    if k is not None:matrix[j,i]=k
            actual=np.array([e['strike'] for e in es]);hits=matrix==actual
            constant=int(np.argmax(hits[:,train]@weights[train]));comparisons+=len(bank)
            tree,n=fit_piecewise(es,hits,features,train,weights,thresholds);comparisons+=n
            full,n=fit_piecewise(es,hits,features,np.arange(len(es)),weights,thresholds,max_depth=4,min_events=10,min_cycles=2)
            name=u+'|'+phase;models[name]=dict(bank=bank,constant_rule=constant,conditional=tree,all_observed_curve_fit=full)
            for kind,rules,ix in [('calibration_constant',np.full(len(es),constant),test),('calibration_conditional',predict_piecewise(tree,features,len(es)),test),
                                  ('all_observed_curve_fit',predict_piecewise(full,features,len(es)),np.arange(len(es)))]:
                pr=[int(matrix[rules[i],i]) if matrix[rules[i],i]>=0 else None for i in ix]
                trpr=[int(matrix[rules[i],i]) if matrix[rules[i],i]>=0 else None for i in train]
                evaluation.append(dict(underlying=u,phase=phase,kind=kind,calibration_exact_rate=scores([es[i] for i in train],trpr)['exact_rate'],**scores([es[i] for i in ix],pr)))
                for i,k in zip(ix,pr):predictions.append(dict(underlying=u,expiry_date=es[i]['expiry_date'],phase=phase,kind=kind,event_time_ist=es[i]['event_time_ist'],
                    option_type=es[i]['option_type'],observed_strike=int(actual[i]),predicted_strike=k if k is not None else '',budget_rule=int(rules[i]),exact=k==actual[i]))
            oracle.append(dict(underlying=u,phase=phase,later_events=len(test),representable_by_any_bank_rule=int(np.any(hits[:,test],axis=0).sum()),
                note='Per-event best possible using actual selected strike as an oracle; not a predictive model or full-chain coverage bound.'))
            print('Conditional hedges',name,evaluation[-2]['exact'],'/',evaluation[-2]['events'],flush=True)
    write('combo_hedge_evaluation.csv',evaluation);write('combo_hedge_predictions.csv.gz',predictions);write('combo_hedge_representability.csv',oracle)
    (OUT/'combo_hedge_programs.json').write_text(json.dumps(models,indent=2)+'\n')
    (OUT/'combo_hedge_summary.json').write_text(json.dumps(dict(calibration_comparisons=comparisons,constant_budget_bank=len(bank),evaluation=evaluation,representability=oracle,
        note='Routine cohorts only. Branches and leaf budgets use earlier data; separate all-observed fits are resubstitution. Incomplete retrospective chain; no actual future wing premium or selected strike is a predictor.'),indent=2)+'\n')


if __name__=='__main__':main()
