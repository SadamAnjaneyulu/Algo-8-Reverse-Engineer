"""Tests for Algo 8 decision engine v1 (parameters extracted from the 35 live cycles)."""
import os, sys, copy, json
import numpy as np, pandas as pd, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import algo8_v1 as V, exec_core as X
from test_core_integrity import fake_cycle


def cyc(seed=1, d0='2026-09-08'):
    c = fake_cycle(seed); c['strikes'] = np.arange(100, 350, 50); c['d0'] = d0; c['d1'] = '2026-09-07'
    for d in (0, 1): c[(d, 'spot')] = 200 + np.cumsum(np.random.default_rng(seed + d).normal(0, 1, X.NM))
    return c


def test_params_are_extracted_from_the_ledger_with_provenance():
    p = V.PARAMS; assert p['provenance']['ledger_sha256'] and 'IN-SAMPLE' in p['provenance']['status']
    assert len(p['ladder_d1']['minutes']) > 10 and len(p['ladder_d0']['minutes']) > 10 and p['flatten']['minute_post_cutover'] == 359 and p['flatten']['minute_pre_cutover'] > 359
    assert all(v[r]['p_act'] >= 0.5 for v in p['ladder_d0']['minutes'].values() for r in v)                     # only minutes where the original acted in >= half of the cycles are scheduled
    assert 'unknown_not_modelled' in p['risk'] and p['risk']['cycle_stop']['limit_rs'] == 144000.0


def test_d0_entries_require_an_active_book():
    c = cyc(2); lp = V.build(c, 'NIFTY', d0_entries=True, leg_stop=False, cycle_stop=False, flatten=False).run(); e = V.events(lp)
    assert (e[(e.d == 0) & (e.tag == 'ENTRY') & (e.role == 'body')].shape[0]) > 0
    first_d0 = e[(e.d == 1) & (e.role == 'body') & (e.tag == 'ENTRY')]
    assert len(first_d0) > 0                                                                                       # carry from D-1 keeps the book active, so D0 entries happen
    c2 = cyc(2); lp2 = V.build(c2, 'NIFTY', d0_entries=True, leg_stop=False, cycle_stop=False, flatten=False)
    lp2.exit_modules = []; lp2.entry_modules[0].d1 = False; lp2.run()                                              # no D-1 entries -> empty book -> no D0 entries at all
    assert not any(f.intent.day == 1 for f in lp2.fills)


def test_flatten_minute_depends_on_the_date():
    pre = V.build(cyc(3, '2026-07-14'), 'NIFTY', cycle_stop=False, leg_stop=False).run(); post = V.build(cyc(3, '2026-09-08'), 'NIFTY', cycle_stop=False, leg_stop=False).run()
    jp = sorted({f.intent.j for f in pre.fills if f.intent.tag == 'FLATTEN'}); jq = sorted({f.intent.j for f in post.fills if f.intent.tag == 'FLATTEN'})
    assert jp == [V.PARAMS['flatten']['minute_pre_cutover']] and jq == [359] and not pre.state.lots and not post.state.lots


def test_cycle_stop_liquidates_everything_and_blocks_entries():
    lp = V.build(cyc(4), 'NIFTY', cycle_limit=1.0, leg_stop=False).run(); e = V.events(lp)
    assert lp.stopped is not None and not lp.state.lots
    assert not ((e.tag == 'ENTRY') & ((e.d > lp.stopped[0]) | ((e.d == lp.stopped[0]) & (e.j > lp.stopped[1])))).any()


def test_decisions_do_not_depend_on_future_bars():
    c = cyc(5); a = V.events(V.build(c, 'NIFTY', slip_mult=0.0).run()); cut = 200; c2 = copy.deepcopy(c)
    for r in ('CE', 'PE'):
        for k in ('close', 'open', 'volume'): c2[(0, r, k)][:, cut:] = 555.0
    c2[(0, 'spot')][cut:] = 4000.0; b = V.events(V.build(c2, 'NIFTY', slip_mult=0.0).run())
    pa = a[(a.d == 0) & (a.j < cut)].reset_index(drop=True); pb = b[(b.d == 0) & (b.j < cut)].reset_index(drop=True)
    assert len(pa) == len(pb) > 0 and (pa[['j', 'right', 'strike', 'side', 'role', 'tag']].values == pb[['j', 'right', 'strike', 'side', 'role', 'tag']].values).all()


def test_net_pnl_identity_and_determinism():
    c = cyc(6); lp = V.build(c, 'NIFTY').run(); r = V.result(lp, c, 'NIFTY'); r2 = V.result(V.build(c, 'NIFTY').run(), c, 'NIFTY')
    assert r == r2 and abs(r['net'] - (lp.state.cash + lp.settle() - r['costs'])) < 1e-6 and abs(r['gross'] - r['net'] - r['costs'] - r['slippage']) < 1e-6


def test_cycle_stop_limit_scales_with_lot_size():
    c = cyc(8); lp_small = V.build(c, 'NIFTY', units=25); lp_big = V.build(c, 'NIFTY', units=65); lp_fixed = V.build(c, 'NIFTY', units=25, stop_scaling='fixed')
    lim = lambda lp: next(m.limit for m in lp.exit_modules if hasattr(m, 'limit'))
    assert abs(lim(lp_small) - 144000.0 * 25 / 65) < 1e-6 and abs(lim(lp_big) - 144000.0) < 1e-6 and lim(lp_fixed) == 144000.0
    c2 = cyc(8); assert abs(lim(V.build(c2, 'SENSEX', units=10)) - 144000.0 * 10 / 20) < 1e-6                                   # per-index lot size reference


def test_cost_model_is_date_aware():
    import costs_v2 as C2
    assert C2.txn_rate('NIFTY', '2024-09-30') == 0.000495 and C2.txn_rate('NIFTY', '2024-10-01') == 0.0003503 and C2.txn_rate('SENSEX', '2024-10-01') == 0.000325
    assert C2.stt_sell('2024-09-30') == 0.000625 and C2.stt_sell('2025-01-01') == 0.001 and C2.stt_sell('2026-04-01') == 0.0015
    buy = C2.order_costs('NIFTY', '2025-01-01', 1, 100000); sell = C2.order_costs('NIFTY', '2025-01-01', -1, 100000); assert sell > buy > 20.0 * 1.18       # STT only on sells, stamp only on buys
