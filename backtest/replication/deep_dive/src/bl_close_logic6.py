"""Buy-back study, step 7: buy-back CLUSTERS (single-link, gap <= 3 s, same cycle-day, any strike/right). Pre-registered after the below-1.2x classification left a large residual and a first look showed sub-1.2x buy-backs sit within seconds of stop-like ones.
Stop-like = ratio >= 1.5x against the cheapest open entry (LOW reference; decision price = limit/1.15). Questions: how many sub-1.2x buy-backs belong to a cluster that contains a stop-like member (vs a time-shifted null); which lots join (same right / same strike / distance in steps) vs the lots that were available.
Outputs outputs/bl_close_clusters_{D-1,D0}.csv, bl_summary_close6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
F = pd.read_csv(f'{OUT}/bl_close_orders_flags.csv'); rng = np.random.default_rng(3); R = {}; W = 3.0; STOP = 1.5; LOWTHR = 1.2
def clusterize(d):
    d = d.sort_values(['und', 'expiry', 'te']).reset_index(drop=True); gap = d.groupby(['und', 'expiry']).te.diff(); d['cl'] = ((gap.isna()) | (gap > W)).cumsum(); return d
for day in ('D-1', 'D0'):
    d = clusterize(F[F.day == day].copy()); d['stoplike'] = d.r_low >= STOP; d['sub'] = d.r_low < LOWTHR
    C = d.groupby('cl').agg(und=('und', 'first'), expiry=('expiry', 'first'), n=('lots', 'size'), strikes=('strike', 'nunique'), rights=('cp', 'nunique'), stop=('stoplike', 'sum'), sub=('sub', 'sum'), rmax=('r_low', 'max'), rmin=('r_low', 'min'), t0=('te', 'min'), t1=('te', 'max'))
    C['has_stop'] = C.stop > 0; C.to_csv(f'{OUT}/bl_close_clusters_{day}.csv')
    print(f'\n===== {day}: {len(d)} orders in {len(C)} clusters; size q50/75/90/max {C.n.quantile([.5, .75, .9, 1]).tolist()}; singletons {(C.n == 1).mean():.2f}')
    R[f'{day}_clusters'] = len(C); R[f'{day}_cluster_singletons'] = float((C.n == 1).mean()); R[f'{day}_cluster_size_q'] = C.n.quantile([.5, .75, .9, 1]).tolist(); R[f'{day}_cluster_has_stop'] = float(C.has_stop.mean())
    d = d.merge(C[['n', 'stop', 'has_stop']].rename(columns={'n': 'cl_n', 'stop': 'cl_stop', 'has_stop': 'cl_has_stop'}), left_on='cl', right_index=True)
    sub = d[d['sub']]; ns = len(sub); sub_in = sub[(sub.cl_n > 1)]; sub_with_stop = sub[sub.cl_has_stop]
    # null: shift the sub-1.2 order times circularly within the cycle-day (cluster-with-stop = a stop-like order within W of it)
    obs = []; null = []
    for (u, e), g in d.groupby(['und', 'expiry']):
        te = g.te.values; st = te[g.stoplike.values]; sb = te[g['sub'].values & ~g.stoplike.values]
        if len(st) == 0 or len(sb) == 0: continue
        lo, hi = te.min(), te.max(); span = max(hi - lo, 1); obs.append((np.mean([(np.abs(st - t) <= W).any() for t in sb]), len(sb))); nn = []
        for _ in range(60): sh = lo + ((sb - lo + rng.uniform(0, span)) % span); nn.append(np.mean([(np.abs(st - t) <= W).any() for t in sh]))
        null.append((np.mean(nn), len(sb)))
    w = np.array([x[1] for x in obs]); o = float(np.average([x[0] for x in obs], weights=w)); nl = float(np.average([x[0] for x in null], weights=w))
    R[f'{day}_sub_n'] = ns; R[f'{day}_sub_within3s_of_stop'] = o; R[f'{day}_sub_within3s_null'] = nl; R[f'{day}_sub_in_multi_cluster'] = float((sub.cl_n > 1).mean()); R[f'{day}_sub_in_cluster_with_stop'] = float(sub.cl_has_stop.mean())
    print(f'sub-1.2x buy-backs (LOW ref): {ns}; in a multi-order cluster: {(sub.cl_n > 1).mean():.3f}; in a cluster containing a stop-like (>=1.5x) member: {sub.cl_has_stop.mean():.3f}; within {W:.0f} s of a stop-like order: {o:.3f} vs shifted null {nl:.3f}')
    # who joins: among sub-1.2x orders in clusters with a stop-like member: same right / same strike as the nearest stop-like order, strike distance
    rows = []
    for cl, g in d[d.cl_has_stop].groupby('cl'):
        S = g[g.stoplike]; B = g[g['sub']]
        for b in B.itertuples():
            s = S.iloc[np.argmin(np.abs(S.te.values - b.te))]; rows.append((b.cp == s.cp, b.strike == s.strike, abs(b.strike - s.strike) / ref.STEP[b.und]))
    if rows:
        J = pd.DataFrame(rows, columns=['same_right', 'same_strike', 'dist_steps']); R[f'{day}_join_same_right'] = float(J.same_right.mean()); R[f'{day}_join_same_strike'] = float(J.same_strike.mean()); R[f'{day}_join_dist_q'] = J.dist_steps.quantile([.5, .75, .9]).tolist()
        print(f'joiners (n={len(J)}): same right as the stop-like order {J.same_right.mean():.2f}, same strike {J.same_strike.mean():.2f}, distance in steps q50/75/90 {J.dist_steps.quantile([.5, .75, .9]).tolist()}')
    # cluster composition for clusters with a stop-like member: share of the right's open lots closed
    # what fraction of ALL orders are in clusters that have a stop-like member
    R[f'{day}_orders_in_stop_clusters'] = float(d.cl_has_stop.mean()); print(f'orders in clusters with a stop-like member: {d.cl_has_stop.mean():.3f}; sub-1.2x orders NOT in such a cluster: {(~sub.cl_has_stop).sum()} of {ns} ({(~sub.cl_has_stop).mean():.3f})')
    res = sub[~sub.cl_has_stop]; R[f'{day}_residual_n'] = len(res)
    if len(res): print(f'  residual: median ratio(LOW) {res.r_low.median():.2f}, in multi-order cluster {(res.cl_n > 1).mean():.2f}, at end of day (>=15:10) {(res.tod >= 15 * 3600 + 600).mean():.2f}, empties strike {res.empties.mean():.2f}, re-sold within 60 s (same right) {res.resell_any.mean():.2f}')
    d.to_csv(f'{OUT}/bl_close_orders_clusters_{day}.csv', index=False)
# window sensitivity (single-link clustering at W seconds): share of sub-1.2x orders whose cluster has a stop-like member / a member >= 1.2x
d1 = F[F.day == 'D-1'].copy(); sens = {}
for Wn in (3, 10, 30, 60):
    z = d1.sort_values(['und', 'expiry', 'te']).reset_index(drop=True); gp = z.groupby(['und', 'expiry']).te.diff(); z['cl'] = ((gp.isna()) | (gp > Wn)).cumsum(); z['rmax'] = z.groupby('cl').r_low.transform('max'); z['n'] = z.groupby('cl').cl.transform('size'); sb = z[z.r_low < LOWTHR]
    sens[str(Wn)] = dict(clusters=int(z.cl.nunique()), ge15=float((sb.rmax >= STOP).mean()), ge12=float((sb.rmax >= 1.2).mean()), singleton=float((sb.n == 1).mean()))
R['D-1_window_sensitivity'] = sens; print('window sensitivity (D-1):', {k: {a: round(b, 3) for a, b in v.items()} for k, v in sens.items()})
rec('close6', R)
