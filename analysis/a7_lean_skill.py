"""Is Algo 8's lean ACTIVE skill or PASSIVE short-gamma mechanics?  python3 analysis/a7_lean_skill.py
(a) lean of the PASSIVE book: identical body sales + wings, never managed (held to expiry; no buy-backs, stops, rolls, lump).
(b) forecasting: does the actual book delta predict the next 15/60-min and overnight index move better than the passive book delta?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
from a7_lean import bs_vec, iv_vec
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged(); ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
rows, fc = [], []
for r in A.itertuples():
    e = pd.Timestamp(r.expiry); u = r.und; c = d[(d.und == u) & (d.expiry == e)].sort_values(['t', 'row'])
    days = sorted(c.date.unique()); lot = c.lot.iloc[0]
    s = ix[(ix.und == u) & ix.ts.dt.normalize().isin(days)].set_index('ts').close.sort_index(); grid = s.index
    c = c.assign(m=c.t.dt.floor('min'), key=c.cp + '|' + c.strike.astype(int).astype(str))
    keys = sorted(c.key.unique())
    act = c.pivot_table(index='m', columns='key', values='sl', aggfunc='sum').reindex(grid).fillna(0).cumsum().reindex(columns=keys, fill_value=0)
    passive_fills = c[((c.tp == 'num') & (c.side == 'Sell')) | ((c.tp == 'h_') & (c.side == 'Buy'))]
    pas = passive_fills.pivot_table(index='m', columns='key', values='sl', aggfunc='sum').reindex(grid).fillna(0).cumsum().reindex(columns=keys, fill_value=0)
    o = op[(op.und == u) & (op.expiry == e)].assign(key=lambda z: z.cp + '|' + z.strike.astype(int).astype(str))
    px = o.pivot_table(index='ts', columns='key', values='c', aggfunc='last').reindex(grid).ffill().reindex(columns=keys)
    lastfill = c.groupby('key').px_fill.last()
    for k in px.columns[px.isna().all()]: px[k] = lastfill[k]
    px = px.ffill().bfill()
    K = np.array([float(k.split('|')[1]) for k in keys]); isc = np.array([k.startswith('CE') for k in keys])
    T = ((e + pd.Timedelta('15:30:00') - grid).total_seconds().values / (365 * 86400)).clip(min=1 / 525600)[:, None]
    Sm = s.values[:, None]; P = px.values
    intr = np.where(isc, np.maximum(Sm - K, 0), np.maximum(K - Sm, 0)); Pc = np.maximum(P, intr + 0.05)
    shp = P.shape
    v = iv_vec(np.broadcast_to(isc, shp), np.broadcast_to(Sm, shp), np.broadcast_to(K, shp), np.broadcast_to(T, shp), Pc)
    _, de = bs_vec(np.broadcast_to(isc, shp), Sm, K, T, v)
    dA = (act.values * de).sum(1) * lot; dP = (pas.values * de).sum(1) * lot
    dS = np.diff(s.values)
    rows.append(dict(und=u, expiry=e.date(), total=r.total_actual, lean_actual=(dA[:-1] * dS).sum(), lean_passive=(dP[:-1] * dS).sum(),
                     lean_active_part=((dA - dP)[:-1] * dS).sum()))
    for h in (15, 60):
        fwd = pd.Series(s.values, index=grid).shift(-h).values - s.values
        ok = np.isfinite(fwd) & (grid.normalize() == pd.DatetimeIndex(pd.Series(grid).shift(-h)).normalize())
        fc.append(pd.DataFrame(dict(und=u, expiry=e.date(), h=h, dA=dA[ok], dP=dP[ok], dX=(dA - dP)[ok], fwd=fwd[ok])))
R = pd.DataFrame(rows); F = pd.concat(fc)
pd.set_option('display.width', 200)
print(f"SUM (Rs lakh): lean actual {R.lean_actual.sum() / 1e5:.2f} | lean of PASSIVE book (same sales, no management) {R.lean_passive.sum() / 1e5:.2f} | ACTIVE part (actual - passive delta) {R.lean_active_part.sum() / 1e5:.2f}")
for u, g in R.groupby('und'): print(f'  {u}: actual {g.lean_actual.sum() / 1e5:.2f}  passive {g.lean_passive.sum() / 1e5:.2f}  active {g.lean_active_part.sum() / 1e5:.2f}  | cycles active part > 0: {(g.lean_active_part > 0).sum()}/{len(g)}')
rng = np.random.default_rng(0); x = R.lean_active_part.values
bs = [rng.choice(x, len(x)).mean() for _ in range(4000)]
print(f'active-lean mean per cycle Rs {x.mean():,.0f}, 95% CI [{np.percentile(bs, 2.5):,.0f}, {np.percentile(bs, 97.5):,.0f}]')
print('\nForecast check: corr(delta, forward index move) [positive = delta points the right way]')
for h, g in F.groupby('h'):
    print(f'  h={h:3d}m  actual book {np.corrcoef(np.sign(g.dA), g.fwd)[0, 1]:+.3f} | passive book {np.corrcoef(np.sign(g.dP), g.fwd)[0, 1]:+.3f} | active part {np.corrcoef(np.sign(g.dX), g.fwd)[0, 1]:+.3f}')
R.to_pickle(os.path.join(C, 'a8_lean_skill.pkl'))
