"""Secondary hedge-cost hypotheses; reuses the saved prior-quote candidate audit.

Linked-short reference is conditional on the observed adjacent short strike;
it is not an independently predicted strike or future execution price.
"""
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime

from audit_strike_hedge_rules import ROOT,OUT,Market,logs,write,selector_score


def key(r):return (r['underlying'],r['expiry_date'],r.get('event_time_ist',r.get('t')),r['option_type'],int(r.get('bought_strike',r.get('strike'))))


def select(candidates,target,mode,spot):
    if target is None or not candidates:return None
    eligible=[c for c in candidates if c['volume']>0 and (mode!='ceiling' or c['price']<=target) and (mode!='floor' or c['price']>=target)]
    return min(eligible,key=lambda c:(abs(c['price']-target),abs(c['strike']-spot),c['strike']))['strike'] if eligible else None


def main():
    events=list(csv.DictReader((OUT/'rule_match_hedge_events.csv').open()))
    events=[r for r in events if r['stage']=='routine']
    quotes=defaultdict(list);keys={key(r) for r in events}
    with gzip.open(OUT/'rule_match_hedge_candidate_quotes.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            k=key(r)
            if k in keys:quotes[k].append(dict(strike=int(r['strike']),price=float(r['price']),volume=float(r['volume'])))
    linked=defaultdict(set)
    for r in csv.DictReader((OUT/'rule_match_hedge_short_links.csv').open()):
        if float(r['nearest_short_parent_distance_seconds'])>5:continue
        for source in r['source_rows'].split(';'):
            linked[int(source)].update(int(k) for k in r['short_strikes'].split(';'))
    metadata=defaultdict(list);bycycle=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for r in events:bycycle[(r['underlying'],r['expiry_date'])].append(r)
    index,_=logs.load_index();rows=[]
    for (u,e),es in sorted(bycycle.items()):
        market=Market(u,e,metadata[(u,e)],index)
        for raw in es:
            day=raw['date'];clock=raw['candidate_clock'];right=raw['option_type'];ks=set()
            for source in raw['sources'].split(';'):ks.update(linked[int(source)])
            r={**raw,'strike':int(raw['strike']),'spot':float(raw['spot']) if raw['spot'] else None,'quotes':quotes[key(raw)]}
            refs={'atm_leg':int(float(raw['atm'])) if raw['atm'] else None,
                  'previous_short_leg':int(float(raw['last_short'])) if raw['last_short'] else None,
                  'linked_short_leg_conditional':next(iter(ks)) if len(ks)==1 else None}
            for name,k in refs.items():
                b=market.bar(day,k,right,clock) if k is not None else None
                r[name]=b['close'] if b and b['volume']>0 else None
            rows.append(r)
    grid=[];comparisons=[];predictions=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            a=[r for r in rows if r['underlying']==u and r['phase']==phase]
            train=[r for r in a if r['expiry_date']<='2026-08-31'];test=[r for r in a if r['expiry_date']>'2026-08-31']
            for reference in ('atm_leg','previous_short_leg','linked_short_leg_conditional'):
                rank=[]
                for mode in ('nearest','ceiling','floor'):
                    for ratio in (.005,.0075,.01,.0125,.015,.02,.025,.03,.04,.05,.075,.1):
                        pr=[select(r['quotes'],r[reference]*ratio if r[reference] is not None else None,mode,r['spot']) for r in train]
                        rec=dict(underlying=u,phase=phase,reference=reference,mode=mode,ratio=ratio,**selector_score(train,pr))
                        grid.append(rec);rank.append(rec)
                best=max(rank,key=lambda r:(r['cycle_mean_exact'],r['exact_rate']))
                pr=[select(r['quotes'],r[reference]*best['ratio'] if r[reference] is not None else None,best['mode'],r['spot']) for r in test]
                comparisons.append(dict(underlying=u,phase=phase,reference=reference,mode=best['mode'],ratio=best['ratio'],
                    calibration_cycle_mean_exact=best['cycle_mean_exact'],reference_quote_available=sum(r[reference] is not None for r in test),**selector_score(test,pr)))
                for r,k in zip(test,pr):predictions.append(dict(underlying=u,expiry_date=r['expiry_date'],phase=phase,reference=reference,
                    event_time_ist=r['t'],option_type=r['option_type'],observed_strike=r['strike'],predicted_strike=k if k is not None else '',exact=k==r['strike']))
    contexts=[]
    for r in rows:
        selected=next((c for c in r['quotes'] if c['strike']==r['strike']),None)
        ref=r['atm_leg'];premium=selected['price'] if selected else None
        contexts.append(dict(underlying=r['underlying'],expiry_date=r['expiry_date'],phase=r['phase'],event_time_ist=r['t'],
            option_type=r['option_type'],bought_strike=r['strike'],atm_leg_prior_premium=ref,
            selected_prior_premium=premium,selected_prior_volume=selected['volume'] if selected else None,
            selected_cost_pct_of_atm=100*premium/ref if premium is not None and ref else None,
            target_2point5pct=ref*.025 if ref else None,executed_hedge_price=r['executed_price'],source_rows=r['sources']))
    write('rule_match_leg_ratio_event_inputs.csv',contexts)
    write('rule_match_leg_ratio_grid_calibration.csv',grid);write('rule_match_leg_ratio_evaluation.csv',comparisons)
    write('rule_match_leg_ratio_predictions.csv',predictions)
    summary=dict(parameter_comparisons=len(grid),selected_comparisons=comparisons,
        note='Secondary routine-only search added after inspecting paired buy/sell premiums. Linked-short reference conditions on the adjacent observed short strike using its preceding completed quote, not its future fill price. Incomplete retrospective chain; previously inspected later period.')
    (OUT/'rule_match_leg_ratio_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
