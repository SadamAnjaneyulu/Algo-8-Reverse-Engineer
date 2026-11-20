"""Capital-loss trigger study, part 6: artifact control. Part 5 used P&L changes that include execution-vs-mark gaps of earlier buy-backs (a dripped buy-back episode would then predict its own continuation).
Here the change is MARK-ONLY: sum over the right's CURRENT net positions of (price now - price w minutes ago) x lot (bl_book_mtm.py dm{w}_{CE,PE}). Right-minute unit; target B (residual), A, S. Subsets: all; no body buy-back on this right in the previous 5 minutes; no stop-like buy-back anywhere in the cycle in the previous 15 minutes.
Outputs bl_book_mark_auc.csv, bl_book_mark_threshold.csv, bl_summary_book6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
C = 2e7; rng = np.random.default_rng(61); R = {}
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz', usecols=['und', 'expiry', 'day', 'cp', 'j', 'n_open'])
U = P.groupby(['und', 'expiry', 'day', 'cp', 'j']).agg(n_open=('n_open', 'sum')).reset_index().merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left')
for w in (1, 3, 5, 15): U[f'own{w}'] = np.where(U.cp == 'CE', U[f'dm{w}_CE'], U[f'dm{w}_PE']); U[f'oth{w}'] = np.where(U.cp == 'CE', U[f'dm{w}_PE'], U[f'dm{w}_CE'])
for k, nm in (('sub-1.2x residual', 'B'), ('stop-like (>=1.5x)', 'S')): U = U.merge(ev[ev.klass == k].groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename(nm).reset_index(), on=['und', 'expiry', 'day', 'cp', 'j'], how='left')
U = U.merge(ev[ev.klass.str.startswith('sub')].groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename('A').reset_index(), on=['und', 'expiry', 'day', 'cp', 'j'], how='left').fillna({'A': 0, 'B': 0, 'S': 0})
allb = ev.groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename('nb').reset_index(); U = U.merge(allb, on=['und', 'expiry', 'day', 'cp', 'j'], how='left').fillna({'nb': 0}).sort_values(['und', 'expiry', 'day', 'cp', 'j'])
U['bb_prev5'] = U.groupby(['und', 'expiry', 'day', 'cp']).nb.transform(lambda s: s.shift(1).rolling(5, min_periods=1).sum()).fillna(0)
stp = ev[ev.klass == 'stop-like (>=1.5x)'].groupby(['und', 'expiry', 'day', 'j']).size().rename('s').reset_index(); cm = Bk[['und', 'expiry', 'day', 'j']].merge(stp, on=['und', 'expiry', 'day', 'j'], how='left').fillna({'s': 0}).sort_values(['und', 'expiry', 'day', 'j']); cm['stop_prev15'] = cm.groupby(['und', 'expiry', 'day']).s.transform(lambda x: x.shift(1).rolling(15, min_periods=1).sum()).fillna(0)
U = U.merge(cm[['und', 'expiry', 'day', 'j', 'stop_prev15']], on=['und', 'expiry', 'day', 'j'], how='left'); U = U[U.own15.notna()]
def auc(x, y): n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 > 2 and n0 > 2 else np.nan
rows = []; thr = []
for day in ('D-1', 'D0'):
    for sub, Q in (('all', U[U.day == day]), ('no body buy-back on this right in prev 5 min', U[(U.day == day) & (U.bb_prev5 == 0)]), ('no stop-like in cycle in prev 15 min', U[(U.day == day) & (U.stop_prev15 == 0)])):
        g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
        for tgt in ('B', 'S'):
            y = (Q[tgt] > 0).astype(int).values
            for f in ('own1', 'own3', 'own5', 'own15', 'oth3', 'oth5', 'oth15'):
                x = Q[f].values; a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(100))]; rows.append((day, sub, tgt, f, int(y.sum()), len(Q), a, *np.nanquantile(bs, [.025, .975])))
    Q = U[(U.day == day) & (U.bb_prev5 == 0)]; yb = (Q.B > 0).values; base = yb.mean()
    for w in (3, 5, 15):
        for X in (5e3, 10e3, 20e3, 30e3, 50e3, 75e3):
            m = (Q[f'own{w}'] <= -X).values; thr.append((day, w, X, X / C * 100, int(m.sum()), int(yb[m].sum()), yb[m].mean() if m.sum() else np.nan, base, (yb[m].mean() / base) if m.sum() else np.nan, yb[m].sum() / max(yb.sum(), 1)))
A = pd.DataFrame(rows, columns=['day', 'subset', 'target', 'variable', 'events', 'rows', 'AUC', 'lo', 'hi']).round(3); A.to_csv(f'{OUT}/bl_book_mark_auc.csv', index=False)
T = pd.DataFrame(thr, columns=['day', 'window_min', 'loss_rs', 'pct_of_capital', 'right_minutes', 'events', 'hazard', 'base_hazard', 'lift', 'recall']).round(4); T.to_csv(f'{OUT}/bl_book_mark_threshold.csv', index=False)
for day in ('D-1', 'D0'):
    print(f'\n=== {day}: AUC of MARK-ONLY own/other-right P&L change (< 0.5 = recent loss goes with a buy-back)'); print(A[(A.day == day)].pivot_table(index=['target', 'variable'], columns='subset', values='AUC').round(3).to_string()); print(A[(A.day == day) & (A.variable == 'own3')][['subset', 'target', 'events', 'rows', 'lo', 'hi']].to_string(index=False))
print('\nD-1 residual hazard when the own right lost >= X over the last w minutes (mark-only; no body buy-back on the right in the previous 5 min):'); print(T[T.day == 'D-1'].to_string(index=False))
rec('book6', {'auc': A.to_dict('list'), 'thr': T.to_dict('list')})
