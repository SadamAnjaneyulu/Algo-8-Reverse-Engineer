"""Automated checks for the exit-engine research code.  Run from the repo root:  python -m pytest -q analysis/exit_engine/tests
Needs the Breeze caches (analysis/_cache); tests that need a missing cache are skipped."""
import os, sys, hashlib, subprocess
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); EE = os.path.dirname(HERE); AN = os.path.dirname(EE); ROOT = os.path.dirname(AN)
sys.path.insert(0, AN); sys.path.insert(0, EE)
CACHE = os.path.join(AN, '_cache')
need = lambda *f: pytest.mark.skipif(not all(os.path.exists(os.path.join(CACHE, x)) for x in f), reason='cache missing')

def test_alpha_freeze_untouched():
    """alpha_freeze/ must be byte-identical to the commit that froze it (d695b777)"""
    for f in sorted(os.listdir(os.path.join(ROOT, 'alpha_freeze'))):
        blob = subprocess.run(['git', 'show', f'd695b777:alpha_freeze/{f}'], cwd=ROOT, capture_output=True).stdout
        assert blob, f
        assert hashlib.sha256(blob).hexdigest() == hashlib.sha256(open(os.path.join(ROOT, 'alpha_freeze', f), 'rb').read()).hexdigest(), f

def test_splits_chronological_and_disjoint():
    from common import split_of, DEV_END, VAL_END
    assert split_of('2026-08-20') == 'DEV' and split_of('2026-08-21') == 'VAL' and split_of('2026-09-22') == 'VAL' and split_of('2026-09-23') == 'TEST'
    assert DEV_END < VAL_END

@need('exit_orders.pkl', 'exit_mkt.pkl')
def test_split_sessions_do_not_overlap():
    from common import orders
    o = orders(); d = o.groupby('split').date.agg(['min', 'max'])
    assert d.loc['DEV', 'max'] < d.loc['VAL', 'min'] and d.loc['VAL', 'max'] < d.loc['TEST', 'min']

@need('exit_orders.pkl', 'exit_lots_cheap.pkl')
def test_book_reconciles_with_fills():
    """unit-lot book: per contract, open lots at the end == net filled lots; every unit lot is accounted for"""
    from common import orders, replay_book
    o = orders(); Lt = replay_book('cheap')
    net = o.assign(s=np.where(o.side == 'Buy', 1, -1) * o.lots).groupby(['und', 'expiry', 'cp', 'strike']).s.sum()
    op = Lt[Lt.exit_oid.isna()].groupby(['und', 'expiry', 'cp', 'strike']).sgn.sum()
    j = pd.concat([net, op], axis=1).fillna(0)
    assert (j.iloc[:, 0] == j.iloc[:, 1]).all()
    assert (Lt.exit_mi >= Lt.entry_mi).all()

def test_taxonomy_side_vs_basket_flags():
    """regression for the swapped side/basket bug: 'CE' has len 2 but is ONE side"""
    from exit_engine.taxonomy import classify
    X = pd.DataFrame(dict(und='NIFTY', expiry=pd.Timestamp('2026-07-07'), t_dec=pd.to_datetime(['2026-07-07 10:05:00', '2026-07-07 10:05:01', '2026-07-07 11:05:00', '2026-07-07 11:05:01']),
                          cp=['CE', 'CE', 'CE', 'PE'], strike=[25000, 25100, 25000, 25000], closing_short=True, tp='num', algoid='99999', dte=0, L=50.0, r_avg=1.0, r_cheap=1.0,
                          run_max_since_cheap=1.0, remaining_after=1, oid=['a', 'b', 'c', 'd']))
    sells = pd.DataFrame(dict(und=['NIFTY'], expiry=[pd.Timestamp('2026-07-07')], cp=['PE'], t=[pd.Timestamp('2026-07-07 09:00:00')]))
    Y = classify(X, sells).set_index('oid')
    assert Y.loc['a', 'flag_side_multi'] and not Y.loc['a', 'flag_basket']
    assert Y.loc['c', 'flag_basket'] and not Y.loc['c', 'flag_side_multi']
    assert Y.loc['a', 'label'] == '3 side-level reduction' and Y.loc['c', 'label'] == '4 basket-level reduction'

def test_clock_b_tick_window():
    from clock_b import tick_of
    T = lambda s: pd.Timestamp('2026-07-07 ' + s)
    assert tick_of(T('09:29:50')) == T('09:29:00') and tick_of(T('09:30:10')) == T('09:29:00') and tick_of(T('09:28:45')) == T('09:29:00')
    assert pd.isna(tick_of(T('09:30:20'))) and pd.isna(tick_of(T('09:28:40'))) and pd.isna(tick_of(T('09:14:50')))

def test_action_columns_never_features():
    from models import feats_of, ACTION_COLS
    df = pd.DataFrame({c: [1.0] for c in list(ACTION_COLS) + ['r_cheap', 'mtm', 'y_lotstop']})
    f = feats_of(df)
    assert f == ['r_cheap', 'mtm']

@need('exit_orders.pkl', 'exit_mkt.pkl', 'exit_lots_cheap.pkl', 'exit_cm.pkl', 'exit_bm.pkl')
@pytest.mark.parametrize('cyc', [0, 20])
def test_teacher_forced_replay_reproduces_panel_and_pnl(cyc):
    """the replay's own sequential feature computation, fed the actual orders, must reproduce the vectorised panel (causal by construction:
    the replay computes minute-m features BEFORE applying any minute-m order) and the cash-flow P&L"""
    from common import orders, markets
    import bookstate, replay
    o = orders(); mk = markets(); CM, BM = bookstate.load()
    key = sorted(mk)[cyc]; m = mk[key]; u, e = key
    A = replay.run_cycle(m, None, None, None, policy='teacher', teacher=o[(o.und == u) & (o.expiry == e)])
    F = pd.DataFrame(A['fe']); cm = CM[(CM.und == u) & (CM.expiry == e)]
    J = cm.merge(F, on=['mi', 'cp', 'strike'], suffixes=('', '_r'))
    assert len(J) >= 0.99 * len(cm)
    for c in ['n_lots', 'e_cheap', 'e_avg', 'px', 'upnl', 'upnl_side', 'delta', 'otm_pts', 'n_carried', 'n_reentry', 'age_oldest', 'age_newest']:
        a, b = J[c].astype(float).values, J[c + '_r'].astype(float).values
        ok = np.isclose(a, b, rtol=1e-6, atol=1e-6, equal_nan=True).mean()
        assert ok >= 0.995, (c, ok)
    for c in ['since_sale_k', 'since_bb_k']:
        ok = np.isclose(J[c].astype(float), J[c + '_r'].astype(float), equal_nan=True).mean(); assert ok >= 0.99, (c, ok)
    bm = BM[(BM.und == u) & (BM.expiry == e)].set_index('mi')
    fb = F.groupby('mi').first()
    for c in ['mtm', 'net_delta', 'lots_tot']:
        jj = bm[[c]].join(fb[['b_' + c]], how='inner')
        assert np.isclose(jj[c], jj['b_' + c], rtol=1e-6, atol=1e-3).mean() >= 0.995, c
    oc = o[(o.und == u) & (o.expiry == e)]; lot = 65 if u == 'NIFTY' else 20
    cash = (-np.where(oc.side == 'Buy', 1, -1) * oc.vwap * oc.lots * lot).sum()
    pos = oc.assign(s=np.where(oc.side == 'Buy', 1, -1) * oc.lots).groupby(['cp', 'strike']).s.sum()
    S = m['S'][-1]; settle = sum(v * lot * (max(S - k, 0) if cp == 'CE' else max(k - S, 0)) for (cp, k), v in pos.items())
    assert abs(A['pnl'] - (cash + settle)) < 1.0

@need('fp_exits.pkl', 'exit_mkt.pkl', 'exit_lots_cheap.pkl', 'exit_orders.pkl')
def test_first_passage_ambiguity_classes_rederived():
    """independent re-derivation of definite / ambiguous / not-crossed for a sample of exits (cheapest x 1.55, minute high)"""
    from common import markets, replay_book, orders, cycle_stop_minute
    X = pd.read_pickle(os.path.join(CACHE, 'fp_exits.pkl')); X = X[(X.ref == 'cheap') & (X.basis == 'high') & (X.k == 1.55)].sample(300, random_state=0)
    mk = markets(); Lt = replay_book('cheap'); sh = Lt[Lt.sgn < 0]; cs = cycle_stop_minute(); o = orders().set_index('oid')
    for r in X.itertuples():
        m = mk[(r.und, r.expiry)]; n = len(m['grid']); cut = cs.get((r.und, r.expiry), n); kk = m['k2i'][(r.cp, r.strike)]
        L = sh[(sh.und == r.und) & (sh.expiry == r.expiry) & (sh.cp == r.cp) & (sh.strike == r.strike)]
        cheap = np.full(n, np.nan)
        for mm in range(n):
            op = L[(L.entry_mi < mm) & (np.minimum(L.exit_mi, cut - 1) >= mm)]
            if len(op): cheap[mm] = op.entry_px.min()
        H = m['H'][kk].astype(float); cond = np.isfinite(cheap) & np.isfinite(H) & (H >= 1.55 * cheap)
        xm = r.mi; st = xm
        while st > 0 and np.isfinite(cheap[st - 1]): st -= 1
        q = o.loc[r.oid, 'L']; qc = bool(np.isfinite(q) and q >= 1.55 * cheap[xm])
        assert qc == r.quote_conf
        assert bool(cond[xm] and not cond[st:xm].any() and not qc) == r.ambiguous
        assert bool(not cond[st:xm + 1].any() and not qc) == r.never
