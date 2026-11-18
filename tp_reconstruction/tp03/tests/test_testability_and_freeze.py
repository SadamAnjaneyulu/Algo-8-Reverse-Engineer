import os, sys, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
import tp03_common as c


def test_e2_action_uses_the_minority_gates_and_the_general_rule_together():
    # pre-expiry design (672 observations, minorities 36 / 49): testable although the minority is below 100
    assert c.testability('E2_action', 672, [15, 17], 85, [36, 49])['testable']
    # expiry-day design (554 observations, minorities 17 / 27): testable under the pooled >= 30 and per-underlying >= 10 gates
    assert c.testability('E2_action', 554, [12, 14], 44, [17, 27])['testable']
    # the general min_events=100 is NOT applied to the minority class; it applies to N
    r = c.testability('E2_action', 80, [15, 17], 85, [36, 49]); assert not r['testable'] and any('N=80' in x for x in r['reasons'])
    # each gate fails independently
    assert not c.testability('E2_action', 672, [15, 17], 29, [36, 49])['testable'] and not c.testability('E2_action', 672, [15, 17], 85, [36, 9])['testable'] and not c.testability('E2_action', 672, [9, 17], 85, [36, 49])['testable']


def test_non_binary_tests_have_no_minority_gate():
    assert c.testability('E3_quantity', 544, [15, 17])['testable'] and not c.testability('E3_quantity', 99, [15, 17])['testable']
    with pytest.raises(ValueError): c.testability('E2_action', 672, [15, 17])


def test_registered_gates_are_the_clarified_ones():
    g = c.CFG['entry']['testability_gates']; assert (g['min_minority_class_events_pooled'], g['min_minority_class_events_per_underlying'], g['min_cycles_per_underlying']) == (30, 10, 10) and c.CFG['inference']['min_events'] == 100
    assert 'applies_to' in g and 'minority class' in g['applies_to'] and 'EXPLORATORY' in g['evidence_ceiling']


def test_e2_evidence_ceiling():
    f = c.e2_evidence_ceiling
    assert f(True, True, True) == 'STRONGLY_SUPPORTED_POSSIBLE'
    assert f(True, True, False) == 'WEAKLY_SUPPORTED_CAP' and f(True, False, True) == 'WEAKLY_SUPPORTED_CAP' and f(False, True, True) == 'WEAKLY_SUPPORTED_CAP'
    assert f(False, False, True) == 'NO_EFFECT_OR_UNRESOLVED'


def test_configuration_is_frozen():
    assert c.CFG['frozen'] is True and c.CFG['version'] == 3
    c.assert_frozen()                                         # raises if config.yaml differs from config.sha256
