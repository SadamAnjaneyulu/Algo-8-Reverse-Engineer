"""Solo decode step 8: reactive entries - number of pairs (multi-lot entries) and extra favourable-side lots ("attached solo") per fire, and what they depend on (break size, candle, time, earlier fires, book state, tilt, other-modules). Fire = reactive pair orders within 5 s; attached = regular solo lots within 3 s before to 10 s after the fire.
Outputs bl_sd_reactlots.csv, bl_sd_reactlots_assoc.csv, bl_summary_sd7.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
import bl_ohlc
OH = bl_ohlc.load(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); D = D[~D.deep]; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); R = {}; rows = []
for i, r in enumerate(CY.itertuples()):
    u, e = r.und, r.expiry; o = OH[(u, e)]; h, l, c = o.high.values, o.low.values, o.close.values; step = ref.STEP[u]
    g = Pr[(Pr.und == u) & (Pr.expiry == e) & Pr.reactive].sort_values('te'); z = D[D.cid == i]; t = g.te.values
    if not len(t): continue
    grp = np.r_[0, np.cumsum(np.diff(t) > 5)]; n_before = 0; last_t = None
    bod = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])]; sl = np.where(bod.role == 'open_short', bod.lots, -bod.lots)
    for gi in np.unique(grp):
        m = grp == gi; t0 = t[m][0]; j = int((t0 - 33300) // 60); k = g.strike.values[m][0]
        if j < 2 or j > 374: continue
        atm = round(c[j - 1] / step) * step; side = int(np.sign(k - atm)) or 1; fav = 'PE' if side > 0 else 'CE'
        w = z[(z.te >= t0 - 3) & (z.te <= t0 + 10) & (z.typ == 'solo')]; extra_fav = int((w.cp == fav).sum()); extra_oth = int((w.cp != fav).sum())
        clock = 33300 + 60 * j; b0 = (clock // 1800) * 1800; a = int(np.ceil((b0 - 3600 - 33300) / 60)); eidx = int(np.ceil((b0 - 33300) / 60)); H, L = h[max(a, 0):eidx].max(), l[max(a, 0):eidx].min()
        depth = ((h[j] - H) if side > 0 else (L - l[j])) / step; mt = bod.te.values < t0 - 0.5; ce = int(sl[mt & (bod.cp.values == 'CE')].sum()); pe = int(sl[mt & (bod.cp.values == 'PE')].sum())
        rows.append(dict(cid=i, und=u, t=t0, side=side, pairs=int(m.sum()), extra_fav=extra_fav, extra_other=extra_oth, depth=depth, minute_range=(h[j] - l[j]) / step, chan_width=(H - L) / step, min_in_candle=(clock % 1800) / 60, hour=t0 / 3600,
                         n_fires_before=n_before, min_since_last_fire=(t0 - last_t) / 60 if last_t else np.nan, tilt_fav=(ce - pe) * (1 if fav == 'CE' else -1), short_lots=ce + pe, move_open=(o.open.values[0] - c[j - 1]) / step * (-side), lot_unit=r.unit, v2=int(r.version == 'V2')))
        n_before += 1; last_t = t0
F = pd.DataFrame(rows); F['total_lots'] = 2 * F.pairs + F.extra_fav + F.extra_other; F.round(4).to_csv(f'{OUT}/bl_sd_reactlots.csv', index=False)
print('fires', len(F)); print('pairs per fire', F.pairs.value_counts().sort_index().to_dict()); print('extra favourable lots per fire', F.extra_fav.value_counts().sort_index().to_dict(), 'extra other-side lots', int(F.extra_other.sum()))
print(pd.crosstab(F.pairs, F.extra_fav))
out = []
for tgt in ('pairs', 'extra_fav'):
    for v in ('depth', 'minute_range', 'chan_width', 'min_in_candle', 'hour', 'n_fires_before', 'min_since_last_fire', 'tilt_fav', 'short_lots', 'move_open', 'side', 'v2', 'lot_unit'):
        x = F[v].values.astype(float); mm = ~np.isnan(x); rr, p = spearmanr(x[mm], F[tgt].values[mm]); out.append(dict(target=tgt, variable=v, spearman=rr, p=p))
A = pd.DataFrame(out).sort_values(['target', 'p']); A.round(4).to_csv(f'{OUT}/bl_sd_reactlots_assoc.csv', index=False); print(A.groupby('target').head(6).round(3).to_string(index=False))
R['pairs_dist'] = {int(k): int(v) for k, v in F.pairs.value_counts().sort_index().items()}; R['extra_dist'] = {int(k): int(v) for k, v in F.extra_fav.value_counts().sort_index().items()}; R['share_with_extra'] = float((F.extra_fav > 0).mean()); R['assoc'] = A.round(4).to_dict('records'); rec('sd7', R)
