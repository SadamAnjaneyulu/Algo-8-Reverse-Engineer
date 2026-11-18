"""Final input, accounting, numerical-reproduction and software audit."""
import hashlib,json,os,platform,re,subprocess,sys
import numpy as np
import pandas as pd
import scipy
from inputs import HERE,ROOT,sha,COSTS

def run():
    audit=json.loads((HERE/'input_audit.json').read_text())
    for name,h in audit['immutable_inputs_sha256'].items():assert sha(ROOT/name)==h,name
    strong=subprocess.check_output(['git','show','f5b4ab8:STRONG_FINDINGS.md'],cwd=ROOT);assert hashlib.sha256(strong).hexdigest()==audit['strong_findings_v6_sha256']
    assert audit['canonical_child_checks']==41421 and audit['atomic_books_checked']==21882
    e=pd.read_csv(HERE/'cycle_economic_results.csv');assert len(e)==35 and e.known_initialization.sum()==32 and (e.known_initialization&e.flat_received_endpoint).sum()==22
    assert e.unpriced_residuals.sum()==0 and e.modeled_endpoint_prices.sum()==0
    np.testing.assert_allclose(e.gross_realised_pnl+e.marked_unrealised_pnl,e.marked_economic_pnl,rtol=0,atol=1e-6)
    np.testing.assert_allclose(e.fill_cashflow+e.residual_marked_value,e.marked_economic_pnl,rtol=0,atol=1e-6)
    immutable_before={name:sha(ROOT/name) for name in audit['immutable_inputs_sha256']}
    # Recompute all economic, benchmark, attribution and inference tables from
    # the audited cache. Exact byte equality is required for saved numeric CSVs
    # and the verdict; no new model definition/parameter search is run.
    numerical=[p for p in HERE.iterdir() if p.suffix=='.csv' or p.name.endswith('.csv.gz') or p.name=='final_verdict.json']
    numerical=[p for p in numerical if p.name not in ['data_quality_and_coverage.csv','residual_position_ledger.csv']]
    before={p.name:sha(p) for p in numerical};env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1'
    (HERE/'.cache').mkdir(exist_ok=True)
    with (HERE/'.cache/reproduction.log').open('w') as stream:
        for script in ['economics.py','benchmarks.py','attribution.py','summarize.py']:
            subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,env=env,check=True,stdout=stream,stderr=subprocess.STDOUT)
    after={p.name:sha(p) for p in numerical};assert before==after,[n for n in before if before[n]!=after[n]]
    assert immutable_before=={name:sha(ROOT/name) for name in immutable_before}
    changed=subprocess.check_output(['git','diff','12dc6af','--name-only'],cwd=ROOT,text=True).splitlines();assert all(p.startswith('research/final_alpha_attribution/') for p in changed),changed
    report=(HERE/'FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md').read_text()
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if not target.startswith(('http:','https:','#')) and target!='validation_audit.json':assert (HERE/target).exists(),target
    required=['FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md','data_quality_and_coverage.csv','cycle_economic_results.csv','cycle_pnl_decomposition.csv','benchmark_comparison.csv','cost_stress_results.csv','risk_and_drawdown_summary.csv','leave_one_cycle_out.csv','attribution_counterexamples.csv','final_verdict.json','run.py']
    assert all((HERE/n).exists() for n in required)
    proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','research','-p','test_*.py'],cwd=ROOT,env=env,text=True,capture_output=True)
    (HERE/'.cache/repository_tests.log').write_text(proc.stdout+proc.stderr);assert proc.returncode==0,proc.stderr[-5000:]
    count=int(re.search(r'Ran (\d+) tests',proc.stderr).group(1));assert count==252,count
    verdict=json.loads((HERE/'final_verdict.json').read_text());assert verdict['outcome']=='B' and verdict['data_support_economic_alpha'] is False and verdict['research_closed'] is True
    result=dict(status='passed',repository_tests=count,new_economic_tests=18,canonical_child_checks=audit['canonical_child_checks'],atomic_book_checks=audit['atomic_books_checked'],
        raw_quote_minute_equity_checks=audit['raw_quote_minute_equity_checks'],max_quote_reconciliation_error=audit['max_mark_reconciliation_error'],
        source_files_hashed=len(audit['immutable_inputs_sha256']),all_source_hashes_unchanged=True,strong_findings_v6_preserved=True,earlier_configs_and_outputs_unchanged=True,
        primary_cycles=32,uncertain_initialization_sensitivity_cycles=3,primary_flat_cycles=22,all_endpoint_marks_quoted=True,modeled_endpoint_valuations=0,
        exactly_reproduced_numeric_artifacts=len(before),numeric_artifacts_sha256=after,required_outputs_complete=True,
        final_outcome='B',economic_alpha_established=False,research_closed=True,no_further_search_launched=True,
        code_sha256={p.name:sha(p) for p in HERE.iterdir() if p.suffix=='.py'},
        environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__),
        interpretation='software/accounting/reproduction validation, not verified broker NAV, settlement, original rule truth or alpha')
    (HERE/'validation_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['numeric_artifacts_sha256','code_sha256']},indent=2))
if __name__=='__main__':run()
