"""Indicator search step 2 (plan tests 1-5): per-indicator direction hit (D) and activation AUC (A); family cross-validated scores (parameter chosen on one half of the cycles, scored on the other); paired cluster-bootstrap differences; absolute vs volatility-scaled neutral zone; neutral-zone width; combination test.
Outputs bl_ind_scores.csv, bl_ind_family_cv.csv, bl_ind_boot.csv, bl_ind_norm.csv, bl_ind_zone.csv, bl_ind_combo.csv, bl_summary_ind.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
rng = np.random.default_rng(601); R = {}; D = pd.read_pickle(f'{OUT}/bl_ind_table.pkl.gz'); M = pd.read_csv(f'{OUT}/bl_ind_meta.csv'); y = D.y.values; cid = D.cid.values; ucy = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in ucy}; ev = y == 1
half = (cid % 2).astype(int)
def auc(x, y_): m = ~np.isnan(x); x, y_ = x[m], y_[m]; n1 = y_.sum(); n0 = len(y_) - n1; r = stats.rankdata(x); return (r[y_ == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
def hit(v, mask): s = np.sign(v[mask]); return float(((D.atm.values[mask] + s * D.step.values[mask]) == D.strike.values[mask]).mean())
def scores(name, mask_h=None):
    v = D[name].values; m = np.ones(len(D), bool) if mask_h is None else mask_h
    return hit(v, ev & m), auc(np.abs(v[m]), y[m])
rows = []
for nm in M.indicator:
    d_, a_ = scores(nm); rows.append((nm, d_, a_))
S = M.merge(pd.DataFrame(rows, columns=['indicator', 'direction_hit', 'activation_AUC']), on='indicator'); S.round(4).to_csv(f'{OUT}/bl_ind_scores.csv', index=False)
# ---- cross-validated family scores
fam_rows = []; chosen = {}
for fam, g in S.groupby('family'):
    out = {}
    for met in ('direction_hit', 'activation_AUC'):
        sc = []
        for hsel in (0, 1):
            tr = half == hsel; te = ~tr; best = max(g.indicator, key=lambda nm: scores(nm, tr)[0 if met == 'direction_hit' else 1]); sc.append(scores(best, te)[0 if met == 'direction_hit' else 1]); chosen[(fam, met, hsel)] = best
        out[met] = float(np.mean(sc))
    fam_rows.append((fam, len(g), g.direction_hit.max(), g.indicator[g.direction_hit.idxmax()].split('|')[1], out['direction_hit'], g.activation_AUC.max(), g.indicator[g.activation_AUC.idxmax()].split('|')[1], out['activation_AUC'], int((g.direction_hit >= g.direction_hit.max() - .01).sum()), int((g.activation_AUC >= g.activation_AUC.max() - .01).sum())))
F = pd.DataFrame(fam_rows, columns=['family', 'n_params', 'best_D_fullsample', 'best_D_param', 'D_crossvalidated', 'best_A_fullsample', 'best_A_param', 'A_crossvalidated', 'params_within_1pt_D', 'params_within_0.01_A']).sort_values('A_crossvalidated', ascending=False); F.round(4).to_csv(f'{OUT}/bl_ind_family_cv.csv', index=False); print(F.round(3).to_string(index=False)); R['family_cv'] = F.round(4).to_dict('list')
# ---- paired cluster bootstrap of the family differences (out-of-fold values, parameters chosen on the original split)
def oof(fam, met):
    v = np.full(len(D), np.nan)
    for hsel in (0, 1): nm = chosen[(fam, met, hsel)]; te = half != hsel; v[te] = D[nm].values[te]
    return v
bs_idx = [rng.choice(ucy, len(ucy)) for _ in range(300)]
def boot(met, fams):
    V = {f: oof(f, met) for f in fams}; res = {f: [] for f in fams}
    for b in bs_idx:
        ii = np.concatenate([idx[c] for c in b])
        for f in fams:
            v = V[f][ii]; yy = y[ii]; ee = ev[ii]; hh = half[ii]
            if met == 'direction_hit': s = np.sign(v[ee]); res[f].append(float(((D.atm.values[ii][ee] + s * D.step.values[ii][ee]) == D.strike.values[ii][ee]).mean()))
            else: res[f].append(np.mean([auc(np.abs(v[hh == h]), yy[hh == h]) for h in (0, 1)]))
    return res
fams = list(F.family); BD = boot('direction_hit', fams); BA = boot('activation_AUC', fams); bt = []
topD = F.sort_values('D_crossvalidated', ascending=False).family.iloc[0]; topA = F.family.iloc[0]
for f in fams: bt.append((f, np.mean(BD[f]), *np.quantile(np.array(BD[f]) - np.array(BD[topD]), [.025, .975]), np.mean(BA[f]), *np.quantile(np.array(BA[f]) - np.array(BA[topA]), [.025, .975])))
B = pd.DataFrame(bt, columns=['family', 'D_boot_mean', 'D_diff_vs_best_lo', 'D_diff_vs_best_hi', 'A_boot_mean', 'A_diff_vs_best_lo', 'A_diff_vs_best_hi']); B.round(4).to_csv(f'{OUT}/bl_ind_boot.csv', index=False); print('\npaired bootstrap vs the best family on each metric (best D family:', topD, '| best A family:', topA, ')'); print(B.round(3).to_string(index=False)); R['topD'] = topD; R['topA'] = topA; R['boot'] = B.round(4).to_dict('list')
indist_D = [f for f, lo, hi in zip(B.family, B.D_diff_vs_best_lo, B.D_diff_vs_best_hi) if hi >= 0 and lo <= 0 and f != topD] + [topD]; indist_A = [f for f, lo, hi in zip(B.family, B.A_diff_vs_best_lo, B.A_diff_vs_best_hi) if hi >= 0 and lo <= 0 and f != topA] + [topA]; R['indistinguishable_D'] = indist_D; R['indistinguishable_A'] = indist_A
# ---- absolute vs volatility-scaled neutral zone: A for |gap| vs |Bollinger z| vs |gap/ATR| at the same N
rows = []
for N in (5, 10, 15, 20, 30, 45, 60, 90):
    g_ = S.set_index('indicator'); rows.append((N, g_.loc[f'SMA gap|{N}', 'activation_AUC'], g_.loc[f'Bollinger z|{N}', 'activation_AUC'], g_.loc[f'gap/ATR|{N}', 'activation_AUC'], g_.loc[f'SMA gap|{N}', 'direction_hit']))
NR = pd.DataFrame(rows, columns=['N', 'A_abs_gap_steps', 'A_abs_bollinger_z', 'A_abs_gap_over_ATR', 'D_sma_gap']); NR.round(4).to_csv(f'{OUT}/bl_ind_norm.csv', index=False); print('\nabsolute vs volatility-scaled neutral zone'); print(NR.round(3).to_string(index=False)); R['norm'] = NR.round(4).to_dict('list')
# bootstrap difference for the best N of each
bestN = int(NR.sort_values('A_abs_gap_steps', ascending=False).N.iloc[0]); dd = []
for b in bs_idx:
    ii = np.concatenate([idx[c] for c in b]); a1 = auc(np.abs(D[f'SMA gap|{bestN}'].values[ii]), y[ii]); a2 = auc(np.abs(D[f'Bollinger z|{bestN}'].values[ii]), y[ii]); a3 = auc(np.abs(D[f'gap/ATR|{bestN}'].values[ii]), y[ii]); dd.append((a2 - a1, a3 - a1))
dd = np.array(dd); R['norm_boot'] = {'N': bestN, 'z_minus_abs': [float(np.quantile(dd[:, 0], .025)), float(np.quantile(dd[:, 0], .975)), float(dd[:, 0].mean())], 'atr_minus_abs': [float(np.quantile(dd[:, 1], .025)), float(np.quantile(dd[:, 1], .975)), float(dd[:, 1].mean())]}; print('best N', bestN, 'z - abs AUC diff CI', np.round(R['norm_boot']['z_minus_abs'], 3), '| gap/ATR - abs AUC diff CI', np.round(R['norm_boot']['atr_minus_abs'], 3))
# ---- neutral zone for the leading activation indicator (density ratio of events vs controls by control-quantile bins, base rate 2.77%/min)
lead = F.iloc[0].family + '|' + str(F.iloc[0].best_A_param); R['lead'] = lead; prof = S[S.family == F.iloc[0].family][['param', 'direction_hit', 'activation_AUC']]; R['lead_profile'] = prof.round(4).to_dict('list'); print('\nprofile of', F.iloc[0].family, ':'); print(prof.round(3).to_string(index=False))
base = 0.0277; zr = []
for nm in (lead, 'Bollinger z|30', 'EMA z|30', 'SMA gap|10'):
    v = np.abs(D[nm].values); c = v[~ev]; q = np.unique(np.quantile(c, np.linspace(0, 1, 11))); q[0] -= 1e-9; q[-1] += 1e-9; pe = np.histogram(v[ev], q)[0] / ev.sum(); pc = np.histogram(c, q)[0] / len(c)
    for i in range(len(q) - 1): zr.append((nm, i + 1, q[i], q[i + 1], pe[i], pc[i], base * pe[i] / pc[i] * 1000))
Z = pd.DataFrame(zr, columns=['indicator', 'control_decile', 'lo_steps', 'hi_steps', 'share_events', 'share_controls', 'rate_per1000_min']); Z.round(4).to_csv(f'{OUT}/bl_ind_zone.csv', index=False)
zz = Z[Z.indicator == lead]; plateau = zz.rate_per1000_min.iloc[5:].mean(); half_pt = zz[zz.rate_per1000_min >= plateau / 2].lo_steps.min(); R['zone'] = {'indicator': lead, 'plateau_per1000': float(plateau), 'half_rate_at_steps': float(half_pt), 'first_decile_rate': float(zz.rate_per1000_min.iloc[0]), 'deciles': zz.round(4).to_dict('list')}; print('\nneutral zone for', lead, ': plateau', round(plateau, 1), 'per 1000 min; half-rate at |v| >=', round(half_pt, 3), '; lowest decile rate', round(zz.rate_per1000_min.iloc[0], 1)); print(zz.round(3).to_string(index=False))
# zone width in points / % by underlying

# ---- combination: leave-one-cycle-out logistic, leading gap alone vs + other indicators
def loco(cols):
    X = D[cols].astype(float).abs().fillna(0).values; X = (X - X.mean(0)) / (X.std(0) + 1e-9); o = np.zeros(len(y))
    for c in ucy:
        tr = cid != c; m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr]); o[~tr] = m.predict_proba(X[~tr])[:, 1]
    return roc_auc_score(y, o)
combos = {f'{lead} alone': [lead], '+ SMA gap 10 (absolute)': [lead, 'SMA gap|10'], '+ Bollinger z 30': [lead, 'Bollinger z|30'], '+ EMA z 30': [lead, 'EMA z|30'], '+ gap/ATR 15': [lead, 'gap/ATR|15'], '+ momentum 15': [lead, 'momentum|15'], '+ SMA cross (10,30)': [lead, 'SMA cross|10-30'], '+ MACD (12,26)': [lead, 'MACD|12-26'], '+ regression drift 30': [lead, 'regression drift|30'], '+ Donchian position 15': [lead, 'Donchian position|15'], '+ RSI 14ish (30)': [lead, 'RSI minus 50|30']}
CB = pd.DataFrame([(k, loco(v)) for k, v in combos.items()], columns=['model', 'LOCO_AUC']); CB['gain_vs_alone'] = CB.LOCO_AUC - CB.LOCO_AUC.iloc[0]; CB.round(4).to_csv(f'{OUT}/bl_ind_combo.csv', index=False); print('\ncombination (leave-one-cycle-out logistic on |values|)'); print(CB.round(3).to_string(index=False)); R['combo'] = CB.round(4).to_dict('list')
rec('ind', R)
