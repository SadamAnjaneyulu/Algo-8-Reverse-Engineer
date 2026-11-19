import copy, pytest
from core import rulemeta as RM


def test_register_is_valid():
    assert RM.validate(RM.load()) == []


def test_every_rule_group_is_present():
    g = {r['group'][0] for r in RM.load()['rules']}
    assert {'A', 'B', 'C', 'D', 'E'} <= g


def test_rejected_rules_cannot_run():
    doc = RM.load(); rej = [r['id'] for r in doc['rules'] if r['classification'] == 'REJECTED']; assert rej
    assert all(RM.check_run_config(doc, {i: 'ON'}) for i in rej)


def test_unknown_trigger_modules_may_not_run_historically():
    doc = RM.load(); by = {r['id']: r for r in doc['rules']}
    for rid in ('B-07', 'C-03', 'C-06', 'C-07', 'C-09', 'D-03', 'D-06'): assert by[rid]['may_run_historically'] is False
    assert RM.check_run_config(doc, {'B-07': 'ON'}) and not RM.check_run_config(doc, {'B-07': 'OFF'})


def test_validator_catches_a_tampered_register():
    doc = copy.deepcopy(RM.load()); doc['rules'][0]['classification'] = 'PROFITABLE'; assert RM.validate(doc)
    doc = copy.deepcopy(RM.load()); r = next(x for x in doc['rules'] if x['classification'] == 'REJECTED'); r['mode'] = 'BAND'; assert RM.validate(doc)
    doc = copy.deepcopy(RM.load()); doc['rules'][1]['id'] = doc['rules'][0]['id']; assert RM.validate(doc)


def test_failed_rules_from_earlier_phases_are_rejected():
    by = {r['id']: r for r in RM.load()['rules']}
    assert by['C-11']['classification'] == 'REJECTED' and by['C-12']['classification'] == 'REJECTED' and by['C-09']['classification'] == 'REJECTED'
