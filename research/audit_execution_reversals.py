"""Audit rapid same-contract liquidation reversals; intent remains unobserved."""
import json
from collections import defaultdict

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import OUT,logs
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def detect_motifs(records):
    """Atomic records with t, before/after quantity and source lists."""
    motifs=[];i=0;sign_start=None
    while i<len(records):
        r=records[i]
        if r['before']==0 and r['after']!=0:sign_start=r['t']
        if r['before']*r['after']<0:sign_start=r['t']
        if r['before'] and r['after']==0 and i+1<len(records):
            next_r=records[i+1];opposite=np.sign(next_r['after'])==-np.sign(r['before'])
            if next_r['before']==0 and opposite and 0<=next_r['t']-r['t']<=10:
                maximum=abs(next_r['after']);j=i+2
                while j<len(records) and records[j]['t']-next_r['t']<=60:
                    candidate=records[j]
                    if candidate['after']*r['before']>0:break
                    maximum=max(maximum,abs(candidate['after']))
                    if candidate['after']==0:
                        age=r['t']-sign_start if sign_start is not None else None
                        motifs.append(dict(close=r,opening=next_r,end=candidate,records=records[i+1:j+1],
                                           peak_opposite_quantity=maximum,old_sign_age_seconds=age,
                                           conservative=(age is not None and age>=60 and maximum<=abs(r['before']))))
                        i=j;sign_start=None;break
                    j+=1
        i+=1
    return motifs


def main():
    f=pd.read_csv(OUT/'playbook_fill_ledger.csv.gz');e=pd.read_csv(OUT/'playbook_event_book.csv.gz')
    parents=load_parents();parentmap={p['parent_id']:p for p in parents}
    sourceparent={int(s):p['parent_id'] for p in parents for s in p['sources'].split(';')}
    flats={key:np.array([pd.Timestamp(t).timestamp() for t in g.timestamp_ist]) for key,g in
           e[e.event_class.isin(['short_book_flat','all_roles_flat'])].groupby(['underlying','expiry_date'])}
    rows=[];tagged=defaultdict(set)
    for (u,expiry,k,right),g in f.sort_values(['timestamp_ist','source_row']).groupby(['underlying','expiry_date','strike','option_type']):
        records=[]
        for t,q in g.groupby('timestamp_ist',sort=True):
            records.append(dict(t=pd.Timestamp(t).timestamp(),timestamp_ist=t,before=int(q.quantity_before.iloc[0]),after=int(q.quantity_after.iloc[-1]),
                                sources=q.source_row.astype(int).tolist(),opening_sources=q[q.opening_quantity>0].source_row.astype(int).tolist()))
        for motif in detect_motifs(records):
            a,b,c=motif['close'],motif['opening'],motif['end'];all_sources=[s for r in motif['records'] for s in r['opening_sources']]
            if motif['conservative']:
                for source in all_sources:tagged[sourceparent[source]].add(source)
            times=flats.get((u,expiry),np.array([]));near=np.any((times>=a['t']-10)&(times<=c['t']+10))
            rows.append(dict(underlying=u,expiry_date=expiry,option_type=right,strike=k,phase='preexpiry' if a['timestamp_ist'][:10]<expiry else 'expiry',
                close_to_zero_ist=a['timestamp_ist'],opposite_open_ist=b['timestamp_ist'],neutralized_ist=c['timestamp_ist'],
                prior_quantity=a['before'],opposite_quantity=b['after'],peak_opposite_quantity=motif['peak_opposite_quantity'],
                old_sign_age_seconds=motif['old_sign_age_seconds'],neutralization_seconds=c['t']-b['t'],
                conservative_candidate=motif['conservative'],near_short_book_flat=bool(near),
                opening_sources=';'.join(map(str,all_sources)),
                opening_parent_ids=';'.join(sorted({sourceparent[s] for s in all_sources}))))
    tagrows=[]
    for pid,sources in tagged.items():
        p=parentmap[pid];all_sources={int(s) for s in p['sources'].split(';')}
        tagrows.append(dict(parent_id=pid,underlying=p['underlying'],expiry_date=p['expiry_date'],phase='preexpiry' if str(p['first'].date())<p['expiry_date'] else 'expiry',
                            role=p['role'],quantity=p['quantity'],fully_tagged=all_sources<=sources,
                            tagged_source_rows=';'.join(map(str,sorted(sources)))))
    save_records('playbook_rapid_reversal_motifs.csv',rows);save_records('playbook_reversal_parent_flags.csv',tagrows)
    fully={r['parent_id'] for r in tagrows if r['fully_tagged'] and r['role'] in ('new_short','new_long')}
    summaries=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            m=[r for r in rows if r['underlying']==u and r['phase']==phase]
            ps=[p for p in parents if p['underlying']==u and ('preexpiry' if str(p['first'].date())<p['expiry_date'] else 'expiry')==phase]
            summaries.append(dict(underlying=u,phase=phase,motifs=len(m),conservative_motifs=sum(r['conservative_candidate'] for r in m),
                cycles_with_motif=len({r['expiry_date'] for r in m}),
                conservative_motifs_near_short_flat=sum(r['conservative_candidate'] and r['near_short_book_flat'] for r in m),
                pure_new_short_parents=sum(p['role']=='new_short' for p in ps),
                fully_tagged_new_short_parents=sum(p['role']=='new_short' and p['parent_id'] in fully for p in ps),
                fully_tagged_new_long_parents=sum(p['role']=='new_long' and p['parent_id'] in fully for p in ps)))
    save_records('playbook_reversal_summary.csv',summaries)
    predictions=pd.read_csv(OUT/'deep_allocation_stop_predictions.csv.gz')
    predictions=predictions[predictions.task.str.startswith('completed_close|fifo|')]
    comparisons=[]
    for model in ('global_program','clock_only'):
        for sample in ('all_inventory_openings','excluding_conservative_reversals'):
            q=predictions[predictions.model.eq(model)]
            if sample.startswith('excluding'):q=q[~q.parent_id.isin(fully)]
            comparisons.append(dict(model=model,sample=sample,later_cases=len(q),matches2=int(q.error_minutes.abs().le(2).sum()),
                                    match_rate2=float(q.error_minutes.abs().le(2).mean())))
    save_records('playbook_frozen_exit_reversal_sensitivity.csv',comparisons)
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
