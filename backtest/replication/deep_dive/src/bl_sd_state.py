"""Solo decode step 3: state at each solo decision (burst) vs control minutes of the same cycle and right: last-sold contract premium ratio (current/sale price; previous close and current-minute low/high), average short-book ratio of the right, book delta signed toward the right, CE/PE short-lot imbalance, minutes since last sale on the right, spot move since that sale. Outputs bl_sd_state.pkl.gz, bl_sd_state_auc.csv, bl_summary_sd2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata, norm
import bl_ohlc, bl_sd_build
OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); B = pd.read_pickle(f'{OUT}/bl_sd_bursts.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); R = {}; rng = np.random.default_rng(5)
rows = []
for i, r in enumerate(CY.itertuples()):
    u, e = r.und, r.expiry; o = OH[(u, e)]; op = OP[(u, e)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; step = ref.STEP[u]
    sells = D[(D.cid == i) & ~D.deep].sort_values('te'); bod = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row'])
    bb = B[B.cid == i]; qs = [(t, cp, 1) for t, cp in zip(bb.te, bb.cp)]
    for cp in ('CE', 'PE'):
        for t in rng.uniform(33360, 55800, 300): qs.append((t, cp, 0))
    for t, cp, y in qs:
        j = int((t - 33300) // 60)
        if j < 2 or j > 374: continue
        prev = sells[(sells.cp == cp) & (sells.te < t - 0.5)]
        if not len(prev): continue
        last = prev.iloc[-1]; k = ki.get(last.strike)
        p_prev = op[(cp, 'close')][k, j - 1] if k is not None else np.nan; p_ext = (op[(cp, 'low')][k, j] if k is not None else np.nan)
        # short book of this right and the other: average entry and mark
        z = bod[bod.te < t - 0.5]; pos = {}
        for q in z.itertuples():
            key = (q.cp, int(q.strike)); n, a = pos.get(key, (0, 0.0))
            pos[key] = (n + q.lots, (a * n + q.px_avg * q.lots) / (n + q.lots)) if q.role == 'open_short' else (max(n - q.lots, 0), a)
        S_ = o.close.values[j - 1]; atm = K[np.argmin(np.abs(K - S_))]; straddle = op[('CE', 'close')][ki[int(atm)], j - 1] + op[('PE', 'close')][ki[int(atm)], j - 1]; sig = straddle / (0.7979 * S_)
        book = {}; delta = 0.0
        for (c_, kk), (n, a) in pos.items():
            if n <= 0 or kk not in ki: continue
            px = op[(c_, 'close')][ki[kk], j - 1]; nm, dn = book.get(c_, (0.0, 0.0)); book[c_] = (nm + n * px, dn + n * a)
            d1 = np.log(S_ / kk) / sig + sig / 2; dl = norm.cdf(d1) if c_ == 'CE' else norm.cdf(d1) - 1; delta += -n * dl
        other = 'PE' if cp == 'CE' else 'CE'; sgn = 1 if cp == 'CE' else -1
        lots = {c_: sum(n for (cc, kk), (n, a) in pos.items() if cc == c_) for c_ in ('CE', 'PE')}
        rows.append(dict(cid=i, cp=cp, y=y, t=t, last_ratio_prev=p_prev / last.px, last_ratio_ext=(p_ext / last.px) if cp else np.nan, min_since_last=(t - last.te) / 60, last_typ=last.typ,
                         spot_move_since_last=-sgn * (S_ - o.close.values[min(max(int((last.te - 33300) // 60) - 1, 0), 374)]) / step, own_book=book.get(cp, (np.nan, np.nan))[0] / book.get(cp, (np.nan, 1))[1] if cp in book else np.nan,
                         other_book=book[other][0] / book[other][1] if other in book else np.nan, delta_toward=sgn * delta, imbalance=lots[cp] - lots[other], hour=t / 3600))
X = pd.DataFrame(rows); X.to_pickle(f'{OUT}/bl_sd_state.pkl.gz')
def auc(s, y): m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
y = X.y.values; half = X.cid.values % 2 == 0; out = []
for v in ('last_ratio_prev', 'last_ratio_ext', 'min_since_last', 'spot_move_since_last', 'own_book', 'other_book', 'delta_toward', 'imbalance', 'hour'):
    x = X[v].values.astype(float); out.append(dict(variable=v, AUC=auc(x, y), AUC_even=auc(x[half], y[half]), AUC_odd=auc(x[~half], y[~half]), median_events=np.nanmedian(x[y == 1]), median_controls=np.nanmedian(x[y == 0])))
U = pd.DataFrame(out); U.round(3).to_csv(f'{OUT}/bl_sd_state_auc.csv', index=False); print(U.round(3).to_string(index=False))
E1 = X[X.y == 1]; print('last-sold premium ratio at solo decisions, quantiles:', E1.last_ratio_prev.quantile([.1, .25, .5, .75, .9]).round(3).to_dict())
print('histogram of last ratio (events vs controls):'); bins = [0, .5, .7, .8, .85, .9, .95, 1, 1.05, 1.1, 1.2, 1.5, 10]; print(pd.DataFrame({'events': np.histogram(E1.last_ratio_prev.dropna(), bins)[0], 'controls': np.histogram(X[X.y == 0].last_ratio_prev.dropna(), bins)[0]}, index=[f'{a}-{b}' for a, b in zip(bins[:-1], bins[1:])]).T.to_string())
print('spot move since last sale (favourable steps), events quantiles:', E1.spot_move_since_last.quantile([.1, .25, .5, .75, .9]).round(2).to_dict())
R['auc'] = U.round(4).to_dict('records'); rec('sd2', R)
