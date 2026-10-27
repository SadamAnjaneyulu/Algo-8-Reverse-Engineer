"""Deterministic grammar, staged autonomous replay, reconstruction ranking."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,itertools,json,os,shutil,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from prepare import HERE,ROOT,OUT,CACHE,digest

ALLOC=['index_clock','pooled_clock','fixed_increment','target_restore','replace_covers','clock_risk_iv']
EXITS=['deadline_only','premium_loss30','premium_loss50','premium_loss75','profit90','profit50_trail20','adverse_spot0p3','adverse_spot0p5','side_equity100k','expiry_cycle_equity200k','carry4pct_debit','premium50_or_capital200k']
GATES=['none','range15_le0p35','efficiency15_le0p70']
WINGS=['seed_then_budget','budget_always','fixed_distance','seed_budget_decay_refresh']
REENTRY=['scheduled_only','cooldown5_then_one','cooldown15_then_one','lock_after_short_flat']
FINALS=['fixed1514','phase_date_deadline']
REFS=['completed_close','median_last3_closes']
WEIGHTS={'primary':[.4,.2,.3,.1],'event_heavy':[.6,.15,.15,.1],'inventory_heavy':[.25,.15,.5,.1]}
PARAMS=['id','allocation','exit','gate','wing','reentry','final','reference','latency','scale','budget','loss_override','cap_scale','close_fraction','deadline_shift']


def base_config():return dict(allocation=0,exit=0,gate=0,wing=0,reentry=0,final=0,reference=0,latency=0,scale=1.,budget=.025,loss_override=0.,cap_scale=1.,close_fraction=1.,deadline_shift=0)

def key(config):return json.dumps({k:v for k,v in config.items() if k not in ['id','parent_id','stage']},sort_keys=True,separators=(',',':'))

def complexity(c):
    return (3+[2,1,0,3,2,5][c['allocation']]+[0,1,1,1,1,3,2,2,3,3,5,4][c['exit']]
            +[0,2,2][c['gate']]+[2,1,0,4][c['wing']]+[0,3,3,1][c['reentry']]+c['final']+c['reference']
            +sum(c[k]!=base_config()[k] for k in ['latency','scale','budget','loss_override','cap_scale','close_fraction','deadline_shift']))


def main_bank():
    configs=[]
    for values in itertools.product(range(6),range(12),range(3),range(4),range(4),range(2),range(2)):
        c=base_config();c.update(dict(zip(['allocation','exit','gate','wing','reentry','final','reference'],values)))
        changes=sum(c[k]!=base_config()[k] for k in ['allocation','exit','gate','wing','reentry','final','reference'])
        c.update(id=len(configs),parent_id=None,stage='baseline' if changes==0 else 'component' if changes==1 else 'combination')
        configs.append(c)
    assert len(configs)==13824 and len({key(c) for c in configs})==len(configs)
    return configs


def registry(configs):
    rows=[]
    for c in configs:
        rows.append(dict(candidate_id=c['id'],stage=c['stage'],parent_id=c['parent_id'],definition_sha256=hashlib.sha256(key(c).encode()).hexdigest(),
              allocation=ALLOC[c['allocation']],exit=EXITS[c['exit']],gate=GATES[c['gate']],wing=WINGS[c['wing']],reentry=REENTRY[c['reentry']],
              final=FINALS[c['final']],reference=REFS[c['reference']],complexity=complexity(c),configuration=key(c),
              calendar='received sessions only; eligibility unknown',chain='historically selected stored contracts',
              greek_model='flat ATM implied-volatility surface',execution='candle open; missing request unfilled'))
    return pd.DataFrame(rows)


def write_kernel_configs(configs,path):
    with open(path,'w') as f:
        for c in configs:f.write(','.join(str(c[k]) for k in PARAMS)+'\n')


def calibration_text():
    c=json.loads((OUT/'calibration.json').read_text())
    vals=np.array(c['index_clock']).ravel().tolist()+np.array(c['pooled_clock']).ravel().tolist()
    for row in c['caps']:vals.extend(row[k] for k in ['side_units','vega_rupees','iv_pct'])
    (CACHE/'calibration.txt').write_text(' '.join(map(str,vals)))


def compile_kernel():
    subprocess.run(['g++','-O3','-std=c++17',str(HERE/'replay.cpp'),'-o',str(CACHE/'replay')],check=True)


def replay_batch(configs,label,workers=4):
    # Independent process partitions share no mutable state. Scores stream to gzip.
    partitions=[configs[i::workers] for i in range(workers)]
    def work(pair):
        i,cs=pair;path=CACHE/f'{label}_{i}.csv';write_kernel_configs(cs,path)
        with gzip.open(OUT/f'cycle_scores_{label}_{i}.csv.gz','wt',compresslevel=3) as out,open(CACHE/f'{label}_{i}.log','w') as err:
            proc=subprocess.Popen([str(CACHE/'replay'),str(CACHE/'replay.bin'),str(path),str(CACHE/'calibration.txt')],stdout=subprocess.PIPE,stderr=err,text=True)
            for chunk in iter(lambda:proc.stdout.read(1<<20),''):out.write(chunk)
            if proc.wait():raise RuntimeError(f'Kernel failed, see {err.name}')
        return OUT/f'cycle_scores_{label}_{i}.csv.gz'
    with ThreadPoolExecutor(max_workers=workers) as pool:return list(pool.map(work,enumerate(partitions)))


def with_metrics(d):
    d=d.copy()
    for r in range(4):
        p=d[f'pred{r}'];a=d[f'actual{r}'];m=d[f'match{r}']
        d[f'precision{r}']=m/p.replace(0,np.nan);d[f'recall{r}']=m/a.replace(0,np.nan)
        d[f'f1_{r}']=np.where(p+a>0,2*m/(p+a),np.nan)
    d['event_macro_f1']=d[[f'f1_{r}' for r in range(4)]].mean(axis=1)
    d['quantity_score']=np.where(d.qdenom>0,1-d.qerror/d.qdenom,1.)
    d['inventory_score']=np.where(d.inventory_denom>0,1-d.inventory_error/d.inventory_denom,1.)
    d['final_score']=np.where(d.final_target>0,d.final_match/d.final_target,np.nan)
    # No target is unavailable, not a manufactured correct closure. Renormalize weights.
    for name,w in WEIGHTS.items():
        v=d[['event_macro_f1','quantity_score','inventory_score','final_score']].to_numpy();valid=np.isfinite(v)
        d[name+'_raw']=np.nansum(v*np.array(w),axis=1)/(valid*np.array(w)).sum(axis=1)
    return d


def load_cycle_scores(files,configs):
    frames=[pd.read_csv(p,dtype={'prediction_hash':str}) for p in files];d=pd.concat(frames,ignore_index=True)
    d=d[d.minutes.gt(0)].copy()
    for r in range(4):assert (d[f'match{r}']<=d[f'pred{r}']).all() and (d[f'match{r}']<=d[f'actual{r}']).all()
    assert (d.qerror>=-1e-5).all() and (d.qerror<=d.qdenom+1e-5).all()
    d=with_metrics(d)
    d['complexity']=d.candidate_id.map({c['id']:complexity(c) for c in configs})
    for name in WEIGHTS:d[name+'_score']=d[name+'_raw']-.002*d.complexity
    return d


def aggregate(d,configs):
    # Cycle means of independently scored whole-cycle paths; dependent fills not trials.
    metrics=['event_macro_f1','quantity_score','inventory_score','final_score']+[x+s for x in WEIGHTS for s in ['_raw','_score']]
    metrics+=[f'{n}{r}' for r in range(4) for n in ['pred','actual','match','exactq','exacttime','time1','precision','recall','f1_']]
    metrics+=['qerror','qdenom','timing_abs_minutes','near_strike_matches','inventory_error','inventory_denom','role_error','net_error','unmatched_minutes','observed_unmatched_minutes','final_target','final_match','final_error','unfilled_requests','unfilled_quantity','turnover','cost','realized','final_equity','missing_marks','negative_call_minutes','vega_breach_minutes','max_short_base_units','max_gross_base_units','loss_breach_minutes','max_loss','max_abs_vega','directional_matches','flow_minutes','flow_class_matches']
    metrics=list(dict.fromkeys(metrics))
    grouped=d.groupby(['candidate_id','split','phase'],sort=True)
    scores=grouped[metrics].mean().reset_index()
    scores['cycles']=grouped.size().to_numpy()
    scores['complexity']=scores.candidate_id.map({c['id']:complexity(c) for c in configs})
    scores['index']='pooled'
    scores[scores.phase.eq(2)].to_csv(OUT/'candidate_scores.csv',index=False,float_format='%.9g')
    strata=d.groupby(['candidate_id','split','index','phase'])[metrics].mean().reset_index()
    strata.to_csv(OUT/'candidate_stratum_scores.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3},float_format='%.9g')
    return scores


def refine(configs,cycle):
    fit=cycle[(cycle.split==0)&(cycle.phase==2)].groupby('candidate_id').primary_score.mean().sort_values(ascending=False,kind='stable')
    parents=fit.head(4).index.tolist();seen={key(c) for c in configs};new=[];discarded=[]
    for pid in parents:
        c=configs[pid]
        variants=[('scale',.75),('scale',1.25),('budget',.02),('budget',.03),('latency',1),('close_fraction',.5),('deadline_shift',-1),('deadline_shift',1)]
        if c['exit'] in [1,2,3,11]:
            loss={1:.3,2:.5,3:.75,11:.5}[c['exit']];variants.extend([('loss_override',loss-.05),('loss_override',loss+.05)])
        if c['exit'] in [8,9,10,11]:variants.extend([('cap_scale',.75),('cap_scale',1.25)])
        for k,v in variants:
            if (k=='budget' and c['wing']==2) or (k=='close_fraction' and c['exit'] not in [1,2,3,4,5,6,7,11]):
                discarded.append(dict(parent_id=pid,parameter=k,value=v,reason='semantically inactive'));continue
            candidate=dict(c);candidate[k]=v
            if key(candidate) in seen:discarded.append(dict(parent_id=pid,parameter=k,value=v,reason='duplicate definition'));continue
            candidate.update(id=len(configs)+len(new),parent_id=pid,stage='local_refinement');new.append(candidate);seen.add(key(candidate))
    pd.DataFrame(discarded,columns=['parent_id','parameter','value','reason']).to_csv(OUT/'discarded_candidates.csv',index=False)
    return new


def select_cohort(scores,configs):
    aug=scores[(scores.split==1)&(scores.phase==2)].sort_values(['primary_score','complexity','candidate_id'],ascending=[False,True,True])
    fit=scores[(scores.split==0)&(scores.phase==2)].sort_values(['primary_score','complexity','candidate_id'],ascending=[False,True,True])
    cohort=[0,16,2320,4624,int(aug.iloc[0].candidate_id),int(fit.iloc[0].candidate_id)]
    for weight in ['event_heavy','inventory_heavy']:cohort.append(int(aug.sort_values([weight+'_score','complexity'],ascending=[False,True]).iloc[0].candidate_id))
    # One component champion per allocation family, ranked on August only.
    for allocation in range(6):
        ids=[c['id'] for c in configs if c['allocation']==allocation]
        cohort.append(int(aug[aug.candidate_id.isin(ids)].iloc[0].candidate_id))
    # Simplicity/accuracy frontier and top candidates are frozen without later selection.
    frontier=[];best=-np.inf
    for cp,g in aug.groupby('complexity',sort=True):
        q=g.sort_values('primary_raw',ascending=False).iloc[0]
        if q.primary_raw>best+1e-12:frontier.append(int(q.candidate_id));best=q.primary_raw
    aug[aug.candidate_id.isin(frontier)].to_csv(OUT/'pareto_frontier.csv',index=False)
    if frontier:cohort.extend([frontier[0],frontier[-1]])
    cohort=list(dict.fromkeys(cohort));return cohort,int(aug.iloc[0].candidate_id)


def trace_cohort(configs,ids):
    path=CACHE/'top_configs.csv';write_kernel_configs([configs[i] for i in ids],path)
    with open(CACHE/'top_scores.csv','w') as out:
        subprocess.run([str(CACHE/'replay'),str(CACHE/'replay.bin'),str(path),str(CACHE/'calibration.txt'),str(CACHE/'top')],stdout=out,check=True)
    for suffix,target in [('actions','replay_predictions.csv.gz'),('inventory','inventory_replay.csv.gz')]:
        with open(CACHE/f'top_{suffix}.csv','rb') as src,gzip.GzipFile(filename=str(OUT/target),mode='wb',mtime=0) as dst:shutil.copyfileobj(src,dst)


def save_configs(configs,best,ids):
    dest=OUT/'top_candidate_configs';dest.mkdir(exist_ok=True)
    for i in ids:
        c=configs[i];(dest/f'candidate_{i:05}.json').write_text(json.dumps(c,indent=2,sort_keys=True))
    c=dict(configs[best]);c['description']=registry([configs[best]]).iloc[0].to_dict();c['calibration_reference']='calibration.json'
    (OUT/'best_candidate.yaml').write_text(yaml.safe_dump(c,sort_keys=False))


def manifest(configs,ids,best):
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    code={p.name:digest(p) for p in HERE.iterdir() if p.suffix in ['.py','.cpp','.md']}
    return dict(schema_version=1,source_revision=revision,strong_findings_revision='4e00077',seed=0,
        candidate_count=len(configs),main_bank_count=13824,failed_candidates=0,discarded_definitions='discarded_candidates.csv',
        grammar=dict(allocation=ALLOC,exit=EXITS,gate=GATES,wing=WINGS,reentry=REENTRY,final=FINALS,reference=REFS),
        scoring_weights=WEIGHTS,complexity_penalty=.002,parameter_count_is_not_sample_size=True,
        fit='expiry <= 2026-07-31',validation='2026-08-01..2026-08-31',later='2026-09-01..2026-10-22, previously inspected',external_validation='none',
        selected_on='internal August cycle mean penalized reconstruction score, never later profit',best_candidate_id=best,trace_candidate_ids=ids,
        inputs='input_hashes.json',code_sha256=code,spec_sha256=digest(HERE/'SEARCH_SPEC.md'),
        causal_input='prior completed minute, own simulated book only; no teacher-forced inventory',
        unsupported=['true account margin','complete option chain','certified entry eligibility','original allocation ownership','verified decision/cancel times'],
        greek_assumption='flat ATM IV surface from previous completed minute; hypothetical simulation Greek approximation',
        execution='selected prior-candle contract; current or latency minute open, missing positive quote = unfilled; no historical trade borrowed as fill',
        final_valuation='same preceding price state as decisions; no settlement invented',
        fragmentation='one base-unit request per 65/20 units for cost; aggregated contract/minute action for reconstruction',
        evidence='canonical_events.csv.gz + canonical_atomic_books.csv.gz; received calendar only')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--replay-config',type=Path);ap.add_argument('--replay-output',type=Path);args=ap.parse_args()
    CACHE.mkdir(exist_ok=True);calibration_text();compile_kernel()
    if args.replay_config:
        c=yaml.safe_load(args.replay_config.read_text());dest=args.replay_output or CACHE/f'saved_{c["id"]}'
        path=CACHE/'saved_config.csv';write_kernel_configs([c],path)
        with open(str(dest)+'_scores.csv','w') as out:
            subprocess.run([str(CACHE/'replay'),str(CACHE/'replay.bin'),str(path),str(CACHE/'calibration.txt'),str(dest)],stdout=out,check=True)
        print('Saved-candidate replay:',dest);return
    start=time.time();configs=main_bank();registry(configs).to_csv(OUT/'candidate_registry.csv',index=False)
    pd.DataFrame(columns=['candidate_id','stage','failure_category','reason']).to_csv(OUT/'failed_candidates.csv',index=False)
    files=replay_batch(configs,'main',args.workers);print('Main bank done in',round(time.time()-start),flush=True)
    cycle=load_cycle_scores(files,configs);new=refine(configs,cycle)
    if new:
        configs.extend(new);more=replay_batch(new,'local',args.workers);files+=more;cycle=load_cycle_scores(files,configs)
    signatures=cycle[cycle.phase.eq(2)].sort_values(['candidate_id','cycle_id']).groupby('candidate_id').prediction_hash.agg(lambda x:hashlib.sha256('|'.join(x).encode()).hexdigest())
    groups=pd.DataFrame({'candidate_id':signatures.index,'prediction_sha256':signatures.values})
    groups['equivalence_group']=groups.prediction_sha256.factorize(sort=True)[0]
    groups['group_size']=groups.groupby('equivalence_group').candidate_id.transform('size')
    groups['definition']='identical full-sample chronological action fingerprints; collision caveat, top-cohort exact traces checked separately'
    groups.to_csv(OUT/'candidate_equivalence_groups.csv',index=False)
    registry(configs).to_csv(OUT/'candidate_registry.csv',index=False)
    # Preserve all per-cycle metrics; remove redundant shard files only after successful consolidation.
    # Full per-cycle traces are persisted for top candidates. All candidates retain
    # whole-cycle metrics and compact per-phase score vectors without redundant CSVs.
    whole=cycle[cycle.phase.eq(2)]
    whole.to_csv(OUT/'cycle_scores.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3},float_format='%.9g')
    phase_columns=['candidate_id','cycle_id','index','split','phase','minutes','event_macro_f1','quantity_score','inventory_score','final_score','primary_raw','primary_score']+[f'f1_{i}' for i in range(4)]
    cycle[cycle.phase.lt(2)][phase_columns].to_csv(OUT/'phase_cycle_scores.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3},float_format='%.9g')
    scores=aggregate(cycle,configs);ids,best=select_cohort(scores,configs)
    aug=scores[(scores.split==1)&(scores.phase==2)].sort_values(['primary_score','complexity','candidate_id'],ascending=[False,True,True]).head(100)
    aug.merge(registry(configs),on=['candidate_id','complexity']).to_csv(OUT/'ranked_candidates.csv',index=False)
    save_configs(configs,best,ids);trace_cohort(configs,ids)
    m=manifest(configs,ids,best);m['elapsed_seconds']=round(time.time()-start,2);(OUT/'search_manifest.json').write_text(json.dumps(m,indent=2))
    for p in files:p.unlink()
    print(json.dumps(dict(candidates=len(configs),best=best,trace_cohort=ids,elapsed_seconds=m['elapsed_seconds']),indent=2))

if __name__=='__main__':main()
