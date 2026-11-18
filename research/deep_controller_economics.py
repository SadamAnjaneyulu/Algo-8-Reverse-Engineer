"""Conditional economics of frozen selected side exits against clock exits.

Recorded entries and inferred equal-quantity outward protection are shared by
both arms. This does not test autonomous entry alpha or original margin risk.
"""
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime,timedelta

import numpy as np

from audit_strike_hedge_rules import ROOT,OUT,logs,Market
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def main():
    parents={p['parent_id']:p for p in load_parents()}
    links={r['short_parent']:r for r in csv.DictReader((OUT/'allocation_inferred_hedge_links.csv').open())
           if r['association_ambiguous']=='False'}
    predictions=list(csv.DictReader(gzip.open(OUT/'deep_allocation_stop_predictions.csv.gz','rt')))
    predictions=[r for r in predictions if r['task'].startswith('completed_close|fifo|') and r['model']=='global_program' and r['parent_id'] in links]
    meta=defaultdict(list);group=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());meta[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for r in predictions:group[(r['underlying'],r['expiry_date'])].append(r)
    index,_=logs.load_index();rows=[];excluded=[]
    for (u,e),batch in sorted(group.items()):
        market=Market(u,e,meta[(u,e)],index)
        deadline=datetime.fromisoformat(e+('T15:14' if e>='2026-08-03' else 'T15:25')).replace(tzinfo=logs.IST)
        for r in batch:
            short=parents[r['parent_id']];long=parents[links[r['parent_id']]['long_parent']]
            predicted=datetime.fromtimestamp(float(r['predicted'])*60,logs.IST)
            exit_time=predicted+timedelta(minutes=1) if predicted<deadline else deadline
            if max(short['last'],long['last'])>=min(exit_time,deadline):continue
            width=abs(short['strike']-long['strike']);credit=short['price']-long['price'];risk=short['quantity']*(width-credit)
            results={}
            for arm,t in [('candidate',exit_time),('clock',deadline)]:
                quotes=[market.bar(str(t.date()),p['strike'],p['option_type'],t.strftime('%H:%M')) for p in (short,long)]
                if any(q is None for q in quotes):break
                s,h=[q['open'] for q in quotes];q=short['quantity']
                turnover=q*(short['price']+long['price']+s+h)
                gross=q*(credit-s+h)
                results[arm]=dict(net=gross-.0025*turnover-4*20-4*q*.05,
                                  high_net=gross-.005*turnover-4*20-4*q*.1,
                                  zero_volume_bars=sum(quote['volume']<=0 for quote in quotes),
                                  price_bound_violation=not(-.1<=s-h<=width+.1))
            if len(results)<2 or risk<=0:
                excluded.append(dict(parent_id=r['parent_id'],underlying=u,expiry_date=e,reason='Missing shared endpoints or nonpositive risk denominator'));continue
            row=dict(parent_id=r['parent_id'],underlying=u,expiry_date=e,option_type=short['option_type'],
                     entry_phase='preexpiry' if str(short['first'].date())<e else 'expiry',quantity=short['quantity'],
                     theoretical_vertical_loss=risk,candidate_exit_ist=exit_time.isoformat(),clock_exit_ist=deadline.isoformat())
            for arm,values in results.items():row.update({arm+'_'+k:v for k,v in values.items()})
            row['net_difference']=results['candidate']['net']-results['clock']['net']
            row['high_net_difference']=results['candidate']['high_net']-results['clock']['high_net']
            rows.append(row)
    save_records('deep_controller_economics_allocations.csv.gz',rows);save_records('deep_controller_economics_exclusions.csv',excluded)
    summaries=[]
    for u in ('NIFTY','SENSEX','pooled'):
        for quality in ('all_shared_endpoints','nonzero_volume_and_price_bounds'):
            rs=[r for r in rows if (u=='pooled' or r['underlying']==u) and
                (quality=='all_shared_endpoints' or not(r['candidate_zero_volume_bars'] or r['clock_zero_volume_bars'] or r['candidate_price_bound_violation'] or r['clock_price_bound_violation']))]
            if not rs:continue
            cycles=defaultdict(float)
            for r in rs:cycles[(r['underlying'],r['expiry_date'])]+=r['net_difference']
            weeks=defaultdict(list)
            for key,value in cycles.items():
                iso=datetime.fromisoformat(key[1]).isocalendar();weeks[(iso.year,iso.week)].append(value)
            groups=list(weeks.values());rng=np.random.default_rng(20261027)
            boots=[np.mean([v for i in rng.integers(0,len(groups),len(groups)) for v in groups[i]]) for _ in range(2000)]
            low,high=np.quantile(boots,[.025,.975])
            summaries.append(dict(underlying=u,quality=quality,allocations=len(rs),cycles=len(cycles),
                candidate_net=sum(r['candidate_net'] for r in rs),clock_net=sum(r['clock_net'] for r in rs),
                net_difference=sum(r['net_difference'] for r in rs),high_cost_difference=sum(r['high_net_difference'] for r in rs),
                cycles_improved=sum(v>0 for v in cycles.values()),mean_cycle_difference=np.mean(list(cycles.values())),
                weekly_bootstrap_mean_cycle_lower=low,weekly_bootstrap_mean_cycle_upper=high))
    save_records('deep_controller_economics_summary.csv',summaries)
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
