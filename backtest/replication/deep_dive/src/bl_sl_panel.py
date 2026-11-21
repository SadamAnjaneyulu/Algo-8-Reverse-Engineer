"""After-15:00 solo, step 3: minute x right panel 15:00-15:29 (label = >= 1 regular late solo lot on that right in the minute) with feature blocks: clock, market/indicators (fresh extremes 5/15/60 on true OHLC, favourable moves 1/5/15/30, range position 60, RSI14, minute range), volatility (realised 15/30, ATM straddle change 5/15/30, straddle level), option microstructure (ATM volume net of Algo 8 vs its 30-min mean, target-strike volume), Greeks (whole-book delta toward the right, gamma), inventory (own/other short lots, own/other book ratio, tilt), order flow (buy-backs own/other right last 2 min, lumps last 5 min, wing closes last 2 min, reactive pair in the minute), history (solo lots on the right before 15:00, minutes since the last sale on the right).
Leave-one-cycle-out logistic / boosting by block; univariate AUCs. Outputs bl_sl_panel.pkl.gz, bl_sl_auc.csv, bl_sl_blocks.csv, bl_summary_sl3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata, norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import bl_ohlc, bl_sd_build
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); R = {}; unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}
rows = []
for i, r in enumerate(CY.itertuples()):
    u, e = r.und, r.expiry; o = OH[(u, e)]; h, l, c = o.high.values, o.low.values, o.close.values; op = OP[(u, e)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; step = ref.STEP[u]; cb = CycleBook(u, e, unit[(u, e)])
    z = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0)]; dd = D[D.cid == i]; sol = dd[(dd.typ == 'solo') & ~dd.deep]; g = Pr[(Pr.und == u) & (Pr.expiry == e)]
    atmv = lambda j: np.nansum([op[(cp, 'close')][ki[int(K[np.argmin(np.abs(K - c[j - 1]))])], j - 1] for cp in ('CE', 'PE')])
    for j in range(345, 375):
        T0 = 33300 + 60 * j; pm = j - 1; st = cb.state(T0, c[pm], pm); dlt = st.get('delta', np.nan)
        dc = c[1:j] - c[:j - 1]; up = np.clip(dc[-14:], 0, None).sum(); dn = -np.clip(dc[-14:], None, 0).sum(); rsi = 100 - 100 / (1 + up / dn) if dn > 0 else 100.0
        w60h, w60l = h[j - 60:j].max(), l[j - 60:j].min(); s_now = atmv(j); s5 = atmv(j - 5); s15 = atmv(j - 15); s30 = atmv(j - 30)
        k_atm = int(K[np.argmin(np.abs(K - c[pm]))])
        c_ = ch.cyc(u, e); kk = c_['_si'].get(k_atm); vt = (c_[(0, 'CE', 'volume')][kk, pm] + c_[(0, 'PE', 'volume')][kk, pm]) if kk is not None else np.nan; vm = np.nanmean([(c_[(0, 'CE', 'volume')][kk, x] + c_[(0, 'PE', 'volume')][kk, x]) for x in range(pm - 30, pm)]) if kk is not None else np.nan
        own_fill = z[(z.strike == k_atm) & (((z.te - 33300) // 60) == pm)].lots.sum() * unit[(u, e)]
        for cp in ('CE', 'PE'):
            sg = 1 if cp == 'CE' else -1; oth = 'PE' if cp == 'CE' else 'CE'; prev = dd[(dd.cp == cp) & (dd.te < T0)]
            fav = lambda n: -sg * (c[pm] - c[pm - n]) / step
            rows.append(dict(cid=i, j=j, cp=cp, y=int(((sol.cp == cp) & (((sol.te - 33300) // 60) == j)).any()), minute=j - 345, is_ce=int(cp == 'CE'),
                             bk5=int((l[j] < l[j - 5:j].min()) if cp == 'CE' else (h[j] > h[j - 5:j].max())), bk15=int((l[j] < l[j - 15:j].min()) if cp == 'CE' else (h[j] > h[j - 15:j].max())), bk60=int((l[j] < w60l) if cp == 'CE' else (h[j] > w60h)),
                             fav1=fav(1), fav5=fav(5), fav15=fav(15), fav30=fav(30), pos60=((c[pm] - w60l) / max(w60h - w60l, 1e-9) - 0.5) * (-sg), rsi_fav=(50 - rsi) * sg, mrange=(h[j] - l[j]) / step,
                             rv15=np.abs(np.diff(c[pm - 15:pm + 1])).sum() / step, rv30=np.abs(np.diff(c[pm - 30:pm + 1])).sum() / step, strad=s_now, strad_chg5=s_now / s5 - 1 if s5 > 0 else np.nan, strad_chg15=s_now / s15 - 1 if s15 > 0 else np.nan, strad_chg30=s_now / s30 - 1 if s30 > 0 else np.nan,
                             vol_rel=(vt - own_fill) / vm if vm and vm > 0 else np.nan, delta_toward=sg * dlt, gamma=st.get('gamma', np.nan), short_lots=st.get('short_lots', np.nan), net_lots=st.get('net_lots', np.nan),
                             bb_own_2m=int(((z.role == 'cover_short') & (z.cp == cp) & (z.te >= T0 - 120) & (z.te < T0)).sum()), bb_oth_2m=int(((z.role == 'cover_short') & (z.cp == oth) & (z.te >= T0 - 120) & (z.te < T0)).sum()), lump_5m=int(((z.module == 'v_') & (z.te >= T0 - 300) & (z.te < T0)).sum()),
                             wclose_2m=int(((z.role == 'close_long') & (z.te >= T0 - 120) & (z.te < T0)).sum()), react_min=int((((g[g.reactive].te - 33300) // 60) == j).any()), solo_before15=int(sol[(sol.cp == cp) & (sol.te < 54000)].lots.sum()),
                             min_since_last=(T0 - prev.te.max()) / 60 if len(prev) else 400.0, last_typ_solo=int(len(prev) > 0 and prev.typ.iloc[-1] == 'solo')))
X = pd.DataFrame(rows); X.to_pickle(f'{OUT}/bl_sl_panel.pkl.gz'); print(X.shape, 'positives', int(X.y.sum()))
def auc(s, y): m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
B = dict(clock=['minute'], market=['bk5', 'bk15', 'bk60', 'fav1', 'fav5', 'fav15', 'fav30', 'pos60', 'rsi_fav', 'mrange'], volatility=['rv15', 'rv30', 'strad', 'strad_chg5', 'strad_chg15', 'strad_chg30'], micro=['vol_rel'], greeks=['delta_toward', 'gamma'], inventory=['short_lots', 'net_lots'], flow=['bb_own_2m', 'bb_oth_2m', 'lump_5m', 'wclose_2m', 'react_min'], history=['solo_before15', 'min_since_last', 'last_typ_solo'])
y = X.y.values; half = X.cid.values % 2 == 0; U = []
for b, cols in B.items():
    for v in cols: x = X[v].values.astype(float); U.append(dict(block=b, variable=v, AUC=auc(x, y), AUC_even=auc(x[half], y[half]), AUC_odd=auc(x[~half], y[~half])))
U = pd.DataFrame(U); U['s'] = (U.AUC - .5).abs(); U = U.sort_values('s', ascending=False).drop(columns='s'); U.round(3).to_csv(f'{OUT}/bl_sl_auc.csv', index=False); print(U.head(16).round(3).to_string(index=False))
cid = X.cid.values
def loco(cols, kind):
    Xm = X[cols + ['is_ce']].values.astype(float); p = np.zeros(len(y))
    for c_ in np.unique(cid):
        te = cid == c_; tr = ~te
        if kind == 'lr': med = np.nanmedian(Xm[tr], 0); med = np.where(np.isnan(med), 0, med); Xt = np.where(np.isnan(Xm), med, Xm); sc = StandardScaler().fit(Xt[tr]); p[te] = LogisticRegression(C=0.3, max_iter=500).fit(sc.transform(Xt[tr]), y[tr]).predict_proba(sc.transform(Xt[te]))[:, 1]
        else: p[te] = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(Xm[tr], y[tr]).predict_proba(Xm[te])[:, 1]
    return p
M = []
for b, cols in list(B.items()) + [('all', sum(B.values(), []))]:
    for kd in ('lr', 'gb'): p = loco(cols, kd); M.append(dict(block=b, model=kd, AUC=auc(p, y)))
M = pd.DataFrame(M); M.round(3).to_csv(f'{OUT}/bl_sl_blocks.csv', index=False); print(M.pivot(index='block', columns='model', values='AUC').round(3)); R['univariate'] = U.round(4).to_dict('records'); R['blocks'] = M.round(4).to_dict('records'); R['n'] = len(X); R['pos'] = int(y.sum()); rec('sl3', R)
