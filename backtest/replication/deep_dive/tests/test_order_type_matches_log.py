"""The engine's explicit order-type table must agree with the real D-1 log (module and validity per order), so type scoring compares like with like."""
import os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_d0x_diag as DG
from d1_algo.engine import ROLE_ORDER_TYPE
os.chdir(_cwd)
def test_real_d1_module_to_validity_is_deterministic_and_matches_the_engine_table():
    O = DG.real_orders(); d = O[(O.dayno == 0) & (O.module != 's_')]; combos = d.groupby(['module', 'validity']).size()
    assert set(combos.index) == {('h_', 'IOC'), ('num', 'DAY'), ('v_', 'IOC')} and int(combos.sum()) == 9885                       # no exception in 9,885 orders
    assert {v for r, v in ROLE_ORDER_TYPE.items() if not r.startswith('cycle_stop')} == set(combos.index)          # the default-off cycle-stop candidate roles are (s_, DAY): the stop module is outside the 9,885 orders compared here
