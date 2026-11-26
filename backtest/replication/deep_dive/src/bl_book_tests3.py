"""Capital-loss trigger study, part 3: right-level view. Unit = (cycle, day, minute, right) with body shorts open on that right. Event = residual sub-1.2x buy-back on that right (target B) or any sub-1.2x (A) or stop-like (S).
Hazard by own-right P&L bin x other-right P&L bin (cumulative LTP-marked, lakh). Tests the 'profitable side closed while the other side loses' reading. Output bl_book_right_hazard.csv, bl_summary_book3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
LAKH = 1e5; rng = np.random.default_rng(31); R = {}
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz', usecols=['und', 'expiry', 'day', 'cp', 'j'])
U = P.drop_duplicates().merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); U['B_own'] = np.where(U.cp == 'CE', U.B_CE, U.B_PE) / LAKH; U['B_oth'] = np.where(U.cp == 'CE', U.B_PE, U.B_CE) / LAKH
for k, nm in (('sub-1.2x residual', 'B'), ('stop-like (>=1.5x)', 'S')): U = U.merge(ev[ev.klass == k].groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename(nm).reset_index(), on=['und', 'expiry', 'day', 'cp', 'j'], how='left')
U = U.merge(ev[ev.klass.str.startswith('sub')].groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename('A').reset_index(), on=['und', 'expiry', 'day', 'cp', 'j'], how='left').fillna({'A': 0, 'B': 0, 'S': 0}); U = U[U.B_own.notna()]
def auc(x, y): n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
rows = []
for day in ('D-1', 'D0'):
    Q = U[U.day == day].copy(); Q['diff'] = Q.B_own - Q.B_oth; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
    print(f'\n== {day}: right-minutes {len(Q):,}; events A {int((Q.A > 0).sum())}, B(residual) {int((Q.B > 0).sum())}, S(stop-like) {int((Q.S > 0).sum())}')
    for tgt in ('A', 'B', 'S'):
        y = (Q[tgt] > 0).astype(int).values
        for v in ('B_own', 'B_oth', 'diff'):
            x = Q[v].values; a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(100))]
            nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(12)]; rows.append((day, tgt, v, a, np.quantile(bs, .025), np.quantile(bs, .975), np.median(nul), max(nul)))
    print(pd.DataFrame([r for r in rows if r[0] == day], columns=['d', 'target', 'var', 'AUC', 'lo', 'hi', 'nm', 'nx']).round(3).drop(columns='d').to_string(index=False))
    Q['own_b'] = pd.cut(Q.B_own, [-1e9, -0.5, -0.1, 0.1, 0.5, 1e9], labels=['own<-0.5L', '-0.5..-0.1', '-0.1..0.1', '0.1..0.5', 'own>0.5L']); Q['oth_b'] = pd.cut(Q.B_oth, [-1e9, -0.5, -0.1, 0.1, 0.5, 1e9], labels=['oth<-0.5L', '-0.5..-0.1', '-0.1..0.1', '0.1..0.5', 'oth>0.5L'])
    for tgt in ('B', 'S'):
        t = Q.groupby(['own_b', 'oth_b'], observed=False)[tgt].agg(n='size', ev=lambda s: (s > 0).sum()); t['per1000'] = t.ev / t.n * 1000; t = t.reset_index(); t.insert(0, 'target', tgt); t.insert(0, 'day', day); rows_h = t; rows.append(None) if False else None
        if day == 'D-1': print(f'\n{day} target {tgt}: events per 1000 right-minutes (rows own-right P&L, columns other-right P&L)'); print(t.pivot(index='own_b', columns='oth_b', values='per1000').round(1).to_string()); print(t.pivot(index='own_b', columns='oth_b', values='n').to_string())
        t.to_csv(f'{OUT}/bl_book_right_hazard_{day}_{tgt}.csv', index=False)
rec('book3', {'auc_rows': [list(map(lambda z: float(z) if not isinstance(z, str) else z, r)) for r in rows if r]})
