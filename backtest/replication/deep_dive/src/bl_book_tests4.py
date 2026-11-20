"""Capital-loss trigger study, part 4 (decision rule (i) and (iii)): shape of the book-P&L-change effect on D-1 residual sub-1.2x buy-backs.
(a) cycle-minute hazard by bin of dB5 / dB15 / dB30 / DD (lakh and % of C=2 crore), target B (residual), A (all sub-1.2x), S (stop-like); adjacent-bin steps;
(b) chronological-halves replication (cycles split at the median expiry date); (c) the same with minutes that had NO stop-like buy-back in the previous 15 minutes;
(d) own-right vs other-right 15-min P&L change (contract-minute AUC, target B). Outputs bl_book_shape_*.csv, bl_summary_book4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
LAKH = 1e5; C = 2e7; rng = np.random.default_rng(41); R = {}
Cm = pd.read_csv(f'{OUT}/bl_book_cycle_minutes.csv.gz'); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz')
# previous-15-min stop-like activity per cycle-minute
st = ev[ev.klass == 'stop-like (>=1.5x)'].groupby(['und', 'expiry', 'day', 'j']).size().rename('s').reset_index(); Cm = Cm.merge(st, on=['und', 'expiry', 'day', 'j'], how='left').fillna({'s': 0}); Cm = Cm.sort_values(['und', 'expiry', 'day', 'j'])
Cm['stop_prev15'] = Cm.groupby(['und', 'expiry', 'day']).s.transform(lambda x: x.shift(1).rolling(15, min_periods=1).sum()).fillna(0)
edges = {'dB15': [-1e9, -1.0, -0.5, -0.25, -0.1, 0, 0.1, 0.25, 1e9], 'dB5': [-1e9, -0.5, -0.25, -0.1, -0.05, 0, 0.05, 0.1, 1e9], 'dB30': [-1e9, -1.0, -0.5, -0.25, -0.1, 0, 0.1, 0.25, 1e9], 'DD': [-1, 1e-4, 0.1, 0.25, 0.5, 1.0, 1e9]}
yrs = sorted(Cm.expiry.unique()); med = yrs[len(yrs) // 2]; Cm['half'] = np.where(Cm.expiry < med, 'first half', 'second half'); R['split_expiry'] = med
def hz(Q, v, tgt):
    x = Q[v] / LAKH; t = Q.groupby(pd.cut(x, edges[v]), observed=False)[tgt].agg(n='size', ev=lambda s: (s > 0).sum()); t['per1000'] = t.ev / t.n * 1000; return t
rows = []
for day in ('D-1', 'D0'):
    for sub, Q0 in (('all', Cm[Cm.day == day]), ('first half', Cm[(Cm.day == day) & (Cm.half == 'first half')]), ('second half', Cm[(Cm.day == day) & (Cm.half == 'second half')]), ('no stop-like in prev 15 min', Cm[(Cm.day == day) & (Cm.stop_prev15 == 0)])):
        for v in edges:
            Q = Q0[Q0[v].notna()]
            for tgt in ('B', 'A', 'S'):
                t = hz(Q, v, tgt).reset_index().rename(columns={v: 'bin'}); t.insert(0, 'target', tgt); t.insert(0, 'var', v); t.insert(0, 'subset', sub); t.insert(0, 'day', day); rows.append(t)
H = pd.concat(rows).assign(bin=lambda d: d['bin'].astype(str)); H.to_csv(f'{OUT}/bl_book_shape.csv', index=False)
for sub in ('all', 'first half', 'second half', 'no stop-like in prev 15 min'):
    for v in ('dB15', 'DD'):
        h = H[(H.day == 'D-1') & (H.subset == sub) & (H['var'] == v)].pivot(index='bin', columns='target', values='per1000').round(1); n = H[(H.day == 'D-1') & (H.subset == sub) & (H['var'] == v) & (H.target == 'B')].set_index('bin')[['n', 'ev']]; h['cycle-min'] = n.n; h['B events'] = n.ev; print(f'\nD-1 | {sub} | hazard per 1000 cycle-minutes by {v} (lakh): B residual, A all sub-1.2x, S stop-like'); print(h.reindex(H[(H.day == 'D-1') & (H.subset == sub) & (H['var'] == v) & (H.target == 'B')].bin.tolist()).to_string())
# (d) own-right vs other-right 15-min change, contract-minute AUC on lots below 1.2x
Bk = Bk.sort_values(['und', 'expiry', 'day', 'j']); 
for cp in ('CE', 'PE'): Bk[f'd15_{cp}'] = Bk.groupby(['und', 'expiry', 'day'])[f'B_{cp}'].diff(15)
P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); resid = ev[ev.klass == 'sub-1.2x residual'].groupby(['und', 'expiry', 'day', 'cp', 'strike', 'j']).size().rename('resid_n').reset_index()
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
rows = []
for day in ('D-1', 'D0'):
    Q = P[(P.day == day) & (P.r_low < 1.2)].merge(Bk[['und', 'expiry', 'day', 'j', 'dB15', 'd15_CE', 'd15_PE', 'DD']], on=['und', 'expiry', 'day', 'j'], how='left').merge(resid, on=['und', 'expiry', 'day', 'cp', 'strike', 'j'], how='left'); Q = Q[Q.dB15.notna()]
    Q['d15_own'] = np.where(Q.cp == 'CE', Q.d15_CE, Q.d15_PE); Q['d15_oth'] = np.where(Q.cp == 'CE', Q.d15_PE, Q.d15_CE); y = (Q.resid_n.fillna(0) > 0).astype(int).values; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
    for f in ('dB15', 'd15_own', 'd15_oth', 'DD'):
        x = Q[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(100))]; rows.append((day, f, a, *np.quantile(bs, [.025, .975])))
A = pd.DataFrame(rows, columns=['day', 'variable', 'AUC', 'lo', 'hi']).round(3); A.to_csv(f'{OUT}/bl_book_own_other_d15.csv', index=False); print('\nown-right vs other-right 15-min P&L change (residual target, contract-minutes below 1.2x):'); print(A.to_string(index=False)); R['own_other'] = A.to_dict('list')
rec('book4', R)
