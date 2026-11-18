"""Mass-match predeclared programmed-rule hypotheses to observed executions.

Run after discover_addition_patterns.py and the option replay. No live orders.
Parameter selection uses calibration cycles only; later cycles were seen before.
"""
import argparse
import csv
import gzip
import json
import math
import random
import bisect
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from statistics import mean,median

import numpy as np
import analyze_index_triggers as logs
from analyze_iv_theta_hypothesis import Market
from discover_addition_patterns import FeatureBuilder,MARKET_FEATURES,STATE_FEATURES
from strategy_rule_features import indicator_arrays,predicate_grid
from audit_strike_hedge_rules import reconstruct_parents,short_batches,write

ROOT=logs.ROOT;OUT=logs.OUT


def numeric(value):
    if value in ('',None):return None
    x=float(value)
    return x if math.isfinite(x) else None


def normalized_decision_minute(t):
    return (t+timedelta(seconds=2)).replace(second=0,microsecond=0)


def family(name):
    for prefix in ('rsi','ema','bollinger','atr','adx','supertrend','donchian','spot'):
        if name.startswith(prefix):return prefix
    if name in STATE_FEATURES:return 'book_state'
    if name in MARKET_FEATURES:return 'option_market'
    return 'session_price'


def build_features(fills,parents,index,metadata):
    bycycle=defaultdict(list);replay=defaultdict(dict);targets=defaultdict(Counter)
    pairs=logs.pairing(fills,index)
    for r in fills:bycycle[(r['u'],str(r['expiry']))].append(r)
    for r in csv.DictReader((OUT/'option_minute_portfolio_replay.csv').open()):
        replay[(r['underlying'],r['expiry_date'])][(r['bar_start_ist'][:10],r['bar_start_ist'][11:16])]=numeric(r['marked_equity_close'])
    for b in short_batches(parents):
        t=normalized_decision_minute(b['start'])
        targets[(b['underlying'],b['expiry_date'],t)]['paired_sale']=1
    for p in parents:
        key=(p['underlying'],p['expiry_date'],normalized_decision_minute(p['first']))
        if p['role']=='short_cover':targets[key]['cover_quantity']+=p['quantity']
        if p['role']=='new_long':targets[key]['long_quantity']+=p['quantity']
    quarter={}
    for r in csv.DictReader((OUT/'addition_decision_opportunities.csv').open()):
        quarter[(r['underlying'],r['expiry_date'],r['date'],r['clock'])]=int(r['target'])
    bank={};data=[]
    for (u,expiry),rs in sorted(bycycle.items()):
        market=Market(u,expiry,metadata[(u,expiry)],index)
        feature=FeatureBuilder(market,rs,index,[r for r in pairs if r['underlying']==u and r['expiry_date']==expiry],replay[(u,expiry)])
        for day in sorted({str(r['t'].date()) for r in rs}):
            if (u,day) not in bank:
                bars=index.get((u,day),[])
                if any(bars[i]['t']-bars[i-1]['t']!=timedelta(minutes=1) for i in range(1,len(bars))):
                    raise ValueError('Discontinuous cash series needs segmented indicator initialization.')
                previous=sorted(d for v,d in index if v==u and d<day)
                close=index[(u,previous[-1])][-1]['close'] if previous else None
                arrays=indicator_arrays(bars,close)
                bank[(u,day)]={b['t'].strftime('%H:%M'):{k:(float(v[i]) if np.isfinite(v[i]) else None) for k,v in arrays.items()} for i,b in enumerate(bars)}
            start=datetime.fromisoformat(day+'T09:18').replace(tzinfo=logs.IST)
            for i in range(327):
                t=start+timedelta(minutes=i);clock=t.strftime('%H:%M');prev=(t-timedelta(minutes=2)).strftime('%H:%M')
                ind=bank[(u,day)].get(prev)
                if ind is None:continue
                action=targets[(u,expiry,t)];unit=logs.UNIT[u]
                qkey=(u,expiry,day,clock)
                row=dict(underlying=u,expiry_date=expiry,cycle=u+'|'+expiry,date=day,phase='preexpiry' if day<expiry else 'expiry',clock=clock,
                    split='calibration' if expiry<='2026-08-31' else 'evaluation',
                    paired_sale=action['paired_sale'],short_cover=int(action['cover_quantity']>=unit),new_long=int(action['long_quantity']>=unit),
                    cover_quantity=action['cover_quantity'],long_quantity=action['long_quantity'],quarter_target=quarter.get(qkey),
                    off_quarter=int('09:30'<=clock<'14:45' and t.minute%15 not in (0,1,2)),
                    **feature.at(t),**ind)
                data.append(row)
        print(f'Indicator features {u} {expiry}',flush=True)
    return data


def score(y,p,w=None):
    y=np.asarray(y,dtype=bool);p=np.asarray(p,dtype=bool)
    tp=int(np.sum(y&p));fp=int(np.sum(~y&p));fn=int(np.sum(y&~p));tn=int(np.sum(~y&~p))
    if w is None:w=np.ones(len(y))
    wt=float(w[y&p].sum());wf=float(w[~y&p].sum());wn=float(w[y&~p].sum())
    return dict(rows=len(y),positives=int(y.sum()),negatives=int((~y).sum()),signals=int(p.sum()),true_positives=tp,
        false_positives=fp,false_negatives=fn,precision=tp/(tp+fp) if tp+fp else None,
        recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
        balanced_accuracy=(tp/(tp+fn)+tn/(tn+fp))/2 if tp+fn and tn+fp else None,
        cycle_weighted_f1=2*wt/(2*wt+wf+wn) if 2*wt+wf+wn else 0.)


def cycle_weights(rows,indices):
    counts=Counter(rows[i]['cycle'] for i in indices)
    return np.array([1/counts[rows[i]['cycle']] for i in indices])


def predicate(values,op,level,mode,previous):
    valid=np.isfinite(values);state=valid&((values<=level) if op=='le' else (values>level))
    if mode=='state':return state
    old=np.zeros(len(values),dtype=bool);oldvalid=np.zeros(len(values),dtype=bool)
    ix=np.flatnonzero(previous>=0);old[ix]=state[previous[ix]];oldvalid[ix]=valid[previous[ix]]
    return state&oldvalid&~old


def clock_predictions(rows,indices,target):
    counts=defaultdict(lambda:[0,0]);bycycle=defaultdict(lambda:[0,0])
    for i in indices:
        if rows[i]['split']!='calibration':continue
        r=rows[i];key=(r['underlying'],r['phase'],r['clock']);y=int(r[target])
        counts[key][0]+=y;counts[key][1]+=1;bycycle[(key,r['cycle'])][0]+=y;bycycle[(key,r['cycle'])][1]+=1
    result=np.zeros(len(rows),dtype=bool)
    for i in indices:
        r=rows[i];key=(r['underlying'],r['phase'],r['clock']);a,n=counts[key]
        if r['split']=='calibration':
            b,m=bycycle[(key,r['cycle'])];a-=b;n-=m
        result[i]=(a+1)/(n+2)>=.5
    return result


def bootstrap_f1(rows,y,p,baseline,draws=5000):
    groups=defaultdict(lambda:np.zeros((2,3)))
    for r,a,b,c in zip(rows,y,p,baseline):
        d=datetime.fromisoformat(r['expiry_date']).date().isocalendar();k=(d.year,d.week)
        for j,z in enumerate((b,c)):
            groups[k][j]+=np.array([a and z,(not a) and z,a and not z],dtype=float)
    values=list(groups.values());rng=random.Random(20261026);changes=[]
    for _ in range(draws):
        v=sum(rng.choices(values,k=len(values)))
        f=[2*x[0]/(2*x[0]+x[1]+x[2]) if 2*x[0]+x[1]+x[2] else 0. for x in v]
        changes.append(f[0]-f[1])
    changes.sort()
    return dict(weeks=len(values),f1_difference=score(y,p)['f1']-score(y,baseline)['f1'],
        lower=changes[int(.025*(draws-1))],upper=changes[int(.975*(draws-1))],draws=draws)


def tolerant_event_score(rows,y,p,minutes=2):
    """One predicted signal can explain at most one same-session later event."""
    groups=defaultdict(list)
    for i,r in enumerate(rows):groups[(r['cycle'],r['date'])].append(i)
    tp=0;signals=int(np.sum(p));positives=int(np.sum(y))
    for ix in groups.values():
        events=[datetime.fromisoformat(rows[i]['date']+'T'+rows[i]['clock']) for i in ix if y[i]]
        for i in ix:
            if not p[i]:continue
            start=datetime.fromisoformat(rows[i]['date']+'T'+rows[i]['clock']);j=bisect.bisect_left(events,start)
            if j<len(events) and events[j]<=start+timedelta(minutes=minutes):
                tp+=1;events.pop(j)
    return dict(tolerance_minutes=minutes,signals=signals,events=positives,matched_events=tp,
        precision=tp/signals if signals else None,recall=tp/positives if positives else None,
        f1=2*tp/(signals+positives) if signals+positives else 0.)


def scan_indicators(rows,exclude_quarter=False,prefix='rule_match_indicator'):
    columns=[k for k in rows[0] if predicate_grid([k])]
    grid=predicate_grid(columns);arrays={k:np.array([np.nan if r[k] is None else r[k] for r in rows]) for k in columns}
    previous=np.full(len(rows),-1,dtype=int)
    for i in range(1,len(rows)):
        a,b=rows[i-1],rows[i]
        if a['cycle']==b['cycle'] and a['date']==b['date'] and datetime.fromisoformat(b['date']+'T'+b['clock'])-datetime.fromisoformat(a['date']+'T'+a['clock'])==timedelta(minutes=1):previous[i]=i-1
    tasks=[]
    for phase in ('preexpiry','expiry'):
        for task,target in [('quarter_additions','quarter_target'),('off_quarter_additions','paired_sale'),('short_covers','short_cover'),('new_protection','new_long')]:
            if exclude_quarter and task=='quarter_additions':continue
            ix=np.array([i for i,r in enumerate(rows) if r['phase']==phase and
                (r['quarter_target'] is not None if task=='quarter_additions' else bool(r['off_quarter']) if task=='off_quarter_additions' else True)],dtype=int)
            train=np.array([i for i in ix if rows[i]['split']=='calibration']);test=np.array([i for i in ix if rows[i]['split']=='evaluation'])
            y=np.array([bool(r[target]) for r in rows]);clock=clock_predictions(rows,ix,target)
            if task in ('quarter_additions','off_quarter_additions','short_covers'):clock&=np.array([bool(r['has_short_book']) for r in rows])
            tasks.append(dict(task=task,phase=phase,target=target,train=train,test=test,y=y,clock=clock,weights=cycle_weights(rows,train),rank=[]))
    all_scores=[]
    for t in tasks:
        result=score(t['y'][t['train']],t['clock'][t['train']],t['weights'])
        r=dict(task=t['task'],phase=t['phase'],family='clock',feature='clock_open_book',operator='',parameter='',mode='baseline',gate='none',feature_coverage=1.,**result)
        t['rank'].append((r,t['clock']));all_scores.append(r)
    for field,op,level,mode in grid:
        raw=predicate(arrays[field],op,level,mode,previous)
        for t in tasks:
            for gate in (('none','clock_filter') if t['task']=='quarter_additions' else ('none',)):
                pr=raw&t['clock'] if gate=='clock_filter' else raw
                result=score(t['y'][t['train']],pr[t['train']],t['weights'])
                rec=dict(task=t['task'],phase=t['phase'],family=family(field),feature=field,operator=op,parameter=level,mode=mode,gate=gate,
                    feature_coverage=float(np.isfinite(arrays[field][t['train']]).mean()),**result)
                all_scores.append(rec)
                # Retain at most a family winner, rather than a giant prediction cube.
                old=next((x for x in t['rank'] if x[0]['family']==rec['family']),None)
                rankkey=lambda r:(r['cycle_weighted_f1'],r['f1'],-r['false_positives'])
                if old is None:t['rank'].append((rec,pr.copy()))
                elif rankkey(rec)>rankkey(old[0]):t['rank'][t['rank'].index(old)]=(rec,pr.copy())
    evaluations=[];predictions=[];intervals=[];tolerant=[]
    for t in tasks:
        winner=max(t['rank'],key=lambda x:(x[0]['cycle_weighted_f1'],x[0]['f1'],-x[0]['false_positives']))
        for rec,pr in t['rank']:
            ix=t['test'];cal={k:rec[k] for k in ('family','feature','operator','parameter','mode','gate')}
            result=score(t['y'][ix],pr[ix],cycle_weights(rows,ix))
            evaluations.append(dict(task=t['task'],phase=t['phase'],selected_overall=rec is winner[0],
                calibration_cycle_weighted_f1=rec['cycle_weighted_f1'],**cal,**result))
            if rec is winner[0] or rec['family']=='clock':
                tolerant.append(dict(task=t['task'],phase=t['phase'],kind='selected' if rec is winner[0] else 'clock',
                    **tolerant_event_score([rows[i] for i in ix],t['y'][ix],pr[ix])))
                for i in ix:
                    r=rows[i];predictions.append(dict(task=t['task'],phase=t['phase'],kind='selected' if rec is winner[0] else 'clock',
                        underlying=r['underlying'],expiry_date=r['expiry_date'],date=r['date'],clock=r['clock'],target=int(t['y'][i]),predicted=int(pr[i]),**cal))
        ix=t['test'];intervals.append(dict(task=t['task'],phase=t['phase'],selected_family=winner[0]['family'],
            **bootstrap_f1([rows[i] for i in ix],t['y'][ix],winner[1][ix],t['clock'][ix])))
        print('Indicator winner',t['task'],t['phase'],winner[0]['feature'],winner[0]['parameter'],flush=True)
    write(prefix+'_grid_calibration.csv',all_scores);write(prefix+'_family_evaluation.csv',evaluations)
    write(prefix+'_predictions.csv',predictions);write(prefix+'_week_intervals.csv',intervals)
    write(prefix+'_tolerant_event_evaluation.csv',tolerant)
    return dict(distinct_indicator_predicates=len(grid),calibration_comparisons=len(all_scores),
                selected_evaluations=[r for r in evaluations if r['selected_overall']],weekly_intervals=intervals,tolerant_event_evaluation=tolerant)


def faster_feature_alignment(rows,parents):
    """Use cached next-row features: at T+1 their embargo cutoff is exactly T.

    Targets are relabeled by the actual first-fill minute, without the two-second
    shift. Thus no own-window fill can enter the no-extra-embargo sensitivity.
    The tolerated quarter-window task is excluded because its early fills could
    precede T. Only strict physical-minute action targets are used here.
    """
    targets=defaultdict(Counter)
    for b in short_batches(parents):targets[(b['underlying'],b['expiry_date'],b['start'].replace(second=0))]['paired_sale']=1
    for p in parents:
        key=(p['underlying'],p['expiry_date'],p['first'].replace(second=0))
        if p['role']=='short_cover':targets[key]['cover_quantity']+=p['quantity']
        if p['role']=='new_long':targets[key]['long_quantity']+=p['quantity']
    fixed={'underlying','expiry_date','cycle','date','phase','clock','split','paired_sale','short_cover','new_long',
           'cover_quantity','long_quantity','quarter_target','off_quarter'}
    result=[]
    for a,b in zip(rows,rows[1:]):
        if a['cycle']!=b['cycle'] or a['date']!=b['date']:continue
        t=datetime.fromisoformat(a['date']+'T'+a['clock']).replace(tzinfo=logs.IST)
        future=datetime.fromisoformat(b['date']+'T'+b['clock']).replace(tzinfo=logs.IST)
        if future-t!=timedelta(minutes=1):continue
        if datetime.fromisoformat(b['feature_cutoff_ist'])!=t:raise ValueError('Faster alignment does not have cutoff T.')
        action=targets[(a['underlying'],a['expiry_date'],t)];unit=logs.UNIT[a['underlying']]
        r={**a,**{k:v for k,v in b.items() if k not in fixed},'quarter_target':None,
           'paired_sale':action['paired_sale'],'short_cover':int(action['cover_quantity']>=unit),
           'new_long':int(action['long_quantity']>=unit),'cover_quantity':action['cover_quantity'],'long_quantity':action['long_quantity']}
        result.append(r)
    return result


def exit_grid():
    result=[('fixed_time','',0,'time')]
    levels=(.1,.15,.2,.25,.3,.4,.5,.6,.75,1,1.25,1.5)
    for field in ('cycle_equity_pct','day_change_previous_close_pct','day_change_open_pct','day_drawdown_pct'):
        result.extend(('capital_stop',field,-v,'le') for v in levels)
    for field in ('cycle_equity_pct','day_change_previous_close_pct','day_change_open_pct'):
        result.extend(('profit_target',field,v,'gt') for v in levels)
    result.extend(('carry_debit_stop','carry_debit_change_pct',v,'gt') for v in (1,2,3,4,5,7.5,10,15,20,25,30,40,50,75,100))
    result.extend(('spot_displacement','initial_spot_abs_move_pct',v,'gt') for v in (.1,.2,.3,.4,.5,.75,1,1.5,2))
    return result


def exit_match_score(cycles,predictions):
    delays=[(p-datetime.fromisoformat(c['target'])).total_seconds()/60 for c,p in zip(cycles,predictions)]
    return dict(cycles=len(cycles),matches_within_2m=sum(abs(x)<=2 for x in delays),matches_within_5m=sum(abs(x)<=5 for x in delays),
        match_rate_2m=mean(abs(x)<=2 for x in delays) if delays else None,
        median_abs_error_minutes=median(abs(x) for x in delays) if delays else None,
        mean_abs_error_minutes=mean(abs(x) for x in delays) if delays else None)


def exit_path_data(minute_rows,index):
    summaries={(r['underlying'],r['expiry_date']):r for r in csv.DictReader((OUT/'option_marked_cycle_summary.csv').open())}
    entries={(r['underlying'],r['expiry_date']):r for r in csv.DictReader((OUT/'trigger_initial_entries.csv').open())}
    indicators={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in minute_rows}
    paths=defaultdict(list);excluded=[];highwater={}
    for r in csv.DictReader((OUT/'option_minute_portfolio_replay.csv').open()):
        u,e=r['underlying'],r['expiry_date'];c=summaries[(u,e)]
        if r['bar_start_ist'][:10]!=e:continue
        if float(c['short_carry_quantity'])<=0 or not c['terminal_95pct_short_reduction_ist']:continue
        t=datetime.fromisoformat(r['equity_available_at_ist']);equity=numeric(r['marked_equity_close'])
        if equity is None or float(r['short_quantity_after_minute'])<=0:continue
        prior=numeric(c['preexpiry_last_minute_equity']);opened=numeric(c['expiry_opening_equity_before_fills'])
        previous_high=highwater.get((u,e),opened if opened is not None else equity);highwater[(u,e)]=max(previous_high,equity)
        debit=numeric(r['fixed_carry_short_debit']);debit0=numeric(c['carry_short_debit_at_previous_close'])
        entry=entries.get((u,e));bars=index.get((u,e),[])
        b=next((b for b in bars if b['t']==t-timedelta(minutes=1)),None)
        reference=numeric(entry['reference_close']) if entry else None
        features=dict(cycle_equity_pct=equity/20_000_000*100,
            day_change_previous_close_pct=(equity-prior)/20_000_000*100 if prior is not None else None,
            day_change_open_pct=(equity-opened)/20_000_000*100 if opened is not None else None,
            day_drawdown_pct=(equity-highwater[(u,e)])/20_000_000*100,
            carry_debit_change_pct=100*(debit/debit0-1) if debit is not None and debit0 else None,
            initial_spot_abs_move_pct=100*abs(b['close']/reference-1) if b and reference else None)
        cached=indicators.get((u,e,e,t.strftime('%H:%M')),{})
        for k,v in cached.items():
            if predicate_grid([k]):features[k]=v
        paths[(u,e)].append(dict(t=t,zero_volume=int(r['active_zero_volume_contracts'])>0,**features))
    cycles=[]
    for (u,e),c in summaries.items():
        if float(c['short_carry_quantity'])<=0 or not c['terminal_95pct_short_reduction_ist'] or not paths[(u,e)]:
            excluded.append(dict(underlying=u,expiry_date=e,reason='No positive carry, no observed terminal 95% short reduction, or no active completed mark.'));continue
        cycles.append(dict(underlying=u,expiry_date=e,target=c['terminal_95pct_short_reduction_ist'],path=paths[(u,e)],
            fallback=datetime.fromisoformat(e+('T15:14' if e>='2026-08-03' else 'T15:29')).replace(tzinfo=logs.IST)))
    write('rule_match_exit_exclusions.csv',excluded)
    return cycles


def predict_exit(cycle,field,parameter,op,mode='state',fresh=False):
    if op=='time':return cycle['fallback']
    previous=None
    for r in cycle['path']:
        if r['t']>=cycle['fallback']:break
        value=r.get(field)
        if value is None or (fresh and r['zero_volume']):previous=None;continue
        active=value<=parameter if op=='le' else value>parameter
        crossing=active and previous is False
        previous=active
        if active and (mode=='state' or crossing):return r['t']
    return cycle['fallback']


def scan_exits(rows,index):
    cycles=exit_path_data(rows,index);train=[c for c in cycles if c['expiry_date']<='2026-08-31'];test=[c for c in cycles if c['expiry_date']>'2026-08-31']
    grid=exit_grid()
    for field,op,param,mode in predicate_grid(list(rows[0])):
        if family(field) in ('rsi','ema','bollinger','adx','supertrend','donchian') and mode=='cross':grid.append((family(field),field,param,op))
    scores=[];selected=[];predictions=[]
    for fresh in (False,True):
        rank=[]
        for kind,field,param,op in grid:
            mode='cross' if kind in ('rsi','ema','bollinger','adx','supertrend','donchian') else 'state'
            pr=[predict_exit(c,field,param,op,mode,fresh) for c in train]
            rec=dict(family=kind,feature=field,parameter=param,operator=op,mode=mode,positive_volume_marks_only=fresh,**exit_match_score(train,pr))
            scores.append(rec);rank.append(rec)
        best=min(rank,key=lambda r:(-r['matches_within_2m'],r['mean_abs_error_minutes'],r['family']!='fixed_time',r['family'],r['feature'],r['parameter']))
        chosen=[best]+[min([r for r in rank if r['family']==f],key=lambda r:(-r['matches_within_2m'],r['mean_abs_error_minutes'])) for f in sorted({r['family'] for r in rank})]
        seen=set()
        for r in chosen:
            ident=(r['family'],r['feature'],r['parameter'],r['operator'])
            if ident in seen:continue
            seen.add(ident)
            pr=[predict_exit(c,r['feature'],r['parameter'],r['operator'],r['mode'],fresh) for c in test]
            selected.append(dict(selected_overall=r is best,calibration_cycles=r['cycles'],calibration_matches_2m=r['matches_within_2m'],
                **{k:r[k] for k in ('family','feature','parameter','operator','mode','positive_volume_marks_only')},**exit_match_score(test,pr)))
            for c,p in zip(test,pr):
                predictions.append(dict(underlying=c['underlying'],expiry_date=c['expiry_date'],selected_overall=r is best,
                    family=r['family'],feature=r['feature'],parameter=r['parameter'],positive_volume_marks_only=fresh,
                    observed_terminal_reduction_ist=c['target'],predicted_ist=p.isoformat(),
                    prediction_minus_observed_minutes=(p-datetime.fromisoformat(c['target'])).total_seconds()/60))
    write('rule_match_exit_grid_calibration.csv',scores);write('rule_match_exit_selected_evaluation.csv',selected)
    write('rule_match_exit_predictions.csv',predictions)
    return dict(eligible_cycles=len(cycles),calibration_cycles=len(train),evaluation_cycles=len(test),parameter_comparisons=len(scores),selected_comparisons=selected,
        warning='First crossings on the actual evolving book with a fixed time fallback. Not a counterfactual exit backtest; terminal 95% reduction is an analysis label, not an inferred original stop scope. Completed marks can miss intraminute triggers.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reuse-features',action='store_true')
    p.add_argument('--fast-only',action='store_true');args=p.parse_args()
    if args.reuse_features or args.fast_only:
        with gzip.open(OUT/'rule_match_indicator_features.csv.gz','rt') as f:
            rows=list(csv.DictReader(f))
        text={'underlying','expiry_date','cycle','date','phase','clock','split','feature_cutoff_ist','last_completed_bar_start_ist'}
        for r in rows:
            for k,v in r.items():
                if k not in text:r[k]=numeric(v)
        index,_=logs.load_index()
    else:
        fills=logs.read_fills();parents=reconstruct_parents(fills);index,_=logs.load_index();metadata=defaultdict(list)
        for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
            m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
        rows=build_features(fills,parents,index,metadata)
        write('rule_match_indicator_features.csv.gz',rows)
    if args.fast_only:
        fast=faster_feature_alignment(rows,reconstruct_parents(logs.read_fills()))
        result=scan_indicators(fast,exclude_quarter=True,prefix='rule_match_fast_indicator')
        result.update(minute_opportunities=len(fast),timing='Actual first-fill minute; fills before T and completed bars through T−1, without extra embargo. Quarter-window task excluded.')
        (OUT/'rule_match_fast_indicator_summary.json').write_text(json.dumps(result,indent=2)+'\n')
        return
    indicators=scan_indicators(rows);exits=scan_exits(rows,index)
    summary=dict(minute_opportunities=len(rows),indicator_scan=indicators,exit_scan=exits,
        limitations=['Retrospective hypothesis search with previously examined later data, not blinded replication.',
                     'Missing feature inputs never count as a satisfied predicate. All tested opportunities remain in denominators.',
                     'Neither indicator agreement nor exit-time agreement establishes original code identity or economic alpha.'])
    (OUT/'rule_match_mass_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
