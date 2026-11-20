"""Slot decisions (plan A/B): is the paired sale a fixed schedule, or does the state at the slot change execution or quantity?
1 execution by slot / index; 2 ladder structure (unique values, mode share, previous-cycle equality); 3 variance explained by (index x slot) alone; 4 LOCO incremental value of every state variable over (index x slot) with permutation nulls; 5 link to buy-backs / losses."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.linear_model import Ridge
from joblib import Parallel, delayed
P = pd.read_csv(f'{OUT}/bl_slot_panel.csv'); rng = np.random.default_rng(0)
S = P[P.day == 'D-1'].copy(); SCHED = [k for k in range(0, 14) if k != 12]            # slots with a scheduled ladder on D-1 (executed in >= 97 % of cycles)
ex = S.groupby('k').agg(rows=('k', 'size'), executed=('lots_paired', lambda s: (s > 0).mean()), mean_lots=('lots_paired', 'mean')).round(3); ex.to_csv(f'{OUT}/bl_slot_execution_d1.csv'); print('D-1 execution by slot:'); print(ex.T.to_string())
for und in ('NIFTY', 'SENSEX'): print(und, 'executed share, scheduled slots (k in 0-11,13):', round((S[(S.und == und) & S.k.isin(SCHED)].lots_paired > 0).mean(), 3))
T = S[S.k.isin(SCHED)].copy(); T['cell'] = T.und + '_' + T.k.astype(str)
mode = T.groupby('cell').lots_paired.agg(lambda s: s.mode().iloc[0]); T['mode'] = T.cell.map(mode); print('\nladder: share of slot-rights equal to the (index, slot) mode: %.3f ; unique values per cell median %d' % ((T.lots_paired == T['mode']).mean(), T.groupby('cell').lots_paired.nunique().median()))
# equality with the previous cycle of the same index and right
T = T.sort_values(['und', 'cp', 'expiry', 'k']); T['prev_cycle_lots'] = T.groupby(['und', 'cp', 'k']).lots_paired.shift(1); print('equal to the previous cycle (same index, right, slot): %.3f' % (T.lots_paired == T.prev_cycle_lots)[T.prev_cycle_lots.notna()].mean())
tot = ((T.lots_paired - T.lots_paired.mean()) ** 2).sum(); res = ((T.lots_paired - T.groupby('cell').lots_paired.transform('mean')) ** 2).sum(); print('variance of slot lots explained by (index x slot) alone: R2 = %.3f' % (1 - res / tot))
# CE vs PE
w = T.pivot_table(index=['und', 'expiry', 'k'], columns='cp', values='lots_paired'); print('CE lots == PE lots: %.3f' % (w.CE == w.PE).mean())
# by chronological half and weekday-like era
T['half'] = T.expiry.map({e: (0 if i < T.expiry.nunique() / 2 else 1) for i, e in enumerate(sorted(T.expiry.unique()))}); print('ladder equal to mode, by half:', T.groupby('half').apply(lambda g: (g.lots_paired == g['mode']).mean()).round(3).to_dict())
# 4 incremental value of state variables over the cell mean (LOCO, ridge)
FEATS = ['fav5', 'fav15', 'fav30', 'fav60', 'fav_open', 'dd_ext', 'abs15', 'rv30', 'own_ratio', 'other_ratio', 'asym', 'book_ratio', 'mtm_own', 'mtm_other', 'mtm_tot', 'S_own', 'S_other', 'L_own', 'L_other', 'imb', 'cov_own', 'cov_oth', 'solo_own_since', 'prev_paired', 'nd', 'delta_need', 'nd_per_short', 'gamma', 'vega', 'atm_iv', 'd_iv15', 'd_iv30', 'iv_rel', 'straddle', 'd_str15', 'd_str30']
T = T.reset_index(drop=True); g = (T.und + T.expiry).values; Xc = pd.get_dummies(T.cell).values.astype(float); y = T.lots_paired.values.astype(float)
def loco_pred(X):
    out = np.zeros(len(y))
    def one(c):
        tr = g != c; m = Ridge(alpha=1.0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict(X[~tr])
    for i, p in Parallel(n_jobs=4)(delayed(one)(c) for c in np.unique(g)): out[i] = p
    return out
def r2(p): return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()
p0 = loco_pred(Xc); r0 = r2(p0); print('\nLOCO R2 of (index x slot) cell means: %.3f' % r0)
def zs(v): v = pd.Series(v); v = v.fillna(v.median()); return ((v - v.mean()) / (v.std() if v.std() > 0 else 1)).values
ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; out = []
for f in FEATS:
    x = zs(T[f].values); p1 = loco_pred(np.column_stack([Xc, x])); gain = r2(p1) - r0; bs = []
    for _ in range(100): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bs.append((1 - ((y[ii] - p1[ii]) ** 2).sum() / ((y[ii] - y[ii].mean()) ** 2).sum()) - (1 - ((y[ii] - p0[ii]) ** 2).sum() / ((y[ii] - y[ii].mean()) ** 2).sum()))
    nul = [r2(loco_pred(np.column_stack([Xc, zs(T.assign(v=T.groupby('cell')[f].transform(lambda s: rng.permutation(s.values))).v.values)]))) - r0 for _ in range(3)]
    out.append((f, gain, np.quantile(bs, .025), np.quantile(bs, .975), np.median(nul), max(nul), stats_rho := T[[f]].assign(r=y - p0).corr(method='spearman').iloc[0, 1]))
R = pd.DataFrame(out, columns=['feature', 'R2_gain', 'lo', 'hi', 'perm_null_median', 'perm_null_max', 'spearman_with_residual']).sort_values('R2_gain', ascending=False); R.round(4).to_csv(f'{OUT}/bl_slot_state_tests.csv', index=False); print(R.round(4).head(12).to_string(index=False))
print('\nfeatures with CI above 0 AND gain above the permutation-null max:', R[(R.lo > 0) & (R.R2_gain > R.perm_null_max)].feature.tolist())
# 5 link to buy-backs and losses: lots in slot vs buy-backs since previous slot; executed vs book loss
T['resid'] = y - p0; print('Spearman(resid, own-right buy-backs since previous slot) %.3f ; (resid, book_ratio) %.3f ; (resid, mtm_tot) %.3f' % tuple(T[['resid', c]].corr(method='spearman').iloc[0, 1] for c in ('cov_own', 'book_ratio', 'mtm_tot')))
print('lots by quartile of buy-backs since the previous slot (own right):', T.groupby(pd.qcut(T.cov_own, 4, duplicates='drop')).lots_paired.mean().round(2).to_dict())
print('lots by quartile of book price ratio:', T.groupby(pd.qcut(T.book_ratio, 4, duplicates='drop')).lots_paired.mean().round(2).to_dict())
T.to_csv(f'{OUT}/bl_slot_d1_scheduled.csv', index=False)
