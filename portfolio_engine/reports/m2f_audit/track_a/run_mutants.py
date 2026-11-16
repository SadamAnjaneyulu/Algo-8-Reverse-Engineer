"""Mutation runner. For each mutant: copy the scratch mirror (tests/tools/fixtures/cpp/python copied; tp_reconstruction + raw CSV symlinked read-only), apply edits to the COPY, then
(a) run the EXISTING tests covering the area against the mutant, (b) run OWN independent checks (raw-derived reference comparison, fuzz vs reference; for C++ mutants cpp_raw_run + fuzz with the mutated binary).
usage: run_mutants.py ID [ID...]  -> writes mut_results/<ID>.json"""
import os, sys, json, shutil, subprocess, re, time
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import mutants
S='/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_a'; MIR=S+'/mirror'; RES=HERE+'/mut_results'; os.makedirs(RES,exist_ok=True)
TESTS=['tests/test_accounting.py','tests/test_lineage.py','tests/test_lineage_mutations.py','tests/test_lineage_parity.py','tests/test_lineage_real.py','tests/test_lineage_reference.py','tests/test_tp01_reconciliation.py','tests/test_parity.py']
def run(mid):
    m=[x for x in mutants.M if x['id']==mid][0]; d=f'{S}/mut/{mid}'; shutil.rmtree(d,ignore_errors=True); os.makedirs(os.path.dirname(d),exist_ok=True)
    shutil.copytree(MIR,d,symlinks=True)
    p=f'{d}/portfolio_engine/{m["file"]}'; t=open(p).read()
    for o,n in m['edits']:
        assert o in t,(mid,o[:50]); t=t.replace(o,n)
    open(p,'w').write(t)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'); out=dict(id=mid,name=m['name'],file=m['file'],expected=m['expected'])
    t0=time.time(); r=subprocess.run(['python3','-m','pytest','-p','no:cacheprovider','-q','--tb=no','-rfE']+TESTS,cwd=d+'/portfolio_engine',capture_output=True,text=True,env=env)
    fails=re.findall(r'^(?:FAILED|ERROR) (\S+)',r.stdout,re.M); out['existing_tests']=dict(returncode=r.returncode,failed=fails,summary=r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '',seconds=round(time.time()-t0))
    pe_py=d+'/portfolio_engine/python'; own={}
    if mid.startswith('C'):
        binp=d+'/portfolio_engine/build/pe_replay'; e2=dict(env,PE_BIN=binp,OUT_JSON=f'{S}/mut/{mid}_cpp_raw.json'); 
        rr=subprocess.run(['python3',HERE+'/cpp_raw_run.py'],capture_output=True,text=True,env=e2); 
        try: j=json.load(open(e2['OUT_JSON'])); own['cpp_raw_vs_ref_false_keys']=[k for k,v in j.items() if v is False and 'equals_ref' in k]; own['cpp_vs_py_byte_diff_files']=sum(1 for k,v in j.items() if k.endswith('byte_identical') for n,b in v.items() if not b)
        except Exception as ex: own['cpp_raw_error']=str(ex)[:200]+rr.stderr[-200:]
        rf=subprocess.run(['python3',HERE+'/fuzz_diff.py','60','777'],capture_output=True,text=True,env=dict(env,PE_BIN=binp))
        try: j=json.loads(rf.stdout); own['fuzz']={k:j[k] for k in('cases','xlang_byte_mismatch','cpp_vs_ref_mismatch','py_vs_ref_mismatch')}
        except Exception: own['fuzz_error']=rf.stderr[-300:]
        own['killed']=bool(own.get('cpp_raw_vs_ref_false_keys') or own.get('cpp_vs_py_byte_diff_files') or own.get('fuzz',{}).get('cpp_vs_ref_mismatch') or own.get('fuzz',{}).get('xlang_byte_mismatch'))
    else:
        e2=dict(env,PE_PY=pe_py,OUT_JSON=f'{S}/mut/{mid}_cmp.json'); rr=subprocess.run(['python3',HERE+'/compare_ref_vs_engine.py'],capture_output=True,text=True,env=e2)
        try:
            j=json.load(open(e2['OUT_JSON'])); res=j['results']; own['engine_exception']=res.get('ENGINE_EXCEPTION'); own['mismatch_summary']=res.get('MISMATCH_SUMMARY'); own['false_flags']=[k for k,v in res.items() if v is False]
        except Exception as ex: own['compare_error']=str(ex)[:200]+rr.stderr[-300:]
        rf=subprocess.run(['python3',HERE+'/fuzz_diff.py','60','777'],capture_output=True,text=True,env=dict(env,PE_PY=pe_py))
        try: j=json.loads(rf.stdout); own['fuzz']={k:j[k] for k in('cases','xlang_byte_mismatch','py_vs_ref_mismatch')}
        except Exception: own['fuzz_error']=(rf.stderr or rf.stdout)[-300:]
        own['killed']=bool(own.get('engine_exception') or own.get('mismatch_summary') or own.get('false_flags') or own.get('fuzz',{}).get('py_vs_ref_mismatch') or own.get('fuzz',{}).get('xlang_byte_mismatch') or own.get('fuzz_error'))
    out['own']=own; json.dump(out,open(f'{RES}/{mid}.json','w'),indent=1); shutil.rmtree(d,ignore_errors=True); print(mid,'done',out['existing_tests']['summary'],'own_killed',own['killed'],flush=True)
if __name__=='__main__':
    for mid in sys.argv[1:]: run(mid)
