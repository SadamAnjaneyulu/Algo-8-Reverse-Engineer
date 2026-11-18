"""Small factorial policy/execution experiment; no unrestricted parameter bank."""
import gzip,hashlib,json,subprocess,sys,shutil
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CACHE=HERE/'.cache';PRIOR=ROOT/'research/hypothesis_controller_search'
sys.path.insert(0,str(PRIOR))
from search import with_metrics
from replay_inputs import market_cache,calibration_path

ALLOCATION=['fixed_increment','pooled_clock_increment','cumulative_clock_target','capped_clock_restore']
RISK=['deadline_only','pooled_contract_premium50','side_equity100k_episode']
# id, lag, per-base spacing, leg lag, persist, cancel ack, duplicate,
# reconciliation period, stale state lag, pending-aware, target-bounded, TTL
MECHANICS=[
 ('safe_immediate','policy_alone',[0,0,0,0,0,0,0,0,0,0,1,120],0),
 ('sequential_base_slices','stateful_execution',[1,0,1,2,1,0,0,0,0,0,1,120],2),
 ('delayed_partial_keep','stateful_execution',[2,30,5,2,1,0,0,0,0,0,0,120],4),
 ('delayed_cancel_replace','stateful_execution',[3,30,5,2,0,2,0,0,0,0,0,120],5),
 ('stale_flatten_duplicate','stateful_execution',[4,0,0,0,1,0,1,0,0,0,0,120],5),
 ('pending_aware_reconcile','inventory_reconciliation',[5,2,1,2,1,0,0,5,0,1,1,120],5),
 ('stale_ignore_pending','inventory_reconciliation',[6,10,0,0,1,0,0,5,2,0,0,120],8)]

def policies():
    return [dict(policy_id=a*3+r,allocation=ALLOCATION[a],risk=RISK[r],allocation_code=a,risk_code=r,complexity=8+[0,2,4,6][a]+[0,2,4][r],
        opening='fixed evidence-derived three-base seed module; no historical opening labels used',calendar='received pre-initialised sessions; expiry-only initial history unknown',
        carry_guard='15:10 target long coverage, 15:20 confirmed protection short reduction',reentry='next scheduled window; own target activity gates expiry additions') for a in range(4) for r in range(3)]

def mechanics():
    names=['id','lag_seconds','slice_spacing_seconds','leg_lag_seconds','keep_pending','cancel_ack_seconds','duplicate_on_flatten','reconcile_seconds','stale_seconds','pending_aware','target_bounded','ttl_seconds']
    return [dict(mechanics_id=i,name=name,system=system,complexity=cp,parameters=dict(zip(names,values)),assumption='latent hypothetical process; original orders unobserved',
                 maximum_outstanding_per_contract=2 if i==6 else None,parent_fragmentation='one base per expansion request; reductions can be bulk/partial' if i==1 else 'aggregate target delta; configured child slices',duplicate_lag_seconds=1 if i==4 else None,duplicate_minimum_age_seconds=60 if i==4 else None,duplicate_correction_seconds=5 if i==4 else None) for i,(name,system,values,cp) in enumerate(MECHANICS)]

def compile_kernel():
    CACHE.mkdir(exist_ok=True)
    subprocess.run(['g++','-O3','-std=c++17',str(HERE/'execution.cpp'),'-o',str(CACHE/'separated')],check=True)

def definitions():
    return [dict(model_id=p['policy_id']*7+e['mechanics_id'],policy_id=p['policy_id'],mechanics_id=e['mechanics_id'],allocation=p['allocation'],risk=p['risk'],mechanics=e['name'],system=e['system'],complexity=p['complexity']+e['complexity']) for p in policies() for e in mechanics()]

def write_configs(defs,path):
    with open(path,'w') as f:
        for model in defs:
            p=policies()[model['policy_id']];params=MECHANICS[model['mechanics_id']][2]
            f.write(','.join(map(str,[model['model_id'],p['allocation_code'],p['risk_code']]+params))+'\n')

def execute(defs,label,frozen_policy=None,detailed_models=None):
    path=CACHE/f'{label}_configs.csv';write_configs(defs,path);prefix=CACHE/label
    # Rebuild only disposable adapters under this module when the original
    # cache is absent; never rerun a writer against prior committed outputs.
    canonical_cache=market_cache();calibration=calibration_path()
    cmd=[str(CACHE/'separated'),str(canonical_cache/'replay.bin'),str(path),str(calibration),str(prefix)]
    cmd.append(str(frozen_policy if frozen_policy is not None else -1))
    cmd.append(','.join(map(str,detailed_models or [])))
    with open(CACHE/f'{label}_scores.csv','w') as out,open(CACHE/f'{label}.log','w') as err:subprocess.run(cmd,stdout=out,stderr=err,check=True)
    for suffix in ['scores','fills','goals','requests','inventory','coarse','closures','request_audit']:
        if suffix in ['fills','requests','inventory'] and not detailed_models:continue
        if suffix=='coarse' and label=='closed_loop':continue
        src=CACHE/f'{label}_{suffix}.csv';dest=HERE/f'{label}_{suffix}.csv.gz'
        with src.open('rb') as inp,gzip.GzipFile(filename=str(dest),mode='wb',mtime=0,compresslevel=3) as output:shutil.copyfileobj(inp,output)
    return prefix

def pack_cohort(ids):
    # Full scores/closures/request audits cover84 models; full minute action
    # traces are retained for a cohort selected on August, never later outcomes.
    dest=HERE/'closed_loop_coarse.csv.gz'
    with gzip.open(dest,'wt',compresslevel=3) as output:
        first=True
        for frame in pd.read_csv(CACHE/'closed_loop_coarse.csv',chunksize=200000):
            q=frame[frame.model_id.isin(ids)]
            if len(q):q.to_csv(output,index=False,header=first);first=False
    (HERE/'trace_cohort.json').write_text(json.dumps(dict(model_ids=ids,full_scores_models=84,closures_and_request_audits_models=84,
       detailed_trace_exclusion='stale-ignore-pending negative control has complete aggregate actions and closure diagnostics, not all repetitive child orders'),indent=2))
    for label in ['closed_loop','frozen_targets']:
        for suffix in ['fills','requests','inventory']:
            p=HERE/f'{label}_{suffix}.csv.gz'
            if p.exists():p.unlink()


def score_table(label,defs):
    raw=pd.read_csv(HERE/f'{label}_scores.csv.gz',dtype={'prediction_hash':str});raw=with_metrics(raw)
    meta=json.loads((PRIOR/'outputs/cycle_metadata.json').read_text());known={c['cycle_id']:c['dates'][0]<c['expiry_date'] for c in meta}
    raw['initialization_known']=raw.cycle_id.map(known);raw=raw.rename(columns={'candidate_id':'model_id'})
    lookup=pd.DataFrame(defs);raw=raw.merge(lookup,on='model_id',validate='many_to_one')
    raw['penalized_score']=raw.primary_raw-.002*raw.complexity
    raw.to_csv(HERE/f'{label}_cycle_scores.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3},float_format='%.10g')
    return raw

def run():
    compile_kernel();ps=policies();es=mechanics();defs=definitions()
    pd.DataFrame(ps).to_csv(HERE/'desired_inventory_candidates.csv',index=False)
    pd.DataFrame([dict(e,parameters=json.dumps(e['parameters'],sort_keys=True)) for e in es]).to_csv(HERE/'execution_mechanics_candidates.csv',index=False)
    pd.DataFrame(defs).to_csv(HERE/'model_registry.csv',index=False)
    execute(defs,'closed_loop');raw=score_table('closed_loop',defs)
    eligible=raw[raw.initialization_known&raw.phase.eq(2)];metrics=['event_macro_f1','quantity_score','inventory_score','final_score','primary_raw','penalized_score']
    summary=eligible.groupby(['model_id','policy_id','mechanics_id','system','allocation','risk','mechanics','complexity','split'])[metrics].mean().reset_index()
    summary['cycles']=eligible.groupby(['model_id','split']).size().reindex(pd.MultiIndex.from_frame(summary[['model_id','split']])).to_numpy()
    summary.to_csv(HERE/'policy_vs_execution_comparison.csv',index=False,float_format='%.10g')
    aug=summary[summary.split.eq(1)].sort_values(['penalized_score','complexity','model_id'],ascending=[False,True,True]);best=int(aug.iloc[0].model_id);selected=defs[best]
    # Frozen-stream intervention: all mechanics face the selected policy's SAME
    # safe-generated intents. This does not infer the original hidden decisions.
    common=[d for d in defs if d['policy_id']==selected['policy_id']]
    cohort=[d['model_id'] for d in common]+[0]
    for name,group in aug.groupby('allocation',sort=True):cohort.append(int(group.iloc[0].model_id))
    cohort=list(dict.fromkeys(cohort));pack_cohort(cohort)
    execute(common,'frozen_targets',selected['policy_id']);score_table('frozen_targets',common)
    detailed=[d for d in common if d['mechanics_id']!=6]
    execute(detailed,'detailed',detailed_models=[d['model_id'] for d in detailed])
    config=dict(selected_model=selected,policy=ps[selected['policy_id']],execution=es[selected['mechanics_id']],
       selection='August penalized cycle mean on same32 pre-initialised cycles; later previously inspected',
       opening_frozen_before_evaluation=True,source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       registration_sha256=hashlib.sha256((HERE/'REGISTERED_PLAN.md').read_bytes()).hexdigest(),
       execution_quotes='minute-open proxies at simulated fill times, not tick quotes',canonical_accounting='inherited Replay::fill and score',
       inputs={'motif_source_sha256':hashlib.sha256((ROOT/'research/outputs/playbook_rapid_reversal_motifs.csv').read_bytes()).hexdigest(),
               'cache_sha256':hashlib.sha256((market_cache()/'replay.bin').read_bytes()).hexdigest()})
    (HERE/'selected_model_config.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    print(json.dumps(dict(models=len(defs),selected=selected),indent=2))

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--replay-config',type=Path);args=parser.parse_args()
    if args.replay_config:
        saved=yaml.safe_load(args.replay_config.read_text());selected=saved['selected_model']
        assert saved['policy']==policies()[selected['policy_id']]
        assert saved['execution']==mechanics()[selected['mechanics_id']]
        assert selected==definitions()[selected['model_id']]
        compile_kernel();execute([selected],'saved_replay',detailed_models=[selected['model_id']]);print('Saved configuration replayed without reselection.');return
    run()

if __name__=='__main__':main()
