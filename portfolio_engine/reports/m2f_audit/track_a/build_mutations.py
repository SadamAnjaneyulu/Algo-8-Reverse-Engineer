import json,glob,collections,mutants
R={}
for f in glob.glob('mut_results/*.json'): j=json.load(open(f)); R[j['id']]=j
def cat(fails):
    files=collections.Counter(x.split('::')[0].split('/')[-1] for x in fails); ind=[]
    indep={'test_tp01_reconciliation.py':'TP-01 reference outputs','test_lineage_reference.py':'in-test independent matcher','test_lineage_real.py':'TP-01/TP-02 reference counts+invariants'}
    for k in indep:
        if k in files: ind.append(k)
    xl=[k for k in files if k in('test_parity.py','test_lineage_parity.py')]
    internal=[k for k in files if k in('test_accounting.py','test_lineage.py','test_lineage_mutations.py')]
    return dict(files=dict(files),independent_reference_tests=ind,xlang_tests=xl,internal_or_handcomputed_tests=internal)
out=[]
NOTES={'M11':'SURVIVOR of all 127 existing tests: the shift is uniform so ordering, day assignment (max IST time 15:39+5:30 < 24:00) and all aggregates are unchanged; only a comparison of timestamp_s against raw column 161 (my compare_ref_vs_engine) detects it.',
'M17':'Existing-test failures are a consequence of an IndexError crash (deque index out of range) after the wrong lot is popped, i.e. a crash, not a designed invariant detector; counted as crash-not-kill for the existing suite. My reference comparison reports ENGINE_EXCEPTION as well, so also crash-only for own check on the Python engine; fuzz kill compares C++ output to reference only for C-mutants, Python mutants are compared in-process (py_vs_ref) and the crash is flagged.',
'M18':'Killed by the designed role-arithmetic InvariantViolation guard (an internal invariant [INV], same code path family as the mutation but a purpose-built check); not an independent detector.',
'M16':'Convention leak is caught by the LineageSet separation guard (a cross-convention comparison of outputs) and by reference comparison.'}
for m in mutants.M:
    j=R.get(m['id'])
    if not j: out.append(dict(id=m['id'],change=m['name'],expected_detector=m['expected'],existing_tests_caught='NOT RUN',own_check_caught='NOT RUN',detector_independent='n/a',notes='run did not finish')); continue
    e=j['existing_tests']; c=cat(e['failed']); own=j['own']
    caught=bool(e['failed']) or e['returncode']!=0
    ownd=[]
    if own.get('engine_exception'): ownd.append('engine exception: '+own['engine_exception'][:80])
    if own.get('mismatch_summary'): ownd.append('ref mismatches '+json.dumps(own['mismatch_summary']))
    if own.get('false_flags'): ownd.append('false flags '+','.join(own['false_flags'][:6]))
    if own.get('fuzz',{}).get('py_vs_ref_mismatch') or own.get('fuzz',{}).get('cpp_vs_ref_mismatch'): ownd.append(f"fuzz vs ref mismatches py={own['fuzz'].get('py_vs_ref_mismatch')} cpp={own['fuzz'].get('cpp_vs_ref_mismatch')}")
    if own.get('fuzz',{}).get('xlang_byte_mismatch'): ownd.append(f"fuzz xlang byte mismatch {own['fuzz']['xlang_byte_mismatch']}")
    if own.get('cpp_raw_vs_ref_false_keys'): ownd.append('C++ raw run vs ref: '+','.join(own['cpp_raw_vs_ref_false_keys'][:6]))
    if own.get('cpp_vs_py_byte_diff_files'): ownd.append(f"cpp vs py byte diffs {own['cpp_vs_py_byte_diff_files']}")
    indep = bool(c['independent_reference_tests']) or (not caught and bool(own['killed']))
    out.append(dict(id=m['id'],change=f"{m['name']} [{m['file']}]",expected_detector=m['expected'],
        existing_tests_caught=dict(caught=caught,summary=e['summary'],n_failed=len(e['failed']),detecting_test_files=c['files'],failing_tests_sample=e['failed'][:6]),
        own_check_caught=dict(caught=bool(own['killed']),detail=ownd),
        detector_independent=dict(existing_suite_has_independent_reference_detector=bool(c['independent_reference_tests']),independent_reference_test_files=c['independent_reference_tests'],xlang_only_files=c['xlang_tests'],internal_files=c['internal_or_handcomputed_tests'],own_check_is_raw_or_impl=True),
        notes=NOTES.get(m['id'],'')))
json.dump(out,open('mutations.json','w'),indent=1)
for o in out:
    if isinstance(o['existing_tests_caught'],dict): print(o['id'],o['existing_tests_caught']['caught'],o['own_check_caught']['caught'],o['detector_independent']['independent_reference_test_files'],o['detector_independent']['xlang_only_files'])
