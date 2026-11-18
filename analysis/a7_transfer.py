"""Transfer Algo 7 findings to Algo 8: (1) delta-target strike selection for body sells (BS delta from prev-minute closes, own IV);
(2) share of body orders that add delta in the direction of the last 5-min index move (Algo 7: 58.8%).  python3 analysis/a7_transfer.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
from a7_lean import bs_vec, iv_vec
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
f = pd.read_pickle(os.path.join(C, 'p4_orders_cons.pkl')); f['K0'] = (f.prev_close / f.step).round() * f.step
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
pc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).set_index(['und', 'expiry', 'cp', 'm', 'strike']).c.sort_index()
sec = (f.t - f.t.dt.normalize() - pd.Timedelta('09:15:00')).dt.total_seconds(); ph = sec % 900
f['clock'] = np.where((ph >= 55) & (ph < 180), 'A', np.where((ph >= 13 * 60 + 45) | (ph < 15), 'B', np.where(ph < 55, 'A0', 'unchained')))
rows = []
for r in f.itertuples():
    S = r.prev_close; T = max((r.expiry + pd.Timedelta('15:30:00') - r.m).total_seconds() / (365 * 86400), 1 / 525600)
    cand = []
    for j in range(-4, 5):
        K = r.K0 + j * r.step; p = pc.get((r.und, r.expiry, r.cp, r.m, K), np.nan)
        if not np.isfinite(p): continue
        isc = np.array([r.cp == 'CE']); intr = max(S - K, 0) if r.cp == 'CE' else max(K - S, 0)
        v = iv_vec(isc, np.array([S]), np.array([K]), np.array([T]), np.array([max(p, intr + 0.05)]))
        _, de = bs_vec(isc, np.array([S]), np.array([K]), np.array([T]), v); cand.append((K, abs(de[0])))
    if len(cand) < 3: continue
    chosen = [a for K, a in cand if K == r.strike]
    rows.append(dict(oid=r.oid, day=r.day, clock=r.clock, cp=r.cp, und=r.und, strike=r.strike, K0=r.K0, cand=cand, d_chosen=chosen[0] if chosen else np.nan))
X = pd.DataFrame(rows).dropna(subset=['d_chosen'])
pd.set_option('display.width', 200)
print('|delta| of the SOLD strike (quantiles) by clock & side:')
print(X.groupby(['clock', 'cp']).d_chosen.quantile([.1, .25, .5, .75, .9]).unstack().round(2).to_string())
print('\nrule accuracy: pick candidate with |delta| closest to target (per side), vs nearest-ATM')
for tgt in [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
    X['pred'] = [min(c, key=lambda z: abs(z[1] - tgt))[0] for c in X.cand]
    acc = X.assign(ok=X.pred == X.strike).groupby('clock').ok.mean().round(3).to_dict()
    print(f'  target {tgt:.2f}: overall {(X.pred == X.strike).mean():.3f}  by clock {acc}')
print(f"  nearest-ATM (index prev close): overall {(X.K0 == X.strike).mean():.3f}  by clock {X.assign(ok=X.K0 == X.strike).groupby('clock').ok.mean().round(3).to_dict()}")
# best per-side target
for (clk, cp), g in X.groupby(['clock', 'cp']):
    best = max(np.arange(0.30, 0.71, 0.025), key=lambda t: np.mean([min(c, key=lambda z: abs(z[1] - t))[0] == k for c, k in zip(g.cand, g.strike)]))
    accb = np.mean([min(c, key=lambda z: abs(z[1] - best))[0] == k for c, k in zip(g.cand, g.strike)])
    print(f'  best delta target {clk:9s} {cp}: {best:.3f} -> accuracy {accb:.3f} (ATM {np.mean(g.K0 == g.strike):.3f}, n={len(g)})')
# (2) momentum rebalancing share
d = load_tagged(); ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')).set_index(['und', 'ts']).close.sort_index()
b = d[(d.tp == 'num') & (d.px_fill >= 5)].groupby('oid').first().reset_index()
b['m'] = b.t.dt.floor('min')
mv = np.array([ix.get((u, m - pd.Timedelta(minutes=1)), np.nan) - ix.get((u, m - pd.Timedelta(minutes=6)), np.nan) for u, m in zip(b.und, b.m)])
# order delta sign: Sell CE -, Sell PE +, Buy CE +, Buy PE -
od = np.where(b.cp == 'CE', -1, 1) * np.where(b.side == 'Sell', 1, -1)
ok = np.isfinite(mv) & (mv != 0)
same = (np.sign(mv[ok]) == od[ok])
print(f'\nshare of body orders adding delta in the direction of the last 5-min move: {same.mean():.3f} (n={ok.sum()})  [Algo 7: 0.588]')
b = b[ok].assign(same=same, day=np.where(b[ok].dte >= 1, 'D-1', 'D0'))
print(b.groupby(['day', 'side']).same.mean().round(3).to_dict())
