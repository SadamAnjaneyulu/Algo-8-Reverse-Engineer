import numpy as np, pandas as pd, pytest
from conftest import mk, mk_ledger, T0, real, tc
import matching as mt, reconstruct_positions as rp, classify_exits as ce


def test_one_open_then_several_partial_closes_each_classified_separately():
    f = mk([(T0, 'S', 195, 50), (T0 + 60, 'B', 65, 30), (T0 + 120, 'B', 65, 50), (T0 + 180, 'B', 65, 70)])
    for m in ['FIFO', 'LIFO', 'AVG']:
        o = mt.run_matching(f, m); c = o['closures']
        assert c.qty.tolist() == [65, 65, 65] and mt.classify(c.pnl_pts.values, tc.TOL).tolist() == ['PROFIT', 'BREAKEVEN', 'LOSS'] and len(o['remaining']) == 0
        assert o['roles'].inventory_after.tolist() == [-195, -130, -65, 0]


def test_exit_events_mark_partial_versus_full_and_remaining_quantity():
    L = mk_ledger([(T0, 'S', 195, 50), (T0 + 60, 'B', 65, 30), (T0 + 120, 'B', 130, 40)]); L['expiry'] = pd.Timestamp('2026-12-31')
    B = rp.build(L); P = B['pieces']; C = ce.label_pieces(P[P.row_type == 'CLOSED'])
    E = ce.build_exit_events(C, L, B['roles'], B['episodes']); f = E[E.method == 'FIFO'].set_index('close_row')
    assert f.loc[1, 'exit_type'] == 'PARTIAL' and f.loc[1, 'remaining_after_units'] == 130 and f.loc[2, 'exit_type'] == 'FULL' and f.loc[2, 'remaining_after_units'] == 0
    assert f.loc[1, 'label'] == 'PROFIT' and f.loc[2, 'label'] == 'PROFIT' and (f.position_opened_units_total == 195).all() and f.net_pnl_rupees.isna().all()


def test_partial_fills_of_one_order_are_not_merged():
    f = mk([(T0, 'S', 65, 50), (T0, 'S', 65, 50.05), (T0 + 60, 'B', 130, 40)])
    o = mt.run_matching(f, 'FIFO'); assert len(o['closures']) == 2 and o['closures'].open_row.tolist() == [0, 1]


@real
def test_real_data_partial_exits_exist_and_remaining_is_consistent():
    import os
    E = pd.read_parquet(os.path.join(tc.DATA, 'exit_events.parquet')); f = E[E.method == 'FIFO']
    assert (f.exit_type == 'PARTIAL').sum() > 0 and (f.exit_type == 'FULL').sum() > 0
    assert (f[f.exit_type == 'PARTIAL'].remaining_after_units > 0).all() and (f[f.exit_type == 'FULL'].remaining_after_units == 0).all()
    assert (f.qty_closed <= f.position_opened_units_total).all()
