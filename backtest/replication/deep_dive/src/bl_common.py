"""Body lifecycle study: shared builders. Builds on bh_common (order table, Chain, Book) and bh_b1 roles."""
from bh_common import *
K15 = 0.15


def body_table():
    """body (numeric-tag) orders with contract-level role, decision-time reference price (limit/(1+-0.15)), spot closes at minute j-1 and j, nearest strikes (R1, R2). One row per order."""
    O = order_table(); R = pd.read_csv(f'{OUT}/bh_b1_order_roles.csv', dtype={'tag': str})[['tag', 'role', 'net_before']]
    B = O[O.module == 'num'].merge(R, on='tag', how='left'); ch = Chain()
    B['ref_px'] = np.where(B.side == 'Sell', B.lim_px / (1 - K15), B.lim_px / (1 + K15)); B['step'] = B.und.map(ref.STEP)
    sp_prev = []; sp_cur = []; n1 = []; n2 = []
    for r in B.itertuples():
        j = int(r.j); st = ch.strikes(r.und, r.expiry)
        a = ch.spot(r.und, r.expiry, r.dayno, j - 1) if j >= 1 else np.nan; b = ch.spot(r.und, r.expiry, r.dayno, j)
        sp_prev.append(a); sp_cur.append(b); n1.append(st[np.argmin(np.abs(st - a))] if a == a else np.nan); n2.append(st[np.argmin(np.abs(st - b))] if b == b else np.nan)
    B['spot_prev'] = sp_prev; B['spot_cur'] = sp_cur; B['atm_prev'] = n1; B['atm_cur'] = n2
    return B.sort_values(['und', 'expiry', 'tt_first', 'row']).reset_index(drop=True)


ORDERS_PKL = f'{OUT}/bl_all_orders.pkl.gz'


def load_orders():
    """all orders with roles, ATM references, classes and running contract/right state (built by bl_events.py)"""
    return pd.read_pickle(ORDERS_PKL)


def rec(name, d):
    """write a summary dict to outputs/bl_summary_<name>.json (numbers quoted in the report). Series with a float index (quantiles) become lists; other Series become {index: value} dicts."""
    import json
    def f(x):
        if isinstance(x, (bool, int, float, str)) or x is None: return x
        if isinstance(x, np.bool_): return bool(x)
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.floating): return float(x)
        if isinstance(x, pd.Series):
            if pd.api.types.is_float_dtype(x.index): return [f(v) for v in x.values]
            return {str(k): f(v) for k, v in x.items()}
        if isinstance(x, (pd.Index, np.ndarray, list, tuple)): return [f(v) for v in x]
        if isinstance(x, dict): return {str(k): f(v) for k, v in x.items()}
        return str(x)
    json.dump({k: f(v) for k, v in d.items()}, open(f'{OUT}/bl_summary_{name}.json', 'w'), indent=1)
