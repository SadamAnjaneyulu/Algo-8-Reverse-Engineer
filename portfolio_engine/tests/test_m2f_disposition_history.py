"""Historical preservation of the M2-F audit record: the original dispositions of the six defects whose status changed later are kept VERBATIM next to every amendment, and the M2-F
final report and limitations document were extended by addenda only (no line of the 562d7eb6 text deleted)."""
import json, os, re, subprocess
import pytest
from conftest import PE, REPO

HIST = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'disposition_history.json')))['defects']
SIX = ['D-A01', 'D-A08', 'B-01', 'C-01', 'C-02', 'E-D03']
REG = open(os.path.join(PE, 'reports', 'M2F_DEFECT_REGISTER.md')).read()


def git(*a):
    p = subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True)
    if p.returncode: pytest.skip('git history for 562d7eb6 not available')
    return p.stdout


def test_six_defects_are_all_present_with_original_amendments_and_current_state():
    assert sorted(HIST) == sorted(SIX)
    for i in SIX:
        h = HIST[i]; assert h['original']['commit'] == '562d7eb6' and h['original']['text'] and h['amendments'] and h['current_state']
        sec = re.search(r'^### ' + re.escape(i) + r' .*?(?=^### |^## |\Z)', REG, re.S | re.M).group(0)
        assert f"* **Original disposition (M2-F audit, commit 562d7eb6, verbatim):** " in sec and 'Current state:' in sec and sec.count('**Amendment ') == len(h['amendments'])
        assert h['original']['text'].replace('|', '\\|') in sec or h['original']['text'] in sec                      # verbatim (the register escapes table pipes)
        assert all(a['date'] and a['commit'] and a['evidence'] and a['kind'] for a in h['amendments'])


def test_original_text_equals_the_562d7eb6_register_line_verbatim():
    old = git('show', '562d7eb6:portfolio_engine/reports/M2F_DEFECT_REGISTER.md')
    for i in SIX:
        sec = re.search(r'^### ' + re.escape(i) + r' .*?(?=^### |^## |\Z)', old, re.S | re.M).group(0)
        line = [l for l in sec.split('\n') if l.startswith('* **Disposition:** ')][0][len('* **Disposition:** '):]
        assert HIST[i]['original']['text'] == line, i


@pytest.mark.parametrize('rel', ['portfolio_engine/reports/M2F_FINAL_AUDIT_REPORT.md', 'portfolio_engine/reports/M2F_METHODOLOGY_LIMITATIONS.md', 'portfolio_engine/reports/M2F_CLAIM_EVIDENCE_REGISTER.md', 'portfolio_engine/reports/M2F_TEST_COVERAGE.md'])
def test_m2f_documents_have_no_deleted_or_changed_original_lines(rel):
    num = git('diff', '--numstat', '562d7eb6', '--', rel).split()
    assert not num or int(num[1]) == 0, f'{rel}: {num[1]} line(s) of the 562d7eb6 text deleted or changed'
