import json, os
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_e/mut/_results/'
meta = {  # id: (expected detector, own check result, independent?, note)
 'E01': ('check_view duplicate-batch-id check; id-uniqueness tests', 'id_audit.py batch-id uniqueness (not run on this mutant; same class as E02)', 'partly: invariant lives on the mutated path', 'killed in 10 s by test_COUNTEREXAMPLE_mixed_parent...'),
 'E02': ('lifecycle event-id uniqueness (none exists in LineageSet.check: only OA/CP and CA ids are checked)', 'id_audit.py: lifecycle_event_id_dupes = 2660 -> CAUGHT', 'killed only by REPRO (committed datasets differ), not by an identity invariant', 'gap: no uniqueness invariant for LE ids'),
 'E03': ('TP-01 role reconciliation / closing-batch partition tests', 'parity_fuzz vs unmodified C++: 80/105 differ, 23 reference mismatches -> CAUGHT', 'yes ([IMPL] reference and [XLANG])', 'killed in 28 s'),
 'E04': ('Python/C++ parity (fixture AVG decimals)', 'parity_fuzz: 29/89 differ -> CAUGHT', 'XLANG only; no Python-only test pins the 6-decimal format', 'killed in 623 s (under load) by test_parity only'),
 'E05': ('manifest-vs-files check on regenerated output', 'manifest_check.py after running the mutated script: all 6 m2c entries bad -> CAUGHT', 'yes (recomputes hashes from files)', 'SURVIVOR of the suite: no test executes the stage scripts'),
 'E06': ('committed-manifest reproduction test', 'not needed', 'REPRO only', 'killed by test_real_outputs_reproduce_the_committed_manifest'),
 'E07': ('provenance.git_sha vs `git rev-parse HEAD`', 'direct comparison: mutant returns 40 zeros vs real HEAD -> CAUGHT', 'yes', 'SURVIVOR: provenance.py is 55 % covered, git_sha unasserted'),
 'E08': ('invalid schema_version fixture', 'parse_probe bad_schema_version: Python ACCEPT vs C++ REJECT -> CAUGHT', 'yes', 'SURVIVOR: no invalid fixture for schema_version; real writer always emits v1'),
 'E09': ('IST day-boundary tests (Python)', 'parity_fuzz profile 3: 15/15 cross-midnight cases differ vs C++ -> CAUGHT', 'yes', 'killed (default UTC TZ) by test_COUNTEREXAMPLE_session_expiry...; also killed under TZ=America/New_York (E09_NY) by test_date_arithmetic_roundtrip. On a TZ=UTC machine market hours fall on the same UTC and IST date, so only cross-midnight fixtures detect it'),
 'E11': ('output reproduction under varying PYTHONHASHSEED', 'seeds 1,2,3 give 3 different batch-file hashes -> CAUGHT', 'yes', 'killed by REPRO test; detection depends on the random hash seed of that run (flaky detector)'),
 'E12': ('CA-id uniqueness invariant I-unique-ca-ids', 'parity_fuzz: 60/89 differ -> CAUGHT', 'invariant on the mutated path plus XLANG', 'killed in 143 s'),
 'E13': ('forensics IST string tests', 'not needed', 'yes (hand-pinned epoch 0 -> 05:30)', 'killed in 36 s'),
 'E14': ('manifest-vs-files check on regenerated output', 'manifest_check.py after running the mutated script: fills.tsv, inventory_series.tsv, session_carry.tsv bad in both cycles -> CAUGHT', 'yes', 'SURVIVOR of the suite'),
 'E15': ('committed-output reproduction; fill-id format', 'id_audit.py fill_id_is_F_plus_6digit = false -> CAUGHT', 'REPRO / INV', 'killed in 45 s'),
 'E16': ('committed datasets with IST columns', 'parity_fuzz profile 3: 15/15 differ -> CAUGHT', 'REPRO (committed files) rather than an explicit unit test of schema.IST_OFFSET_S', 'killed in 159 s'),
 'E17': ('parity on a fixture crossing 18:30 UTC', 'parity_fuzz profile 3: 15/15 differ vs unmodified Python -> CAUGHT', 'yes', 'SURVIVOR of all 274 tests + 24 C++ checks: no fixture or real-data day crosses IST midnight in UTC terms'),
 'E18': ('parity lineage fixtures (AVG decimals)', 'not needed', 'XLANG only', 'killed by test_lineage_parity_on_all_fixtures (C++ rebuilt per mutant)'),
 'E19': ('lineage parity (trailing newline)', 'parity_fuzz: 89/89 differ -> CAUGHT', 'XLANG only', 'killed by test_lineage_parity_on_all_fixtures'),
}
changes = {}
import re
src = open(os.path.join(T, 'scripts', 'mut_run.py')).read(); ns = {}
exec("MUT = " + src.split("MUT = ", 1)[1].split("\nap = argparse")[0], ns)
out = []
for fn in sorted(os.listdir(S)):
    r = json.load(open(S + fn)); i = r['id']; base = i.split('_')[0]; m = meta[base]
    out.append(dict(id=i, change=r['change'] + f" [{r['file']}]" + (' env ' + ' '.join(r['env']) if r['env'] else ''), expected_detector=m[0], existing_tests_caught=bool(r['killed']), existing_tests_first_failure=(r['failed'][0] if r['failed'] else None), suite_runtime_s=r['seconds'],
                    own_check_caught=('CAUGHT' in m[1]) if 'not needed' not in m[1] else 'n/a (suite caught it)', own_check=m[1], detector_independent=m[2], notes=m[3]))
json.dump(out, open(os.path.join(T, 'mutations.json'), 'w'), indent=1); print(len(out), 'mutations;', sum(1 for o in out if not o['existing_tests_caught']), 'survivors:', [o['id'] for o in out if not o['existing_tests_caught']])
