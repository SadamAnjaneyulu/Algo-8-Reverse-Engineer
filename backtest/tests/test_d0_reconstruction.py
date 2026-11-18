"""Tests for the D0 reconstruction (event table, holdout guard, freeze integrity, D0 simulator temporal correctness, regression of frozen holdout results)."""
import os, sys, copy, hashlib, json, importlib
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(HERE, 'replication', 'd0_reconstruction'); sys.path.insert(0, D); sys.path.insert(0, os.path.join(HERE, 'replication')); sys.path.insert(0, HERE)
RES = os.path.join(D, 'results')
if not os.path.exists(os.path.join(RES, 'd0_events.csv')): pytest.skip('d0 results not present', allow_module_level=True)
import d0common as C


def ev(): return pd.read_csv(os.path.join(RES, 'd0_events.csv'), parse_dates=['t'])


def test_event_table_reconciles_with_ledger():
    e = ev(); d = C.live_ledger(); assert len(e) == d.tag.nunique() == 39874 and abs(e.lots.sum() - d.lots.sum()) < 1e-6
    led = d.assign(expiry=pd.to_datetime(d.expiry).dt.strftime('%Y-%m-%d')).groupby(['und', 'expiry', 'cp', 'strike']).apply(lambda x: (x.sgn * x.lots).sum()); last = e.sort_values(['t', 'sec']).groupby(['und', 'expiry', 'cp', 'strike']).contract_net_after.last()
    assert (abs(led - last) < 1e-6).all()


def test_every_order_has_one_class_and_split_boundary():
    e = ev(); assert e.event_class.notna().all() and set(e.day) == {'D-1', 'D0'}
    assert (e[e.split == 'HOLDOUT'].expiry >= '2026-09-23').all() and (e[e.split == 'DISCOVERY'].expiry < '2026-09-23').all()
    s = pd.read_csv(os.path.join(RES, 'cycle_status.csv')); assert len(s) == 35 and s.has_d0.sum() == 33 and s.carry_in_known.sum() == 30
    sales = e[(e.module == 'num') & (e.side == 'Sell') & (e.opened_lots > 0)]; assert set(sales.event_class) <= {'REPLACEMENT_SALE', 'SCHEDULED_SALE', 'OFF_SCHEDULE_SALE', 'POSITION_REDUCTION_OF_LONG'}


def test_holdout_guard(tmp_path, monkeypatch):
    import shutil; shutil.copy(os.path.join(RES, 'd0_events.csv'), tmp_path / 'd0_events.csv'); monkeypatch.setattr(C, 'RES', str(tmp_path))
    with pytest.raises(PermissionError): C.load_events(discovery_only=False)
    assert set(C.load_events(discovery_only=True).split) == {'DISCOVERY'}


def test_frozen_files_unchanged():
    fz = json.load(open(os.path.join(RES, 'FREEZE.json'))); ad = json.load(open(os.path.join(RES, 'FREEZE_ADDENDUM_1.json'))); sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    for name, h in fz['hashes'].items():
        p = os.path.normpath(os.path.join(D, name))
        if name == 'd0_sim.py': continue                                              # superseded by addendum 1 (bug fix); the frozen v1.0 copy is checked below
        assert sha(p) == h, f'{name} changed after freeze'
    assert sha(os.path.join(RES, 'v1_0_frozen_outputs', 'd0_sim_v1_0_frozen.py')) == fz['hashes']['d0_sim.py'] == ad['d0_sim_v1_0_sha256'] and sha(os.path.join(D, 'd0_sim.py')) == ad['d0_sim_v1_1_sha256']


def _cycle(und='SENSEX', exp='2026-07-02'):
    from data import load_cycle, CACHE
    st = pd.read_csv(os.path.join(RES, 'cycle_status.csv')); s = st[(st.und == und) & (st.expiry == exp)].iloc[0]
    if not os.path.exists(os.path.join(CACHE, f'{und}_{exp}.pkl')): pytest.skip('cache absent')
    return load_cycle(und, exp, s.d1, s.d0), s


def test_sim_start_book_matches_ledger_and_no_lookahead_at_d0_open():
    import d0_sim as S
    c, s = _cycle(); e = ev(); e1 = e[(e.und == s.und) & (e.expiry == s.expiry) & (e.day == 'D-1')]; body, wing, passive, cash = S.start_book(e1)
    led = e1[e1.module == 'num'].assign(x=lambda z: np.where(z.side == 'Sell', z.lots, -z.lots)).groupby(['cp', 'strike']).x.sum().clip(lower=0)
    sim = pd.Series({k: sum(x[0] for x in L) for k, L in body.items()}); assert abs(sim.sum() - led.sum()) < 1e-6
    base = S.simulate_d0(c, s.und, e1)['orders']; c2 = copy.deepcopy(c)
    for r in ('CE', 'PE'): c2[(1, r, 'close')][:, 0] = c2[(1, r, 'close')][:, 0] * 3 + 5
    c2[(1, 'spot')][0] = c2[(1, 'spot')][0] + 1000
    pert = S.simulate_d0(c2, s.und, e1)['orders']; f = lambda o: o[o.j == 0][['cp', 'strike', 'side', 'lots', 'cls']].reset_index(drop=True)
    pd.testing.assert_frame_equal(f(base), f(pert))                                                     # decisions at the D0 open do not depend on the 09:15 bar's close/spot


def test_sim_flatten_and_stop_semantics():
    import d0_sim as S
    c, s = _cycle(); e = ev(); e1 = e[(e.und == s.und) & (e.expiry == s.expiry) & (e.day == 'D-1')]
    r = S.simulate_d0(c, s.und, e1, cycle_stop=False); o = r['orders']; assert (o[o.cls == 'FINAL_LIQUIDATION'].j == 359).all()
    r2 = S.simulate_d0(c, s.und, e1, stop_rs=-1e9); assert r2['stopped']; o2 = r2['orders']; j0 = o2[o2.cls == 'STOP_LIQUIDATION'].j.min(); assert not ((o2.cls.isin(['SCHEDULED_SALE', 'REPLACEMENT_SALE'])) & (o2.j >= j0)).any()


def test_regression_frozen_holdout_results():
    m = pd.read_csv(os.path.join(RES, 'compare_events_holdout_V1.csv')).set_index('category')
    assert abs(m.loc['scheduled sales', 'precision_L2'] - 0.647) < 0.002 and abs(m.loc['scheduled sales', 'recall_L2'] - 0.483) < 0.002 and abs(m.loc['final liquidation (>=15:10)', 'recall_L2'] - 0.604) < 0.002


def test_lineage_reconciles_with_live_pnl():
    Lg = pd.read_csv(os.path.join(RES, 'lot_lineage.csv')); LP = pd.read_csv(os.path.join(HERE, 'replication', 'results', 'live_cycle_pnl.csv')); assert abs(Lg.pnl.sum() - LP.gross.sum()) / abs(LP.gross.sum()) < 0.002
