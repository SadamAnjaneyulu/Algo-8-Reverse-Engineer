"""Look-back study part 2: (7) live-spot proxy (linear interpolation between the last two minute closes by the order's second) — is the strike consistent with the LIVE spot at the order second rather than the last completed bar? (8) hazard ratio flat vs moving market with cluster bootstrap. Output bl_lb_live.csv, bl_summary_lb2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(411); R = {}; D = pd.read_pickle(f'{OUT}/bl_lb_events.pkl'); ch = Chain(); rows = []
for r in D.itertuples():
    c = ch.cyc(r.und, r.expiry); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; j = r.j; f = r.sec / 60.0; step = r.step; near = lambda s: K[np.argmin(np.abs(K - s))]
    live = sp[j - 1] + f * (sp[j] - sp[j - 1]); live15 = sp[j - 16] + f * (sp[j - 15] - sp[j - 16])   # same point 15 minutes earlier
    atm_live = near(live); s_live = np.sign(live - live15)
    rows.append((r.cid, r.sec, float(atm_live + s_live * step == r.strike), float(atm_live == r.strike), float(near(live) == near(sp[j - 1])), r.__getattribute__('_9') if False else None))
L = pd.DataFrame(rows, columns=['cid', 'sec', 'hit_live_proxy', 'atm_live_hit', 'atm_same', 'x']).drop(columns='x'); L['hit_bar'] = D['hit|rolling 15'].values; L['sb'] = pd.cut(L.sec, [-1, 9, 19, 29, 39, 49, 59])
T = L.groupby('sb', observed=True).agg(n=('cid', 'size'), hit_bar=('hit_bar', 'mean'), hit_live_proxy=('hit_live_proxy', 'mean'), atm_live_hit=('atm_live_hit', 'mean')); T.round(3).reset_index().assign(sb=lambda d: d.sb.astype(str)).to_csv(f'{OUT}/bl_lb_live.csv', index=False); print(T.round(3).to_string()); R['bar_hit'] = float(L.hit_bar.mean()); R['live_hit'] = float(L.hit_live_proxy.mean()); R['bar_vs_sec_rho'] = float(stats.spearmanr(L.sec, L.hit_bar)[0]); R['live_vs_sec_rho'] = float(stats.spearmanr(L.sec, L.hit_live_proxy)[0])
cid = L.cid.values; ucy = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in ucy}; bs = []
for _ in range(400): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bs.append(L.hit_live_proxy.values[ii].mean() - L.hit_bar.values[ii].mean())
R['live_minus_bar_ci'] = [float(np.quantile(bs, .025)), float(np.quantile(bs, .975)), float(np.mean(L.hit_live_proxy) - np.mean(L.hit_bar))]; print(f"bar-based rule hit {R['bar_hit']:.3f}; live-proxy rule hit {R['live_hit']:.3f}; difference CI {R['live_minus_bar_ci']}; Spearman(second, hit): bar {R['bar_vs_sec_rho']:.2f}, live {R['live_vs_sec_rho']:.2f}")
# late seconds only (>= 40 s): is the live proxy better?
late = L.sec >= 40; R['late_bar'] = float(L[late].hit_bar.mean()); R['late_live'] = float(L[late].hit_live_proxy.mean()); R['late_n'] = int(late.sum()); print(f"seconds >= 40 (n={late.sum()}): bar {R['late_bar']:.3f}, live proxy {R['late_live']:.3f}")
# ---- hazard ratio flat vs moving
P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); W = P[(P.j >= 75) & (P.j < 360)].copy(); W['g'] = W.und + W.expiry; W['flat'] = (W.ch15.abs() < 0.02); ug = W.g.unique(); ix = {c: np.where(W.g.values == c)[0] for c in ug}; y = W.yR.values; fl = W.flat.values
def hr(ii): a = y[ii][fl[ii]].mean(); b = y[ii][~fl[ii]].mean(); return b / a if a > 0 else np.nan
est = hr(np.arange(len(W))); bs = [hr(np.concatenate([ix[c] for c in rng.choice(ug, len(ug))])) for _ in range(400)]; R['hazard_ratio_moving_vs_flat'] = [float(est), float(np.nanquantile(bs, .025)), float(np.nanquantile(bs, .975))]; R['flat_share_of_minutes'] = float(fl.mean()); print(f"hazard moving / flat (|15-min move| < 0.02% = flat; {fl.mean():.2f} of minutes): {est:.2f} (CI {np.nanquantile(bs, .025):.2f}-{np.nanquantile(bs, .975):.2f})")
# up vs down hazard (moving only)
mv = W[~W.flat]; up = mv[mv.ch15 > 0].yR.mean() * 1000; dn = mv[mv.ch15 < 0].yR.mean() * 1000; R['hazard_up_down'] = [float(up), float(dn)]; print(f'moving only: up {up:.1f} vs down {dn:.1f} per 1000')
rec('lb2', R)
