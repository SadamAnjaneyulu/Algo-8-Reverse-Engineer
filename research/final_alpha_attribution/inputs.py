"""Immutable canonical inputs and independently priced minute book adapter."""
from __future__ import annotations
import csv,hashlib,json,sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SOURCE=ROOT/'research/outputs';CACHE=HERE/'.cache'
sys.path.insert(0,str(ROOT/'research'))
from analyze_index_triggers import load_index
META=json.loads((ROOT/'research/hypothesis_controller_search/outputs/cycle_metadata.json').read_text())
CID={(m['underlying'],m['expiry_date']):m['cycle_id'] for m in META}
ROLES=['short_CE','short_PE','long_CE','long_PE']
COSTS={'zero_diagnostic':(0.,0.,0.),'moderate':(.0025,20.,.05),'conservative':(.005,20.,.1),'adverse_execution':(.005,40.,.2)}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def iso(s):return pd.Timestamp(int(s),unit='s',tz='UTC').tz_convert('Asia/Kolkata').isoformat()
def sec(s):return int(pd.Timestamp(s).timestamp())
def save(df,name):
    kw={'compression':{'method':'gzip','mtime':0,'compresslevel':3}} if name.endswith('.gz') else {}
    df.to_csv(HERE/name,index=False,**kw)
def fills():
    f=pd.read_csv(SOURCE/'playbook_fill_ledger.csv.gz');f['second']=pd.to_datetime(f.timestamp_ist).astype('int64')//10**9
    f['cycle_id']=[CID[x] for x in zip(f.underlying,f.expiry_date)];return f.sort_values(['cycle_id','second','source_row']).reset_index(drop=True)
def role(right,sign):return (0 if sign<0 else 2)+int(right=='PE')
def cycle_data(cid):
    path=CACHE/f'cycle_{cid:02}.npz'
    if not path.exists():raise RuntimeError('Run audit.py first to build immutable raw-quote cache.')
    with np.load(path) as z:return {k:z[k] for k in z.files}

class DecimalBook:
    """Independent signed-position cost/cash arithmetic in canonical child order."""
    def __init__(self):self.q={};self.cost={};self.cash=Decimal(0);self.realized=Decimal(0)
    def apply(self,key,quantity,price,side):
        q=self.q.get(key,0);oldcost=self.cost.get(key,Decimal(0));signed=quantity*(1 if side=='Buy' else -1)
        closed=min(abs(q),quantity) if q*signed<0 else 0;opened=quantity-closed
        pnl=closed*(price-oldcost)*(1 if q>0 else -1);new=q+signed;remaining=abs(q)-closed
        if opened:self.cost[key]=(remaining*oldcost+opened*price)/(remaining+opened)
        elif not new:self.cost.pop(key,None)
        self.q[key]=new;self.cash-=signed*price;self.realized+=pnl
        return q,new,closed,opened,pnl

def actual_path(fs,z):
    T,C=z['close'].shape;delta=np.zeros((T,C),np.int64);cf=np.zeros(T);real=np.zeros((T,4));turn=np.zeros((T,4));units=np.zeros((T,4));parent=np.zeros((T,4));rolecash=np.zeros((T,4));uncertain=np.zeros(T)
    lookup={(int(k),'PE' if r else 'CE'):j for j,(k,r) in enumerate(zip(z['strikes'],z['rights']))};tm={int(t):i for i,t in enumerate(z['minutes'])};seen=set()
    for r in fs.itertuples():
        i=tm[r.second//60];j=lookup[(r.strike,r.option_type)];signed=int(r.incremental_quantity)*(1 if r.side=='Buy' else -1)
        delta[i,j]+=signed;cf[i]+=r.cash_change
        for quantity,oldsign,closing in [(r.closing_quantity,np.sign(r.quantity_before),True),(r.opening_quantity,1 if r.side=='Buy' else -1,False)]:
            if not quantity:continue
            rr=role(r.option_type,oldsign);fraction=quantity/r.incremental_quantity
            rolecash[i,rr]+=float(r.cash_change)*fraction;turn[i,rr]+=quantity*r.execution_price;units[i,rr]+=quantity
            if closing:real[i,rr]+=r.realized_pnl_change
            if r.parent_id not in seen:parent[i,rr]+=fraction
        seen.add(r.parent_id)
        lo,hi=z['low'][i,j],z['high'][i,j]
        if not np.isfinite(lo+hi) or not lo-1e-8<=r.execution_price<=hi+1e-8:uncertain[i]+=r.incremental_quantity
    q=np.cumsum(delta,axis=0);before=q-delta;cash=np.cumsum(cf);active=q!=0;missing=np.sum(active&~np.isfinite(z['close']),axis=1)
    value=np.sum(np.where(active,q*np.nan_to_num(z['close'],nan=0),0),axis=1);equity=np.where(missing==0,cash+value,np.nan)
    cost={n:np.cumsum(a*turn.sum(axis=1)+b*parent.sum(axis=1)+c*units.sum(axis=1)) for n,(a,b,c) in COSTS.items()}
    return dict(q=q,before=before,delta=delta,cash=cash,equity=equity,missing=missing,rolecash=rolecash,real=real,turn=turn,units=units,parent=parent,cost=cost,uncertain_units=uncertain)
