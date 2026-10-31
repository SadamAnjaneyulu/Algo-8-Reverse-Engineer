"""Fault injection and resume integrity, independent of real research outcomes."""
import json
from pathlib import Path
import pandas as pd
import pytest
from .checkpoints import CheckpointStore,atomic_json,atomic_frame,publish_partial,sha
from .stages import validate_manifest,finish_manifest


def test_torn_checkpoint_without_commit_marker_is_never_loaded(tmp_path):
    p=tmp_path/'checkpoints/fold0';p.mkdir(parents=True)
    (p/'payload.pkl').write_bytes(b'partial bytes from a killed write')
    assert CheckpointStore(tmp_path,'same-inputs').load('fold0') is None


def test_resume_survives_new_process_and_does_not_refit(tmp_path):
    calls=[]
    def task():calls.append('fit');return {'precision':.4,'recall':.3}
    store=CheckpointStore(tmp_path,'same-inputs')
    value=store.load('fold0')
    if value is None:store.save('fold0',task())
    # New store simulates a fresh runner restored from its artifact.
    restored=CheckpointStore(tmp_path,'same-inputs').load('fold0')
    if restored is None:task()
    assert calls==['fit'] and restored=={'precision':.4,'recall':.3}


def test_changed_inputs_or_protocol_reject_checkpoint(tmp_path):
    CheckpointStore(tmp_path,'old').save('fold0',{'result':1})
    with pytest.raises(RuntimeError,match='signature mismatch'):
        CheckpointStore(tmp_path,'new').load('fold0')


def test_corrupt_or_missing_model_is_not_reused(tmp_path):
    model=tmp_path/'model.pkl';model.write_bytes(b'original')
    store=CheckpointStore(tmp_path,'same');store.save('fold0',{'result':1},[model])
    model.write_bytes(b'corrupt')
    with pytest.raises(RuntimeError,match='corrupt'):store.load('fold0')


def test_failed_quantity_does_not_invalidate_completed_action(tmp_path):
    action=tmp_path/'actions/fold_00';action.mkdir(parents=True)
    atomic_frame(pd.DataFrame({'precision':[.4]}),action/'scores.csv')
    finish_manifest(action,{'signature':'actions-input','stage':'actions'},'complete')
    quantity=tmp_path/'quantities/fold_00';quantity.mkdir(parents=True)
    finish_manifest(quantity,{'signature':'quantity-input','error':'injected interruption'},'interrupted_or_failed')
    assert validate_manifest(action,'actions-input')['status']=='complete'
    assert validate_manifest(quantity,'quantity-input') is None
    # Failure is not silently converted into an empty successful quantity stage.
    assert json.loads((quantity/'stage_manifest.json').read_text())['status']=='interrupted_or_failed'


def test_completed_stage_checks_every_output_before_skip(tmp_path):
    output=tmp_path/'scores.csv';output.write_text('precision\n0.4\n')
    finish_manifest(tmp_path,{'signature':'same','stage':'actions'},'complete')
    assert validate_manifest(tmp_path,'same')['status']=='complete'
    output.write_text('precision\n1.0\n')
    with pytest.raises(RuntimeError,match='Corrupt'):validate_manifest(tmp_path,'same')


def test_partial_report_never_claims_final_assessment(tmp_path):
    publish_partial(tmp_path,'actions',1,6,pd.DataFrame({'precision':[.8],'recall':[.8]}))
    state=json.loads((tmp_path/'partial_progress.json').read_text())
    assert state['status']=='partial' and state['final_assessment'] is False
    assert 'No final 75%' in (tmp_path/'PARTIAL_RESEARCH_REPORT.md').read_text()


def test_stage_skip_cannot_accept_wrong_signature(tmp_path):
    (tmp_path/'scores.csv').write_text('value\n1\n')
    finish_manifest(tmp_path,{'signature':'old'},'complete')
    with pytest.raises(RuntimeError,match='Stale checkpoint'):validate_manifest(tmp_path,'new')


def test_failed_atomic_replace_preserves_prior_file(tmp_path,monkeypatch):
    from . import checkpoints
    p=tmp_path/'status.json';atomic_json(p,{'version':1})
    def fail(*args):raise OSError('injected shutdown before replace')
    monkeypatch.setattr(checkpoints.os,'replace',fail)
    with pytest.raises(OSError):atomic_json(p,{'version':2})
    assert json.loads(p.read_text())=={'version':1}


def test_thread_execution_preserves_registered_protocol():
    from .dataset import HERE
    protocol=json.loads((HERE/'protocol.json').read_text())
    assert protocol['precision_target']==protocol['recall_target']==.75
    assert protocol['minimum_training_cycles']==8
    assert protocol['test_block_cycles']==4
    assert protocol['inner_validation_cycles']==2
    assert protocol['models']==['logistic','lightgbm','catboost','gam','hazard']


def test_interrupted_stage_keeps_failure_evidence_and_then_resumes(tmp_path,monkeypatch):
    from . import stages
    monkeypatch.setattr(stages,'snapshot_evidence',lambda:{})
    monkeypatch.setattr(stages,'runtime_signature',lambda *args,**kwargs:'same-run')
    calls=[]
    def fail(*args,**kwargs):
        calls.append('interrupted')
        raise InterruptedError('injected runner shutdown')
    monkeypatch.setattr(stages,'build_dataset',fail)
    with pytest.raises(InterruptedError):stages.run('dataset',tmp_path)
    out=tmp_path/'dataset'
    assert (out/'failure_evidence.json').exists()
    assert validate_manifest(out,'same-run') is None
    def recover(path,**kwargs):
        calls.append('recover')
        frame=pd.DataFrame({'cycle_id':[0]})
        atomic_frame(frame,path/'canonical_ml_decision_dataset.parquet')
        return frame,[]
    monkeypatch.setattr(stages,'build_dataset',recover)
    stages.run('dataset',tmp_path)
    stages.run('dataset',tmp_path)
    assert calls==['interrupted','recover']
    assert validate_manifest(out,'same-run')['status']=='complete'


def test_workflow_saves_groups_and_does_not_cancel_older_studies():
    import yaml
    from .dataset import ROOT
    w=yaml.safe_load((ROOT/'.github/workflows/algo8-ml-research.yml').read_text())
    assert w['concurrency']['cancel-in-progress'] is False
    assert set(w['jobs'])=={'dataset','actions','quantities','exits','replay','report'}
    assert 'always()' in w['jobs']['report']['if']
    for name,job in w['jobs'].items():
        uploads=[s for s in job['steps'] if s.get('uses','').startswith('actions/upload-artifact@')]
        assert uploads and all(s['if']=='always()' for s in uploads)
    assert len([s for s in w['jobs']['actions']['steps'] if s.get('uses','').startswith('actions/upload-artifact@')])==3
    assert w['env']['OMP_NUM_THREADS']=='1'
    quantity_commands=' '.join(s.get('run','') for s in w['jobs']['quantities']['steps'])
    assert '--stage actions' not in quantity_commands
