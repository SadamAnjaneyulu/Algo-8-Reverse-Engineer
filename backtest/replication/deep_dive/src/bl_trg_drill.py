"""Trigger study step 4 (plan block C/E drill-down): which single feature separates firing from non-firing breakout minutes; inter-pair gaps; repeat-strike and same-side effects.
Outputs bl_trg_uni.csv, bl_trg_gaps.csv, bl_trg_repeat.csv, bl_summary_trg3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
rng = np.random.default_rng(31); R = {}; P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz').reset_index(drop=True); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); Pr = Pr[Pr.reactive].sort_values(['und', 'expiry', 'te'])
def auc(s, y):
    m = ~np.isnan(s); s = s[m]; y = y[m]; n1 = y.sum(); n0 = len(y) - n1
    return np.nan if n1 < 5 or n0 < 5 else (rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
# 1. univariate AUC within look-ahead breakout minutes and within causal breakout minutes
rows = []; feats = ['depth60', 'run60', 'width60', 'posprev60', 'depth45', 'depth90', 'min_since_1030', 'age_pair', 'age_react', 'age_sell', 'age_bb', 'age_oth', 'n_react_sofar', 'n_sell_sofar', 'n_bb_sofar', 'last_react_same_side', 'short_ce', 'short_pe', 'short_tot', 'tgt_short_ce', 'tgt_short_pe', 'tgt_pair_open', 'centre_d', 'prem_tgt', 'prem_ratio', 'vol_tgt', 'vol_rel', 'absm1', 'absm5', 'vol30']
for nm, sel in (('LOOK-AHEAD breakout minutes', P.bkLA60 != 0), ('causal breakout minutes', P.bk60 != 0)):
    d = P[sel]; y = d.y.values; half = d.cid.values % 2 == 0
    for f in feats:
        x = d[f].values.astype(float); a = auc(x, y); rows.append(dict(population=nm, feature=f, AUC=a, AUC_even=auc(x[half], y[half]), AUC_odd=auc(x[~half], y[~half]), n=len(d), n_pairs=int(y.sum())))
U = pd.DataFrame(rows); U['abs_edge'] = (U.AUC - .5).abs(); U = U.sort_values(['population', 'abs_edge'], ascending=[True, False]).drop(columns='abs_edge'); U.round(3).to_csv(f'{OUT}/bl_trg_uni.csv', index=False); print(U.round(3).to_string(index=False))
# 2. inter-pair gaps (distinct pair times > 3 s apart) within cycle
gaps = []
for (u, e), g in Pr.groupby(['und', 'expiry']):
    t = np.sort(g.te.values); t = t[np.r_[True, np.diff(t) > 3]]; gaps += list(np.diff(t))
gaps = np.array(gaps); G = pd.DataFrame({'quantile': [0, .01, .05, .1, .25, .5, .75, .9], 'gap_seconds': np.quantile(gaps, [0, .01, .05, .1, .25, .5, .75, .9])}); G.to_csv(f'{OUT}/bl_trg_gaps.csv', index=False); R['gaps_n'] = int(len(gaps)); R['gaps_q'] = G.set_index('quantile').gap_seconds.round(1).to_dict(); print(G.round(1).to_string(index=False)); R['share_gap_lt_60s'] = float((gaps < 60).mean()); R['share_gap_lt_120s'] = float((gaps < 120).mean())
# 3. repeat-strike: does the pair strike repeat the previous reactive pair strike / an already open pair?
Pr = Pr.copy(); Pr['prev_strike'] = Pr.groupby(['und', 'expiry']).strike.shift(1); Pr['rep'] = (Pr.strike == Pr.prev_strike).astype(float).where(Pr.prev_strike.notna())
R['share_repeat_prev_reactive_strike'] = float(Pr.rep.mean()); R['n_pairs'] = int(len(Pr))
d = P[P.bkLA60 != 0].copy(); d['tgt_eq_last'] = np.nan
last_k = {}
for (u, e), g in Pr.groupby(['und', 'expiry']): last_k[(u, e)] = (np.sort(g.te.values), g.sort_values('te').strike.values)
vals = []
for r in d.itertuples():
    ts, ks = last_k[(r.und, r.expiry)]; T0 = 33300 + 60 * r.j; i = np.searchsorted(ts, T0 - 3) - 1; vals.append(float(ks[i] == r.target) if i >= 0 else np.nan)
d['tgt_eq_last'] = vals
out = []
for col in ('tgt_eq_last', 'tgt_pair_open', 'last_react_same_side'):
    t = d[d[col].notna()].groupby(col).agg(minutes=('y', 'size'), pair_minutes=('y', 'sum')); t['per1000'] = 1000 * t.pair_minutes / t.minutes; t['feature'] = col; out.append(t.reset_index().rename(columns={col: 'value'}))
RP = pd.concat(out); RP.round(1).to_csv(f'{OUT}/bl_trg_repeat.csv', index=False); print(RP.round(1).to_string(index=False))
# 4. firing hazard in LA breakout minutes by minutes-since-last-pair, finer, and by depth
d['age_min'] = (d.age_react / 60); fine = pd.cut(d.age_min, [0, 1, 2, 3, 5, 8, 12, 20, 40, 1000]); t = d.groupby(fine, observed=True).agg(minutes=('y', 'size'), pair_minutes=('y', 'sum')); t['per1000'] = 1000 * t.pair_minutes / t.minutes; print(t.round(1)); R['fine_age'] = {str(k): [int(v.minutes), int(v.pair_minutes), float(v.per1000)] for k, v in t.iterrows()}
dd = pd.qcut(d.depth60, 5, duplicates='drop'); t2 = d.groupby(dd, observed=True).agg(minutes=('y', 'size'), pair_minutes=('y', 'sum')); t2['per1000'] = 1000 * t2.pair_minutes / t2.minutes; print(t2.round(1)); R['depth_quint'] = {str(k): [int(v.minutes), int(v.pair_minutes), float(v.per1000)] for k, v in t2.iterrows()}
rec('trg3', R); print(json.dumps(R, default=float)[:1200])
