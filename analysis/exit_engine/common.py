"""Shared utilities for exit-engine sections 4-10.
* Chronological whole-cycle splits (DEV / VAL / TEST by expiry).  TEST is never used for fitting or tuning in sections 4-9.
  Caveat (stated in the report): constants found in sections 1-3 and in the main FINDINGS (1.45-1.55x stop, clocks, salvage
  thresholds) were discovered on ALL 35 cycles, so TEST is contaminated for those hand-derived constants; it is untouched only
  for the models and thresholds fitted here.
* Order table (one row per order) with decision-time bounds:
    tagged orders (h_/s_/v_/m_): t_dec = microsecond tag time (exact), t_dec_lo = t_dec
    body orders (num): order entry is only stamped to the minute -> t_dec_lo = order minute start, t_dec = first fill (upper bound)
* Market matrices per cycle (Breeze 1-min OHLC, float32, cached).
* Unit-lot book replay from the actual fills.  Contract positions are fungible in the dump, so WHICH lot a buy-back closes is
  unobservable; it is a convention ('cheap' = cheapest entry first, 'fifo', 'lifo') and results are reported per convention.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN)
import numpy as np, pandas as pd
C = os.path.join(AN, '_cache'); RES = os.path.join(HERE, 'results'); os.makedirs(RES, exist_ok=True)
DEV_END, VAL_END = pd.Timestamp('2026-08-20'), pd.Timestamp('2026-09-22')
LOT = {'NIFTY': 65, 'SENSEX': 20}
SCHEDULED = ('5 cycle stop & liquidation', '7 expiry-day salvage', '6 clock-based exit (final flatten)', '10 manual / platform risk engine')

def split_of(expiry):
    e = pd.Timestamp(expiry)
    return 'DEV' if e <= DEV_END else ('VAL' if e <= VAL_END else 'TEST')

def orders():
    p = os.path.join(C, 'exit_orders.pkl')
    if os.path.exists(p): return pd.read_pickle(p)
    from load import load_tagged, RAW
    from exit_engine.ledger import decision_times
    raw = pd.read_csv(RAW, header=None, dtype=str, keep_default_na=False)
    d = load_tagged(); d['algoid'] = raw[144].values
    d['oid'] = d['tag']      # col 4 order ids are reused across days; col 163 is unique per order (== oid + date)
    d['om'] = pd.to_datetime(d.ts_order_txt, format='%m/%d/%Y %H:%M')
    d['L'] = np.where(d.side == 'Buy', d.px_order / 1.15, d.px_order / 0.85)
    v = d.tp == 'v_'; d.loc[v, 'L'] = np.where(d.side == 'Buy', d.px_order / 1.03, d.px_order / 0.85)[v]
    dt = decision_times(d)
    d = d.sort_values(['t', 'row'])
    o = d.groupby('oid').agg(t_fill=('t', 'min'), t_fill_last=('t', 'max'), om=('om', 'min'), und=('und', 'first'), expiry=('expiry', 'first'),
                             date=('date', 'first'), dte=('dte', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), side=('side', 'first'),
                             tp=('tp', 'first'), algoid=('algoid', 'first'), lots=('lots', 'sum'), L=('L', 'first'), n_fills=('t', 'size'),
                             vwap=('px_fill', lambda x: np.average(x, weights=d.loc[x.index, 'qty_fill'])))
    o['t_dec'] = dt.reindex(o.index).values
    tagged = o.tp != 'num'
    o['t_dec_lo'] = np.where(tagged, o.t_dec, o.om)
    o['t_dec_lo'] = pd.to_datetime(o.t_dec_lo).where(pd.to_datetime(o.t_dec_lo) <= o.t_dec, o.t_dec)
    o['dec_exact'] = tagged
    o = o.reset_index()
    X = pd.read_pickle(os.path.join(C, 'exit_taxonomy.pkl'))[['oid', 'label', 'closing_short', 'clock', 'episode', 'n_contracts', 'sides']]
    o = o.merge(X, on='oid', how='left'); o['label'] = o.label.fillna('open')
    o['split'] = o.expiry.map(split_of); o['lots'] = o.lots.round().astype(int)
    o = o.sort_values(['t_dec', 'oid']).reset_index(drop=True)
    o.to_pickle(p); return o

def markets():
    """dict (und, expiry) -> dict(grid, S, day(0=D-1,1=D0), O,H,L,C (raw, nan where no trade), Cf (ffill), keys, k2i, atr1(points, causal), ind)"""
    p = os.path.join(C, 'exit_mkt.pkl')
    if os.path.exists(p): return pd.read_pickle(p)
    o = orders()
    ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
    I = pd.read_pickle(os.path.join(C, 'indicators_index.pkl')).set_index(['und', 'm'])
    out = {}
    for (u, e), g in o.groupby(['und', 'expiry']):
        days = sorted(g.date.unique())
        s = ix[(ix.und == u) & ix.ts.dt.normalize().isin(days)].set_index('ts').sort_index()
        grid = s.index; n = len(grid); gpos = {t: i for i, t in enumerate(grid)}
        oc = op[(op.und == u) & (op.expiry == e) & op.ts.isin(grid)]
        keys = sorted(set(zip(oc.cp, oc.strike)) | set(zip(g.cp, g.strike))); k2i = {k: i for i, k in enumerate(keys)}
        M = {c: np.full((len(keys), n), np.nan, np.float32) for c in 'ohlc'}
        ki = np.array([k2i[(a, b)] for a, b in zip(oc.cp, oc.strike)]); ti = np.array([gpos[t] for t in oc.ts])
        for c in 'ohlc': M[c][ki, ti] = oc[c].values
        Cf = pd.DataFrame(M['c'].T).ffill().values.T.astype(np.float32)
        ind = I.reindex([(u, t) for t in grid])
        S = s.close.values
        out[(u, e)] = dict(und=u, expiry=e, grid=grid, S=S, Sh=s.high.values, Sl=s.low.values, day=(grid.normalize() == e).astype(int),
                           O=M['o'], H=M['h'], L=M['l'], C=M['c'], Cf=Cf, keys=keys, k2i=k2i,
                           atr1=ind['1m_atr14_bp'].values * S / 1e4, atr5=ind['5m_atr14_bp'].values * S / 1e4,
                           rv1=ind['1m_rv20_bp'].values, day_range_bp=ind['day_range_bp'].values if 'day_range_bp' in ind else np.full(n, np.nan))
    pd.to_pickle(out, p); return out

def minute_index(grid, t):
    """index of the minute containing t (clipped to the grid)"""
    i = grid.searchsorted(pd.Timestamp(t).floor('min'), side='left')
    return int(min(i, len(grid) - 1))

def replay_book(conv='cheap'):
    """Unit-lot book from the actual orders (tag-agnostic per contract).  Returns DataFrame of unit lots:
    und, expiry, cp, strike, sgn(-1 short / +1 long), entry_oid, entry_tp, entry_t, entry_mi, entry_px, entry_day,
    exit_oid, exit_t, exit_mi, exit_px, exit_label, carried (entered D-1 and open at D0 start), reentry (contract had a buy-back before entry)."""
    p = os.path.join(C, f'exit_lots_{conv}.pkl')
    if os.path.exists(p): return pd.read_pickle(p)
    o = orders(); mk = markets(); rows = []
    for (u, e), g in o.groupby(['und', 'expiry']):
        m = mk[(u, e)]; grid = m['grid']; d0_start = grid[m['day'].argmax()] if m['day'].any() else None
        book = {}; had_bb = set()
        for r in g.itertuples():
            k = (r.cp, r.strike); L_ = book.setdefault(k, []); n = int(r.lots); sg = 1 if r.side == 'Buy' else -1
            pos = sum(x['sgn'] for x in L_); mi = minute_index(grid, r.t_dec_lo)   # decision minute (order-entry minute for body orders)
            if (sg > 0 and pos < 0) or (sg < 0 and pos > 0):
                if conv == 'cheap': L_.sort(key=lambda x: (x['entry_px'] if pos < 0 else -x['entry_px'], x['entry_t']))
                elif conv == 'fifo': L_.sort(key=lambda x: x['entry_t'])
                elif conv == 'lifo': L_.sort(key=lambda x: x['entry_t'], reverse=True)
                take = min(n, len(L_))
                for x in L_[:take]:
                    x.update(exit_oid=r.oid, exit_t=r.t_dec, exit_mi=mi, exit_px=r.vwap, exit_label=r.label, exit_tp=r.tp); rows.append(x)
                del L_[:take]; n -= take
                if pos < 0: had_bb.add(k)
            for _ in range(n):
                L_.append(dict(und=u, expiry=e, cp=r.cp, strike=r.strike, sgn=sg, entry_oid=r.oid, entry_tp=r.tp, entry_t=r.t_dec, entry_mi=mi,
                               entry_px=r.vwap, entry_day=int(m['day'][mi]), reentry=k in had_bb))
        for k, L_ in book.items():
            for x in L_: x.update(exit_oid=None, exit_t=pd.NaT, exit_mi=len(grid) - 1, exit_px=np.nan, exit_label='expired/open', exit_tp=None); rows.append(x)
    Lt = pd.DataFrame(rows)
    Lt['split'] = Lt.expiry.map(split_of)
    # carried = entered on D-1 and still open at the first D0 minute (depends on the closing convention)
    d0i = {k: (int(v['day'].argmax()) if v['day'].any() else 10 ** 9) for k, v in mk.items()}
    Lt['d0_mi'] = [d0i[(u, e)] for u, e in zip(Lt.und, Lt.expiry)]
    Lt['carried'] = (Lt.entry_day == 0) & (Lt.exit_mi >= Lt.d0_mi)
    Lt.to_pickle(p); return Lt

def cycle_stop_minute():
    o = orders(); s = o[o.tp == 's_'].groupby(['und', 'expiry']).t_dec.min()
    mk = markets(); return {k: minute_index(mk[k]['grid'], t) for k, t in s.items()}

if __name__ == '__main__':
    o = orders(); mk = markets()
    print('orders', len(o), '| cycles', len(mk), '| split cycles:', o.groupby('split').expiry.nunique().to_dict())
    for conv in ('cheap', 'fifo', 'lifo'):
        Lt = replay_book(conv); sh = Lt[Lt.sgn < 0]
        print(conv, 'short unit lots', len(sh), '| carried', int(sh.carried.sum()), '| open at end', int(sh.exit_oid.isna().sum()))
