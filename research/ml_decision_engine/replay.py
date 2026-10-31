"""Abstaining hierarchical replay with own confirmed inventory, never actual state."""
from __future__ import annotations
import json
import pickle
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd
from .dataset import HERE, ROOT, CanonicalState, canonical_cache, load_market, ROLES
from .features import WINDOWS, strict_event_matches
from .models import scores


def run_replay(configurations,quantities,predictions,meta,protocol,out):
    sys.path.insert(0,str(ROOT/'research'))
    from reconstruct_operational_book import IndependentBook
    cache=canonical_cache(); market=load_market()
    result=[];fills=[];paths=[];requests=[];coverage=[]
    models={}
    for conf in configurations:
        if conf['feature_set']!='full':continue
        key=(conf['fold'],conf['level'],conf['action'])
        path=out/'selected_model_configurations'/f"fold{conf['fold']}_{conf['level']}_{conf['action']}_full.pkl"
        with path.open('rb') as f:models[key]=(conf,pickle.load(f))
    qs={}
    for conf in quantities:
        with (out/'selected_model_configurations'/conf['model_path']).open('rb') as f:
            qs[(conf['fold'],conf['level'],conf['option_type'],conf['role'])]=(conf,pickle.load(f))
    fold_tests={c['fold']:c['test_cycles'] for c in configurations}
    for fold,test_ids in sorted(fold_tests.items()):
        boundary=min(m['dates'][0] for m in meta if m['cycle_id'] in test_ids)
        approved={}
        for (f,level,action),(conf,model) in models.items():
            if f!=fold:continue
            earlier=predictions[(predictions.fold<fold)&(predictions.feature_set=='full')&
                predictions.level.eq(level)&predictions.action.eq(action)&predictions.expiry_date.astype(str).lt(boundary)]
            s=scores(earlier.target,earlier.prediction) if len(earlier) else dict(precision=0.,recall=0.,actual_events=0)
            supported=conf['replay_eligible'] and earlier.cycle_id.nunique()>=protocol['minimum_target_cycles'] and s['actual_events']>=protocol['minimum_target_events'] and s['precision']>=.75 and s['recall']>=.75
            approved[(level,action)]=supported
            coverage.append(dict(fold=fold,level=level,action=action,approved=bool(supported),prior_test_cycles=earlier.cycle_id.nunique(),
                prior_precision=s['precision'],prior_recall=s['recall'],reason='past OOF support and current inner check required'))
        for cid in test_ids:
            m=next(x for x in meta if x['cycle_id']==cid)
            with np.load(cache/f'cycle_{cid:02}.npz') as a:z={k:a[k] for k in a.files}
            T,C=z['observed'].shape;rr=z['rights'];base=int(z['base'])
            state=CanonicalState(C,rr,base);book=IndependentBook();running_cost=0.;source=0
            previous_signals={};cycle_fills=[];l1=denom=exact=0;failed=0
            def row_at(ti,level,right=None,j=None):
                t=int(z['minutes'][ti])*60
                stamp=pd.Timestamp(t,unit='s',tz='UTC').tz_convert('Asia/Kolkata');day=str(stamp.date());clock=int(z['clock'][ti])
                frame=market.get((m['underlying'],day));mk=frame.loc[stamp].to_dict() if frame is not None and stamp in frame.index else {}
                mk.pop('prior_close_date',None)
                ctx=state.context(z,ti,t)
                row=dict(underlying=m['underlying'],phase='expiry' if day==m['expiry_date'] else 'preexpiry',
                    option_type='BOTH' if right is None else 'PE' if right else 'CE',
                    clock_minute=clock,clock_sin=np.sin(2*np.pi*clock/1440),clock_cos=np.cos(2*np.pi*clock/1440),
                    minute_mod15=clock%15,initial_window=clock in range(555,559),
                    scheduled_window=clock in [570,585,600,615,630,645,660,675,690,705,720,750,810,825,840,855,870],
                    minutes_to_next_quarter=15-clock%15,tau_days=float(z['feature'][ti,7]),
                    atm_iv_pct=float(z['feature'][ti,6]),**ctx,**mk)
                for w in WINDOWS:
                    valid=ti>=w and z['minutes'][ti]-z['minutes'][ti-w]==w and z['session'][ti]==z['session'][ti-w]
                    row[f'iv_change_{w}']=float(z['feature'][ti,6]-z['feature'][ti-w,6]) if valid else np.nan
                row['iv_minus_rv15']=row['atm_iv_pct']-row.get('rv_15',np.nan)*np.sqrt(252*375/15)
                spot=row.get('spot',np.nan)
                atm=int(np.floor(spot/int(z['step'])+.5)*int(z['step'])) if np.isfinite(spot) else None
                for r,name in [(0,'ce'),(1,'pe')]:
                    matches=np.flatnonzero((z['strikes']==atm)&(rr==r)) if atm is not None else []
                    row[f'atm_{name}_premium']=float(z['previous'][ti,matches[0]]) if len(matches) else np.nan
                row['atm_combined_premium']=row['atm_ce_premium']+row['atm_pe_premium']
                if right is not None:row['side_units']=row[('pe' if right else 'ce')+'_short_units']
                if j is not None:
                    p=float(z['previous'][ti,j]);cost=state.cost[j]
                    row.update(contract_units=float(state.q[j]/base),option_mark=p,entry_cost=cost,
                        premium_loss_pct=100*(p/cost-1) if state.q[j]<0 and p>0 and cost>0 else np.nan,
                        premium_capture_pct=100*(1-p/cost) if state.q[j]<0 and p>0 and cost>0 else np.nan,
                        trailing_rebound_pct=100*(p/np.fmin(state.minimum[j],p)-1) if state.q[j]<0 and p>0 and np.isfinite(state.minimum[j]) else np.nan,
                        position_age_minutes=(t-state.epoch[j])/60,since_contract_add_minutes=(t-state.last_add[j])/60,
                        since_contract_close_minutes=(t-state.last_close[j])/60,previous_closed_pnl=state.last_closed_pnl[j],
                        relative_strike_grids=(z['strikes'][j]-row.get('spot',np.nan))/int(z['step']),
                        previous_bar_volume=float(z['previous_volume'][ti,j]),contract_delta=float(z['delta'][ti,j]),
                        contract_gamma=float(z['gamma'][ti,j]),contract_vega=float(z['vega'][ti,j]))
                    for w in WINDOWS:
                        valid=ti>=w and z['minutes'][ti]-z['minutes'][ti-w]==w and z['session'][ti]==z['session'][ti-w]
                        old=z['previous'][ti-w,j] if valid else np.nan
                        row[f'premium_change_{w}']=100*(p/old-1) if p>0 and old>0 else np.nan
                return row
            def probability(level,action,rows,require_approval=True):
                pair=models.get((fold,level,action))
                if pair is None or (require_approval and not approved.get((level,action),False)):
                    return np.zeros(len(rows)),1.1
                conf,model=pair
                frame=pd.DataFrame(rows).reindex(columns=conf['features'])
                return model.predict_proba(frame)[:,1],conf['threshold']
            def amount(level,right,role,row):
                pair=qs.get((fold,level,'PE' if right else 'CE',role))
                if pair is None:return 0
                conf,model=pair
                n=conf['constant'] if model is None else model.predict(pd.DataFrame([row]).reindex(columns=conf['features']))[0]
                return max(0,int(round(float(n))))*base
            def execute(ti,j,signed,action):
                nonlocal failed,source,running_cost
                if signed==0:return
                price=float(z['open'][ti,j]);t=int(z['minutes'][ti])*60
                record=dict(fold=fold,cycle_id=cid,second=t,strike=int(z['strikes'][j]),option_type='PE' if rr[j] else 'CE',
                    signed_quantity=int(signed),action=action,execution='hypothetical minute open',previous_volume=float(z['previous_volume'][ti,j]),
                    execution_volume=float(z['volume'][ti,j]),filled=bool(np.isfinite(price) and price>0),price=price)
                requests.append(record)
                if not record['filled']:failed+=1;return
                # Reuse the established Decimal accounting for simulated fills.
                side='Buy' if signed>0 else 'Sell'
                f=dict(strike=int(z['strikes'][j]),ot='PE' if rr[j] else 'CE',q=abs(int(signed)),price=str(price),side=side)
                change=book.apply(f);source+=1
                r=SimpleNamespace(**change,source_row=source,second=t,side=side)
                state.consume(r,j)
                cost=protocol['cost_scenarios']['moderate']
                charge=abs(signed)*price*cost['premium_turnover_fraction']+np.ceil(abs(signed)/base)*cost['per_parent']+abs(signed)*cost['per_unit']
                running_cost+=charge
                record['estimated_cost']=charge
                fills.append(record);cycle_fills.append(record)
            for ti in range(T):
                t=int(z['minutes'][ti])*60
                # Snapshot all decisions before submitting same-minute instructions.
                basket=row_at(ti,'basket');contract_rows={int(j):row_at(ti,'contract',int(rr[j]),int(j)) for j in np.flatnonzero(np.isfinite(z['previous'][ti])|(state.q!=0))}
                state.advance_peaks(basket,z['previous'][ti])
                pending=[]
                # Close/reduce existing shorts and close existing wings separately.
                for j,row in contract_rows.items():
                    action='close_contract' if state.q[j]<0 else 'sell_protection' if state.q[j]>0 else None
                    if action is None:continue
                    p,th=probability('contract',action,[row])
                    if p[0]>=th and t-previous_signals.get((action,j),-10**12)>120:
                        qty=abs(int(state.q[j])) if action=='close_contract' else min(abs(int(state.q[j])),amount('contract',int(rr[j]),'long_close',row))
                        pending.append((j,qty if state.q[j]<0 else -qty,action));previous_signals[(action,j)]=t
                    elif state.q[j]<0:
                        p,th=probability('contract','reduce_contract',[row])
                        if p[0]>=th and t-previous_signals.get(('reduce_contract',j),-10**12)>120:
                            qty=min(abs(int(state.q[j])),amount('contract',int(rr[j]),'short_close',row))
                            pending.append((j,qty,'reduce_contract'));previous_signals[('reduce_contract',j)]=t
                # New shorts require independently supported side gating AND strike
                # ranking AND protection module. No manual seed or clock rule fills gaps.
                for right,name in [(0,'ce'),(1,'pe')]:
                    row=row_at(ti,'side',right)
                    p,th=probability('side','add_'+name,[row])
                    wingp,wingth=probability('side','buy_protection',[row])
                    if p[0]<th or wingp[0]<wingth or t-previous_signals.get(('add',right),-10**12)<=120:
                        continue
                    js=[j for j in contract_rows if rr[j]==right and np.isfinite(z['previous'][ti,j])]
                    if not js:continue
                    candidate=[contract_rows[j] for j in js]
                    sp,sth=probability('contract','new_short',candidate)
                    hp,hth=probability('contract','buy_protection',candidate)
                    spot=basket.get('spot',np.nan)
                    outward=np.array([z['strikes'][j]>spot if right==0 else z['strikes'][j]<spot for j in js])
                    hp=np.where(outward,hp,-1.)
                    jshort,jhedge=js[int(np.argmax(sp))],js[int(np.argmax(hp))]
                    if max(sp)<sth or max(hp)<hth or jshort==jhedge:continue
                    shortqty=amount('side',right,'short_open',row);longqty=amount('side',right,'long_open',row)
                    if shortqty<=0 or longqty<=0:continue
                    # Realized fill success matters: never count a failed wing as protection.
                    execute(ti,jhedge,longqty,'buy_protection')
                    if state.q[jhedge]<=0:continue
                    pending.append((jshort,-shortqty,'new_short'));previous_signals[('add',right)]=t
                for j,signed,action in pending:execute(ti,j,signed,action)
                # Scoring targets are read only AFTER decisions and confirmed fills.
                actual=z['observed'][ti]
                l1+=int(np.abs(state.q-actual).sum());denom+=int((np.abs(state.q)+np.abs(actual)).sum())
                exact+=int(np.array_equal(state.q,actual))
                marks=z['previous'][ti].astype(float);live=state.q!=0
                equity=float(book.cash)+np.dot(state.q[live],marks[live]) if np.isfinite(marks[live]).all() else np.nan
                paths.append(dict(fold=fold,cycle_id=cid,second=t,simulated_equity=equity,estimated_cost=running_cost,
                    net_marked_equity=equity-running_cost,simulated_short_units=float(-state.q[state.q<0].sum()/base),
                    actual_short_units=float(-actual[actual<0].sum()/base),exact_inventory=np.array_equal(state.q,actual)))
                # A fill belongs to current minute; drawdown updates use only next
                # iteration's completed price, never current minute's future close.
            actual_actions=z['actual'];pred_actions=np.zeros_like(actual_actions)
            lookup={(int(k),'PE' if r else 'CE'):j for j,(k,r) in enumerate(zip(z['strikes'],rr))}
            # Map own fills to observable actions using their requested role.
            time_lookup={int(m)*60:i for i,m in enumerate(z['minutes'])}
            role_map={'new_short':0,'reduce_contract':1,'close_contract':1,'buy_protection':2,'sell_protection':3}
            for f in cycle_fills:
                pred_actions[time_lookup[f['second']],lookup[(f['strike'],f['option_type'])],role_map[f['action']]]+=abs(f['signed_quantity'])
            for role_index,role in enumerate(ROLES):
                for tolerance in [0,60,120]:
                    ac=pc=matches=0
                    for j in range(C):
                        aa=(z['minutes'][actual_actions[:,j,role_index]>0]*60).tolist()
                        pp=(z['minutes'][pred_actions[:,j,role_index]>0]*60).tolist()
                        ac+=len(aa);pc+=len(pp);matches+=len(strict_event_matches(aa,pp,tolerance))
                    result.append(dict(fold=fold,cycle_id=cid,underlying=m['underlying'],role=role,tolerance_seconds=tolerance,
                        actual=ac,predicted=pc,matched=matches,precision=matches/pc if pc else 0.,recall=matches/ac if ac else 0.,
                        inventory_overlap=1-l1/denom if denom else 1.,exact_inventory_fraction=exact/T,
                        failed_requests=failed,simulated_fills=len(cycle_fills),status='supported_modules_only; unapproved modules abstain',
                        final_inventory_reproduced=bool(np.array_equal(state.q,z['observed'][-1]))))
            print('Replay',fold,cid,'fills',len(cycle_fills),'approved',sum(approved.values()),flush=True)
    score=pd.DataFrame(result);score.to_csv(out/'autonomous_replay_scores.csv',index=False)
    pd.DataFrame(coverage).to_csv(out/'replay_module_eligibility.csv',index=False)
    pd.DataFrame(requests).to_csv(out/'autonomous_replay_requests.csv.gz',index=False,compression='gzip')
    pd.DataFrame(fills).to_csv(out/'autonomous_replay_fills.csv.gz',index=False,compression='gzip')
    pd.DataFrame(paths).to_csv(out/'autonomous_inventory_paths.csv.gz',index=False,compression='gzip')
    if paths:
        pd.DataFrame(paths).groupby(['fold','cycle_id']).tail(1).to_csv(out/'autonomous_cycle_economics.csv',index=False)
    return score
