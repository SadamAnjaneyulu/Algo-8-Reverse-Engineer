"""Registered cost scenarios (decision D5): read from analysis/engine.py and never redefined.
A scenario is (a, b, c): a = share of premium turnover, b = rupees per parent order, c = rupees per unit traded;  cost = a*turnover + b*orders + c*units."""
import os, importlib.util
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def registered():
    spec = importlib.util.spec_from_file_location('alpha_engine', os.path.join(REPO, 'analysis', 'engine.py')); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return dict(mod.COSTS)


def straddle_round_trip(premium_points, lot, scen):
    """cost in rupees and as a share of the entry premium for ONE lot of an ATM straddle bought or sold and later closed at the same premium:
    4 parent orders (2 legs x entry and exit), 4*lot units, turnover = 2 * premium * lot."""
    a, b, c = registered()[scen]; rs = a * 2 * premium_points * lot + b * 4 + c * 4 * lot
    return rs, rs / (premium_points * lot)
