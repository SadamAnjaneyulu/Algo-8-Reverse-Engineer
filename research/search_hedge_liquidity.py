"""Budget × quote rounding × volume/OI eligibility combinations for hedge strikes."""
import csv
import gzip
import json
from collections import defaultdict,Counter
from itertools import product

import numpy as np
from audit_strike_hedge_rules import ROOT,OUT,logs,write
from scan_hedge_leg_ratios import key
from refine_hedge_budget import rounded_budget,scores


def predict(prices,strikes,volumes,oi,reference,rule):
    fraction,tick,rounding,selector,minvolume,minoi=rule
    target=np.array([rounded_budget(v*fraction,tick,rounding) if np.isfinite(v) else np.nan for v in reference])
    valid=np.isfinite(prices)&np.isfinite(target[:,None])&(volumes>=minvolume)&(oi>=minoi)
    if selector=='ceiling':valid&=prices<=target[:,None]
    if selector=='floor':valid&=prices>=target[:,None]
    errors=np.where(valid,abs(prices-target[:,None]),np.inf);chosen=errors.argmin(axis=1)
    result=strikes[np.arange(len(strikes)),chosen].copy();result[~valid.any(axis=1)]=-1
    return result


def main():
    es=[];quotes=defaultdict(list);needed=defaultdict(set)
    spots={key(r):float(r['spot']) if r['spot'] else None for r in csv.DictReader((OUT/'rule_match_hedge_events.csv').open())}
    for r in csv.DictReader((OUT/'rule_match_leg_ratio_event_inputs.csv').open()):
        r['strike']=int(r['bought_strike']);r['reference']=float(r['atm_leg_prior_premium']) if r['atm_leg_prior_premium'] else np.nan;r['spot']=spots[key(r)];es.append(r)
    keys={key(r) for r in es}
    with gzip.open(OUT/'rule_match_hedge_candidate_quotes.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            if key(r) not in keys:continue
            contract=(r['underlying'],r['expiry_date'],r['candidate_bar_start_ist'][:10],int(r['strike']),r['option_type']);clock=r['candidate_bar_start_ist'][11:16]
            needed[contract].add(clock);quotes[key(r)].append(dict(strike=int(r['strike']),price=float(r['price']),volume=float(r['volume']),contract=contract,clock=clock))
    interest={};coverage=Counter()
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());c=m['contract'];contract=(c['underlying'],c['expiry_date'],c['trade_date'],c['strike'],c['option_type'])
        if contract not in needed:continue
        for r in csv.DictReader((ROOT/'data/breeze'/m['normalized_path']).open()):
            clock=r['timestamp_ist'][11:16]
            if clock not in needed[contract]:continue
            oi=float(r['open_interest']) if r['open_interest'] else 0
            interest[(contract,clock)]=oi;coverage[(c['underlying'],'queried')]+=1;coverage[(c['underlying'],'positive')]+=oi>0
    calibration=[];evaluation=[];predictions=[];models={}
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            events=[r for r in es if r['underlying']==u and r['phase']==phase];n=len(events);width=max(len(quotes[key(r)]) for r in events)
            prices=np.full((n,width),np.inf);strikes=np.full((n,width),-1,dtype=int);volumes=np.full((n,width),-1.);oi=np.zeros((n,width))
            for i,e in enumerate(events):
                chain=sorted(quotes[key(e)],key=lambda c:(abs(c['strike']-(e['spot'] or 0)),c['strike']))
                for j,c in enumerate(chain):prices[i,j]=c['price'];strikes[i,j]=c['strike'];volumes[i,j]=c['volume'];oi[i,j]=interest.get((c['contract'],c['clock']),0)
            reference=np.array([r['reference'] for r in events]);actual=np.array([r['strike'] for r in events]);train=np.array([i for i,r in enumerate(events) if r['expiry_date']<='2026-08-31']);test=np.array([i for i,r in enumerate(events) if r['expiry_date']>'2026-08-31']);counts=Counter(events[i]['expiry_date'] for i in train);weights=np.array([1/counts[events[i]['expiry_date']] for i in train]);unit=logs.UNIT[u]
            grid=list(product((.02,.0225,.025,.0275,.03),[(0,'none'),(.1,'nearest'),(.1,'floor'),(.1,'ceil')],('nearest','ceiling','floor'),(0,unit,unit*10,unit*50,unit*100,unit*500),
                              (0,unit*100,unit*500,unit*1000,unit*5000,unit*10000,unit*50000) if u=='NIFTY' else (0,)))
            best=None
            for fraction,roundrule,selector,minvol,minoi in grid:
                rule=(fraction,*roundrule,selector,minvol,minoi);pr=predict(prices[train],strikes[train],volumes[train],oi[train],reference[train],rule);hit=pr==actual[train]
                weighted=float(hit@weights/weights.sum());complexity=bool(minvol)+bool(minoi)+bool(roundrule[0]);rank=(weighted,float(hit.mean()),-complexity)
                calibration.append(dict(underlying=u,phase=phase,fraction=fraction,tick=roundrule[0],rounding=roundrule[1],selector=selector,min_volume=minvol,min_oi=minoi,
                    calibration_events=len(train),exact=int(hit.sum()),exact_rate=float(hit.mean()),cycle_mean_exact=weighted))
                if best is None or rank>best[0]:best=(rank,rule)
            base=(.025,.1,'nearest','ceiling',unit,0) if (u,phase)==('SENSEX','preexpiry') else (.025,.1,'floor','nearest',unit,0) if (u,phase)==('SENSEX','expiry') else (.025,0,'none','nearest' if phase=='expiry' else 'ceiling',unit,0)
            models[u+'|'+phase]=dict(selected=best[1],base=base)
            for kind,rule in [('calibration_selected_liquidity',best[1]),('existing_budget_reference',base)]:
                pr=predict(prices[test],strikes[test],volumes[test],oi[test],reference[test],rule);chosen=[int(k) if k>=0 else None for k in pr]
                evaluation.append(dict(underlying=u,phase=phase,kind=kind,fraction=rule[0],tick=rule[1],rounding=rule[2],selector=rule[3],min_volume=rule[4],min_oi=rule[5],**scores([events[i] for i in test],chosen)))
                for i,k in zip(test,chosen):predictions.append(dict(underlying=u,expiry_date=events[i]['expiry_date'],phase=phase,kind=kind,event_time_ist=events[i]['event_time_ist'],option_type=events[i]['option_type'],actual_strike=int(actual[i]),predicted_strike=k if k is not None else '',exact=k==actual[i]))
            print('Liquidity hedge search',u,phase,evaluation[-2]['exact'],'/',len(test),flush=True)
    write('combo_liquidity_calibration.csv',calibration);write('combo_liquidity_evaluation.csv',evaluation);write('combo_liquidity_predictions.csv.gz',predictions)
    (OUT/'combo_liquidity_programs.json').write_text(json.dumps(models,indent=2)+'\n')
    (OUT/'combo_liquidity_summary.json').write_text(json.dumps(dict(calibration_comparisons=len(calibration),evaluation=evaluation,
        oi_coverage={u:dict(queried=coverage[(u,'queried')],positive=coverage[(u,'positive')]) for u in ('NIFTY','SENSEX')},
        note='OI unavailable where supplied as zero. SENSEX OI eligibility is not tested; only volume/budget combinations are tested there. Candidate quotes are an incomplete retrospective chain.'),indent=2)+'\n')


if __name__=='__main__':main()
