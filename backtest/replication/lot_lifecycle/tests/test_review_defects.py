"""Regression tests for the independent-review defects D1-D9 (INDEPENDENT_REVIEW.md). Each fails on the pre-review (v1) behaviour."""
import os, copy
import numpy as np, pandas as pd, pytest
from fixtures import fills
from lots import build_cycle

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs')


def build(spec, conv='FIFO', carry=True, settle=None, **kw):
    f = fills(spec); return build_cycle(f, 'NIFTY', '2030-01-09', carry, conv, settle, **kw), f


def test_d1_excess_body_buy_is_an_explicit_unresolved_interpretation():
    spec = [('D0', 300, 'num', 'Buy', 'CE', 24000, 2, 60.0)]                                                    # buy with no recorded short, carry-in known
    L, _ = build(spec, settle=24000.0); assert (L.side == 'LONG').all() and L['flags'].str.contains('BODY_BUY_WITHOUT_RECORDED_SHORT_OPENED_AS_LONG').all() and not L.entry_unrecorded.any()
    L2, _ = build(spec, settle=24000.0, excess_body_buy='unrecorded_short'); assert (L2.side == 'SHORT').all() and L2.entry_unrecorded.all() and L2['flags'].str.contains('UNRECORDED_PRIOR_SHORT_INTERPRETATION').all() and L2.realized_pnl.isna().all()


def test_d2_stop_module_buy_closes_body_shorts_and_is_not_a_new_long():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 2, 100.0), ('D0', 300, 's_', 'Buy', 'CE', 24000, 2, 160.0)]
    L, _ = build(spec, settle=24000.0); assert (L.close_reason == 'STOP_MODULE').all() and (L.side == 'SHORT').all() and (L.realized_pnl < 0).all() and len(L) == 2


def test_d3_expiry_day_eod_body_sell_closes_wing_longs_of_the_same_contract_first():
    spec = [('D-1', 100, 'h_', 'Buy', 'CE', 24500, 1, 3.0), ('D0', 15 * 3600 + 20 * 60, 'num', 'Sell', 'CE', 24500, 1, 0.5)]
    L, _ = build(spec, settle=24000.0); w = L[L.role == 'wing']; assert len(w) == 1 and w.close_reason.iloc[0] == 'CROSS_ROLE_EOD_WING_CLOSE_BY_BODY' and 'CROSS_ROLE_EOD_WING_CLOSE' in w['flags'].iloc[0]
    assert (L.side == 'LONG').all() and len(L) == 1                                                             # no spurious body short opened


def test_d6_entry_order_lots_is_order_size_not_fill_size():
    f = fills([('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0, 'ORD'), ('D-1', 101, 'num', 'Sell', 'CE', 24000, 2, 101.0, 'ORD')])
    L = build_cycle(f, 'NIFTY', '2030-01-09', True, 'FIFO', 24000.0); assert (L.entry_order_lots == 3).all() and sorted(L.entry_fill_lots.unique()) == [1, 2]


def test_d7_start_book_is_not_mutated_by_the_simulator():
    import d0_sim_v2 as S2
    from opening_book import opening_book
    from ledger import load_fills
    from data import load_cycle, CACHE
    if not os.path.exists(os.path.join(CACHE, 'SENSEX_2026-09-24.pkl')): pytest.skip('cache absent')
    F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); r = C[(C.und == 'SENSEX') & (C.expiry == '2026-09-24')].iloc[0]; c = load_cycle(r.und, r.expiry, r.d1, r.d0)
    start = opening_book(F, r.und, r.expiry, r.d1); before = copy.deepcopy(start); S2.simulate_d0(c, r.und, None, start=start, price_stop=True); assert start == before


def test_d8_passive_at_stop_has_two_explicit_bounds():
    import d0_sim_v2 as S2
    from opening_book import opening_book
    from ledger import load_fills
    from data import load_cycle, CACHE
    if not os.path.exists(os.path.join(CACHE, 'SENSEX_2026-09-24.pkl')): pytest.skip('cache absent')
    F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); r = C[(C.und == 'SENSEX') & (C.expiry == '2026-09-24')].iloc[0]; c = load_cycle(r.und, r.expiry, r.d1, r.d0)
    a = S2.simulate_d0(c, r.und, None, start=opening_book(F, r.und, r.expiry, r.d1), price_stop=True, passive_at_stop='close_all'); b = S2.simulate_d0(c, r.und, None, start=opening_book(F, r.und, r.expiry, r.d1), price_stop=True, passive_at_stop='keep')
    assert not a['passive_open_at_end'] and len(b['passive_open_at_end']) > 0 and abs(a['gross'] - b['gross']) > 1000


def test_d4_panel_at_d0_minute_zero_never_reads_the_d0_0915_bar():
    import panel
    from ledger import load_fills
    from data import load_cycle, CACHE
    if not os.path.exists(os.path.join(CACHE, 'NIFTY_2026-07-14.pkl')): pytest.skip('cache absent')
    F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); r = C[(C.und == 'NIFTY') & (C.expiry == '2026-07-14')].iloc[0]; g = F[(F.und == r.und) & (F.expiry == r.expiry)].sort_values(['t', 'row'])
    c = load_cycle(r.und, r.expiry, r.d1, r.d0); P0 = panel.panel_cycle(c, g, r.und, r.expiry, r.d1, r.d0); c2 = copy.deepcopy(c)
    for rt in ('CE', 'PE'): c2[(1, rt, 'close')] = c2[(1, rt, 'close')].copy(); c2[(1, rt, 'close')][:, 0] = 12345.0
    c2[(1, 'spot')] = c2[(1, 'spot')].copy(); c2[(1, 'spot')][0] = 99999.0
    P1 = panel.panel_cycle(c2, g, r.und, r.expiry, r.d1, r.d0); a = P0[P0.j == 0].reset_index(drop=True); b = P1[P1.j == 0].reset_index(drop=True)
    assert len(a) > 0 and a[['price', 'ratio_avg', 'ratio_cheapest', 'off_steps', 'itm']].equals(b[['price', 'ratio_avg', 'ratio_cheapest', 'off_steps', 'itm']])


def test_d5_replacement_pairs_are_one_to_one_and_null_is_complete():
    p = f'{OUT}/replacement_pairs.csv.gz'; h = f'{OUT}/replacement_headline.csv'
    if not (os.path.exists(p) and os.path.exists(h)): pytest.skip('replacement outputs absent')
    P = pd.read_csv(p); P = P[P.has_candidate]; assert not P.duplicated(['und', 'expiry', 's_tag']).any()          # an opening-sale order is consumed by at most one buy-back
    H = pd.read_csv(h).iloc[0]; assert H.draws >= 200 and H.ci_lo < H.ratio < H.ci_hi


def test_holding_seconds_are_market_seconds_across_the_overnight_gap():
    spec = [('D-1', 15 * 3600, 'num', 'Sell', 'CE', 24000, 1, 100.0), ('D0', 9 * 3600 + 20 * 60, 'num', 'Buy', 'CE', 24000, 1, 80.0)]
    L, _ = build(spec, settle=24000.0); assert L.holding_seconds.iloc[0] == 30 * 60 + 5 * 60


def test_settlement_proxy_changes_settled_pnl_only():
    spec = [('D-1', 100, 'num', 'Sell', 'CE', 24000, 1, 100.0)]
    a, _ = build(spec, settle=24100.0); b, _ = build(spec, settle=24089.0); assert (a.close_reason == 'SETTLEMENT').all() and abs((b.realized_pnl.iloc[0] - a.realized_pnl.iloc[0]) - 11 * 65) < 1e-6
