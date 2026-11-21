"""Tracker study T3 (POST-HOC): residuals of the stateful range-edge machine M1 (bar variant, N=70, K=12, frozen from the cross-validated search): what separates machine fires that match a pair from those that do not, and which pairs it misses.
Outputs bl_trk_resid_uni.csv, bl_trk_miss.csv, bl_summary_trk4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
sys.argv = ['x']; exec(open('bl_trk_sim2.py').read().split("CONFIGS = [")[0])      # reuse CYC, run(), match() definitions
R = {}; N0, K0 = 70, 12
P = P.reset_index(drop=True); key = {(r.und, r.expiry): d['cid'] for r, d in zip(CY.itertuples(), CYC)}; P['cidx'] = [key[(u, e)] for u, e in zip(P.und, P.expiry)]
fire = {}; side = {}
for d in CYC:
    for f, s in run(d, 'M1', 'bar', N0, K0): fire[(d['cid'], f)] = 1; side[(d['cid'], f)] = s
P['fire'] = [fire.get((c, j), 0) for c, j in zip(P.cidx, P.j)]
A = {d['cid']: set(d['A']) for d in CYC}; P['near_pair'] = [int(any((j + o) in A[c] for o in (-1, 0, 1))) for c, j in zip(P.cidx, P.j)]
F = P[P.fire == 1].copy(); y = F.near_pair.values; R['fires'] = int(len(F)); R['fires_matching'] = int(y.sum()); R['precision'] = float(y.mean())
def auc(s, y):
    m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return np.nan if n1 < 5 or n0 < 5 else (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
feats = ['min_since_1030', 'age_pair', 'age_react', 'age_sell', 'age_bb', 'age_oth', 'n_react_sofar', 'n_sell_sofar', 'n_bb_sofar', 'last_react_same_side', 'short_ce', 'short_pe', 'short_tot', 'tgt_short_ce', 'tgt_short_pe', 'tgt_pair_open', 'centre_d', 'prem_tgt', 'prem_ratio', 'vol_tgt', 'vol_rel', 'absm1', 'absm5', 'vol30', 'depth60', 'width60', 'run60', 'posprev60']
half = (F.cidx.values % 2 == 0); rows = [dict(feature=f, AUC=auc(F[f].values.astype(float), y), AUC_even=auc(F[f].values[half].astype(float), y[half]), AUC_odd=auc(F[f].values[~half].astype(float), y[~half])) for f in feats]
U = pd.DataFrame(rows); U['edge'] = (U.AUC - .5).abs(); U = U.sort_values('edge', ascending=False).drop(columns='edge'); U.round(3).to_csv(f'{OUT}/bl_trk_resid_uni.csv', index=False); print(U.head(12).round(3).to_string(index=False))
# misses: actual pair minutes with no machine fire within +-1 minute
M = P[(P.y == 1)].copy(); M['machine_near'] = [int(any(fire.get((c, j + o), 0) for o in (-1, 0, 1))) for c, j in zip(M.cidx, M.j)]; R['pair_minutes'] = int(len(M)); R['pair_minutes_matched'] = int(M.machine_near.sum()); R['recall'] = float(M.machine_near.mean())
M['inside_range_prior60'] = (M.bkLA60 == 0).astype(int); M['LA_breakout'] = (M.bkLA60 != 0).astype(int); M['causal_breakout'] = (M.bk60 != 0).astype(int)
t = M.groupby('machine_near').agg(n=('y', 'size'), la_breakout=('LA_breakout', 'mean'), causal_breakout=('causal_breakout', 'mean'), age_react_min=('age_react', lambda s: np.nanmedian(s) / 60), posprev60=('posprev60', lambda s: np.nanmedian(np.abs(s))), n_react_sofar=('n_react_sofar', 'mean'), minute_since_1030=('min_since_1030', 'mean')).reset_index(); t.round(3).to_csv(f'{OUT}/bl_trk_miss.csv', index=False); print(t.round(3).to_string(index=False)); R['miss'] = t.round(4).to_dict('records')
# do machine fires without a pair look like "ordinary" edge minutes? compare share of non-matching fires by side/time
F['hour'] = (F.min_since_1030 // 60 + 10.5).astype(int); print(F.groupby('hour').near_pair.agg(['size', 'mean']).round(3)); R['precision_by_hour'] = F.groupby('hour').near_pair.mean().round(3).to_dict()
print(F.groupby(F.n_react_sofar.clip(upper=12)).near_pair.agg(['size', 'mean']).round(3).T)
rec('trk4', R); print(json.dumps(R, default=float)[:900])
