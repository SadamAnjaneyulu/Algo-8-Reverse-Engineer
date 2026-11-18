"""Fixed, interpretable allocation and market-state audit; no indicator search."""
import csv
import json
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
from datetime import datetime,timedelta

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import ROOT,OUT,logs
from analyze_side_allocations import load_parents
from clarify_position_lifecycle import WINDOWS
from rank_trigger_probabilities import save_records


ROLES=['CE_short','PE_short','CE_long','PE_long']
CLOCKS=['09:16']+[f'{m//60:02d}:{m%60:02d}' for m in range(570,871,15)]


def block(expiry):return 'fit_Jun_Jul' if expiry<='2026-07-31' else 'validation_Aug' if expiry<='2026-08-31' else 'later_Sep_Oct'


def mode(values):
    counts=Counter(values);peak=max(counts.values());choices=sorted(v for v,n in counts.items() if n==peak)
    return choices[0],choices,peak


def features(index,u,cutoff):
    day=str(cutoff.date());bars=index.get((u,day),[])
    past=[b for b in bars if b['t']+timedelta(minutes=1)<=cutoff]
    out=dict(market_available_at_ist=past[-1]['t'].isoformat() if past else '',
             prior15_return_pct=None,prior15_efficiency=None,prior15_range_pct=None,prior15_rv_annual_pct=None,
             direction15='unavailable',efficiency15='unavailable',range15='unavailable',
             opening_body_pct=None,opening_range_pct=None,gap_pct=None,prior_session_type='unavailable')
    if past:
        first=past[0];out['market_available_at_ist']=(past[-1]['t']+timedelta(minutes=1)).isoformat()
        if first['t'].strftime('%H:%M')=='09:15':
            body=100*(first['close']/first['open']-1);width=100*(first['high']-first['low'])/first['open']
            out.update(opening_body_pct=body,opening_range_pct=width)
        if len(past)>=16 and (past[-1]['t']-past[-16]['t']).total_seconds()==900:
            closes=np.array([b['close'] for b in past[-16:]]);changes=np.diff(closes)
            ret=100*(closes[-1]/closes[0]-1);denom=abs(changes).sum();eff=abs(closes[-1]-closes[0])/denom if denom else 0.
            width=100*(max(b['high'] for b in past[-15:])-min(b['low'] for b in past[-15:]))/closes[0]
            rv=np.sqrt(np.mean(np.diff(np.log(closes))**2)*252*(360 if day>='2026-08-03' else 375))*100
            out.update(prior15_return_pct=ret,prior15_efficiency=eff,prior15_range_pct=width,prior15_rv_annual_pct=rv,
                       direction15='down' if ret<-.1 else 'up' if ret>.1 else 'flat',
                       efficiency15='choppy' if eff<=.3 else 'directional' if eff>=.7 else 'mixed',
                       range15='small' if width<=.15 else 'medium' if width<=.35 else 'large')
    earlier=sorted(d for (right,d) in index if right==u and d<day)
    if earlier and past:
        previous=index[(u,earlier[-1])]
        if previous:
            out['gap_pct']=100*(past[0]['open']/previous[-1]['close']-1)
            width=max(b['high'] for b in previous)-min(b['low'] for b in previous)
            body=abs(previous[-1]['close']-previous[0]['open'])/width if width else 0.
            out['prior_session_type']='choppy' if body<=.3 else 'directional' if body>=.7 else 'mixed'
    return out


def snapshot(sequence,stamp):
    where=bisect_left(sequence['times'],stamp)-1
    return {role:0 for role in ROLES} if where<0 else {role:int(sequence['rows'][where]['after_'+role]) for role in ROLES}


def main():
    fills=pd.read_csv(OUT/'playbook_fill_ledger.csv.gz');events=pd.read_csv(OUT/'playbook_event_book.csv.gz')
    parents=load_parents();index,_=logs.load_index()
    event_groups={key:dict(times=g.timestamp_ist.tolist(),rows=g.to_dict('records')) for key,g in events.sort_values('timestamp_ist').groupby(['underlying','expiry_date'])}
    fill_groups={key:g.to_dict('records') for key,g in fills.groupby(['underlying','expiry_date','date'])}
    flowtypes={'CE_short':('Sell','CE','opening_quantity'),'PE_short':('Sell','PE','opening_quantity'),
               'CE_long':('Buy','CE','opening_quantity'),'PE_long':('Buy','PE','opening_quantity')}
    windows=[]
    for (u,e,day),fs in sorted(fill_groups.items()):
        previous=None
        for clock in CLOCKS:
            t=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=logs.IST)
            start=t-timedelta(minutes=1) if clock=='09:16' else t-timedelta(seconds=2)
            end=t+timedelta(minutes=1 if clock=='09:16' else 3)
            chosen=[f for f in fs if start.isoformat()<=f['timestamp_ist']<end.isoformat()]
            before=snapshot(event_groups[(u,e)],start.isoformat());after=snapshot(event_groups[(u,e)],end.isoformat())
            row=dict(underlying=u,expiry_date=e,date=day,phase='preexpiry' if day<e else 'expiry',block=block(e),clock=clock,
                     window_start_ist=start.isoformat(),window_end_exclusive_ist=end.isoformat(),
                     clock_type='opening' if clock=='09:16' else 'recurring17' if clock in WINDOWS else 'other_quarter',
                     active_short_before=before['CE_short']+before['PE_short']>0,
                     **features(index,u,t if clock=='09:16' else start))
            for role,(side,right,qfield) in flowtypes.items():
                rs=[r for r in chosen if r['side']==side and r['option_type']==right]
                row['before_'+role]=before[role];row['after_'+role]=after[role]
                row['add_'+role]=sum(r[qfield] for r in rs);row['units_'+role]=row['add_'+role]/logs.UNIT[u]
                row['first_'+role]=min((r['timestamp_ist'] for r in rs if r[qfield]>0),default='')
                if previous is not None and role.endswith('short'):
                    between=[r for r in fs if previous['window_end_exclusive_ist']<=r['timestamp_ist']<start.isoformat() and r['side']=='Buy' and r['option_type']==right]
                    row['replace_'+role+'_units']=sum(r['closing_quantity'] for r in between)/logs.UNIT[u]
                    row['restore_'+role+'_units']=max(0,previous['after_'+role]-before[role])/logs.UNIT[u]
            row['any_new_short']=row['add_CE_short']+row['add_PE_short']>0
            row['both_short_rights']=min(row['add_CE_short'],row['add_PE_short'])>0
            row['all_four_new']=all(row['add_'+role]>0 for role in ROLES)
            row['equal_short_quantities']=row['add_CE_short']==row['add_PE_short']
            row['equal_all_four']=len({row['add_'+role] for role in ROLES})==1
            if row['both_short_rights']:
                row['short_first_fill_gap_seconds']=abs((datetime.fromisoformat(row['first_CE_short'])-datetime.fromisoformat(row['first_PE_short'])).total_seconds())
            else:row['short_first_fill_gap_seconds']=None
            row['mean_short_base_units']=(row['units_CE_short']+row['units_PE_short'])/2
            windows.append(row);previous=row
    w=pd.DataFrame(windows)
    legacy=pd.read_csv(OUT/'allocation_window_sizes.csv')
    merged=w.merge(legacy,on=['underlying','expiry_date','date','clock'],validate='one_to_one')
    for role in ROLES:
        right,typ=role.split('_');assert np.array_equal(merged['add_'+role],merged['new_'+typ+'_'+right+'_quantity'])
    fitted={}
    for (u,phase,clock),g in w[w.block.eq('fit_Jun_Jul')].groupby(['underlying','phase','clock']):
        fitted[(u,phase,clock)]=np.mean([mode(g['units_'+role].tolist())[0] for role in ROLES[:2]])
    w['clock_expected_short_units_per_right']=[fitted[(r.underlying,r.phase,r.clock)] for r in w.itertuples()]
    w['clock_centered_short_units']=w.mean_short_base_units-w.clock_expected_short_units_per_right
    save_records('playbook_allocation_windows.csv',w.to_dict('records'))
    stats=[]
    for (u,phase,clock),g in w.groupby(['underlying','phase','clock']):
        for role in ROLES:
            values=g['units_'+role].tolist();m,choices,n=mode(values)
            stats.append(dict(underlying=u,phase=phase,clock=clock,role=role,sessions=len(g),positive_windows=int(g['units_'+role].gt(0).sum()),
                              minimum_units=min(values),median_units=float(np.median(values)),maximum_units=max(values),
                              modal_units=m,all_modes='|'.join(map(str,choices)),modal_sessions=n))
    save_records('playbook_quantity_distributions.csv',stats)
    models=[];model_predictions=[]
    for (u,phase),g in w.groupby(['underlying','phase']):
        fit=g[g.block.eq('fit_Jun_Jul')]
        modes={clock:np.array([mode(q['units_'+role].tolist())[0] for role in ROLES]) for clock,q in fit.groupby('clock')}
        for label in ('validation_Aug','later_Sep_Oct'):
            sample=g[g.block.eq(label)&g.clock.isin(WINDOWS)]
            for model in ('clock_modes','replace_previous_covers','restore_previous_after_quantity'):
                hits=[];errors=[];joint=[]
                for r in sample.to_dict('records'):
                    actual=np.array([r['units_'+role] for role in ROLES])
                    guess=modes[r['clock']] if model=='clock_modes' else np.array([r[('replace_' if model.startswith('replace') else 'restore_')+role+'_units'] for role in ROLES[:2]])
                    length=len(guess);hits.append(np.array_equal(actual[:2],guess[:2]));errors.append(np.mean(abs(actual[:length]-guess)))
                    if length==4:joint.append(np.array_equal(actual,guess))
                    model_predictions.append(dict(underlying=u,phase=phase,block=label,clock=r['clock'],expiry_date=r['expiry_date'],model=model,
                                                  actual_short_units='|'.join(map(str,actual[:2])),predicted_short_units='|'.join(map(str,guess[:2])),exact_short_pair=hits[-1]))
                if hits:models.append(dict(underlying=u,phase=phase,block=label,model=model,windows=len(hits),cycles=sample.expiry_date.nunique(),
                                            short_pair_match=float(np.mean(hits)),mean_abs_base_units=float(np.mean(errors)),four_role_match=float(np.mean(joint)) if joint else None))
    save_records('playbook_size_model_checks.csv',models);save_records('playbook_size_model_predictions.csv',model_predictions)
    marketrows=[]
    for (u,phase,kind),g in w[w.clock.ne('09:16')].groupby(['underlying','phase','clock_type']):
        for axis in ('direction15','efficiency15','range15'):
            for state,q in g.groupby(axis):
                marketrows.append(dict(underlying=u,phase=phase,clock_type=kind,axis=axis,market_state=state,
                    observed_sessions=q.date.nunique(),cycles=q.expiry_date.nunique(),windows=len(q),active_windows=int(q.active_short_before.sum()),
                    allocations=int(q.any_new_short.sum()),allocation_rate=float(q.any_new_short.mean()),
                    active_allocations=int((q.active_short_before&q.any_new_short).sum()),
                    active_allocation_rate=float(q[q.active_short_before].any_new_short.mean()) if q.active_short_before.any() else None,
                    mean_added_short_units_per_right=float(q.mean_short_base_units.mean()),
                    mean_clock_centered_short_units=float(q.clock_centered_short_units.mean()),
                    short_quantity_symmetric_rate=float(q.equal_short_quantities.mean())))
    save_records('playbook_market_state_windows.csv',marketrows)
    contrasts=[]
    active=w[w.active_short_before&w.clock.ne('09:16')]
    active=active[active.phase.eq('expiry')|active.clock_type.eq('recurring17')]
    for (u,phase,period),g in active.groupby(['underlying','phase','block']):
        for axis,a,b in [('direction15','up','down'),('efficiency15','directional','choppy'),('range15','large','small')]:
            pivot=g.groupby(['date',axis]).clock_centered_short_units.mean().unstack()
            if a not in pivot or b not in pivot:continue
            values=(pivot[a]-pivot[b]).dropna().to_numpy()
            if not len(values):continue
            rng=np.random.default_rng(20261027)
            low,high=np.quantile(values[rng.integers(0,len(values),size=(2000,len(values)))].mean(axis=1),[.025,.975]) if len(values)>=3 else (None,None)
            contrasts.append(dict(underlying=u,phase=phase,block=period,axis=axis,contrast=a+' minus '+b,paired_sessions=len(values),
                                  mean_clock_centered_quantity_difference=float(np.mean(values)),session_bootstrap_lower=low,session_bootstrap_upper=high))
    save_records('playbook_market_size_contrasts.csv',contrasts)
    # Calendar candidates use only the 35 logged expiries and stored index sessions.
    candidates=[];first_trade_date=fills.date.min();last_trade_date=fills.date.max()
    for (u,e),sequence in sorted(event_groups.items()):
        days=sorted(day for (right,day) in index if right==u and day<e)
        day=days[-1] if days else None
        if day is None:continue
        fs=fill_groups.get((u,e,day),[])
        ss=[r for r in fs if r['side']=='Sell' and r['opening_quantity']>0]
        t=datetime.fromisoformat(day+'T09:16').replace(tzinfo=logs.IST)
        f=features(index,u,t)
        candidates.append(dict(underlying=u,expiry_date=e,candidate_preexpiry_date=day,
            observed_new_short=bool(ss),first_new_short_ist=min((r['timestamp_ist'] for r in ss),default=''),
            trade_history_status='observed' if ss else 'outside_export_date_range' if day<first_trade_date or day>last_trade_date else 'no_recorded_preexpiry_trade_eligibility_unknown',
            **f))
    save_records('playbook_calendar_candidates.csv',candidates)
    openings=[]
    for (u,e,day),fs in sorted(fill_groups.items()):
        if day>=e:continue
        seq=event_groups[(u,e)];t=datetime.fromisoformat(day+'T09:17').replace(tzinfo=logs.IST)
        q=snapshot(seq,t.isoformat());row=dict(underlying=u,expiry_date=e,date=day,snapshot_ist=t.isoformat(),**q)
        for role,(side,right,field) in flowtypes.items():
            matching=[r for r in fs if r['side']==side and r['option_type']==right and r[field]>0]
            first=min(matching,key=lambda r:r['timestamp_ist']) if matching else None
            row['first_'+role+'_ist']=first['timestamp_ist'] if first else ''
            row['first_'+role+'_label']=first['order_label_ist'] if first else ''
            row['first_'+role+'_strike']=first['strike'] if first else None
            row['gross_'+role+'_before0917']=sum(r[field] for r in matching if r['timestamp_ist']<t.isoformat())
        openings.append(row)
    save_records('playbook_initial_role_times.csv',openings)
    openingstates=[]
    c=pd.DataFrame(candidates)
    for u,g in c.groupby('underlying'):
        axes=dict(prior_session_type=g.prior_session_type,
                  opening_body=g.opening_body_pct.map(lambda x:'unavailable' if pd.isna(x) else 'down' if x<-.1 else 'up' if x>.1 else 'flat'),
                  opening_range=g.opening_range_pct.map(lambda x:'unavailable' if pd.isna(x) else 'small' if x<=.15 else 'medium' if x<=.3 else 'large'),
                  gap=g.gap_pct.abs().map(lambda x:'unavailable' if pd.isna(x) else 'small' if x<=.3 else 'medium' if x<=.75 else 'large'))
        for axis,values in axes.items():
            for state,ix in values.groupby(values).groups.items():
                q=g.loc[ix];openingstates.append(dict(underlying=u,axis=axis,market_state=state,candidate_sessions=len(q),observed_entry_sessions=int(q.observed_new_short.sum()),
                    observed_rate=float(q.observed_new_short.mean()),missing_or_unknown_trade_sessions=int((~q.observed_new_short).sum())))
    save_records('playbook_initial_market_states.csv',openingstates)
    cadence=[]
    for (u,phase),gs in events.groupby(['underlying','phase']):
        pure=[p for p in parents if p['underlying']==u and p['role']=='new_short' and ('preexpiry' if str(p['first'].date())<p['expiry_date'] else 'expiry')==phase]
        def timed(t):
            secs=t.hour*3600+t.minute*60+t.second
            return any(int(clock[:2])*3600+int(clock[3:])*60-2<=secs<int(clock[:2])*3600+int(clock[3:])*60+180 for clock in CLOCKS)
        short_seconds=gs[gs.short_CE_open.add(gs.short_PE_open).gt(0)]
        cadence.append(dict(underlying=u,phase=phase,fresh_short_parents=len(pure),parents_in_nominal_windows=sum(timed(p['first']) for p in pure),
                            parents_outside_nominal_windows=sum(not timed(p['first']) for p in pure),
                            fresh_short_seconds=len(short_seconds),seconds_in_nominal_windows=sum(timed(datetime.fromisoformat(t)) for t in short_seconds.timestamp_ist),
                            requested_parent_size_one_base_unit=sum(p['requested_quantity']==logs.UNIT[u] for p in pure),
                            requested_parent_size_multiple_base_unit=sum(p['requested_quantity']%logs.UNIT[u]==0 for p in pure),
                            parent_labels_in_nominal_windows=sum(timed(p['label']) for p in pure),
                            first_fills_after1433=sum(p['first'].strftime('%H:%M:%S')>='14:33:00' for p in pure),
                            first_fills_after1500=sum(p['first'].strftime('%H:%M:%S')>='15:00:00' for p in pure),
                            minimum_requested_units=min(p['requested_quantity']/logs.UNIT[u] for p in pure),
                            median_requested_units=float(np.median([p['requested_quantity']/logs.UNIT[u] for p in pure])),
                            maximum_requested_units=max(p['requested_quantity']/logs.UNIT[u] for p in pure)))
    save_records('playbook_cadence_summary.csv',cadence)
    summary=dict(windows=len(w),source_window_quantity_matches=len(merged),calendar_candidates=len(candidates),
                 preexpiry_observed_sessions=len(openings),preexpiry_candidates_without_recorded_entry=int((~c.observed_new_short).sum()),
                 preexpiry_recurring_windows=len(w[w.phase.eq('preexpiry')&w.clock_type.eq('recurring17')]),
                 note='Fixed buckets and quantity comparisons, no indicator search. Calendar candidates are not a certified eligible/no-trade universe. Earlier/validation/later dates have been inspected previously.')
    (OUT/'playbook_allocation_audit.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
