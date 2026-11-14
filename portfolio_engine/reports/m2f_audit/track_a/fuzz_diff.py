"""Task 4b: random differential fuzz. Each random sequence is replayed by (i) scratch-built C++ core (pe_replay), (ii) Python engine pe.replay (lineage=True), (iii) independent reference ref_model.
Comparisons: C++ vs Python byte-for-byte on 5 lineage files + dump + roles = [XLANG] only; C++ files (parsed) vs reference and Python files (parsed) vs reference = [IMPL] (reference is a separate re-implementation, integer/Fraction exact).
usage: fuzz_diff.py N SEED"""
import os, sys, json, random, subprocess, tempfile
os.environ['PYTHONDONTWRITEBYTECODE']='1'
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
S='/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_a'
sys.path.insert(0,os.environ.get('PE_PY','/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python'))
import ref_model as RM
from fractions import Fraction
from pe import tsvio, replay as rp
MODE='SYNTHETIC_TEST'; BIN=os.environ.get('PE_BIN',S+'/build/pe_replay')
EVH=['schema_version','execution_mode','fill_id','source_row_id','parent_order_id','module_tag','instrument_id','timestamp_s','side','quantity','price_paise','requested_quantity','order_status','is_duplicate_fill','evidence_source']
INH=['instrument_id','underlying','exchange_segment','instrument_type','option_type','strike','expiry','lot_size','tick_size_paise','lot_size_source']

def gen(rnd):
    n_inst=rnd.randint(1,6); insts=[]
    for k in range(n_inst):
        und=rnd.choice(['NIFTY','SENSEX']); cp=rnd.choice(['CE','PE']); strike=20000+500*k; exp=rnd.choice(['2026-06-23','2026-06-30','2026-07-07'])
        insts.append((f'{und}|{exp}|{cp}|{strike}',und,cp,strike,exp))
    n=rnd.randint(5,200); ts=1782186364+rnd.randint(0,10**6); rows=[]; lot={'NIFTY':65,'SENSEX':20}; shuffle=rnd.random()<0.15; mode_small=rnd.random()<0.6
    px={i[0]:rnd.randint(1,4000)*5 for i in insts}
    for r in range(n):
        i=rnd.choice(insts); 
        if rnd.random()<0.6: ts+=rnd.choice([0,0,0,1,2,5,60,86400//2,86400])
        side=rnd.choice([1,-1]); q=lot[i[1]]*(rnd.randint(1,3) if mode_small else rnd.randint(1,12))
        if rnd.random()<0.05: q=rnd.randint(1,500)             # non-lot units are legal for the engine
        px[i[0]]=max(5,px[i[0]]+5*rnd.randint(-6,6)); p=px[i[0]]
        rows.append(dict(row=r,parent=f'P{rnd.randint(0,n//2)}',inst=i[0],ts=ts,side=side,qty=q,px=p,order_qty=q,status=rnd.choice(['Filled','PartiallyFilled']),dup=1 if rnd.random()<0.02 else 0,module='num'))
    if shuffle: rnd.shuffle(rows); [r.__setitem__('row',k) for k,r in enumerate(rows)]    # file order no longer time order; rows renumbered
    return insts,rows

def write_tsv(d,insts,rows):
    with open(d+'/e.tsv','w',newline='\n') as f:
        f.write('\t'.join(EVH)+'\n')
        for r in rows: f.write('\t'.join(['pe.fill.v1',MODE,RM.to_fill_id(r['row']),str(r['row']),r['parent'],r['module'],r['inst'],str(r['ts']),str(r['side']),str(r['qty']),str(r['px']),str(r['order_qty']),r['status'],str(r['dup']),'fuzz'])+'\n')
    with open(d+'/i.tsv','w',newline='\n') as f:
        f.write('\t'.join(INH)+'\n')
        for (iid,und,cp,k,e) in insts: f.write('\t'.join([iid,und,'NSEFO','OPTION',cp,str(k),e,str(RM.LOT[und]),'5','fuzz'])+'\n')

def canon_files(F,m):
    """parse lineage text files -> canonical comparable structure"""
    obs=[l.split('\t') for l in F['observed_allocations.tsv'].splitlines()[1:]]
    oa={int(x[2][1:]):(x[3],x[5],int(x[6]),int(x[7]),int(x[8]),int(x[9])) for x in obs if x[0]=='OA'}; cp={int(x[2][1:]):(x[3],x[5],int(x[6]),int(x[7]),int(x[8]),int(x[9])) for x in obs if x[0]=='CP'}
    ev=sorted((x[1],int(x[2]),x[3],int(x[4][1:]),int(x[7]),int(x[8]),int(x[9])) for x in (l.split('\t') for l in F['lifecycle.tsv'].splitlines()[1:]))
    ep=sorted((x[0],int(x[2]),int(x[4]),int(x[5]),x[7],int(x[11]),int(x[12]),bool(int(x[3])),x[8]) for x in (l.split('\t') for l in F['episodes.tsv'].splitlines()[1:]))
    ca=[]
    for l in F[f'ca_{m}.tsv'].splitlines()[1:]:
        x=l.split('\t'); src=x[3] if m=='AVG' else int(x[3][4:]); ca.append((int(x[2][4:]),src,int(x[4]),Fraction(x[5]),int(x[6]),Fraction(x[7]),int(x[8])))
    sl={}
    for l in F[f'slices_{m}.tsv'].splitlines()[1:]:
        x=l.split('\t'); sl[x[4] if m=='AVG' else int(x[3][4:])]=(int(x[5]),Fraction(x[6]),x[4])
    return dict(oa=oa,cp=cp,ev=ev,ep=ep,ca=ca,sl=sl)
def canon_ref(R,m,last_day_fn):
    rf=lambda D:{k:(v['parent'],v['ep'],v['ts'],v['side'],v['qty'],v['px']) for k,v in D.items()}
    ep=[]
    for k,v in R.episodes.items():
        rem=v['opened']-v['closed']; ts_= 'CLOSED' if rem==0 and v['ended_by']=='flat' else 'REVERSED' if rem==0 else last_day_fn(v['inst'])
        ep.append((k,v['dir'],v['opened'],v['closed'],v['ended_by'],v['n_open'],v['n_close'],v['rev'],ts_))
    ca=[(x[0],x[1],x[2],x[3],x[4],x[5],x[6]) for x in R.ca]
    sl={}
    for k,v in R.slices.items(): sl[k]=(v[1],Fraction(v[2]) if m!='AVG' else v[2],v[3] if m!='AVG' else k)
    return dict(oa=rf(R.oa),cp=rf(R.cp),ev=sorted((e[0],e[1],e[2],e[3],e[4],e[5],e[6]) for e in R.events),ep=sorted(ep),ca=ca,sl=sl)
def same(a,b,m):
    """returns list of mismatching sections. AVG numeric fields: abs tol 1e-5 (C++/Python print 6 decimals of a binary float; reference is exact rational)"""
    bad=[]
    for k in ('oa','cp','ev','ep'):
        if a[k]!=b[k]: bad.append(k)
    if len(a['ca'])!=len(b['ca']): bad.append('ca_len')
    else:
        for x,y in zip(a['ca'],b['ca']):
            if (x[0],x[1],x[2],x[4],x[6])!=(y[0],y[1],y[2],y[4],y[6]): bad.append('ca_key'); break
            if m!='AVG':
                if (x[3],x[5])!=(y[3],y[5]): bad.append('ca_val'); break
            elif abs(float(x[3])-float(y[3]))>1e-5 or abs(float(x[5])-float(y[5]))>1e-4: bad.append('ca_val_avg'); break
    if set(a['sl'])!=set(b['sl']): bad.append('sl_keys')
    else:
        for k in a['sl']:
            x,y=a['sl'][k],b['sl'][k]
            if x[0]!=y[0] or x[2]!=y[2] or abs(float(x[1])-float(y[1]))>(1e-5 if m=='AVG' else 0): bad.append('sl_val'); break
    return bad

def run(N,seed):
    rnd=random.Random(seed); stats=dict(sequences=N,fills=0,cases=0,xlang_byte_mismatch=0,cpp_vs_ref_mismatch=0,py_vs_ref_mismatch=0,reversals_seen=0,mixed_second_groups=0,partial_close_fills=0,dups=0,examples=[])
    import datetime
    def day(s): y,m,d=map(int,s.split('-')); return (datetime.date(y,m,d)-datetime.date(1970,1,1)).days
    with tempfile.TemporaryDirectory(dir=S) as d:
        for s in range(N):
            insts,rows=gen(rnd); write_tsv(d,insts,rows); ins=tsvio.read_instruments(d+'/i.tsv'); fills=tsvio.read_events(d+'/e.tsv',ins)
            live=[r for r in rows if not r['dup']]; stats['fills']+=len(rows); stats['dups']+=len(rows)-len(live)
            lastts=max(r['ts'] for r in live) if live else 0; lastday=(sorted(live,key=lambda r:(r['ts'],r['row']))[-1]['ts']+19800)//86400 if live else 0
            tstat=lambda i:('EXPIRED_UNCLOSED' if day(i.split('|')[1])<=lastday else 'OPEN_AT_END_OF_DATA')
            for tie in ('src','sells_first','buys_first'):
                ordered=RM.order_fills(live,tie)
                for m in ('FIFO','LIFO','AVG'):
                    od=f'{d}/o_{m}_{tie}'; os.makedirs(od,exist_ok=True)
                    p=subprocess.run([BIN,'--events',d+'/e.tsv','--instruments',d+'/i.tsv','--mode',MODE,'--method',m,'--tie',tie,'--lineage-dir',od,'--dump',od+'/dump.tsv','--roles',od+'/roles.tsv'],capture_output=True,text=True)
                    res=rp.replay(fills,ins,MODE,m,tie,lineage=True,strict=True); py=rp.lineage_files(res); py['dump.tsv']=res.dump; py['roles.tsv']=rp.roles_tsv(res.roles)
                    cpp={n:open(f'{od}/{n}').read() for n in py} if p.returncode==0 else None
                    stats['cases']+=1
                    if cpp is None or any(cpp[n]!=py[n] for n in py):
                        stats['xlang_byte_mismatch']+=1; stats['examples'].append(('xlang',s,tie,m,p.stderr[:200]))
                        if cpp is None: continue
                    R=RM.replay_ref(ordered,m); cr=canon_ref(R,m,tstat)
                    if same(canon_files(cpp,m),cr,m): stats['cpp_vs_ref_mismatch']+=1; stats['examples'].append(('cpp_ref',s,tie,m,same(canon_files(cpp,m),cr,m)))
                    if same(canon_files(py,m),cr,m): stats['py_vs_ref_mismatch']+=1; stats['examples'].append(('py_ref',s,tie,m,same(canon_files(py,m),cr,m)))
                    # per-fill roles & totals vs ref
                    rl=[l.split('\t') for l in py['roles.tsv'].splitlines()[1:]]
                    for x in rl:
                        f=R.fills[int(x[0][1:])]
                        if (int(x[2]),int(x[3]),int(x[4]),bool(int(x[5])))!=(f['close'],f['open'],f['inv_after'],f['rev']): stats['py_vs_ref_mismatch']+=1; stats['examples'].append(('roles',s,tie,m,x)); break
                    if tie=='src' and m=='FIFO':
                        stats['reversals_seen']+=sum(1 for f in R.fills.values() if f['rev']); stats['partial_close_fills']+=sum(1 for e in R.events if e[2]=='PARTIALLY_REDUCED')
                        g={}
                        for r in live: g.setdefault((r['inst'],r['ts']),set()).add(r['side'])
                        stats['mixed_second_groups']+=sum(1 for v in g.values() if len(v)==2)
                    # totals
                    tot=[l for l in py['dump.tsv'].splitlines() if l.startswith('TOTAL\trealized')][0].split('\t')[2]
                    exact=R.realized_total
                    if (m!='AVG' and Fraction(tot)!=exact) or (m=='AVG' and abs(float(tot)-float(exact))>1e-4): stats['py_vs_ref_mismatch']+=1; stats['examples'].append(('total',s,tie,m,tot,float(exact)))
    return stats
if __name__=='__main__':
    N=int(sys.argv[1]); seed=int(sys.argv[2]); st=run(N,seed); st['examples']=st['examples'][:10]; print(json.dumps(st,indent=1))
    if len(sys.argv)>3: json.dump(st,open(sys.argv[3],'w'),indent=1,default=str)
