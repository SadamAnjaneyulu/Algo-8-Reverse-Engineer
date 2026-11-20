"""Capital-loss trigger study, part 5: which loss variable and window? Right-level unit (cycle, day, minute, right with body shorts open); target B = residual sub-1.2x buy-back on that right (also A and S for contrast).
Own-right P&L change over windows 3/5/10/15/20/30/45/60 min, own-right drawdown from its running peak (within the day), per-short-lot normalised versions, and the threshold-precision table for own-right 15-min loss levels (Rs thousand / % of Rs 2 crore). D-1 primary.
Outputs bl_book_window_auc.csv, bl_book_threshold.csv, bl_summary_book5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
LAKH = 1e5; C = 2e7; rng = np.random.default_rng(51); R = {}
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz').sort_values(['und', 'expiry', 'day', 'j']); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz', usecols=['und', 'expiry', 'day', 'cp', 'j', 'n_open', 'price', 'avg', 'r_low'])
W = (3, 5, 10, 15, 20, 30, 45, 60); gb = Bk.groupby(['und', 'expiry', 'day'])
for cp in ('CE', 'PE'):
    for w in W: Bk[f'd{w}_{cp}'] = gb[f'B_{cp}'].diff(w)
    Bk[f'peak_{cp}'] = gb[f'B_{cp}'].cummax(); Bk[f'dd_{cp}'] = Bk[f'peak_{cp}'] - Bk[f'B_{cp}']
U = P.groupby(['und', 'expiry', 'day', 'cp', 'j']).agg(n_open=('n_open', 'sum')).reset_index().merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left')
for w in W: U[f'own{w}'] = np.where(U.cp == 'CE', U[f'd{w}_CE'], U[f'd{w}_PE'])
U['own_dd'] = np.where(U.cp == 'CE', U.dd_CE, U.dd_PE)
for k, nm in (('sub-1.2x residual', 'B'), ('stop-like (>=1.5x)', 'S')): U = U.merge(ev[ev.klass == k].groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename(nm).reset_index(), on=['und', 'expiry', 'day', 'cp', 'j'], how='left')
U = U.merge(ev[ev.klass.str.startswith('sub')].groupby(['und', 'expiry', 'day', 'cp', 'j']).size().rename('A').reset_index(), on=['und', 'expiry', 'day', 'cp', 'j'], how='left').fillna({'A': 0, 'B': 0, 'S': 0}); U = U[U.own15.notna()]
for w in (15,): U[f'own{w}_perlot'] = U[f'own{w}'] / U.n_open.clip(lower=1)
def auc(x, y): n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
rows = []; thr = []
for day in ('D-1', 'D0'):
    Q = U[U.day == day]; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
    for tgt in ('B', 'A', 'S'):
        y = (Q[tgt] > 0).astype(int).values
        for f in [f'own{w}' for w in W] + ['own15_perlot', 'own_dd']:
            x = Q[f].values; a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(100))]; rows.append((day, tgt, f, int(y.sum()), a, *np.quantile(bs, [.025, .975])))
    A = pd.DataFrame([r for r in rows if r[0] == day and r[1] == 'B'], columns=['d', 't', 'f', 'n', 'AUC', 'lo', 'hi']); print(f'\n{day} target B residual (right-minutes {len(Q):,}, events {int((Q.B > 0).sum())}): AUC of own-right P&L change; < 0.5 means a recent LOSS on the own right goes with a buy-back'); print(A.drop(columns=['d', 't']).round(3).to_string(index=False))
    # threshold-precision table for own15 loss levels (Rs)
    yb = (Q.B > 0).values; base = yb.mean()
    for X in (10e3, 20e3, 30e3, 50e3, 75e3, 100e3, 150e3):
        m = (Q.own15 <= -X).values; thr.append((day, X, X / C * 100, int(m.sum()), int(yb[m].sum()), yb[m].mean() if m.sum() else np.nan, base, (yb[m].mean() / base) if m.sum() else np.nan, yb[m].sum() / max(yb.sum(), 1)))
T = pd.DataFrame(thr, columns=['day', 'loss_rs', 'pct_of_capital', 'right_minutes', 'events', 'hazard', 'base_hazard', 'lift', 'recall']).round(4); T.to_csv(f'{OUT}/bl_book_threshold.csv', index=False); print('\nown-right 15-min loss >= X (residual buy-back hazard vs base):'); print(T[T.day == 'D-1'].to_string(index=False))
pd.DataFrame(rows, columns=['day', 'target', 'variable', 'events', 'AUC', 'lo', 'hi']).round(4).to_csv(f'{OUT}/bl_book_window_auc.csv', index=False); rec('book5', {'thr': T.to_dict('list')})
