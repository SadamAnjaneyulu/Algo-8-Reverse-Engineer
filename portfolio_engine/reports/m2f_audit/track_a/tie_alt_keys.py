"""[RAW][IMPL] Alternative intra-second keys that exist in the RAW file: trade id (col 28; SENSEX ids embed a ns timestamp), order number (col 4), col 1.
Reports in which (instrument,second) groups the file-order disagrees with each key and the measured impact on the observed layer if that key were used instead."""
import os, sys, json, re, collections
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import ref_model as RM
import csv
raw=list(csv.reader(open(RM.RAW,newline='')))
rows=RM.load_raw()
def tkey(s): return tuple(int(x) for x in s.split('-'))
for r,rr in zip(rows,raw): r['tid']=tkey(rr[28]); r['ono']=int(rr[4]); r['c1']=int(rr[1])
def order_by(key): return sorted(rows,key=lambda f:(f['ts'],key(f),f['row']))
G=collections.defaultdict(list)
for r in rows: G[(r['inst'],r['ts'])].append(r)
def disagree(key):
    n=0; mixed=0; ex=[]
    for k,v in G.items():
        if len(v)<2: continue
        if [x['row'] for x in sorted(v,key=lambda f:(key(f),f['row']))]!=[x['row'] for x in v]:
            n+=1; mixed+= len({x['side'] for x in v})>1; ex.append((k,[(x['row'],x['side'],x['qty'],x['px']) for x in v]))
    return n,mixed,ex
base={m:RM.replay_ref(RM.order_fills(rows,'src'),m) for m in ('FIFO','LIFO','AVG')}
def sig(R):
    rows_by={}
    for r,o in R.oa.items(): rows_by.setdefault(o['ep'],[]).append(r)
    return {eid:((e['dir'],e['opened'],e['closed'],e['ended_by'],e['rev'],e['n_open'],e['n_close']),frozenset(rows_by.get(eid,[]))) for eid,e in R.episodes.items()}
bs={m:sig(base[m]) for m in base}
out={}
for name,key in (('trade_id',lambda f:f['tid']),('order_no',lambda f:f['ono']),('col1',lambda f:f['c1'])):
    n,mx,ex=disagree(key); out[name]=dict(groups_where_file_order_differs=n,of_which_mixed_side=mx,examples=ex[:6]); ordered=order_by(key)
    for m in ('FIFO','LIFO','AVG'):
        R=RM.replay_ref(ordered,m); s=sig(R); B=bs[m]
        eids=set(s)|set(B); idchg=[e for e in eids if s.get(e)!=B.get(e)]; struct=[e for e in eids if (s.get(e) or (0,))[0]!=(B.get(e) or (0,))[0]]
        out[name][m]=dict(instruments_changed=len({e.split('#')[0] for e in idchg}),episodes_identity_changed=len(idchg),episodes_structure_changed=len(struct),n_episodes=len(R.episodes),
            fills_split_changed=sum(1 for r in base[m].fills if (base[m].fills[r]['close'],base[m].fills[r]['open'])!=(R.fills[r]['close'],R.fills[r]['open'])),
            OA=len(R.oa),CP=len(R.cp),reversal_fills=sum(1 for f in R.fills.values() if f['rev']),realized_delta_paise=float(R.realized_total-base[m].realized_total),final_inv_equal=R.final_inv==base[m].final_inv)
json.dump(out,open(os.path.join(HERE,'tie_alt_keys_result.json'),'w'),indent=1,default=str)
for k,v in out.items():
    print(k,{a:b for a,b in v.items() if a not in('examples','FIFO','LIFO','AVG')})
    for m in ('FIFO','LIFO','AVG'): print('   ',m,v[m])
print(json.dumps(out['trade_id']['examples'][:3]))
