"""Tracker study block T1 (plan BODY_REACTIVE_TRACKER_PLAN.md): second-of-minute structure and per-cycle counts. Outputs bl_trk_seconds.csv, bl_trk_counts.csv, bl_summary_trk1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import chisquare, spearmanr
R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); ch = Chain()
rows = []
for nm, d in (('reactive pairs', Pr[Pr.reactive]), ('scheduled (timetable) pairs', Pr[Pr.sched])):
    sec = (d.te.values % 60).astype(int); h = np.bincount(sec, minlength=60); band = [int(h[i:i + 10].sum()) for i in range(0, 60, 10)]; exp = len(d) / 6
    rows.append(dict(group=nm, n=len(d), **{f'sec {i}-{i + 9}': b for i, b in zip(range(0, 60, 10), band)}, chi2_p_uniform=chisquare(h).pvalue, share_first_10s=band[0] / len(d), expected_if_uniform=1 / 6))
    R[nm] = dict(band=band, p=float(chisquare(h).pvalue))
# a possible per-minute tracker would act in a narrow second window; take the reactive pairs with the strictest alternative: counts by exact second 0-5 vs 55-59
r = Pr[Pr.reactive]; sec = (r.te.values % 60).astype(int); R['react_share_0_5s'] = float((sec < 6).mean()); R['react_share_54_59s'] = float((sec >= 54).mean()); R['uniform_share_6s'] = 0.1
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_trk_seconds.csv', index=False); print(S.round(3).T.to_string())
# per-cycle counts (all cycles in the cycle list, D-1)
cl = pd.read_csv(f'{OUT}/bl_size_cycles.csv')[['und', 'expiry']]; cnt = Pr[Pr.reactive].groupby(['und', 'expiry']).size().rename('reactive_pairs'); C = cl.merge(cnt.reset_index(), on=['und', 'expiry'], how='left').fillna({'reactive_pairs': 0})
g = P.groupby(['und', 'expiry']).agg(la_breakout_minutes=('bkLA60', lambda s: int((s != 0).sum())), causal_breakout_minutes=('bk60', lambda s: int((s != 0).sum())), pair_minutes=('y', 'sum'), minutes=('y', 'size')).reset_index(); C = C.merge(g, on=['und', 'expiry'], how='left'); C.to_csv(f'{OUT}/bl_trk_counts.csv', index=False)
x = C.reactive_pairs.values; R['cycles_total'] = int(len(C)); R['cycles_with_pairs'] = int((x > 0).sum()); R['mean'] = float(x.mean()); R['var'] = float(x.var(ddof=1)); R['dispersion_var_over_mean'] = float(x.var(ddof=1) / x.mean()); R['min_max'] = [int(x.min()), int(x.max())]; R['median'] = float(np.median(x))
m = C.la_breakout_minutes.notna(); R['spearman_pairs_vs_la_breakout_minutes'] = [float(v) for v in spearmanr(C.reactive_pairs[m], C.la_breakout_minutes[m])]; R['spearman_pairs_vs_causal_breakout_minutes'] = [float(v) for v in spearmanr(C.reactive_pairs[m], C.causal_breakout_minutes[m])]
O = load_orders(); O1 = O[(O.dayno == 0) & (O.module == 'num')]
bbl = [int(O1[(O1.und == r.und) & (O1.expiry == r.expiry) & (O1.role == 'cover_short')].lots.sum()) for r in C.itertuples()]; sch = [int(Pr[(Pr.und == r.und) & (Pr.expiry == r.expiry)].sched.sum()) for r in C.itertuples()]
R['spearman_pairs_vs_buyback_lots'] = [float(v) for v in spearmanr(C.reactive_pairs, bbl)]; R['spearman_pairs_vs_scheduled_pairs'] = [float(v) for v in spearmanr(C.reactive_pairs, sch)]; R['count_dispersion_chi2_p_lower'] = None
print(json.dumps(R, indent=1, default=float)); print(C.describe().round(2).T)
rec('trk1', R)
