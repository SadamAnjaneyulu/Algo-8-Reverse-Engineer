"""Univariate association of body-position actions (REDUCED/CLOSED vs RETAINED vs ADDED) with decision-time features. Tabulation + rank AUC only. No fitting, no causal claims."""
from scipy.stats import rankdata
from common import *
T = pd.read_csv(f'{RES}/position_transitions.csv'); B = T[T.role == 'num'].copy(); B['is_exit'] = B.action.isin(['REDUCED', 'CLOSED']); B['is_add'] = B.action.isin(['ADDED'])
B['mtm_bucket'] = pd.cut(B.cycle_mtm, [-1e9, -100000, -50000, 0, 50000, 100000, 1e9], labels=['<-1.0L', '-1.0..-0.5L', '-0.5..0', '0..0.5L', '0.5..1.0L', '>1.0L'])
B['ratio_bin'] = pd.cut(B.ratio_cheapest, [0, .5, .8, 1.0, 1.2, 1.45, 1.55, 1.7, 2.0, 3, 1e9]); B['delta_abs'] = B.delta.abs()
B['delta_bin'] = pd.cut(B.delta_abs, [0, .05, .15, .3, .45, .6, 1.0]); B['hours_bin'] = pd.cut(B.hours_to_exp, [0, 1, 2, 3, 4, 6, 12, 20, 40])
def auc(x, y):
    m = x.notna(); x, y = x[m], y[m]
    if y.sum() == 0 or (~y).sum() == 0: return np.nan
    r = rankdata(x); n1 = y.sum(); n0 = len(y) - n1; return (r[y.values].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
out = []
for day in ('D-1', 'D0'):
    x = B[B.day == day]
    for f in ('ratio_cheapest', 'ratio_avg', 'strike_off_steps', 'delta_abs', 'iv', 'cycle_mtm', 'hours_to_exp', 'price', 'lots_total_book', 'spot_move_steps'):
        out.append(dict(day=day, feature=f, n=len(x), exit_rate=x.is_exit.mean(), auc_exit=auc(x[f], x.is_exit), add_rate=x.is_add.mean(), auc_add=auc(x[f], x.is_add)))
A = pd.DataFrame(out); A.to_csv(f'{RES}/transition_feature_auc.csv', index=False); pd.set_option('display.width', 250); print(A.round(3).to_string(index=False))
for f in ('ratio_bin', 'mtm_bucket', 'delta_bin', 'hours_bin'):
    t = B.groupby(['day', f], observed=True).agg(n=('is_exit', 'size'), exit_rate=('is_exit', 'mean'), add_rate=('is_add', 'mean')).round(3); print(t.to_string()); t.to_csv(f'{RES}/transition_rate_by_{f}.csv')
# counterexamples for the stop-like regime: D-1 body contracts with ratio >= 1.7 retained (no exit within the slot) and exits at ratio < 1.2
c1 = B[(B.day == 'D-1') & (B.ratio_cheapest >= 1.7)]; print('D-1 ratio>=1.7: n', len(c1), 'exit share', c1.is_exit.mean().round(3), ' not reduced:', (~c1.is_exit).sum())
c2 = B[(B.day == 'D-1') & (B.ratio_cheapest < 1.2)]; print('D-1 ratio<1.2: n', len(c2), 'exit share', c2.is_exit.mean().round(3), ' exits:', c2.is_exit.sum())
c1 = B[(B.day == 'D0') & (B.ratio_cheapest >= 1.7)]; print('D0 ratio>=1.7: n', len(c1), 'exit share', c1.is_exit.mean().round(3))
# outcome of reductions: price change over the slot after exit vs retained (association with subsequent move)
x = B[B.day == 'D-1']; print('mean d_price/price after exit vs retained (D-1):', (x[x.is_exit].d_price / x[x.is_exit].price).mean().round(3), (x[x.action == 'RETAINED'].d_price / x[x.action == 'RETAINED'].price).mean().round(3))
B.to_csv(f'{RES}/position_transitions_body_enriched.csv', index=False)
