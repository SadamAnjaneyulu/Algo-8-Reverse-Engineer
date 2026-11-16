"""Shared engine for the risk-rule validation (read-only reuse of the PR #3 clean build).

Inputs reused unchanged:
  * orders()          analysis/exit_engine/common.py  - 39,874 orders keyed by column-163 UniqueOrderIdentifier, decision-time bounds, taxonomy label
  * markets()         per-cycle 1-minute grids (D-1 + D0), forward-filled option closes Cf, day flag (0 = D-1, 1 = D0)
  * replay_book(conv) unit-lot ledgers under ownership conventions 'cheap' (cheapest entry first), 'fifo', 'lifo'
  * load_tagged()     raw fills (for convention-free net positions and fills-based MTM)
Nothing in analysis/ or its caches is written.

Accounting (per unit lot, lot size 65 NIFTY / 20 SENSEX; sgn = -1 short, +1 long):
  cumulative P&L from entry   open:   sgn * (mark_t - entry) * lot      closed: sgn * (exit - entry) * lot  (realised at the exit decision minute)
  expiry-day (D0) P&L         reference = D-1 closing mark for carried lots, entry price for lots opened on D0
  mark_t = forward-filled close of minute t; before the contract's first print the lot is marked at its entry (zero unrealised).
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE); AN = os.path.join(REPO, 'analysis')
for p in (AN, os.path.join(AN, 'exit_engine')):
    if p not in sys.path: sys.path.insert(0, p)
from exit_engine.common import orders, markets, replay_book, split_of, LOT   # noqa: E402
RES = os.path.join(HERE, 'results'); os.makedirs(RES, exist_ok=True)
CONVS = ('cheap', 'fifo', 'lifo')
CAPITAL = 2.0e7
CARRY_PCT = 0.04            # client wording: "carry forward SL of 4 % on the positions carry forward to expiry"
EXPIRY_LIMIT = 0.01 * CAPITAL   # client wording: "1 % on the entire capital on expiry day" -> Rs 2,00,000
ACTION_WIN = 5              # minutes; the response window used in PR #3 / PR #5
SCHEDULED = ('5 cycle stop & liquidation', '7 expiry-day salvage', '6 clock-based exit (final flatten)', '10 manual / platform risk engine')
CLOCKED = ('8 clock-B rebalance', '6 clock-based exit (clock B, no replacement)', '8b grid rebalance (A/:00 clock)')


def cycle_keys():
    return sorted(markets().keys(), key=lambda k: (k[1], k[0]))


def d_bounds(m):
    """(index of last D-1 minute or None, index of first D0 minute or None)"""
    day = m['day']; d1 = np.where(day == 0)[0]; d0 = np.where(day == 1)[0]
    return (int(d1[-1]) if len(d1) else None), (int(d0[0]) if len(d0) else None)


CACHE = os.path.join(HERE, '_cache'); os.makedirs(CACHE, exist_ok=True)


def session_minute(m, t, date):
    """minute index of time t inside its OWN session (clipped to that session's first/last bar).
    PR #3's minute_index clips to the whole grid, so an order after the last D-1 bar lands on the first D0 minute; this does not."""
    g = m['grid']; sess = np.where(g.normalize() == pd.Timestamp(date).normalize())[0]
    if not len(sess): return int(min(g.searchsorted(pd.Timestamp(t).floor('min')), len(g) - 1))
    sub = g[sess]; i = sub.searchsorted(pd.Timestamp(t).floor('min'), side='left')
    return int(sess[min(i, len(sess) - 1)])


def ledger(conv='fifo'):
    """Unit-lot ledger: the PR #3 replay_book algorithm (same orders, same order sequence, same closing conventions),
    with one change: decision minutes are mapped inside the order's own session, and entry_day comes from the order date."""
    p = os.path.join(CACHE, f'lots_{conv}.pkl')
    if os.path.exists(p): return pd.read_pickle(p)
    o = orders(); mk = markets(); rows = []
    for (u, e), g in o.groupby(['und', 'expiry']):
        m = mk[(u, e)]; grid = m['grid']; book = {}; had_bb = set()
        for r in g.itertuples():
            k = (r.cp, r.strike); L_ = book.setdefault(k, []); n = int(r.lots); sg = 1 if r.side == 'Buy' else -1
            pos = sum(x['sgn'] for x in L_); mi = session_minute(m, r.t_dec_lo, r.date)
            if (sg > 0 and pos < 0) or (sg < 0 and pos > 0):
                if conv == 'cheap': L_.sort(key=lambda x: (x['entry_px'] if pos < 0 else -x['entry_px'], x['entry_t']))
                elif conv == 'fifo': L_.sort(key=lambda x: x['entry_t'])
                elif conv == 'lifo': L_.sort(key=lambda x: x['entry_t'], reverse=True)
                take = min(n, len(L_))
                for x in L_[:take]:
                    x.update(exit_oid=r.oid, exit_t=r.t_dec, exit_mi=mi, exit_px=r.vwap, exit_label=r.label, exit_tp=r.tp, exit_date=r.date); rows.append(x)
                del L_[:take]; n -= take
                if pos < 0: had_bb.add(k)
            for _ in range(n):
                L_.append(dict(und=u, expiry=e, cp=r.cp, strike=r.strike, sgn=sg, entry_oid=r.oid, entry_tp=r.tp, entry_t=r.t_dec, entry_mi=mi,
                               entry_px=r.vwap, entry_day=int(pd.Timestamp(r.date) == e), reentry=k in had_bb))
        for k, L_ in book.items():
            for x in L_: x.update(exit_oid=None, exit_t=pd.NaT, exit_mi=len(grid) - 1, exit_px=np.nan, exit_label='expired/open', exit_tp=None, exit_date=pd.NaT); rows.append(x)
    Lt = pd.DataFrame(rows); Lt['split'] = Lt.expiry.map(split_of)
    # carried = entered on the D-1 date and not closed on the D-1 date (open at the start of D0, or open at the end of the export)
    Lt['carried'] = (Lt.entry_day == 0) & ~(Lt.exit_date.notna() & (pd.to_datetime(Lt.exit_date) < Lt.expiry))
    Lt.to_pickle(p); return Lt


class CycleBook:
    """Unit-lot P&L matrices for one cycle under one ownership convention."""
    def __init__(self, und, expiry, conv, lots=None, m=None, ref_mode='bar_1529'):
        self.und, self.expiry, self.conv = und, expiry, conv
        m = m if m is not None else markets()[(und, expiry)]
        L = lots if lots is not None else ledger(conv)
        L = L[(L.und == und) & (L.expiry == expiry)].reset_index(drop=True)
        self.m, self.L = m, L
        n = len(m['grid']); self.n = n; self.lot = LOT[und]
        self.d1_last, self.d0_first = d_bounds(m)
        k = np.array([m['k2i'][(c, s)] for c, s in zip(L.cp, L.strike)], dtype=int)
        self.k = k
        mk = m['Cf'][k, :].astype(float) if len(k) else np.zeros((0, n))
        epx = L.entry_px.values.astype(float)
        mk = np.where(np.isfinite(mk), mk, epx[:, None])
        self.mark = mk
        self.sg = L.sgn.values.astype(float); self.epx = epx
        self.xpx = L.exit_px.values.astype(float)
        self.emi = L.entry_mi.values.astype(int)
        xmi = L.exit_mi.values.astype(int)
        self.xmi = np.where(np.isfinite(self.xpx), xmi, n + 10)        # open at the end of the export: never closes inside the grid
        self.carried = L.carried.values.astype(bool) if self.d1_last is not None else np.zeros(len(L), bool)
        self.new_d0 = (L.entry_day.values == 1)
        t = np.arange(n)[None, :]
        self.open = (t >= self.emi[:, None]) & (t < self.xmi[:, None])
        self.closed = t >= self.xmi[:, None]
        lot = self.lot
        self.U = np.where(self.open, self.sg[:, None] * (self.mark - self.epx[:, None]) * lot, 0.0)
        self.R = np.where(self.closed, (self.sg * (np.nan_to_num(self.xpx) - self.epx) * lot)[:, None], 0.0)
        # D-1 closing reference mark for carried lots
        if self.d1_last is not None:
            self.ref = np.where(self.carried, self.mark[:, self.d1_last], self.epx)
            if ref_mode == 'last_print':          # sensitivity: last D-1 option print including the 15:30-15:39 post-close bars
                lp = d1_last_prints(und, expiry, m['grid'][self.d1_last].normalize())
                alt = np.array([lp.get((c, s_), np.nan) for c, s_ in zip(L.cp, L.strike)])
                self.ref = np.where(self.carried & np.isfinite(alt), alt, self.ref)
        else:
            self.ref = self.epx.copy()

    # ---------- cumulative (from entry) ----------
    def cum(self, mask=None):
        mask = np.ones(len(self.L), bool) if mask is None else mask
        return (self.U[mask] + self.R[mask]).sum(axis=0)

    # ---------- expiry-day (D0 only) ----------
    def day_parts(self, mask=None):
        """(realised_D0, unrealised_D0) arrays over the grid; zero before the first D0 minute. Reference = D-1 close for carried lots."""
        n = self.n; z = np.zeros(n)
        if self.d0_first is None: return z, z
        mask = np.ones(len(self.L), bool) if mask is None else mask
        mask = mask & (self.carried | self.new_d0)
        t = np.arange(n)[None, :]; on_d0 = t >= self.d0_first
        ref = self.ref[mask][:, None]; sg = self.sg[mask][:, None]; lot = self.lot
        U = np.where(self.open[mask] & on_d0, sg * (self.mark[mask] - ref) * lot, 0.0)
        xd0 = (self.xmi[mask] >= self.d0_first)[:, None]
        R = np.where(self.closed[mask] & on_d0 & xd0, sg * (np.nan_to_num(self.xpx[mask])[:, None] - ref) * lot, 0.0)
        return R.sum(axis=0), U.sum(axis=0)

    def carried_held_day(self, shorts_only=False):
        """Convention-free 'held' path: the carried inventory frozen at the D-1 close and marked through D0 (ignores D0 trades)."""
        if self.d0_first is None or not self.carried.any(): return np.zeros(self.n)
        msk = self.carried & ((self.sg < 0) if shorts_only else True)
        t = np.arange(self.n); on = t >= self.d0_first
        return np.where(on, (self.sg[msk][:, None] * (self.mark[msk] - self.ref[msk][:, None]) * self.lot).sum(axis=0), 0.0)


_OPT = {}
def d1_last_prints(und, expiry, d1date):
    if 'o' not in _OPT: _OPT['o'] = pd.read_pickle(os.path.join(AN, '_cache', 'opt_candles.pkl'))
    o = _OPT['o']; x = o[(o.und == und) & (o.expiry == expiry) & (o.ts.dt.normalize() == d1date)].sort_values('ts')
    return x.groupby(['cp', 'strike']).c.last().to_dict()


def fills():
    from load import load_tagged
    d = load_tagged(); d['oid'] = d['tag']
    return d


def net_positions_at(d_cycle, t):
    """convention-free net lots per (cp, strike) from fills strictly before time t"""
    x = d_cycle[d_cycle.t < t]
    return x.groupby(['cp', 'strike']).sl.sum()


def minute_of(m, t):
    g = m['grid']; i = g.searchsorted(pd.Timestamp(t).floor('min'), side='left'); return int(min(i, len(g) - 1))


def order_minutes(o_cycle, m):
    """decision minute index (order-entry minute for body orders, tag time for tagged orders) on the cycle grid"""
    return np.array([minute_of(m, t) for t in o_cycle.t_dec_lo])


def first_cross(series, threshold, start, mask=None):
    """first index >= start with series <= threshold (threshold may be an array); None if never"""
    s = np.asarray(series, float); th = np.broadcast_to(np.asarray(threshold, float), s.shape)
    ok = np.zeros(len(s), bool); ok[start:] = True
    if mask is not None: ok &= mask
    hit = np.where(ok & (s <= th))[0]
    return int(hit[0]) if len(hit) else None
