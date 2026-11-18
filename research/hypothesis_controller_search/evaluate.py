"""Top-cohort mismatch, path, ablation, uncertainty and identifiability audits."""
from __future__ import annotations
import argparse,gzip,hashlib,itertools,json,subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from prepare import HERE,ROOT,OUT,CACHE,ROLES,SLOTS,mode
from search import WEIGHTS,base_config,key,registry,write_kernel_configs,with_metrics,complexity

ACTIONS=['new_short','short_cover','wing_buy','wing_sell']
REASONS={1:'scheduled allocation',2:'side/contract stop',4:'portfolio stop',8:'cooldown re-entry',16:'final deadline',32:'wing decay refresh'}


def matched_actions(pred,actual,tolerance=2):
    """Chronological max-cardinality exact-instrument/action match, not nearest reuse."""
    groups=defaultdict(list)
    for index,row in enumerate(actual):groups[(row['strike'],row['right'],row['action'])].append(index)
    cursor=defaultdict(int);pairs=[];used=set()
    for pi,p in enumerate(pred):
        g=(p['strike'],p['right'],p['action']);choices=groups[g];where=cursor[g]
        while where<len(choices) and actual[choices[where]]['minute']<p['minute']-tolerance:where+=1
        if where<len(choices) and actual[choices[where]]['minute']<=p['minute']+tolerance:
            ai=choices[where];pairs.append((pi,ai));used.add(ai);where+=1
        cursor[g]=where
    matched_pred={p for p,a in pairs}
    return pairs,[i for i in range(len(pred)) if i not in matched_pred],[i for i in range(len(actual)) if i not in used]


def timestamp(minute):return pd.Timestamp(int(minute),unit='m',tz='UTC').tz_convert('Asia/Kolkata').isoformat()

def observed_actions():
    f=pd.read_csv(OUT/'canonical_events.csv.gz');meta=json.loads((OUT/'cycle_metadata.json').read_text());mapping={(c['underlying'],c['expiry_date']):c['cycle_id'] for c in meta}
    rows=[]
    for row in f.itertuples():
        common=dict(cycle_id=mapping[(row.underlying,row.expiry_date)],minute=int(pd.Timestamp(row.timestamp_ist).timestamp()//60),strike=row.strike,right=int(row.option_type=='PE'))
        if row.opening_quantity:rows.append(dict(common,action=0 if row.side=='Sell' else 2,quantity=row.opening_quantity))
        if row.closing_quantity:rows.append(dict(common,action=1 if row.side=='Buy' else 3,quantity=row.closing_quantity))
    return pd.DataFrame(rows).groupby(['cycle_id','minute','strike','right','action'],sort=True).quantity.sum().reset_index()


def decode_book(value):
    return {(int(k),int(r)):int(q) for part in value[1:-1].split(';') if part for k,r,q in [part.split(':')]}


def diagnostics():
    manifest=json.loads((OUT/'search_manifest.json').read_text());best=manifest['best_candidate_id'];ids=manifest['trace_candidate_ids']
    registry_df=pd.read_csv(OUT/'candidate_registry.csv');configs={int(r.candidate_id):dict(json.loads(r.configuration),id=int(r.candidate_id)) for r in registry_df.itertuples()}
    meta=json.loads((OUT/'cycle_metadata.json').read_text());scores=pd.read_csv(OUT/'candidate_scores.csv');cycles=pd.read_csv(OUT/'cycle_scores.csv.gz',dtype={'prediction_hash':str})
    actual=observed_actions();actual.to_csv(OUT/'observed_action_targets.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pred=pd.read_csv(OUT/'replay_predictions.csv.gz');inventory=pd.read_csv(OUT/'inventory_replay.csv.gz')
    actual_groups={int(cid):g.to_dict('records') for cid,g in actual.groupby('cycle_id')};mismatches=[];robust=[];quality=[]
    pred_groups={k:g for k,g in pred.groupby(['candidate_id','cycle_id'])}
    for candidate,cid in itertools.product(ids,range(len(meta))):
        g=pred_groups.get((candidate,cid),pred.iloc[:0])
        ps=g.sort_values(['minute','strike','right','action']).to_dict('records');aa=actual_groups[cid]
        # Kernel loops contracts sorted strike/right, then action: matches this ordering.
        for tol in [0,1,2]:
            pairs,extras,misses=matched_actions(ps,aa,tol)
            for action in range(4):
                pp=sum(p['action']==action for p in ps);a=sum(v['action']==action for v in aa);mm=sum(ps[p]['action']==action for p,q in pairs)
                robust.append(dict(candidate_id=candidate,cycle_id=cid,index=meta[cid]['underlying'],expiry_date=meta[cid]['expiry_date'],split=meta[cid]['split'],tolerance_minutes=tol,action=ACTIONS[action],predicted=pp,actual=a,matched=mm,precision=mm/pp if pp else np.nan,recall=mm/a if a else np.nan,f1=2*mm/(pp+a) if pp+a else np.nan))
            if tol!=2:continue
            for pi,ai in pairs:
                p,a=ps[pi],aa[ai];kind='mis_sized' if p['quantity']!=a['quantity'] else 'mis_timed' if p['minute']!=a['minute'] else None
                if kind:mismatches.append(dict(candidate_id=candidate,cycle_id=cid,kind=kind,predicted_time_ist=timestamp(p['minute']),actual_time_ist=timestamp(a['minute']),strike=p['strike'],right=p['right'],action=ACTIONS[p['action']],predicted_quantity=p['quantity'],actual_quantity=a['quantity'],timing_error_minutes=p['minute']-a['minute'],reason_mask=p['reason_mask']))
            for pi in extras:
                p=ps[pi];mismatches.append(dict(candidate_id=candidate,cycle_id=cid,kind='extra_action',predicted_time_ist=timestamp(p['minute']),actual_time_ist='',strike=p['strike'],right=p['right'],action=ACTIONS[p['action']],predicted_quantity=p['quantity'],actual_quantity=0,timing_error_minutes=np.nan,reason_mask=p['reason_mask']))
            for ai in misses:
                a=aa[ai];mismatches.append(dict(candidate_id=candidate,cycle_id=cid,kind='missed_action',predicted_time_ist='',actual_time_ist=timestamp(a['minute']),strike=a['strike'],right=a['right'],action=ACTIONS[a['action']],predicted_quantity=0,actual_quantity=a['quantity'],timing_error_minutes=np.nan,reason_mask=0))
        c=np.load(CACHE/f'cycle_{cid:02}.npz');lookup={(int(k),int(r)):j for j,(k,r) in enumerate(zip(c['strikes'],c['rights']))};tlookup={t:i for i,t in enumerate(c['minutes'])}
        prior_quotes=c['previous'];prior_volumes=c['previous_volume'];c.close()
        prior_missing=0;zero_volume=0;path=inventory[(inventory.candidate_id==candidate)&(inventory.cycle_id==cid)]
        for row in path.itertuples():
            t=tlookup[row.minute];book=decode_book(row.simulated_book)
            for contract,q in book.items():
                j=lookup[contract]
                prior_missing+=not np.isfinite(prior_quotes[t,j])
                zero_volume+=not(prior_volumes[t,j]>0)
        expected=cycles[(cycles.candidate_id==candidate)&(cycles.cycle_id==cid)&(cycles.phase==2)].iloc[0]
        assert int(expected.pred0+expected.pred1+expected.pred2+expected.pred3)==len(ps)
        assert np.isclose(expected.match0+expected.match1+expected.match2+expected.match3,sum(r['matched'] for r in robust if r['candidate_id']==candidate and r['cycle_id']==cid and r['tolerance_minutes']==2))
        quality.append(dict(candidate_id=candidate,cycle_id=cid,index=meta[cid]['underlying'],split=meta[cid]['split'],predicted_actions=len(ps),missing_prior_held_quote_cells=prior_missing,nonpositive_prior_volume_cells=zero_volume,
              nonpositive_execution_volume_actions=int((g.execution_bar_volume.fillna(0)<=0).sum()),strict_cycle_valid=prior_missing==0 and zero_volume==0 and (g.execution_bar_volume>0).all()))
    pd.DataFrame(mismatches).to_csv(OUT/'event_mismatch_ledger.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(robust).to_csv(OUT/'timestamp_tolerance_scores.csv',index=False)
    pd.DataFrame(quality).to_csv(OUT/'quote_quality_by_cycle.csv',index=False)
    # Autonomous initial-opening comparison, separately from teacher-forced priors.
    opening=[]
    for candidate in ids:
        for c in meta:
            day=c['dates'][0];start=pd.Timestamp(day+' 09:15',tz='Asia/Kolkata').timestamp()//60
            p=pred[(pred.candidate_id==candidate)&(pred.cycle_id==c['cycle_id'])&pred.minute.ge(start)&pred.minute.lt(start+3)]
            a=actual[(actual.cycle_id==c['cycle_id'])&actual.minute.ge(start)&actual.minute.lt(start+3)]
            extra={}
            for action,label in [(0,'short'),(2,'wing')]:
                for right,right_label in [(0,'CE'),(1,'PE')]:
                    pp=p[p.action.eq(action)&p.right.eq(right)].sort_values('minute');aa=a[a.action.eq(action)&a.right.eq(right)].sort_values('minute')
                    extra[f'predicted_first_{right_label}_{label}_strike']=int(pp.iloc[0].strike) if len(pp) else np.nan
                    extra[f'observed_first_{right_label}_{label}_strike']=int(aa.iloc[0].strike) if len(aa) else np.nan
                    extra[f'predicted_{right_label}_{label}_quantity']=int(pp.quantity.sum())
                    extra[f'observed_{right_label}_{label}_quantity']=int(aa.quantity.sum())
            opening.append(dict(candidate_id=candidate,cycle_id=c['cycle_id'],index=c['underlying'],split=c['split'],first_received_phase='preexpiry' if day<c['expiry_date'] else 'expiry',
                predicted_short_quantity=int(p[p.action.eq(0)].quantity.sum()),observed_short_quantity=int(a[a.action.eq(0)].quantity.sum()),
                predicted_strikes=';'.join(map(str,sorted(p[p.action.eq(0)].strike.unique()))),observed_strikes=';'.join(map(str,sorted(a[a.action.eq(0)].strike.unique()))),eligibility='unknown outside received sessions',window='09:15 inclusive to 09:18 exclusive; gross actions, not 09:17 net snapshot',**extra))
    pd.DataFrame(opening).to_csv(OUT/'initial_entry_reconstruction.csv',index=False)
    intermediate=[]
    for candidate,cid in itertools.product(ids,range(len(meta))):
        p=pred_groups.get((candidate,cid),pred.iloc[:0]);aa=pd.DataFrame(actual_groups[cid])
        def clock_minutes(frame):return pd.to_datetime(frame.minute,unit='m',utc=True).dt.tz_convert('Asia/Kolkata').dt.hour*60+pd.to_datetime(frame.minute,unit='m',utc=True).dt.tz_convert('Asia/Kolkata').dt.minute
        for ph in ['preexpiry','expiry']:
            pday=pd.to_datetime(p.minute,unit='m',utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%Y-%m-%d');aday=pd.to_datetime(aa.minute,unit='m',utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%Y-%m-%d')
            pp=p[p.action.eq(1)&clock_minutes(p).lt(900)&(pday.lt(meta[cid]['expiry_date']) if ph=='preexpiry' else pday.eq(meta[cid]['expiry_date']))]
            a=aa[aa.action.eq(1)&clock_minutes(aa).lt(900)&(aday.lt(meta[cid]['expiry_date']) if ph=='preexpiry' else aday.eq(meta[cid]['expiry_date']))]
            pairs,extra,miss=matched_actions(pp.to_dict('records'),a.to_dict('records'),2)
            intermediate.append(dict(candidate_id=candidate,cycle_id=cid,index=meta[cid]['underlying'],split=meta[cid]['split'],phase=ph,predicted=len(pp),actual=len(a),matched=len(pairs),false_actions=len(extra),missed_actions=len(miss)))
    pd.DataFrame(intermediate).to_csv(OUT/'intermediate_cover_scores.csv',index=False)
    # Top-cohort action equality and overlap; same full action path implies same inventory.
    sets={i:{tuple(row) for row in pred[pred.candidate_id==i][['cycle_id','minute','strike','right','action','quantity']].itertuples(index=False,name=None)} for i in ids}
    equivalent=[]
    for a,b in itertools.combinations(ids,2):
        x,y=sets[a],sets[b];overlap=len(x&y)
        equivalent.append(dict(candidate_a=a,candidate_b=b,exact_same_trace=x==y,exact_action_overlap_dice=2*overlap/(len(x)+len(y)) if x or y else 1,disagreeing_actions=len(x^y)))
    pd.DataFrame(equivalent).to_csv(OUT/'top_candidate_equivalence.csv',index=False)
    aug=scores[(scores.split==1)&(scores.phase==2)&scores.candidate_id.isin(ids)].sort_values('primary_score',ascending=False)
    alternate=next((int(i) for i in aug.candidate_id if i!=best and sets[i]!=sets[best]),0)
    discriminating=[]
    for cid,minute in sorted({(x[0],x[1]) for x in sets[best]^sets[alternate]},key=lambda x:(meta[x[0]]['expiry_date'],x[1]))[:24]:
        def describe(i):
            q=pred[(pred.candidate_id==i)&(pred.cycle_id==cid)&(pred.minute==minute)]
            return '; '.join(f'{ACTIONS[r.action]} {r.strike}{["CE","PE"][r.right]} qty={r.quantity} [{"+".join(name for bit,name in REASONS.items() if r.reason_mask&bit)}]' for r in q.itertuples()) or 'no action'
        observed=actual[(actual.cycle_id==cid)&actual.minute.between(minute-2,minute+2)]
        prior=inventory[(inventory.candidate_id==best)&(inventory.cycle_id==cid)&inventory.minute.lt(minute)].tail(1)
        discriminating.append(dict(candidate_a=best,candidate_b=alternate,index=meta[cid]['underlying'],expiry_date=meta[cid]['expiry_date'],timestamp_ist=timestamp(minute),
            controller_a=describe(best),controller_b=describe(alternate),observed_within2min='; '.join(f'{ACTIONS[r.action]} {r.strike}{["CE","PE"][r.right]} qty={r.quantity} at {timestamp(r.minute)}' for r in observed.itertuples()) or 'no recorded action',
            a_prior_simulated_equity=float(prior.marked_equity.iloc[0]) if len(prior) else 0.,a_prior_simulated_book=prior.simulated_book.iloc[0] if len(prior) else '[]',
            observable='execution contrast observable subject to missing quotes; original decision cause unobserved',missing_evidence='submission/cancel/ack times, strategy IDs, tick quotes and account state'))
    pd.DataFrame(discriminating).to_csv(OUT/'discriminating_events.csv',index=False)
    # Frozen best-v-baseline paired cycle uncertainty, never fill-level binomial CIs.
    rng=np.random.default_rng(803);uncertainty=[]
    for baseline in [0,16,2320]:
      for sp in range(3):
        for index in ['pooled',0,1]:
            d=cycles[(cycles.split==sp)&(cycles.phase==2)&cycles.candidate_id.isin([best,baseline])]
            if index!='pooled':d=d[d['index']==index]
            for metric in ['primary_score','primary_raw','event_macro_f1','quantity_score','inventory_score']:
                pair=d.pivot(index='cycle_id',columns='candidate_id',values=metric).dropna();delta=(pair[best]-pair[baseline]).to_numpy()
                boot=delta[rng.integers(0,len(delta),(2000,len(delta)))].mean(axis=1)
                uncertainty.append(dict(baseline_id=baseline,split=sp,index=index,metric=metric,cycles=len(delta),mean_difference=float(delta.mean()),low95=float(np.quantile(boot,.025)),high95=float(np.quantile(boot,.975))))
    pd.DataFrame(uncertainty).to_csv(OUT/'cycle_uncertainty.csv',index=False)
    # Conditional processing model: no observed-close timestamps are fed to autonomous search.
    motifs=pd.read_csv(ROOT/'research/outputs/playbook_rapid_reversal_motifs.csv');m=motifs[motifs.conservative_candidate]
    mechanics=[]
    for r in m.itertuples():mechanics.append(dict(index=r.underlying,expiry_date=r.expiry_date,close_ist=r.close_to_zero_ist,opposite_open_ist=r.opposite_open_ist,neutralized_ist=r.neutralized_ist,
        prior_quantity=r.prior_quantity,observed_opposite=r.opposite_quantity,stale_full_duplicate_prediction=-r.prior_quantity,idempotent_target_prediction=0,
        exact_full_duplicate_quantity=(-r.prior_quantity)==r.opposite_quantity,peak_within_prior=abs(r.peak_opposite_quantity)<=abs(r.prior_quantity),
        status='conditional on observed liquidation, not autonomous cause prediction; no submission/cancellation evidence'))
    pd.DataFrame(mechanics).to_csv(OUT/'order_mechanics_diagnostic.csv',index=False)
    # Best August champion in each component family, with later metrics carried along.
    components=[]
    for family in ['allocation','exit','gate','wing','reentry','final','reference']:
        for value,group in registry_df.groupby(family):
            eligible=scores[(scores.split==1)&(scores.phase==2)&scores.candidate_id.isin(group.candidate_id)]
            row=eligible.sort_values(['primary_score','complexity','candidate_id'],ascending=[False,True,True]).iloc[0];cid=int(row.candidate_id)
            for r in scores[(scores.phase==2)&(scores.candidate_id==cid)].to_dict('records'):components.append(dict(family=family,value=value,**r))
    pd.DataFrame(components).to_csv(OUT/'component_champions.csv',index=False)
    # Paired gate ablation on main-bank candidate best in August, no other parameters changed.
    main=registry_df[registry_df.stage.ne('local_refinement')];main_best=int(scores[(scores.split==1)&(scores.phase==2)&scores.candidate_id.isin(main.candidate_id)].sort_values('primary_score',ascending=False).iloc[0].candidate_id)
    keymap={key(c):cid for cid,c in configs.items()};ablation=[]
    for gate in range(3):
        c=dict(configs[main_best],gate=gate);cid=keymap[key(c)]
        for r in scores[(scores.candidate_id==cid)&scores.phase.eq(2)].to_dict('records'):ablation.append(dict(gate=['none','range','efficiency'][gate],**r))
    pd.DataFrame(ablation).to_csv(OUT/'market_gate_ablation.csv',index=False)
    # Economics is diagnostic and only for the predefined top cohort.
    economic=cycles[cycles.candidate_id.isin(ids)&cycles.phase.eq(2)].copy()
    economic['gross_pnl']=economic.final_equity;economic['net_pnl']=economic.gross_pnl-economic.cost
    economic['high_cost_net']=economic.net_pnl-.0025*economic.turnover
    economic['valuation_status']=np.where(economic.gross_pnl.isna(),'unavailable final mark','preceding-candle mark, not settlement')
    economic.to_csv(OUT/'economic_diagnostics.csv',index=False)
    # Strict quote screen requires equal compared-cycle support, not favored per-policy exclusions.
    quality=pd.DataFrame(quality);strict=[]
    for sp in ['fit_Jun_Jul','validation_Aug','later_Sep_Oct']:
        q=quality[quality.split==sp];valid=set(q[q.strict_cycle_valid].cycle_id)&set(q[q.candidate_id==0].cycle_id)&set(q[q.candidate_id==best].cycle_id)
        a=set(q[(q.candidate_id==0)&q.strict_cycle_valid&q.predicted_actions.gt(0)].cycle_id);b=set(q[(q.candidate_id==best)&q.strict_cycle_valid&q.predicted_actions.gt(0)].cycle_id);valid=a&b
        for candidate in [0,best]:
            d=economic[economic.candidate_id.eq(candidate)&economic.cycle_id.isin(valid)]
            strict.append(dict(split=sp,candidate_id=candidate,common_strict_cycles=len(d),net_sum=d.net_pnl.sum(min_count=1),definition='both policies traded; all held prior quotes and prior volumes positive; all execution-bar volumes positive; ex-post quality cohort'))
    pd.DataFrame(strict).to_csv(OUT/'strict_quote_sensitivity.csv',index=False)
    print('Top traces reconciled; mismatches',len(mismatches),'best',best,'competing controller',alternate)


if __name__=='__main__':diagnostics()
