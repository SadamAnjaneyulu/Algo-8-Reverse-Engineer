"""Tracker study: group reactive pairs placed within 5 s of each other into 'fires' (one fire can place 2-3 pair-lots). Output bl_trk_fires.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); r = Pr[Pr.reactive].sort_values(['und', 'expiry', 'te']); rows = []
for (u, e), g in r.groupby(['und', 'expiry']):
    t = g.te.values; k = g.strike.values; grp = np.r_[0, np.cumsum(np.diff(t) > 5)]
    for gi in np.unique(grp): m = grp == gi; rows.append(dict(und=u, expiry=e, t=t[m][0], pairs=int(m.sum()), strikes=len(set(k[m])), span=t[m][-1] - t[m][0]))
F = pd.DataFrame(rows); F['gap_prev_min'] = F.groupby(['und', 'expiry']).t.diff() / 60; F.to_csv(f'{OUT}/bl_trk_fires.csv', index=False)
print(len(F), 'fires from', len(r), 'pairs', F.pairs.value_counts().sort_index().to_dict(), 'lots-vs-gap spearman', [round(float(v), 3) for v in spearmanr(F.pairs[F.gap_prev_min.notna()], F.gap_prev_min.dropna())])
