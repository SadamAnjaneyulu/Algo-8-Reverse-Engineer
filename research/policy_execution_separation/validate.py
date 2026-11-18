"""Final source, accounting, causal-interface and saved-configuration audit."""
import csv,hashlib,json,re,subprocess,sys
from decimal import Decimal
from pathlib import Path
import pandas as pd
import yaml
from model_runner import HERE,ROOT,PRIOR,definitions
from replay_inputs import market_cache


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    source=ROOT/'research/outputs/playbook_rapid_reversal_motifs.csv';original=pd.read_csv(source);original=original[original.conservative_candidate]
    ledger=pd.read_csv(HERE/'reversal_motif_ledger.csv');manifest=json.loads((HERE/'forensic_manifest.json').read_text())
    assert len(original)==len(ledger)==59 and manifest['source_sha256']==sha(source)
    expected={(r.underlying,r.expiry_date,r.strike,r.option_type,r.close_to_zero_ist,r.opposite_open_ist,r.neutralized_ist) for r in original.itertuples()}
    actual={(r.underlying,r.expiry_date,r.strike,r.option_type,r.first_close_to_zero_ist,r.opposite_open_ist,r.neutralized_ist) for r in ledger.itertuples()}
    assert expected==actual and ledger.motif_id.is_unique
    assert ledger.atomic_quantity_equal.sum()==49 and ledger.same_parent_at_boundary.sum()==0
    # Request and incremental prices remain available observations, not invented
    # intent/order-type labels. Check the inferred limit-bound property directly.
    prices=0
    with (ROOT/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as stream:
        for row in csv.reader(stream):
            limit,price=Decimal(row[17]),Decimal(row[137])
            assert price<=limit+Decimal('.00001') if row[11]=='Buy' else price>=limit-Decimal('.00001')
            prices+=1
    child=pd.read_csv(HERE/'reversal_child_fills.csv.gz');canonical=pd.read_csv(ROOT/'research/outputs/playbook_fill_ledger.csv.gz').set_index('source_row')
    for r in child.itertuples():
        a=canonical.loc[r.source_row]
        assert r.incremental_quantity==a.incremental_quantity and r.parent_id==a.parent_id and r.timestamp_ist==a.timestamp_ist and abs(r.execution_price-a.execution_price)<1e-8
    hypothesis=pd.read_csv(HERE/'reversal_hypothesis_scores.csv')
    assert hypothesis.groupby(['hypothesis','variant']).motif_id.nunique().eq(59).all()
    controls=pd.read_csv(HERE/'all_closure_controls.csv').set_index('sequence_id');matched=pd.read_csv(HERE/'matched_nonreversal_controls.csv')
    for r in matched.itertuples():assert not bool(controls.loc[r.control_id].reopening_opposite)
    # Every model is scored on35 cycles; the primary cohort is the same32 cases.
    scores=pd.read_csv(HERE/'closed_loop_cycle_scores.csv.gz');whole=scores[scores.phase.eq(2)]
    assert len(whole)==84*35 and whole.groupby('model_id').initialization_known.sum().eq(32).all()
    comparison=pd.read_csv(HERE/'policy_vs_execution_comparison.csv');assert set(comparison.model_id)==set(range(84))
    assert comparison.groupby('split').cycles.unique().apply(list).to_dict()=={0:[11],1:[7],2:[14]}
    for label in ['closed_loop','frozen_targets','detailed']:
        audit=pd.read_csv(HERE/f'{label}_request_audit.csv.gz')
        assert (audit.requested_quantity==audit.executed_quantity+audit.cancelled_quantity+audit.failed_quantity+audit.pending_quantity).all()
    # Desired policies and execution processes do not read the historical labels.
    policy=(HERE/'policy.hpp').read_text();execution=(HERE/'execution.cpp').read_text();body=execution[execution.index('struct Execution'):execution.index('void augment_seeds')]
    assert not re.search(r'\bd\.(actual|observed)\b',policy+body)
    # The original opening contradiction is retained and independently re-audited.
    opening=pd.read_csv(HERE/'opening_vs_prior_contradiction.csv')
    old=opening[opening.model.str.startswith('prior')];assert old.both_first_wings_exact.eq(0).all() and old.both_short_gross_exact.eq(0).all()
    selected=yaml.safe_load((HERE/'selected_model_config.yaml').read_text());best=selected['selected_model']['model_id']
    assert selected['selected_model']==definitions()[best]
    # Frozen goals truly are identical across the seven execution interventions.
    goals=pd.read_csv(HERE/'frozen_targets_goals.csv.gz');reference=None
    for model,g in goals.groupby('model_id'):
        events=g.drop(columns='model_id').reset_index(drop=True)
        if reference is None:reference=events
        else:pd.testing.assert_frame_equal(reference,events,check_dtype=False,check_exact=True)
    # Public YAML replay must reproduce all selected child actions and books.
    subprocess.run([sys.executable,str(HERE/'model_runner.py'),'--replay-config',str(HERE/'selected_model_config.yaml')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    for suffix in ['fills','goals','requests','inventory','coarse']:
        replay=pd.read_csv(HERE/f'saved_replay_{suffix}.csv.gz');expected=pd.read_csv(HERE/f'detailed_{suffix}.csv.gz');expected=expected[expected.model_id.eq(best)].reset_index(drop=True)
        pd.testing.assert_frame_equal(replay,expected,check_dtype=False,check_exact=True)
    # Independently rebuilt canonical arrays are byte-identical and did not
    # require overwriting any earlier committed output.
    current=market_cache();cold=market_cache(force_local=True);assert sha(current/'replay.bin')==sha(cold/'replay.bin')
    proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','research','-p','test_*.py'],cwd=ROOT,text=True,capture_output=True)
    (HERE/'.cache/full_test_output.txt').write_text(proc.stdout+proc.stderr);assert proc.returncode==0,proc.stderr[-4000:]
    count=int(re.search(r'Ran (\d+) tests',proc.stderr).group(1));assert count==217
    # All working-tree edits outside this new module remain untouched.
    changed=subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT,text=True).splitlines()
    assert all(path.startswith('research/policy_execution_separation/') for path in changed),changed
    result=dict(status='passed',original_motifs=59,cohort_sha256=sha(source),source_rows_verified=len(child),limit_price_bound_checks=prices,
        simulator_definitions=84,model_cycle_replays=84*35,primary_initialised_cycles=32,primary_split_cycles=[11,7,14],
        request_quantity_conservation=True,policy_execution_do_not_read_historical_targets=True,frozen_target_streams_identical=True,
        prior_0_of32_contradiction_preserved_and_reaudited=True,saved_yaml_exact_child_goal_request_inventory_replay=True,
        cold_cache_byte_identical=True,prior_tracked_outputs_unchanged=True,repository_tests=count,
        interpretation='software and evidence checks, not proof of original controller, cause or economic alpha')
    (HERE/'validation_audit.json').write_text(json.dumps(result,indent=2))
    inherited=PRIOR/'replay.cpp'
    research_manifest=dict(base_research_revision='8524844',base_strong_findings_revision='9ebffe6',registration_sha256=sha(HERE/'REGISTERED_PLAN.md'),
        code_sha256={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.cpp','.hpp']},inherited_replay_sha256=sha(inherited),
        canonical_cache_sha256=sha(current/'replay.bin'),input_manifest_sha256=sha(PRIOR/'outputs/input_hashes.json'),model_definitions=84,
        selected_model_id=best,selection='August penalized cycle means,32 pre-initialised cycles; later data already inspected',
        original_decisions_observed=False,order_submission_cancel_ack_observed=False,limit_field='inferred price-bound candidate, not confirmed order type',
        source_tags='T0/T1 are uninterpreted export categories, not strategy or manual/automated labels',
        remaining_quantity='scheduled child quantity unprocessed by replay end; not confirmation of active original orders',
        prices='causal minute-open execution proxies at simulated time, not tick bid/ask',
        trace_cohort=json.loads((HERE/'trace_cohort.json').read_text()),measurement_audit='MEASUREMENT_NOTES.md',test_count=count)
    (HERE/'research_manifest.json').write_text(json.dumps(research_manifest,indent=2))
    required=['reversal_motif_ledger.csv','reversal_hypothesis_scores.csv','desired_inventory_candidates.csv','execution_mechanics_candidates.csv','policy_vs_execution_comparison.csv','policy_execution_mismatch_ledger.csv.gz','candidate_discriminating_events.csv','selected_model_config.yaml','POLICY_EXECUTION_RECONSTRUCTION.md']
    for name in required:assert (HERE/name).stat().st_size>0,name
    report=(HERE/'POLICY_EXECUTION_RECONSTRUCTION.md').read_text()
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if not target.startswith(('http:','https:','#')):assert (HERE/target).exists(),target
    for path in HERE.glob('saved_replay_*.csv.gz'):path.unlink()
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
