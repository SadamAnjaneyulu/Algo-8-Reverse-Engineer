"""capital_stop (backtest extension): triggers on open-leg loss, phase-specific limits, one atomic group, and Python/C++ byte parity."""
import os, subprocess
import pytest
from helpers import *
from test_parity import both, compare, build   # noqa: F401  (build = module fixture that compiles the C++ runner)


def stop_body(carry=0, expiry=0, switch=0, extra=''):
    return (L('PLUGIN', 'capital_stop', '1.0.0', 1) + plugins(False, False, True) + cfg('capital_stop', 'carry_limit_paise', carry) + cfg('capital_stop', 'expiry_limit_paise', expiry) + cfg('capital_stop', 'phase_switch_ts', T0 + switch) + extra
            + ''.join(mark(o, i, px) for o, vals in ((0, (10000, 9000, 200, 250)), (300, (11000, 9000, 200, 250)), (600, (13000, 9000, 200, 250))) for i, px in zip((SCE, SPE, WCE, WPE), vals)) + ''.join(tick(o) for o in (0, 300, 600)))


def acts(f): return [(a['action_id'], a['status'], a['qty']) for a in table(f['actions.tsv'])]


def test_no_stop_when_limit_is_zero_or_not_reached():
    sim, f = run(scn(stop_body(switch=10 ** 6))); assert not acts(f) and {d['reason'] for d in table(f['decisions.tsv']) if d['plugin'] == 'capital_stop'} == {'STOP_DISABLED_FOR_PHASE'}
    sim, f = run(scn(stop_body(carry=10 ** 9, switch=10 ** 6))); assert not acts(f) and {d['reason'] for d in table(f['decisions.tsv']) if d['plugin'] == 'capital_stop'} == {'WITHIN_LIMIT'}


def test_stop_cuts_every_open_leg_as_one_group_when_the_loss_limit_is_hit():
    # short CE entry 10000 -> mark 13000: loss = (13000-10000)*195 = 585,000 paise; limit 500,000 -> triggered at +600 only
    sim, f = run(scn(stop_body(carry=500000, switch=10 ** 6))); a = table(f['actions.tsv']); assert len(a) == 4 and all(x['status'] == 'ACCEPTED' and x['reason'] == 'OK' for x in a) and {x['ts'] for x in a} == {str(T0 + 600)}
    assert {x['group_id'] for x in a} == {f'capital_stop|{T0 + 600}|B1'} and kv(f, 'actions_accepted') == '4'
    st = table(f['states.tsv']); assert st[-1]['basket_status'] == 'FULLY_CUT'
    assert [d for d in table(f['decisions.tsv']) if d['plugin'] == 'capital_stop' and d['ts'] == str(T0 + 300)][0]['reason'] == 'WITHIN_LIMIT'


def test_phase_switch_selects_the_limit():
    sim, f = run(scn(stop_body(carry=10 ** 12, expiry=500000, switch=300))); a = table(f['actions.tsv']); assert {x['ts'] for x in a} == {str(T0 + 600)}            # carry phase (ts < switch) tolerant, expiry phase strict
    sim, f = run(scn(stop_body(carry=500000, expiry=10 ** 12, switch=300))); assert not acts(f)


def test_rejects_a_scenario_with_an_unknown_config_key():
    with pytest.raises(Exception): run(scn(stop_body(extra=cfg('capital_stop', 'nonsense', 1))))


def test_python_and_cpp_write_identical_files(tmp_path, build):
    for name, body in (('trig', stop_body(carry=500000, switch=10 ** 6)), ('none', stop_body(carry=10 ** 9, switch=10 ** 6)), ('phase', stop_body(carry=10 ** 12, expiry=500000, switch=300))):
        py, cp = both(tmp_path, scn(body), name); compare(py, cp, name)
