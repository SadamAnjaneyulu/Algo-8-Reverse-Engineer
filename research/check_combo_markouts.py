"""Fixed-basket economic diagnostics for selected conditional signals.

Not a full-cycle backtest: state features come from the recorded book, baskets
can overlap, the received chain is incomplete, and margin is not reconstructed.
"""
import csv
import gzip
import json
import random
from collections import defaultdict,Counter
from datetime import datetime,timedelta
from statistics import mean

from audit_strike_hedge_rules import ROOT,OUT,logs,Market,write
from combo_features import datasets
from refine_hedge_budget import rounded_budget
from scan_hedge_leg_ratios import select


def basket_markout(market,index,u,e,t,horizon):
    day=str(t.date());prior=t-timedelta(minutes=1);bars={b['t']:b for b in index.get((u,day),[])}
    guide=bars.get(prior)
    if guide is None:return None,'missing_prior_cash_bar'
    k=logs.round_strike(guide['close'],u);clock=prior.strftime('%H:%M');rights={}
    phase='preexpiry' if day<e else 'expiry'
    for right in ('CE','PE'):
        ref=market.bar(day,k,right,clock)
        if ref is None or ref['volume']<=0:return None,'missing_fresh_atm_reference'
        target=.025*ref['close'];selector='ceiling'
        if u=='SENSEX' and phase=='preexpiry':target=rounded_budget(target,.1,'nearest')
        if phase=='expiry':
            selector='nearest'
            if u=='SENSEX':target=rounded_budget(target,.1,'floor')
        chain=[]
        for (d,strike,ot),qs in market.quotes.items():
            if d!=day or ot!=right or not(strike>k if right=='CE' else strike<k):continue
            bar=qs.get(clock)
            if bar and bar['close']>0:chain.append(dict(strike=strike,price=bar['close'],volume=bar['volume']))
        selected=select(chain,target,selector,guide['close'])
        if selected is None:return None,'no_eligible_wing'
        rights[right]=selected
    entry=t+timedelta(minutes=1)
    end=entry+timedelta(minutes=15) if horizon=='15_minutes' else datetime.fromisoformat(e+'T15:14').replace(tzinfo=logs.IST)
    if end<=entry:return None,'exit_not_after_entry'
    positions=[(k,'CE',-1),(k,'PE',-1),(rights['CE'],'CE',1),(rights['PE'],'PE',1)];entry_prices=[];exit_prices=[];zero=0
    for strike,right,sign in positions:
        a=market.bar(str(entry.date()),strike,right,entry.strftime('%H:%M'));b=market.bar(str(end.date()),strike,right,end.strftime('%H:%M'))
        if a is None:return None,'missing_entry_open'
        if b is None:return None,'missing_exit_open'
        entry_prices.append(a['open']);exit_prices.append(b['open']);zero+=a['volume']==0 or b['volume']==0
    credit=entry_prices[0]+entry_prices[1]-entry_prices[2]-entry_prices[3]
    risk=max(rights['CE']-k,k-rights['PE'])-credit
    if risk<=0:return None,'nonpositive_theoretical_tail_loss'
    q=logs.UNIT[u];gross=q*sum(sign*(b-a) for (_,_,sign),a,b in zip(positions,entry_prices,exit_prices))
    turnover=q*sum(entry_prices+exit_prices);cost=.0025*turnover+8*20+8*q*.05;net=gross-cost
    return dict(underlying=u,expiry_date=e,date=day,phase=phase,decision_ist=t.isoformat(),entry_ist=entry.isoformat(),exit_ist=end.isoformat(),horizon=horizon,
        short_strike=k,long_ce_strike=rights['CE'],long_pe_strike=rights['PE'],quantity=q,gross_pnl=gross,cost_stress=cost,net_pnl=net,
        theoretical_expiry_tail_loss=q*risk,net_per_10000_tail_loss=net/(q*risk)*10000,zero_volume_endpoint_legs=zero),None


def week_key(expiry):
    d=datetime.fromisoformat(expiry).date().isocalendar();return (d.year,d.week)


def bootstrap_difference(rows,model,baseline='fixed_clock_active_book',draws=10000):
    grouped=defaultdict(lambda:defaultdict(list))
    for r in rows:
        if r['model'] in (model,baseline):grouped[week_key(r['expiry_date'])][r['model']].append(r['net_per_10000_tail_loss'])
    common=[k for k,v in grouped.items() if v[model] and v[baseline]]
    if not common:return dict(weeks=0,mean_difference=None,lower=None,upper=None)
    rng=random.Random(20261026);samples=[]
    for _ in range(draws):
        chosen=rng.choices(common,k=len(common));a=[p for k in chosen for p in grouped[k][model]];b=[p for k in chosen for p in grouped[k][baseline]]
        samples.append(mean(a)-mean(b))
    samples.sort();a=[p for k in common for p in grouped[k][model]];b=[p for k in common for p in grouped[k][baseline]]
    return dict(weeks=len(common),mean_difference=mean(a)-mean(b),lower=samples[int(.025*(draws-1))],upper=samples[int(.975*(draws-1))])


def main():
    _,fast=datasets();signals=defaultdict(set)
    preclocks={'09:30','09:45','10:00','10:15','10:30','10:45','11:00','11:15','11:30','11:45','12:00','12:30','13:30','13:45','14:00','14:15','14:30'}
    for r in fast:
        if r['split']!='evaluation':continue
        selected=r['clock'] in preclocks if r['phase']=='preexpiry' else r['clock']>='09:30' and r['clock']<='14:30' and int(r['clock'][3:])%15==0
        if selected and r['x_short_units']>0:signals[(r['underlying'],r['expiry_date'],r['date'],r['clock'])].add('fixed_clock_active_book')
    with gzip.open(OUT/'combo_action_predictions.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            if r['task']=='fresh_pairs' and r['predicted']=='1' and r['kind'] in ('boolean_temporal','tree_combinations'):
                signals[(r['underlying'],r['expiry_date'],r['date'],r['clock'])].add(r['kind'])
    for r in csv.DictReader((OUT/'combo_joint_predictions.csv').open()):
        if r['task']=='fresh_pairs' and r['predicted']=='1':signals[(r['underlying'],r['expiry_date'],r['date'],r['clock'])].add('joint_entry_exit')
    metadata=defaultdict(list);bycycle=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for key,modes in signals.items():bycycle[key[:2]].append((key,modes))
    index,_=logs.load_index();observations=[];excluded=[];attempts=Counter()
    for (u,e),items in sorted(bycycle.items()):
        market=Market(u,e,metadata[(u,e)],index)
        for key,modes in items:
            t=datetime.fromisoformat(key[2]+'T'+key[3]).replace(tzinfo=logs.IST)
            for horizon in ('15_minutes','expiry_15:14'):
                result,reason=basket_markout(market,index,u,e,t,horizon)
                for model in sorted(modes):
                    attempts[(model,horizon)]+=1
                    if reason:excluded.append(dict(underlying=u,expiry_date=e,date=key[2],clock=key[3],model=model,horizon=horizon,reason=reason))
                    else:observations.append(dict(model=model,**result))
    summaries=[];comparisons=[]
    for horizon in ('15_minutes','expiry_15:14'):
        for model in sorted({r['model'] for r in observations}):
            rs=[r for r in observations if r['model']==model and r['horizon']==horizon]
            if not rs:continue
            summaries.append(dict(model=model,horizon=horizon,attempted=attempts[(model,horizon)],quoted_allocations=len(rs),cycles=len({r['expiry_date'] for r in rs}),
                mean_net_pnl_per_observed_quantity_unit=mean(r['net_pnl'] for r in rs),
                mean_net_per_10000_tail_loss=mean(r['net_per_10000_tail_loss'] for r in rs),
                positive_after_stress=sum(r['net_pnl']>0 for r in rs),allocations_with_zero_volume_endpoint=sum(r['zero_volume_endpoint_legs']>0 for r in rs)))
            if model!='fixed_clock_active_book':comparisons.append(dict(model=model,horizon=horizon,**bootstrap_difference([r for r in observations if r['horizon']==horizon],model)))
    write('combo_economic_markouts.csv.gz',observations);write('combo_economic_exclusions.csv',excluded)
    write('combo_economic_summary.csv',summaries);write('combo_economic_comparisons.csv',comparisons)
    (OUT/'combo_economic_summary.json').write_text(json.dumps(dict(summaries=summaries,comparisons=comparisons,
        assumptions=['Same independently chosen ATM short strike and 2.5%-budget wings for all signal models at a given minute.',
          'Selection uses prior completed prices; entry is the next minute open, with 15-minute or fixed expiry-cutoff exit opens.',
          'Costs: 25 bps of premium turnover, eight orders at 20 each, eight transacted quantities at 0.05 each; these are stress assumptions.',
          'PnL normalized by the static basket theoretical expiry tail loss, not historical margin/gamma; no account equity or compounded return is claimed.',
          'Overlapping allocations, missing chain/quote coverage, zero-volume endpoints and actual-book-conditioned signals preclude an autonomous strategy or alpha claim.'],
        note='Later-period fixed-basket conditional markout diagnostic, not the original Algo 8 backtest or independent alpha validation.'),indent=2)+'\n')


if __name__=='__main__':main()
