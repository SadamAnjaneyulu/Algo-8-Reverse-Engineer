"""Activation study step 4 (post-hoc after the single-feature diagnostic, labelled): spot-minus-moving-average gap as the activation variable. Minute-level causal panel (D-1, 10:30-15:15, no timetable wave). gap_N = (close[j-1] - mean(close[j-1-N .. j-2])) / step.
AUC of |gap_N| for reactive-pair minutes by N (cluster bootstrap), hazard by |gap| bins and signed gap, threshold scan, halves/underlyings. Outputs bl_act_gap_auc.csv, bl_act_gap_hazard.csv, bl_summary_act4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(521); R = {}; P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); P = P[(P.j >= 75) & (P.j < 360)].reset_index(drop=True); ch = Chain(); NS = [3, 5, 10, 15, 20, 30, 45, 60, 90, 120]; cols = {f'gap{N}': np.full(len(P), np.nan) for N in NS}; cols['gap_pct60'] = np.full(len(P), np.nan)
for (u, e), idx in P.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; js = P.loc[idx, 'j'].values
    for N in NS: cols[f'gap{N}'][idx] = [(sp[j - 1] - sp[max(j - 1 - N, 0):j - 1].mean()) / step if j - 1 > 0 else np.nan for j in js]
    cols['gap_pct60'][idx] = [(sp[j - 1] / sp[max(j - 61, 0):j - 1].mean() - 1) * 100 for j in js]
for N in NS:
    pass
for (u, e), idx in P.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; js = P.loc[idx, 'j'].values
    for N in NS: cols.setdefault(f'mv{N}', np.full(len(P), np.nan))[idx] = [(sp[j - 1] - sp[max(j - 1 - N, 0)]) / step for j in js]
for k, v in cols.items(): P[k] = v
P['g'] = P.und + P.expiry; g = P.g.values; y = P.yR.values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; bs_idx = [np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(150)]; yrs = sorted(P.expiry.unique()); med = yrs[len(yrs) // 2]
def auc(x, y_): m = ~np.isnan(x); x, y_ = x[m], y_[m]; n1 = y_.sum(); n0 = len(y_) - n1; r = stats.rankdata(x); return (r[y_ == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
rows = []
for N in NS:
    x = np.abs(P[f'gap{N}'].values); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in bs_idx]; nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(10)]; h1 = auc(x[(P.expiry < med).values], y[(P.expiry < med).values]); h2 = auc(x[(P.expiry >= med).values], y[(P.expiry >= med).values]); rows.append((N, a, np.quantile(bs, .025), np.quantile(bs, .975), np.max(nul), h1, h2))
mrows = []
for N in NS: x = np.abs(P[f'mv{N}'].values); mrows.append((N, auc(x, y)))
A = pd.DataFrame(rows, columns=['N_min', 'AUC_abs_gap', 'lo', 'hi', 'null_max', 'half1', 'half2']); A['AUC_abs_move_L'] = [m[1] for m in mrows]; R['auc_move_by_L'] = {str(m[0]): float(m[1]) for m in mrows}; A.round(4).to_csv(f'{OUT}/bl_act_gap_auc.csv', index=False); print(A.round(3).to_string(index=False)); R['auc_by_N'] = A.round(4).to_dict('list'); R['best_N'] = int(A.sort_values('AUC_abs_gap', ascending=False).N_min.iloc[0])
Nb = 60; P['absg'] = P[f'gap{Nb}'].abs(); bins = [0, .05, .1, .2, .3, .5, .75, 1, 1.5, 10]; H = P.groupby(pd.cut(P.absg, bins), observed=True).yR.agg(['size', 'sum']); H['per1000'] = (H['sum'] / H['size'] * 1000).round(1); H['step_vs_prev'] = (H.per1000 / H.per1000.shift(1)).round(2); print(f'\nreactive-pair hazard by |spot - SMA{Nb}| (steps), D-1 10:30-15:15'); print(H.to_string())
Hs = P.groupby(pd.cut(P[f'gap{Nb}'], [-10, -1, -.5, -.2, -.05, .05, .2, .5, 1, 10]), observed=True).yR.agg(['size', 'sum']); Hs['per1000'] = (Hs['sum'] / Hs['size'] * 1000).round(1); print('\nhazard by signed gap'); print(Hs.to_string())
out = []
for nm, Q in (('all', P), ('first half', P[P.expiry < med]), ('second half', P[P.expiry >= med]), ('NIFTY', P[P.und == 'NIFTY']), ('SENSEX', P[P.und == 'SENSEX'])):
    for lab, lo, hi in (('|gap| < 0.1 step', 0, .1), ('0.1 - 0.5', .1, .5), ('>= 0.5', .5, 99)):
        m = (Q.absg >= lo) & (Q.absg < hi); out.append((nm, lab, int(m.sum()), int(Q.yR[m].sum()), Q.yR[m].mean() * 1000))
Hh = pd.DataFrame(out, columns=['subset', 'gap_group', 'cycle_minutes', 'events', 'per1000']); Hh.round(2).to_csv(f'{OUT}/bl_act_gap_hazard.csv', index=False); print(Hh.round(1).to_string(index=False)); R['hazard_groups'] = Hh.round(3).to_dict('list'); R['hazard_bins'] = H.reset_index().assign(absg=lambda d: d.absg.astype(str)).to_dict('list')
R['share_minutes_small_gap'] = float((P.absg < 0.1).mean()); R['share_events_small_gap'] = float((P.absg[P.yR == 1] < 0.1).mean())
# sign agreement of the gap with the strike side (re-check on the minute panel events with strike info is in the previous study); here: events by sign of gap
ev = P[P.yR == 1]; R['events_gap_above'] = float((ev[f'gap{Nb}'] > 0).mean()); R['controls_gap_above'] = float((P[f'gap{Nb}'] > 0).mean())
rec('act4', R)
