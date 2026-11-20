"""Body/Hedge investigation: order-level table with the order columns the earlier studies did not use (limit price, validity, status, remaining qty), plus fill-level table with those columns joined. Read-only on the ledger."""
from dd_common import *
import load as L

_RAW = None


def raw_cols():
    """order-level raw columns keyed by ledger row: limit price (c17), order qty (c19), remaining qty (c20), validity (c22), status (c27), price band (c154)"""
    global _RAW
    if _RAW is None:
        d = L.load_tagged()
        _RAW = d[['row', 'px_order', 'qty_order', 'qty_c20', 'validity', 'status', 'c154']].rename(columns={'px_order': 'lim_px', 'qty_c20': 'rem_qty', 'c154': 'band'})
    return _RAW


def fills_x():
    """fill-level table (ref.load_fills) + order columns"""
    F = fills(); X = F.merge(raw_cols().drop(columns=['validity']), on='row', how='left'); X['lim_lots'] = X.qty_order / X.und.map(LOT); X['rem_lots'] = X.rem_qty / X.und.map(LOT)
    lo_hi = X.band.str.extract(r'^([\d.]+)-([\d.]+)$').astype(float); X['band_lo'] = lo_hi[0]; X['band_hi'] = lo_hi[1]
    return X.sort_values(['t', 'row']).reset_index(drop=True)


def order_table(X=None):
    """one row per order (tag). fill_secs = distinct fill seconds, t_first/t_last = first/last fill second (IST seconds since midnight), px_first = first fill price, px_avg = qty-weighted avg, lim_px = order limit price (c17), t_dec only for stamped modules."""
    X = fills_x() if X is None else X
    X = X.assign(w=X.px * X.n_lots)
    g = X.groupby('tag')
    O = g.agg(und=('und', 'first'), expiry=('expiry', 'first'), dayno=('dayno', 'first'), module=('module', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), side=('side', 'first'),
              lots=('n_lots', 'sum'), lim_lots=('lim_lots', 'first'), lim_px=('lim_px', 'first'), validity=('validity', 'first'), n_fills=('row', 'size'), fill_secs=('sec', 'nunique'), t_first=('sec', 'min'), t_last=('sec', 'max'),
              row=('row', 'min'), w=('w', 'sum'), j=('j', 'min'), status_last=('status', 'last'), n_partial=('status', lambda s: (s == 'PartiallyFilled').sum()), complete=('carry_in_known', 'first')).reset_index()
    O['px_avg'] = O.w / O.lots; O['px_first'] = X.sort_values(['t', 'row']).groupby('tag').px.first().reindex(O.tag).values
    T = tagged_orders(fills()); O = O.merge(T[['tag', 't_dec']], on='tag', how='left')
    O['tt_first'] = O.dayno * 100000 + O.t_first; O['tt_last'] = O.dayno * 100000 + O.t_last; O['tt_dec'] = O.dayno * 100000 + O.t_dec
    return O.sort_values(['und', 'expiry', 'tt_first', 'row']).reset_index(drop=True)


class Chain:
    """minute option/spot lookup per cycle from replication/data.load_cycle (cached pickles). open/close/volume only (no bid/ask)."""
    def __init__(self):
        import data
        from bt import cycles as Cy
        self.cl = Cy.cycle_list(); self.data = data; self._c = {}

    def cyc(self, und, exp):
        k = (und, exp)
        if k not in self._c:
            m = self.cl[(self.cl.und == und) & (self.cl.expiry == exp)].iloc[0]; c = self.data.load_cycle(und, exp, m.d1, m.d0); c['_si'] = {int(s): i for i, s in enumerate(c['strikes'])}; self._c[k] = c
        return self._c[k]

    def px(self, und, exp, dayno, cp, strike, j, kind='close'):
        """contract price at minute j (0..374) of day dayno (0 = D-1, 1 = D0); NaN if missing"""
        c = self.cyc(und, exp); i = c['_si'].get(int(strike))
        if i is None or j < 0 or j > 374: return np.nan
        return c[(dayno, cp, kind)][i, j]

    def spot(self, und, exp, dayno, j):
        c = self.cyc(und, exp); return c[(dayno, 'spot')][j] if 0 <= j <= 374 else np.nan

    def strikes(self, und, exp): return self.cyc(und, exp)['strikes']


class Book:
    """Contract-level state queries per (und, expiry, cp) from all orders (ownership-free). Event time te = order decision stamp for stamped modules, first fill second for body orders.
    state(T, inclusive) -> (S, L, nets) with S = short lots, L = long lots = sums of the negative / positive net positions over strikes after all events with te < T (or <= T if inclusive)."""
    def __init__(self, O):
        O = O.copy(); O['te'] = np.where(O.module.isin(['h_', 's_', 'v_', 'm_']), O.tt_dec, O.tt_first); O['sl'] = np.where(O.side == 'Buy', O.lots, -O.lots); self.d = {}
        for (u, e, cp), o in O.groupby(['und', 'expiry', 'cp']):
            o = o.sort_values(['te', 'row']); ks = sorted(o.strike.unique()); idx = {k: i for i, k in enumerate(ks)}; te = o.te.values; M = np.zeros((len(o), len(ks))); M[np.arange(len(o)), o.strike.map(idx).values] = o.sl.values
            self.d[(u, e, cp)] = (te, np.cumsum(M, axis=0), ks, o.complete.iloc[0])

    def state(self, u, e, cp, T, inclusive=False):
        te, C, ks, comp = self.d[(u, e, cp)]; i = np.searchsorted(te, T, side='right' if inclusive else 'left')
        net = C[i - 1] if i > 0 else np.zeros(len(ks)); return -net[net < 0].sum(), net[net > 0].sum(), dict(zip(ks, net))
