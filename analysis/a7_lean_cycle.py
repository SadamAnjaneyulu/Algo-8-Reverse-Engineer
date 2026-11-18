"""Cycle-level directional test: book delta measured BEFORE the move vs the subsequent index move.
Checkpoints: D-1 13:00, D-1 close, D0 10:00. Permutation p-value (shuffle moves across cycles).  python3 analysis/a7_lean_cycle.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
from a7_lean import bs_vec, iv_vec
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged(); ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
rows = []
for r in A.itertuples():
    e = pd.Timestamp(r.expiry); u = r.und; c = d[(d.und == u) & (d.expiry == e)].sort_values(['t', 'row'])
    days = sorted(c.date.unique()); lot = c.lot.iloc[0]
    s = ix[(ix.und == u) & ix.ts.dt.normalize().isin(days)].set_index('ts').close.sort_index()
    Send = s.iloc[-1]
    for name, ts in [('D-1 13:00', days[0] + pd.Timedelta('13:00:00')), ('D-1 close', days[0] + pd.Timedelta('15:28:00')), ('D0 10:00', days[-1] + pd.Timedelta('10:00:00'))]:
        if len(days) < 2 and name.startswith('D-1'): continue
        if ts not in s.index: continue
        pre = c[c.t < ts]; pos = pre.groupby(['cp', 'strike']).sl.sum(); pos = pos[pos.abs() > 1e-9]
        if pos.empty: continue
        o = op[(op.und == u) & (op.expiry == e) & (op.ts == ts - pd.Timedelta(minutes=1))].set_index(['cp', 'strike']).c
        S = s[ts]; T = max((e + pd.Timedelta('15:30:00') - ts).total_seconds() / (365 * 86400), 1 / 525600)
        dl = 0.0
        for (cp, K), q in pos.items():
            p = o.get((cp, K), np.nan)
            if not np.isfinite(p): p = pre[(pre.cp == cp) & (pre.strike == K)].px_fill.iloc[-1]
            intr = max(S - K, 0) if cp == 'CE' else max(K - S, 0)
            isc = np.array([cp == 'CE']); v = iv_vec(isc, np.array([S]), np.array([K]), np.array([T]), np.array([max(p, intr + 0.05)]))
            _, de = bs_vec(isc, np.array([S]), np.array([K]), np.array([T]), v); dl += q * de[0]
        rows.append(dict(und=u, expiry=e.date(), checkpoint=name, delta_lots=dl, move_after_bp=(Send - S) / S * 1e4, lean_after=dl * lot * (Send - S)))
R = pd.DataFrame(rows)
rng = np.random.default_rng(0)
pd.set_option('display.width', 200)
for cp, g in R.groupby('checkpoint'):
    agree = (np.sign(g.delta_lots) == np.sign(g.move_after_bp)).mean()
    rho = np.corrcoef(g.delta_lots, g.move_after_bp)[0, 1]
    perm = np.array([np.corrcoef(g.delta_lots, rng.permutation(g.move_after_bp.values))[0, 1] for _ in range(5000)])
    print(f'{cp:10s}: n={len(g)} | book short delta in {(g.delta_lots < 0).mean():.0%} of cycles | sign agreement with later move {agree:.0%} | '
          f'corr(delta, later move) {rho:+.2f} (perm p={(np.abs(perm) >= abs(rho)).mean():.3f}) | lean-after sum Rs {g.lean_after.sum() / 1e5:.1f} L')
mv = R[R.checkpoint == 'D-1 close'].move_after_bp
print(f'\nmarket over these cycles (D-1 close -> expiry close): mean {mv.mean():+.1f} bp, down in {(mv < 0).mean():.0%} of cycles')
R.to_pickle(os.path.join(C, 'a8_lean_cycle.pkl'))
