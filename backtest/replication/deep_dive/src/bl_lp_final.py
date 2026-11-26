"""Lump study step 6: (a) size models, leave-one-cycle-out (log-linear OLS on main decisions): S_h; S_h + und; S_h + lump price; S_h + und + price; loss at lump strike; all. MAE (lots), median abs error %, within 5 lots.
(b) lump strike rule, out-of-fold (halves): % OTM of spot, sigma*sqrt(T) units (ATM straddle), premium = k x ATM same-right price, delta target; exact / within one strike.
(c) D0 fate of the lump: v_ D0 orders (role, time), share of lump lots sold on D0, sale price / purchase price.
Outputs bl_lp_size.csv, bl_lp_strike.csv, bl_lp_d0.csv, bl_summary_lp6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import norm
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); D = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); R = {}
M = D[D.main == 1].reset_index(drop=True).copy(); M['nifty'] = (M.und == 'NIFTY').astype(int); M['loss_rs'] = M.loss_at_KL_pts * M.unit; y = np.log(M.lots.clip(lower=1))
feats = {'S_h': ['lS'], 'S_h + und': ['lS', 'nifty'], 'S_h + lump price': ['lS', 'lpx'], 'S_h + und + lump price': ['lS', 'nifty', 'lpx'], 'loss at lump strike': ['lloss'], 'S_h + und + price + loss': ['lS', 'nifty', 'lpx', 'lloss']}
M['lS'] = np.log(M.S_h); M['lpx'] = np.log(M.px); M['lloss'] = np.log(M.loss_rs); res = []
for nm, cols in feats.items():
    p = np.zeros(len(M))
    for i in range(len(M)):
        tr = np.arange(len(M)) != i; A = np.c_[np.ones(tr.sum()), M.loc[tr, cols].values]; b = np.linalg.lstsq(A, y[tr], rcond=None)[0]; p[i] = np.exp(np.r_[1, M.loc[i, cols].values] @ b)
    e = np.abs(np.round(p) - M.lots); res.append(dict(model=nm, MAE_lots=e.mean(), median_abs_err_pct=float(np.median(e / M.lots) * 100), within_5_lots=float((e <= 5).mean()), within_10_lots=float((e <= 10).mean())))
S = pd.DataFrame(res); S.round(3).to_csv(f'{OUT}/bl_lp_size.csv', index=False); print(S.round(2).to_string(index=False)); R['size'] = S.round(4).to_dict('records')
# (b) strike
rows = []
for x in D.itertuples():
    r = CY.iloc[x.cid]; op = OP[(r.und, r.expiry)]; K = op['K']; j = min(int((x.t - 33300) // 60), 374); sg = 1 if x.cp == 'CE' else -1; S0 = x.spot; a = np.argmin(np.abs(K - S0))
    sig = (op[('CE', 'close')][a, j - 1] + op[('PE', 'close')][a, j - 1]) / (0.7979 * S0); otmK = K[sg * (K - S0) > 0]; prices = np.array([op[(x.cp, 'close')][np.where(np.abs(K - k) < 1)[0][0], j - 1] for k in otmK])
    rows.append(dict(cid=x.cid, und=x.und, strike=x.strike, S0=S0, sig=sig, sg=sg, step=ref.STEP[r.und], K=otmK, P=prices, atm=x.atm_px))
B = pd.DataFrame(rows); halves = [B.cid % 2 == 0, B.cid % 2 == 1]
def rule(df, kind, v):
    out = []
    for z in df.itertuples():
        if kind == 'pct': t = z.S0 * (1 + z.sg * v / 100); kk = z.K[np.argmin(np.abs(z.K - t))]
        elif kind == 'sigma': t = z.S0 * (1 + z.sg * v * z.sig); kk = z.K[np.argmin(np.abs(z.K - t))]
        elif kind == 'premium': kk = z.K[np.argmin(np.abs(np.log(np.maximum(z.P, 1e-3) / (v * z.atm))))]
        else:
            d = np.abs(norm.cdf(np.log(z.S0 / z.K) / z.sig + z.sig / 2) - (1 if z.sg < 0 else 0)) if False else np.abs(norm.cdf(z.sg * (np.log(z.S0 / z.K) / z.sig + z.sig / 2))); kk = z.K[np.argmin(np.abs(d - v))]
        out.append((kk == z.strike, abs(kk - z.strike) <= z.step))
    o = np.array(out); return o[:, 0].mean(), o[:, 1].mean()
grids = {'pct': np.arange(0.5, 3.01, 0.05), 'sigma': np.arange(0.5, 4.01, 0.05), 'premium': np.arange(0.01, 0.3, 0.005), 'delta': np.arange(0.01, 0.4, 0.005)}; res = []
for kd, g in grids.items():
    oof = []
    for h in (0, 1):
        tr, te = B[halves[h]], B[halves[1 - h]]; v = max(g, key=lambda v: rule(tr, kd, v)[0]); ex, w1 = rule(te, kd, v); oof.append((v, ex, w1, len(te)))
    n = sum(o[3] for o in oof); res.append(dict(rule=kd, param_fold=f'{oof[0][0]:.3f}/{oof[1][0]:.3f}', exact=sum(o[1] * o[3] for o in oof) / n, within1=sum(o[2] * o[3] for o in oof) / n))
T = pd.DataFrame(res); T.round(3).to_csv(f'{OUT}/bl_lp_strike.csv', index=False); print(T.round(3).to_string(index=False)); R['strike'] = T.round(4).to_dict('records')
# (c) D0 fate
v = O[O.module == 'v_']; f = v.groupby(['dayno', 'role']).lots.sum().to_dict(); print(f)
d0 = v[(v.dayno == 1)]; d0 = d0.assign(hhmm=(d0.te // 3600).astype(int).astype(str) + ':' + ((d0.te % 3600) // 60).astype(int).astype(str).str.zfill(2))
q = []
for (u, e), g in v.groupby(['und', 'expiry']):
    b = g[(g.dayno == 0) & (g.role == 'open_long')]; s = g[(g.dayno == 1) & (g.role == 'close_long')]
    if len(b): q.append(dict(und=u, expiry=e, bought=int(b.lots.sum()), sold_d0=int(s.lots.sum()), buy_px=float((b.lots * b.px_avg).sum() / b.lots.sum()), sell_px=float((s.lots * s.px_avg).sum() / s.lots.sum()) if len(s) else np.nan, first_sale=float(s.tod.min() / 3600) if len(s) else np.nan, last_sale=float(s.tod.max() / 3600) if len(s) else np.nan, n_sale_orders=len(s)))
Q = pd.DataFrame(q); Q.to_csv(f'{OUT}/bl_lp_d0.csv', index=False); R['d0'] = dict(roles=str(f), share_sold_d0=float(Q.sold_d0.sum() / Q.bought.sum()), sell_over_buy_median=float((Q.sell_px / Q.buy_px).median()), first_sale_q=Q.first_sale.quantile([.1, .5, .9]).round(3).to_dict(), last_sale_q=Q.last_sale.quantile([.1, .5, .9]).round(3).to_dict(), sale_orders_median=float(Q.n_sale_orders.median()))
print(R['d0']); print(Q.round(2).to_string(index=False)); rec('lp6', R)
# (d) contract-level D0 closure of lump contracts by any module (modules share contracts, so lot ownership is a convention)
cc = []
for (u, e), g in O[(O.module == 'v_') & (O.dayno == 0)].groupby(['und', 'expiry']):
    d0 = O[(O.und == u) & (O.expiry == e) & (O.dayno == 1)]
    for (cp, k), gg in g.groupby(['cp', 'strike']):
        x = d0[(d0.cp == cp) & (d0.strike == k) & (d0.side == 'Sell')]; cc.append(dict(und=u, expiry=e, cp=cp, strike=k, bought=int(gg.lots.sum()), **{f'sold_{m}': int(x[x.module == m].lots.sum()) for m in ('v_', 'num', 'h_', 's_', 'm_')}))
CC = pd.DataFrame(cc); CC['sold_all'] = CC.filter(like='sold_').sum(axis=1); CC.to_csv(f'{OUT}/bl_lp_d0_contracts.csv', index=False)
R['d0_contracts'] = dict(n=len(CC), fully_closed_any_module=float((CC.sold_all >= CC.bought).mean()), none_sold=float((CC.sold_all == 0).mean()), sold_by_module=CC.filter(like='sold_').sum().to_dict()); print(R['d0_contracts']); rec('lp6', R)
