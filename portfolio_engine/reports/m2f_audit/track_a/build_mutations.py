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
OVR={'M01':(True,'RERUN after adding emitted-row-list length check to compare_ref_vs_engine.py: 65,128 observed rows vs reference 41,444. My ORIGINAL comparison was blind (dict keyed by fill id) and caught M01 only through XLANG.'),'M15':(True,'RERUN after adding dump TOTAL checks: remaining_expired_unclosed_units mismatch. ORIGINAL comparison did not compare dump totals (only XLANG fuzz caught it).'),'M19':(True,'Real-data comparison cannot detect it (no non-flat instrument has expiry == last data day 2026-10-22; 72 instruments expire that day, all flat); fuzz vs reference (9 of 540 cases) does.')}
NOTES={'M03':'Data-dependent: only 1 in 997 source rows; fuzz sequences (<997 rows) cannot hit it; detected on the real ledger only (test_lineage_real, my raw comparison).','M19':'Existing suite: 1 test (synthetic exact expiry boundary). Real ledger does not exercise the boundary.','M20':'Real data contains no flagged duplicates, so only synthetic duplicate fixtures can detect it.','M22':'Python-only tie-key swap; real-data src order never uses the key, so detection needs sells_first/buys_first runs (parity vs C++, fuzz).','M11':'SURVIVOR of all 127 existing tests: the shift is uniform so ordering, day assignment (max IST time 15:39+5:30 < 24:00) and all aggregates are unchanged; only a comparison of timestamp_s against raw column 161 (my compare_ref_vs_engine) detects it.',
'M17':'Existing-test failures are a consequence of an IndexError crash (deque index out of range) after the wrong lot is popped, i.e. a crash, not a designed invariant detector; counted as crash-not-kill for the existing suite. My reference comparison reports ENGINE_EXCEPTION as well, so also crash-only for own check on the Python engine; fuzz kill compares C++ output to reference only for C-mutants, Python mutants are compared in-process (py_vs_ref) and the crash is flagged.',
'M18':'Killed by the designed role-arithmetic InvariantViolation guard (an internal invariant [INV], same code path family as the mutation but a purpose-built check); not an independent detector.',
'M16':'Convention leak is caught by the LineageSet separation guard (a cross-convention comparison of outputs) and by reference comparison.'}
for m in mutants.M:
    j=R.get(m['id'])
    if not j: out.append(dict(id=m['id'],change=m['name'],expected_detector=m['expected'],existing_tests_caught='NOT RUN',own_check_caught='NOT RUN',detector_independent='n/a',notes='run did not finish')); continue
    e=j['existing_tests']; c=cat(e['failed']); own=j['own']
    caught=bool(e['failed']) or e['returncode']!=0
    ownd=[]; BEN={'AVG_exact_total_is_integer'}
    ff=[k for k in own.get('false_flags',[]) if k not in BEN]
    exc=own.get('engine_exception'); mm=own.get('mismatch_summary') or {}
    fz=own.get('fuzz') or {}
    impl=bool(mm or ff or fz.get('py_vs_ref_mismatch') or fz.get('cpp_vs_ref_mismatch') or own.get('cpp_raw_vs_ref_false_keys'))
    xl=bool(fz.get('xlang_byte_mismatch') or own.get('cpp_vs_py_byte_diff_files'))
    if exc: ownd.append('engine exception: '+exc[:90])
    if mm: ownd.append('raw-reference mismatches '+json.dumps(mm)[:150])
    if ff: ownd.append('false flags '+','.join(ff[:6]))
    if fz.get('py_vs_ref_mismatch') or fz.get('cpp_vs_ref_mismatch'): ownd.append(f"fuzz vs reference mismatches py={fz.get('py_vs_ref_mismatch')} cpp={fz.get('cpp_vs_ref_mismatch')} of {fz.get('cases')}")
    if xl: ownd.append('cross-language byte mismatch (XLANG only)')
    if own.get('fuzz_error'): ownd.append('fuzz harness crashed (KeyError: engine emitted a role for a fill the reference excluded)')
    if m['id'] in OVR: impl=OVR[m['id']][0]; ownd.append(OVR[m['id']][1])
    indep = bool(c['independent_reference_tests']) or (not caught and bool(own['killed']))
    out.append(dict(id=m['id'],change=f"{m['name']} [{m['file']}]",expected_detector=m['expected'],
        existing_tests_caught=dict(caught=caught,summary=e['summary'],n_failed=len(e['failed']),detecting_test_files=c['files'],failing_tests_sample=e['failed'][:6]),
        own_check_caught=dict(caught=bool(impl or exc or xl or own.get('fuzz_error')),caught_by_independent_reference_comparison=bool(impl),caught_only_by_crash_or_internal_guard=bool((exc or own.get('fuzz_error')) and not impl),caught_only_by_xlang=bool(xl and not impl and not exc),detail=ownd),
        detector_independent=dict(existing_suite_has_independent_reference_detector=bool(c['independent_reference_tests']),independent_reference_test_files=c['independent_reference_tests'],xlang_only_files=c['xlang_tests'],internal_files=c['internal_or_handcomputed_tests'],own_check_class='[RAW]/[IMPL] reference comparison' if impl else ('[XLANG] only' if xl else '[INV]/crash')),
        notes=NOTES.get(m['id'],'')))
json.dump(out,open('mutations.json','w'),indent=1)
for o in out:
    if isinstance(o['existing_tests_caught'],dict): print(o['id'],o['existing_tests_caught']['caught'],o['own_check_caught']['caught'],o['detector_independent']['independent_reference_test_files'],o['detector_independent']['xlang_only_files'])
