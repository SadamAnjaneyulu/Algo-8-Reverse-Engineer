"""Descriptive per-option IV Shapley decomposition with explicit residuals."""
from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
from scipy.special import ndtr
from inputs import HERE,META,ROLES,fills,cycle_data,actual_path,iso,save
VARIANTS={'primary':(0.,0,False),'rate_6pct':(.06,0,False),'expiry_5min_earlier':(0.,-5,False),'expiry_5min_later':(0.,5,False),'spot_only_forward':(0.,0,True)}

def black(F,K,tau,sigma,right,rate=0):
    t=np.maximum(tau,1e-15);v=np.maximum(sigma,1e-12)*np.sqrt(t);d1=np.log(np.maximum(F,1)/K)/v+v/2;d2=d1-v
    return np.exp(-rate*t)*np.where(right==0,F*ndtr(d1)-K*ndtr(d2),K*ndtr(-d2)-F*ndtr(-d1))
def fit_iv(price,F,K,tau,right,rate=0):
    intrinsic=np.exp(-rate*np.maximum(tau,0))*np.where(right==0,np.maximum(F-K,0),np.maximum(K-F,0))
    valid=np.isfinite(price+F+K+tau)&(F>0)&(tau>0)&(price-intrinsic>.025)&(price<np.exp(-rate*np.maximum(tau,0))*np.where(right==0,F,K))
    valid&=black(F,K,tau,np.full(len(price),5.),right,rate)>=price
    low=np.full(len(price),.0001);high=np.full(len(price),5.)
    for _ in range(42):
        mid=(low+high)/2;p=black(F,K,tau,mid,right,rate);below=p<price;low=np.where(below,mid,low);high=np.where(below,high,mid)
    return np.where(valid,(low+high)/2,np.nan)
def shapley(F0,t0,s0,F1,t1,s1,K,right,rate=0):
    prices=[black(F1 if mask&1 else F0,K,t1 if mask&2 else t0,s1 if mask&4 else s0,right,rate) for mask in range(8)]
    parts=[]
    for j in range(3):
        part=np.zeros(len(K))
        for mask in range(8):
            if mask&(1<<j):continue
            size=mask.bit_count();weight=1/3 if size in [0,2] else 1/6;part+=weight*(prices[mask|(1<<j)]-prices[mask])
        parts.append(part)
    return parts

def run():
    f=fills();role_results=pd.read_csv(HERE/'role_economic_results.csv');rows=[];intervals=[];phase_rows=[]
    for cid,fs in f.groupby('cycle_id',sort=True):
        m=META[cid];z=cycle_data(cid);a=actual_path(fs,z);T,C=z['close'].shape;rr=z['rights'];K=z['strikes'];dates=np.array([iso(int(t)*60)[:10] for t in z['minutes']]);lookup={(int(k),int(r)):j for j,(k,r) in enumerate(zip(K,rr))}
        # A parity-derived forward is a proxy, not an observed futures quote.
        basis={}
        for field in ['open','close']:
            b=np.full((T,C),np.nan)
            for k in np.unique(K):
                ce,pe=lookup.get((int(k),0)),lookup.get((int(k),1))
                if ce is None or pe is None:continue
                valid=(z[field][:,ce]>.025)&(z[field][:,pe]>.025)&(z['volume'][:,ce]>0)&(z['volume'][:,pe]>0)
                b[valid,ce]=z[field][valid,ce]-z[field][valid,pe];b[valid,pe]=b[valid,ce]
            basis[field]=b
        d=defaultdict_list()
        def add(i,pidx,field0,field1,start,end,phase):
            q=a['before'][i];js=np.flatnonzero(q)
            if not len(js):return
            for name,val in dict(cycle_id=np.full(len(js),cid),strike=K[js],right=rr[js],role=np.where(q[js]<0,0,2)+rr[js],quantity=q[js],
                phase=np.full(len(js),phase),start_second=np.full(len(js),start),end_second=np.full(len(js),end),
                p0=z[field0][pidx,js],p1=z[field1][i,js],spot0=np.full(len(js),z['spot_'+field0][pidx]),spot1=np.full(len(js),z['spot_'+field1][i]),
                basis0=basis[field0][pidx,js],basis1=basis[field1][i,js],volume0=z['volume'][pidx,js],volume1=z['volume'][i,js]).items():d[name].append(val)
        for i in range(T):
            phase='expiry' if dates[i]==m['expiry_date'] else 'preexpiry';start=int(z['minutes'][i]*60);end=start+60
            if i>0 and dates[i]!=dates[i-1]:
                add(i,i-1,'close','open',int((z['minutes'][i-1]+1)*60),start,'overnight');add(i,i,'open','close',start,end,phase)
            elif i>0:add(i,i-1,'close','close',int((z['minutes'][i-1]+1)*60),end,phase)
            else:add(i,i,'open','close',start,end,phase)
        dd={k:np.concatenate(v) for k,v in d.items()};N=len(dd['quantity']);p0,p1=dd['p0'],dd['p1'];q=dd['quantity'];k=dd['strike'];right=dd['right'];role=dd['role'];phase=dd['phase']
        quoted=np.isfinite(p0+p1);movement=np.where(quoted,q*(p1-p0),0.);liquid=(dd['volume0']>0)&(dd['volume1']>0);outputs={}
        expiry_clock='15:35' if m['expiry_date']>='2026-08-03' else '15:30';expiry=int(pd.Timestamp(m['expiry_date']+' '+expiry_clock,tz='Asia/Kolkata').timestamp())
        for name,(rate,shift,spotonly) in VARIANTS.items():
            t0=(expiry+shift*60-dd['start_second'])/(365*86400);t1=(expiry+shift*60-dd['end_second'])/(365*86400)
            def forward(spot,basis,tau):
                fp=k+basis*np.exp(rate*np.maximum(tau,0));ok=np.isfinite(fp)&(fp>0)&np.isfinite(spot)&(np.abs(fp/spot-1)<=.03)
                return (spot.copy(),np.zeros(N,bool)) if spotonly else (np.where(ok,fp,spot),ok)
            F0,par0=forward(dd['spot0'],dd['basis0'],t0);F1,par1=forward(dd['spot1'],dd['basis1'],t1)
            s0=fit_iv(p0,F0,k,t0,right,rate);s1=fit_iv(p1,F1,k,t1,right,rate);valid=quoted&liquid&np.isfinite(s0+s1)
            js=np.flatnonzero(valid);parts=np.zeros((N,3));delta=np.zeros(N);gamma=np.zeros(N)
            if len(js):
                vals=shapley(F0[js],t0[js],s0[js],F1[js],t1[js],s1[js],k[js],right[js],rate)
                for j in range(3):parts[js,j]=q[js]*vals[j]
                vol=s0[js]*np.sqrt(t0[js]);d1=np.log(F0[js]/k[js])/vol+vol/2;density=np.exp(-.5*d1*d1)/np.sqrt(2*np.pi);discount=np.exp(-rate*t0[js])
                delta[js]=q[js]*discount*(ndtr(d1)-right[js])*(F1[js]-F0[js]);gamma[js]=q[js]*.5*discount*density/(F0[js]*vol)*(F1[js]-F0[js])**2
                assert np.max(np.abs(parts[js].sum(axis=1)-movement[js]),initial=0)<1e-4
            outputs[name]=dict(valid=valid,parts=parts,delta=delta,gamma=gamma,parity=par0&par1)
        common=np.logical_and.reduce([v['valid'] for v in outputs.values()]);bridge=np.zeros(4);bridge_missing=np.zeros(4,int)
        for x in fs.itertuples():
            i=int(np.searchsorted(z['minutes'],x.second//60));j=lookup[(x.strike,int(x.option_type=='PE'))];p=z['close'][i,j];signed=1 if x.side=='Buy' else -1
            for qty,sign in [(x.closing_quantity,np.sign(x.quantity_before)),(x.opening_quantity,signed)]:
                if qty:
                    r=(0 if sign<0 else 2)+int(x.option_type=='PE')
                    if np.isfinite(p):bridge[r]+=signed*qty*(p-x.execution_price)
                    else:bridge_missing[r]+=1
        for name,out in outputs.items():
            for quality,allowed in [('variant_valid',out['valid']),('common_all_models',common)]:
                for r,label in enumerate(ROLES):
                    ix=role==r;ok=ix&allowed;part=out['parts'][ok].sum(axis=0);direct=role_results[(role_results.cycle_id==cid)&role_results.role.eq(label)].iloc[0]
                    known=float(movement[ix].sum());fitted=float(movement[ok].sum());economic=float(direct.economic_pnl)
                    rows.append(dict(cycle_id=cid,underlying=m['underlying'],expiry_date=m['expiry_date'],role=label,model=name,coverage=quality,economic_pnl=economic,
                        observed_fill_cashflow=direct.fill_cashflow,observed_realised=direct.realised_pnl,marked_unrealised=direct.marked_unrealised_pnl,
                        modeled_direction_pnl=part[0],modeled_time_pnl=part[1],modeled_iv_surface_pnl=part[2],trade_to_bar_mark_bridge=bridge[r],
                        unexplained_residual=economic-bridge[r]-part.sum(),unfitted_quoted_movement=known-fitted,uncovered_path_residual=economic-bridge[r]-known,
                        fitted_reconciliation_error=fitted-part.sum(),delta_linear_diagnostic=out['delta'][ok].sum(),gamma_quadratic_diagnostic=out['gamma'][ok].sum(),
                        direction_higher_and_interaction=part[0]-out['delta'][ok].sum()-out['gamma'][ok].sum(),
                        active_contract_intervals=int(ix.sum()),quoteable_intervals=int((ix&quoted).sum()),fitted_intervals=int(ok.sum()),zero_volume_intervals=int((ix&~liquid).sum()),
                        fitted_absolute_quoted_movement=float(np.abs(movement[ok]).sum()),total_absolute_quoted_movement=float(np.abs(movement[ix]).sum()),
                        parity_forward_intervals=int((ok&out['parity']).sum()),missing_trade_bridge_components=int(bridge_missing[r]),
                        model_prices_used_for_liquidation=False,interpretation='descriptive Shapley estimates; not causal theta/vol alpha'))
                if quality=='variant_valid':
                    for ph in ['preexpiry','overnight','expiry']:
                        ok=allowed&(phase==ph);part=out['parts'][ok].sum(axis=0)
                        phase_rows.append(dict(cycle_id=cid,underlying=m['underlying'],expiry_date=m['expiry_date'],model=name,phase=ph,modeled_direction_pnl=part[0],modeled_time_pnl=part[1],modeled_iv_surface_pnl=part[2],fitted_intervals=int(ok.sum()),quoteable_movement=float(movement[phase==ph].sum()),fitted_movement=float(movement[ok].sum())))
        frame=pd.DataFrame(dd);frame['quote_movement']=movement;frame['primary_fitted']=outputs['primary']['valid'];frame['common_model_fitted']=common
        for j,col in enumerate(['primary_direction','primary_time','primary_iv']):frame[col]=outputs['primary']['parts'][:,j]
        intervals.append(frame);print('Attributed',cid,'intervals',N,'valid',outputs['primary']['valid'].sum(),flush=True)
    save(pd.DataFrame(rows),'cycle_pnl_decomposition.csv');save(pd.DataFrame(phase_rows),'model_phase_components.csv');save(pd.concat(intervals,ignore_index=True),'attribution_interval_ledger.csv.gz')
    print('Attribution complete; residuals retained.',flush=True)
def defaultdict_list():
    from collections import defaultdict
    return defaultdict(list)
if __name__=='__main__':run()
