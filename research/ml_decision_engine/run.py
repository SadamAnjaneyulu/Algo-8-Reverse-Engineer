"""Reproducible CLI; audit old evidence, run the study and retain failure state."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import time
import traceback
from pathlib import Path
import pandas as pd
from .dataset import HERE,ROOT,digest,build_dataset
from .models import train_models
from .quantities import run_quantities
from .first_passage import run_first_passage
from .replay import run_replay
from .reporting import summarize,write_report

PRIOR_REPORTS = [
 'STRONG_FINDINGS.md','ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md',
 'research/hypothesis_controller_search/HYPOTHESIS_CONTROLLER_SEARCH.md',
 'research/policy_execution_separation/POLICY_EXECUTION_RECONSTRUCTION.md',
 'research/intermediate_exit_study/INTERMEDIATE_EXIT_CONTROLLER.md',
 'research/final_alpha_attribution/FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md',
]


def snapshot_evidence():
    paths=[ROOT/p for p in PRIOR_REPORTS]
    paths.extend(p for p in (ROOT/'research').rglob('*') if p.is_file() and HERE not in p.parents and '.cache' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.bin'])
    paths.extend(p for p in (ROOT/'data/breeze').rglob('*') if p.is_file())
    paths.extend([ROOT/'Trades_GKOHNP140.csv',ROOT/'Info.txt'])
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(set(paths))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=HERE/'results')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'reproduction_manifest.json').exists():
        raise RuntimeError('Choose an empty output directory; do not overwrite a previous run')
    protocol=json.loads((HERE/'protocol.json').read_text())
    started=time.time()
    manifest=dict(status='started',source_revision=protocol['source_revision'],protocol=protocol,
        python=platform.python_version(),platform=platform.platform(),started_unix=started,
        github_run_url=os.environ.get('ALGO8_RUN_URL'),previously_inspected=True)
    def checkpoint(status):
        manifest.update(status=status,elapsed_seconds=time.time()-started)
        (out/'reproduction_manifest.json').write_text(json.dumps(manifest,indent=2,default=str)+'\n')
        print('Stage:',status,flush=True)
    before={}
    try:
        manifest['packages']={name:importlib.metadata.version(name) for name in ['numpy','pandas','scikit-learn','lightgbm','catboost','interpret-core','shap','pyarrow']}
        manifest['implementation_sha256']={p.name:digest(p) for p in HERE.glob('*.py')}
        manifest['implementation_sha256']['protocol.json']=digest(HERE/'protocol.json')
        before=snapshot_evidence();manifest['input_sha256']=before
        manifest['branch_tracking']=dict(research_base=protocol['source_revision'],branch_heads=protocol['branches'],
            relationship='main ancestor of data/local-breeze-fetch; data branch ancestor of research/strong-findings (15 commits behind)')
        checkpoint('building_canonical_dataset')
        dataset,meta=build_dataset(out)
        manifest['dataset_rows']=len(dataset);manifest['cycles']=len(meta)
        checkpoint('training_chronological_models')
        score,pred,configs,labels=train_models(dataset,meta,protocol,out)
        checkpoint('training_quantity_models')
        quantity,qconfig=run_quantities(dataset,meta,protocol,pred,out)
        checkpoint('first_passage_diagnostics')
        run_first_passage(dataset,protocol,out,meta)
        checkpoint('supported_autonomous_replay')
        replay=run_replay(configs,qconfig,pred,meta,protocol,out)
        checkpoint('summarizing_and_auditing')
        agg,strata=summarize(dataset,score,pred,labels,protocol,out)
        after={p:digest(ROOT/p) for p in before}
        changed=[p for p in before if before[p]!=after[p]]
        manifest['prior_evidence_changed']=changed
        if changed:raise AssertionError(('Existing evidence changed',changed))
        manifest['row_label_definition']='received next-minute execution flow; decisions and intent unobserved'
        manifest['autonomous_status']='own-state replay with unsupported modules abstaining; inspect eligibility ledger'
        manifest['target_75_full_tasks']=int(agg[agg.feature_set.eq('full')].target_75_achieved.sum()) if len(agg) else 0
        checkpoint('complete')
        write_report(out,agg,strata,replay,manifest)
        manifest['output_sha256']={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='reproduction_manifest.json' and not p.name.startswith('.dataset_cycle_')}
        checkpoint('complete')
    except Exception as exc:
        manifest['error']=str(exc);manifest['traceback']=traceback.format_exc()
        checkpoint('failed')
        (out/'ML_DECISION_ENGINE_RESEARCH_REPORT.md').write_text('# ML research execution incomplete\n\nThe run failed before a complete research result was produced. No 75% result, recovered decision engine or economic conclusion is claimed.\n\n'+traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':main()
