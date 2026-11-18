"""Hedge refresh timing versus old-hedge decay, moneyness and portfolio risk."""
import csv
import json
from collections import defaultdict
from datetime import datetime,timedelta

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import ROOT,OUT,logs,Market,pricing
from analyze_side_allocations import load_parents
from refine_exit_scopes import RoleBook
from deep_controller_search import Atom,search_group,crossing_mask
from rank_trigger_probabilities import save_records


def hedge_catalog(d):
    specs={'hedge_fraction_cost':[.1,.2,.25,.3,.4,.5,.6,.75,1,1.25,1.5,2,3],
           'hedge_fraction_atm':[.001,.0025,.005,.0075,.01,.0125,.015,.02,.025,.03,.04,.05,.075,.1],
           'hedge_price':[.1,.2,.25,.3,.5,.75,1,1.5,2,3,5,7,10,15,20],
           'hedge_abs_delta':[.001,.005,.01,.02,.025,.03,.05,.075,.1,.15,.2,.3],
           'outward_distance_pct':[.25,.5,.75,1,1.5,2,3,4,5,7.5],
           'g_book_delta_per_short_unit':[-.4,-.3,-.2,-.1,0,.1,.2,.3,.4],
           'g_book_vega_pct_capital':[-1,-.75,-.5,-.25,-.1,-.05,0],
           'g_book_gamma_move1pct_pct_capital':[-15,-10,-7.5,-5,-3,-2,-1,0],
           'adverse_spot5_pct':[-.5,-.25,-.1,-.05,0,.05,.1,.2,.3,.5],
           'adverse_spot15_pct':[-.5,-.25,-.1,0,.1,.2,.3,.5,1],
           'g_atm_iv_pct':[10,12,15,18,20,25,30],
           'g_range15_pct':[.05,.1,.2,.3,.5,.75,1]}
    positions=pd.Series(np.arange(len(d)),index=d.index).groupby([d.contract,d.date],sort=False).shift().to_numpy()
    previous_clock=d.groupby(['contract','date'],sort=False).clock_minutes.shift().to_numpy()
    consecutive=np.isfinite(positions)&(d.clock_minutes.to_numpy()-previous_clock==1)
    trigger=[];filters=[]
    for field,levels in specs.items():
        v=d[field].to_numpy(float)
        for level in levels:
            for op in ('>=','<='):
                mask=np.isfinite(v)&((v>=level) if op=='>=' else v<=level)
                text=f'{field} {op} {level:g}'
                trigger.extend([Atom(text,field,mask),Atom('CROSS('+text+')',field,crossing_mask(mask,positions,consecutive))])
                if level in levels[::2]:filters.append(Atom(text,field,mask))
    gates=[Atom('ALWAYS','always',np.ones(len(d),bool))]
    for level in (600,660,720,780,840,870,900):
        gates.append(Atom(f'clock_minutes >= {level}','clock_minutes',d.clock_minutes.to_numpy()>=level))
    return trigger,filters,gates


def main():
    parents={p['parent_id']:p for p in load_parents()};targets=set()
    for r in csv.DictReader((OUT/'deep_hedge_refresh_pairs.csv').open()):
        p=parents[r['sell_parent']]
        targets.add((p['underlying'],p['expiry_date'],str(p['first'].date()),p['first'].strftime('%H:%M'),p['strike'],p['option_type']))
    context=pd.read_csv(OUT/'allocation_greek_context.csv.gz')
    meta=defaultdict(list);fills=defaultdict(list)
    for f in logs.read_fills():fills[(f['u'],str(f['expiry']))].append(f)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());meta[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index();rows=[]
    for (u,e),cs in context.groupby(['underlying','expiry_date'],sort=True):
        market=Market(u,e,meta[(u,e)],index);book=RoleBook();pointer=0;fs=fills[(u,e)]
        for c in cs.sort_values(['date','clock']).to_dict('records'):
            day,clock=c['date'],c['clock'];t=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=logs.IST)
            while pointer<len(fs) and fs[pointer]['t']<t:book.apply(fs[pointer]);pointer+=1
            if not (555<=t.hour*60+t.minute<=939):continue
            prior_clock=(t-timedelta(minutes=1)).strftime('%H:%M')
            state=market.state(day,prior_clock)
            guides=[b for b in index.get((u,day),[]) if b['t']<t]
            guide=state['forward'] if state else guides[-1]['close'] if guides else None
            if guide is None:continue
            atm_strike=state['strike'] if state else logs.round_strike(guide,u)
            for (k,right),q in book.inventory.items():
                if q<=0:continue
                quote=market.bar(day,k,right,prior_clock)
                atm=market.bar(day,atm_strike,right,prior_clock)
                if not quote or not atm or atm['close']<=0:continue
                p=quote['close'];cost=book.average[(k,right)]
                iv=pricing.implied_vol(p,state['forward'],k,state['tau'],right,state['rate']) if state else None
                delta=abs(pricing.greeks(state['forward'],k,state['tau'],iv,right,state['rate'])['delta']) if iv is not None else np.nan
                sign=1 if right=='CE' else -1
                rows.append(dict(**c,option_type=right,strike=k,contract=f'{u}|{e}|{k}|{right}',cycle=u+'|'+e,
                                 target_cover=int((u,e,day,clock,k,right) in targets),onset_eligible=1,
                                 clock_minutes=t.hour*60+t.minute,hedge_price=p,
                                 hedge_fraction_cost=p/cost if cost>0 else np.nan,
                                 hedge_fraction_atm=p/atm['close'],hedge_abs_delta=delta,
                                 outward_distance_pct=sign*(k/guide-1)*100,
                                 adverse_spot5_pct=sign*c['g_spot_return5_pct'],adverse_spot15_pct=sign*c['g_spot_return15_pct']))
        print('Hedge timing paths',u,e,flush=True)
    d=pd.DataFrame(rows);save_records('deep_hedge_timing_features.csv.gz',rows)
    represented={(r['underlying'],r['expiry_date'],r['date'],r['clock'],r['strike'],r['option_type']) for r in rows}
    excluded=[dict(underlying=u,expiry_date=e,date=day,clock=clock,strike=k,option_type=right,
                   reason='No held-long, preceding quote, ATM quote or index guide in the feature grid')
              for u,e,day,clock,k,right in sorted(targets-represented)]
    save_records('deep_hedge_timing_excluded_targets.csv',excluded)
    summaries=[];evaluation=[];predictions=[]
    for phase in ('preexpiry','expiry'):
        for u in ('NIFTY','SENSEX'):
            sample=d[(d.phase==phase)&(d.underlying==u)].copy()
            if sample.empty or sample[sample.split=='calibration'].target_cover.sum()==0:continue
            s,ev,pr=search_group(sample,phase+'|'+u+'|hedge_refresh',hedge_catalog)
            summaries.append(s);evaluation.extend(ev);predictions.extend(pr)
    save_records('deep_hedge_timing_evaluation.csv',evaluation)
    save_records('deep_hedge_timing_event_predictions.csv.gz',predictions)
    (OUT/'deep_hedge_timing_summary.json').write_text(json.dumps(dict(programs_scored=sum(s['programs_scored'] for s in summaries),groups=summaries,
        observable_refresh_contract_minutes=len(targets),positive_contract_minutes=int(d.target_cover.sum()),excluded_contract_minutes=len(excluded),
        note='Targets are equal-quantity different-strike long replacements within five seconds, with no nearby same-right new short. Associations may be ambiguous. Prior-known held-long states and minute bars; actual book is conditioned upon. Data are not independent of earlier research.'),indent=2)+'\n')


if __name__=='__main__':main()
