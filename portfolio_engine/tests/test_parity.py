"""Cross-language parity: C++ unit tests, fixtures through both implementations, full real ledger through both implementations."""
import json, os, subprocess, pytest
from conftest import PE, REPO
import parity
from pe.generators import historical as H


@pytest.fixture(scope='module', autouse=True)
def built(): parity.build()


def test_cpp_core_unit_tests_pass():
    r = subprocess.run([os.path.join(parity.BUILD, 'pe_core_tests')], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr; assert 'core checks passed' in r.stdout


def test_fixture_parity_all_conventions_and_tie_orders(tmp_path):
    import glob
    n = 0
    for ev in sorted(glob.glob(os.path.join(PE, 'fixtures', 'synthetic', '*_events.tsv'))) + sorted(glob.glob(os.path.join(PE, 'fixtures', 'historical_sample', '*_events.tsv'))):
        mode = 'SYNTHETIC_TEST' if '/synthetic/' in ev else 'HISTORICAL_OBSERVED_REPLAY'
        for m in parity.METHODS:
            for t in parity.TIE_ORDERS:
                r = parity.parity_case(ev, ev.replace('_events.tsv', '_instruments.tsv'), mode, m, t, 0, str(tmp_path)); assert r['ok'], (ev, m, t, r); n += 1
    assert n == 117


def test_real_full_ledger_parity_all_conventions_and_tie_orders(tmp_path):
    ev, ip, _ = H.write(REPO, str(tmp_path), None, 'full'); n = 0
    for m in parity.METHODS:
        for t in parity.TIE_ORDERS:
            r = parity.parity_case(ev, ip, 'HISTORICAL_OBSERVED_REPLAY', m, t, 5000, str(tmp_path)); assert r['ok'] and r['roles_identical'] and r['events'] == 41421, (m, t, r); n += 1
    assert n == 9


def test_invalid_fixtures_rejected_by_both(tmp_path):
    import glob
    ip = os.path.join(PE, 'fixtures', 'invalid', 'base_instruments.tsv')
    for ev in glob.glob(os.path.join(PE, 'fixtures', 'invalid', '*_events.tsv')):
        rc, _ = parity.run_cpp(ev, ip, 'SYNTHETIC_TEST', 'FIFO', 'src', 0, str(tmp_path / 'x'), str(tmp_path / 'y')); assert rc == 2, ev


def test_cpp_rejects_mode_contamination(tmp_path):
    ev = os.path.join(PE, 'fixtures', 'synthetic', 'open_close_full_events.tsv'); ip = ev.replace('_events', '_instruments')
    rc, err = parity.run_cpp(ev, ip, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'src', 0, str(tmp_path / 'x'), str(tmp_path / 'y')); assert rc == 2 and 'mode' in err.lower()
