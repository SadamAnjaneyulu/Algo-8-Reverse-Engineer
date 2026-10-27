"""Fixed-cohort source forensics and negative controls; no intent labels invented."""
from __future__ import annotations
import hashlib,json,sys
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from replay_inputs import market_cache

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CACHE=HERE/'.cache'
sys.path.insert(0,str(ROOT/'research'))
from audit_execution_reversals import detect_motifs
from clarify_position_lifecycle import WINDOWS
SOURCE=ROOT/'research/outputs';PRIOR=ROOT/'research/hypothesis_controller_search'

def iso(t):return pd.Timestamp(t,unit='s',tz='UTC').tz_convert('Asia/Kolkata').isoformat()
def seconds(s):return int(pd.Timestamp(s).timestamp())
def qty_at(records,t):
    i=bisect_right([r['t'] for r in records],t)-1
    return records[i]['after'] if i>=0 else 0

def atomize(fills):
    histories={};closures=[]
    for key,g in fills.sort_values(['timestamp_ist','source_row']).groupby(['underlying','expiry_date','strike','option_type'],sort=True):
        rs=[];age=None
        for stamp,q in g.groupby('timestamp_ist',sort=True):
            r=dict(t=seconds(stamp),before=int(q.quantity_before.iloc[0]),after=int(q.quantity_after.iloc[-1]),sources=q.source_row.astype(int).tolist(),
                   parents=sorted(q.parent_id.unique()),timestamp_ist=stamp)
            if (r['before']==0 and r['after']!=0) or r['before']*r['after']<0:age=r['t']
            r['old_sign_age']=None if age is None else r['t']-age
            rs.append(r)
        histories[key]=rs
        for i,r in enumerate(rs):
            if not r['before'] or r['after']!=0 or r['old_sign_age'] is None or r['old_sign_age']<60:continue
            nxt=rs[i+1] if i+1<len(rs) else None;reopen=nxt if nxt and 0<=nxt['t']-r['t']<=10 and nxt['after'] else None
            peak=0;neutral=None
            if reopen:
                for a in rs[i+1:]:
                    if a['t']>reopen['t']+60:break
                    peak=max(peak,abs(a['after']))
                    if a['after']==0:neutral=a;break
            u,e,k,right=key
            closures.append(dict(sequence_id=f'{u}|{e}|{k}{right}|{r["timestamp_ist"]}',underlying=u,expiry_date=e,strike=k,option_type=right,
                phase='preexpiry' if r['timestamp_ist'][:10]<e else 'expiry',split='fit' if e<='2026-07-31' else 'validation' if e<='2026-08-31' else 'later',
                close_ist=r['timestamp_ist'],closed_quantity=abs(r['before']),old_role='long' if r['before']>0 else 'short',old_sign_age_seconds=r['old_sign_age'],
                reopen_within10=reopen is not None,reopen_ist=reopen['timestamp_ist'] if reopen else '',reopen_quantity=abs(reopen['after']) if reopen else None,
                reopening_opposite=np.sign(reopen['after'])==-np.sign(r['before']) if reopen else None,
                quantity_equal=abs(reopen['after'])==abs(r['before']) if reopen else None,
                bounded_peak=peak<=abs(r['before']) if reopen else None,peak_quantity=peak if reopen else None,
                returned_zero_60=neutral is not None if reopen else None,
                close_sources=';'.join(map(str,r['sources'])),closed_base_units=abs(r['before'])/(65 if u=='NIFTY' else 20)))
    return histories,pd.DataFrame(closures)


def run():
    HERE.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    fills=pd.read_csv(SOURCE/'playbook_fill_ledger.csv.gz');fills['second']=pd.to_datetime(fills.timestamp_ist).map(lambda t:int(t.timestamp()))
    original=pd.read_csv(SOURCE/'playbook_rapid_reversal_motifs.csv');cases=original[original.conservative_candidate].copy().reset_index(drop=True);assert len(cases)==59
    fingerprint=hashlib.sha256((SOURCE/'playbook_rapid_reversal_motifs.csv').read_bytes()).hexdigest()
    histories,controls=atomize(fills)
    meta=json.loads((PRIOR/'outputs/cycle_metadata.json').read_text());cyclemap={(c['underlying'],c['expiry_date']):c['cycle_id'] for c in meta}
    market={};sources=fills.set_index('source_row',drop=False);parent_counts=fills.groupby('parent_id').size();ledger=[];children=[];timeline=[];neighbors=[];hyp=[]
    grouped={(u,e):g for (u,e),g in fills.groupby(['underlying','expiry_date'])}
    # Available export references, not verified order-submission identifiers.
    import csv
    with (ROOT/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as stream:
        rawrefs={i:(row[3],row[4],float(row[17]),int(row[20]),row[27],row[28],row[166]) for i,row in enumerate(csv.reader(stream),1)}
    tag_codes={tag:f'T{i}' for i,tag in enumerate(sorted({r[6] for r in rawrefs.values()}))}
    for i,m in cases.iterrows():
        mid=f'M{i+1:02}';key=(m.underlying,m.expiry_date,int(m.strike),m.option_type);rs=histories[key]
        close,op,end=map(seconds,[m.close_to_zero_ist,m.opposite_open_ist,m.neutralized_ist]);lookup={r['t']:j for j,r in enumerate(rs)};at=lookup[close];oi=lookup[op];ei=lookup[end]
        assert rs[at]['before']==m.prior_quantity and rs[oi]['after']==m.opposite_quantity and rs[ei]['after']==0
        burst=at
        while burst>0:
            a,b=rs[burst-1],rs[burst]
            if b['t']-a['t']>10 or a['before']*m.prior_quantity<=0 or abs(a['after'])>=abs(a['before']) or a['after']*m.prior_quantity<0:break
            burst-=1
        start=rs[burst]['t'];burst_qty=abs(rs[burst]['before']);closing=sources.loc[[s for r in rs[burst:at+1] for s in r['sources']]]
        opening=sources.loc[rs[oi]['sources']];neutral=sources.loc[rs[ei]['sources']]
        boundary_same=bool(set(rs[at]['parents'])&set(rs[oi]['parents']));all_close_parents=set(closing.parent_id);open_parents=set(opening.parent_id)
        ff=grouped[(m.underlying,m.expiry_date)];contract=ff[ff.strike.eq(m.strike)&ff.option_type.eq(m.option_type)]
        seq=contract[contract.second.between(start,end)]
        closing_sizes=set(sources.loc[rs[at]['sources']].parent_requested_quantity)
        opening_sizes=set(opening.parent_requested_quantity)
        repeated_payload=bool(closing_sizes&opening_sizes)
        close_rows=sources.loc[rs[at]['sources']]
        close_signature={(int(r.parent_requested_quantity),rawrefs[int(r.source_row)][2]) for r in close_rows.itertuples()}
        open_signature={(int(r.parent_requested_quantity),rawrefs[int(r.source_row)][2]) for r in opening.itertuples()}
        same_quantity_limit=bool(close_signature&open_signature)
        close_tags={tag_codes[rawrefs[int(s)][6]] for s in close_rows.source_row};open_tags={tag_codes[rawrefs[int(s)][6]] for s in opening.source_row};neutral_tags={tag_codes[rawrefs[int(s)][6]] for s in neutral.source_row}
        repeated_burst_payload=bool(set(closing.parent_requested_quantity)&opening_sizes)
        same_label=bool(set(closing.order_label_ist)&set(opening.order_label_ist))
        partial=any(parent_counts[p]>1 for p in all_close_parents|open_parents|set(neutral.parent_id))
        eq=abs(m.opposite_quantity)==abs(m.prior_quantity);reqeq=bool(opening.parent_requested_quantity.eq(abs(m.prior_quantity)).any())
        opposite=sources.loc[[s for r in rs[oi:ei+1] for s in r['sources']]]
        gross=float(opposite.cash_change.sum());turn=float((opposite.incremental_quantity*opposite.execution_price).sum());parents=int(opposite.parent_id.nunique())
        rotation=ff[ff.option_type.eq(m.option_type)&ff.strike.ne(m.strike)&ff.side.eq('Buy')&ff.opening_quantity.eq(abs(m.prior_quantity))&ff.second.between(close-5,end+5)]
        nearby_short=ff[ff.option_type.eq(m.option_type)&ff.side.eq('Sell')&ff.opening_quantity.gt(0)&ff.second.between(close-5,end+5)]
        pure_rotation=m.prior_quantity>0 and len(rotation)>0 and len(nearby_short)==0
        near_allocation=ff[ff.side.eq('Sell')&ff.opening_quantity.gt(0)&ff.second.between(op-5,op+5)]
        paired_strikes=[int(k) for k,g in near_allocation.groupby('strike') if set(g.option_type)=={'CE','PE'}]
        scheduled_label=bool(set(opening.order_label_ist.str[11:16])&({'09:16'}|set(WINDOWS)))
        scheduled_pair=bool(paired_strikes and scheduled_label)
        cid=cyclemap[(m.underlying,m.expiry_date)]
        if cid not in market:
            z=np.load(market_cache()/f'cycle_{cid:02}.npz');market[cid]={k:z[k] for k in ['minutes','strikes','rights','feature','previous']};z.close()
        z=market[cid];ci=next(j for j,(k,r) in enumerate(zip(z['strikes'],z['rights'])) if k==m.strike and r==int(m.option_type=='PE'))
        def quote(t):
            minute=t//60;where=np.searchsorted(z['minutes'],minute)
            if where>=len(z['minutes']) or z['minutes'][where]!=minute:return (np.nan,np.nan,'')
            return float(z['feature'][where,0]),float(z['previous'][where,ci]),iso(minute*60)
        pre=quote(close);post1=quote(end+60);post5=quote(end+300);before5=quote(close-300)
        next_contract=next((r for r in rs[ei+1:]),None)
        later_same=ff[ff.option_type.eq(m.option_type)&ff.second.gt(end)&ff.opening_quantity.gt(0)].sort_values(['second','source_row'])
        later_other=ff[ff.option_type.ne(m.option_type)&ff.second.gt(end)&ff.opening_quantity.gt(0)].sort_values(['second','source_row'])
        q60=qty_at(rs,end+60);q300=qty_at(rs,end+300);restored=next((r['timestamp_ist'] for r in rs[ei+1:] if r['t']<=end+300 and r['after']==m.prior_quantity),'')
        source_ids=[s for r in rs[burst:ei+1] for s in r['sources']]
        row=dict(motif_id=mid,underlying=m.underlying,expiry_date=m.expiry_date,strike=int(m.strike),option_type=m.option_type,phase=m.phase,
             split='fit' if m.expiry_date<='2026-07-31' else 'validation' if m.expiry_date<='2026-08-31' else 'later',
             closing_burst_start_ist=iso(start),first_close_to_zero_ist=m.close_to_zero_ist,opposite_open_ist=m.opposite_open_ist,neutralized_ist=m.neutralized_ist,
             prior_atomic_quantity=int(m.prior_quantity),closing_burst_initial_quantity=int(rs[burst]['before']),opposite_quantity=int(m.opposite_quantity),
             atomic_quantity_equal=bool(eq),burst_quantity_equal=abs(m.opposite_quantity)==burst_qty,opposite_vs_atomic='equal' if eq else 'below' if abs(m.opposite_quantity)<abs(m.prior_quantity) else 'above',
             one_base_atomic_close=abs(m.prior_quantity)==(65 if m.underlying=='NIFTY' else 20),old_sign_age_seconds=m.old_sign_age_seconds,neutralization_seconds=m.neutralization_seconds,
             same_parent_at_boundary=boundary_same,parent_partial_fill_present=partial,repeated_request_quantity_and_limit_candidate=same_quantity_limit,close_limit_candidates=';'.join(map(str,sorted({p for q,p in close_signature}))),opposite_limit_candidates=';'.join(map(str,sorted({p for q,p in open_signature}))),close_tag_codes=';'.join(sorted(close_tags)),opposite_tag_codes=';'.join(sorted(open_tags)),neutral_tag_codes=';'.join(sorted(neutral_tags)),repeat_requested_quantity_atomic=repeated_payload,repeat_requested_quantity_burst=repeated_burst_payload,same_order_label_minute=same_label,closing_order_labels=';'.join(sorted(closing.order_label_ist.unique())),opposite_order_labels=';'.join(sorted(opening.order_label_ist.unique())),neutral_order_labels=';'.join(sorted(neutral.order_label_ist.unique())),shared_any_closing_parent=bool(all_close_parents&open_parents),
             atomic_close_parent_ids=';'.join(rs[at]['parents']),opposite_parent_ids=';'.join(rs[oi]['parents']),neutral_parent_ids=';'.join(rs[ei]['parents']),
             opposite_requested_quantities=';'.join(map(str,sorted(opening.parent_requested_quantity.unique()))),request_equals_atomic_close=reqeq,
             q_after60=q60,q_after300=q300,next_same_contract_ist=next_contract['timestamp_ist'] if next_contract else '',next_same_contract_quantity=next_contract['after'] if next_contract else np.nan,next_same_right_opening_ist=later_same.timestamp_ist.iloc[0] if len(later_same) else '',next_opposite_right_opening_ist=later_other.timestamp_ist.iloc[0] if len(later_other) else '',opposite_label_before_close_minute=bool(pd.to_datetime(opening.order_label_ist).min()<pd.Timestamp(m.close_to_zero_ist).floor('min')),restores_prior_level_by300=bool(restored),restore_ist=restored,
             new_same_contract_after300=int(contract[contract.second.between(end+1,end+300)].opening_quantity.sum()),
             same_right_opening_after300=int(ff[ff.option_type.eq(m.option_type)&ff.second.between(end+1,end+300)].opening_quantity.sum()),
             opposite_right_opening_after300=int(ff[ff.option_type.ne(m.option_type)&ff.second.between(end+1,end+300)].opening_quantity.sum()),
             paired_rotation_compatible=bool(pure_rotation),nearby_same_strike_short_pairs=';'.join(map(str,paired_strikes)),scheduled_pair_compatible=scheduled_pair,rotation_candidate_sources=';'.join(map(str,rotation.source_row)),
             spot_pre=pre[0],option_pre=pre[1],spot_post60=post1[0],option_post60=post1[1],spot_post300=post5[0],option_post300=post5[1],
             spot_prior5min_change_pct=100*(pre[0]/before5[0]-1) if before5[0]>0 else np.nan,
             spot_after5min_change_pct=100*(post5[0]/pre[0]-1) if pre[0]>0 else np.nan,
             option_after5min_change_pct=100*(post5[1]/pre[1]-1) if pre[1]>0 else np.nan,
             opposite_roundtrip_gross=gross,opposite_roundtrip_cost_proxy=.0025*turn+20*parents+.05*opposite.incremental_quantity.sum(),
             near_short_book_flat=bool(m.near_short_book_flat),source_event_ids=';'.join(map(str,source_ids)),
             timestamp_flag='export event seconds; exchange matching semantics unverified',intent_status='unidentified')
        ledger.append(row)
        for r in seq.itertuples():
            child=r._asdict();child.update(motif_id=mid,raw_ref_column3=rawrefs[r.source_row][0],raw_ref_column4=rawrefs[r.source_row][1],raw_limit_price_candidate=rawrefs[r.source_row][2],raw_remaining_quantity=rawrefs[r.source_row][3],raw_fill_status=rawrefs[r.source_row][4],raw_event_reference_candidate=rawrefs[r.source_row][5],uninterpreted_tag_code=tag_codes[rawrefs[r.source_row][6]],
                  role_in_motif='closing_burst' if r.second<=close else 'opposite_open_or_neutralisation',atomic_state_is_net_of_same_second=True)
            children.append(child)
        for t in range(start-1,end+61):
            a=[r for r in rs if r['t']==t]
            timeline.append(dict(motif_id=mid,timestamp_ist=iso(t),quantity_before=qty_at(rs,t-1),quantity_after=qty_at(rs,t),
               source_rows=';'.join(str(s) for x in a for s in x['sources']),parent_ids=';'.join(p for x in a for p in x['parents']),has_fill=bool(a)))
        for r in ff[ff.second.between(start-60,end+900)].itertuples():
            neighbors.append(dict(motif_id=mid,source_row=r.source_row,timestamp_ist=r.timestamp_ist,parent_id=r.parent_id,strike=r.strike,option_type=r.option_type,side=r.side,
               incremental_quantity=r.incremental_quantity,opening_quantity=r.opening_quantity,closing_quantity=r.closing_quantity,
               relation='same_contract' if r.strike==m.strike and r.option_type==m.option_type else 'same_right' if r.option_type==m.option_type else 'opposite_right'))
        # Nonexclusive observable implications, not a forced classification of intent.
        variants=[('A_duplicate_stale_close','two_distinct_parent_full_atomic_duplicate',eq and not boundary_same,boundary_same or not eq,'same grouped parent contradicts two-distinct-parent variant; equality also selected by size restriction'),
                  ('A_duplicate_stale_close','distinct_parent_requested_quantity_repeats',repeated_payload,not repeated_payload,'same instrument/direction follows from reversal; repeated requested size is compatible with stale requests or deliberate trades, not proof of duplicate intent'),
                  ('A_duplicate_stale_close','distinct_parent_size_and_limit_candidate_repeat',same_quantity_limit,not same_quantity_limit,'limit field semantics are inferred from fill bounds; same payload can reflect distinct policy instructions, repricing/retry or a duplicate'),
                  ('B_intentional_rotation','persistent_opposite_exposure_at5min',q300*m.prior_quantity<0,q300*m.prior_quantity>=0,'short-lived round trips remain possible; initial <=60sec flattening is selected'),
                  ('B_intentional_rotation','nearby_paired_shorts_at_prior_clock_label',scheduled_pair,False,'time/strike association permits an allocation or rotation explanation; labels are not confirmed submission timestamps and allocation IDs are missing'),
                  ('C_target_synchronisation','zero_target_correction_within5sec',m.neutralization_seconds<=5,m.neutralization_seconds>5,'zero target is latent; <=60sec correction is imposed by cohort'),
                  ('D_protective_adjustment','old_long_and_near_equal_new_long',pure_rotation,m.prior_quantity<0,'strict pure-rotation variant excludes nearby shorts, including a possible overshoot; lack of compatibility does not rule out mixed hedge adjustment and execution effects'),
                  ('E_partial_or_ordering','one_grouped_parent_spans_flat_boundary',boundary_same,not boundary_same,'supports a received parent spanning zero; not direct submission/cancellation evidence'),
                  ('E_partial_or_ordering','multiple_child_fills_in_involved_parent',partial,not partial,'observed fragmentation can coexist with repeated requests; it does not identify the reason for the opposite order'),
                  ('F_other_unresolved','unique_cause_identification',False,False,'all intents unconfirmed; A-E compatibility can overlap')]
        for label,variant,support,contradiction,limit in variants:
            hyp.append(dict(motif_id=mid,hypothesis=label,variant=variant,status='compatible' if support else 'contradicted_variant' if contradiction else 'unresolved',
                direct_submission_evidence=False,limitation=limit))
    ledger=pd.DataFrame(ledger);ledger.to_csv(HERE/'reversal_motif_ledger.csv',index=False)
    pd.DataFrame(children).to_csv(HERE/'reversal_child_fills.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(timeline).to_csv(HERE/'reversal_second_timelines.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(neighbors).to_csv(HERE/'reversal_neighbor_activity.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    hypotheses=pd.DataFrame(hyp);hypotheses.to_csv(HERE/'reversal_hypothesis_scores.csv',index=False)
    hypotheses.groupby(['hypothesis','variant','status']).size().rename('motifs').reset_index().to_csv(HERE/'reversal_hypothesis_summary.csv',index=False)
    casekeys={(r.underlying,r.expiry_date,int(r.strike),r.option_type,r.first_close_to_zero_ist):r.motif_id for r in ledger.itertuples()}
    controls['motif_id']=[casekeys.get((r.underlying,r.expiry_date,r.strike,r.option_type,r.close_ist),'') for r in controls.itertuples()]
    controls.to_csv(HERE/'all_closure_controls.csv',index=False)
    summaries=[]
    for capped in [False,True]:
        d=controls[controls.reopen_within10]
        if capped:d=d[d.bounded_peak.eq(True)]
        for size in ['all','one_base','multiple_base']:
            q=d if size=='all' else d[d.closed_base_units.eq(1)] if size=='one_base' else d[d.closed_base_units.gt(1)]
            for label,g in [('fixed_motifs',q[q.motif_id.ne('')]),('non_motif_controls',q[q.motif_id.eq('')]),('strict_nonreversal_controls',q[q.motif_id.eq('')&q.reopening_opposite.eq(False)])]:
                summaries.append(dict(bounded_peak=capped,size=size,cohort=label,cases=len(g),cycles=g[['underlying','expiry_date']].drop_duplicates().shape[0],equal=int(g.quantity_equal.eq(True).sum()),rate=float(g.quantity_equal.eq(True).mean()) if len(g) else np.nan))
    pd.DataFrame(summaries).to_csv(HERE/'quantity_equality_controls.csv',index=False)
    matched=[];used=set();pool=controls[controls.motif_id.eq('')&controls.reopen_within10&controls.bounded_peak.eq(True)&controls.reopening_opposite.eq(False)]
    for case in controls[controls.motif_id.ne('')].sort_values('close_ist').itertuples():
        g=pool[pool.underlying.eq(case.underlying)&pool.expiry_date.eq(case.expiry_date)&pool.phase.eq(case.phase)&pool.old_role.eq(case.old_role)&pool.closed_quantity.eq(case.closed_quantity)&~pool.sequence_id.isin(used)].copy()
        g['distance']=(pd.to_datetime(g.close_ist,utc=True)-pd.Timestamp(case.close_ist).tz_convert('UTC')).abs().dt.total_seconds()
        for r in g.sort_values(['distance','sequence_id']).head(3).itertuples():
            matched.append(dict(motif_id=case.motif_id,control_id=r.sequence_id,underlying=case.underlying,expiry_date=case.expiry_date,closed_base_units=case.closed_base_units,
                case_equal=case.quantity_equal,control_equal=r.quantity_equal,time_distance_seconds=r.distance,old_role=case.old_role,phase=case.phase))
            used.add(r.sequence_id)
    pd.DataFrame(matched,columns=['motif_id','control_id','underlying','expiry_date','closed_base_units','case_equal','control_equal','time_distance_seconds','old_role','phase']).to_csv(HERE/'matched_nonreversal_controls.csv',index=False)
    summary=dict(motifs=59,source_sha256=fingerprint,atomic_equal=int(ledger.atomic_quantity_equal.sum()),burst_equal=int(ledger.burst_quantity_equal.sum()),
        one_base=int(ledger.one_base_atomic_close.sum()),partial_parent_cases=int(ledger.parent_partial_fill_present.sum()),same_parent_boundary=int(ledger.same_parent_at_boundary.sum()),all_old_closures=len(controls),reopened10=int(controls.reopen_within10.sum()),
        matched_case_count=len({r['motif_id'] for r in matched}),matched_controls=len(matched),source_event_ids_immutable=True,
        interpretation='compatibility is not intent probability; original <=size and <=60sec selection acknowledged')
    (HERE/'forensic_manifest.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':run()
