"""Unit tests for the Phase-2 stop-reference simulation.  python -m pytest analysis/allocation/tests"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AL = os.path.dirname(HERE); AN = os.path.dirname(AL)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, AL)
import numpy as np, pandas as pd
import stop_reference as sr, stop_select as sel, stop_discriminator as sd

def arr_two_lots():
    # one contract (index 0): lot A entered minute 0 at 10, closed at minute 5 (exit_mi = 5); lot B entered minute 1 at 20, open to the end; 10 minutes
    return dict(mi0=np.array([0, 1]), mi1=np.array([5, 9]), px=np.array([10., 20.]), ki=np.array([0, 0]), carried=np.array([False, False]), day=np.zeros(10, int),
                slot=np.array([0, 0]), chain=np.array([0, 1]), ocode=np.array([0, 1]))

def test_closed_lots_are_excluded_from_the_reference():
    Op, SEG, refs = sr.build_refs(arr_two_lots(), 1, 10)
    T, uc = refs['cheapest open entry']
    assert T[0, 1] == 10 and T[0, 2] == 10                    # lot A open from minute 1 (entered in an earlier minute)
    assert T[0, 5] == 10                                       # closes IN minute 5: still open at the start of 5 (the trigger may be what closed it)
    assert T[0, 6] == 20                                       # closed lots are excluded afterwards: reference is lot B only
    assert np.isnan(T[0, 0])                                   # nothing is open in the entry minute itself
    W = refs['lot-weighted contract average'][0]
    assert W[0, 2] == 15 and W[0, 6] == 20
    S = refs['slot-allocation average'][0]; assert S[0, 2] == 15                       # both lots in slot 0
    C = refs['chain-allocation average'][0]; assert C.shape[0] == 2 and C[0, 2] == 10 and C[1, 2] == 20   # separate chains
    O, _ = refs['own entry (per lot)']; assert O[0, 6] != O[0, 6] and O[1, 6] == 20     # lot A's own reference is NaN once closed

def test_matching_is_one_to_one_and_respects_window_and_quote():
    ev_c = np.array([0, 0]); ev_m = np.array([3, 3]); ev_ref = np.array([10., 10.])
    bb_c = np.array([0]); bb_m = np.array([4]); bb_L = np.array([16.]); bb_t = np.array([1.])
    me, mb = sr.match(ev_c, ev_m, ev_ref, bb_c, bb_m, bb_L, bb_t, 2, 1.5, True)
    assert me.sum() == 1 and mb.sum() == 1                      # one buy-back credits ONE of the two events
    me, mb = sr.match(ev_c, ev_m, ev_ref, bb_c, bb_m, np.array([14.]), bb_t, 2, 1.5, True); assert me.sum() == 0   # own quote below 1.5 x entry: not quote-confirmed
    me, mb = sr.match(ev_c, ev_m, ev_ref, bb_c, bb_m, np.array([14.]), bb_t, 2, 1.5, False); assert me.sum() == 1  # association-only ignores the quote
    me, mb = sr.match(ev_c, ev_m, ev_ref, bb_c, np.array([7]), bb_L, bb_t, 2, 1.5, True); assert me.sum() == 0    # outside the window
    me, mb = sr.match(ev_c, np.array([5, 5]), ev_ref, bb_c, bb_m, bb_L, bb_t, 2, 1.5, True); assert me.sum() == 0  # buy-back BEFORE the crossing minute

def test_f1_and_bootstrap_helpers():
    assert abs(float(sel.f1(np.array([0.5]), np.array([0.5]))[0]) - 0.5) < 1e-12
    d = pd.DataFrame(dict(und='N', expiry=[1, 2, 3], ev_first=[10, 10, 10], ev_repeat=0, tp_first=[5, 5, 5], tp_repeat=0, buybacks=[10, 10, 10], matched_buybacks=[5, 5, 5], covered_buybacks=[9, 9, 9]))
    b = sel.boot(d, reps=200); assert abs(b['p_lo'] - 0.5) < 1e-9 and abs(b['r_hi'] - 0.5) < 1e-9 and abs(b['c_lo'] - 0.9) < 1e-9

def test_matched_hazard_delta_is_zero_when_hazard_depends_only_on_the_lot_ratio():
    nb = len(sd.BINS) - 1; cnt = np.zeros((3, nb, 4)); cnt[:, 5, :] = [100, 10, 100, 10]; cnt[:, 6, :] = [100, 20, 100, 20]   # same hazard in the 'high' and 'low' dispersion groups
    dl, hl, used = sd.matched_delta(cnt); assert abs(dl) < 1e-12 and used == 2
    cnt[:, 5, :] = [100, 5, 100, 10]; assert sd.matched_delta(cnt)[0] < 0                              # lower hazard when the average is far away => average-like
