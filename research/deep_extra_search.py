"""Extra entries: recent closures, delays, risk capacity and market conditions."""
import json
import time

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import OUT
from deep_controller_search import Atom, search_group, crossing_mask
from rank_trigger_probabilities import save_records


def entry_catalog(d):
    trigger=[];filters=[]
    positions=pd.Series(np.arange(len(d)),index=d.index).groupby([d.contract,d.date],sort=False).shift().to_numpy()
    oldclock=d.groupby(['contract','date'],sort=False).clock_minutes.shift().to_numpy()
    consecutive=np.isfinite(positions)&(d.clock_minutes.to_numpy()-oldclock==1)
    specs={
        'since_cover':[0,1,2,3,4,5,7,10,15,20,30,45,60],
        'since_entry':[1,2,3,5,7,10,15,20,30,45,60],
        'covers15_units':[0,1,2,3,4,5,10,15,20],
        'new_shorts15_units':[0,1,2,3,4,5,10,15,20],
        'side_short_loss_pct':[-75,-50,-25,0,4,10,25,50,75,100],
        'adverse_spot5_pct':[-.5,-.25,-.1,-.05,0,.05,.1,.2,.3,.5],
        'adverse_spot15_pct':[-.5,-.25,-.1,0,.1,.2,.3,.5,.75,1],
        'g_range15_pct':[.05,.1,.15,.2,.3,.4,.5,.75,1],
        'same_equity_pct_capital':[-1,-.75,-.5,-.25,-.1,0,.1,.25,.5,.75,1],
        'net_equity':[-1,-.75,-.5,-.25,-.1,0,.1,.25,.5,.75,1],
        'book_abs_delta':[.025,.05,.1,.15,.2,.3,.4],
        'maximum_delta':[.4,.5,.6,.7,.8,.9],
        'g_book_vega_pct_capital':[-1,-.75,-.5,-.25,-.1,-.05,0],
        'g_book_gamma_move1pct_pct_capital':[-15,-10,-7.5,-5,-3,-2,-1,0],
        'same_short_units':[1,3,5,10,15,20,25,30,40,50,60],
        'hedge_ratio':[.5,.75,.9,1,1.1,1.25,1.5,2],
    }
    for field,levels in specs.items():
        values=d[field].to_numpy(float)
        for level in levels:
            for operator in ('>=','<='):
                state=np.isfinite(values)&((values>=level) if operator=='>=' else values<=level)
                text=f'{field} {operator} {level:g}'
                trigger.append(Atom(text,field,state))
                trigger.append(Atom('CROSS('+text+')',field,crossing_mask(state,positions,consecutive)))
                # A coarser second condition limits redundant tiny threshold changes.
                if level in levels[::2]:filters.append(Atom(text,field,state))
    gates=[Atom('ALWAYS','always',np.ones(len(d),bool))]
    for field,levels in {'clock_minutes':[600,660,720,780,840],
                         'since_cover':[1,3,5,10,15],
                         'since_entry':[1,3,5,10,15]}.items():
        values=d[field].to_numpy(float)
        for level in levels:
            gates.append(Atom(f'{field} >= {level:g}',field,np.isfinite(values)&(values>=level)))
    return trigger,filters,gates


def main():
    started=time.monotonic();d=pd.read_csv(OUT/'deep_side_minute_features.csv.gz')
    clock=d.clock_minutes
    # Whole-minute exclusions avoid labeling a T-2-second timer fill as extra.
    active=(d.g_CE_short_units+d.g_PE_short_units)>0
    clean=~((clock<=870)&((clock%15).isin([14,0,1,2])))
    d=d[active&clean&(clock>=573)&(clock<=883)].copy()
    summaries=[];evaluation=[];predictions=[]
    for phase in ('preexpiry','expiry'):
        for u in ('NIFTY','SENSEX'):
            s,e,p=search_group(d[(d.phase==phase)&(d.underlying==u)].copy(),phase+'|'+u+'|extra_side',entry_catalog)
            summaries.append(s);evaluation.extend(e);predictions.extend(p)
    save_records('deep_extra_search_evaluation.csv',evaluation)
    save_records('deep_extra_search_event_predictions.csv.gz',predictions)
    (OUT/'deep_extra_search_summary.json').write_text(json.dumps(dict(programs_scored=sum(s['programs_scored'] for s in summaries),
        seconds=time.monotonic()-started,groups=summaries,
        note='Conditional on actual prior active book. Side-minute labels differ from paired-basket labels. Timer-neighbor whole minutes excluded. No later threshold selection, independent alpha or recovered original controller is implied.'),indent=2)+'\n')


if __name__=='__main__':main()
