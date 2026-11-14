"""Task 4a. Build raw-derived TSV (from raw CSV by ref_model.load_raw, NOT via TP-01 parquet), run scratch C++ core and engine Python replay on the SAME TSV, compare
(a) C++ vs Python files byte-for-byte [XLANG only], (b) C++ files parsed vs independent reference [RAW][IMPL] (C++ outputs only loaded)."""
import os, sys, json, subprocess, csv, hashlib
os.environ['PYTHONDONTWRITEBYTECODE']='1'
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
S='/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_a'
sys.path.insert(0,'/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
import ref_model as RM
from pe import tsvio, replay as rp
from fractions import Fraction
MODE='HISTORICAL_OBSERVED_REPLAY'; BIN=S+'/build/pe_replay'
rows=RM.load_raw(); seg={}
for i,r in enumerate(csv.reader(open(RM.RAW,newline=''))): seg[rows[i]['inst']]=r[3]
def mod(p): return 'num' if p.isdigit() else p.split('_')[0]+'_'
os.makedirs(S+'/rawtsv',exist_ok=True)
with open(S+'/rawtsv/raw_events.tsv','w',newline='\n') as f:
    f.write('\t'.join(['schema_version','execution_mode','fill_id','source_row_id','parent_order_id','module_tag','instrument_id','timestamp_s','side','quantity','price_paise','requested_quantity','order_status','is_duplicate_fill','evidence_source'])+'\n')
    for r in rows: f.write('\t'.join(['pe.fill.v1',MODE,RM.to_fill_id(r['row']),str(r['row']),r['parent'],mod(r['parent']),r['inst'],str(r['ts']),str(r['side']),str(r['qty']),str(r['px']),str(r['order_qty']),r['status'],'0',f'RAW:row={r["row"]}'])+'\n')
with open(S+'/rawtsv/raw_instruments.tsv','w',newline='\n') as f:
    f.write('\t'.join(['instrument_id','underlying','exchange_segment','instrument_type','option_type','strike','expiry','lot_size','tick_size_paise','lot_size_source'])+'\n')
    for i in sorted({r['inst'] for r in rows}):
        u,e,c,k=i.split('|'); f.write('\t'.join([i,u,seg[i],'OPTION',c,k,e,str(RM.LOT[u]),'5','RAW_CONFIG'])+'\n')
EV=S+'/rawtsv/raw_events.tsv'; IP=S+'/rawtsv/raw_instruments.tsv'
ins=tsvio.read_instruments(IP); fills=tsvio.read_events(EV,ins)
out={}; ordered=RM.order_fills(rows,'src')
def files_for(m): return ['observed_allocations.tsv','lifecycle.tsv','episodes.tsv',f'ca_{m}.tsv',f'slices_{m}.tsv']
for m in ('FIFO','LIFO','AVG'):
    R=RM.replay_ref(ordered,m)
    for tie in ('src','sells_first','buys_first'):
        d=f'{S}/cpp_out_{m}_{tie}'; os.makedirs(d,exist_ok=True)
        p=subprocess.run([BIN,'--events',EV,'--instruments',IP,'--mode',MODE,'--method',m,'--tie',tie,'--lineage-dir',d,'--dump',d+'/dump.tsv','--roles',d+'/roles.tsv'],capture_output=True,text=True)
        res=rp.replay(fills,ins,MODE,m,tie,lineage=True); py=rp.lineage_files(res); py['dump.tsv']=res.dump; py['roles.tsv']=rp.roles_tsv(res.roles)
        cmp={}
        for n in files_for(m)+['dump.tsv','roles.tsv']: cmp[n]=(open(f'{d}/{n}').read()==py[n])
        out[f'{m}/{tie}/cpp_vs_py_byte_identical']=cmp; out[f'{m}/{tie}/rc']=p.returncode
        if tie=='src':
            # parse C++ files and compare with independent reference [RAW][IMPL]
            obs=[l.split('\t') for l in open(f'{d}/observed_allocations.tsv').read().splitlines()[1:]]
            oa={int(x[2][1:]):(x[3],x[5],int(x[6]),int(x[7]),int(x[8]),int(x[9])) for x in obs if x[0]=='OA'}; cp={int(x[2][1:]):(x[3],x[5],int(x[6]),int(x[7]),int(x[8]),int(x[9])) for x in obs if x[0]=='CP'}
            rf=lambda D:{k:(v['parent'],v['ep'],v['ts'],v['side'],v['qty'],v['px']) for k,v in D.items()}
            out[f'{m}/cpp_OA_equals_ref']=(oa==rf(R.oa)); out[f'{m}/cpp_CP_equals_ref']=(cp==rf(R.cp))
            ev=sorted((x[1],int(x[2]),x[3],int(x[4][1:]),int(x[7]),int(x[8]),int(x[9])) for x in (l.split('\t') for l in open(f'{d}/lifecycle.tsv').read().splitlines()[1:]))
            out[f'{m}/cpp_lifecycle_equals_ref']=(ev==sorted(R.events))
            epl=[l.split('\t') for l in open(f'{d}/episodes.tsv').read().splitlines()[1:]]
            out[f'{m}/cpp_episodes_equals_ref']=(sorted((x[0],int(x[2]),int(x[4]),int(x[5]),x[7],int(x[11]),int(x[12]),bool(int(x[3]))) for x in epl)==sorted((k,v['dir'],v['opened'],v['closed'],v['ended_by'],v['n_open'],v['n_close'],v['rev']) for k,v in R.episodes.items()))
            ca=[l.split('\t') for l in open(f'{d}/ca_{m}.tsv').read().splitlines()[1:]]; ok=len(ca)==len(R.ca)
            tot=Fraction(0)
            for x,y in zip(ca,R.ca):
                src=x[3] if m=='AVG' else int(x[3][4:])
                tot+=Fraction(x[7])
                if (int(x[2][4:]),src,int(x[4]),int(x[6]),int(x[8]))!=(y[0],y[1],y[2],y[4],y[6]): ok=False
                if m!='AVG' and (int(x[5])!=y[3] or int(x[7])!=y[5]): ok=False
                if m=='AVG' and abs(float(x[7])-float(y[5]))>1e-5: ok=False
            out[f'{m}/cpp_CA_equals_ref']=ok; out[f'{m}/cpp_CA_total_paise']=str(tot) if m=='AVG' else int(tot); 
            out[f'{m}/cpp_CA_total_minus_ref_exact']=float(tot-R.realized_total)
            out[f'{m}/cpp_dump_realized']=[l for l in open(f'{d}/dump.tsv').read().splitlines() if l.startswith('TOTAL\trealized')]
print(json.dumps(out,indent=1))
json.dump(out,open(HERE+'/cpp_raw_run_result.json','w'),indent=1)
print('SHA events tsv', hashlib.sha256(open(EV,'rb').read()).hexdigest())
