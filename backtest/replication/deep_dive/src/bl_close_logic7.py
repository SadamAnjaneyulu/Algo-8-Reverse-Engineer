"""Buy-back study, step 8: is the RIGHT (CE or PE) chosen for a buy-back the one with more short lots (a balance-control hypothesis, by analogy with the hedge)? Compare with the lot-proportional chance expectation (right drawn in proportion to its short lots).
Modes by cheapest-open-entry ratio at the order: stop-like (>=1.5), middle (1.2-1.5), sub-1.2. Output bl_summary_close7.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); F = pd.read_csv(f'{OUT}/bl_close_orders_flags.csv'); R = {}; rng = np.random.default_rng(0)
for day in ('D-1', 'D0'):
    d = F[F.day == day].copy(); rows = []
    for (u, e), g in O[O.dayno == (0 if day == 'D-1' else 1)].groupby(['und', 'expiry']):
        g = g.sort_values(['te', 'row']); S = {cp: (g[g.cp == cp].te.values, g[g.cp == cp].S_after.values) for cp in ('CE', 'PE')}
        for r in d[(d.und == u) & (d.expiry == e)].itertuples():
            def at(cp): t, s = S[cp]; i = np.searchsorted(t, r.te, side='left') - 1; return s[i] if i >= 0 else 0
            rows.append((r.tag, at(r.cp), at('PE' if r.cp == 'CE' else 'CE')))
    B = pd.DataFrame(rows, columns=['tag', 'S_own', 'S_oth']); B['tag'] = B.tag.astype(d.tag.dtype); d = d.merge(B, on='tag').drop_duplicates('tag'); d['mode'] = np.where(d.r_low >= 1.5, 'stop-like (>=1.5x)', np.where(d.r_low >= 1.2, 'middle (1.2-1.5x)', 'sub-1.2x'))
    for m, x in d.groupby('mode'):
        y = x[x.S_own != x.S_oth]; obs = float((y.S_own > y.S_oth).mean()); exp = float((np.maximum(y.S_own, y.S_oth) / (y.S_own + y.S_oth)).mean()); g = (y.und + y.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; h = (y.S_own > y.S_oth).values.astype(float)
        bs = [h[np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))])].mean() for _ in range(300)]
        R[f'{day}|{m}'] = dict(n=len(y), own_larger=obs, lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975)), expected_if_lot_proportional=exp)
        print(f'{day} {m:20s} n={len(y):5d} own side larger {obs:.3f} (CI {np.quantile(bs, .025):.3f}-{np.quantile(bs, .975):.3f}); expected under lot-proportional choice {exp:.3f}')
rec('close7', R)
