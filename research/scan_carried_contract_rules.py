"""Compare price-reference stops with first buybacks in carried short contracts.

Contract-level attribution is deliberately not asserted to identify original lots.
"""
import json
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from statistics import mean,median

import analyze_index_triggers as logs
from analyze_iv_theta_hypothesis import Market
from audit_strike_hedge_rules import write

ROOT=logs.ROOT;OUT=logs.OUT


def remaining_entry_references(rows):
    """FIFO/LIFO residual lot costs and pooled short-position average."""
    books=[[],[]];q=0;average=None;stable=True
    for r in rows:
        stable&=r['opening']==r['reverse_opening']
        if r['side']=='Sell' and r['opening']:
            add=r['opening'];p=float(r['price'])
            average=((average or 0)*q+p*add)/(q+add);q+=add
            for b in books:b.append([add,p])
        if r['side']=='Buy':
            cover=r['q']-r['opening'];q-=cover
            if q==0:average=None
            for j,b in enumerate(books):
                left=cover
                while left and b:
                    i=0 if j==0 else -1;take=min(left,b[i][0]);left-=take;b[i][0]-=take
                    if b[i][0]==0:b.pop(i)
                if left:stable=False
    references=[]
    for b in books:references.append(sum(n*p for n,p in b)/sum(n for n,p in b) if b else None)
    return dict(fifo_entry=references[0] if stable else None,lifo_entry=references[1] if stable else None,
                pooled_entry=average if stable else None,entry_reference_stable=stable,tracked_short_quantity=q)


def contract_signal(row,reference,kind,parameter,opening=True):
    base=row.get(reference)
    if not base or base<=0:return row['fallback']
    minimum=base
    for point in row['prices']:
        if point['opening'] and not opening:continue
        if point['t']>=row['fallback']:break
        p=point['price']
        if kind=='fixed_stop':hit=p>=base*(1+parameter/100)-1e-10
        elif kind=='profit_target':hit=p<=base*(1-parameter/100)+1e-10
        else:
            minimum=min(minimum,p);hit=p>=minimum*(1+parameter/100)-1e-10
        if hit:return point['t']
    return row['fallback']


def match_score(rows,predictions):
    bycycle=defaultdict(list);delays=[]
    for r,p in zip(rows,predictions):
        d=(p-r['target']).total_seconds()/60;delays.append(d);bycycle[(r['underlying'],r['expiry_date'])].append(abs(d)<=2)
    return dict(contracts=len(rows),cycles=len(bycycle),matches_2m=sum(abs(d)<=2 for d in delays),
                match_rate_2m=mean(abs(d)<=2 for d in delays) if delays else None,
                cycle_mean_match=mean(mean(v) for v in bycycle.values()) if bycycle else None,
                mean_abs_error_minutes=mean(abs(d) for d in delays) if delays else None)


def main():
    fills=defaultdict(list);metadata=defaultdict(list)
    for r in logs.read_fills():fills[(r['u'],str(r['expiry']))].append(r)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index();rows=[];excluded=[]
    for (u,e),rs in sorted(fills.items()):
        market=Market(u,e,metadata[(u,e)],index);pre=[r for r in rs if str(r['t'].date())<e]
        book=Counter()
        for r in pre:book[(r['strike'],r['ot'])]+=r['signed']
        prior_days=sorted(d for d in market.days if d<e)
        if not prior_days:continue
        day=prior_days[-1];clock='15:39' if day>='2026-08-03' else '15:29'
        for (k,ot),quantity in book.items():
            if quantity>=0:continue
            prior=market.bar(day,k,ot,clock);opened=market.bar(e,k,ot,'09:15')
            covers=[r for r in rs if str(r['t'].date())==e and r['strike']==k and r['ot']==ot and
                    r['side']=='Buy' and r['q']>r['opening'] and r['opening']==r['reverse_opening']]
            if not covers or prior is None or opened is None:
                excluded.append(dict(underlying=u,expiry_date=e,strike=k,option_type=ot,reason='No stable observed first cover, previous close or expiry opening bar.'));continue
            reference=remaining_entry_references([r for r in pre if (r['strike'],r['ot'])==(k,ot)])
            prices=[dict(t=datetime.fromisoformat(e+'T09:15').replace(tzinfo=logs.IST),price=opened['open'],opening=True)]
            for c,b in sorted(market.quotes.get((e,k,ot),{}).items()):
                if b['volume']>0:
                    prices.append(dict(t=datetime.fromisoformat(e+'T'+c).replace(tzinfo=logs.IST)+timedelta(minutes=1),price=b['close'],opening=False))
            rows.append(dict(underlying=u,expiry_date=e,strike=k,option_type=ot,carried_short_quantity=-quantity,
                previous_close=prior['close'],expiry_open=opened['open'],**reference,prices=prices,target=min(r['t'] for r in covers),
                target_source=min(covers,key=lambda r:r['t'])['source'],
                fallback=datetime.fromisoformat(e+('T15:14' if e>='2026-08-03' else 'T15:29')).replace(tzinfo=logs.IST)))
    train=[r for r in rows if r['expiry_date']<='2026-08-31'];test=[r for r in rows if r['expiry_date']>'2026-08-31']
    scores=[];comparisons=[];predictions=[]
    for opening in (False,True):
        rank=[]
        for ref in ('previous_close','pooled_entry','fifo_entry','lifo_entry','expiry_open'):
            for kind in ('fixed_stop','profit_target','expiry_trailing_stop'):
                for param in (.5,1,2,3,4,5,7.5,10,15,20,25,30,40,50,75,100):
                    pr=[contract_signal(r,ref,kind,param,opening) for r in train]
                    rec=dict(reference=ref,family=kind,parameter=param,include_opening_proxy=opening,**match_score(train,pr))
                    scores.append(rec);rank.append(rec)
        best=max(rank,key=lambda r:(r['cycle_mean_match'],-r['mean_abs_error_minutes']))
        chosen=[('selected',best),('stated_4pct_previous_close',next(r for r in rank if (r['reference'],r['family'],r['parameter'])==('previous_close','fixed_stop',4))),
                ('stated_4pct_pooled_entry',next(r for r in rank if (r['reference'],r['family'],r['parameter'])==('pooled_entry','fixed_stop',4)))]
        for name,rec in chosen:
            pr=[contract_signal(r,rec['reference'],rec['family'],rec['parameter'],opening) for r in test]
            comparisons.append(dict(kind=name,reference=rec['reference'],family=rec['family'],parameter=rec['parameter'],include_opening_proxy=opening,
                calibration_cycle_mean_match=rec['cycle_mean_match'],**match_score(test,pr)))
            for r,p in zip(test,pr):predictions.append(dict(underlying=r['underlying'],expiry_date=r['expiry_date'],strike=r['strike'],option_type=r['option_type'],
                kind=name,include_opening_proxy=opening,observed_first_cover_ist=r['target'].isoformat(),predicted_ist=p.isoformat(),
                prediction_minus_observed_minutes=(p-r['target']).total_seconds()/60,reference=rec['reference'],family=rec['family'],parameter=rec['parameter'],source_row=r['target_source']))
    write('rule_match_carry_contract_inputs.csv',[{k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in r.items() if k!='prices'} for r in rows])
    write('rule_match_carry_contract_grid_calibration.csv',scores);write('rule_match_carry_contract_evaluation.csv',comparisons)
    write('rule_match_carry_contract_predictions.csv',predictions);write('rule_match_carry_contract_exclusions.csv',excluded)
    summary=dict(contracts=len(rows),calibration_contracts=len(train),evaluation_contracts=len(test),parameter_comparisons=len(scores),selected_comparisons=comparisons,
        note='Target is first stable buyback in a carried contract, not verified closing of a particular overnight lot. Entry reference uses alternative FIFO/LIFO or pooled allocations. Includes fixed terminal time fallback; first crossings use positive-volume completed prices, with opening proxy separately flagged.')
    (OUT/'rule_match_carry_contract_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
