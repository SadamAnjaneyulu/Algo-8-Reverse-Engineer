"""Tests for the order-sequence investigation (reports/LATE_SALE_SEQUENCE.md): helper correctness on synthetic orders and regression of the reported numbers."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_trig5_sequence as Q, bl_fwd_eval_v2 as E
os.chdir(_cwd)
T5 = f'{BASE}/outputs/trig5'
def orders():
    rows = [(1000.0, 'CE', 100, -1, 5, 'num', 'open_short'), (1001.0, 'CE', 100, -1, 5, 'num', 'open_short'), (1002.0, 'CE', 120, 1, 7, 'h_', 'open_long'), (1003.0, 'CE', 150, 1, 4, 'v_', 'open_long'), (1004.0, 'PE', 90, -1, 3, 'num', 'open_short')]
    return pd.DataFrame(rows, columns=['t_first', 'cp', 'strike', 'sg', 'lots', 'module', 'role'])
def test_book_short_and_long_lots_and_inclusive_time():
    g = orders(); S, L, net = Q.book(g, 'CE', 1003.0); assert (S, L) == (10.0, 7.0) and net[100] == -10 and net[120] == 7           # strictly before 1003: lump (1003) excluded, PE excluded
    S2, L2, _ = Q.book(g, 'CE', 1003.0, upto_inclusive=True); assert (S2, L2) == (10.0, 11.0)
def test_tolerance_and_clusters():
    assert Q.tol(0) == 1.0 and Q.tol(40) == 4.0 and Q.tol(5) == 1.0
    x = pd.DataFrame(dict(t_first=[0.0, 4.0, 14.0, 40.0])); cl = Q.clusters(x); assert [len(c) for c in cl] == [3, 1]
def test_reported_sequence_results():
    r = json.load(open(f'{T5}/sequence.json')); F = pd.read_csv(f'{T5}/family.csv'); d = json.load(open(f'{T5}/wing_diag_summary.json'))
    assert r['W2']['observed'] == 10 and r['W2']['clusters'] == 13 and r['W2']['excess'] > 0.30 and r['W3']['observed'] == 11 and r['W3']['excess'] > 0.30
    assert r['W1']['excess'] < 0.30 and F.bh_significant_10.all() and len(F) == 3                                           # W1 is BH-significant but misses its pre-set size rule (flawed definition, reported as such)
    assert r['descriptive']['lag_since_body_any']['50%'] == 4.0 and r['descriptive']['burst_first'] == 10 and r['descriptive']['cluster_first'] == 2
    assert d['after_exact_equal'] == 18 and d['clusters_all'] == 18 and d['before_positive'] == 16 and d['random_times_exact_equal'] > 0.98
def test_frozen_objects_unchanged():
    assert E.verify_frozen(E.load_config()) is True
