"""Permutation importance of every library feature in a flexible model (HistGradientBoosting), leave-one-cycle-out, non-slot minutes only. AUC drop when the feature is shuffled inside the held-out cycle (3 shuffles). Output outputs/bl_var_gb_importance.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
F = pd.read_csv(f'{OUT}/bl_feat_panel.csv'); F = F[F.tslot != 0].reset_index(drop=True)
BASE = ['fav30', 'own_ratio', 'other_ratio']
FAM = {'spot': ['fav5', 'fav15', 'fav60', 'fav_open', 'dd_ext', 'abs15', 'rv30', 'rv_rel'], 'position': ['S_own', 'S_other', 'imb', 'L_own', 'L_other', 'own_share', 'n_strikes', 'dev_book'], 'pnl': ['asym', 'mtm_own', 'mtm_other', 'mtm_tot'],
       'greeks': ['delta_need', 'delta_need_pct', 'nd_per_short', 'delta_own', 'delta_oth', 'nd', 'gamma', 'vega'], 'vol': ['atm_iv', 'd_iv15', 'd_iv30', 'iv_rel', 'straddle', 'd_str15', 'd_str30'],
       'clock': ['mins'], 'activity': ['tsl_own', 'tsl_other', 'solo_own30', 'solo_oth30', 'sched30']}
ALLF = BASE + [c for v in FAM.values() for c in v]; fam_of = {f: k for k, v in FAM.items() for f in v}; [fam_of.update({b: 'baseline'}) for b in BASE]
def one(Q, c, cols):
    tr = Q.cycle != c; te = ~tr; X = Q[cols]; med = X[tr].median(); Xtr = X[tr].fillna(med); Xte = X[te].fillna(med); m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.06, min_samples_leaf=40, random_state=0).fit(Xtr, Q.ep[tr]); yt = Q.ep[te].values
    if yt.sum() == 0: return c, None, None
    base = roc_auc_score(yt, m.predict_proba(Xte)[:, 1]); rg = np.random.default_rng(abs(hash(c)) % 2 ** 32); drops = {}
    for f in cols:
        d = []
        for _ in range(3): Xp = Xte.copy(); Xp[f] = rg.permutation(Xp[f].values); d.append(base - roc_auc_score(yt, m.predict_proba(Xp)[:, 1]))
        drops[f] = np.mean(d)
    return c, base, drops
out = []
for day in ('D-1', 'D0'):
    Q = F[F.day == day].reset_index(drop=True); Q['cycle'] = Q.und + Q.expiry; res = Parallel(n_jobs=4)(delayed(one)(Q, c, ALLF) for c in Q.cycle.unique()); res = [r for r in res if r[1] is not None]
    D = pd.DataFrame([r[2] for r in res]); print(f'\n== {day}: GB LOCO mean per-cycle AUC {np.mean([r[1] for r in res]):.3f} over {len(res)} cycles with episodes')
    rg = np.random.default_rng(0)
    for f in ALLF:
        v = D[f].values; bs = [v[rg.integers(0, len(v), len(v))].mean() for _ in range(300)]; out.append((day, fam_of[f], f, v.mean(), np.quantile(bs, .025), np.quantile(bs, .975)))
I = pd.DataFrame(out, columns=['day', 'family', 'feature', 'auc_drop', 'lo', 'hi']); I.round(4).to_csv(f'{OUT}/bl_var_gb_importance.csv', index=False)
for day in ('D-1', 'D0'): print('\n', day); print(I[I.day == day].sort_values('auc_drop', ascending=False).head(14).round(4).to_string(index=False))
