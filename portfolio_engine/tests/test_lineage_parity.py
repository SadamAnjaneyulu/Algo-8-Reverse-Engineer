"""Python vs C++ parity for the lineage files on every fixture and on the full real ledger."""
import pytest as _pt
import glob, os, pytest
from conftest import PE
import parity, parity_lineage as pl


@pytest.fixture(scope='module', autouse=True)
def built(): parity.build()


def test_lineage_parity_on_all_fixtures(tmp_path):
    n = 0
    for d, mode in (('synthetic_m2', 'SYNTHETIC_TEST'), ('synthetic', 'SYNTHETIC_TEST'), ('historical_sample', 'HISTORICAL_OBSERVED_REPLAY')):
        for ev in sorted(glob.glob(os.path.join(PE, 'fixtures', d, '*_events.tsv'))):
            for m in parity.METHODS:
                for t in parity.TIE_ORDERS: r = pl.case(ev, ev.replace('_events.tsv', '_instruments.tsv'), mode, m, t, str(tmp_path)); assert r['ok'] and r['bit_identical'], (ev, m, t, r); n += 1
    assert n == 24 * 9


def test_lineage_parity_on_the_full_real_ledger(tmp_path):
    from pe.generators import historical as H
    from conftest import REPO
    ev, ip, _ = H.write(REPO, str(tmp_path), None, 'full')
    for m in parity.METHODS:
        for t in parity.TIE_ORDERS: r = pl.case(ev, ip, 'HISTORICAL_OBSERVED_REPLAY', m, t, str(tmp_path)); assert r['ok'] and r['events'] == 41421, (m, t, r)

pytestmark = _pt.mark.slow
