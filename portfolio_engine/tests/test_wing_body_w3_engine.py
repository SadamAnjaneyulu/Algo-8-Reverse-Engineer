"""M2-F defect C-02: ENGINE-LEVEL, hand-calculated test of the W3 queue matching (queue_matched_units, segment, weight, residuals) with wings and bodies of UNEQUAL quantities.
No committed output is read; every expected number is calculated by hand below.

W3 rule (python/pe/wing_body.py, queue_w3 and docs): inside one (level OPENING, underlying, expiry, right, session) group, wing items and body items are each ordered by (first fill time, ...) and the wing units are matched to the body units FIRST-IN-FIRST-OUT:
the earliest wing item consumes the earliest body item's units; each segment matches u = min(wing units still open, body units still open); a segment's `weight` is u / (the WHOLE wing item's quantity).

GROUP G1 = (NIFTY, 2026-01-08, CE, session 2026-01-05). Wings (buy, tag h_) in time order, bodies (sell, tag num) in time order:
  wings : W1 t=10 qty 100 | W2 t=20 qty 50 | W3 t=30 qty 130      (280 wing units)
  bodies: B1 t=0 qty 60 | B2 t=5 qty 40 | B3 t=15 qty 200 | B4 t=25 qty 30   (330 body units)
  seg1: W1(100 open) vs B1(60 open): u = min(100, 60) = 60 ; W1 has 40 left, B1 is used up          weight 60/100 = 0.6
  seg2: W1(40 open)  vs B2(40 open): u = min(40, 40)  = 40 ; both used up                           weight 40/100 = 0.4
  seg3: W2(50 open)  vs B3(200 open): u = 50 ; W2 used up, B3 has 150 left                           weight 50/50 = 1.0
  seg4: W3(130 open) vs B3(150 open): u = 130 ; W3 used up, B3 has 20 left                          weight 130/130 = 1.0
  wings are exhausted -> stop. Unmatched: wing 0 ; body 20 (rest of B3) + 30 (B4) = 50.   Check: matched 60+40+50+130 = 280 = all wing units; 330 - 280 = 50 body units unmatched.
  qty_ratio = round(wing_qty / body_qty, 6): seg1 100/60 = 1.666667, seg2 100/40 = 2.5, seg3 50/200 = 0.25, seg4 130/200 = 0.65.
  The mutant `weight = u / body_qty` would give 60/60 = 1.0, 40/40 = 1.0, 50/200 = 0.25, 130/200 = 0.65; `wing_qty / body_qty` would give the qty_ratio values; a reversed queue would start with W3 / B4.
GROUP G2 = (NIFTY, 2026-01-08, CE, session 2026-01-06, the NEXT IST day): body BN t=d+10 qty 70, wing WN t=d+20 qty 25: u = 25, weight 25/25 = 1.0; body unmatched 70 - 25 = 45 (sessions are never mixed with G1).
GROUP G3 = (NIFTY, 2026-01-08, PE, session 2026-01-05): wing WP t=10 qty 90 ; bodies P1 t=0 qty 30, P2 t=1 qty 30, P3 t=2 qty 30: three segments of u = 30 each, weight 30/90 = 1/3 -> round(1/3, 9) = 0.333333333; nothing unmatched.
GROUP G4 = (NIFTY, 2026-01-15, CE, session 2026-01-05): wing WE t=10 qty 80 ; body BE t=0 qty 50: u = min(80, 50) = 50, weight 50/80 = 0.625 ; wing unmatched 80 - 50 = 30.
Totals: wing units unmatched 30 (G4) ; body units unmatched 50 (G1) + 45 (G2) = 95.
Entry minutes (offset in minutes) decide only `in_primary_candidate_set` / `same_entry_minute`: W1 0, B1 0 -> seg1 1 ; W1 0, B2 1 -> seg2 0 ; W2 1, B3 1 -> seg3 1 ; W3 2, B3 1 -> seg4 0.
Link order in R.links['W3'] = groups sorted by (level, underlying, expiry, right, session): G1 (01-08 CE day1), G2 (01-08 CE day2), G3 (01-08 PE day1), G4 (01-15 CE day1).
"""
import pytest
from pe import wing_body as wb
from pe.schema import *
from test_wing_body import mk, N

D = 86400 - (9 * 3600 + 16 * 60)                                                              # BASE_TS + D = 00:00:00 IST of the next day (as used in test_wing_body)
CE_A = lambda k: N('CE', k); CE_L = lambda k: N('CE', k, '2026-01-15'); PE_ = lambda k: N('PE', k)


def build():
    spec = [('wing', CE_A(24800), 10, 100, 'W1', 0), ('wing', CE_A(24900), 20, 50, 'W2', 1), ('wing', CE_A(25000), 30, 130, 'W3', 2),
            ('body', CE_A(24000), 0, 60, 'B1', 0), ('body', CE_A(24050), 5, 40, 'B2', 1), ('body', CE_A(24100), 15, 200, 'B3', 1), ('body', CE_A(24150), 25, 30, 'B4', 3),
            ('body', CE_A(24000), D + 10, 70, 'BN', 400), ('wing', CE_A(24800), D + 20, 25, 'WN', 400),
            ('wing', PE_(23200), 10, 90, 'WP', 0), ('body', PE_(24000), 0, 30, 'P1', 0), ('body', PE_(23900), 1, 30, 'P2', 0), ('body', PE_(23800), 2, 30, 'P3', 0),
            ('wing', CE_L(24800), 10, 80, 'WE', 0), ('body', CE_L(24000), 0, 50, 'BE', 0)]
    ls, meta, _ = mk(spec); return ls, meta, wb.analyse(ls, meta)


# (wing parent, body parent, queue_matched_units, weight, segment, wing_qty, body_qty, qty_ratio, in_primary_candidate_set, n_candidates_for_wing, n_wings_for_body)
EXPECTED = [('W1', 'B1', 60, 0.6, 1, 100, 60, 1.666667, 1, 2, 1), ('W1', 'B2', 40, 0.4, 2, 100, 40, 2.5, 0, 2, 1), ('W2', 'B3', 50, 1.0, 3, 50, 200, 0.25, 1, 1, 2), ('W3', 'B3', 130, 1.0, 4, 130, 200, 0.65, 0, 1, 2),
            ('WN', 'BN', 25, 1.0, 1, 25, 70, 0.357143, 1, 1, 1),
            ('WP', 'P1', 30, 0.333333333, 1, 90, 30, 3.0, 1, 3, 1), ('WP', 'P2', 30, 0.333333333, 2, 90, 30, 3.0, 1, 3, 1), ('WP', 'P3', 30, 0.333333333, 3, 90, 30, 3.0, 1, 3, 1),
            ('WE', 'BE', 50, 0.625, 1, 80, 50, 1.6, 1, 1, 1)]


@pytest.fixture(scope='module')
def eng(): return build()


def test_W3_queue_matched_units_segments_and_order(eng):
    ls, meta, R = eng; got = [(l['wing_parent'], l['body_parent'], l['queue_matched_units'], l['segment']) for l in R.links['W3']]
    assert got == [(w, b, u, s) for w, b, u, _, s, *_ in EXPECTED]                                # FIFO order: earliest wing x earliest body first; units 60,40,50,130 | 25 | 30,30,30 | 50
    assert [l['level'] for l in R.links['W3']] == ['OPENING'] * 9


def test_W3_weight_column_is_queue_matched_units_over_the_whole_wing_quantity(eng):
    ls, meta, R = eng; got = [(l['wing_parent'], l['body_parent'], l['weight']) for l in R.links['W3']]
    want = [(w, b, wt) for w, b, _, wt, *_ in EXPECTED]
    assert got == want                                                                            # 0.6, 0.4, 1.0, 1.0 | 1.0 | 1/3 x3 (round 9) | 0.625
    for l in R.links['W3']: assert l['weight'] == pytest.approx(l['queue_matched_units'] / l['wing_qty'], abs=1e-9)
    by = {(l['wing_parent'], l['body_parent']): l for l in R.links['W3']}
    assert by[('WE', 'BE')]['weight'] == 0.625 and by[('WE', 'BE')]['weight'] != 50 / 50           # 50/80, not 50/50
    assert by[('W1', 'B1')]['weight'] == 0.6 and by[('W1', 'B1')]['weight'] != 1.0               # 60/100, not 60/60
    assert by[('W2', 'B3')]['weight'] == 1.0 and by[('W2', 'B3')]['weight'] != 0.25               # 50/50, not 50/200
    assert by[('W3', 'B3')]['weight'] == 1.0 and by[('W3', 'B3')]['weight'] != 0.65               # 130/130, not 130/200 and not wing_qty / body_qty
    assert by[('W1', 'B2')]['weight'] == 0.4                                                        # 40/100
    assert by[('WP', 'P1')]['weight'] == 0.333333333                                                # round(30/90, 9)
    assert sum(l['weight'] for l in R.links['W3'] if l['wing_parent'] == 'W1') == pytest.approx(1.0)     # W1's two segments consume all of W1: 0.6 + 0.4
    assert sum(l['weight'] for l in R.links['W3'] if l['wing_parent'] == 'WE') == 0.625            # partially matched wing: the weights do NOT sum to 1


def test_W3_link_quantities_ratio_and_flags(eng):
    ls, meta, R = eng
    got = [(l['wing_parent'], l['body_parent'], l['wing_qty'], l['body_qty'], l['qty_ratio'], l['in_primary_candidate_set'], l['n_candidates_for_wing'], l['n_wings_for_body']) for l in R.links['W3']]
    assert got == [(w, b, wq, bq, qr, ip, nc, nw) for w, b, _, _, _, wq, bq, qr, ip, nc, nw in EXPECTED]
    assert all(l['link_status'] == 'ARITHMETIC_SEGMENT' and l['nearest'] == 'NA' and l['method'] == 'W3' for l in R.links['W3'])
    assert [l['segment'] for l in R.links['W3']] == [1, 2, 3, 4, 1, 1, 2, 3, 1]                    # segment numbering restarts in each group and starts at 1


def test_W3_residuals_and_coverage_are_hand_values(eng):
    ls, meta, R = eng
    assert R.w3_residual == dict(wing_units_unmatched=30, body_units_unmatched=95)               # G4 wing 80-50 = 30 ; G1 body 20 + 30 + G2 body 45 = 95
    c = wb.coverage(R, 'OPENING', 'W3')
    assert (c['wing_units'], c['body_units'], c['links']) == (100 + 50 + 130 + 25 + 90 + 80, 60 + 40 + 200 + 30 + 70 + 90 + 50, 9)      # 475 wing units, 540 body units
    assert (c['wing_units_unmatched'], c['body_units_without_wing']) == (30, 95) and c['wing_units_with_candidate'] == 475 - 30 and c['body_units_with_wing_candidate'] == 540 - 95
    assert sum(l['queue_matched_units'] for l in R.links['W3']) == 60 + 40 + 50 + 130 + 25 + 90 + 50 == 445          # matched units: wing side 475 - 30 = body side 540 - 95 = 445


def test_W3_conserves_units_per_wing_and_per_body(eng):
    ls, meta, R = eng; wing_used = {}; body_used = {}
    for l in R.links['W3']:
        wing_used[l['wing_parent']] = wing_used.get(l['wing_parent'], 0) + l['queue_matched_units']; body_used[l['body_parent']] = body_used.get(l['body_parent'], 0) + l['queue_matched_units']
    assert wing_used == {'W1': 100, 'W2': 50, 'W3': 130, 'WN': 25, 'WP': 90, 'WE': 50}           # every wing is fully used except WE (50 of 80)
    assert {k: body_used[k] for k in ('B1', 'B2', 'B3', 'BN', 'P1', 'P2', 'P3', 'BE')} == {'B1': 60, 'B2': 40, 'B3': 50 + 130, 'BN': 25, 'P1': 30, 'P2': 30, 'P3': 30, 'BE': 50}
    assert 'B4' not in body_used                                                                    # B4 (30 units, last in the queue) is never reached
    wb.check(R, ls)                                                                                 # the engine's own invariants agree
