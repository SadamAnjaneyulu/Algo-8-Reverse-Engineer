"""Past-known same-strike option volume/OI context; zero OI stays unavailable."""
import csv
import json
from collections import defaultdict,Counter
from datetime import datetime,timedelta

import numpy as np
from audit_strike_hedge_rules import ROOT,OUT,logs,write


def flow_grid(columns):
    rules=[]
    for field in columns:
        if not field.startswith('o_'):continue
        if 'pcr' in field:levels=(.25,.5,.75,1,1.25,1.5,2,3,5)
        elif 'change' in field:levels=(-20,-10,-5,-2,-1,0,1,2,5,10,20)
        elif 'relative_volume' in field:levels=(.25,.5,1,1.5,2,3,5,10)
        elif 'quadrant' in field or 'missing' in field:levels=(.5,)
        else:levels=(0,100,1000,10000,100000,1000000)
        for level in levels:
            for op in ('le','gt'):
                rules.append((field,op,float(level),'state'));rules.append((field,op,float(level),'cross'))
    return rules


def main():
    from combo_features import load_context
    contexts=load_context();bycycle=defaultdict(list);metadata=defaultdict(list);coverage=Counter()
    for r in contexts:bycycle[(r['underlying'],r['expiry_date'])].append(r)
    index,_=logs.load_index();pairs=logs.pairing(logs.read_fills(),index)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    result=[]
    for (u,e),rows in sorted(bycycle.items()):
        quotes={}
        for m in metadata[(u,e)]:
            c=m['contract'];bars={}
            with (ROOT/'data/breeze'/m['normalized_path']).open() as f:
                for r in csv.DictReader(f):
                    oi=float(r['open_interest']) if r['open_interest'] else 0
                    bars[r['timestamp_ist'][11:16]]=dict(close=float(r['close']),volume=float(r['volume']),oi=oi if oi>0 else None)
                    coverage[(u,'bars')]+=1;coverage[(u,'positive_oi')]+=oi>0
            quotes[(c['trade_date'],c['strike'],c['option_type'])]=bars
        known=[p for p in pairs if p['underlying']==u and p['expiry_date']==e]
        def bar(day,k,right,clock):return quotes.get((day,k,right),{}).get(clock)
        for row in rows:
            t=datetime.fromisoformat(row['x_cutoff_ist']);prev=t-timedelta(minutes=1);day=row['date'];clock=prev.strftime('%H:%M')
            past=[p for p in known if datetime.fromisoformat(p['event_minute_ist'])+timedelta(minutes=1)<=t]
            last=max(past,key=lambda p:p['first_leg_time_ist']) if past else None
            r=dict(underlying=u,expiry_date=e,date=day,clock=row['clock'],
                flow_reference_strike=last['strike'] if last else None,
                flow_reference_pair_minute_ist=last['event_minute_ist'] if last else '',flow_bar_start_ist=prev.isoformat())
            fields=['o_volume_pcr','o_oi_pcr','o_oi_missing']
            for right in ('ce','pe'):
                fields += [f'o_{right}_relative_volume_5',f'o_{right}_relative_volume_15',f'o_{right}_oi_change_1',f'o_{right}_oi_change_5',f'o_{right}_oi_change_15',f'o_{right}_price_oi_quadrant_upup',f'o_{right}_price_oi_quadrant_downup']
            r.update({field:None for field in fields})
            if last:
                k=last['strike'];c,p=bar(day,k,'CE',clock),bar(day,k,'PE',clock)
                r['o_oi_missing']=int(not(c and p and c['oi'] is not None and p['oi'] is not None))
                if c and p:
                    if c['volume']>0:r['o_volume_pcr']=p['volume']/c['volume']
                    if c['oi'] is not None and p['oi'] is not None:r['o_oi_pcr']=p['oi']/c['oi']
                for right in ('CE','PE'):
                    now=bar(day,k,right,clock)
                    if now is None:continue
                    for window in (1,5,15):
                        old=bar(day,k,right,(prev-timedelta(minutes=window)).strftime('%H:%M'))
                        if old and now['oi'] is not None and old['oi'] is not None:
                            r[f'o_{right.lower()}_oi_change_{window}']=100*(now['oi']/old['oi']-1)
                            if window==5:
                                r[f'o_{right.lower()}_price_oi_quadrant_upup']=int(now['close']>old['close'] and now['oi']>old['oi'])
                                r[f'o_{right.lower()}_price_oi_quadrant_downup']=int(now['close']<old['close'] and now['oi']>old['oi'])
                        if window in (5,15):
                            oldbars=[bar(day,k,right,(prev-timedelta(minutes=j)).strftime('%H:%M')) for j in range(1,window+1)]
                            if all(oldbars):
                                average=sum(b['volume'] for b in oldbars)/window
                                if average>0:r[f'o_{right.lower()}_relative_volume_{window}']=now['volume']/average
            result.append(r)
    write('combo_option_flow_features.csv.gz',result)
    summary={u:dict(bars=coverage[(u,'bars')],positive_oi=coverage[(u,'positive_oi')]) for u in ('NIFTY','SENSEX')}
    (OUT/'combo_option_flow_summary.json').write_text(json.dumps(dict(coverage=summary,context_rows=len(result),
        note='Reference is a previously executed paired strike with a completed minute. OI changes use the same strike; zero OI is missing, not a flat signal. Price/OI sign quadrants do not identify buyer/seller intent.'),indent=2)+'\n')


if __name__=='__main__':main()
