"""Breakout (fresh favourable extreme) variable: window scan, timing after the break, robustness by right / index, break magnitude, and joint test with the baseline. Non-slot minutes. D-1 and D0. Outputs outputs/bl_breakout_*.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
F = pd.read_csv(f'{OUT}/bl_shape_panel.csv'); F = F[F.tslot != 0].reset_index(drop=True); ch = Chain(); rng = np.random.default_rng(0); BASE = ['fav30', 'own_ratio', 'other_ratio']
WINS = [5, 10, 15, 20, 30, 45, 60, 90, 120]; cache = {}
def spot(u, e, d):
    k = (u, e, d)
    if k not in cache: cache[k] = np.array([ch.spot(u, e, d, j) for j in range(375)])
    return cache[k]
cols = {f'bk{w}': [] for w in WINS}; cols.update({'bk_day': [], 'since_bk15': [], 'break_steps15': [], 'new_ext_now': []})
for r in F.itertuples():
    d = 0 if r.day == 'D-1' else 1; s = spot(r.und, r.expiry, d); sgn = 1 if r.cp == 'CE' else -1; step = ref.STEP[r.und]; j = r.j; v = -sgn * s                       # favourable direction = larger v
    for w in WINS: cols[f'bk{w}'].append(int(v[j - 1] >= np.nanmax(v[max(j - w, 0):j]) - 1e-9))
    cols['bk_day'].append(int(v[j - 1] >= np.nanmax(v[:j]) - 1e-9))
    k = 0
    while k < 30 and not (v[j - 1 - k] >= np.nanmax(v[max(j - 1 - k - 15, 0):j - k]) - 1e-9): k += 1
    cols['since_bk15'].append(k); prev = np.nanmax(v[max(j - 16, 0):j - 1]); cols['break_steps15'].append(max(v[j - 1] - prev, 0) / step)
    cols['new_ext_now'].append(int(v[j - 1] > np.nanmax(v[max(j - 16, 0):j - 1]) + 1e-9))
for k, v in cols.items(): F[k] = v
F.to_csv(f'{OUT}/bl_breakout_panel.csv', index=False)
def prep(Q, cs): X = Q[cs].copy(); X = X.fillna(X.median()); X = (X - X.mean()) / X.std().replace(0, 1); return X.values
def fold(X, y, g, c): tr = g != c; m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(X, y, g):
    o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, y, g, c) for c in np.unique(g)): o[i] = p
    return o
def boot(p1, p0, y, g, n=150):
    ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; d = []
    for _ in range(n): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); d.append(roc_auc_score(y[ii], p1[ii]) - roc_auc_score(y[ii], p0[ii]))
    return np.quantile(d, .025), np.quantile(d, .975)
rows = []
for day in ('D-1', 'D0'):
    Q = F[F.day == day].reset_index(drop=True); y = Q.ep.values; g = (Q.und + Q.expiry).values; pb = loco(prep(Q, BASE), y, g); ab = roc_auc_score(y, pb); base = y.mean()
    print(f'\n== {day} (baseline LOCO AUC {ab:.3f}) breakout window scan: rate per 1000 min when the previous close is the most favourable close of the last N minutes')
    for w in WINS + ['day']:
        f = f'bk{w}' if w != 'day' else 'bk_day'; on = Q[f] == 1; p1 = loco(prep(Q, BASE + [f]), y, g); a1 = roc_auc_score(y, p1); lo, hi = boot(p1, pb, y, g)
        rows.append((day, f, on.mean(), Q[on].ep.mean() * 1000, Q[~on].ep.mean() * 1000, roc_auc_score(y, Q[f]), a1 - ab, lo, hi)); print(f'  N={w}: flagged {on.mean():.3f} of minutes, rate {Q[on].ep.mean() * 1000:.1f} vs {Q[~on].ep.mean() * 1000:.1f} | univariate AUC {roc_auc_score(y, Q[f]):.3f} | baseline + bk AUC gain {a1 - ab:+.3f} ({lo:+.3f}..{hi:+.3f})')
    t = Q.groupby(Q.since_bk15.clip(upper=12)).ep.agg(['size', 'sum']); t['rate_per_1000'] = (t['sum'] / t['size'] * 1000).round(1); print('  rate by minutes since the last 15-min breakout (0 = the previous close broke out):', t.rate_per_1000.to_dict())
    for nm, sub in (('CE only', Q[Q.cp == 'CE']), ('PE only', Q[Q.cp == 'PE']), ('NIFTY', Q[Q.und == 'NIFTY']), ('SENSEX', Q[Q.und == 'SENSEX'])):
        on = sub.bk15 == 1; print(f'  {nm}: bk15 rate {sub[on].ep.mean() * 1000:.1f} vs {sub[~on].ep.mean() * 1000:.1f} per 1000 min ; univariate AUC {roc_auc_score(sub.ep, sub.bk15):.3f}')
    b = Q[Q.bk15 == 1]; print('  among breakout minutes, rate by break size over the prior 15-min extreme (steps):', b.groupby(pd.cut(b.break_steps15, [-1, 0, .1, .25, .5, 1, 50])).ep.agg(lambda s: round(s.mean() * 1000, 1)).to_dict())
    # does breakout carry the baseline? 2-D: favourable fav30 sign x bk15
    Q['fb'] = pd.cut(Q.fav30, [-100, 0, .1, 100], labels=['fav30<=0', '0-.1', '>.1']); tt = Q.groupby(['fb', 'bk15']).ep.agg(['size', 'sum']); tt['rate'] = (tt['sum'] / tt['size'] * 1000).round(1); print('  rate per 1000 min: favourable 30-min move (rows) x breakout15 (cols 0/1):'); print(tt.rate.unstack().to_string()); print(tt['size'].unstack().to_string())
R = pd.DataFrame(rows, columns=['day', 'feature', 'share_flagged', 'rate_on', 'rate_off', 'univariate_AUC', 'AUC_gain_over_baseline', 'lo', 'hi']).round(4); R.to_csv(f'{OUT}/bl_breakout_scan.csv', index=False)
