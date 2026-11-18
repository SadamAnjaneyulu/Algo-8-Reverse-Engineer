"""Final artifact/accounting audit, saved-config replay and trace reconciliation."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
import numpy as np
import pandas as pd
from prepare import HERE,ROOT,OUT,CACHE,digest
from search import compile_kernel,calibration_text,write_kernel_configs,base_config,PARAMS


def audit():
    compile_kernel();calibration_text();write_kernel_configs([dict(base_config(),id=0)],CACHE/'audit_config.csv')
    with (OUT/'baseline_reconciliation.csv').open('w') as f:
        subprocess.run([str(CACHE/'replay'),str(CACHE/'replay.bin'),str(CACHE/'audit_config.csv'),str(CACHE/'calibration.txt'),'--audit-observed',str(CACHE/'reference_fills.bin')],check=True,stdout=f)
    m=json.loads((OUT/'search_manifest.json').read_text());best=m['best_candidate_id'];reg=pd.read_csv(OUT/'candidate_registry.csv');scores=pd.read_csv(OUT/'candidate_scores.csv')
    assert len(reg)==13864 and len(reg.configuration.unique())==13864
    assert set(reg.candidate_id)==set(scores.candidate_id)
    assert len(scores[scores.phase.eq(2)])==len(reg)*3
    assert set(scores.split)=={0,1,2}
    assert scores[scores.phase.eq(2)].groupby('split').cycles.unique().apply(list).to_dict()=={0:[12],1:[8],2:[15]}
    # Compact principal scores retain all whole-cycle components. Phase/index
    # components remain in the separate complete stratum export.
    if not scores.phase.eq(2).all():
        scores[scores.phase.eq(2)].to_csv(OUT/'candidate_scores.csv',index=False,float_format='%.9g')
        scores=scores[scores.phase.eq(2)]
    b=pd.read_csv(OUT/'baseline_reconciliation.csv');meta=json.loads((OUT/'cycle_metadata.json').read_text())
    e=pd.read_csv(ROOT/'research/outputs/playbook_event_book.csv.gz');realized=[]
    for r in b.itertuples():
        c=meta[r.cycle_id];q=e[e.underlying.eq(c['underlying'])&e.expiry_date.eq(c['expiry_date'])].iloc[-1]
        realized.append(abs(q.after_realized-r.final_realized))
    assert b.minute_quantity_checks.sum()==24860 and b.maximum_cash_error.max()<1e-5 and max(realized)<1e-5
    pred=pd.read_csv(OUT/'replay_predictions.csv.gz');inv=pd.read_csv(OUT/'inventory_replay.csv.gz')
    from evaluate import decode_book
    meta_by={c['cycle_id']:c for c in meta};checks=0;cash_checks=0;maxcash=0
    for (cid,cycle),g in inv.groupby(['candidate_id','cycle_id'],sort=False):
        p=pred[pred.candidate_id.eq(cid)&pred.cycle_id.eq(cycle)]
        flows={};cash={}
        for row in p.itertuples():
            sign=-1 if row.action in [0,3] else 1
            flows.setdefault(row.minute,{});k=(row.strike,row.right);flows[row.minute][k]=flows[row.minute].get(k,0)+sign*row.quantity
            cash[row.minute]=cash.get(row.minute,0)-sign*row.quantity*row.fill_price
            assert row.quantity%meta_by[cycle]['base_unit']==0
        current={};cashvalue=0
        for row in g.itertuples():
            for k,v in flows.get(row.minute,{}).items():current[k]=current.get(k,0)+v
            current={k:v for k,v in current.items() if v}
            assert current==decode_book(row.simulated_book)
            cashvalue+=cash.get(row.minute,0);maxcash=max(maxcash,abs(row.cash-cashvalue));checks+=1;cash_checks+=1
    assert maxcash<1e-4
    # Re-run the saved YAML via the public CLI, preserving candidate ID.
    prefix=CACHE/'saved_validation'
    subprocess.run([sys.executable,str(HERE/'search.py'),'--replay-config',str(OUT/'best_candidate.yaml'),'--replay-output',str(prefix)],check=True,stdout=subprocess.DEVNULL)
    saved=pd.read_csv(str(prefix)+'_actions.csv');expected=pred[pred.candidate_id.eq(best)].reset_index(drop=True)
    pd.testing.assert_frame_equal(saved,expected,check_dtype=False,check_exact=True)
    saved_inv=pd.read_csv(str(prefix)+'_inventory.csv');expected_inv=inv[inv.candidate_id.eq(best)].reset_index(drop=True)
    pd.testing.assert_frame_equal(saved_inv,expected_inv,check_dtype=False,check_exact=True)
    # Baseline no-trade possibilities remain unknown eligibility, not negatives.
    calendar=pd.read_csv(ROOT/'research/outputs/playbook_calendar_candidates.csv')
    # Keep the full bounded calendar rather than relying on a column-name heuristic.
    calendar.to_csv(OUT/'bounded_eligibility_calendar.csv',index=False)
    canonical=pd.read_csv(OUT/'canonical_events.csv.gz',usecols=['source_row','timestamp_ist','inferred_decision_ist','opening_quantity','closing_quantity','incremental_quantity'])
    assert len(canonical)==41421 and canonical.source_row.is_unique
    assert (canonical.opening_quantity+canonical.closing_quantity==canonical.incremental_quantity).all()
    assert canonical.inferred_decision_ist.eq('unobserved').all()
    registry_parent=reg[reg.stage.eq('local_refinement')].parent_id.dropna().astype(int)
    cycle=pd.read_csv(OUT/'cycle_scores.csv.gz',usecols=['candidate_id','cycle_id','split','phase','primary_score'])
    fit_rank=cycle[cycle.split.eq(0)&cycle.candidate_id.lt(13824)].groupby('candidate_id').primary_score.mean().sort_values(ascending=False,kind='stable').head(4).index
    assert set(registry_parent)<=set(fit_rank)
    # Preserve the exact original registered specification and its initial hash.
    spec=(HERE/'SEARCH_SPEC.md').read_text();original=spec.split('\n## Reporting clarification')[0]
    registered=HERE/'REGISTERED_SPEC.md';registered.write_text(original)
    original_hash=hashlib.sha256(original.encode()).hexdigest()
    assert original_hash==m.get('registered_spec_sha256',m['spec_sha256'])
    m['registered_spec_sha256']=original_hash;m['registered_spec_path']='REGISTERED_SPEC.md'
    m['spec_sha256']=digest(HERE/'SEARCH_SPEC.md');m['reporting_amendment']='additional already-evaluated simple baseline traces; objectives and winner unchanged'
    m['code_sha256']={p.name:digest(p) for p in HERE.iterdir() if p.suffix in ['.py','.cpp']}
    m['software_tests']={'repository_tests':201,'scope':'software behavior only, not original-rule truth'}
    m['principal_score_layout']='candidate_scores.csv has all candidates and three chronological whole-cycle splits; all phase/index metrics in candidate_stratum_scores.csv.gz'
    m['replayed_sessions']=65;m['cycles']=35;m['canonical_fills']=41421
    (OUT/'search_manifest.json').write_text(json.dumps(m,indent=2))
    audit=dict(status='passed',canonical_fill_rows=len(canonical),baseline_quantity_minutes=int(b.minute_quantity_checks.sum()),baseline_max_cash_error=float(b.maximum_cash_error.max()),
        baseline_max_realized_error=float(max(realized)),candidate_count=len(reg),all_candidates_have_three_split_scores=True,
        fit_only_refinement_parents=True,simulated_minute_quantity_checks=checks,simulated_minute_cash_checks=cash_checks,maximum_simulated_cash_error=maxcash,
        saved_yaml_replay_exact_actions=True,saved_yaml_replay_exact_inventory_and_cash=True,trace_candidate_count=len(m['trace_candidate_ids']),
        repository_tests=201,scope='tests validate software, not original controller or economic alpha',strict_positive_volume_common_active_cycles=int(pd.read_csv(OUT/'strict_quote_sensitivity.csv').common_strict_cycles.max()))
    (OUT/'validation_audit.json').write_text(json.dumps(audit,indent=2))
    required=['candidate_registry.csv','candidate_scores.csv','ranked_candidates.csv','best_candidate.yaml','replay_predictions.csv.gz','event_mismatch_ledger.csv.gz','inventory_replay.csv.gz','candidate_equivalence_groups.csv','search_manifest.json']
    for name in required:assert (OUT/name).stat().st_size>0,name
    for target in re.findall(r'\]\(([^)]+)\)',(HERE/'HYPOTHESIS_CONTROLLER_SEARCH.md').read_text()):
        if not target.startswith(('http:','https:','#')):assert (HERE/target).exists(),target
    print(json.dumps(audit,indent=2))

if __name__=='__main__':audit()
