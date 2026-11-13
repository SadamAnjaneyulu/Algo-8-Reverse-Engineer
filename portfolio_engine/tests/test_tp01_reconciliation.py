"""REAL data: the engine (re-implemented rules, not imported TP-01 code) must reproduce TP-01's published totals, all 2,667 episodes per method, every per-fill role, and the 6 tie-ambiguous fills."""
import pytest as _pt
import os, pytest
import pandas as pd
from conftest import REPO, PE
from pe import replay as rp, tsvio
from pe.schema import *
from pe.generators import historical as H
TP = os.path.join(REPO, 'tp_reconstruction', 'data'); M = 'HISTORICAL_OBSERVED_REPLAY'


@pytest.fixture(scope='module')
def data():
    ins, fills, src = H.generate(REPO); return ins, fills, src


@pytest.fixture(scope='module')
def runs(data):
    ins, fills, _ = data; return {m: rp.replay(fills, ins, M, m, 'src', snapshot_interval=0, strict=False) for m in METHODS}


def test_source_hash_matches_tp01_manifest(data): assert data[2]['raw_trades_sha256'] == '86e65ab6ece492a74402cb3f0ed0fc3c0d638a46a8b62b33ff2bf0094c06f528' and len(data[1]) == 41421


@pytest.mark.parametrize('method', METHODS)
def test_totals_match_tp01_reconciliation_summary(runs, method):
    S = pd.read_csv(os.path.join(TP, 'reconciliation_summary.csv')).set_index('method').loc[method]; r = runs[method]; t = lambda n: float(next(l.split('\t')[2] for l in r.dump.splitlines() if l.startswith(f'TOTAL\t{n}\t')))
    assert t('opened_units') == S.opened_units == 1414545 and t('closed_units') == S.closed_units == 1377065 and t('remaining_units') == S.remaining_units == 37480
    assert t('reversal_fills') == S.reversal_fills == 23 and t('reversal_units_reopened') == S.reversal_units_reopened
    assert t('realized_pnl_paise') / 100 == pytest.approx(S.realized_gross_pnl_rupees, abs=0.01) and t('cash_flow_paise') / 100 == pytest.approx(S.cash_flow_total, abs=0.01)
    assert t('remaining_book_value_paise') / 100 == pytest.approx(S.remaining_book_value, abs=0.01)
    assert t('remaining_expired_unclosed_units') == S.remaining_expired_unclosed_units == 37480 and t('remaining_open_at_end_units') == 0
    assert r.warnings['TIE_GROUP_MIXED_SIDE'] >= 1


@pytest.mark.parametrize('method', METHODS)
def test_every_episode_matches_tp01(runs, method):
    E = pd.read_parquet(os.path.join(TP, 'position_episodes.parquet')); E = E[E.method == method].set_index('episode_id'); r = runs[method]; got = {}
    for l in r.dump.splitlines():
        if l.startswith('EPISODE\t'): p = l.split('\t'); got[p[1]] = p
    assert set(got) == set(E.index) and len(got) == 2667
    for eid, p in got.items():
        e = E.loc[eid]; assert int(p[2]) == e.direction and int(p[3]) == e.opened_units and int(p[4]) == e.closed_units and int(p[5]) == e.remaining_units and p[7] == e.ended_by and int(p[8]) == e.n_open_fills and int(p[9]) == e.n_close_fills
        assert float(p[6]) / 100 == pytest.approx(e.realized_pnl, abs=0.011), eid


@pytest.mark.parametrize('method', METHODS)
def test_every_fill_role_matches_tp01(runs, method):
    R = pd.read_parquet(os.path.join(TP, 'fill_roles.parquet')); R = R[R.method == method].copy(); R['fill_id'] = R.src_row.map(lambda v: f'F{v:06d}'); R = R.set_index('fill_id')
    for x in runs[method].roles:
        t = R.loc[x.fill_id]; assert (x.close_qty, x.open_qty, x.inventory_after) == (t.close_qty, t.open_qty, t.inventory_after), x.fill_id


def test_role_ambiguity_set_equals_tp01_six_fills(data):
    ins, fills, _ = data; cq = {}
    for tie in TIE_ORDERS: cq[tie] = {x.fill_id: x.close_qty for x in rp.replay(fills, ins, M, 'FIFO', tie).roles}
    amb = {k for k in cq['src'] if len({cq[t][k] for t in TIE_ORDERS}) > 1}; ref = {f'F{int(v):06d}' for v in pd.read_csv(os.path.join(TP, 'role_ambiguity_fills.csv')).src_row}
    assert amb == ref and len(amb) == 6


def test_expired_units_are_reported_not_settled(runs):
    r = runs['FIFO']; assert r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 81 and all(s['unrealized'] == 'NA' for s in r.snapshots)       # 81 episodes/instruments with remaining units; no settlement P&L invented


def test_all_invariants_on_real_data(data):
    ins, fills, _ = data
    for m in METHODS: assert len(rp.replay(fills, ins, M, m, 'src').checks) >= 10

pytestmark = _pt.mark.slow
