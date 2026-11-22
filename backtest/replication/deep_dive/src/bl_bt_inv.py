"""Buy-back third pass, step 1 (descriptive): what does the trigger level co-move with? For every buy-back order on a lot in loss (decision price > entry decision price of the cheapest open lot):
ratio (decision / entry) and points (decision - entry) vs entry price, underlying, time of day, minutes since the lot's sale, ATM straddle at entry, D-1 date. Spearman correlations; log-log slope of (decision - entry) on entry per underlying (slope 1 = fixed ratio, slope 0 = fixed points).
Outputs bl_bt_inv.csv, bl_summary_bt1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); R = {}; rows = []
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); book = {}
    op = OP[(r.und, r.expiry)]; K = op['K']; c = OH[(r.und, r.expiry)].close.values
    for q in z.itertuples():
        k = (q.cp, int(q.strike))
        if q.role == 'open_short': book.setdefault(k, []).extend([(q.ref_px, q.te)] * int(q.lots)); continue
        lots = book.get(k, [])
        if not lots: continue
        a = int(np.argmin([l_[0] for l_ in lots])); e, te0 = lots[a]; je = min(max(int((te0 - 33300) // 60), 1), 374); ak = int(np.argmin(np.abs(K - c[je - 1])))
        strad = op[('CE', 'close')][ak, je - 1] + op[('PE', 'close')][ak, je - 1]
        rows.append(dict(cid=i, und=r.und, unit=r.unit, version=r.version, d1=r.d1, te=q.te, hour=q.te / 3600, cp=q.cp, entry=e, dec=q.ref_px, ratio=q.ref_px / e, pts=q.ref_px - e, rs_lot=(q.ref_px - e) * r.unit, mins_held=(q.te - te0) / 60, strad_entry=strad, pts_over_strad=(q.ref_px - e) / strad if strad > 0 else np.nan, n_open=len(lots)))
        lots.pop(a); book[k] = lots
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_bt_inv.csv', index=False); L = X[X.ratio > 1]; print('buy-back orders', len(X), 'in loss', len(L))
for und, g in L.groupby('und'):
    sl = np.polyfit(np.log(g.entry), np.log(g.pts), 1)[0]; R[und] = dict(n=len(g), slope_logpts_on_logentry=float(sl), **{f'rho_ratio_{v}': float(spearmanr(g.ratio, g[v])[0]) for v in ('entry', 'hour', 'mins_held', 'strad_entry', 'n_open')}, ratio_cv=float(g.ratio.std() / g.ratio.mean()), pts_cv=float(g.pts.std() / g.pts.mean()), pts_over_strad_cv=float(g.pts_over_strad.std() / g.pts_over_strad.mean()))
    print(und, {k: round(v, 3) for k, v in R[und].items()})
    print('   ratio by entry-price quintile', g.groupby(pd.qcut(g.entry, 5)).ratio.median().round(3).to_dict())
    print('   ratio by hour', g.groupby(g.hour.astype(int)).ratio.median().round(3).to_dict())
    print('   ratio by minutes held', g.groupby(pd.cut(g.mins_held, [0, 15, 30, 60, 120, 240, 400])).ratio.median().round(3).to_dict())
rec('bt1', R)
