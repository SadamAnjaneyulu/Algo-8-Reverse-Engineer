"""[RAW]+[IMPL] reference vs TP-01 committed parquet outputs (read-only). TP-01 outputs are an earlier implementation, so agreement = reproduction of prior result, not an independent economic truth."""
import os, sys, json
os.environ['PYTHONDONTWRITEBYTECODE']='1'
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import pandas as pd, numpy as np
from fractions import Fraction
import ref_model as RM
D='/home/user/Algo-8-Reverse-Engineer/tp_reconstruction/data/'
rows=RM.load_raw(); out={}
E=pd.read_parquet(D+'position_episodes.parquet'); L=pd.read_parquet(D+'reconstructed_position_ledger.parquet'); FR=pd.read_parquet(D+'fill_roles.parquet')
out['episodes_methods']=E.method.value_counts().to_dict(); out['ledger_methods_ties']=L.groupby(['method','tie_order']).size().to_dict().__repr__(); out['fill_roles_methods']=FR.method.value_counts().to_dict()
out['ledger_row_type']=L.row_type.value_counts().to_dict()
for tie in ['src','sells_first','buys_first']:
  ordered=RM.order_fills(rows,tie)
  for m in ['FIFO','LIFO','AVG']:
    R=RM.replay_ref(ordered,m); key=f'{m}/{tie}'
    # episodes (TP-01 has 1 episode table; check which tie)
    if tie=='src':
        e=E[E.method==m].set_index('episode_id'); okc=0; bad=[]
        for eid,x in R.episodes.items():
            if eid not in e.index: bad.append(('missing',eid)); continue
            t=e.loc[eid]; rp=float(x['realized'])/100
            if (t.direction,t.opened_units,t.closed_units,t.n_open_fills,t.n_close_fills,t.ended_by,bool(t.started_by_reversal))==(x['dir'],x['opened'],x['closed'],x['n_open'],x['n_close'],x['ended_by'],x['rev']) and abs(t.realized_pnl-rp)<0.005+1e-9: okc+=1
            else: bad.append((eid,float(t.realized_pnl),rp))
        out[key+'_episodes']=dict(ref=len(R.episodes),tp01=len(e),exact=okc,bad=bad[:5],extra_in_tp01=len(set(e.index)-set(R.episodes)))
    # ledger pieces
    lg=L[(L.method==m)&(L.tie_order==tie)&(L.row_type=='CLOSED')]
    if len(lg):
        tp=sorted((int(r.close_row),int(r.open_row) if m!='AVG' and r.open_row==r.open_row else -1,int(r.qty),round(r.pnl*100)) for r in lg.itertuples()) if m!='AVG' else None
        if m!='AVG':
            mine=sorted((x[0],x[1],x[2],int(x[5])) for x in R.ca)
            out[key+'_pieces']=dict(ref=len(mine),tp01=len(tp),equal=(mine==tp))
        else:
            # AVG ledger may aggregate per closing: compare by close_row sums
            a={};b={}
            for r in lg.itertuples(): a[int(r.close_row)]=a.get(int(r.close_row),0)+r.pnl
            for x in R.ca: b[x[0]]=b.get(x[0],0)+float(x[5])/100
            out[key+'_pieces']=dict(ref=len(b),tp01=len(a),max_abs_diff_rupees_per_close=max(abs(a[k]-b.get(k,0)) for k in a) if a else None, same_keys=set(a)==set(b))
    out[key+'_realized_rupees']=float(R.realized_total)/100
    if tie=='src':
        fr=FR[FR.method==m].set_index('src_row'); nb=0
        for rw,f in R.fills.items():
            t=fr.loc[rw]
            if (t.close_qty,t.open_qty,t.inventory_after,bool(t.is_reversal))!=(f['close'],f['open'],f['inv_after'],f['rev']): nb+=1
        out[key+'_fill_roles_mismatch']=nb
S=pd.read_csv(D+'reconciliation_summary.csv').set_index('method'); out['tp01_summary_realized_rupees']=S.realized_gross_pnl_rupees.to_dict()
print(json.dumps(out,indent=1,default=str)); json.dump(out,open(os.path.join(HERE,'compare_ref_vs_tp01_result.json'),'w'),indent=1,default=str)
