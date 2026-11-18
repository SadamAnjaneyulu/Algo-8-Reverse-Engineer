"""Adversarial fixtures for the lot lifecycle engine (Phase 8 hardening). Every test checks conservation: every ledger unit is accounted for and P&L identities hold."""
import numpy as np, pandas as pd, pytest
from fixtures import fills
from lots import build_cycle, CONVENTIONS, LOT


def build(spec, conv='FIFO', carry=True, settle=None, **kw):
    f = fills(spec, **kw); return build_cycle(f, 'NIFTY', '2030-01-09', carry, conv, settle), f


def pnl_identity(L, f, settle):
    """sum lot pnl (+ unrecorded close cash) == ledger cash + settlement cash"""
    u = 65; cash = float((-f.sgn * f.qty_fill * f.px).sum()); res = L[L.close_reason == 'SETTLEMENT']
    sc = float((np.where(res.side == 'SHORT', -1, 1) * res.close_price * u).sum()); unrec = float((-L[L.entry_unrecorded].close_price * u).sum())
    return cash + sc - (float(L.realized_pnl.sum()) + unrec)


def test_multiple_entries_same_contract_and_partial_buybacks():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 3, 100.0), ('D-1', 200, 'num', 'Sell', 'CE', 24000, 2, 120.0), ('D0', 300, 'num', 'Buy', 'CE', 24000, 1, 90.0), ('D0', 400, 'num', 'Buy', 'CE', 24000, 2, 50.0)]
    L, f = build(spec, settle=24100.0); assert len(L) == 5 and (L.side == 'SHORT').all() and (L.open == False).all() and (L.close_reason == 'BODY_BUYBACK').sum() == 3 and (L.close_reason == 'SETTLEMENT').sum() == 2
    assert abs(pnl_identity(L, f, 24100.0)) < 1e-6 and L.entry_order_lots.dropna().isin([3, 2]).all()


@pytest.mark.parametrize('conv', CONVENTIONS)
def test_conventions_agree_on_cycle_total_but_not_on_lots(conv):
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0), ('D-1', 200, 'num', 'Sell', 'CE', 24000, 1, 150.0), ('D0', 300, 'num', 'Buy', 'CE', 24000, 1, 120.0)]
    L, f = build(spec, conv, settle=24000.0); assert abs(pnl_identity(L, f, 24000.0)) < 1e-6
    closed = L[L.close_reason == 'BODY_BUYBACK'].iloc[0]; assert closed.entry_price == {'FIFO': 100.0, 'LIFO': 150.0, 'LOW_ENTRY_FIRST': 100.0, 'HIGH_ENTRY_FIRST': 150.0}[conv]


def test_same_second_executions_keep_file_order():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0), ('D0', 500, 'num', 'Buy', 'CE', 24000, 1, 90.0), ('D0', 500, 'num', 'Sell', 'CE', 24000, 1, 95.0)]       # buy then sell in the same second
    L, f = build(spec, settle=24000.0); assert len(L) == 2 and (L.close_reason == 'BODY_BUYBACK').sum() == 1 and (L.close_reason == 'SETTLEMENT').sum() == 1 and abs(pnl_identity(L, f, 24000.0)) < 1e-6


def test_reentry_after_full_closure_is_a_new_lot():
    spec = [('D-1', 100, 'num', 'Sell', 'PE', 23000, 2, 50.0), ('D0', 200, 'num', 'Buy', 'PE', 23000, 2, 40.0), ('D0', 210, 'num', 'Sell', 'PE', 23000, 2, 45.0)]
    L, f = build(spec, settle=23500.0); assert len(L) == 4 and L.lot_id.is_unique and (L.close_reason == 'SETTLEMENT').sum() == 2


def test_hedge_lots_and_stop_module_routing():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0), ('D-1', 101, 'h_', 'Buy', 'CE', 24500, 1, 3.0), ('D-1', 900, 'v_', 'Buy', 'PE', 22000, 2, 4.0),
            ('D0', 300, 's_', 'Buy', 'CE', 24000, 1, 160.0), ('D0', 301, 's_', 'Sell', 'CE', 24500, 1, 1.0), ('D0', 302, 'v_', 'Sell', 'PE', 22000, 1, 6.0)]
    L, f = build(spec, settle=24000.0); assert (L[L.role == 'lump'].close_reason.isin(['LUMP_ORDER', 'SETTLEMENT'])).all()
    assert L[(L.role == 'body')].close_reason.iloc[0] == 'STOP_MODULE' and L[(L.role == 'wing')].close_reason.iloc[0] == 'STOP_MODULE' and abs(pnl_identity(L, f, 24000.0)) < 1e-6
    assert (L.close_reason == 'SETTLEMENT').sum() == 1                                           # one lump lot remains (2 bought, 1 sold) -> not silently closed by the stop


def test_missing_carry_in_creates_unrecorded_shorts_not_phantom_longs():
    spec = [('D0', 300, 'num', 'Buy', 'CE', 24000, 2, 60.0)]
    L, f = build(spec, carry=False, settle=24000.0); assert (L.entry_unrecorded).all() and len(L) == 2 and (L.side == 'SHORT').all() and L.realized_pnl.isna().all()
    L2, _ = build(spec, carry=True, settle=24000.0); assert (L2.side == 'LONG').all() and (L2['flags'] == 'ANOMALOUS_OPEN_LONG_BY_BODY_BUY').all()      # with a known carry-in the same fill is flagged, never matched to nothing


def test_expiry_settlement_in_and_out_of_the_money():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0), ('D-1', 101, 'num', 'Sell', 'PE', 24000, 1, 100.0)]
    L, f = build(spec, settle=24300.0); ce = L[L.cp == 'CE'].iloc[0]; pe = L[L.cp == 'PE'].iloc[0]; assert ce.close_price == 300.0 and pe.close_price == 0.0 and abs(pnl_identity(L, f, 24300.0)) < 1e-6


def test_duplicate_trade_ids_do_not_merge_lots():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0), ('D-1', 101, 'num', 'Sell', 'CE', 24050, 1, 80.0)]
    f = fills(spec); f['tradeid'] = 'SAME'; L = build_cycle(f, 'NIFTY', '2030-01-09', True, 'FIFO', 24000.0); assert len(L) == 2 and L.lot_id.is_unique


def test_every_ledger_unit_is_accounted_for():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 4, 100.0), ('D-1', 110, 'h_', 'Buy', 'CE', 24500, 4, 3.0), ('D0', 300, 'num', 'Buy', 'CE', 24000, 3, 80.0), ('D0', 310, 'h_', 'Sell', 'CE', 24500, 3, 1.0)]
    L, f = build(spec, settle=24000.0); sells = int(f[f.side == 'Sell'].n_lots.sum()); buys = int(f[f.side == 'Buy'].n_lots.sum())
    short_open = int(((L.side == 'SHORT') & ~L.entry_unrecorded).sum()); long_closed_by_sell = int(((L.side == 'LONG') & (L.close_reason != 'SETTLEMENT')).sum()); long_open = int((L.side == 'LONG').sum()); short_closed = int(((L.side == 'SHORT') & (L.close_reason != 'SETTLEMENT')).sum())
    assert sells == short_open + long_closed_by_sell and buys == long_open + short_closed
