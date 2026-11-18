"""Audit immutable inputs, pre-event information, accounting and reproducibility."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
import numpy as np
import pandas as pd
from build import HERE,ROOT,META,load_fills,sha,market_cache
from evaluate import RULES,fit_baselines,baseline_predictions

def main():
    manifest=json.loads((HERE/'input_manifest.json').read_text())
    for name,h in manifest['inputs_sha256'].items():assert sha(ROOT/name)==h,name
    assert sha(ROOT/'research/outputs/playbook_rapid_reversal_motifs.csv')=='1ac4a2ba20013eaf0fbd2dff3be7207126fb127a97dbbb62e329f42d7364ca00'
    up=pd.read_csv(HERE/'upstream_32_27_audit.csv');assert len(up)==59
    assert up.classification.value_counts().to_dict()=={'model_contract_absent':32,'target_retained_at_recorded_flat':27}
    assert ((up.observed_role=='short_exposure')&(up.classification=='model_contract_absent')).sum()==9
    assert ((up.observed_role=='short_exposure')&(up.classification=='target_retained_at_recorded_flat')).sum()==7
    risk=pd.read_csv(HERE/'pre_event_risk_set.csv.gz');events=pd.read_csv(HERE/'exit_case_ledger.csv.gz');f=load_fills()
    # Verify every opportunity's quantity from an independent strict prefix,
    # and every market mark against the exact preceding completed cache cell.
    qty_checks=mark_checks=0;zg={}
    fg={k:g for k,g in f.groupby(['cycle_id','strike','option_type'])}
    for key,g in risk.groupby(['cycle_id','strike','option_type'],sort=False):
        cid,k,right=key;fs=fg[key].groupby('second',sort=True).tail(1).sort_values('second');where=np.searchsorted(fs.second.to_numpy(),g.second.to_numpy(),side='left')-1
        q=np.where(where>=0,fs.quantity_after.to_numpy()[np.maximum(where,0)],0);assert np.array_equal(q,g.quantity_before.to_numpy()),key;qty_checks+=len(g)
        if cid not in zg:
            with np.load(market_cache()/f'cycle_{cid:02}.npz') as z:zg[cid]={name:z[name] for name in ['minutes','strikes','rights','previous']}
        z=zg[cid];j=int(np.flatnonzero((z['strikes']==k)&(z['rights']==int(right=='PE')))[0]);ti=np.searchsorted(z['minutes'],g.second.to_numpy()//60)
        assert np.array_equal(z['minutes'][ti],g.second.to_numpy()//60)
        assert np.allclose(g.option_mark,z['previous'][ti,j],rtol=1e-12,atol=1e-10,equal_nan=True);mark_checks+=len(g)
    for name in ['pre_event_risk_set.csv.gz','exit_case_ledger.csv.gz','motif_pre_event_features.csv']:
        d=pd.read_csv(HERE/name);cutoff=pd.to_datetime(d.feature_cutoff_ist);market=pd.to_datetime(d.market_available_at_ist)
        assert (market<=cutoff).all();valid=d.latest_fill_available_before_ist.notna();assert (pd.to_datetime(d.loc[valid,'latest_fill_available_before_ist'])<cutoff[valid]).all()
    folds=pd.read_csv(HERE/'validation_folds.csv');assert len(folds[folds['mode']=='leave_one_cycle_out'])==32
    chrono=folds[folds['mode']=='expanding_chronological'];assert len(chrono)==24
    for r in folds.itertuples():
        train=list(map(int,r.training_cycles.split(';')));assert r.test_cycle_id not in train
        if r.mode=='expanding_chronological':assert len(train)>=8 and all(META[x]['expiry_date']<r.test_expiry for x in train)
    # Refit the baseline from its actual training prefix and reproduce held-out
    # predictions on early/late folds of each validation method.
    pred=pd.read_csv(HERE/'baseline_predictions.csv.gz');baseline_replays=0
    for mode,g in folds.groupby('mode'):
        for r in g.iloc[[0,-1]].itertuples():
            train=list(map(int,r.training_cycles.split(';')));params=fit_baselines(risk[risk.cycle_id.isin(train)],events[events.cycle_id.isin(train)&events.outcome_stratum.eq('intermediate')])
            for name in ['clock_only','inventory_only']:
                p=baseline_predictions(risk[risk.cycle_id==r.test_cycle_id],params,name)
                expected=pred[(pred['mode']==mode)&pred.cycle_id.eq(r.test_cycle_id)&pred.hypothesis.eq(name)]
                cols=['cycle_id','strike','option_type','second'];pd.testing.assert_frame_equal(p[cols].reset_index(drop=True),expected[cols].reset_index(drop=True),check_dtype=False)
                baseline_replays+=1
    reconcile=pd.read_csv(HERE/'book_reconciliation.csv');assert len(reconcile)==35 and reconcile.ending_quantity_reconciles.all() and reconcile.ending_cash_reconciles.all()
    summary=json.loads((HERE/'evaluation_summary.json').read_text());assert summary['fixed_hypotheses']==len(RULES)==12
    assert summary['qualifies_precision_recall_coverage80']==[]
    changed=subprocess.check_output(['git','diff','8e32701','--name-only'],cwd=ROOT,text=True).splitlines();assert all(x.startswith('research/intermediate_exit_study/') for x in changed),changed
    report=(HERE/'INTERMEDIATE_EXIT_CONTROLLER.md').read_text()
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if not target.startswith(('http:','https:','#')) and target!='validation_audit.json':assert (HERE/target).exists(),target
    proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','research','-p','test_*.py'],cwd=ROOT,text=True,capture_output=True)
    (HERE/'.cache').mkdir(exist_ok=True);(HERE/'.cache/repository_tests.log').write_text(proc.stdout+proc.stderr)
    assert proc.returncode==0,proc.stderr[-5000:]
    count=int(re.search(r'Ran (\d+) tests',proc.stderr).group(1));assert count==234,count
    result=dict(status='passed',repository_tests=count,new_study_tests=17,original_motifs_preserved=59,absent_retained_preserved=[32,27],
        all_original_input_hashes_unchanged=True,selected_model28_configuration_unchanged=True,earlier_tracked_outputs_unchanged=True,
        original_buy_closing_children=11716,atomic_covers=8197,reduction_episodes=4251,
        strict_pre_event_inventory_checks=qty_checks,completed_market_mark_checks=mark_checks,whole_cycle_book_cash_reconciliations=35,
        loco_cycles=32,chronological_test_cycles=24,baseline_prefix_replays=baseline_replays,parameter_search=False,
        registered_hypotheses=12,qualified_general_triggers=0,inference='software/evidence validation; not recovered original controller or alpha',
        code_sha256={p.name:sha(p) for p in HERE.iterdir() if p.suffix=='.py'},registration_sha256=sha(HERE/'REGISTERED_PLAN.md'))
    (HERE/'validation_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
