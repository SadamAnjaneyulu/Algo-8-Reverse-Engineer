"""Follow-up: rounding and nearby fractions for the ATM-leg hedge budget.

Reuses the same incomplete prior-quote candidate universe. Not independent data.
"""
import csv
import gzip
import json
import math
from collections import defaultdict
from statistics import mean

from audit_strike_hedge_rules import OUT,logs,write,selector_score
from scan_hedge_leg_ratios import key,select


def rounded_budget(value,tick,mode):
    if not tick:return value
    scaled=value/tick
    units=math.floor(scaled+1e-10) if mode=='floor' else math.ceil(scaled-1e-10) if mode=='ceil' else math.floor(scaled+.5+1e-10)
    return units*tick


def scores(events,predicted):
    result=selector_score(events,predicted);step=logs.STEP[events[0]['underlying']]
    close=sum(k is not None and abs(k-e['strike'])<=step for e,k in zip(events,predicted))
    result.update(within_one_step=close,within_one_step_rate=close/len(events))
    return result


def main():
    spots={key(r):float(r['spot']) if r['spot'] else None for r in csv.DictReader((OUT/'rule_match_hedge_events.csv').open())}
    events=[];quotes=defaultdict(list)
    for r in csv.DictReader((OUT/'rule_match_leg_ratio_event_inputs.csv').open()):
        r['spot']=spots[key(r)];r['strike']=int(r['bought_strike']);r['reference']=float(r['atm_leg_prior_premium']) if r['atm_leg_prior_premium'] else None
        events.append(r)
    keys={key(r) for r in events}
    with gzip.open(OUT/'rule_match_hedge_candidate_quotes.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            if key(r) in keys:quotes[key(r)].append(dict(strike=int(r['strike']),price=float(r['price']),volume=float(r['volume'])))
    grid=[(fraction,tick,rounding,selector) for fraction in (.02,.0225,.025,.0275,.03)
          for tick,rounding in [(0,'none')]+[(t,m) for t in (.05,.1,.25,.5,1) for m in ('nearest','floor','ceil')]
          for selector in ('nearest','ceiling','floor')]
    def predict(e,rule):
        fraction,tick,rounding,selector=rule
        target=rounded_budget(e['reference']*fraction,tick,rounding) if e['reference'] is not None else None
        return select(quotes[key(e)],target,selector,e['spot'])
    calibration=[];evaluation=[];predictions=[];cycles=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            es=[e for e in events if e['underlying']==u and e['phase']==phase]
            train=[e for e in es if e['expiry_date']<='2026-08-31'];test=[e for e in es if e['expiry_date']>'2026-08-31'];rank=[]
            for rule in grid:
                stat=scores(train,[predict(e,rule) for e in train])
                row=dict(underlying=u,phase=phase,fraction=rule[0],tick=rule[1],rounding=rule[2],selector=rule[3],**stat)
                rank.append((row,rule));calibration.append(row)
            best=max(rank,key=lambda x:(x[0]['cycle_mean_exact'],x[0]['exact_rate']))
            base=(.025,0,'none','nearest' if (u,phase)==('NIFTY','expiry') else 'ceiling')
            for kind,rule in [('selected_refinement',best[1]),('original_2point5pct',base),
                              ('unrounded_nearest_2point5pct',(.025,0,'none','nearest')),
                              ('unrounded_ceiling_2point5pct',(.025,0,'none','ceiling'))]:
                pr=[predict(e,rule) for e in test]
                evaluation.append(dict(underlying=u,phase=phase,kind=kind,fraction=rule[0],tick=rule[1],rounding=rule[2],selector=rule[3],
                    calibration_cycle_mean_exact=next(row['cycle_mean_exact'] for row,r in rank if r==rule),**scores(test,pr)))
                for e,k in zip(test,pr):predictions.append(dict(underlying=u,expiry_date=e['expiry_date'],phase=phase,kind=kind,event_time_ist=e['event_time_ist'],
                    option_type=e['option_type'],observed_strike=e['strike'],predicted_strike=k if k is not None else '',exact=k==e['strike']))
                for expiry in sorted({e['expiry_date'] for e in test}):
                    ix=[i for i,e in enumerate(test) if e['expiry_date']==expiry]
                    cycles.append(dict(underlying=u,expiry_date=expiry,phase=phase,kind=kind,**scores([test[i] for i in ix],[pr[i] for i in ix])))
    write('rule_refine_hedge_grid_calibration.csv',calibration);write('rule_refine_hedge_evaluation.csv',evaluation)
    write('rule_refine_hedge_predictions.csv',predictions);write('rule_refine_hedge_cycle_scores.csv',cycles)
    summary=dict(calibration_comparisons=len(calibration),evaluation=evaluation,
        note='Secondary rounding refinement on the same retrospective incomplete traded-option chain. Earlier-only selection; later data previously inspected.')
    (OUT/'rule_refine_hedge_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
