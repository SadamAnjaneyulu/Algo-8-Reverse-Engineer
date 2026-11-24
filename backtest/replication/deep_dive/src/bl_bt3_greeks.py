"""Physical decomposition of the combined backtest P&L (plan reports/ALPHA_SOURCE_PLAN.md, Method 1).
Per cycle, per contract, per minute (D-1 09:15 -> D0 15:14): MtM change = pos(t-1) x (mark(t) - mark(t-1)) + q(t) x (mark(t) - fill price); the first term is split with Black-Scholes sensitivities at t-1
(delta, gamma, theta [calendar time to expiry 15:30 on D0, r = 6.5%, no dividend], vega, residual); the second is the EXECUTION term. The sum equals the cycle's gross cash P&L (reconciliation check).
Marks = minute closes; the D0 first step (t = 375) contains the overnight gap and the first minute. Run: OMP_NUM_THREADS=1 python bl_bt3_greeks.py"""
import sys, os, time, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, datetime as dt
from scipy.special import ndtr
from multiprocessing import Pool
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RES = f'{OUT}/bt3_results'; BT3 = f'{OUT}/bt3'; RATE = 0.065
def bs(S, K, T, sig, is_call):
    sq = np.sqrt(T); d1 = (np.log(S / K) + (RATE + 0.5 * sig ** 2) * T) / (sig * sq); d2 = d1 - sig * sq; disc = np.exp(-RATE * T); pdf = np.exp(-0.5 * d1 ** 2) / np.sqrt(2 * np.pi)
    price = np.where(is_call, S * ndtr(d1) - K * disc * ndtr(d2), K * disc * ndtr(-d2) - S * ndtr(-d1)); delta = np.where(is_call, ndtr(d1), ndtr(d1) - 1); gamma = pdf / (S * sig * sq); vega = S * pdf * sq
    dcdT = np.where(is_call, S * pdf * sig / (2 * sq) + RATE * K * disc * ndtr(d2), S * pdf * sig / (2 * sq) - RATE * K * disc * ndtr(-d2)); return price, delta, gamma, vega, dcdT
def implied_vol(price, S, K, T, is_call):
    lo = np.full(price.shape, 0.01); hi = np.full(price.shape, 4.0)
    for _ in range(45):
        mid = 0.5 * (lo + hi); p = bs(S, K, T, mid, is_call)[0]; up = p < price; lo = np.where(up, mid, lo); hi = np.where(up, hi, mid)
    return 0.5 * (lo + hi)
CLOCK = sys.argv[1] if len(sys.argv) > 1 else 'calendar'
def one(args):
    und, expiry, d1, d0, unit, split, tag, fills = args; cyc = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); f = fills; NT = 750
    S = np.concatenate([cyc['spot1'].close.values, cyc['spot0'].close.values]).astype(float)
    t_dt = [dt.datetime.fromisoformat(d1) + dt.timedelta(hours=9, minutes=15 + j) for j in range(375)] + [dt.datetime.fromisoformat(d0) + dt.timedelta(hours=9, minutes=15 + j) for j in range(375)]
    exp = dt.datetime.fromisoformat(d0) + dt.timedelta(hours=15, minutes=30); T = np.array([max((exp - x).total_seconds() / (365.25 * 86400), 1e-7) for x in t_dt]) if CLOCK == 'calendar' else np.array([(750 - t) / 93750.0 for t in range(750)])                          # calendar time, or trading minutes (375 per day, 250 days)
    contracts = sorted({(r.cp, int(r.strike)) for r in f.itertuples()}); nC = len(contracts); M = np.full((nC, NT), np.nan); pos = np.zeros((nC, NT)); q = np.zeros((nC, NT)); pq = np.zeros((nC, NT)); ex = np.zeros((nC, NT))
    for ci, (cp, k) in enumerate(contracts):
        for sess, (o, off) in enumerate(((cyc['opt1'], 0), (cyc['opt0'], 375))):
            i = int(np.searchsorted(o['K'], k))
            if i < len(o['K']) and o['K'][i] == k: M[ci, off:off + 375] = o[(cp, 'close')][i]
        s = f[(f.cp == cp) & (f.strike == k)]
        for r in s.itertuples():
            t = r.day * 375 + int(r.j); qq = r.side * r.lots; q[ci, t] += qq; pq[ci, t] += qq * r.price
    for ci in range(nC):                                                                    # marks: forward fill, then back fill; where a fill exists use its price if the mark is missing
        s = pd.Series(M[ci]); s = s.ffill().bfill(); M[ci] = s.values
    pos = np.cumsum(q, axis=1); posp = np.concatenate([np.zeros((nC, 1)), pos[:, :-1]], axis=1)
    Mp = np.concatenate([M[:, :1], M[:, :-1]], axis=1); dC = M - Mp; Sp = np.concatenate([S[:1], S[:-1]]); dS = S - Sp; Tp = np.concatenate([T[:1], T[:-1]]); dT = Tp - T
    Kk = np.array([k for _, k in contracts], float)[:, None]; isc = np.array([cp == 'CE' for cp, _ in contracts])[:, None]
    intr = np.where(isc, np.maximum(Sp[None, :] - Kk, 0), np.maximum(Kk - Sp[None, :], 0)); valid = (Mp - intr > 0.05) & (Mp > 0.2)
    Sg = np.broadcast_to(Sp[None, :], M.shape); Tg = np.broadcast_to(Tp[None, :], M.shape); Kg = np.broadcast_to(Kk, M.shape); Cg = np.broadcast_to(isc, M.shape)
    sig_prev = np.full(M.shape, np.nan); sig_now = np.full(M.shape, np.nan)
    sig_prev[valid] = implied_vol(Mp[valid], Sg[valid], Kg[valid], Tg[valid], Cg[valid])
    intr_now = np.where(isc, np.maximum(S[None, :] - Kk, 0), np.maximum(Kk - S[None, :], 0)); vnow = (M - intr_now > 0.05) & (M > 0.2); Tn = np.broadcast_to(T[None, :], M.shape); Sn = np.broadcast_to(S[None, :], M.shape)
    sig_now[vnow] = implied_vol(M[vnow], Sn[vnow], Kg[vnow], Tn[vnow], Cg[vnow])
    delta = np.zeros(M.shape); gamma = np.zeros(M.shape); vega = np.zeros(M.shape); dcdT = np.zeros(M.shape)
    _, dl, ga, ve, dc = bs(Sg[valid], Kg[valid], Tg[valid], sig_prev[valid], Cg[valid]); delta[valid] = dl; gamma[valid] = ga; vega[valid] = ve; dcdT[valid] = dc
    dsig = np.where(valid & vnow, sig_now - sig_prev, 0.0); c_delta = delta * dS[None, :]; c_gamma = 0.5 * gamma * dS[None, :] ** 2; c_theta = -dcdT * dT[None, :]; c_vega = vega * dsig; c_res = dC - c_delta - c_gamma - c_theta - c_vega
    c_delta[~valid] = 0; c_gamma[~valid] = 0; c_theta[~valid] = 0; c_vega[~valid] = 0; c_res = np.where(valid, dC - c_delta - c_gamma - c_theta - c_vega, dC)
    sess = np.zeros(NT, int); sess[1:375] = 0; sess[375] = 1; sess[376:] = 2                                    # 0 D-1 day, 1 overnight step (+ first D0 minute), 2 D0 day
    ex_t = q * M - pq; gross = float(-pq.sum() * unit)
    rows = []
    for side_nm, mask in (('short', posp < 0), ('long', posp > 0)):
        for sn in (0, 1, 2):
            sm = (sess == sn)[None, :] & mask; w = posp * sm * unit
            rows.append(dict(und=und, expiry=expiry, split=split, side=side_nm, session=['D-1 day', 'overnight step', 'D0 day'][sn], delta=float((w * c_delta).sum()), gamma=float((w * c_gamma).sum()), theta=float((w * c_theta).sum()), vega=float((w * c_vega).sum()), resid=float((w * c_res).sum()), holding=float((w * dC).sum())))
    ex_total = float((ex_t * unit).sum()); hold_total = float(sum(r['holding'] for r in rows)); sold = float(-(pq[q < 0].sum()) * unit)
    return rows, dict(und=und, expiry=expiry, split=split, gross=gross, holding=hold_total, execution=ex_total, recon_diff=gross - hold_total - ex_total, premium_sold=sold, valid_share=float(valid[posp != 0].mean()) if (posp != 0).any() else np.nan)
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); t0 = time.time(); jobs = []
    for split, tag in (('IS', 'IS_B-V2'), ('OOS', 'OOS_B-V2'), ('LIVE_FITTED', 'LIVE_FITTED_A-V1')):
        F = pd.read_csv(f'{RES}/{tag}_fills.csv.gz'); G = {k: v for k, v in F.groupby(['und', 'expiry'])}
        for r in T0[(T0.split3 == split) & T0.ok].itertuples(): jobs.append((r.und, r.expiry, r.d1, r.d0, float(r.unit), split, tag, G[(r.und, r.expiry)]))
    with Pool(4) as p: res = p.map(one, jobs, chunksize=2)
    comp = pd.DataFrame([r for rs, _ in res for r in rs]); recon = pd.DataFrame([i for _, i in res]); comp.to_csv(f'{RES}/greeks_components_{CLOCK}.csv', index=False); recon.to_csv(f'{RES}/greeks_reconciliation_{CLOCK}.csv', index=False)
    print('cycles', len(recon), 'in', round(time.time() - t0), 's; max |reconciliation diff| (Rs):', recon.recon_diff.abs().max(), '; mean valid-Greek share of held contract-minutes:', round(recon.valid_share.mean(), 3))
    t = comp.groupby('split')[['delta', 'gamma', 'theta', 'vega', 'resid', 'holding']].sum().div(recon.groupby('split').size(), axis=0).round(0); t['execution'] = recon.groupby('split').execution.mean().round(0); t['gross'] = recon.groupby('split').gross.mean().round(0); print('mean per cycle (Rs):'); print(t.to_string())
    print(comp.groupby(['side', 'session'])[['delta', 'gamma', 'theta', 'vega', 'resid', 'holding']].sum().div(len(recon)).round(0).to_string())
