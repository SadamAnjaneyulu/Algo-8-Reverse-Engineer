"""Cover-to-re-entry landmarks, matched controls and incremental prediction.

See COVER_REENTRY_TEST_PLAN.md. Everything is conditional on received executions
and reconstructed inventory. Neither association nor added predictive power
identifies an original instruction or a causal effect.
"""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from audit_strike_hedge_rules import ROOT, OUT, logs
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


TIMERS=np.array([556]+list(range(570,871,15)))*60
FEATURES=['own_short','opposite_short','own_long','side_equity','side_loss',
          'book_delta','book_vega','book_gamma','atm_iv','adverse_spot5',
          'adverse_spot15','range15','new_short15','since_entry','new_short1']


def count_window(times, start, end):
    """Half-open interval [start,end): no future or right-boundary leakage."""
    return np.searchsorted(times,end,side='left')-np.searchsorted(times,start,side='left')


def timer_seconds(start, duration=300):
    return int(np.maximum(0,np.minimum(start+duration,TIMERS+180)-np.maximum(start,TIMERS-2)).sum())


def outside_timer(local_seconds):
    return not np.any((TIMERS-2<=local_seconds)&(local_seconds<TIMERS+180))


def grouped_new_orders(parents):
    out=defaultdict(list)
    for p in parents:
        if p['role']=='new_short':
            out[(p['underlying'],p['expiry_date'],str(p['first'].date()),p['option_type'])].append(p)
    for ps in out.values():ps.sort(key=lambda p:(p['first'],int(p['sources'].split(';')[0])))
    return out


def build_inputs():
    d=pd.read_csv(OUT/'deep_side_minute_features.csv.gz')
    d=d.sort_values(['contract','date','clock']).reset_index(drop=True)
    d['stamp']=pd.to_datetime(d.cutoff_ist).astype('int64')/1e9
    d['previous_stamp']=d.groupby(['contract','date'],sort=False).stamp.shift()
    parents=load_parents();orders=grouped_new_orders(parents)
    covers=defaultdict(list)
    for f in logs.read_fills():
        if f['side']=='Buy' and f['q']>f['opening']:
            covers[(f['u'],str(f['expiry']),str(f['t'].date()),f['ot'])].append(f['t'].timestamp())
    for key in covers:covers[key]=np.array(sorted(covers[key]))
    rows=[]
    for key,rs in d.groupby(['underlying','expiry_date','date','option_type'],sort=False):
        u,e,day,right=key;ts=rs.stamp.to_numpy();cover=covers.get(key,np.array([]))
        own=orders.get(key,[]);other=orders.get((u,e,day,'PE' if right=='CE' else 'CE'),[])
        entry=np.array([p['first'].timestamp() for p in own]);opposite=np.array([p['first'].timestamp() for p in other])
        opposite_cover=covers.get((u,e,day,'PE' if right=='CE' else 'CE'),np.array([]))
        off=np.array([p['first'].timestamp() for p in own if outside_timer(p['first'].hour*3600+p['first'].minute*60+p['first'].second)])
        validlabels=[p for p in own if p['label'].timestamp()<=p['first'].timestamp()]
        labels=np.array([p['label'].timestamp() for p in validlabels]);label_entries=np.array([p['first'].timestamp() for p in validlabels])
        count1=count_window(cover,ts-60,ts);earlier5=count_window(cover,ts-360,ts-60)
        new1=count_window(entry,ts-60,ts)
        for i,r in enumerate(rs.to_dict('records')):
            t=ts[i];r['cover_previous_minute']=int(count1[i]>0)
            r['cover_onset']=int(count1[i]>0 and earlier5[i]==0)
            r['quiet_control']=int(count1[i]==0 and earlier5[i]==0)
            r['new_entries_previous_minute']=int(new1[i])
            r['new_parent_previous5_positive']=int(count_window(entry,t-300,t)>0)
            r['opposite_cover_previous_minute']=int(count_window(opposite_cover,t-60,t)>0)
            r['cover_next5']=int(count_window(cover,t,t+300)>0)
            r['timer_seconds5']=timer_seconds(int(r['clock_minutes'])*60)
            r['clock_phase']=int(r['clock_minutes'])%15
            r['split']='calibration' if e<='2026-08-31' else 'evaluation'
            r['week']='-'.join(map(str,datetime.fromisoformat(e).isocalendar()[:2]))
            r['backward_entry5']=int(count_window(entry,t-300,t)>0)
            for h in (1,5,10):
                r[f'entry{h}']=int(count_window(entry,t,t+h*60)>0)
                r[f'offtimer_entry{h}']=int(count_window(off,t,t+h*60)>0)
                r[f'opposite_entry{h}']=int(count_window(opposite,t,t+h*60)>0)
                r[f'later_label_entry{h}']=int(np.any((label_entries>=t)&(label_entries<t+h*60)&(labels>=t)))
            r['both_rights_entry5']=r['entry5']&r['opposite_entry5']
            rows.append(r)
    d=pd.DataFrame(rows).sort_values(['contract','date','clock']).reset_index(drop=True)
    sign=np.where(d.option_type=='CE',1.,-1.)
    own=d.same_short_units
    opposite=np.where(d.option_type=='CE',d.g_PE_short_units,d.g_CE_short_units)
    source=dict(own_short=np.log1p(own),opposite_short=np.log1p(opposite),own_long=np.log1p(d.same_long_units),
                side_equity=d.same_equity_pct_capital,side_loss=d.side_short_loss_pct,
                book_delta=-sign*d.g_book_delta_per_short_unit,book_vega=d.g_book_vega_pct_capital,
                book_gamma=d.g_book_gamma_move1pct_pct_capital,atm_iv=d.g_atm_iv_pct,
                adverse_spot5=d.adverse_spot5_pct,adverse_spot15=d.adverse_spot15_pct,
                range15=d.g_range15_pct,new_short15=np.log1p(d.new_shorts15_units),
                since_entry=np.log1p(d.since_entry.clip(lower=0)),new_short1=np.log1p(d.new_entries_previous_minute))
    for name,value in source.items():d['post_'+name]=value
    for name in FEATURES:d['pre_'+name]=d.groupby(['contract','date'],sort=False)['post_'+name].shift()
    d['pre_active']=d.pre_own_short.gt(0)&d.stamp.sub(d.previous_stamp).eq(60)
    d['post_book_active']=(d.g_CE_short_units+d.g_PE_short_units)>0
    d['time_eligible']=d.clock_minutes.between(556,904)
    d['eligible']=d.pre_active&d.post_book_active&d.time_eligible
    d['row_id']=np.arange(len(d))
    assert np.array_equal(d.entry1.to_numpy(),d.target_cover.to_numpy()),'Fresh-parent minute labels disagree with existing audit.'
    return d,parents,covers,orders


def robust_transform(d,prefix):
    names=[prefix+'_'+n for n in FEATURES]
    values=d[names].to_numpy(float)
    earlier=values[d.split.eq('calibration')&d.eligible]
    median=np.nanmedian(earlier,axis=0)
    median=np.where(np.isfinite(median),median,0.)
    lo,hi=np.nanquantile(earlier,[.25,.75],axis=0)
    scale=np.where(np.isfinite(hi-lo)&((hi-lo)>1e-8),hi-lo,1.)
    missing=~np.isfinite(values)
    filled=np.where(missing,median,values)
    return (filled-median)/scale,missing


def match_landmarks(d,prefix,exclude_simultaneous=False,strict_activity=False):
    """Outcome columns never enter matching, feature scaling or calipers."""
    x,missing=robust_transform(d,prefix)
    design=prefix+('_no_same_minute_entry' if exclude_simultaneous else '')+('_strict_activity' if strict_activity else '')
    treated=d[d.eligible&d.cover_onset.eq(1)]
    if exclude_simultaneous:treated=treated[treated.new_entries_previous_minute.eq(0)]
    controls=d[d.eligible&d.quiet_control.eq(1)]
    if exclude_simultaneous:controls=controls[controls.new_entries_previous_minute.eq(0)]
    pools={key:g.index.to_numpy() for key,g in controls.groupby(['contract','date','clock_phase','timer_seconds5'],sort=False)}
    pairs=[];excluded=[]
    for i,r in treated.iterrows():
        candidate=pools.get((r.contract,r.date,r.clock_phase,r.timer_seconds5),np.array([],int))
        if len(candidate):candidate=candidate[np.abs(d.loc[candidate,'clock_minutes'].to_numpy()-r.clock_minutes)<=45]
        if len(candidate):
            # Ratios refer to quantity+1; zero/nonzero own-side state must agree.
            original=d.loc[candidate,prefix+'_own_short'].to_numpy()
            keep=((original>0)==(r[prefix+'_own_short']>0))&(np.abs(original-r[prefix+'_own_short'])<=np.log(2))
            keep&=np.abs(d.loc[candidate,prefix+'_opposite_short'].to_numpy()-r[prefix+'_opposite_short'])<=np.log(2)
            candidate=candidate[keep]
        if len(candidate) and strict_activity:
            other=d.loc[candidate]
            keep=other.new_entries_previous_minute.gt(0).to_numpy()==(r.new_entries_previous_minute>0)
            keep&=other.new_parent_previous5_positive.to_numpy()==r.new_parent_previous5_positive
            columns=[FEATURES.index(f) for f in ('adverse_spot5','adverse_spot15','range15','since_entry')]
            keep&=(abs(x[candidate][:,columns]-x[i,columns])<=.5).all(axis=1)
            candidate=candidate[keep]
        if not len(candidate):excluded.append(dict(row_id=i,design=design,reason='No within-session clock/quantity control'));continue
        distance=np.minimum(abs(x[candidate]-x[i]),5).mean(axis=1)+(missing[candidate]!=missing[i]).mean(axis=1)
        distance+=.1*np.abs(d.loc[candidate,'clock_minutes'].to_numpy()-r.clock_minutes)/45
        chosen=int(np.argmin(distance));j=int(candidate[chosen])
        if distance[chosen]>(.5 if strict_activity else 1):
            excluded.append(dict(row_id=i,design=design,reason='Market/risk distance exceeds fixed caliper'));continue
        pairs.append(dict(treated_id=int(i),control_id=j,distance=float(distance[chosen]),
                          underlying=r.underlying,expiry_date=r.expiry_date,phase=r.phase,option_type=r.option_type,
                          date=r.date,clock=r.clock,control_clock=d.loc[j,'clock'],week=r.week,split=r.split,
                          design=design))
    return pairs,excluded


def bootstrap_difference(pairs,values,seed=20261027):
    weeks=defaultdict(list)
    for p,value in zip(pairs,values):weeks[p['week']].append(float(value))
    if len(weeks)<3:return float('nan'),float('nan')
    groups=list(weeks.values());rng=np.random.default_rng(seed)
    sums=np.array([sum(g) for g in groups]);counts=np.array([len(g) for g in groups])
    draws=rng.integers(0,len(groups),size=(2000,len(groups)))
    samples=sums[draws].sum(axis=1)/counts[draws].sum(axis=1)
    return tuple(map(float,np.quantile(samples,[.025,.975])))


def summarize_matches(d,pairs):
    rows=[];balance=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            for split in ('all','evaluation'):
                selected=[p for p in pairs if p['underlying']==u and p['phase']==phase and (split=='all' or p['split']==split)]
                if not selected:continue
                a=np.array([p['treated_id'] for p in selected]);b=np.array([p['control_id'] for p in selected])
                candidate=d[d.eligible&d.cover_onset.eq(1)&d.underlying.eq(u)&d.phase.eq(phase)]
                if selected[0]['design'].endswith('no_same_minute_entry'):candidate=candidate[candidate.new_entries_previous_minute.eq(0)]
                if split=='evaluation':candidate=candidate[candidate.split.eq(split)]
                for outcome in ('entry1','entry5','entry10','offtimer_entry5','opposite_entry5','both_rights_entry5','later_label_entry5','backward_entry5'):
                    ya=d.loc[a,outcome].to_numpy();yb=d.loc[b,outcome].to_numpy()
                    low,high=bootstrap_difference(selected,ya-yb)
                    rows.append(dict(underlying=u,phase=phase,split=split,design=selected[0]['design'],outcome=outcome,
                        eligible_cover_onsets=len(candidate),matched=len(selected),matching_coverage=len(selected)/len(candidate),
                        unique_controls=len(set(b)),cycles=len({p['expiry_date'] for p in selected}),
                        treated_rate=float(ya.mean()),control_rate=float(yb.mean()),difference=float((ya-yb).mean()),
                        weekly_bootstrap_lower=low,weekly_bootstrap_upper=high,
                        control_cover_in_next5_rate=float(d.loc[b,'cover_next5'].mean())))
                prefix=selected[0]['design'].split('_')[0]
                for f in FEATURES:
                    xa=d.loc[a,prefix+'_'+f].to_numpy(float);xb=d.loc[b,prefix+'_'+f].to_numpy(float)
                    denominator=np.nanstd(np.r_[xa,xb])
                    balance.append(dict(underlying=u,phase=phase,split=split,design=selected[0]['design'],feature=f,
                        standardized_difference=float((np.nanmean(xa)-np.nanmean(xb))/denominator) if denominator>0 else 0.,
                        treated_missing=float(np.isnan(xa).mean()),control_missing=float(np.isnan(xb).mean())))
    return rows,balance


def raw_forward_rates(covers,orders):
    rows=[];events=[]
    for (u,e,day,right),times in covers.items():
        ps=orders.get((u,e,day,right),[]);et=np.array([p['first'].timestamp() for p in ps])
        byminute=defaultdict(list)
        for t in times:byminute[int(t//60)].append(t)
        for minute,stamps in byminute.items():
            first=min(stamps);clock=datetime.fromtimestamp(first,logs.IST)
            if clock.hour*3600+clock.minute*60+clock.second>15*3600+35*60:continue
            exact=np.flatnonzero(et>=first);next_i=int(exact[0]) if len(exact) else None
            lag=et[next_i]-first if next_i is not None else np.inf
            events.append(dict(underlying=u,expiry_date=e,date=day,option_type=right,
                               phase='preexpiry' if day<e else 'expiry',first_cover_ist=clock.isoformat(),
                               next_short_seconds=float(lag) if np.isfinite(lag) else None,
                               next_short_simultaneous=lag==0,within5s=lag<=5,within60s=lag<=60,within300s=lag<=300))
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            rs=[r for r in events if r['underlying']==u and r['phase']==phase]
            rows.append(dict(underlying=u,phase=phase,cover_minutes=len(rs),
                             next_short_simultaneous=sum(r['next_short_simultaneous'] for r in rs),
                             next_short_within5s=sum(r['within5s'] for r in rs),next_short_within60s=sum(r['within60s'] for r in rs),
                             next_short_within300s=sum(r['within300s'] for r in rs)))
    return rows,events


def prediction_models(d):
    results=[];predictions=[]
    rows=d[d.eligible].copy()
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            r=rows[rows.underlying.eq(u)&rows.phase.eq(phase)].copy()
            r['right_pe']=r.option_type.eq('PE').astype(int)
            r['regime_cas']=r.date.ge('2026-08-03').astype(int)
            r['clock_sin']=np.sin(2*np.pi*r.clock_phase/15);r['clock_cos']=np.cos(2*np.pi*r.clock_phase/15)
            r['since_cover_log']=np.log1p(r.since_cover.clip(lower=0))
            base=['post_'+n for n in FEATURES]+['clock_minutes','clock_sin','clock_cos','timer_seconds5','right_pe','regime_cas']
            extra=['cover_previous_minute','cover_onset','covers15_units','since_cover_log']
            y=r.entry5.to_numpy();cal=np.flatnonzero(r.split.eq('calibration'));test=np.flatnonzero(r.split.eq('evaluation'))
            probabilities={}
            for variant,fields in [('base',base),('plus_cover',base+extra)]:
                x=r[fields].to_numpy(float);oof=np.zeros(len(cal))
                with threadpool_limits(limits=1):
                    for a,b in GroupKFold(n_splits=3).split(cal,groups=r.cycle.iloc[cal]):
                        model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler(),LogisticRegression(C=.1,max_iter=2000))
                        model.fit(x[cal[a]],y[cal[a]]);oof[b]=model.predict_proba(x[cal[b]])[:,1]
                    model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler(),LogisticRegression(C=.1,max_iter=2000))
                    model.fit(x[cal],y[cal]);p=model.predict_proba(x[test])[:,1]
                probabilities[variant]=p
                for label,truth,prob in [('earlier_group_oof',y[cal],oof),('later_check',y[test],p)]:
                    guessed=prob>=.5;tp=int(np.sum(guessed&truth.astype(bool)))
                    results.append(dict(underlying=u,phase=phase,variant=variant,sample=label,rows=len(truth),positives=int(truth.sum()),
                        log_loss=float(log_loss(truth,prob,labels=[0,1])),brier=float(brier_score_loss(truth,prob)),
                        average_precision=float(average_precision_score(truth,prob)),precision_at_050=tp/guessed.sum() if guessed.sum() else None,
                        recall_at_050=tp/truth.sum() if truth.sum() else None))
                for i,p in zip(test,p):predictions.append(dict(underlying=u,phase=phase,variant=variant,expiry_date=r.iloc[i].expiry_date,date=r.iloc[i].date,clock=r.iloc[i].clock,option_type=r.iloc[i].option_type,target=int(y[i]),probability=float(p)))
    return results,predictions


def main():
    d,parents,covers,orders=build_inputs()
    save_records('cover_reentry_landmarks.csv.gz',d.to_dict('records'))
    raw,events=raw_forward_rates(covers,orders)
    save_records('cover_reentry_raw_forward.csv',raw);save_records('cover_reentry_cover_minutes.csv.gz',events)
    allpairs=[];excluded=[];metrics=[];balance=[]
    for prefix,no_simultaneous,strict in [('post',False,False),('pre',False,False),('post',True,False),('post',False,True)]:
        pairs,miss=match_landmarks(d,prefix,no_simultaneous,strict);allpairs.extend(pairs);excluded.extend(miss)
        summaries,diagnostics=summarize_matches(d,pairs);metrics.extend(summaries);balance.extend(diagnostics)
        print('Matched',prefix,no_simultaneous,strict,len(pairs),'unmatched',len(miss),flush=True)
    save_records('cover_reentry_matched_pairs.csv',allpairs);save_records('cover_reentry_unmatched.csv',excluded)
    save_records('cover_reentry_matched_summary.csv',metrics);save_records('cover_reentry_match_balance.csv',balance)
    evaluation,predictions=prediction_models(d)
    save_records('cover_reentry_prediction_evaluation.csv',evaluation);save_records('cover_reentry_prediction_probabilities.csv.gz',predictions)
    counts=[]
    for (u,phase),g in d.groupby(['underlying','phase']):
        counts.append(dict(underlying=u,phase=phase,all_cover_minutes=int(g.cover_previous_minute.sum()),
                           onset_cover_minutes=int(g.cover_onset.sum()),eligible_onsets=int((g.eligible&g.cover_onset.eq(1)).sum()),
                           excluded_time_or_no_prestate=int((g.cover_onset.eq(1)&~(g.time_eligible&g.pre_active)).sum()),
                           full_flat_onsets=int((g.cover_onset.eq(1)&g.pre_active&g.time_eligible&~g.post_book_active).sum())))
    (OUT/'cover_reentry_summary.json').write_text(json.dumps(dict(landmarks=len(d),counts=counts,primary_horizon_minutes=5,
        input_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in
                      (ROOT/'Trades_GKOHNP140.csv',OUT/'allocation_parent_inventory.csv',OUT/'deep_side_minute_features.csv.gz')},
        input_roles='Received fill opening/closing classification and stable pure new-short parents',
        note='Within-cycle matched association and inspected later predictive checks; no identified original re-entry trigger, causal effect or alpha.'),indent=2)+'\n')


if __name__=='__main__':main()
