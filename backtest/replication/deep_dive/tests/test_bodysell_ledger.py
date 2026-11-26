"""Verification of the body-sell ledger classification (reports/BODY_SELL_MISMATCH_PLAN.md, software checks 1-4): hand-built examples with answers known independently."""
import os, sys, numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..')
for p in (f'{BASE}/src', f'{BASE}/../..', f'{BASE}/../../..', f'{BASE}/../../../d1_strategy'): sys.path.insert(0, p)
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_bodysell_ledger as L
os.chdir(_cwd)
O = L.OPEN_S
def R(t, cp, strike=24000.0, lots=1, cls='body_sell', side='sell', cyc='C'): return dict(cyc=cyc, cp=cp, side=side, strike=strike, lots=lots, t=t, cls=cls, row=0)
def S(sec, cp, strike=24000.0, lots=1, cls='body_sell', role='ladder_solo', side='sell', cyc='C'): return dict(cyc=cyc, cp=cp, side=side, strike=strike, lots=lots, sec=sec, cls=cls, role=role, seq=0, t=sec)
def build(real, sim, pairs, tt=None):
    r = pd.DataFrame(real); r['row'] = np.arange(len(r)); s = pd.DataFrame(sim); s['seq'] = np.arange(len(s)); P = pd.DataFrame(pairs, columns=['ri', 'si', 'tier', 'dt', 'dstrike', 'dlots']).astype({'ri': int, 'si': int})
    return L.build_ledgers(r, s, P, tt or {'C': []})
def test_every_missing_real_and_extra_simulated_sell_gets_the_right_category():
    real = [R(1000, 'CE'), R(1010, 'CE'), R(2000, 'PE'), R(3000, 'CE'), R(5000, 'CE'), R(5001, 'PE'), R(9010, 'CE')]
    sim = [S(1000, 'CE'), S(2030, 'CE'), S(3200, 'CE'), S(5001, 'PE'), S(8000, 'CE'), S(9000, 'CE'), S(9010, 'CE')]
    pairs = [(0, 0, 0, 0, 0, 0), (5, 3, 0, 0, 0, 0), (6, 6, 0, 0, 0, 0)]
    LR, LS, r, s = build(real, sim, pairs)
    assert LR.category.tolist() == ['matched', 'M1', 'M2', 'M3', 'M4', 'matched', 'matched']
    assert LS.category.tolist() == ['matched', 'X2', 'X3', 'matched', 'X4', 'X1', 'matched']
    assert LR.loc[4, 'inferred_module'] == 'pair' and LR.loc[1, 'inferred_module'] == 'solo'                                 # r4 has an opposite-type real sell within 2 s; r1 has none
def test_cascade_order_is_enforced_M1_before_M2_before_M3():
    real = [R(11000, 'CE'), R(500, 'CE')]; sim = [S(11020, 'CE'), S(11030, 'PE'), S(11200, 'CE'), S(500, 'CE')]
    LR, LS, r, s = build(real, sim, [(1, 3, 0, 0, 0, 0)]); assert LR.loc[0, 'category'] == 'M1'                          # same-type within 60 s (S0) is not matched here, but the cascade picks it first
    real = [R(11000, 'CE')]; sim = [S(11030, 'PE'), S(11200, 'CE')]; LR, LS, r, s = build(real, sim, []); assert LR.loc[0, 'category'] == 'M2'
    real = [R(11000, 'CE')]; sim = [S(11200, 'CE')]; LR, LS, r, s = build(real, sim, []); assert LR.loc[0, 'category'] == 'M3'
def test_window_boundaries_are_fixed_at_60_and_300_seconds():
    for dist, exp in ((60, 'M2'), (61, 'M4')):                                                                              # opposite-type unmatched at 60 s: M2; at 61 s it is outside the near window and not a same-type far match: M4
        LR, *_ = build([R(1000, 'CE')], [S(1000 + dist, 'PE')], []); assert LR.loc[0, 'category'] == exp
    for dist, exp in ((61, 'M3'), (300, 'M3'), (301, 'M4')):
        LR, *_ = build([R(1000, 'CE')], [S(1000 + dist, 'CE')], []); assert LR.loc[0, 'category'] == exp
    for dist, exp in ((60, 'X2'), (61, 'X4')):
        _, LS, *_ = build([R(1000, 'PE')], [S(1000 + dist, 'CE')], []); assert LS.loc[0, 'category'] == exp
    for dist, exp in ((61, 'X3'), (300, 'X3'), (301, 'X4')):
        _, LS, *_ = build([R(1000, 'CE')], [S(1000 + dist, 'CE')], []); assert LS.loc[0, 'category'] == exp
def test_scheduled_clock_label_uses_the_cycle_timetable_within_one_second():
    t = O + 60 + 7; LR, *_ = build([R(t, 'CE'), R(t + 1, 'PE'), R(t + 5, 'CE')], [S(1, 'CE', cls='wing_sell')], [], {'C': [7]}); assert LR.inferred_module.tolist() == ['scheduled_clock', 'scheduled_clock', 'solo']
    LR2, *_ = build([R(t + 2, 'CE')], [S(1, 'CE', cls='wing_sell')], [], {'C': [7]}); assert LR2.inferred_module.tolist() == ['solo']             # two seconds off the clock is not the scheduled clock
def test_only_body_sells_enter_the_ledgers_but_other_classes_serve_as_neighbours():
    real = [R(2000, 'CE'), R(2011, 'CE', cls='wing_sell')]; sim = [S(2010, 'CE', cls='wing_sell', role='protective_wing_sell')]
    LR, LS, r, s = build(real, sim, [(1, 0, 0, 0, 0, 0)]); assert len(LR) == 1 and len(LS) == 0 and LR.iloc[0].category == 'M1' and LR.iloc[0].nearest_sim_role == 'protective_wing_sell'     # a matched wing sell is the supply neighbour of the missing body sell
def test_books_before_nets_per_contract_and_excludes_the_order_itself():
    df = pd.DataFrame([dict(cyc='C', cp='CE', strike=24000.0, side='sell', lots=2, t=1, row=0), dict(cyc='C', cp='CE', strike=24000.0, side='buy', lots=1, t=2, row=1), dict(cyc='C', cp='PE', strike=23000.0, side='buy', lots=3, t=3, row=2), dict(cyc='C', cp='CE', strike=24100.0, side='sell', lots=1, t=4, row=3)])
    b = L.books_before(df, 't', ['t', 'row']); assert b.loc[0].tolist() == [0, 0, 0, 0] and b.loc[1].tolist() == [2, 0, 0, 0] and b.loc[2].tolist() == [1, 0, 0, 0] and b.loc[3].tolist() == [1, 0, 0, 3]
    S_, L_ = L.book_at_second(df, 't', 'C', 3); assert S_['CE'] == 1 and L_['PE'] == 0 and L.book_at_second(df, 't', 'C', 4)[1]['PE'] == 3
