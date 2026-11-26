"""Contract test of the frozen order-level scoring specification: the file matches its recorded hash, the superseded version is archived with its recorded hash, and the sections the closure standard requires are present (a silent edit or deletion fails)."""
import os, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); SPEC = f'{BASE}/reports/ORDER_LEVEL_SCORING_SPEC.md'; FZ = f'{BASE}/outputs/scoring/spec_freeze.json'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
def test_spec_matches_freeze_hash_and_history_is_archived():
    f = json.load(open(FZ)); assert f['version'] == '1.1' and sha(SPEC) == f['sha256'], 'spec edited after the freeze without a new version and hash'
    h = f['history'][0]; assert h['version'] == '1.0' and sha(f'{BASE}/../../../{h["archived_as"]}') == h['sha256']
def test_spec_keeps_the_required_sections():
    s = open(SPEC).read()
    for req in ('## 4. Matching procedure (frozen)', '## 6. Portfolio state and modes', '## 7. Aggregation and required report tables', '## 9. P&L reconciliation', '## 10. Amendments', '## 11. Verification of the scorer', 'Mutually exclusive tiers', 'Cumulative agreement', 'Same-second ambiguity',
                'Decision timing is not execution timing', 'time-shift placebo', 'TF-E', 'never a primary reconstruction score', 'T is identical to F for D-1', 'Legacy bridge (gate)', 'one-to-one', 'per-cycle distribution', 'historical reproduction', 'out-of-fold', 'independent'):
        assert req in s, req
    assert 'must not** feed back' in s and 'No retrospective adjustment' in s and 'never a universal pass/fail criterion' in s
def test_freeze_record_documents_the_first_run_as_diagnostic_mode_f():
    f = json.load(open(FZ)); r = f['first_scoring_run']; assert r['mode'] == 'F' and r['diagnostic_only'] is True and r['evidence_label'] == 'historical reproduction' and r['t_equals_f_for_d1'] is True and r['spec_sha256'] == f['sha256']
