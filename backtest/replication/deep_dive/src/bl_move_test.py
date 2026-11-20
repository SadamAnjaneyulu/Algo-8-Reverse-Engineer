"""User hypothesis test, step 2: are solo (single-leg) sells triggered by a heavy market move / a loss of x %, and do they drip in during heavy moves?
(A) AUC of pre-registered features, (B) dose-response tables, (C) disentangling own-leg profit from other-leg loss (2-D table + logistic regression with cycle bootstrap), (D) threshold grid (descriptive, no selection), (E) the 'slow injection' (drip) structure."""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
P = pd.read_csv(f'{OUT}/bl_move_panel.csv'); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); ch = Chain(); rng = np.random.default_rng(0)
FE = ['fav5', 'fav15', 'fav30', 'fav60', 'fav_open', 'dd_ext', 'own_ratio', 'other_ratio', 'book_loss']
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
res = []
for day, Q in P.groupby('day'):
    y = Q.ep.values; cy = (Q.und + Q.expiry).values; ucy = np.unique(cy); idx = {c: np.where(cy == c)[0] for c in ucy}
    for f in FE:
        x = Q[f].values.astype(float); a = auc(x, y); bs = []
        for _ in range(300): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bs.append(auc(x[ii], y[ii]))
        bs = np.array(bs); bs = bs[~np.isnan(bs)]; p = 2 * min((bs <= .5).mean(), (bs >= .5).mean()); res.append((day, f, a, np.quantile(bs, .025), np.quantile(bs, .975), max(p, 1 / 300)))
A = pd.DataFrame(res, columns=['day', 'feature', 'AUC', 'lo', 'hi', 'p_boot']); A['holm_p'] = A.groupby('day').p_boot.transform(lambda s: np.minimum(1, s.rank(method='first').pipe(lambda r: (len(s) - r + 1) * s)).cummax()) if False else np.nan
for day in A.day.unique():
    m = A.day == day; s = A[m].sort_values('p_boot'); hp = np.minimum(1, [(len(s) - i) * p for i, p in enumerate(s.p_boot)]); A.loc[s.index, 'holm_p'] = np.maximum.accumulate(hp)
A.round(3).to_csv(f'{OUT}/bl_move_auc.csv', index=False); print('(A) AUC (episode start vs other minutes); <0.5 = lower at episode starts'); print(A.round(3).pivot(index='feature', columns='day', values='AUC').to_string())
# (B) dose-response
def haz(Q, f, bins, ev='ep'):
    t = Q.groupby(pd.cut(Q[f], bins)).agg(minutes=(ev, 'size'), events=(ev, 'sum')); t['rate_per_1000'] = (t.events / t.minutes * 1000).round(1); t['lift'] = (t.events / t.minutes / Q[ev].mean()).round(2); return t
FB = [-100, 0, .1, .2, .35, .5, .75, 100]; out = []
for day, Q in P.groupby('day'):
    for f in ('fav15', 'fav30', 'fav60', 'dd_ext', 'fav_open'):
        t = haz(Q, f, FB).reset_index(); t.insert(0, 'day', day); t.insert(1, 'feature', f); t = t.rename(columns={f: 'bin'}); out.append(t)
D = pd.concat(out); D['bin'] = D.bin.astype(str); D.to_csv(f'{OUT}/bl_move_dose.csv', index=False)
for day in ('D-1', 'D0'): print('\n(B)', day, 'episode-start rate per 1000 minutes by favourable move over 30 min (%):'); print(D[(D.day == day) & (D.feature == 'fav30')][['bin', 'minutes', 'events', 'rate_per_1000', 'lift']].to_string(index=False))
# (C) 2-D: favourable 30-min move x other-leg book ratio ; logistic regression
for day, Q in P.groupby('day'):
    Q = Q.assign(fb=pd.cut(Q.fav30, [-100, 0, .2, .5, 100], labels=['<=0', '0-.2', '.2-.5', '>.5']), ob=pd.cut(Q.other_ratio, [0, .9, 1.1, 100], labels=['other<=.9', 'other .9-1.1', 'other>1.1']))
    t = Q.groupby(['fb', 'ob']).ep.agg(['size', 'sum']).assign(rate=lambda d: (d['sum'] / d['size'] * 1000).round(1)); print('\n(C)', day, 'rate per 1000 minutes: favourable 30-min move (rows) x other-leg book ratio (cols); cell n in brackets'); print(t.rate.unstack().to_string()); print(t['size'].unstack().to_string())
def logit(X, y, it=50):
    X = np.column_stack([np.ones(len(X)), X]); b = np.zeros(X.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-X @ b)); W = p * (1 - p); g = X.T @ (y - p); H = (X * W[:, None]).T @ X + 1e-6 * np.eye(len(b)); b = b + np.linalg.solve(H, g)
    return b
reg = []
for day, Q in P.groupby('day'):
    Q = Q.dropna(subset=['fav30', 'own_ratio', 'other_ratio']); y = Q.ep.values; cols = ['fav30', 'own_ratio', 'other_ratio']; X = (Q[cols] - Q[cols].mean()) / Q[cols].std(); X = X.values; b = logit(X, y)[1:]
    cy = (Q.und + Q.expiry).values; ucy = np.unique(cy); idx = {c: np.where(cy == c)[0] for c in ucy}; bs = []
    for _ in range(150): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bs.append(logit(X[ii], y[ii])[1:])
    bs = np.array(bs)
    for i, c in enumerate(cols): reg.append((day, c, b[i], np.quantile(bs[:, i], .025), np.quantile(bs[:, i], .975)))
R = pd.DataFrame(reg, columns=['day', 'term', 'coef_per_SD', 'lo', 'hi']).round(3); R.to_csv(f'{OUT}/bl_move_logit.csv', index=False); print('\n(C) logistic regression (standardised; episode start ~ fav30 + own_ratio + other_ratio), cluster bootstrap 95% CI'); print(R.to_string(index=False))
# (D) threshold grid
rows = []
for day, Q in P.groupby('day'):
    base = Q.ep.mean(); n_ep = Q.ep.sum()
    for f, ths in (('fav15', (.1, .2, .3, .5, .75, 1.0)), ('fav30', (.1, .2, .3, .5, .75, 1.0)), ('fav60', (.2, .3, .5, .75, 1.0)), ('dd_ext', (.2, .3, .5, .75, 1.0)), ('fav_open', (.2, .3, .5, .75, 1.0))):
        for th in ths: m = Q[f] >= th; rows.append((day, f'{f} >= {th} %', m.mean(), Q[m].ep.sum() / n_ep, Q[m].ep.mean() / base))
    for th in (.1, .2, .3): m = Q.other_ratio >= 1 + th; rows.append((day, f'other-leg book loss >= {int(th * 100)} %', m.mean(), Q[m].ep.sum() / n_ep, Q[m].ep.mean() / base))
    for th in (.1, .2, .3): m = Q.own_ratio <= 1 - th; rows.append((day, f'own-leg book profit >= {int(th * 100)} %', m.mean(), Q[m].ep.sum() / n_ep, Q[m].ep.mean() / base))
    for th in (-10, -5, 5, 10): m = (Q.book_loss <= th) if th < 0 else (Q.book_loss >= th); rows.append((day, f'combined book {"profit" if th < 0 else "loss"} >= {abs(th)} %', m.mean(), Q[m].ep.sum() / n_ep, Q[m].ep.mean() / base))
T = pd.DataFrame(rows, columns=['day', 'rule', 'share_of_minutes_flagged', 'recall_of_episode_starts', 'lift']).round(3); T.to_csv(f'{OUT}/bl_move_thresholds.csv', index=False)
for day in ('D-1', 'D0'): print('\n(D)', day); print(T[T.day == day].drop(columns='day').to_string(index=False))
