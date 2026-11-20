"""Body/Hedge investigation tests: pure-function behaviour on synthetic data + invariants of the computed outputs. Outputs are produced by src/bh_*.py (run order in README of this folder's report)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import bh_common as C
OUT = C.OUT


def _orders(rows):
    cols = ['tag', 'und', 'expiry', 'dayno', 'module', 'cp', 'strike', 'side', 'lots', 'tt_first', 'tt_dec', 'row', 'complete']
    return pd.DataFrame(rows, columns=cols)


def test_book_short_long_state():
    O = _orders([('1', 'NIFTY', 'E', 0, 'num', 'CE', 100, 'Sell', 3, 10.0, np.nan, 1, True),
                 ('2', 'NIFTY', 'E', 0, 'h_', 'CE', 200, 'Buy', 2, 11.0, 14.5, 2, True),
                 ('3', 'NIFTY', 'E', 0, 'num', 'CE', 100, 'Buy', 1, 20.0, np.nan, 3, True)])
    bk = C.Book(O)
    assert bk.state('NIFTY', 'E', 'CE', 5.0)[:2] == (0, 0)
    assert bk.state('NIFTY', 'E', 'CE', 12.0)[:2] == (3, 0)        # body sold 3 lots at t=10; hedge decision at 14.5 not yet
    assert bk.state('NIFTY', 'E', 'CE', 15.0)[:2] == (3, 2)        # hedge long 2 after its stamp
    assert bk.state('NIFTY', 'E', 'CE', 25.0)[:2] == (2, 2)        # one lot covered
    assert bk.state('NIFTY', 'E', 'CE', 14.5, inclusive=False)[:2] == (3, 0) and bk.state('NIFTY', 'E', 'CE', 14.5, inclusive=True)[:2] == (3, 2)


def test_match_window_and_greedy():
    import bh_h1 as H
    B = _orders([('b1', 'NIFTY', 'E', 0, 'num', 'CE', 100, 'Sell', 1, 10.0, np.nan, 1, True), ('b2', 'NIFTY', 'E', 0, 'num', 'CE', 100, 'Sell', 1, 11.0, np.nan, 2, True)])
    W = _orders([('w1', 'NIFTY', 'E', 0, 'h_', 'CE', 300, 'Buy', 1, 10.0, 13.5, 3, True), ('w2', 'NIFTY', 'E', 0, 'h_', 'CE', 300, 'Buy', 1, 10.0, 40.0, 4, True), ('w3', 'NIFTY', 'E', 0, 'h_', 'PE', 300, 'Buy', 1, 10.0, 14.0, 5, True)])
    BL, WL = H.match(B, W, 1.5, 20)
    assert list(BL.matched) == [True, False]                      # w1 matches b1 (lag 3.5); b2's earliest unmatched in window is none (w2 at lag 29 > 20)
    assert BL.lag.iloc[0] == 3.5 and BL.wing_tag.iloc[0] == 'w1'
    assert WL.set_index('tag').loc['w1', 'matched'] and not WL.set_index('tag').loc['w2', 'matched']
    assert 'w3' not in set(WL.tag)                                # other right never matched


def test_order_table_invariants_on_ledger():
    X = C.fills_x(); O = C.order_table(X)
    assert len(O) == X.tag.nunique() and O.lots.sum() == X.n_lots.sum()
    assert (O.fill_secs > 1).sum() <= 1                           # every order's fills are in one second except one 18-lot body order (57 s span)
    assert set(O.module) <= {'num', 'h_', 's_', 'v_', 'm_'}
    assert set(O[O.module == 'h_'].validity) == {'IOC'} and set(O[O.module == 'num'].validity) == {'DAY'}


def test_limits_are_marketable():
    O = C.order_table(); g = O[(O.module.isin(['num', 'h_'])) & (O.px_first >= 10)]
    sell_ok = (g[g.side == 'Sell'].lim_px < g[g.side == 'Sell'].px_first).mean(); buy_ok = (g[g.side == 'Buy'].lim_px > g[g.side == 'Buy'].px_first).mean()
    assert sell_ok > 0.99 and buy_ok > 0.99


def test_level_control_outputs():
    G = pd.read_csv(f'{OUT}/bh_h3c_wing_orders.csv'); c = G[G.complete]
    assert ((c.sw == c.gap_before).mean() > 0.85) and ((np.sign(c.sw) == np.sign(c.gap_before)).mean() > 0.95)
    W = pd.read_csv(f'{OUT}/bh_h8_waves.csv'); W = W[W.complete]; assert (W.sum_signed == W.gap_at_start).mean() > 0.9
    B = pd.read_csv(f'{OUT}/bh_h9_baselines.csv', index_col=0)['value']; assert B['wave_exact_real'] - B['wave_exact_null_p975'] > 0.3 and B['quiet_balance_real'] - B['quiet_cross_right_null'] > 0.8
    Q = pd.read_csv(f'{OUT}/bh_h3b_quiet.csv'); assert (Q.gap_all == 0).mean() > 0.9


def test_h6_partition_complete():
    A = pd.read_csv(f'{OUT}/bh_h6_bursts.csv'); D = pd.read_csv(f'{OUT}/dd_hedge_bursts.csv')
    assert len(A) == int((~D.responded).sum()) == 928 and A.cls.notna().all()
    assert set(A.cls) <= {'balanced', 'late_response', 'carry_in_unknown', 'flatten', 'near_stop', 'd0_open_window', 'other_imbalanced'}


def test_strike_rule_outputs_consistent():
    R = pd.read_csv(f'{OUT}/bh_h2_rule_tests.csv').set_index('rule')
    assert R.exact['P25'] > 2 * R.null_exact['P25'] and R.exact['P25'] > R.exact['P20'] and R.exact['P25'] > R.exact['P30'] and R.exact['P25'] > R.exact['FIX']
    S = pd.read_csv(f'{OUT}/bh_h2_simple_final.csv'); assert S.simple.all() and (S.lots == 1).all() and (S.n_trig_orders == 1).all()


def test_wing_after_stamp_only_for_isolated():
    H = pd.read_csv(f'{OUT}/bh_h7_isolated_lag.csv'); e = H[(H.lag_lo >= -2) & (H.lag_hi <= 2.5)]; p = H[(H.lag_lo >= 2.5) & (H.lag_hi <= 10)]
    assert p.real.sum() > 20 * p.null_per_shift.sum() and e.real.sum() < 3 * max(e.null_per_shift.sum(), 1)


def test_report_has_required_sections():
    t = open(os.path.join(C.REP, 'BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md')).read()
    for h in ['## 1. Executive summary', '## 4. Body structure', '## 6. Hedge trigger', '## 7. Hedge quantity', '## 8. Hedge strike', '## 9. Hedge lifecycle', '## 11. Representative case studies', '## 12. Missing-hedge', '## 13. Evidence', '## 14. Unresolved', '## 15. Data limitations', '## 16. Final reconstruction']: assert h in t, h
    assert 'Question | Finding | Evidence level | Remaining uncertainty'.replace(' | ', ' | ') in t.replace('|---|---|---|---|', '').replace('  ', ' ') or '| Question | Finding | Evidence level | Remaining uncertainty |' in t
