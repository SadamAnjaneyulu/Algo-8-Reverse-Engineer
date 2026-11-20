"""Buy-back study, step 3b: pre-registered decision rule for a COMBINED trigger -- on strike-minutes where BOTH legs were bought back, does the max leg ratio beat each single-leg ratio with a cluster-bootstrap CI that excludes 0? D-1. Output bl_summary_close2b.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(5)
def auc(x, y):
    m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); Q = P[(P.day == 'D-1') & (P.cp == 'CE') & (P.o_n_open > 0) & P.o_r_avg.notna()].reset_index(drop=True)
Q['r_ce'] = Q.r_avg; Q['r_pe'] = Q.o_r_avg; Q['r_max'] = Q[['r_ce', 'r_pe']].max(axis=1); Q['both'] = ((Q.bb_lots > 0) & (Q.o_bb_lots > 0)).astype(int)
y = Q.both.values; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; out = {}
for v in ('r_ce', 'r_pe'):
    d = []
    for _ in range(400):
        ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))])
        if y[ii].sum() < 3: continue
        d.append(auc(Q.r_max.values[ii], y[ii]) - auc(Q[v].values[ii], y[ii]))
    out[v] = (auc(Q.r_max.values, y) - auc(Q[v].values, y), *np.quantile(d, [.025, .975])); print(f'AUC(r_max) - AUC({v}) for both-legs events: {out[v][0]:+.3f} CI {out[v][1]:+.3f}..{out[v][2]:+.3f}')
json.dump({k: [float(x) for x in v] for k, v in out.items()}, open(f'{OUT}/bl_summary_close2b.json', 'w'))
