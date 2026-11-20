"""H9 baselines for the level-control claims. (a) shuffled-gap null for per-order and per-wave exactness: replace each order's S-L by that of a random other order of the same und/day/side (seed 0), 200 repeats.
(b) cross-right null for quiet-time balance: S of one right vs L of the OTHER right at the same sample time. Outputs outputs/bh_h9_baselines.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
rng = np.random.default_rng(0)
G = pd.read_csv(f'{OUT}/bh_h3c_wing_orders.csv', dtype={'tag': str}); G = G[G.complete]; res = {}
def shuf(df, gapcol, valcol, keys, reps=200):
    out = []
    for _ in range(reps):
        h = 0; n = 0
        for _, g in df.groupby(keys):
            gp = rng.permutation(g[gapcol].values); h += (g[valcol].values == gp).sum(); n += len(g)
        out.append(h / n)
    return np.mean(out), np.quantile(out, .975)
res['order_exact_real'] = (G.sw == G.gap_before).mean(); res['order_exact_null_mean'], res['order_exact_null_p975'] = shuf(G, 'gap_before', 'sw', ['und', 'dayno', 'side'])
W = pd.read_csv(f'{OUT}/bh_h8_waves.csv'); W = W[W.complete]; res['wave_exact_real'] = (W.sum_signed == W.gap_at_start).mean(); res['wave_exact_null_mean'], res['wave_exact_null_p975'] = shuf(W, 'gap_at_start', 'sum_signed', ['und', 'dayno', 'side'])
# per day/side
for (d, s), g in G.groupby(['dayno', 'side']): m, p = shuf(g, 'gap_before', 'sw', ['und']); res[f'order_null_{["D-1","D0"][d]}_{s}'] = m
# (b)
O = order_table(); bk = Book(O); Q = pd.read_csv(f'{OUT}/bh_h3b_quiet.csv'); eq = 0; eqx = 0; n = 0
for r in Q.itertuples():
    other = 'PE' if r.cp == 'CE' else 'CE'
    if (r.und, r.expiry, other) not in bk.d: continue
    S, Lg, _ = bk.state(r.und, r.expiry, other, r.T, inclusive=True); n += 1; eqx += (r.S == Lg)
res['quiet_balance_real'] = (Q.gap_all == 0).mean(); res['quiet_cross_right_null'] = eqx / n
pd.Series(res).to_csv(f'{OUT}/bh_h9_baselines.csv', header=['value']); print(pd.Series(res).round(4).to_string())
