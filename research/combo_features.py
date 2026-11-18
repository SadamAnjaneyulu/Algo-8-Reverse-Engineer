"""Causal position/order context for combined-rule inverse search."""
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime,timedelta

from audit_strike_hedge_rules import ROOT,OUT,Market,logs,reconstruct_parents,write
from mass_match_strategy_rules import numeric,faster_feature_alignment
from refine_exit_scopes import RoleBook


def load_base():
    text={'underlying','expiry_date','cycle','date','phase','clock','split','feature_cutoff_ist','last_completed_bar_start_ist'}
    with gzip.open(OUT/'rule_match_indicator_features.csv.gz','rt') as f:rows=list(csv.DictReader(f))
    for r in rows:
        for k,v in r.items():
            if k not in text:r[k]=numeric(v)
    return rows


def context_grid(columns):
    rules=[]
    for k in columns:
        if not k.startswith('x_') or k.endswith('_ist'):continue
        if 'pct_capital' in k:levels=(-1.5,-1,-.75,-.5,-.4,-.25,-.1,0,.1,.25,.5,.75,1,1.5)
        elif k in ('x_max_short_loss_pct','x_mean_short_loss_pct','x_max_trailing_rise_pct'):levels=(0,2,4,5,7.5,10,15,20,25,30,40,50,75,100)
        elif 'fraction' in k or 'coverage' in k:levels=(0,.25,.5,.75,1,1.25,1.5,2)
        elif 'spot_gap' in k:levels=(-3,-2,-1,-.5,-.25,0,.25,.5,1,2,3)
        elif 'spot_change' in k:levels=(-1,-.5,-.25,-.1,-.05,0,.05,.1,.25,.5,1)
        elif k=='x_phase_minute':levels=(15,30,45,60,90,120,150,180,210,240,270,300)
        else:levels=(0,1,2,3,5,10,15,20,30,40,60,100)
        for v in levels:
            for op in ('le','gt'):
                rules.append((k,op,float(v),'state'));rules.append((k,op,float(v),'cross'))
    return rules


def build_context():
    fills=logs.read_fills();parents=reconstruct_parents(fills);source={r['source']:r for r in fills}
    bycycle=defaultdict(list);metadata=defaultdict(list);first_events=defaultdict(list)
    for r in fills:bycycle[(r['u'],str(r['expiry']))].append(r)
    for p in parents:
        r=min((source[int(s)] for s in p['sources'].split(';')),key=lambda r:(r['t'],r['source']))
        roles=[]
        if r['side']=='Sell' and r['opening']>0:roles.append('short')
        if r['side']=='Buy' and r['opening']>0:roles.append('long')
        if r['side']=='Buy' and r['q']>r['opening']:roles.append('cover')
        first_events[(p['underlying'],p['expiry_date'])].append((r['t'],roles))
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index();pairs=logs.pairing(fills,index);records=[]
    for (u,e),rs in sorted(bycycle.items()):
        market=Market(u,e,metadata[(u,e)],index);book=RoleBook();cursor=0;minima={}
        history=sorted(first_events[(u,e)]);known_pairs=[p for p in pairs if p['underlying']==u and p['expiry_date']==e]
        for day in sorted({str(r['t'].date()) for r in rs}):
            start=datetime.fromisoformat(day+'T09:15').replace(tzinfo=logs.IST)
            bars={b['t'].strftime('%H:%M'):b for b in index.get((u,day),[])}
            count=385 if day>='2026-08-03' else 375
            for i in range(count+1):
                t=start+timedelta(minutes=i)
                while cursor<len(rs) and rs[cursor]['t']<t:
                    r=rs[cursor];key=(r['strike'],r['ot']);old=book.inventory[key];book.apply(r)
                    if book.inventory[key]>=0:minima.pop(key,None)
                    elif old>=0:minima[key]=float(r['price'])
                    cursor+=1
                prev=t-timedelta(minutes=1);clock=prev.strftime('%H:%M');mark=book.mark(market,day,clock)
                active=[(k,o,q) for (k,o),q in book.inventory.items() if q<0];unit=logs.UNIT[u]
                losses=[];weights=[];trails=[];missing=0
                for k,o,q in active:
                    b=market.bar(day,k,o,clock)
                    if not b:missing+=1;continue
                    cost=book.average[(k,o)];price=b['close'];minima[(k,o)]=min(minima.get((k,o),cost),price)
                    if cost>0:losses.append(100*(price/cost-1));weights.append(-q)
                    if minima[(k,o)]>0:trails.append(100*(price/minima[(k,o)]-1))
                ce=sum(-q for k,o,q in active if o=='CE')/unit;pe=sum(-q for k,o,q in active if o=='PE')/unit
                longs=sum(q for q in book.inventory.values() if q>0)/unit;shorts=ce+pe
                current=[(when,roles) for when,roles in history if str(when.date())==day and when<t]
                completed=[p for p in known_pairs if datetime.fromisoformat(p['event_minute_ist'])+timedelta(minutes=1)<=t]
                last=max(completed,key=lambda p:p['first_leg_time_ist']) if completed else None
                spot=bars.get(clock);entry=numeric(last.get('reference_close')) if last else None
                known=[b for b in bars.values() if b['t']<=prev];latest=known[-1] if known else None
                r=dict(underlying=u,expiry_date=e,date=day,clock=t.strftime('%H:%M'),x_cutoff_ist=t.isoformat(),
                    x_phase_minute=i,x_spot_reference_age_minutes=(prev-latest['t']).total_seconds()/60 if latest else None,
                    x_last_known_spot_change_pct=100*(latest['close']/next(iter(bars.values()))['open']-1) if latest else None,
                    x_short_units=shorts,x_long_units=longs,x_short_ce_units=ce,x_short_pe_units=pe,
                    x_side_imbalance_units=ce-pe,x_hedge_coverage=longs/shorts if shorts else None,
                    x_max_short_loss_pct=max(losses) if losses and not missing else None,
                    x_mean_short_loss_pct=sum(v*w for v,w in zip(losses,weights))/sum(weights) if weights and not missing else None,
                    x_short_over4_fraction=sum(v>=4 for v in losses)/len(losses) if losses and not missing else None,
                    x_short_over25_fraction=sum(v>=25 for v in losses)/len(losses) if losses and not missing else None,
                    x_max_trailing_rise_pct=max(trails) if trails and not missing else None,
                    x_prior_pair_spot_gap_steps=(spot['close']-last['strike'])/logs.STEP[u] if spot and last else None,
                    x_spot_change_since_pair_pct=100*(spot['close']/entry-1) if spot and entry else None)
                for role in ('short','cover','long'):
                    past=[when for when,roles in current if role in roles]
                    r[f'x_since_{role}_minutes']=(t-past[-1]).total_seconds()/60 if past else None
                    for window in (5,15):r[f'x_{role}_orders_{window}m']=sum(t-timedelta(minutes=window)<=when for when in past)
                    r[f'x_{role}_orders_today']=len(past)
                for field in ('net_equity','short_book_equity','long_book_equity','realized_equity','unrealized_equity','short_unrealized','gross_losing_open'):
                    r['x_'+field+'_pct_capital']=mark[field]/20_000_000*100 if mark[field] is not None else None
                records.append(r)
        print('Extended causal state',u,e,flush=True)
    write('combo_context_features.csv.gz',records)
    return records


def load_context(include_flow=False):
    with gzip.open(OUT/'combo_context_features.csv.gz','rt') as f:rows=list(csv.DictReader(f))
    for r in rows:
        for k,v in r.items():
            if k.startswith('x_') and not k.endswith('_ist'):r[k]=numeric(v)
    if include_flow:
        with gzip.open(OUT/'combo_option_flow_features.csv.gz','rt') as f:flow=list(csv.DictReader(f))
        lookup={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in flow}
        for r in rows:
            extra=lookup[(r['underlying'],r['expiry_date'],r['date'],r['clock'])]
            r.update({k:numeric(v) for k,v in extra.items() if k.startswith('o_')})
    return rows


def datasets(rebuild=False,include_flow=False):
    contexts=build_context() if rebuild or not (OUT/'combo_context_features.csv.gz').exists() else load_context(include_flow)
    lookup={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in contexts}
    slow=load_base();fast=faster_feature_alignment(slow,reconstruct_parents(logs.read_fills()))
    for rows,embargo in ((slow,1),(fast,0)):
        for r in rows:
            t=datetime.fromisoformat(r['date']+'T'+r['clock']).replace(tzinfo=logs.IST)-timedelta(minutes=embargo)
            extra=lookup[(r['underlying'],r['expiry_date'],r['date'],t.strftime('%H:%M'))]
            if datetime.fromisoformat(extra['x_cutoff_ist'])!=t:raise ValueError('Context cutoff mismatch.')
            r.update({k:v for k,v in extra.items() if k.startswith(('x_','o_'))})
    return slow,fast


if __name__=='__main__':build_context()
