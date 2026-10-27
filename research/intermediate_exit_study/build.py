"""Strict pre-event book reconstruction and fixed exit/control cohorts."""
from __future__ import annotations
import hashlib,json,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SOURCE=ROOT/'research/outputs'
PRIOR=ROOT/'research/policy_execution_separation'
sys.path.insert(0,str(PRIOR))
from replay_inputs import market_cache
META=json.loads((ROOT/'research/hypothesis_controller_search/outputs/cycle_metadata.json').read_text())
CID={(m['underlying'],m['expiry_date']):m['cycle_id'] for m in META}
CAPITAL=20_000_000

def iso(s):return pd.Timestamp(int(s),unit='s',tz='UTC').tz_convert('Asia/Kolkata').isoformat()
def sec(s):return int(pd.Timestamp(s).timestamp())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(df,name):
    opts={'compression':{'method':'gzip','mtime':0,'compresslevel':3}} if name.endswith('.gz') else {}
    df.to_csv(HERE/name,index=False,**opts)
def load_fills():
    f=pd.read_csv(SOURCE/'playbook_fill_ledger.csv.gz');f['second']=pd.to_datetime(f.timestamp_ist).astype('int64')//10**9
    f['cycle_id']=[CID[x] for x in zip(f.underlying,f.expiry_date)]
    return f.sort_values(['cycle_id','second','source_row'])

def make_events(f):
    """Outcome strata may use future received records; features must not."""
    buys=f[(f.side=='Buy')&f.closing_quantity.gt(0)]
    atoms=[]
    for (cid,k,r,t),g in buys.groupby(['cycle_id','strike','option_type','second'],sort=True):
        allc=f[(f.cycle_id==cid)&(f.strike==k)&(f.option_type==r)&(f.second==t)]
        meta=META[cid];side=f[(f.cycle_id==cid)&(f.option_type==r)]
        opens=side[(side.side=='Sell')&side.opening_quantity.gt(0)]
        last_open=int(opens.second.max()) if len(opens) else -1
        end=side.sort_values(['second','source_row']).groupby('strike').tail(1)
        ends_flat=not (end.quantity_after<0).any()
        final=iso(t)[:10]==meta['expiry_date'] and iso(t)[11:16]>='15:00' and t>last_open and ends_flat
        atoms.append(dict(atom_id=f'A{len(atoms)+1:05}',cycle_id=cid,underlying=meta['underlying'],expiry_date=meta['expiry_date'],
            strike=int(k),option_type=r,second=int(t),timestamp_ist=iso(t),phase='expiry' if iso(t)[:10]==meta['expiry_date'] else 'preexpiry',
            quantity_before=int(allc.quantity_before.iloc[0]),quantity_after=int(allc.quantity_after.iloc[-1]),cover_quantity=int(g.closing_quantity.sum()),
            gross_buy_quantity=int(g.incremental_quantity.sum()),source_rows=';'.join(map(str,g.source_row)),parent_ids=';'.join(sorted(g.parent_id.unique())),
            child_count=len(g),outcome_stratum='final_liquidation' if final else 'intermediate',
            known_initialization=meta['dates'][0]<meta['expiry_date'],tie_sensitive=bool(allc.tie_sensitive_role.any()),
            last_received_side_open=iso(last_open),received_side_ends_short_flat=ends_flat))
    a=pd.DataFrame(atoms);episodes=[];mapping=[]
    openings={(cid,k,r):g.second.to_numpy() for (cid,k,r),g in f[(f.side=='Sell')&f.opening_quantity.gt(0)].groupby(['cycle_id','strike','option_type'])}
    for key,g in a.groupby(['cycle_id','strike','option_type'],sort=True):
        batch=[];prev=None;ops=openings.get(key,np.array([]))
        def flush():
            if not batch:return
            first,last=batch[0],batch[-1];eid=f'E{len(episodes)+1:05}'
            row=dict(first);row.pop('atom_id');row.update(event_id=eid,last_second=last['second'],last_fill_ist=last['timestamp_ist'],
                duration_seconds=last['second']-first['second'],cover_quantity=sum(x['cover_quantity'] for x in batch),
                quantity_after=last['quantity_after'],atom_count=len(batch),child_count=sum(x['child_count'] for x in batch),
                source_rows=';'.join(x['source_rows'] for x in batch),parent_ids=';'.join(sorted({p for x in batch for p in x['parent_ids'].split(';')})),
                tie_sensitive=any(x['tie_sensitive'] for x in batch),full_contract_flat=last['quantity_after']==0)
            episodes.append(row)
            for x in batch:mapping.append((x['atom_id'],eid))
        for r in g.to_dict('records'):
            separated=prev is not None and (r['second']-prev['second']>120 or r['timestamp_ist'][:10]!=prev['timestamp_ist'][:10] or
                r['outcome_stratum']!=prev['outcome_stratum'] or np.any((ops>prev['second'])&(ops<=r['second'])))
            if separated:flush();batch=[]
            batch.append(r);prev=r
        flush()
    mapping=dict(mapping);a['event_id']=a.atom_id.map(mapping)
    e=pd.DataFrame(episodes).sort_values(['cycle_id','second','strike','option_type']).reset_index(drop=True)
    children=buys.merge(a[['cycle_id','strike','option_type','second','atom_id','event_id','outcome_stratum']],on=['cycle_id','strike','option_type','second'],validate='many_to_one')
    save(a,'short_cover_atoms.csv.gz');save(children,'short_cover_children.csv.gz')
    return a,e

class Book:
    def __init__(self,C):
        self.q=np.zeros(C,dtype=int);self.cost=np.zeros(C);self.cash=np.zeros(2);self.epoch={};self.history=defaultdict(list)
        self.fifo=defaultdict(list);self.lifo=defaultdict(list);self.last_side=np.full(2,np.nan)
    def apply(self,r,j,right,spot):
        old=self.q[j];new=int(r.quantity_after);assert old==int(r.quantity_before),(r.source_row,old,r.quantity_before)
        self.cash[right]+=float(r.cash_change);self.q[j]=new;self.cost[j]=float(r.average_cost_after)
        if old>=0 and new<0:self.epoch[j]=r.second;self.history[j]=[];self.fifo[j]=[];self.lifo[j]=[]
        if r.side=='Sell' and r.opening_quantity>0:
            x=dict(t=int(r.second),qty=int(r.opening_quantity),price=float(r.execution_price),spot=spot,source=int(r.source_row),parent=r.parent_id)
            self.history[j].append(x);self.fifo[j].append(x.copy());self.lifo[j].append(x.copy());self.last_side[right]=r.second
        elif r.side=='Buy' and r.closing_quantity>0:
            for lots,lifo in [(self.fifo[j],False),(self.lifo[j],True)]:
                remaining=int(r.closing_quantity)
                while remaining and lots:
                    x=lots[-1 if lifo else 0];part=min(remaining,x['qty']);x['qty']-=part;remaining-=part
                    if x['qty']==0:lots.pop(-1 if lifo else 0)
                assert remaining==0,(r.source_row,remaining)
        if new>=0:
            self.epoch.pop(j,None);self.history.pop(j,None);self.fifo.pop(j,None);self.lifo.pop(j,None)


def snapshots(f,e,motifs):
    risk=[];casefeatures={};motiffeatures={};coverage=[]
    for cid,fs in f.groupby('cycle_id',sort=True):
        meta=META[cid];z=np.load(market_cache()/f'cycle_{cid:02}.npz');z={k:z[k] for k in z.files};T,C=z['observed'].shape
        lookup={(int(k),'PE' if r else 'CE'):j for j,(k,r) in enumerate(zip(z['strikes'],z['rights']))};book=Book(C)
        records=fs.to_dict('records');bysecond=defaultdict(list)
        for r in records:bysecond[int(r['second'])].append(type('Fill',(),r)())
        es=e[e.cycle_id==cid];ms=motifs[motifs.cycle_id==cid]
        eventsat=defaultdict(list);motifsat=defaultdict(list)
        for r in es.itertuples():eventsat[r.second].append(r)
        for r in ms.itertuples():motifsat[sec(r.observed_close_ist)].append(r)
        minutemap={int(m)*60:i for i,m in enumerate(z['minutes'])}
        times=sorted(set(minutemap)|set(bysecond)|set(eventsat)|set(motifsat))
        running_min=np.full(C,np.nan);side_peak=np.full(2,np.nan);last_sources_time=-1;checks=0
        def mark(t,ti):
            price=z['previous'][ti].astype(float);q=book.q;right=z['rights'];eq=np.full(2,np.nan);dd=eq.copy();missing=[]
            for rr in (0,1):
                live=(q!=0)&(right==rr);missing.append(int(np.sum(live&~np.isfinite(price))))
                if not missing[-1]:
                    eq[rr]=book.cash[rr]+np.dot(q[live],price[live]);dd[rr]=max(0,side_peak[rr]-eq[rr]) if np.isfinite(side_peak[rr]) else np.nan
            return price,eq,dd,missing
        def feature(t,ti,j,marks):
            price,eq,dd,missing=marks;rr=int(z['rights'][j]);s=z['feature'][ti,0];p=price[j];cost=book.cost[j];lots=book.fifo[j];history=book.history[j]
            old=book.epoch.get(j,np.nan);age=(t-old)/60 if np.isfinite(old) else np.nan
            # Only completed marks since the epoch contribute to the trailing anchor.
            minimum=running_min[j];past_min=np.nanmin([minimum,p]) if np.isfinite(minimum) or np.isfinite(p) else np.nan
            previous5=ti-5 if ti>=5 and z['minutes'][ti]-z['minutes'][ti-5]==5 else None
            spot5=z['feature'][previous5,0] if previous5 is not None else np.nan
            opt5=z['previous'][previous5,j] if previous5 is not None else np.nan
            iv=z['feature'][ti,6];iv5=z['feature'][previous5,6] if previous5 is not None else np.nan
            def lotcost(ls):return sum(x['qty']*x['price'] for x in ls)/sum(x['qty'] for x in ls) if ls else np.nan
            fifo=lotcost(lots);lifo=lotcost(book.lifo[j]);total=sum(x['qty'] for x in lots)
            entryspot=sum(x['qty']*x['spot'] for x in lots)/total if total and all(np.isfinite(x['spot']) for x in lots) else np.nan
            sign=1 if rr==0 else -1;losses=[100*(p/x['price']-1) for x in lots] if p>0 else []
            longq=int(np.maximum(book.q[z['rights']==rr],0).sum());shortq=int(np.maximum(-book.q[z['rights']==rr],0).sum())
            contract_qty=int(book.q[j]);base=int(z['base']);sample_age=(t//60*60)-60
            return dict(cycle_id=int(cid),underlying=meta['underlying'],expiry_date=meta['expiry_date'],date=iso(t)[:10],phase='expiry' if iso(t)[:10]==meta['expiry_date'] else 'preexpiry',
                strike=int(z['strikes'][j]),option_type='PE' if rr else 'CE',second=int(t),timestamp_ist=iso(t),feature_cutoff_ist=iso(t),
                latest_fill_available_before_ist=iso(last_sources_time) if last_sources_time>=0 else '',market_bar_start_ist=iso(sample_age),market_available_at_ist=iso(sample_age+60),
                known_initialization=meta['dates'][0]<meta['expiry_date'],quantity_before=contract_qty,short_units=max(-contract_qty,0)/base,
                option_mark=p,mark_fresh=bool(np.isfinite(p)),previous_bar_volume=z['previous_volume'][ti,j],spot=s,entry_cost=cost if contract_qty<0 else np.nan,
                premium_loss_pct=100*(p/cost-1) if p>0 and cost>0 and contract_qty<0 else np.nan,
                premium_change5_pct=100*(p/opt5-1) if p>0 and opt5>0 else np.nan,
                trailing_rebound_pct=100*(p/past_min-1) if p>0 and past_min>0 and contract_qty<0 else np.nan,
                epoch_start_ist=iso(old) if np.isfinite(old) else '',age_minutes=age,last_contract_add_seconds=t-history[-1]['t'] if history else np.nan,
                last_side_add_seconds=t-book.last_side[rr] if np.isfinite(book.last_side[rr]) else np.nan,
                epoch_entry_count=len(history),epoch_gross_entry_quantity=sum(x['qty'] for x in history),
                epoch_entry_sources=';'.join(str(x['source']) for x in history),epoch_entry_parents=';'.join(sorted({x['parent'] for x in history})),
                fifo_cost=fifo,lifo_cost=lifo,fifo_max_lot_loss_pct=max(losses,default=np.nan),fifo_min_lot_loss_pct=min(losses,default=np.nan),
                adverse_spot5_pct=sign*100*(s/spot5-1) if s>0 and spot5>0 else np.nan,
                adverse_entry_pct=sign*100*(s/entryspot-1) if s>0 and entryspot>0 else np.nan,
                side_equity_rupees=eq[rr],side_equity_pct=100*eq[rr]/CAPITAL,side_drawdown_rupees=dd[rr],side_drawdown_pct=100*dd[rr]/CAPITAL,
                side_peak_sampled_rupees=side_peak[rr],side_missing_mark_contracts=missing[rr],side_short_quantity=shortq,side_long_quantity=longq,
                protection_deficit_units=(shortq-longq)/base,atm_iv_pct=iv,iv_change5_points=iv-iv5,
                contract_abs_delta=abs(float(z['delta'][ti,j])),contract_gamma=float(z['gamma'][ti,j]),contract_vega_one_point=float(z['vega'][ti,j]),
                relative_strike_grids=(int(z['strikes'][j])-s)/int(z['step']) if s>0 else np.nan,
                clock_minute=int(z['clock'][ti]),time_bin5=int(z['clock'][ti])//5,
                state_information='strictly earlier fills; preceding complete candle',entry_attribution='pooled cost; FIFO/LIFO sensitivities not original ownership')
        for t in times:
            ti=int(np.searchsorted(z['minutes'],t//60));valid=ti<T and int(z['minutes'][ti])==t//60
            if valid and (t in minutemap or t in eventsat or t in motifsat):
                marks=mark(t,ti)
                if t in minutemap:
                    for j in np.flatnonzero(book.q<0):risk.append(feature(t,ti,j,marks))
                for ev in eventsat[t]:casefeatures[ev.event_id]=feature(t,ti,lookup[(ev.strike,ev.option_type)],marks)
                for ev in motifsat[t]:motiffeatures[ev.motif_id]=feature(t,ti,lookup[(ev.strike,ev.right)],marks)
                # Update sampled extrema only after snapshots, using this observed
                # mark and strictly prior inventory. The current mark may itself be
                # a new minimum; feature() includes it causally.
                if t in minutemap:
                    price,eq,dd,_=marks
                    for j in np.flatnonzero(book.q<0):
                        if np.isfinite(price[j]):running_min[j]=min(running_min[j],price[j]) if np.isfinite(running_min[j]) else price[j]
                    for rr in (0,1):
                        if np.isfinite(eq[rr]):side_peak[rr]=max(side_peak[rr],eq[rr]) if np.isfinite(side_peak[rr]) else eq[rr]
            for r in bysecond.get(t,[]):
                j=lookup[(r.strike,r.option_type)];was=book.q[j];spot=float(z['feature'][ti,0]) if valid else np.nan
                book.apply(r,j,int(r.option_type=='PE'),spot)
                if was>=0 or book.q[j]>=0:running_min[j]=np.nan
                last_sources_time=t
            if t in minutemap and valid:
                # At a minute with no later same-minute fills yet, compare the
                # just-applied minute-boundary fills to the prior boundary book.
                pass
        assert np.array_equal(book.q,z['observed'][-1]);assert abs(book.cash.sum()-z['cash'][-1])<1e-5
        coverage.append(dict(cycle_id=cid,underlying=meta['underlying'],expiry_date=meta['expiry_date'],ending_quantity_reconciles=True,ending_cash_reconciles=True,
                             known_initialization=meta['dates'][0]<meta['expiry_date']))
        print('Snapshots',cid,meta['underlying'],meta['expiry_date'],flush=True)
    risk=pd.DataFrame(risk);risk.insert(0,'observation_id',[f'R{i:07}' for i in range(len(risk))])
    features=pd.DataFrame([dict(event_id=k,**v) for k,v in casefeatures.items()]);features=features.drop(columns=['quantity_before','second','timestamp_ist','underlying','expiry_date','strike','option_type','cycle_id','phase','known_initialization'])
    ledger=e.merge(features,on='event_id',validate='one_to_one')
    # Retain the atomic canonical pre-state as outcome/audit, but use snapshot
    # quantity for features. Atomic pre-state is tied to source order convention.
    qmap={k:v['quantity_before'] for k,v in casefeatures.items()};ledger['snapshot_quantity_before']=ledger.event_id.map(qmap)
    save(risk,'pre_event_risk_set.csv.gz');save(ledger,'exit_case_ledger.csv.gz');save(pd.DataFrame(coverage),'book_reconciliation.csv')
    save(pd.DataFrame([dict(motif_id=k,**v) for k,v in motiffeatures.items()]),'motif_pre_event_features.csv')
    return risk,ledger

def audit_upstream(f):
    c=pd.read_csv(PRIOR/'case_policy_execution_localisation.csv');mot=pd.read_csv(PRIOR/'reversal_motif_ledger.csv');c=c.merge(mot[['motif_id','closing_burst_start_ist','closing_burst_initial_quantity']],on='motif_id')
    pf=pd.read_csv(PRIOR/'detailed_fills.csv.gz');pf=pf[pf.model_id==28];goals=pd.read_csv(PRIOR/'detailed_goals.csv.gz');goals=goals[goals.model_id==28]
    rows=[];history=[]
    def decode(x):return {(int(a),int(b)):int(q) for a,b,q in (part.split(':') for part in x.strip('[]').split(';') if part)}
    for r in c.itertuples():
        close=sec(r.observed_close_ist);sign=1 if r.observed_prior_quantity>0 else -1;right=int(r.right=='PE');role='long_protection' if sign>0 else 'short_exposure'
        actual=f[(f.cycle_id==r.cycle_id)&(f.strike==r.strike)&(f.option_type==r.right)&(f.second<close)]
        opened=actual[(actual.side==('Buy' if sign>0 else 'Sell'))&actual.opening_quantity.gt(0)]
        # Active-sign epoch: no historical entry after the most recent flat/opposite.
        boundary=actual[(actual.quantity_after*sign<=0)]
        lower=int(boundary.second.max()) if len(boundary) else -1
        epoch=opened[opened.second>lower];first=int(epoch.second.min()) if len(epoch) else (int(opened.second.min()) if len(opened) else None)
        p=pf[(pf.cycle_id==r.cycle_id)&(pf.second<close)];same=p[(p.strike==r.strike)&(p.right==right)]
        ever_role=bool(((same.quantity_after*sign)>0).any());ever_contract=len(same)>0
        gs=goals[(goals.cycle_id==r.cycle_id)&(goals.second<close)].sort_values('second');target_ever=False
        for g in gs.itertuples():
            q=decode(g.desired_book).get((r.strike,right),0)
            if q*sign>0:target_ever=True
        closest=np.nan;near_sources='';near_strikes='';candidate_entry_time='';matching_entry=False
        if first is not None:
            near=p[(p.side==('Buy' if sign>0 else 'Sell'))&(p.right==right)&(p.second.between(first-120,min(first+120,close-1)))&((p.quantity_after.abs()>p.quantity_before.abs())|(p.quantity_before*p.quantity_after<=0))]
            if len(near):
                closest=int((near.strike-r.strike).abs().min());near_strikes=';'.join(map(str,sorted(near.strike.unique())));candidate_entry_time=iso(int(near.second.min()));matching_entry=bool(near.strike.eq(r.strike).any())
        initialization_known=META[r.cycle_id]['dates'][0]<META[r.cycle_id]['expiry_date']
        same=same.sort_values(['second','request_id'])
        last_same=same.iloc[-1] if len(same) else None
        role_entries=same[(same.side==('Buy' if sign>0 else 'Sell'))&(same.quantity_after*sign>0)&(same.quantity_after.abs()>same.quantity_before.abs())]
        explanation=('opposite_role_still_held_and_targeted' if r.model_confirmed_before_close*sign<0 else
                     'same_role_still_held_and_targeted' if r.model_confirmed_before_close*sign>0 else
                     'initialization_unobserved' if not initialization_known else
                     'same_contract_previously_held_but_already_reduced' if ever_role else
                     'desired_role_seen_but_no_role_fill' if target_ever else
                     'other_strike_near_recorded_entry' if np.isfinite(closest) and closest>0 else
                     'no_same_role_allocation_near_entry')
        rows.append(dict(r._asdict(),observed_role=role,known_initialization=initialization_known,active_epoch_first_entry_ist=iso(first) if first else '',
            active_epoch_open_quantity=int(epoch.opening_quantity.sum()),active_epoch_entry_sources=';'.join(map(str,epoch.source_row)),
            candidate_ever_same_role=ever_role,candidate_ever_contract=ever_contract,candidate_ever_target_role=target_ever,
            candidate_same_strike_entry_near_actual=matching_entry,closest_candidate_entry_strike_gap=closest,candidate_nearby_entry_strikes=near_strikes,
            candidate_nearby_entry_time=candidate_entry_time,upstream_class=explanation,
            candidate_first_role_entry_ist=iso(role_entries.second.min()) if len(role_entries) else '',
            candidate_last_same_fill_ist=iso(last_same.second) if last_same is not None else '',
            candidate_last_same_fill_side=last_same.side if last_same is not None else '',
            candidate_last_same_fill_reason=int(last_same.reason) if last_same is not None else np.nan,
            candidate_last_same_fill_quantity_after=int(last_same.quantity_after) if last_same is not None else np.nan,
            baseline_immutable=True,explanation_status='observable divergence, not proof of original intention'))
        for a in epoch.itertuples():history.append(dict(motif_id=r.motif_id,observed_role=role,source_row=a.source_row,parent_id=a.parent_id,entry_ist=a.timestamp_ist,
            entry_quantity=a.opening_quantity,strike=a.strike,option_type=a.option_type,price=a.execution_price))
    save(pd.DataFrame(rows),'upstream_32_27_audit.csv');save(pd.DataFrame(history),'motif_active_entry_history.csv')
    return c

def controls(risk,ledger,atoms):
    pool=risk[(risk.clock_minute%5==0)].copy();pool['age_bin']=pd.cut(pool.age_minutes,[-np.inf,15,60,np.inf],labels=[0,1,2]).astype(float)
    pool['allocation_bin']=pd.cut(pool.last_side_add_seconds,[-np.inf,120,600,np.inf],labels=[0,1,2]).astype(float)
    times={(cid,k,r):g.second.to_numpy() for (cid,k,r),g in atoms.groupby(['cycle_id','strike','option_type'])}
    pool['near_cover']=[bool(np.any(np.abs(times.get((x.cycle_id,x.strike,x.option_type),np.array([]))-x.second)<=120)) for x in pool.itertuples()]
    eligible=pool[~pool.near_cover].copy();groups={k:g for k,g in eligible.groupby(['cycle_id','date','option_type'])};used=set();pairs=[];audit=[]
    for e in ledger[ledger.outcome_stratum=='intermediate'].sort_values(['cycle_id','second','strike','option_type']).itertuples():
        p=groups.get((e.cycle_id,e.date,e.option_type),eligible.iloc[:0]);age=0 if e.age_minutes<=15 else 1 if e.age_minutes<=60 else 2
        ab=0 if e.last_side_add_seconds<=120 else 1 if e.last_side_add_seconds<=600 else 2
        q=max(-e.snapshot_quantity_before,0);base=65 if e.underlying=='NIFTY' else 20
        p=p[(p.second-e.second).abs().le(3600)&(p.short_units*base).between(.5*q,2*q)&p.age_bin.eq(age)&p.allocation_bin.eq(ab)]
        primary=p[p.strike.eq(e.strike)];secondary=p[~p.strike.eq(e.strike)&(p.relative_strike_grids-e.relative_strike_grids).abs().le(2)]
        picked=[]
        for tier,g in [('same_contract',primary),('other_strike_secondary',secondary)]:
            g=g.assign(distance=(g.second-e.second).abs()).sort_values(['distance','observation_id'])
            for c in g.itertuples():
                if c.observation_id in used:continue
                used.add(c.observation_id);picked.append(c.observation_id)
                pairs.append(dict(event_id=e.event_id,control_id=c.observation_id,tier=tier,cycle_id=e.cycle_id,underlying=e.underlying,option_type=e.option_type,
                    case_second=e.second,control_second=c.second,time_difference_seconds=c.second-e.second,case_strike=e.strike,control_strike=c.strike,
                    quantity_ratio=c.short_units*base/q,age_bin=age,allocation_bin=ab))
                if len(picked)==2:break
            if len(picked)==2:break
        audit.append(dict(event_id=e.event_id,cycle_id=e.cycle_id,eligible_primary_before_reuse=len(primary),eligible_secondary_before_reuse=len(secondary),matched_controls=len(picked),
            unmatched=len(picked)==0,feature_quantity_valid=q>0))
    pair=pd.DataFrame(pairs);save(pair,'matched_nonexit_controls.csv');save(pd.DataFrame(audit),'control_selection_audit.csv')
    save(pool[['observation_id','cycle_id','strike','option_type','second','near_cover']],'control_pool_audit.csv.gz')
    (HERE/'control_selection_summary.json').write_text(json.dumps(dict(fixed_grid_pool=len(pool),near_cover_excluded=int(pool.near_cover.sum()),eligible_pool=len(eligible),
        matched_pairs=len(pair),unique_controls=pair.control_id.nunique() if len(pair) else 0,cases_with_control=int(sum(x['matched_controls']>0 for x in audit)),cases=len(audit),
        selection='fixed protocol; future cover proximity is outcome-only eligibility, not a trigger feature'),indent=2))

def main():
    f=load_fills();c=audit_upstream(f);a,e=make_events(f);risk,ledger=snapshots(f,e,c);controls(risk,ledger,a)
    hashes={str(p.relative_to(ROOT)):sha(p) for p in [SOURCE/'playbook_fill_ledger.csv.gz',SOURCE/'playbook_event_book.csv.gz',PRIOR/'selected_model_config.yaml',PRIOR/'case_policy_execution_localisation.csv',PRIOR/'reversal_motif_ledger.csv',SOURCE/'playbook_rapid_reversal_motifs.csv',HERE/'REGISTERED_PLAN.md']}
    (HERE/'input_manifest.json').write_text(json.dumps(dict(base_revision='8e32701',inputs_sha256=hashes,fill_count=len(f),buy_closing_children=len(f[(f.side=='Buy')&f.closing_quantity.gt(0)]),
        atomic_short_covers=len(a),episodes=len(e),risk_observations=len(risk),primary_cycles=32,greeks='inherited flat ATM IV surface; approximate; not broker Greeks',
        side_pnl='cash + complete fresh previous-minute marks of both long/short same right; gross of costs',
        sampling='past minute sampled extrema only; not tick high water or full continuous drawdown'),indent=2))
    print('Build complete',len(a),'atoms',len(e),'episodes',len(risk),'opportunities',flush=True)
if __name__=='__main__':main()
