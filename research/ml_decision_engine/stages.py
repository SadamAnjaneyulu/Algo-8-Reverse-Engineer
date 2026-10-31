"""Independent resumable jobs; no stage silently implies a final ML assessment."""
from __future__ import annotations
import argparse
import contextlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import time
import traceback
from pathlib import Path
import pandas as pd
from joblib import parallel_config
from threadpoolctl import threadpool_limits
from .checkpoints import atomic_json,atomic_bytes,atomic_frame,sha,runtime_signature
from .dataset import HERE,ROOT,build_dataset
from .models import train_models,chronological_folds,TASKS
from .quantities import run_quantities
from .first_passage import run_first_passage
from .replay import run_replay
from .reporting import summarize,write_report
from .run import snapshot_evidence

STAGE_CODE={
 'dataset':['dataset.py','features.py','checkpoints.py'],
 'actions':['models.py','features.py','checkpoints.py'],
 'quantities':['models.py','quantities.py','checkpoints.py'],
 'exits':['first_passage.py','checkpoints.py'],
 'replay':['replay.py','dataset.py','models.py','checkpoints.py'],
 'report':['reporting.py','checkpoints.py'],
}


def load_csv(path):
    try:return pd.read_csv(path) if Path(path).exists() else pd.DataFrame()
    except pd.errors.EmptyDataError:return pd.DataFrame()


def validate_manifest(path,signature=None,require_complete=True):
    path=Path(path);marker=path/'stage_manifest.json'
    if not marker.exists():return None
    info=json.loads(marker.read_text())
    for name,digest in info.get('code_sha256',{}).items():
        if sha(HERE/name)!=digest:raise RuntimeError(f'Stage scientific code changed: {path}: {name}')
    if signature is not None and info['signature']!=signature:
        raise RuntimeError(f'Stale checkpoint: {path}; input/protocol/code signature differs')
    if require_complete and info['status']!='complete':return None
    if info['status']=='complete':
        for name,digest in info['output_sha256'].items():
            p=path/name
            if not p.is_file() or sha(p)!=digest:raise RuntimeError(f'Corrupt/missing saved stage output: {p}')
    return info


def finish_manifest(out,info,status):
    info.update(status=status,finished_unix=time.time())
    if status=='complete':
        info['output_sha256']={str(p.relative_to(out)):sha(p) for p in out.rglob('*')
            if p.is_file() and p.name not in ['stage_manifest.json','failure_evidence.json'] and not p.name.endswith('.tmp')}
    atomic_json(out/'stage_manifest.json',info)


def copy_models(source,target):
    target.mkdir(parents=True,exist_ok=True)
    for path in (source/'selected_model_configurations').glob('*'):
        dest=target/path.name
        if dest.exists() and sha(dest)!=sha(path):raise RuntimeError(f'Conflicting model shards: {path.name}')
        if not dest.exists():shutil.copy2(path,dest)


def gather_actions(root,meta,protocol,require_all=True):
    frames=[];labels=[];scores=[];importance=[];configs=[];completed=[]
    expected=len(list(chronological_folds(meta,protocol)))
    target=root/'assembled/selected_model_configurations'
    for fold in range(expected):
        path=root/'actions'/f'fold_{fold:02}'
        info=validate_manifest(path)
        if not info:
            if require_all:raise RuntimeError(f'Action fold {fold} incomplete; refusing downstream evaluation')
            continue
        completed.append(fold)
        frames.append(pd.read_parquet(path/'held_cycle_predictions.parquet'))
        labels.append(pd.read_parquet(path/'market_regime_labels.parquet'))
        scores.append(load_csv(path/'chronological_validation_results.csv'))
        importance.append(load_csv(path/'feature_importance_by_action.csv'))
        configs.extend(json.loads((path/'configurations.json').read_text()))
        copy_models(path,target)
    cat=lambda xs:pd.concat(xs,ignore_index=True) if xs else pd.DataFrame()
    return cat(scores),cat(frames),configs,cat(labels),cat(importance),completed


def gather_quantities(root,meta,protocol,require_all=True):
    scores=[];configs=[];completed=[]
    for fold in range(len(list(chronological_folds(meta,protocol)))):
        path=root/'quantities'/f'fold_{fold:02}'
        if not validate_manifest(path):
            if require_all:raise RuntimeError(f'Quantity fold {fold} incomplete; actions must not be retrained')
            continue
        completed.append(fold);scores.append(load_csv(path/'allocation_model_scores.csv'))
        configs.extend(json.loads((path/'configurations.json').read_text()))
        copy_models(path,root/'assembled/selected_model_configurations')
    return pd.concat(scores,ignore_index=True) if scores else pd.DataFrame(),configs,completed


def resource_evidence():
    evidence={'thread_limits':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','JOBLIB_TEMP_FOLDER']}}
    try:
        import resource
        evidence['max_rss_linux_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:pass
    temp=Path(os.environ.get('JOBLIB_TEMP_FOLDER','/tmp/algo8-joblib'))
    evidence['joblib_temp_bytes']=sum(p.stat().st_size for p in temp.rglob('*') if p.is_file()) if temp.exists() else 0
    return evidence


def run(stage,root,fold=None,level=None):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((HERE/'protocol.json').read_text())
    if stage=='dataset':
        out=root/'dataset';inputs=snapshot_evidence();extra=None
    else:
        ds=validate_manifest(root/'dataset')
        if not ds:raise RuntimeError('Validated complete dataset stage is required')
        inputs={'dataset_signature':ds['signature'],**{k:v for k,v in ds['output_sha256'].items()
            if k in ['canonical_ml_decision_dataset.parquet','cycle_metadata.json','fold_plan.json']}}
        out=root/(stage if stage in ['exits','report'] else f'{stage}/fold_{fold:02}')
        extra={'fold':fold}  # level changes execution scope, never model identity
        if stage in ['quantities','replay']:
            action_folds=[fold] if stage=='quantities' else range(len(json.loads((root/'dataset/fold_plan.json').read_text())))
            for f in action_folds:
                info=validate_manifest(root/'actions'/f'fold_{f:02}')
                if not info:raise RuntimeError(f'Action fold {f} incomplete')
                inputs[f'action_fold_{f}']=info['signature']
        if stage=='replay':
            for f in range(len(json.loads((root/'dataset/fold_plan.json').read_text()))):
                info=validate_manifest(root/'quantities'/f'fold_{f:02}')
                if not info:raise RuntimeError(f'Quantity fold {f} incomplete')
                inputs[f'quantity_fold_{f}']=info['signature']
    signature=runtime_signature(protocol,inputs,[HERE/p for p in STAGE_CODE[stage]],extra)
    out.mkdir(parents=True,exist_ok=True)
    previous=validate_manifest(out,signature,require_complete=False)
    if previous and previous['status']=='complete':
        print('RESUME: verified complete stage; no refitting:',stage,fold,flush=True);return out
    info=dict(stage=stage,fold=fold,status='running',signature=signature,input_sha256=inputs,
              code_sha256={p:sha(HERE/p) for p in STAGE_CODE[stage]},
              protocol_sha256=sha(HERE/'protocol.json'),started_unix=time.time(),
              github_run_url=os.environ.get('ALGO8_RUN_URL'),resources_before=resource_evidence())
    atomic_json(out/'stage_manifest.json',info)
    try:
        if stage=='dataset':
            data,meta=build_dataset(out,resume_signature=signature)
            atomic_json(out/'cycle_metadata.json',meta)
            folds=list(chronological_folds(meta,protocol));atomic_json(out/'fold_plan.json',list(range(len(folds))))
            after={p:sha(ROOT/p) for p in inputs}
            if inputs!=after:raise AssertionError('Original evidence modified during data preparation')
            info.update(dataset_rows=len(data),cycles=len(meta),prior_evidence_changed=[])
            status='complete'
        else:
            meta=json.loads((root/'dataset/cycle_metadata.json').read_text())
            folds=list(chronological_folds(meta,protocol))
            ids=None if fold is None else set(folds[fold][1]+folds[fold][2])
            path=root/'dataset/canonical_ml_decision_dataset.parquet'
            data=pd.read_parquet(path,filters=[('cycle_id','in',sorted(ids))]) if ids is not None else pd.read_parquet(path)
            if stage=='actions':
                score,pred,configs,labels=train_models(data,meta,protocol,out,fold_ids=[fold],levels=[level] if level else None,signature=signature)
                atomic_json(out/'configurations.json',configs)
                expected=sum(map(len,TASKS.values()))
                done=len(list((out/'checkpoints').glob('action_*/complete.json')))
                status='complete' if done==expected else 'partial'
            elif stage=='quantities':
                pred=pd.read_parquet(root/'actions'/f'fold_{fold:02}'/'held_cycle_predictions.parquet')
                score,configs=run_quantities(data,meta,protocol,pred,out,fold_ids=[fold],levels=[level] if level else None,signature=signature)
                atomic_json(out/'configurations.json',configs)
                done=len(list((out/'checkpoints').glob('quantity_*/complete.json')))
                status='complete' if done==64 else 'partial'
            elif stage=='exits':
                run_first_passage(data,protocol,out,meta);status='complete'
                atomic_bytes(out/'PARTIAL_RESEARCH_REPORT.md',b'# Exit diagnostics complete\n\nStop, profit-target and trailing intent remain unobserved. This stage does not establish an identified original exit rule or final 75% assessment.\n')
            elif stage=='replay':
                _,pred,configs,_,_,_=gather_actions(root,meta,protocol)
                _,qconfigs,_=gather_quantities(root,meta,protocol)
                copy_models(root/'assembled',out/'selected_model_configurations')
                run_replay(configs,qconfigs,pred,meta,protocol,out,fold_ids=[fold]);status='complete'
            else:
                assemble_report(root,out,data,meta,protocol,info)
                status=info.get('assessment_status','partial')
        info['resources_after']=resource_evidence()
        finish_manifest(out,info,status)
        print('STAGE',stage,'FOLD',fold,'STATUS',status,flush=True)
        return out
    except BaseException:
        info['resources_after']=resource_evidence();info['error']=traceback.format_exc()
        atomic_json(out/'failure_evidence.json',info)
        finish_manifest(out,info,'interrupted_or_failed')
        atomic_bytes(out/'FAILURE_REPORT.md',('# Incomplete stage\n\nCompleted checkpoints are retained and will be verified before reuse. No final ML assessment is claimed.\n\n```text\n'+info['error']+'\n```\n').encode())
        raise


def assemble_report(root,out,data,meta,protocol,info):
    scores,pred,configs,labels,importance,action_done=gather_actions(root,meta,protocol,require_all=False)
    quantity,qconfigs,quantity_done=gather_quantities(root,meta,protocol,require_all=False)
    expected=len(list(chronological_folds(meta,protocol)))
    replay_frames=[];replay_done=[]
    for fold in range(expected):
        path=root/'replay'/f'fold_{fold:02}'
        if validate_manifest(path):
            replay_frames.append(load_csv(path/'autonomous_replay_scores.csv'));replay_done.append(fold)
    exits=validate_manifest(root/'exits') is not None
    status={'action_folds':action_done,'quantity_folds':quantity_done,'replay_folds':replay_done,'exits_complete':exits,'expected_folds':expected}
    atomic_json(out/'stage_completion_status.json',status)
    atomic_frame(scores,out/'chronological_validation_results.csv')
    atomic_frame(quantity,out/'allocation_model_scores.csv')
    atomic_frame(importance,out/'feature_importance_by_action.csv')
    agg,strata=summarize(data,scores,pred,labels,protocol,out)
    replay=pd.concat(replay_frames,ignore_index=True) if replay_frames else pd.DataFrame()
    atomic_frame(replay,out/'autonomous_replay_scores.csv')
    complete=len(action_done)==len(quantity_done)==len(replay_done)==expected and exits
    info.update(status='complete' if complete else 'partial',assessment_status='complete' if complete else 'partial',
        source_revision=protocol['source_revision'],dataset_rows=len(data),stage_completion=status)
    write_report(out,agg,strata,replay,info)
    if not complete:
        report=out/'ML_DECISION_ENGINE_RESEARCH_REPORT.md'
        text=report.read_text()
        prefix='# INCOMPLETE STUDY - no final ML assessment\n\n'+json.dumps(status,indent=2)+'\n\nCompleted-stage metrics below are partial. They do not assess the full 75% autonomous-replay target. Missing stages are not successes.\n\n'
        atomic_bytes(report,(prefix+text).encode())
    print('PARTIAL STATUS',json.dumps(status),flush=True)
    if len(agg):print(agg[['level','action','feature_set','precision','recall','f1']].to_csv(index=False),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=list(STAGE_CODE),required=True)
    parser.add_argument('--root',type=Path,default=HERE/'results')
    parser.add_argument('--fold',type=int)
    parser.add_argument('--level',choices=['basket','side','contract'])
    args=parser.parse_args()
    if args.stage in ['actions','quantities','replay'] and args.fold is None:parser.error('--fold is required')
    def interrupted(signum,frame):raise InterruptedError(f'Runner signal {signum}; retaining completed checkpoints')
    signal.signal(signal.SIGTERM,interrupted)
    os.environ.setdefault('JOBLIB_TEMP_FOLDER',str(args.root.resolve()/'joblib-temp'))
    Path(os.environ['JOBLIB_TEMP_FOLDER']).mkdir(parents=True,exist_ok=True)
    # No process-based joblib pools or shared-memory mapping. This changes
    # execution resources, not folds, model families, features or score standards.
    with parallel_config(backend='threading',n_jobs=1,max_nbytes=None),threadpool_limits(limits=1):
        run(args.stage,args.root,args.fold,args.level)


if __name__=='__main__':main()
