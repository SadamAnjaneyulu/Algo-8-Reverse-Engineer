"""Tests for the focused late-sale tests (reports/LATE_SALE_FOCUSED.md): helper correctness on synthetic cubes with known answers, and regression checks of the reported numbers."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_trig3_focused as T, bl_fwd_eval_v2 as E
os.chdir(_cwd)
T3 = f'{BASE}/outputs/trig3'
def synth(sep):
    """2 cycles x 2 sides x 10 minutes; the positive minute carries the highest (sep=+1) or lowest (sep=-1) feature value in every block"""
    X = np.tile(np.arange(10.0), (2, 2, 1)); Y = np.zeros((2, 2, 10), int); Y[:, :, 9 if sep > 0 else 0] = 1; return X, Y
def test_auc_perfect_reversed_and_chance():
    X, Y = synth(+1); assert T.auc(T.ranks(X), Y, 10) == 1.0
    X, Y = synth(-1); assert T.auc(T.ranks(X), Y, 10) == 0.0
    Y2 = np.zeros((2, 2, 10), int); Y2[:, :, 4] = 1; Y2[:, :, 5] = 1; X = np.tile(np.array([0, 1, 2, 3, 9, 0, 5, 6, 7, 8.]), (2, 2, 1)); a = T.auc(T.ranks(X), Y2, 10); assert 0.0 <= a <= 1.0
def test_auc_is_stratified_within_blocks():
    """a feature that differs only BETWEEN blocks (cycle level offset) must give AUC 0.5 when every block has the same positive position"""
    X = np.zeros((2, 2, 10)); X[0] += 100.0; Y = np.zeros((2, 2, 10), int); Y[:, :, 3] = 1; assert abs(T.auc(T.ranks(X), Y, 10) - 0.5) < 0.5 and T.auc(T.ranks(X), Y, 10) == 0.5
def test_cubes_shape_and_incomplete_cycles_dropped():
    rows = [dict(cyc=c, side=s, j=j, y=int(j == 365), f=float(j)) for c in ('A', 'B') for s in ('CE', 'PE') for j in range(360, 375)]; rows = [r for r in rows if not (r['cyc'] == 'B' and r['j'] == 370)]
    cyc, nj, X = T.cubes(pd.DataFrame(rows), ['f', 'y'], 360, 374); assert cyc == ['A'] and nj == 15 and X['f'].shape == (1, 2, 15) and X['y'].sum() == 2
def test_null_curveball_keeps_positive_counts():
    rng = np.random.default_rng(1); Y = (rng.random((6, 2, 15)) < 0.15).astype(int); T.RT.RNG = rng
    for s in range(2):
        Z = T.RT.curveball(Y[:, s, :].copy()); assert (Z.sum(1) == Y[:, s, :].sum(1)).all() and (Z.sum(0) == Y[:, s, :].sum(0)).all()
def test_reported_focused_results_regression():
    r = json.load(open(f'{T3}/focused.json')); ex = json.load(open(f'{T3}/focused_extra.json'))
    assert r['F2a']['contrarian_share'] > 0.70 and r['F2a']['ci95'][0] > 0.5 and r['F2a_heldout']['contrarian_share'] > 0.70
    assert r['F1']['auc'] >= 0.50 and r['F1']['power_estimate_7cycles_15min'] < 0.5 and r['F1p']['p_one_sided'] < 0.01
    assert ex['auc_375_384'] < 0.25 and ex['sale_minutes_375_384'] == 7 and ex['auc_360_374'] > 0.40
    assert r['PB1']['after']['sold_above_entry'] == 0.0 and r['PB1']['before']['sold_above_entry'] == 0.0 and r['PB2']['share'] > 0.8
    assert r['PB3']['p_two_sided'] > 0.3 and r['PB5']['p_one_sided'] > 0.2 and r['F3']['J_vs_T']['lin95'][0] < 0 < r['F3']['J_vs_T']['lin95'][1]
def test_family_file_and_pair_window_regression():
    F = pd.read_csv(f'{T3}/family.csv'); assert len(F) == 9 and F.id.is_unique and (F.bh_significant_10 == (F.p_bh_10 <= 0.10)).all() and (F.p_bh_10 >= F.p - 1e-12).all()
    assert set(F[F.bh_significant_10].id) == {'F1p', 'F2a', 'F2a_heldout', 'PB2'}
    ex = json.load(open(f'{T3}/focused_extra.json')); assert ex['pre_auction_bursts'] == 18 and ex['pre_auction_pair_bursts'] == 2
def test_close_long_file_regression():
    CL = pd.read_csv(f'{T3}/close_long.csv'); assert len(CL) == 34 and (CL.ratio.dropna() < 1).all() and set(CL.era) == {'after', 'before'}
def test_frozen_objects_unchanged():
    assert E.verify_frozen(E.load_config()) is True
