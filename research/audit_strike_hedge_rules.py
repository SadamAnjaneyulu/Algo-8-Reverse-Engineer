"""Parent-level strike and fresh-protection audit used by the mass rule study."""
import csv
import argparse
import gzip
import io
import json
import math
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from statistics import mean

import numpy as np
import analyze_index_triggers as logs
import option_pricing_model as pricing
from analyze_iv_theta_hypothesis import Market

ROOT=logs.ROOT;OUT=logs.OUT


def write(name,rows):
    if not rows:return
    if name.endswith('.gz'):
        raw=(OUT/name).open('wb');stream=gzip.GzipFile(fileobj=raw,mode='wb',mtime=0)
        f=io.TextIOWrapper(stream,newline='')
    else:raw=None;f=(OUT/name).open('w',newline='')
    with f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    if raw:raw.close()


def reconstruct_parents(fills):
    bysource={r['source']:r for r in fills};groups=defaultdict(list)
    with (ROOT/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as f:
        for source,raw in enumerate(csv.reader(f),1):
            label=datetime.strptime(raw[23],'%m/%d/%Y %H:%M').replace(tzinfo=logs.IST)
            groups[(str(label.date()),raw[3],raw[4])].append((bysource[source],label,int(raw[19])))
    out=[]
    for group in groups.values():
        rs=[r for r,_,_ in group];r=rs[0];q=sum(x['q'] for x in rs)
        requested=group[0][2]
        if q>requested or len({n for _,_,n in group})!=1:
            raise ValueError('Parent fills exceed a constant requested quantity.')
        stable=all(x['opening']==x['reverse_opening'] for x in rs)
        pureopen=all(x['opening']==x['q'] for x in rs);pureclose=all(x['opening']==0 for x in rs)
        role='mixed_or_tie_sensitive'
        if stable and pureopen:role='new_short' if r['side']=='Sell' else 'new_long'
        if stable and pureclose:role='long_sell' if r['side']=='Sell' else 'short_cover'
        out.append(dict(underlying=r['u'],expiry_date=str(r['expiry']),strike=r['strike'],option_type=r['ot'],
            side=r['side'],quantity=q,requested_quantity=requested,fully_observed_filled=q==requested,
            role=role,first=min(x['t'] for x in rs),last=max(x['t'] for x in rs),
            label=group[0][1],price=sum(float(x['price'])*x['q'] for x in rs)/q,
            sources=';'.join(str(x['source']) for x in rs)))
    return out


def clusters(parents,gap=2):
    result=[]
    for r in sorted(parents,key=lambda x:(x['first'],x['sources'])):
        if not result or (r['first']-result[-1][-1]['first']).total_seconds()>gap:result.append([])
        result[-1].append(r)
    return result


def short_batches(parents):
    sessions=defaultdict(list)
    for r in parents:
        if r['role']=='new_short':sessions[(r['underlying'],r['expiry_date'],str(r['first'].date()))].append(r)
    result=[]
    for (u,e,day),rs in sorted(sessions.items()):
        for batch in clusters(rs):
            ks=defaultdict(set)
            for r in batch:ks[r['strike']].add(r['option_type'])
            paired=sorted(k for k,v in ks.items() if v=={'CE','PE'})
            if not paired:continue
            result.append(dict(underlying=u,expiry_date=e,date=day,start=min(r['first'] for r in batch),
                end=max(r['first'] for r in batch),strikes=paired,parents=batch,
                event_id=f'{u}|{e}|{len(result)+1}'))
    return result


def assign_new_longs(batches,parents,maximum_seconds=30):
    """Every new-long parent assigned at most once; equal-distance ties excluded."""
    assignment=defaultdict(list);ambiguous=0
    lookup=defaultdict(list)
    for b in batches:lookup[(b['underlying'],b['expiry_date'],b['date'])].append(b)
    for p in parents:
        if p['role']!='new_long':continue
        candidates=[]
        for b in lookup[(p['underlying'],p['expiry_date'],str(p['first'].date()))]:
            distance=min(abs((p['first']-r['first']).total_seconds()) for r in b['parents'])
            if distance<=maximum_seconds:candidates.append((distance,b))
        if not candidates:continue
        best=min(x[0] for x in candidates);chosen=[b for d,b in candidates if d==best]
        if len(chosen)!=1:ambiguous+=1;continue
        assignment[chosen[0]['event_id']].append((p,best))
    return assignment,ambiguous


def hedge_link_rows(batches,parents):
    assigned,_=assign_new_longs(batches,parents)
    return [dict(underlying=b['underlying'],expiry_date=b['expiry_date'],event_id=b['event_id'],
        short_batch_start_ist=b['start'].isoformat(),short_strikes=';'.join(map(str,b['strikes'])),
        long_start_ist=p['first'].isoformat(),option_type=p['option_type'],long_strike=p['strike'],long_quantity=p['quantity'],
        executed_long_price=p['price'],nearest_short_parent_distance_seconds=d,
        long_minus_batch_start_seconds=(p['first']-b['start']).total_seconds(),source_rows=p['sources'])
        for b in batches for p,d in assigned[b['event_id']]]


def cover_associations(batches,parents):
    covered=[{**p,'role':'new_long'} for p in parents if p['role']=='short_cover']
    assigned,ambiguous=assign_new_longs(batches,covered)
    links=[];summary=[]
    for b in batches:
        for p,d in assigned[b['event_id']]:
            links.append(dict(underlying=b['underlying'],expiry_date=b['expiry_date'],event_id=b['event_id'],
                short_batch_start_ist=b['start'].isoformat(),new_short_strikes=';'.join(map(str,b['strikes'])),
                cover_start_ist=p['first'].isoformat(),covered_strike=p['strike'],option_type=p['option_type'],
                cover_quantity=p['quantity'],nearest_new_short_distance_seconds=d,
                cover_minus_batch_start_seconds=(p['first']-b['start']).total_seconds(),source_rows=p['sources']))
    for phase in ('preexpiry','expiry'):
        for scheduled in (True,False):
            chosen=[]
            for b in batches:
                t=b['start'];n=(t+timedelta(seconds=2)).replace(second=0);q=n-timedelta(minutes=n.minute%15)
                if ('preexpiry' if b['date']<b['expiry_date'] else 'expiry')==phase and '09:18'<=t.strftime('%H:%M')<'14:45' and ((n-q).total_seconds()<180)==scheduled:chosen.append(b)
            for window in (5,15,30):
                selections=[[p for p,d in assigned[b['event_id']] if d<=window] for b in chosen]
                summary.append(dict(phase=phase,cohort='scheduled' if scheduled else 'off_quarter',window_seconds=window,
                    paired_batches=len(chosen),any_cover=sum(bool(ps) for ps in selections),
                    both_rights_covered=sum({p['option_type'] for p in ps}=={'CE','PE'} for ps in selections),
                    exactly_one_right_covered=sum(len({p['option_type'] for p in ps})==1 for ps in selections)))
    return links,dict(comparisons=summary,ambiguous_cover_nearest_batch=ambiguous,
        note='Temporal links can be before or after fresh sales, and do not prove original basket/stop identity.')


def inventory_at(rows,t):
    inv=Counter()
    for r in rows:
        if r['t']<t:inv[(r['strike'],r['ot'])]+=r['signed']
    return inv


def association_audit(fills,parents,index):
    batches=short_batches(parents);assigned,ambiguous=assign_new_longs(batches,parents)
    bycycle=defaultdict(list)
    for r in fills:bycycle[(r['u'],str(r['expiry']))].append(r)
    initial={}
    for b in batches:
        if b['date']<b['expiry_date']:
            key=(b['underlying'],b['expiry_date'])
            if key not in initial or b['start']<initial[key]['start']:initial[key]=b
    initial_sets={key:{k for b in batches if (b['underlying'],b['expiry_date'])==key and
        seed['start']<=b['start']<seed['start']+timedelta(minutes=1) for k in b['strikes']} for key,seed in initial.items()}
    associations=[];strikes=[]
    for b in batches:
        u,e=b['underlying'],b['expiry_date'];phase='preexpiry' if b['date']<e else 'expiry'
        rs=bycycle[(u,e)];before=inventory_at(rs,b['start']);after=inventory_at(rs,b['end']+timedelta(seconds=6))
        rec=dict(underlying=u,expiry_date=e,date=b['date'],phase=phase,event_id=b['event_id'],
            intraday_0918_1445='09:18'<=b['start'].strftime('%H:%M')<'14:45',
            start_ist=b['start'].isoformat(),last_parent_start_ist=b['end'].isoformat(),paired_strikes=';'.join(map(str,b['strikes'])),
            parent_count=len(b['parents']),source_rows=';'.join(p['sources'] for p in b['parents']))
        for ot in ('CE','PE'):
            q=sum(p['quantity'] for p in b['parents'] if p['option_type']==ot)
            rec['new_short_'+ot.lower()]=q
            for window in (2,5,30):
                buys=[p for p,d in assigned[b['event_id']] if d<=window and p['option_type']==ot]
                outward=[p for p in buys if any(p['strike']>k if ot=='CE' else p['strike']<k for k in b['strikes'])]
                rec[f'new_long_{ot.lower()}_{window}s']=sum(p['quantity'] for p in buys)
                rec[f'outward_new_long_{ot.lower()}_{window}s']=sum(p['quantity'] for p in outward)
            for label,book in [('before',before),('six_seconds_after_last_start',after)]:
                rec[f'{label}_total_short_{ot.lower()}']=sum(max(-v,0) for (k,o),v in book.items() if o==ot)
                rec[f'{label}_total_long_{ot.lower()}']=sum(max(v,0) for (k,o),v in book.items() if o==ot)
                rec[f'{label}_outward_long_{ot.lower()}']=sum(max(v,0) for (k,o),v in book.items() if o==ot and
                    (k>max(b['strikes']) if ot=='CE' else k<min(b['strikes'])))
        associations.append(rec)
        prior,_=logs.reference(index,u,b['start']);seed=initial.get((u,e))
        for k in b['strikes']:
            strikes.append(dict(underlying=u,expiry_date=e,date=b['date'],phase=phase,event_id=b['event_id'],
                event_time_ist=b['start'].isoformat(),strike=k,initial_strike=seed['strikes'][0] if seed else '',
                initial_first_minute_strikes=';'.join(map(str,sorted(initial_sets.get((u,e),set())))),
                matches_any_initial_strike=k in initial_sets.get((u,e),set()),
                opening_batch=bool(seed and seed['start']<=b['start']<seed['start']+timedelta(minutes=1)),
                intraday_0918_1445=rec['intraday_0918_1445'],
                nearest_completed_spot_strike=logs.round_strike(prior['close'],u) if prior else '',
                spot_reference_bar=prior['t'].isoformat() if prior else '',
                source_rows=rec['source_rows']))
    summary=[]
    for u,phase,cohort in [(u,p,c) for u in ('NIFTY','SENSEX') for p in ('preexpiry','expiry') for c in ('all_observed','intraday_0918_1445')]:
            a=[r for r in associations if r['underlying']==u and r['phase']==phase and (cohort=='all_observed' or r['intraday_0918_1445'])]
            k=[r for r in strikes if r['underlying']==u and r['phase']==phase and not r['opening_batch'] and r['initial_strike']!='' and
                (cohort=='all_observed' or r['intraday_0918_1445'])]
            eligible=[r for r in k if r['nearest_completed_spot_strike']!='']
            record=dict(underlying=u,phase=phase,cohort=cohort,paired_batches=len(a),later_strike_observations=len(k),
                same_as_initial=sum(r['strike']==r['initial_strike'] for r in k),different_from_initial=sum(r['strike']!=r['initial_strike'] for r in k),
                same_as_any_initial_strike=sum(r['matches_any_initial_strike'] for r in k),
                different_from_every_initial_strike=sum(not r['matches_any_initial_strike'] for r in k),
                current_spot_reference_available=len(eligible),matches_current_spot_atm=sum(r['strike']==r['nearest_completed_spot_strike'] for r in eligible))
            for w in (2,5,30):
                record[f'both_fresh_outward_buys_within_{w}s']=sum(r[f'outward_new_long_ce_{w}s']>0 and r[f'outward_new_long_pe_{w}s']>0 for r in a)
                record[f'both_new_long_qty_at_least_new_short_{w}s']=sum(r[f'new_long_ce_{w}s']>=r['new_short_ce'] and r[f'new_long_pe_{w}s']>=r['new_short_pe'] for r in a)
            record['both_outward_longs_already_present']=sum(r['before_outward_long_ce']>0 and r['before_outward_long_pe']>0 for r in a)
            record['both_outward_longs_present_six_seconds_after']=sum(r['six_seconds_after_last_start_outward_long_ce']>0 and r['six_seconds_after_last_start_outward_long_pe']>0 for r in a)
            summary.append(record)
    return batches,associations,strikes,dict(groups=summary,ambiguous_new_long_nearest_batch=ambiguous,
        note='One-to-one temporal association, not an original basket ID. Existing long quantities are not proof of sufficient risk coverage.')


def hedge_events(parents):
    bycontract=defaultdict(list)
    for p in parents:
        if p['role']=='new_long':bycontract[(p['underlying'],p['expiry_date'],str(p['first'].date()),p['strike'],p['option_type'])].append(p)
    events=[]
    for (u,e,day,k,ot),ps in sorted(bycontract.items()):
        for batch in clusters(ps):
            t=min(p['first'] for p in batch);q=sum(p['quantity'] for p in batch)
            events.append(dict(underlying=u,expiry_date=e,date=day,strike=k,option_type=ot,t=t,quantity=q,
                phase='preexpiry' if day<e else 'expiry',stage='initial' if t.strftime('%H:%M')<'09:18' else 'routine' if t.strftime('%H:%M')<'14:45' else 'late',
                executed_price=sum(p['price']*p['quantity'] for p in batch)/q,sources=';'.join(p['sources'] for p in batch)))
    return events


def selector_grid(u):
    prices=([.5+i*.25 for i in range(19)]+[6,7.5,10,15,20,30,50,75,100]) if u=='NIFTY' else ([1+i*.5 for i in range(39)]+[25,30,40,50,75,100,150,200])
    rules=[]
    for family in ('premium_nearest','premium_ceiling','premium_floor'):
        rules.extend((family,p) for p in prices)
    step=logs.STEP[u]
    for family in ('atm_fixed_gap','last_short_fixed_gap'):
        rules.extend((family,k) for k in range(step,step*101,step))
    rules.extend(('spot_percent_gap',p/4) for p in range(1,33))
    rules.extend(('sigma_distance',p/4) for p in range(1,33))
    rules.extend(('abs_delta',p) for p in (.005,.01,.015,.02,.025,.03,.04,.05,.075,.1,.15,.2,.25))
    rules.extend(('straddle_premium_ratio',p) for p in (.001,.0025,.005,.0075,.01,.015,.02,.03,.04,.05,.075,.1))
    return rules


def choose_strike(event,candidates,family,parameter,u):
    """Candidates sorted by outward distance; deterministic nearest-strike ties."""
    if not candidates:return None
    sign=1 if event['option_type']=='CE' else -1
    if family in ('atm_fixed_gap','last_short_fixed_gap','spot_percent_gap','sigma_distance'):
        if family=='atm_fixed_gap':base=event['atm'];gap=parameter
        elif family=='last_short_fixed_gap':base=event['last_short'];gap=parameter
        elif family=='spot_percent_gap':base=event['spot'];gap=event['spot']*parameter/100
        else:base=event['spot'];gap=event['sigma_distance']*parameter if event['sigma_distance'] is not None else None
        if base is None or gap is None:return None
        k=logs.round_strike(base+sign*gap,u)
        return k if any(c['strike']==k for c in candidates) else None
    if family=='abs_delta':eligible=[c for c in candidates if c['abs_delta'] is not None];field='abs_delta';target=parameter
    else:
        eligible=candidates;field='price';target=parameter
        if family=='straddle_premium_ratio':
            if event['straddle_price'] is None:return None
            target=parameter*event['straddle_price']
        if family=='premium_ceiling':eligible=[c for c in eligible if c['price']<=target]
        if family=='premium_floor':eligible=[c for c in eligible if c['price']>=target]
    return min(eligible,key=lambda c:(abs(c[field]-target),abs(c['strike']-event['spot']),c['strike']))['strike'] if eligible else None


def selector_score(events,predictions):
    cycles=defaultdict(list);exact=0;available=0;errors=[]
    for e,k in zip(events,predictions):
        hit=k==e['strike'];exact+=hit;available+=k is not None;cycles[e['expiry_date']].append(hit)
        if k is not None:errors.append(abs(k-e['strike'])/logs.STEP[e['underlying']])
    return dict(events=len(events),cycles=len(cycles),predictions_available=available,exact=exact,
                exact_rate=exact/len(events) if events else None,
                cycle_mean_exact=mean(mean(v) for v in cycles.values()) if cycles else None,
                mean_strike_error_steps=mean(errors) if errors else None)


def short_strike_prediction(event,rule,u):
    reference,rounding,offset=rule
    if reference in ('initial_strike','previous_strike','previous_same_window_strike'):return event.get(reference)
    if reference=='hysteresis':
        old=event.get('previous_strike');spot=event.get('spot_lag_1')
        if old is None or spot is None:return None
        return old if abs(spot-old)<=offset*logs.STEP[u] else logs.round_strike(spot,u)
    if reference.startswith(('momentum_shift_','momentum_project_','momentum_round_')):
        period=int(reference.rsplit('_',1)[1]);change=event.get(f'completed_change_{period}');spot=event.get('spot_lag_1')
        if change is None or spot is None or change==0:return None
        sign=1 if change>0 else -1
        if reference.startswith('momentum_shift_'):return logs.round_strike(spot+sign*offset*logs.STEP[u],u)
        if reference.startswith('momentum_project_'):return logs.round_strike(spot+offset*change,u)
        boundary=math.ceil(spot/logs.STEP[u]) if sign>0 else math.floor(spot/logs.STEP[u])
        return int(boundary+sign*offset)*logs.STEP[u]
    spot=event.get(reference)
    if spot is None:return None
    scaled=spot/logs.STEP[u]
    k=math.floor(scaled+.5) if rounding=='nearest' else math.floor(scaled) if rounding=='floor' else math.ceil(scaled)
    return int(k+offset)*logs.STEP[u]


def scan_short_strikes(batches,index,metadata):
    bycycle=defaultdict(list)
    for b in batches:bycycle[(b['underlying'],b['expiry_date'])].append(b)
    events=[]
    for (u,e),bs in sorted(bycycle.items()):
        market=Market(u,e,metadata[(u,e)],index);previous=None;initial=None;window_strikes={}
        for b in sorted(bs,key=lambda b:b['start']):
            if b['date']<e and initial is None:initial=b['strikes'][0]
            t=b['start'];floor=t.replace(second=0,microsecond=0)
            lookup={r['t']:r for r in index.get((u,b['date']),[])}
            refs={}
            for lag in (1,2,3,5):
                bar=lookup.get(floor-timedelta(minutes=lag));refs[f'spot_lag_{lag}']=bar['close'] if bar else None
            current=lookup.get(floor);refs['spot_current_open']=current['open'] if current else None
            state=market.state(b['date'],(floor-timedelta(minutes=1)).strftime('%H:%M')) if refs['spot_lag_1'] else None
            refs['parity_forward']=state['forward'] if state else None
            normalized=(t+timedelta(seconds=2)).replace(second=0,microsecond=0)
            quarter=normalized-timedelta(minutes=normalized.minute%15)
            window=(b['date'],quarter.strftime('%H:%M')) if (normalized-quarter).total_seconds()<180 else None
            refs['previous_same_window_strike']=window_strikes.get(window) if window else None
            for period in (1,3,5,10,15):
                old=lookup.get(floor-timedelta(minutes=1+period))
                refs[f'completed_change_{period}']=refs['spot_lag_1']-old['close'] if old and refs['spot_lag_1'] is not None else None
            for lag in (1,2,3):
                bar_time=quarter-timedelta(minutes=lag)
                bar=lookup.get(bar_time) if window and bar_time+timedelta(minutes=1)<=t else None
                refs[f'quarter_anchor_lag_{lag}']=bar['close'] if bar else None
            if '09:18'<=t.strftime('%H:%M')<'14:45':
                for k in b['strikes']:
                    events.append(dict(underlying=u,expiry_date=e,phase='preexpiry' if b['date']<e else 'expiry',
                        cohort='scheduled' if window and t.strftime('%H:%M')>='09:30' else 'off_quarter',
                        event_time_ist=t.isoformat(),strike=k,initial_strike=initial,previous_strike=previous,
                        actual_bar_atm_interval_overlap=bool(current and current['high']>=k-logs.STEP[u]/2 and current['low']<k+logs.STEP[u]/2),
                        **refs))
            previous=b['strikes'][0]
            if window:window_strikes[window]=b['strikes'][0]
    rules=[(ref,r,offset) for ref in ('spot_lag_1','spot_lag_2','spot_lag_3','spot_lag_5','spot_current_open','parity_forward',
        'quarter_anchor_lag_1','quarter_anchor_lag_2','quarter_anchor_lag_3')
        for r in ('nearest','floor','ceil') for offset in (-1,0,1)]
    rules+=[('initial_strike','identity',0),('previous_strike','identity',0),('previous_same_window_strike','identity',0)]
    rules.extend(('hysteresis','nearest',v) for v in (.5,.75,1,1.25,1.5,2))
    # Secondary directional hypothesis added after inspecting off-quarter strike
    # offsets. It is retrospective discovery, not a preregistered replication.
    for period in (1,3,5,10,15):
        rules.extend((f'momentum_shift_{period}','nearest',v) for v in (-1,-.5,.5,1,1.5,2))
        rules.extend((f'momentum_project_{period}','nearest',v) for v in (-2,-1,.5,1,2,3,5))
        rules.extend((f'momentum_round_{period}','directional',v) for v in (0,1))
    grid=[];selected=[];predictions=[];bounds=[]
    for u,phase,cohort in [(u,p,c) for u in ('NIFTY','SENSEX') for p in ('preexpiry','expiry') for c in ('all','scheduled','off_quarter')]:
            es=[r for r in events if r['underlying']==u and r['phase']==phase and (cohort=='all' or r['cohort']==cohort)]
            train=[r for r in es if r['expiry_date']<='2026-08-31'];test=[r for r in es if r['expiry_date']>'2026-08-31']
            rank=[]
            for rule in rules:
                pr=[short_strike_prediction(r,rule,u) for r in train]
                rec=dict(underlying=u,phase=phase,cohort=cohort,reference=rule[0],rounding=rule[1],offset_or_hysteresis_steps=rule[2],**selector_score(train,pr))
                grid.append(rec);rank.append((rec,rule))
            best=max(rank,key=lambda x:(x[0]['cycle_mean_exact'],x[0]['exact_rate']))
            for kind,rule in [('selected',best[1]),('nearest_prior_close',('spot_lag_1','nearest',0)),('current_minute_open',('spot_current_open','nearest',0))]:
                pr=[short_strike_prediction(r,rule,u) for r in test]
                selected.append(dict(underlying=u,phase=phase,cohort=cohort,kind=kind,reference=rule[0],rounding=rule[1],offset_or_hysteresis_steps=rule[2],
                    calibration_cycle_mean_exact=next(r['cycle_mean_exact'] for r,rule2 in rank if rule2==rule),**selector_score(test,pr)))
                for r,k in zip(test,pr):predictions.append(dict(underlying=u,expiry_date=r['expiry_date'],phase=phase,cohort=cohort,kind=kind,
                    event_time_ist=r['event_time_ist'],observed_strike=r['strike'],predicted_strike=k if k is not None else '',exact=k==r['strike']))
            bounds.append(dict(underlying=u,phase=phase,cohort=cohort,observations=len(es),atm_interval_overlap=sum(r['actual_bar_atm_interval_overlap'] for r in es),
                note='Ex-post full event-minute high/low feasibility only; not a causal decision quote or a fitted selector.'))
    write('rule_match_short_strike_inputs.csv',events);write('rule_match_short_strike_grid_calibration.csv',grid)
    write('rule_match_short_strike_evaluation.csv',selected);write('rule_match_short_strike_predictions.csv',predictions)
    return dict(parameter_rows=len(grid),selected_comparisons=selected,ex_post_spot_range_bounds=bounds)


def scan_hedges(events,parents,index,metadata):
    bycycle=defaultdict(list);ps=defaultdict(list)
    for e in events:bycycle[(e['underlying'],e['expiry_date'])].append(e)
    for p in parents:
        if p['role']=='new_short':ps[(p['underlying'],p['expiry_date'],p['option_type'])].append(p)
    candidate_rows=[];enriched=[]
    for (u,expiry),es in sorted(bycycle.items()):
        market=Market(u,expiry,metadata[(u,expiry)],index)
        for e in es:
            t=e['t'];prior,_=logs.reference(index,u,t);clock=(t.replace(second=0)-timedelta(minutes=1)).strftime('%H:%M')
            spot=prior['close'] if prior else None
            historical=[p for p in ps[(u,expiry,e['option_type'])] if p['first']<t]
            last=max(historical,key=lambda p:p['first'])['strike'] if historical else None
            state=market.state(e['date'],clock) if spot else None
            straddle=None
            if state:
                c,p=market.bar(e['date'],state['strike'],'CE',clock),market.bar(e['date'],state['strike'],'PE',clock)
                straddle=c['close']+p['close']
            r={**e,'spot':spot,'atm':logs.round_strike(spot,u) if spot else None,'last_short':last,
                'sigma_distance':state['forward']*state['iv']*math.sqrt(state['tau']) if state else None,
                'straddle_price':straddle,'candidate_clock':clock,'candidates':[]}
            if spot:
                for (d,k,ot),bars in market.quotes.items():
                    if d!=e['date'] or ot!=e['option_type'] or not(k>spot if ot=='CE' else k<spot):continue
                    b=bars.get(clock)
                    if not b or b['close']<=0:continue
                    delta=None
                    if state:
                        iv=pricing.implied_vol(b['close'],state['forward'],k,state['tau'],ot,state['rate'])
                        if iv is not None:delta=abs(pricing.greeks(state['forward'],k,state['tau'],iv,ot,state['rate'])['delta'])
                    c=dict(strike=k,price=b['close'],volume=b['volume'],abs_delta=delta)
                    r['candidates'].append(c)
                    candidate_rows.append(dict(underlying=u,expiry_date=expiry,event_time_ist=t.isoformat(),bought_strike=e['strike'],
                        option_type=ot,candidate_bar_start_ist=e['date']+'T'+clock+':00+05:30',**c))
            enriched.append(r)
        print(f'Hedge selector quotes {u} {expiry}',flush=True)
    scores=[];selected=[];predictions=[];coverage=[]
    cohorts=sorted({(e['underlying'],e['phase'],e['stage']) for e in enriched})
    for u,phase,stage in cohorts:
        es=[e for e in enriched if (e['underlying'],e['phase'],e['stage'])==(u,phase,stage)]
        train=[e for e in es if e['expiry_date']<='2026-08-31'];test=[e for e in es if e['expiry_date']>'2026-08-31']
        for liquidity in ('positive_volume','positive_price'):
            chains={id(e):[c for c in e['candidates'] if liquidity=='positive_price' or c['volume']>0] for e in es}
            coverage.append(dict(underlying=u,phase=phase,stage=stage,liquidity=liquidity,events=len(es),
                selected_contract_has_eligible_prior_quote=sum(any(c['strike']==e['strike'] for c in chains[id(e)]) for e in es)))
            rank=[]
            for family,param in selector_grid(u):
                pr=[choose_strike(e,chains[id(e)],family,param,u) for e in train]
                score=selector_score(train,pr)
                rec=dict(underlying=u,phase=phase,stage=stage,liquidity=liquidity,family=family,parameter=param,**score)
                scores.append(rec);rank.append(rec)
            if len({e['expiry_date'] for e in train})<3 or len(train)<10 or not test:continue
            best=min(rank,key=lambda r:(-r['cycle_mean_exact'],r['family'],r['parameter']))
            contenders=[('selected',best['family'],best['parameter']),('fixed_premium_reference','premium_nearest',2 if u=='NIFTY' else 7)]
            for kind,family,param in contenders:
                pr=[choose_strike(e,chains[id(e)],family,param,u) for e in test]
                selected.append(dict(underlying=u,phase=phase,stage=stage,liquidity=liquidity,kind=kind,family=family,parameter=param,
                    calibration_cycles=len({e['expiry_date'] for e in train}),calibration_events=len(train),
                    calibration_cycle_mean_exact=next(r['cycle_mean_exact'] for r in rank if r['family']==family and r['parameter']==param),
                    **selector_score(test,pr)))
                for e,k in zip(test,pr):
                    predictions.append(dict(underlying=u,expiry_date=e['expiry_date'],phase=phase,stage=stage,liquidity=liquidity,kind=kind,
                        event_time_ist=e['t'].isoformat(),option_type=e['option_type'],observed_strike=e['strike'],predicted_strike=k if k is not None else '',
                        exact=k==e['strike'],family=family,parameter=param,source_rows=e['sources']))
    write('rule_match_hedge_candidate_quotes.csv.gz',candidate_rows)
    write('rule_match_hedge_grid_calibration.csv',scores);write('rule_match_hedge_selected_evaluation.csv',selected)
    write('rule_match_hedge_predictions.csv',predictions);write('rule_match_hedge_quote_coverage.csv',coverage)
    write('rule_match_hedge_events.csv',[{k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in e.items() if k!='candidates'} for e in enriched])
    return dict(events=len(events),calibration_parameter_rows=len(scores),selected_comparisons=selected,quote_coverage=coverage,
        warning='Incomplete retrospective traded-contract chain; positive-volume eligibility is only a trade-candle freshness proxy, not original executable quotes.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--associations-only',action='store_true')
    p.add_argument('--skip-hedge-grid',action='store_true');args=p.parse_args()
    fills=logs.read_fills();parents=reconstruct_parents(fills);index,_=logs.load_index()
    batches,associations,strikes,summary=association_audit(fills,parents,index)
    summary.update(parent_roles=dict(Counter(p['role'] for p in parents)),
                   incompletely_filled_parents=sum(not p['fully_observed_filled'] for p in parents))
    cover_links,cover_summary=cover_associations(batches,parents)
    summary['cover_associations']=cover_summary
    write('rule_match_short_hedge_associations.csv',associations);write('rule_match_same_or_current_atm.csv',strikes)
    write('rule_match_hedge_short_links.csv',hedge_link_rows(batches,parents))
    write('rule_match_cover_short_links.csv',cover_links)
    (OUT/'rule_match_association_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    if args.associations_only:return
    metadata=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    ss=scan_short_strikes(short_batches(parents),index,metadata)
    (OUT/'rule_match_short_strike_summary.json').write_text(json.dumps(ss,indent=2)+'\n')
    if args.skip_hedge_grid:return
    s=scan_hedges(hedge_events(parents),parents,index,metadata)
    (OUT/'rule_match_hedge_summary.json').write_text(json.dumps(s,indent=2)+'\n')
    print('Completed hedge selector grid',flush=True)


if __name__=='__main__':main()
