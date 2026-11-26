"""Trigger study block A+B (plan BODY_REACTIVE_TRIGGER_PLAN.md): band definition / window identification on the 363 events + 10,890 control seconds.
Outputs bl_trg_band.pkl.gz, bl_trg_bandscan.csv, bl_trg_margin.csv, bl_summary_trg1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import json
from bl_common import *
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
rng = np.random.default_rng(777); R = {}
T = pd.read_pickle(f'{OUT}/bl_act_table.pkl.gz')[['cid', 'und', 'expiry', 'y', 't', 'j', 'strike', 'atm', 'step', 'live', 'v2']].reset_index(drop=True); ch = Chain()
NS = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 120]; names = [f'N{n}' for n in NS] + ['EXP']
pos = {k: np.full(len(T), np.nan) for k in names}; hi = {k: np.full(len(T), np.nan) for k in names}; lo = {k: np.full(len(T), np.nan) for k in names}
for (u, e), idx in T.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; sub = T.loc[idx]; J = sub.j.values.astype(int); L = sub.live.values
    for k, N in zip(names, NS + [None]):
        for ii, (j, l) in zip(idx, zip(J, L)):
            w = sp[max(j - N, 0):j] if N else sp[0:j]               # completed closes only (j-N .. j-1), expanding = since the first minute
            h, lw = w.max(), w.min(); hi[k][ii] = h; lo[k][ii] = lw; pos[k][ii] = (l - lw) / max(h - lw, 1e-6) - 0.5
y = T.y.values; cid = T.cid.values; ucy = np.unique(cid); gi = {c_: np.where(cid == c_)[0] for c_ in ucy}; bs = [np.concatenate([gi[c_] for c_ in rng.choice(ucy, len(ucy))]) for _ in range(600)]
def auc(s, yy):
    r = rankdata(s); n1 = yy.sum(); n0 = len(yy) - n1; return (r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
A = {k: np.abs(pos[k]) for k in names}; half = (cid % 2 == 0)
rows = []
for k in names:
    p = pos[k]; up = p > 0; dn = p < 0; a_all = auc(A[k], y); a_up = auc(A[k][up], y[up]); a_dn = auc(A[k][dn], y[dn])
    beyond = np.abs(p) > 0.5; se = beyond[y == 1].mean(); sc = beyond[y == 0].mean()
    stp = T.step.values; mg = np.where(p > 0, (T.live.values - hi[k]) / stp, (lo[k] - T.live.values) / stp)             # margin beyond the band in steps (>0 = beyond)
    me = mg[(y == 1) & beyond]; mc = mg[(y == 0) & beyond]
    rows.append(dict(window=k, AUC=a_all, AUC_upper_edge=a_up, AUC_lower_edge=a_dn, AUC_half_even=auc(A[k][half], y[half]), AUC_half_odd=auc(A[k][~half], y[~half]), share_events_beyond=se, share_controls_beyond=sc, ratio=se / sc, median_margin_events_steps=np.median(me), median_margin_controls_steps=np.median(mc), share_margin_lt_0p5_events=(me < 0.5).mean(), share_margin_lt_0p5_controls=(mc < 0.5).mean(), n_events_up=int((up & (y == 1)).sum()), n_events_dn=int((dn & (y == 1)).sum())))
S = pd.DataFrame(rows); best = S[S.window != 'EXP'].AUC.idxmax(); bk = S.window[best]
# paired cluster bootstrap vs the best rolling N (and expanding vs best)
bt = {k: np.array([auc(A[k][b], y[b]) for b in bs]) for k in names}
for k in names:
    d = bt[k] - bt[bk]; S.loc[S.window == k, 'diff_vs_best_lo'] = np.quantile(d, .025); S.loc[S.window == k, 'diff_vs_best_hi'] = np.quantile(d, .975)
# upper / lower edge best N separately
for side, col in (('upper', 'AUC_upper_edge'), ('lower', 'AUC_lower_edge')):
    sk = S[S.window != 'EXP'][col].idxmax(); R[f'best_{side}'] = S.window[sk]; R[f'best_{side}_AUC'] = float(S[col][sk])
# log-loss of hazard model (beyond flag + margin) by grouped 5-fold
def ll(k):
    p = pos[k]; stp = T.step.values; mg = np.where(p > 0, (T.live.values - hi[k]) / stp, (lo[k] - T.live.values) / stp); X = np.c_[np.abs(p) > 0.5, np.clip(mg, -3, 3)]; tot = 0
    for f in range(5):
        te = (cid % 5 == f); m = LogisticRegression(C=10).fit(X[~te], y[~te]); pr = m.predict_proba(X[te])[:, 1]; tot += -np.sum(y[te] * np.log(pr) + (1 - y[te]) * np.log(1 - pr))
    return tot / len(y)
S['cv_logloss_beyond_plus_margin'] = [ll(k) for k in names]
S.round(4).to_csv(f'{OUT}/bl_trg_bandscan.csv', index=False); print(S.drop(columns=['n_events_up', 'n_events_dn']).round(3).to_string(index=False))
R['best_rolling'] = bk; R['best_rolling_AUC'] = float(S.AUC[best]); R['expanding_AUC'] = float(S.AUC[S.window == 'EXP'].iloc[0]); R['expanding_diff_lo_hi'] = [float(S.diff_vs_best_lo[S.window == 'EXP'].iloc[0]), float(S.diff_vs_best_hi[S.window == 'EXP'].iloc[0])]
R['within_ci_of_best'] = [k for k in names if k != 'EXP' and S.diff_vs_best_hi[S.window == k].iloc[0] >= 0 and S.diff_vs_best_lo[S.window == k].iloc[0] <= 0 and (S.diff_vs_best_lo[S.window == k].iloc[0] <= 0 or k == bk)]
R['excluded_vs_best'] = [k for k in names if k not in R['within_ci_of_best'] and k != 'EXP']
# B: direction at the edge, N=60 and best
for tag, k in (('N60', 'N60'), ('best', bk)):
    p = pos[k]; E = (y == 1); d = np.sign(p) * T.step.values + T.atm.values == T.strike.values; bey = np.abs(p) > 0.5
    R[f'dir_hit_{tag}'] = dict(beyond=float(d[E & bey].mean()), not_beyond=float(d[E & ~bey].mean()), n_beyond=int((E & bey).sum()), n_not=int((E & ~bey).sum()))
T2 = T.copy()
for k in ['N60', bk, 'EXP']: T2['pos_' + k] = pos[k]; T2['hi_' + k] = hi[k]; T2['lo_' + k] = lo[k]
T2.to_pickle(f'{OUT}/bl_trg_band.pkl.gz'); rec('trg1', R); print(json.dumps(R, indent=1, default=float)[:2500])
