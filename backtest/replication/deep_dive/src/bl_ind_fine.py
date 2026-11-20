"""Indicator search step 4: is the channel length N = 60 special? Fine grid of N for the Donchian position (live spot vs the high/low of the previous N completed closes): activation AUC with paired cluster bootstrap vs N = 60, and direction hit. Output bl_ind_fine.csv, bl_summary_ind3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(621); R = {}; T = pd.read_pickle(f'{OUT}/bl_act_table.pkl.gz')[['cid', 'und', 'expiry', 'y', 'j', 'strike', 'atm', 'step', 'live']].reset_index(drop=True); ch = Chain(); NS = [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90]; P = {N: np.full(len(T), np.nan) for N in NS}
for (u, e), idx in T.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; sub = T.loc[idx]
    for N in NS: P[N][idx] = [((l - sp[max(j - 1 - N + 1, 0): j].min()) / max(sp[max(j - 1 - N + 1, 0): j].max() - sp[max(j - 1 - N + 1, 0): j].min(), 1e-6) - 0.5) for l, j in zip(sub.live.values, sub.j.values)]
y = T.y.values; ev = y == 1; cid = T.cid.values; ucy = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in ucy}
def auc(x, y_): n1 = y_.sum(); n0 = len(y_) - n1; r = stats.rankdata(x); return (r[y_ == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
bs = [np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(300)]; base = {N: [auc(np.abs(P[N][ii]), y[ii]) for ii in bs] for N in NS}; rows = []
for N in NS: a = auc(np.abs(P[N]), y); d = np.array(base[N]) - np.array(base[60]); rows.append((N, a, np.quantile(base[N], .025), np.quantile(base[N], .975), np.quantile(d, .025), np.quantile(d, .975), float(((T.atm.values + np.sign(P[N]) * T.step.values) == T.strike.values)[ev].mean())))
F = pd.DataFrame(rows, columns=['N_min', 'AUC', 'lo', 'hi', 'diff_vs_60_lo', 'diff_vs_60_hi', 'direction_hit']); F.round(4).to_csv(f'{OUT}/bl_ind_fine.csv', index=False); print(F.round(3).to_string(index=False)); R['fine'] = F.round(4).to_dict('list'); R['within_ci_of_60'] = [int(n) for n, lo, hi in zip(F.N_min, F.diff_vs_60_lo, F.diff_vs_60_hi) if lo <= 0 <= hi]
rec('ind3', R)
