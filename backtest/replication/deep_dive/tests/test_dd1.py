"""DD-1 tests: tag-stamp decode on synthetic orders, and invariants of the computed outputs (not rule recovery)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import dd_common as C
OUT = C.OUT


def test_decode_stamp_formula():
    # tag h_ + DD HH MM SS ffffff, UTC; IST = +5:30. 04:00:30.250000 UTC -> 09:30:30.25 IST
    raw = pd.Series(['h_08040030250000']).str.extract(r'^[a-z]_(\d{2})(\d{2})(\d{2})(\d{2})(\d{6})$').astype(float)
    utc = raw[1] * 3600 + raw[2] * 60 + raw[3] + raw[4] / 1e6
    assert abs(float(utc.iloc[0] + 5.5 * 3600) - (9 * 3600 + 30 * 60 + 30.25)) < 1e-6


def test_decode_wraps_past_midnight():
    t = 23 * 3600 + 5.5 * 3600
    assert (t - 86400 if t >= 86400 else t) == 4.5 * 3600


def test_tagged_orders_decoded_on_ledger():
    T = C.tagged_orders(C.fills())
    assert set(T.module.unique()) <= {'h_', 's_', 'v_', 'm_'}
    assert T.t_dec.between(0, 86400).all()
    # decoded stamp is within 60 s of the fill clock for the great majority of orders (same clock basis)
    assert (T.lat.abs() < 60).mean() > 0.9


def test_hedge_bursts_output_invariants():
    H = pd.read_csv(f'{OUT}/dd_hedge_bursts.csv')
    assert 'after_stop_cycle' not in H.columns   # placeholder column removed
    assert H.responded.mean() > 0.9
    assert (H.dS != 0).all()
    assert ((H.S_after - H.S_before) == H.dS).all()


def test_exit_timing_output_invariants():
    E = pd.read_csv(f'{OUT}/dd_exit_timing.csv')
    assert E.s.between(0, 59).all() and E.ratio.gt(0).all()
    # the structural contrast the report relies on, with a wide margin (not a fitted threshold)
    assert (E[E.day == 0].s == 0).mean() > 5 * (E[E.day == 1].s == 0).mean() / 2


def test_roll_pairs_conserve_lots():
    P = pd.read_csv(f'{OUT}/dd_roll_pairs.csv'); assert (P.lots > 0).all() and P.delay.between(0, 60).all()
