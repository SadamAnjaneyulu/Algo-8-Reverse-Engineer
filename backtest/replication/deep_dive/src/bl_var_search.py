"""Variable search for solo-sell episode starts (plan: reports/BODY_SOLO_VARIABLE_SEARCH_PLAN.md). Univariate AUC (cluster bootstrap, Holm), incremental value over the baseline (LOCO logistic, paired cycle bootstrap, permutation null), flexible model with family-drop importance."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss
from joblib import Parallel, delayed
F = pd.read_csv(f'{OUT}/bl_feat_panel.csv'); rng = np.random.default_rng(0)
BASE = ['fav30', 'own_ratio', 'other_ratio']
FAM = {'spot': ['fav5', 'fav15', 'fav60', 'fav_open', 'dd_ext', 'abs15', 'rv30', 'rv_rel'],
       'position': ['S_own', 'S_other', 'imb', 'L_own', 'L_other', 'own_share', 'n_strikes', 'dev_book'],
       'pnl': ['asym', 'mtm_own', 'mtm_other', 'mtm_tot'],
       'greeks': ['delta_need', 'delta_need_pct', 'nd_per_short', 'delta_own', 'delta_oth', 'nd', 'gamma', 'vega'],
       'vol': ['atm_iv', 'd_iv15', 'd_iv30', 'iv_rel', 'straddle', 'd_str15', 'd_str30'],
       'time_activity': ['mins', 'tslot', 'tsl_own', 'tsl_other', 'solo_own30', 'solo_oth30', 'sched30']}
CAND = [c for v in FAM.values() for c in v]
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
def prep(Q, cols): X = Q[cols].copy(); X = X.fillna(X.median()); X = (X - X.mean()) / X.std().replace(0, 1); return X.values
def fold(X, y, g, c, kind):
    tr = g != c; te = ~tr
    if kind == 'lr': m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr])
    else: m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.06, min_samples_leaf=40, random_state=0).fit(X[tr], y[tr])
    return np.where(te)[0], m.predict_proba(X[te])[:, 1]
def loco(X, y, g, kind='lr'):
    out = np.zeros(len(y)); res = Parallel(n_jobs=4)(delayed(fold)(X, y, g, c, kind) for c in np.unique(g))
    for i, p in res: out[i] = p
    return out
def boot_gain(p1, p0, y, g, n=150):
    ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; d = []
    for _ in range(n): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); d.append(roc_auc_score(y[ii], p1[ii]) - roc_auc_score(y[ii], p0[ii]))
    return np.quantile(d, .025), np.quantile(d, .975)
uni = []; inc = []; mods = []; gbs = []
for day in ('D-1', 'D0'):
    Q = F[F.day == day].reset_index(drop=True); y = Q.ep.values; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
    # 1 univariate
    ur = []
    for f in CAND + BASE:
        x = Q[f].values.astype(float); a = auc(x, y); bs = []
        for _ in range(200): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bs.append(auc(x[ii], y[ii]))
        bs = np.array([b for b in bs if b == b]); p = 2 * min((bs <= .5).mean(), (bs >= .5).mean()); fam = next((k for k, v in FAM.items() if f in v), 'baseline'); ur.append((day, fam, f, a, np.quantile(bs, .025), np.quantile(bs, .975), max(p, 1 / 200), Q[f].isna().mean()))
    U = pd.DataFrame(ur, columns=['day', 'family', 'feature', 'AUC', 'lo', 'hi', 'p_boot', 'missing']); s = U.sort_values('p_boot'); U.loc[s.index, 'holm_p'] = np.maximum.accumulate(np.minimum(1, [(len(s) - i) * p for i, p in enumerate(s.p_boot)])); uni.append(U)
    # 2 incremental
    Xb = prep(Q, BASE); pb = loco(Xb, y, g); ab = roc_auc_score(y, pb); lb = log_loss(y, pb); print(f'\n== {day}: baseline LOCO AUC {ab:.3f} logloss {lb:.4f} (episodes {int(y.sum())}, cycles {len(ucy)})')
    def gain(cols, perm=None):
        Xc = Q[cols].copy()
        if perm is not None:
            for c in perm: Xc[c] = Xc.groupby([Q.und + Q.expiry, Q.cp])[c].transform(lambda s: rng.permutation(s.values))
        X = prep(Xc.assign(**{}) if False else pd.concat([Q[BASE], Xc[[c for c in cols if c not in BASE]]], axis=1), BASE + [c for c in cols if c not in BASE]); p = loco(X, y, g); return roc_auc_score(y, p) - ab, lb - log_loss(y, p), p
    for f in CAND:
        gA, gL, p1 = gain(BASE + [f]); lo, hi = boot_gain(p1, pb, y, g); nulls = [gain(BASE + [f], perm=[f])[0] for _ in range(4)]
        inc.append((day, next(k for k, v in FAM.items() if f in v), f, gA, lo, hi, gL, np.median(nulls), max(nulls)))
    for fam, cols in FAM.items():
        gA, gL, p1 = gain(BASE + cols); lo, hi = boot_gain(p1, pb, y, g); inc.append((day, fam, f'[ALL {fam}]', gA, lo, hi, gL, np.nan, np.nan))
    # 3 models
    for nm, cols in (('fav30 only', ['fav30']), ('own+other ratio only', ['own_ratio', 'other_ratio']), ('delta_need only', ['delta_need']), ('delta_need_pct only', ['delta_need_pct']), ('asym only', ['asym']), ('baseline (fav30, own, other)', BASE), ('baseline + delta_need', BASE + ['delta_need']), ('delta_need + fav30', ['delta_need', 'fav30'])):
        p = loco(prep(Q, cols), y, g); mods.append((day, nm, roc_auc_score(y, p), log_loss(y, p)))
    # 4 flexible model, family drop
    ALLF = BASE + CAND; pf = loco(prep(Q, ALLF), y, g, 'gb'); af = roc_auc_score(y, pf); gbs.append((day, 'all features (GB)', af, np.nan)); pbase = loco(prep(Q, BASE), y, g, 'gb'); gbs.append((day, 'baseline only (GB)', roc_auc_score(y, pbase), np.nan))
    for fam, cols in FAM.items(): p = loco(prep(Q, [c for c in ALLF if c not in cols]), y, g, 'gb'); gbs.append((day, f'drop {fam}', roc_auc_score(y, p), af - roc_auc_score(y, p)))
    for fam, cols in FAM.items(): p = loco(prep(Q, BASE + cols), y, g, 'gb'); gbs.append((day, f'baseline + {fam}', roc_auc_score(y, p), roc_auc_score(y, p) - roc_auc_score(y, pbase)))
    print(pd.DataFrame(mods[-8:], columns=['day', 'model', 'AUC', 'logloss']).round(4).to_string(index=False)); print(pd.DataFrame(gbs[-14:], columns=['day', 'model', 'AUC', 'delta']).round(4).to_string(index=False))
U = pd.concat(uni); U.round(4).to_csv(f'{OUT}/bl_var_univariate.csv', index=False)
I = pd.DataFrame(inc, columns=['day', 'family', 'feature', 'AUC_gain', 'lo', 'hi', 'logloss_gain', 'perm_null_median_gain', 'perm_null_max_gain']); I.round(4).to_csv(f'{OUT}/bl_var_incremental.csv', index=False)
pd.DataFrame(mods, columns=['day', 'model', 'AUC', 'logloss']).round(4).to_csv(f'{OUT}/bl_var_models.csv', index=False); pd.DataFrame(gbs, columns=['day', 'model', 'AUC', 'delta']).round(4).to_csv(f'{OUT}/bl_var_gb.csv', index=False)
for day in ('D-1', 'D0'):
    print('\n== univariate AUC top (|AUC-0.5|)', day); u = U[U.day == day].assign(d=lambda d: (d.AUC - .5).abs()).sort_values('d', ascending=False).head(14); print(u[['family', 'feature', 'AUC', 'lo', 'hi', 'holm_p']].round(3).to_string(index=False))
    print('\n== incremental AUC gain over baseline', day); i = I[I.day == day].sort_values('AUC_gain', ascending=False).head(14); print(i.round(4).to_string(index=False))
