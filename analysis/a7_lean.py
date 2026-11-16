"""Algo-7-style lean decomposition for Algo 8: minute book delta (Black-Scholes, own IV from Breeze closes) x index move = LEAN P&L;
everything else = premium/gamma/vega. Per cycle and per phase (D-1 intraday, overnight gap, D0).  python3 analysis/a7_lean.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy.special import ndtr
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
def bs_vec(cp_is_call, S, K, T, v):
    sq = v * np.sqrt(T); d1 = (np.log(S / K) + 0.5 * v * v * T) / sq; d2 = d1 - sq
    c = S * ndtr(d1) - K * ndtr(d2); p = K * ndtr(-d2) - S * ndtr(-d1)
    return np.where(cp_is_call, c, p), np.where(cp_is_call, ndtr(d1), ndtr(d1) - 1)
def iv_vec(cp_is_call, S, K, T, P, it=45):
    lo = np.full_like(P, 1e-3); hi = np.full_like(P, 5.0)
    for _ in range(it):
        mid = (lo + hi) / 2; pm, _ = bs_vec(cp_is_call, S, K, T, mid); up = pm > P
        hi = np.where(up, mid, hi); lo = np.where(up, lo, mid)
    return (lo + hi) / 2
if __name__ == '__main__':
    d = load_tagged(); ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
    A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
    rows = []
    for r in A.itertuples():
        e = pd.Timestamp(r.expiry); u = r.und; c = d[(d.und == u) & (d.expiry == e)].sort_values(['t', 'row'])
        days = sorted(c.date.unique()); lot = c.lot.iloc[0]
        s = ix[(ix.und == u) & ix.ts.dt.normalize().isin(days)].set_index('ts').close.sort_index()
        grid = s.index
        c = c.assign(m=c.t.dt.floor('min'), key=c.cp + '|' + c.strike.astype(int).astype(str))
        pos = c.pivot_table(index='m', columns='key', values='sl', aggfunc='sum').reindex(grid).fillna(0).cumsum()   # end-of-minute positions
        o = op[(op.und == u) & (op.expiry == e)].assign(key=lambda z: z.cp + '|' + z.strike.astype(int).astype(str))
        px = o.pivot_table(index='ts', columns='key', values='c', aggfunc='last').reindex(grid).ffill().reindex(columns=pos.columns)
        lastfill = c.groupby('key').px_fill.last()
        for k in px.columns[px.isna().all()]: px[k] = lastfill[k]
        px = px.ffill().bfill()
        K = np.array([float(k.split('|')[1]) for k in pos.columns]); isc = np.array([k.startswith('CE') for k in pos.columns])
        T = ((e + pd.Timedelta('15:30:00') - grid).total_seconds().values / (365 * 86400)).clip(min=1 / (365 * 24 * 60))[:, None]
        Sm = s.values[:, None]; P = px.values
        intr = np.where(isc, np.maximum(Sm - K, 0), np.maximum(K - Sm, 0))
        Pc = np.maximum(P, intr + 0.05)
        v = iv_vec(np.broadcast_to(isc, P.shape), np.broadcast_to(Sm, P.shape), np.broadcast_to(K, P.shape), np.broadcast_to(T, P.shape), Pc)
        _, delt = bs_vec(np.broadcast_to(isc, P.shape), Sm, K, T, v)
        book_delta = (pos.values * delt).sum(axis=1) * lot                    # units of index (rupees per 1 point)
        dS = np.diff(s.values); lean = book_delta[:-1] * dS
        day_of = grid.normalize()[1:]
        overnight = (grid.normalize()[1:] != grid.normalize()[:-1])
        cash = c.groupby('m').cash.sum().reindex(grid).fillna(0).cumsum().values
        mtm = cash + (pos.values * P).sum(axis=1) * lot
        rows.append(dict(und=u, expiry=e.date(), total=r.total_actual, mtm_end=mtm[-1], lean=lean.sum(), lean_overnight=lean[overnight].sum(),
                         lean_d1=lean[(~overnight) & (day_of == days[0])].sum() if len(days) == 2 else 0.0, lean_d0=lean[(~overnight) & (day_of == days[-1])].sum(),
                         mean_abs_delta=np.abs(book_delta).mean(), frac_short_delta=(book_delta < 0).mean(), index_move=s.values[-1] - s.values[0]))
    R = pd.DataFrame(rows); R['other'] = R.total - R.lean
    pd.set_option('display.width', 220)
    print(R.round(0).to_string(index=False))
    print(f"\nSUM: total {R.total.sum() / 1e5:.2f} L | lean {R.lean.sum() / 1e5:.2f} L (D-1 {R.lean_d1.sum() / 1e5:.2f}, overnight {R.lean_overnight.sum() / 1e5:.2f}, D0 {R.lean_d0.sum() / 1e5:.2f}) | everything else {R.other.sum() / 1e5:.2f} L")
    print(f"corr(session P&L, lean P&L) = {R.total.corr(R.lean):.2f}   corr(session P&L, everything else) = {R.total.corr(R.other):.2f}   [Algo 7: lean 0.71]")
    for u, g in R.groupby('und'): print(u, f"lean {g.lean.sum() / 1e5:.2f} L, other {g.other.sum() / 1e5:.2f} L, corr(total, lean) {g.total.corr(g.lean):.2f}")
    R.to_pickle(os.path.join(C, 'a8_lean.pkl'))
