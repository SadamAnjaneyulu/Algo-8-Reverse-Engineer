"""[XLANG] probe: malformed integer tokens accepted by Python int() but (per inspection) rejected by C++ from_chars. Scratch files only."""
import os, sys, subprocess, json
os.environ['PYTHONDONTWRITEBYTECODE']='1'
S='/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_a'
sys.path.insert(0,'/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
from pe import tsvio
from pe.schema import EngineError
base=open(S+'/rawtsv/raw_events.tsv').read().splitlines()[:3]; ins=tsvio.read_instruments(S+'/rawtsv/raw_instruments.tsv'); out={}
hdr=base[0].split('\t')
for name,idx,val in [('plus_sign_side',8,'+1'),('underscore_qty',9,'1_30'),('space_qty',9,' 130'),('unicode_digit_qty',9,'١٣٠')]:
    row=base[1].split('\t'); row[idx]=val; p=S+'/probe.tsv'; open(p,'w',encoding='utf-8').write('\n'.join([base[0],'\t'.join(row)])+'\n')
    try: f=tsvio.read_events(p,ins); py='ACCEPTED qty=%d side=%d'%(f[0].quantity,f[0].side)
    except EngineError as e: py='REJECTED'
    rc=subprocess.run([S+'/build/pe_replay','--events',p,'--instruments',S+'/rawtsv/raw_instruments.tsv','--mode','HISTORICAL_OBSERVED_REPLAY'],capture_output=True,text=True).returncode
    out[name]=dict(python=py,cpp='REJECTED' if rc==2 else 'ACCEPTED' if rc==0 else f'rc={rc}')
print(json.dumps(out,indent=1)); json.dump(out,open('parse_parity_probe_result.json','w'),indent=1)
