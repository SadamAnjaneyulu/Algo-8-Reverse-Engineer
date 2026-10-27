"""Side-by-side spot/options/Greek casebook and observable management mechanics.

No inferred association is an original basket ID. All feature snapshots precede
the first fill minute; execution prices and nearby actions describe outcomes.
"""
import csv
import json
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import ROOT, OUT, logs, Market
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def main():
    parents=load_parents(); fills=logs.read_fills(); index,_=logs.load_index()
    lag_rows=[]
    for p in parents:
        lag=(p['first'].replace(second=0,microsecond=0)-p['label']).total_seconds()/60
        if lag:
            lag_rows.append(dict(parent_id=p['parent_id'],underlying=p['underlying'],expiry_date=p['expiry_date'],role=p['role'],
                                 order_label_ist=p['label'].isoformat(),first_fill_ist=p['first'].isoformat(),label_to_fill_minutes=lag,
                                 quantity=p['quantity'],requested_quantity=p['requested_quantity']))
    save_records('deep_order_label_fill_lags.csv',lag_rows)
    grouped,meta=defaultdict(list),defaultdict(list)
    for p in parents:grouped[(p['underlying'],p['expiry_date'])].append(p)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());meta[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    context=pd.read_csv(OUT/'allocation_greek_context.csv.gz')
    features={tuple(r[k] for k in ('underlying','expiry_date','date','clock')):r for r in context.to_dict('records')}
    contracts=pd.read_csv(OUT/'allocation_contract_features.csv.gz')
    contracts['weighted_credit']=contracts.g_cost*contracts.g_short_units
    contracts['weighted_mark']=contracts.g_price*contracts.g_short_units
    side=contracts.groupby(['underlying','expiry_date','date','clock','option_type'],sort=False).agg(
        short_units=('g_short_units','sum'), credit=('weighted_credit','sum'), mark=('weighted_mark','sum'),
        worst_lot_loss=('g_fifo_max_loss_pct','max'), maximum_delta=('g_contract_abs_delta','max'))
    side['side_short_loss_pct']=100*(side.mark/side.credit-1)
    side=side.reset_index()
    sidefeatures={tuple(r[k] for k in ('underlying','expiry_date','date','clock','option_type')):r for r in side.to_dict('records')}
    casebook=[]; exposures=[]; hedge=[]; reentries=[]; fillbycycle=defaultdict(list)
    for f in fills:fillbycycle[(f['u'],str(f['expiry']))].append(f)
    for (u,e),batch in sorted(grouped.items()):
        market=Market(u,e,meta[(u,e)],index)
        roles=defaultdict(list)
        for p in batch:roles[(p['option_type'],p['role'])].append(p)
        for values in roles.values():values.sort(key=lambda p:p['first'])
        def nearby(right,role,t,seconds):
            values=roles[(right,role)]; times=[p['first'] for p in values]
            return values[bisect_left(times,t-timedelta(seconds=seconds)):bisect_right(times,t+timedelta(seconds=seconds))]
        inventory=Counter(); maxrows={}
        for f in fillbycycle[(u,e)]:
            inventory[(f['strike'],f['ot'])]+=f['signed']
            phase='preexpiry' if str(f['t'].date())<e else 'expiry'
            values={f'{right}_{role}':sum(max(sign*q,0) for (k,r),q in inventory.items() if r==right)
                    for right in ('CE','PE') for role,sign in (('short',-1),('long',1))}
            for key,value in values.items():
                if key not in maxrows or value>maxrows[key]['quantity']:
                    maxrows[key]=dict(underlying=u,expiry_date=e,phase_at_peak=phase,role=key,
                                      quantity=value,base_units=value/logs.UNIT[u],timestamp_ist=f['t'].isoformat())
        exposures.extend(maxrows.values())
        for p in sorted(batch,key=lambda x:(x['first'],x['sources'])):
            t=p['first'];day=str(t.date());clock=t.strftime('%H:%M');right=p['option_type'];phase='preexpiry' if day<e else 'expiry'
            ctx=features.get((u,e,day,clock),{})
            sd=sidefeatures.get((u,e,day,clock,right),{})
            priorclock=(t.replace(second=0,microsecond=0)-timedelta(minutes=1)).strftime('%H:%M')
            quote=market.bar(day,p['strike'],right,priorclock)
            row=dict(parent_id=p['parent_id'],underlying=u,expiry_date=e,phase=phase,role=p['role'],
                     option_type=right,strike=p['strike'],first_fill_ist=t.isoformat(),quantity=p['quantity'],
                     actual_fill_vwap=p['price'],feature_cutoff_ist=t.replace(second=0,microsecond=0).isoformat(),
                     contract_prior_close=quote['close'] if quote else '',
                     side_short_loss_pct=sd.get('side_short_loss_pct',''),
                     worst_fifo_lot_loss_pct=sd.get('worst_lot_loss',''))
            for field in ('g_spot','g_spot_return5_pct','g_spot_return15_pct','g_range15_pct','g_atm_iv_pct',
                          'g_book_delta_per_short_unit','g_book_vega_pct_capital','g_book_gamma_move1pct_pct_capital',
                          'g_book_theta_pct_capital','g_CE_equity_pct_capital','g_PE_equity_pct_capital',
                          'g_CE_short_units','g_PE_short_units','g_CE_long_units','g_PE_long_units'):
                row[field]=ctx.get(field,'')
            for delay in (5,15):
                oldclock=(t.replace(second=0,microsecond=0)-timedelta(minutes=1+delay)).strftime('%H:%M')
                old=market.bar(day,p['strike'],right,oldclock)
                row[f'contract_premium_change{delay}_pct']=100*(quote['close']/old['close']-1) if quote and old and old['close']>0 else ''
            casebook.append(row)
            if p['role']=='new_long':
                h=dict(parent_id=p['parent_id'],underlying=u,expiry_date=e,date=day,phase=phase,
                       option_type=right,first_fill_ist=t.isoformat(),quantity=p['quantity'],strike=p['strike'])
                for seconds in (1,5,30,60):
                    for role in ('new_short','short_cover','long_sell'):
                        h[f'{role}_within{seconds}s_quantity']=sum(q['quantity'] for q in nearby(right,role,t,seconds))
                h.update({k:row[k] for k in row if k.startswith('g_')})
                hedge.append(h)
            if p['role']=='new_short':
                closes=[c for c in roles[(right,'short_cover')] if str(c['first'].date())==day and c['first']<=t]
                last=max(closes,key=lambda c:c['first']) if closes else None
                seconds=(t-last['first']).total_seconds() if last else None
                r=dict(parent_id=p['parent_id'],underlying=u,expiry_date=e,date=day,phase=phase,
                       option_type=right,strike=p['strike'],quantity=p['quantity'],first_fill_ist=t.isoformat(),
                       prior_cover_seconds=seconds if seconds is not None else '',
                       prior_cover_strike=last['strike'] if last else '',prior_cover_quantity=last['quantity'] if last else '',
                       within_5_seconds=seconds is not None and seconds<=5,
                       within_5_minutes=seconds is not None and seconds<=300,
                       within_15_minutes=seconds is not None and seconds<=900,
                       at_quarter_window=(t.minute%15==14 and t.second>=58) or t.minute%15 in (0,1,2),
                       same_strike_as_cover=last is not None and last['strike']==p['strike'])
                reentries.append(r)
        print('Audited',u,e,flush=True)
    save_records('deep_event_market_casebook.csv.gz',casebook)
    save_records('deep_exposure_peaks.csv',exposures)
    save_records('deep_hedge_action_links.csv.gz',hedge)
    save_records('deep_reentry_actions.csv.gz',reentries)
    summaries=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            hs=[r for r in hedge if r['underlying']==u and r['phase']==phase]
            rs=[r for r in reentries if r['underlying']==u and r['phase']==phase]
            summary=dict(underlying=u,phase=phase,new_long_parents=len(hs),new_short_parents=len(rs),
                         long_with_new_short_5s=sum(r['new_short_within5s_quantity']>0 for r in hs),
                         long_with_new_short_30s=sum(r['new_short_within30s_quantity']>0 for r in hs),
                         long_without_new_short_but_with_long_sale_5s=sum(r['new_short_within5s_quantity']==0 and r['long_sell_within5s_quantity']>0 for r in hs),
                         long_without_near_short_or_long_sale_30s=sum(r['new_short_within30s_quantity']==r['long_sell_within30s_quantity']==0 for r in hs),
                         fresh_short_with_cover_5s=sum(r['within_5_seconds'] for r in rs),
                         fresh_short_with_cover_5min=sum(r['within_5_minutes'] for r in rs),
                         fresh_short_with_cover_15min=sum(r['within_15_minutes'] for r in rs))
            minutes=sorted({(r['date'],r['first_fill_ist'][:16]) for r in hs})
            gaps=[]
            for a,b in zip(minutes,minutes[1:]):
                if a[0]==b[0]:gaps.append((datetime.fromisoformat(b[1])-datetime.fromisoformat(a[1])).total_seconds()/60)
            summary.update(hedge_interevent_gaps=len(gaps),gap_15min=sum(g==15 for g in gaps),gap_50min=sum(g==50 for g in gaps))
            summaries.append(summary)
    save_records('deep_management_audit_summary.csv',summaries)
    # A side-minute grid retains non-events and prior-known reduction histories.
    byside=defaultdict(list)
    for f in fills:byside[(f['u'],str(f['expiry']),f['ot'])].append(f)
    targettimes=defaultdict(set)
    for p in parents:
        if p['role']=='new_short':targettimes[(p['underlying'],p['expiry_date'],str(p['first'].date()),p['option_type'])].add(p['first'].strftime('%H:%M'))
    entries=[]
    for (u,e,right),fs in sorted(byside.items()):
        pointer=0;last_cover=None;last_entry=None; recent=[]
        for c in sorted([r for r in features.values() if r['underlying']==u and r['expiry_date']==e],key=lambda r:(r['date'],r['clock'])):
            day,clock=c['date'],c['clock'];t=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=logs.IST)
            while pointer<len(fs) and fs[pointer]['t']<t:
                f=fs[pointer];pointer+=1
                if f['side']=='Buy' and f['q']>f['opening']:last_cover=f['t']
                if f['side']=='Sell' and f['opening']>0:last_entry=f['t']
                recent.append(f)
            recent=[f for f in recent if t-timedelta(minutes=15)<=f['t']<t]
            sd=sidefeatures.get((u,e,day,clock,right),{})
            r={**c,'option_type':right,'cycle':u+'|'+e,'contract':u+'|'+e+'|'+right,
               'target_cover':int(clock in targettimes[(u,e,day,right)]),'onset_eligible':1,
               'clock_minutes':t.hour*60+t.minute,
               'since_cover':(t-last_cover).total_seconds()/60 if last_cover and str(last_cover.date())==day else np.nan,
               'since_entry':(t-last_entry).total_seconds()/60 if last_entry and str(last_entry.date())==day else np.nan,
               'covers15_units':sum(f['q']-f['opening'] for f in recent if f['side']=='Buy')/logs.UNIT[u],
               'new_shorts15_units':sum(f['opening'] for f in recent if f['side']=='Sell')/logs.UNIT[u],
               'side_short_loss_pct':sd.get('side_short_loss_pct',np.nan),
               'maximum_delta':sd.get('maximum_delta',np.nan)}
            for suffix in ('equity_pct_capital','short_units','long_units','delta_per_short_unit','vega_pct_capital','theta_pct_capital','gamma_move1pct_pct_capital'):
                r['same_'+suffix]=c['g_'+right+'_'+suffix]
            sign=1 if right=='CE' else -1
            r['adverse_spot5_pct']=sign*c['g_spot_return5_pct'];r['adverse_spot15_pct']=sign*c['g_spot_return15_pct']
            r['net_equity']=c['g_CE_equity_pct_capital']+c['g_PE_equity_pct_capital']
            r['book_abs_delta']=abs(c['g_book_delta_per_short_unit'])
            r['hedge_ratio']=r['same_long_units']/r['same_short_units'] if r['same_short_units']>0 else np.nan
            entries.append(r)
    save_records('deep_side_minute_features.csv.gz',entries)
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
