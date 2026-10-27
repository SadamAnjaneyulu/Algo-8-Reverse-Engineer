"""Canonical evidence adapter and causal minute inputs; no alternative reference book."""
from __future__ import annotations
import csv, hashlib, json, struct, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'research'))
from analyze_index_triggers import load_index, IST, UNIT, STEP
from clarify_position_lifecycle import WINDOWS

OUT=HERE/'outputs'; CACHE=HERE/'.cache'
SLOTS=['09:16']+list(WINDOWS)
ROLES=['CE_short','PE_short','CE_long','PE_long']
FEATURES=['spot','return15','range15','efficiency15','opening_range','opening_efficiency','atm_iv_pct','tau_days']


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def split(expiry):return 0 if expiry<='2026-07-31' else 1 if expiry<='2026-08-31' else 2

def mode(values):
    a,n=np.unique(np.asarray(values),return_counts=True)
    return float(a[np.flatnonzero(n==n.max())[0]]) if len(a) else 0.


def build():
    OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    files={name:ROOT/'research/outputs'/name for name in ['playbook_fill_ledger.csv.gz','playbook_event_book.csv.gz','playbook_allocation_windows.csv','allocation_greek_context.csv.gz','option_minute_portfolio_replay.csv']}
    fills=pd.read_csv(files['playbook_fill_ledger.csv.gz']);events=pd.read_csv(files['playbook_event_book.csv.gz'])
    windows=pd.read_csv(files['playbook_allocation_windows.csv']);greeks=pd.read_csv(files['allocation_greek_context.csv.gz'])
    index,_=load_index(); metadata={}; input_hashes={str(p.relative_to(ROOT)):digest(p) for p in files.values()}
    for p in sorted((ROOT/'data/breeze/metadata/options').rglob('*.json')):
        m=json.loads(p.read_text());c=m['contract'];key=(c['underlying'],c['expiry_date'])
        metadata.setdefault(key,[]).append(m)
        input_hashes[str(p.relative_to(ROOT))]=digest(p)
    # Attach existing audit state without relabeling an order timestamp as a decision.
    context=events[[c for c in events.columns if c not in fills.columns or c in ['underlying','expiry_date','timestamp_ist']]]
    canonical=fills.merge(context,on=['underlying','expiry_date','timestamp_ist'],validate='many_to_one')
    canonical['clock']=canonical.timestamp_ist.str[11:16]
    market_columns=['underlying','expiry_date','date','clock','g_spot_return5_pct','g_range5_pct','g_spot_return15_pct','g_range15_pct','g_atm_iv_pct','g_tau_days']
    canonical=canonical.merge(greeks[market_columns],on=['underlying','expiry_date','date','clock'],validate='many_to_one',how='left')
    canonical['market_available_at_ist']=(pd.to_datetime(canonical.quote_bar_start_ist)+pd.Timedelta(minutes=1)).astype(str)
    canonical['inferred_decision_ist']='unobserved'
    canonical['timestamp_quality']='event seconds corroborated to export minute; exchange semantics unverified'
    canonical['account_margin']='unavailable';canonical['supplied_capital_reference']=20000000
    canonical['inventory_opening_is_intentional_allocation']='unidentified'
    canonical.to_csv(OUT/'canonical_events.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    events.to_csv(OUT/'canonical_atomic_books.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    schedules=np.zeros((2,2,len(SLOTS),4),np.float64);pooled=schedules.copy()
    fit=windows[windows.expiry_date.le('2026-07-31')]
    for u in range(2):
        name=['NIFTY','SENSEX'][u]
        for ph in range(2):
            phase=['preexpiry','expiry'][ph]
            for s,clock in enumerate(SLOTS):
                for r,role in enumerate(ROLES):
                    schedules[u,ph,s,r]=mode(fit[(fit.underlying==name)&(fit.phase==phase)&(fit.clock==clock)]['units_'+role].dropna())
                    pooled[u,ph,s,r]=mode(fit[(fit.phase==phase)&(fit.clock==clock)]['units_'+role].dropna())
    caps=[]
    for u,name in enumerate(['NIFTY','SENSEX']):
        g=greeks[(greeks.underlying==name)&greeks.expiry_date.le('2026-07-31')]
        caps.append(dict(index=name,side_units=float(max(g.g_CE_short_units.quantile(.95),g.g_PE_short_units.quantile(.95))),
                         vega_rupees=float((g.g_book_vega_pct_capital.abs()*200000).quantile(.95)),
                         iv_pct=float(g.g_atm_iv_pct.median())))
    calibration=dict(slots=SLOTS,roles=ROLES,index_clock=schedules.tolist(),pooled_clock=pooled.tolist(),caps=caps,
                     fit_through='2026-07-31',tie_break='smallest mode; all zero slots retained; no later fitting')
    (OUT/'calibration.json').write_text(json.dumps(calibration,indent=2))
    cycle_meta=[]; arrays=[]; coverage=[]; reference_fills=[]
    for cid,((u,e),fs) in enumerate(fills.groupby(['underlying','expiry_date'],sort=True)):
        days=sorted(fs.date.unique());contracts=sorted({(int(m['contract']['strike']),m['contract']['option_type']) for m in metadata[(u,e)]}|set(zip(fs.strike.astype(int),fs.option_type)))
        lookup={c:i for i,c in enumerate(contracts)}; rows=[]
        for day in days:
            end='15:30' if day<'2026-08-03' else '15:40'
            rows.extend(pd.date_range(day+' 09:15',day+' '+end,freq='min',tz=IST))
        times=pd.DatetimeIndex(rows);T,C=len(times),len(contracts);timemap={t.isoformat():i for i,t in enumerate(times)}
        o=np.full((T,C),np.nan,np.float32);cl=o.copy();vol=o.copy()
        for m in metadata[(u,e)]:
            p=ROOT/'data/breeze'/m['normalized_path'];assert digest(p)==m['normalized_sha256']
            input_hashes[str(p.relative_to(ROOT))]=m['normalized_sha256']
            q=pd.read_csv(p);j=lookup[(int(m['contract']['strike']),m['contract']['option_type'])]
            for row in q.itertuples():
                t=timemap.get(row.timestamp_ist)
                if t is not None:o[t,j]=row.open;cl[t,j]=row.close;vol[t,j]=row.volume
        previous=np.full_like(o,np.nan);previous_volume=np.full_like(o,np.nan)
        features=np.full((T,len(FEATURES)),np.nan,np.float64)
        gg=greeks[(greeks.underlying==u)&(greeks.expiry_date==e)].set_index(['date','clock'])
        for t,stamp in enumerate(times):
            before=stamp-pd.Timedelta(minutes=1);prev=timemap.get(before.isoformat())
            if prev is not None:previous[t]=cl[prev];previous_volume[t]=vol[prev]
            day=stamp.date().isoformat();past=[b for b in index.get((u,day),[]) if b['t']+pd.Timedelta(minutes=1)<=stamp]
            if past and past[-1]['t']+pd.Timedelta(minutes=1)==stamp:
                spot=past[-1]['close'];features[t,0]=spot
                first=past[0]
                if first['t'].strftime('%H:%M')=='09:15':
                    features[t,4]=100*(first['high']-first['low'])/first['open']
                    if first['high']>first['low']:features[t,5]=abs(first['close']-first['open'])/(first['high']-first['low'])
                    else:features[t,5]=0.
                if len(past)>=16 and (past[-1]['t']-past[-16]['t']).total_seconds()==900:
                    prices=np.array([b['close'] for b in past[-16:]]);path=np.abs(np.diff(prices)).sum()
                    features[t,1]=100*(prices[-1]/prices[0]-1)
                    features[t,2]=100*(max(b['high'] for b in past[-15:])-min(b['low'] for b in past[-15:]))/prices[0]
                    features[t,3]=abs(prices[-1]-prices[0])/path if path else 0.
            key=(day,stamp.strftime('%H:%M'))
            if key in gg.index:
                row=gg.loc[key];features[t,6]=row.g_atm_iv_pct
            expiry_time=pd.Timestamp(e+(' 15:35' if e>='2026-08-03' else ' 15:30'),tz=IST)
            features[t,7]=(expiry_time-stamp).total_seconds()/86400
        # Flat-ATM surface Greeks are simulation approximations, never observed portfolio Greeks.
        strike=np.array([k for k,r in contracts],float)[None,:];right=np.array([0 if r=='CE' else 1 for k,r in contracts],np.int32)
        sigma=features[:,6,None]/100;tau=features[:,7,None]/365;spot=features[:,0,None]
        with np.errstate(invalid='ignore',divide='ignore',over='ignore'):
            d1=(np.log(spot/strike)+.5*sigma*sigma*tau)/(sigma*np.sqrt(tau));density=np.exp(-.5*d1*d1)/np.sqrt(2*np.pi)
            delta=(ndtr(d1)-right[None,:]).astype(np.float32)
            vega=(spot*density*np.sqrt(tau)/100).astype(np.float32)
            gamma=(density/(spot*sigma*np.sqrt(tau))).astype(np.float32)
        actual=np.zeros((T,C,4),np.int32);pos=np.zeros((T,C),np.int32);cash=np.zeros(T,np.float64)
        for row in fs.itertuples():
            t=timemap[pd.Timestamp(row.timestamp_ist).floor('min').isoformat()];j=lookup[(row.strike,row.option_type)]
            reference_fills.append((cid,t,j,int(row.incremental_quantity)*(1 if row.side=='Buy' else -1),float(row.execution_price)))
            role=(0 if row.side=='Sell' else 1) if row.opening_quantity else (3 if row.side=='Sell' else 2)
            # General split fills can contain both a close and opening component.
            if row.opening_quantity:actual[t,j,0 if row.side=='Sell' else 2]+=int(row.opening_quantity)
            if row.closing_quantity:actual[t,j,1 if row.side=='Buy' else 3]+=int(row.closing_quantity)
            pos[t,j]+=int(row.incremental_quantity)*(1 if row.side=='Buy' else -1)
            cash[t]+=row.cash_change
        pos=np.cumsum(pos,axis=0,dtype=np.int32);cash=np.cumsum(cash)
        ev=events[(events.underlying==u)&(events.expiry_date==e)].sort_values('timestamp_ist')
        # Existing atomic book is the canonical reference for all minute boundaries.
        for t,g in ev.groupby(ev.timestamp_ist.str[:16],sort=True):
            stamp=pd.Timestamp(t,tz=IST);j=timemap[stamp.isoformat()]
            expect=np.zeros(C,np.int32)
            for k,r,q,cost in json.loads(g.iloc[-1].after_positions):expect[lookup[(k,r)]]=q
            assert np.array_equal(pos[j],expect)
        clock=np.array([x.hour*60+x.minute for x in times],np.int32)
        session=np.array([days.index(x.date().isoformat()) for x in times],np.int32)
        phase=np.array([int(x.date().isoformat()==e) for x in times],np.int32)
        a=dict(cid=cid,u=int(u=='SENSEX'),split=split(e),base=UNIT[u],step=STEP[u],strikes=strike[0].astype(np.int32),rights=right,
               minutes=(times.asi8//60000000000).astype(np.int32),clock=clock,session=session,phase=phase,
               feature=features,previous=previous,open=o,previous_volume=previous_volume,volume=vol,delta=delta,vega=vega,gamma=gamma,
               actual=actual,observed=pos,cash=cash)
        arrays.append(a);np.savez_compressed(CACHE/f'cycle_{cid:02}.npz',**a)
        cycle_meta.append(dict(cycle_id=cid,underlying=u,expiry_date=e,split=['fit_Jun_Jul','validation_Aug','later_Sep_Oct'][split(e)],dates=days,contracts=contracts,
                               minutes=T,base_unit=UNIT[u],strike_grid=STEP[u]))
        coverage.append(dict(cycle_id=cid,index=u,expiry=e,minutes=T,contracts=C,market_spot_available=int(np.isfinite(features[:,0]).sum()),
                             iv_available=int(np.isfinite(features[:,6]).sum()),quote_cells=int(np.isfinite(previous).sum()),total_quote_cells=T*C,
                             actual_action_cells=int((actual>0).sum()),first_received_session=days[0],eligibility='conditional on received sessions'))
        print(f'Prepared {cid+1}/35 {u} {e}: {T} minutes, {C} contracts',flush=True)
    # Versioned, little-endian binary stream consumed by the C++ simulation kernel.
    with (CACHE/'replay.bin').open('wb') as f:
        f.write(struct.pack('<ii',80301,len(arrays)))
        for a in arrays:
            T,C=a['observed'].shape
            f.write(struct.pack('<8i',a['cid'],a['u'],a['split'],T,C,a['base'],a['step'],int(cycle_meta[a['cid']]['expiry_date'].replace('-',''))))
            for n in ['strikes','rights','minutes','clock','session','phase']:f.write(a[n].astype('<i4').tobytes())
            f.write(a['feature'].astype('<f8').tobytes())
            for n in ['previous','open','previous_volume','volume','delta','vega','gamma']:f.write(a[n].astype('<f4').tobytes())
            for n in ['actual','observed']:f.write(a[n].astype('<i4').tobytes())
            f.write(a['cash'].astype('<f8').tobytes())
    with (CACHE/'reference_fills.bin').open('wb') as ref:
        ref.write(struct.pack('<i',len(reference_fills)))
        for row in reference_fills:ref.write(struct.pack('<iiiid',*row))
    pd.DataFrame(coverage).to_csv(OUT/'data_coverage.csv',index=False)
    (OUT/'cycle_metadata.json').write_text(json.dumps(cycle_meta,indent=2))
    for p in sorted((ROOT/'data/breeze/normalized/indices').rglob('*.csv')):input_hashes[str(p.relative_to(ROOT))]=digest(p)
    for p in list(ROOT.glob('Trades*.csv'))+[ROOT/'Info.txt']:input_hashes[str(p.relative_to(ROOT))]=digest(p)
    (OUT/'input_hashes.json').write_text(json.dumps(input_hashes,sort_keys=True,indent=2))
    print('Canonical fill count',len(canonical),'atomic events',len(events),'binary MB',round((CACHE/'replay.bin').stat().st_size/1e6,1))

if __name__=='__main__':build()
