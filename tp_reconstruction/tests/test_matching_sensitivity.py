import os
import numpy as np, pandas as pd, pytest
from conftest import mk, mk_ledger, T0, real, tc
import matching as mt, reconstruct_positions as rp, classify_exits as ce


SCEN = [(T0, 'S', 65, 40), (T0 + 1, 'S', 65, 60), (T0 + 2, 'B', 65, 50), (T0 + 3, 'B', 65, 50)]


def test_fifo_and_lifo_give_different_closure_labels_on_the_same_fills():
    f = mt.run_matching(mk(SCEN), 'FIFO')['closures']; l = mt.run_matching(mk(SCEN), 'LIFO')['closures']; a = mt.run_matching(mk(SCEN), 'AVG')['closures']
    assert f.pnl_pts.tolist() == [-10, 10] or f.pnl_pts.tolist() == [-10.0, 10.0]      # FIFO: first lot (sold 40) closed at 50 -> loss
    assert l.pnl_pts.tolist() == [10, -10] and a.pnl_pts.tolist() == [0, 0]
    assert mt.classify(a.pnl_pts.values, tc.TOL).tolist() == ['BREAKEVEN', 'BREAKEVEN']


def test_fully_closed_position_pnl_is_identical_across_methods():
    r = [mt.run_matching(mk(SCEN), m)['episodes'].realized_pnl.iloc[0] for m in ['FIFO', 'LIFO', 'AVG']]; assert r == [0, 0, 0]
    f = mk([(T0, 'S', 130, 40), (T0 + 1, 'S', 65, 70), (T0 + 2, 'B', 65, 41), (T0 + 3, 'B', 130, 55)])
    p = [mt.run_matching(f, m)['episodes'].realized_pnl.iloc[0] for m in ['FIFO', 'LIFO', 'AVG']]; assert max(p) - min(p) < 1e-9


def test_average_cost_weights_the_pool_by_quantity():
    c = mt.run_matching(mk([(T0, 'S', 65, 40), (T0 + 1, 'S', 195, 60), (T0 + 2, 'B', 260, 55)]), 'AVG')['closures'].iloc[0]
    assert abs(c.entry_px - 55) < 1e-12 and c.pnl_pts == 0


def test_equal_timestamp_ordering_ambiguity_is_detected_and_alternatives_differ():
    f = mk([(T0 + 10, 'B', 65, 45), (T0 + 10, 'S', 65, 46)])                           # flat contract, same second: buy-then-sell opens a long, sell-then-buy opens a short
    assert mt.role_ambiguity(f) == {0, 1}
    a = mt.run_matching(f, 'FIFO', 'sells_first')['roles'].set_index('src_row').close_qty.to_dict(); b = mt.run_matching(f, 'FIFO', 'buys_first')['roles'].set_index('src_row').close_qty.to_dict(); assert a == {0: 65, 1: 0} and b == {0: 0, 1: 65}


def test_unambiguous_ties_are_not_flagged():
    f = mk([(T0, 'S', 65, 50), (T0 + 10, 'B', 65, 45), (T0 + 10, 'B', 65, 44)])         # same side only
    assert mt.role_ambiguity(f) == set()


def test_duplicate_flagged_fills_are_excluded_from_matching():
    f = mk([(T0, 'S', 65, 50), (T0, 'S', 65, 50), (T0 + 5, 'B', 65, 40)]); f.loc[1, 'dq_duplicate_fill'] = True
    o = mt.run_matching(f, 'FIFO'); assert o['roles'].qty_units.sum() == 130 and o['closures'].qty.sum() == 65 and len(o['remaining']) == 0


def test_consensus_stability_classification():
    E = pd.DataFrame(dict(method=['FIFO', 'LIFO', 'AVG'] * 2, close_row=[1, 1, 1, 2, 2, 2], label=['PROFIT', 'PROFIT', 'PROFIT', 'PROFIT', 'LOSS', 'PROFIT'], pnl_pts_per_unit=[1.0] * 6, order_ambiguous=[False] * 6,
                          contract_id='c', und='NIFTY', expiry=pd.Timestamp('2026-07-07'), strike=1, cp='CE', direction=-1, qty_closed=65, t_fill=pd.Timestamp('2026-07-07'), date=pd.Timestamp('2026-07-07'), module='num', episode_id='e', exit_type='FULL',
                          session_relation='SAME_SESSION', exit_pct_of_entry=50.0, hold_minutes_mean=5.0))
    X = ce.consensus(E).set_index('close_row'); assert X.loc[1, 'stability'] == 'STABLE' and X.loc[1, 'consensus_label'] == 'PROFIT' and X.loc[2, 'stability'] == 'CONVENTION_SENSITIVE'


@real
def test_real_data_three_methods_agree_on_quantities_and_sensitivity_is_reported():
    S = pd.read_csv(os.path.join(tc.DATA, 'reconciliation_summary.csv')); assert S.method.tolist() == ['FIFO', 'LIFO', 'AVG'] and S.closed_units.nunique() == 1
    M = pd.read_csv(os.path.join(tc.ANALYSIS, 'matching_sensitivity.csv')); st = M[M.section == 'closing-fill stability'].set_index('key')
    assert {'STABLE', 'CONVENTION_SENSITIVE'} <= set(st.index) and abs(st.share_of_fills.sum() - 1) < 1e-3
    chk = M[M.section.str.startswith('fully closed positions')]; assert chk.pnl_rupees.iloc[0] < 1e-6
