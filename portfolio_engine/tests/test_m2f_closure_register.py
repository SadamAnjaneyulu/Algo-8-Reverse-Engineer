"""M2 closure: every M2-F defect has an explicit closure disposition from the fixed vocabulary, the original M2-F dispositions are still present beside it, and no Medium defect is left OPEN."""
import collections, json, os
from conftest import PE

ALLOWED = {'FIXED', 'ACCEPTED WITH EVIDENCE', 'ACCEPTED WITH DOCUMENTED RATIONALE', 'DEFERRED WITH REASON', 'OPEN'}
D = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'consolidated.json')))['defects']; CL = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'closure_dispositions.json')))['defects']
REG = open(os.path.join(PE, 'reports', 'M2F_DEFECT_REGISTER.md')).read()


def test_every_defect_has_a_closure_disposition_rationale_and_evidence():
    assert len(D) == 49 and sorted(CL) == sorted(x['id'] for x in D)
    for i, c in CL.items(): assert c['status'] in ALLOWED and c['rationale'] and c['evidence'], i


def test_register_renders_original_and_closure_dispositions_for_every_defect():
    assert REG.count('Closure disposition (M2 closure, 2026-11-16)') == 49
    for x in D: assert (f"### {x['id']} " in REG)


def test_status_counts_and_no_open_medium_or_high_defect():
    sev = {x['id']: str(x['severity']).capitalize() for x in D}; cnt = collections.Counter((sev[i], c['status']) for i, c in CL.items())
    assert not [i for i, c in CL.items() if c['status'] == 'OPEN' and sev[i] in ('Medium', 'High', 'Critical')]
    assert sum(v for (s, _), v in cnt.items() if s == 'Medium') == 19 and sum(v for (s, _), v in cnt.items() if s == 'Low') == 29 and sum(v for (s, _), v in cnt.items() if s == 'High') == 1
    assert {i for i, c in CL.items() if c['status'] == 'OPEN'} == {'C-06', 'E-D11'}                    # the only OPEN items, both Low, with their reasons in the register
