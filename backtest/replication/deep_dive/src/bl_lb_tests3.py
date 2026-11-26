"""Look-back study part 3: with the live-spot proxy, is the look-back length identifiable (is 15 special) and what do the remaining misses look like? Output bl_lb_live_scan.csv, bl_summary_lb3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(421); R = {}; D = pd.read_pickle(f'{OUT}/bl_lb_events.pkl'); ch = Chain(); Ls = [1, 2, 3, 5, 7, 10, 12, 14, 15, 16, 18, 20, 25, 30, 40, 45, 60, 90]; H = {L: [] for L in Ls}; off = []; offL = []
for r in D.itertuples():
    c = ch.cyc(r.und, r.expiry); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; j = r.j; f = r.sec / 60.0; step = r.step; near = lambda s: K[np.argmin(np.abs(K - s))]
    at = lambda k: sp[max(k - 1, 0)] + f * (sp[min(k, 374)] - sp[max(k - 1, 0)])           # live-time spot proxy "k minutes after the previous-bar index"
    live = at(j); atm = near(live)
    for L in Ls: H[L].append(float(atm + np.sign(live - at(j - L)) * step == r.strike))
    s15 = np.sign(live - at(j - 15)); off.append((r.strike - atm) / step * s15 if s15 != 0 else np.nan)
cid = D.cid.values; ucy = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in ucy}; bs_idx = [np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(400)]; rows = []
h15 = np.array(H[15])
for L in Ls: h = np.array(H[L]); d = [h[ii].mean() - h15[ii].mean() for ii in bs_idx]; rows.append((L, h.mean(), np.quantile(d, .025), np.quantile(d, .975)))
T = pd.DataFrame(rows, columns=['L_min', 'hit_rate_live_proxy', 'diff_vs_L15_lo', 'diff_vs_L15_hi']); T.round(4).to_csv(f'{OUT}/bl_lb_live_scan.csv', index=False); print(T.round(3).to_string(index=False)); R['live_scan'] = T.round(4).to_dict('list')
o = pd.Series(off).dropna(); R['live_offset_dist'] = o.round(0).value_counts(normalize=True).sort_index().round(3).to_dict(); print('offset in the move direction (live proxy, L=15):', R['live_offset_dist'])
rec('lb3', R)
