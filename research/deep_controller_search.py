"""Finite, relevant three-condition controller search with exact false signals.

Searches actual prior-known contract states, not an autonomous strategy replay.
September/October were inspected before this study and are not untouched data.
Packed Python integers make millions of explicit programs inexpensive to score.
"""
import csv
import heapq
import json
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import OUT
from allocation_rule_models import event_tolerance, cooldown_predictions
from rank_trigger_probabilities import save_records


@dataclass
class Atom:
    text: str
    field: str
    mask: np.ndarray


def packed(mask):
    return int.from_bytes(np.packbits(mask, bitorder='little').tobytes(), 'little')


def crossing_mask(state, previous_index, consecutive):
    """Crossings require a consecutive observation of the same contract/day."""
    old=np.zeros(len(state),bool)
    old[consecutive]=state[previous_index[consecutive].astype(int)]
    return state&consecutive&~old


def metrics(tp, signals, actual):
    return dict(matched=tp, signals=signals, positives=actual, false_signals=signals-tp,
                missed=actual-tp, precision=tp/signals if signals else 0.,
                recall=tp/actual if actual else 0., f1=2*tp/(signals+actual) if signals+actual else 0.)


def inputs():
    d = pd.read_csv(OUT/'allocation_contract_features.csv.gz')
    sign = np.where(d.option_type == 'CE', 1., -1.)
    d['clock_minutes'] = d.clock.str[:2].astype(int)*60+d.clock.str[3:5].astype(int)
    d['net_equity'] = d.g_CE_equity_pct_capital+d.g_PE_equity_pct_capital
    d['book_abs_delta'] = d.g_book_delta_per_short_unit.abs()
    for suffix in ('equity_pct_capital', 'short_units', 'long_units', 'delta_per_short_unit', 'vega_pct_capital', 'gamma_move1pct_pct_capital'):
        d['same_'+suffix] = np.where(d.option_type == 'CE', d['g_CE_'+suffix], d['g_PE_'+suffix])
    d['same_delta_adverse'] = -sign*d.same_delta_per_short_unit
    d['short_unhedged_units'] = d.same_short_units-d.same_long_units
    d['strike_distance_adverse_pct'] = sign*(d.g_spot/d.strike-1)*100
    lookup = d.set_index(['contract','date','clock'])
    past = (pd.to_datetime(d.clock, format='%H:%M')-pd.Timedelta(minutes=5)).dt.strftime('%H:%M')
    keys = pd.MultiIndex.from_arrays([d.contract,d.date,past])
    for field in ('g_contract_iv_pct','g_contract_abs_delta','g_price'):
        d[field+'_change5'] = d[field].to_numpy()-lookup[field].reindex(keys).to_numpy()
    return d


def catalog(d):
    """Economically interpretable triggers; no arbitrary indicator bank."""
    specifications = {
        'g_loss_pct': [-95,-90,-80,-75,-60,-50,-40,-25,-10,0,4,10,15,20,25,30,40,50,60,70,75,80,90,100,125,150,200],
        'g_fifo_max_loss_pct': [4,10,20,25,30,40,50,60,70,75,80,100,125,150],
        'g_lifo_max_loss_pct': [4,10,20,25,30,40,50,60,70,75,80,100,125,150],
        'g_trailing_recovery_pct': [2,4,5,10,15,20,25,30,40,50,60,75,100],
        'g_from_previous_close_pct': [-75,-50,-25,-10,0,2,3,4,5,7.5,10,15,20,25,40,50,75,100],
        'g_from_expiry_open_pct': [-75,-50,-25,-10,0,2,3,4,5,10,20,25,50,75,100],
        'g_contract_abs_delta': [.3,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95],
        'g_contract_iv_pct_change5': [-2,-1,-.5,-.25,0,.25,.5,1,2,3],
        'g_contract_gamma_move1pct_over_premium': [.25,.5,.75,1,1.5,2,3,4,5,7.5,10],
        'g_adverse_spot5_pct': [-.5,-.25,-.1,0,.025,.05,.075,.1,.15,.2,.3,.5],
        'g_adverse_spot15_pct': [-.5,-.25,-.1,0,.05,.1,.15,.2,.3,.5,.75,1],
        'g_adverse_spot_since_entry_pct': [-1,-.5,-.25,0,.05,.1,.15,.2,.3,.5,.75,1],
        'strike_distance_adverse_pct': [-1,-.5,-.25,-.1,0,.1,.2,.3,.5,.75,1],
        'same_equity_pct_capital': [-1,-.75,-.5,-.4,-.3,-.25,-.2,-.1,0,.1,.2,.3,.5,.75,1],
        'net_equity': [-1,-.75,-.5,-.4,-.3,-.25,-.2,-.1,0,.1,.2,.3,.5,.75,1],
    }
    trigger, filters = [], []
    previous = d.groupby(['contract','date'],sort=False).cumcount().to_numpy()>0
    previous_index = pd.Series(np.arange(len(d)),index=d.index).groupby([d.contract,d.date],sort=False).shift().to_numpy()
    prior_clock = d.groupby(['contract','date'],sort=False).clock_minutes.shift().to_numpy()
    consecutive = previous & (d.clock_minutes.to_numpy()-prior_clock == 1)
    for field, thresholds in specifications.items():
        values = d[field].to_numpy(float)
        for threshold in thresholds:
            for operator in ('>=','<='):
                state = np.isfinite(values)&((values>=threshold) if operator=='>=' else (values<=threshold))
                text = f'{field} {operator} {threshold:g}'
                trigger.append(Atom(text,field,state))
                trigger.append(Atom('CROSS('+text+')',field,crossing_mask(state,previous_index,consecutive)))
    for field, thresholds in {
        'g_loss_pct':[-80,-50,-25,0,4,25,50,75,100],
        'g_trailing_recovery_pct':[4,10,25,50],
        'g_adverse_spot5_pct':[0,.05,.1,.2],
        'g_adverse_spot15_pct':[0,.1,.2,.5],
        'g_contract_abs_delta':[.4,.5,.6,.7,.8],
        'g_contract_iv_pct_change5':[-.5,0,.5,1],
        'g_range15_pct':[.1,.2,.3,.5,.75,1],
        'g_atm_iv_pct':[12,15,18,20,25],
        'same_equity_pct_capital':[-1,-.5,-.25,0,.25,.5],
        'net_equity':[-1,-.5,-.25,0,.25,.5],
        'book_abs_delta':[.05,.1,.2,.3,.4],
        'same_delta_adverse':[.2,.3,.4,.5,.6],
        'g_book_vega_pct_capital':[-.5,-.25,-.1,-.05],
        'g_book_gamma_move1pct_pct_capital':[-10,-5,-2,-1],
        'same_short_units':[5,10,15,20,30,40,50,60],
        'short_unhedged_units':[0,1,2,5],
    }.items():
        values=d[field].to_numpy(float)
        for level in thresholds:
            for operator in ('>=','<='):
                mask=np.isfinite(values)&((values>=level) if operator=='>=' else (values<=level))
                filters.append(Atom(f'{field} {operator} {level:g}',field,mask))
    gates=[Atom('ALWAYS','always',np.ones(len(d),bool))]
    for field, thresholds in {'g_age_minutes':[5,15,30,60,120],
                              'g_since_cover_minutes':[5,15,30],
                              'clock_minutes':[600,660,720,780,840,900]}.items():
        values=d[field].to_numpy(float)
        for level in thresholds:
            gates.append(Atom(f'{field} >= {level:g}',field,np.isfinite(values)&(values>=level)))
    return trigger,filters,gates


def search_group(d, name, catalog_fn=catalog):
    d=d.reset_index(drop=True)
    trigger,filters,gates=catalog_fn(d)
    cal=d.split.eq('calibration').to_numpy()&d.onset_eligible.eq(1).to_numpy()
    later=d.split.eq('evaluation').to_numpy()&d.onset_eligible.eq(1).to_numpy()
    y=d.target_cover.eq(1).to_numpy()
    actual=int(np.sum(cal&y)); truth=packed(y[cal])
    tbits=[packed(a.mask[cal]) for a in trigger]
    fbits=[packed(a.mask[cal]) for a in filters]
    gbits=[packed(a.mask[cal]) for a in gates]
    heap=[]; strict={.8:None,.9:None}; tested=0
    def consider(mask, spec):
        nonlocal tested
        tested+=1
        signals=mask.bit_count()
        if not signals:return
        tp=(mask&truth).bit_count()
        if not tp:return
        f1=2*tp/(signals+actual)
        key=(f1,tp,-signals)
        item=(key,spec)
        if len(heap)<40:heapq.heappush(heap,item)
        elif key>heap[0][0]:heapq.heapreplace(heap,item)
        for target in strict:
            if signals>=20 and tp/signals>=target:
                k=(tp,f1,-signals)
                if strict[target] is None or k>strict[target][0]:strict[target]=(k,spec)
    for ti,ta in enumerate(trigger):
        for fi,fa in enumerate(filters):
            if ta.field==fa.field:continue
            pair=tbits[ti]&fbits[fi]
            for gi,g in enumerate(gates):
                if g.field in (ta.field,fa.field):continue
                consider(pair&gbits[gi],('AND',ti,fi,gi))
    # Independent loss/profit controllers can fire by either branch.
    losses=[i for i,a in enumerate(trigger) if a.field in ('g_loss_pct','g_from_previous_close_pct','g_trailing_recovery_pct') and '>=' in a.text]
    profits=[i for i,a in enumerate(trigger) if a.field=='g_loss_pct' and '<=' in a.text]
    for ti in losses:
        for tj in profits:
            for gi,g in enumerate(gates):
                consider((tbits[ti]|tbits[tj])&gbits[gi],('OR',ti,tj,gi))
    selections={'best_f1':max(heap)[1]}
    selections.update({f'precision_{p}':a[1] for p,a in strict.items() if a is not None})
    testrows=d.loc[later,['underlying','expiry_date','date','clock','contract','cycle']].to_dict('records')
    evaluation=[]; predictions=[]; programs={}
    for policy,spec in selections.items():
        op,i,j,g=spec
        second=filters[j] if op=='AND' else trigger[j]
        raw=(trigger[i].mask&second.mask if op=='AND' else trigger[i].mask|second.mask)&gates[g].mask
        expression=f'({trigger[i].text} {op} {second.text}) AND ({gates[g].text})'
        for cooldown in (0,5,15):
            # Cooldown variants are reported, not selected on later results.
            prediction=cooldown_predictions(testrows,raw[later],cooldown)
            a=y[later]; stat=metrics(int(np.sum(a&prediction)),int(prediction.sum()),int(a.sum()))
            tol=event_tolerance(testrows,a,prediction)
            tr=raw&cal; trstat=metrics(int(np.sum(y&tr)),int(tr.sum()),actual)
            evaluation.append(dict(task=name,policy=policy,cooldown=cooldown,expression=expression,
                                   calibration_precision=trstat['precision'],calibration_recall=trstat['recall'],
                                   **stat,tolerance2_precision=tol['precision'],tolerance2_recall=tol['recall']))
            if cooldown==5:
                for r,truth_value,p in zip(testrows,a,prediction):
                    if truth_value or p:predictions.append(dict(task=name,policy=policy,**r,target=int(truth_value),predicted=int(p)))
        programs[policy]=expression
    summary=dict(task=name,programs_scored=tested,trigger_atoms=len(trigger),filter_atoms=len(filters),gates=len(gates),
                 earlier_opportunities=int(cal.sum()),earlier_events=actual,later_opportunities=int(later.sum()),
                 later_events=int(y[later].sum()),selected=programs)
    print(json.dumps(summary),flush=True)
    return summary,evaluation,predictions


def main():
    started=time.monotonic(); d=inputs(); summaries=[];evaluation=[];predictions=[]
    for phase in ('preexpiry','expiry'):
        for u in ('NIFTY','SENSEX'):
            for right in ('CE','PE'):
                sample=d[(d.phase==phase)&(d.underlying==u)&(d.option_type==right)].copy()
                s,e,p=search_group(sample,phase+'|'+u+'|'+right)
                summaries.append(s);evaluation.extend(e);predictions.extend(p)
                save_records('deep_exit_search_evaluation.csv',evaluation)
    save_records('deep_exit_search_event_predictions.csv.gz',predictions)
    (OUT/'deep_exit_search_summary.json').write_text(json.dumps(dict(
        programs_scored=sum(s['programs_scored'] for s in summaries),seconds=time.monotonic()-started,groups=summaries,
        limitations=['Finite relevant grammar, not all possible programs.',
                     'Programs are scored separately per index, right and phase; this count is not independent hypotheses.',
                     'Actual prior inventory and five-minute quiet-cover eligibility condition the task; no autonomous replay.',
                     'Threshold search is earlier-only, with no nested selection validation. Later dates were previously inspected.',
                     'Minute close-based states can miss intrabar triggers; stops and profit-taking may coexist.',
                     'Precision-target choices are calibration requirements, not later guarantees or probabilities of original intent.']),indent=2)+'\n')


if __name__=='__main__':main()
