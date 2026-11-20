"""Robustness of the move-trigger result: by right (calls into falls vs puts into rises), by underlying, and excluding the last 15 minutes (closing-minute spikes). D-1 and D0. Output outputs/bl_move_robust.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
P = pd.read_csv(f'{OUT}/bl_move_panel.csv'); rng = np.random.default_rng(2)
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
def boot(Q, f, n=200):
    x = Q[f].values.astype(float); y = Q.ep.values; cy = (Q.und + Q.expiry).values; ucy = np.unique(cy); idx = {c: np.where(cy == c)[0] for c in ucy}; a = auc(x, y); bs = []
    for _ in range(n): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bs.append(auc(x[ii], y[ii]))
    bs = np.array([b for b in bs if b == b]); return a, np.quantile(bs, .025), np.quantile(bs, .975)
rows = []
for day in ('D-1', 'D0'):
    for nm, Q in (('all', P[P.day == day]), ('CE only (calls into falls)', P[(P.day == day) & (P.cp == 'CE')]), ('PE only (puts into rises)', P[(P.day == day) & (P.cp == 'PE')]), ('NIFTY', P[(P.day == day) & (P.und == 'NIFTY')]), ('SENSEX', P[(P.day == day) & (P.und == 'SENSEX')]), ('excluding last 15 min (j<360)', P[(P.day == day) & (P.j < 360)]), ('excluding first 90 min (j>=90)', P[(P.day == day) & (P.j >= 90)])):
        for f in ('fav30', 'own_ratio', 'other_ratio'):
            a, lo, hi = boot(Q, f); rows.append((day, nm, f, len(Q), int(Q.ep.sum()), a, lo, hi))
R = pd.DataFrame(rows, columns=['day', 'subset', 'feature', 'minutes', 'episode_starts', 'AUC', 'lo', 'hi']).round(3); R.to_csv(f'{OUT}/bl_move_robust.csv', index=False); print(R[R.feature == 'fav30'].to_string(index=False))
# dose-response by right, D-1, excluding last 15 min
Q = P[(P.day == 'D-1') & (P.j < 360)]; base = Q.ep.mean()
for cp in ('CE', 'PE'):
    q = Q[Q.cp == cp]; t = q.groupby(pd.cut(q.fav30, [-100, 0, .1, .2, .35, 100])).ep.agg(['size', 'sum']); t['rate_per_1000'] = (t['sum'] / t['size'] * 1000).round(1); print('\nD-1', cp, '(j<360) episode-start rate by favourable 30-min move %:'); print(t.to_string())
