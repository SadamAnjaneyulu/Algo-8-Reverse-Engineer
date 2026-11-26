"""Plan reports/UNRESOLVED_THREE_PLAN.md, Question 1 (E1-E5): why is the expiry-day premium rich? Settlement = official close of the D0 date from the repo's daily NIFTY / SENSEX files.
Outputs outputs/unres/prem_cycles.csv, prem_moneyness.csv, prem_flow.csv, prem_pin.csv. Run: OMP_NUM_THREADS=1 python bl_unres_premium.py"""
import sys, os, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
import bl_thesis_tests as TT
OUT = TT.OUT; BT3 = TT.BT3; UN = f'{OUT}/unres'; REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(OUT)))), 'data_validation', 'reference'); STEP = TT.KSTEP; S_ = None
DIST = [0.005, 0.01, 0.015, 0.02, 0.03]
def init():
    global S_; import data as D; S_ = D.Src()
def raw_arrays(f):
    h = f.datetime.str.slice(11, 16); hh = h.str.slice(0, 2).astype(int) * 60 + h.str.slice(3, 5).astype(int) - 555; f = f.assign(j=hh)[(hh >= 0) & (hh < 375)]
    K = np.array(sorted(f.strike.unique()), float); ki = {k: i for i, k in enumerate(K)}; out = {'K': K}
    for cp in ('CE', 'PE'):
        z = f[f.right == cp]; i = z.strike.map(ki).values; j = z.j.values
        for fld in ('close', 'volume', 'open_interest'):
            a = np.full((len(K), 375), np.nan); a[i, j] = z[fld].values; out[(cp, fld)] = a
    return out
def one(a):
    und, expiry, d0, split, settle = a; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); s0, o0 = c['spot0'], c['opt0']; st = STEP[und]; U = TT.LOT[und]
    O0, C0 = s0.open.values.astype(float), s0.close.values.astype(float); r = dict(und=und, expiry=expiry, split=split, settle=settle, spot_1500=O0[345], spot_1529=C0[374], spot_1400=O0[285], spot_0916=O0[1])
    # ---- E1: settlement averaging
    r['x_settle'] = float(np.log(settle / O0[345])); r['x_print'] = float(np.log(C0[374] / O0[345])); r['gap_settle_print_bp'] = 1e4 * float(np.log(settle / C0[374]))
    i = TT.atm_i(o0, O0[345]); K = o0['K'][i]; pin = TT.straddle(o0, i, 345, 'open'); r['k1500'] = K; r['prem_1500'] = pin; r['pay_settle'] = abs(settle - K); r['pay_print'] = abs(C0[374] - K); r['w_1500'] = TT.w_atm(o0, O0[345], 345, 'open')
    # ---- E5: where the D0 straddle premium accrues (ATM at 09:16, same strike)
    i = TT.atm_i(o0, O0[1]); K = o0['K'][i]; p0 = TT.straddle(o0, i, 1, 'open'); r['k0916'] = K; r['prem_0916'] = p0
    for nm, j in (('1400', 285), ('1514', 359)): r[f'prem_{nm}'] = TT.straddle(o0, i, j, 'open')
    r['pay_settle_0916'] = abs(settle - K); r['pay_print_0916'] = abs(C0[374] - K)
    # ---- E3: moneyness
    mon = []
    for d in DIST:
        for cp, sg in (('PE', -1), ('CE', 1)):
            kt = O0[1] * (1 + sg * d); ii = int(np.argmin(np.abs(o0['K'] - kt))); k = o0['K'][ii]; pr = TT.px(o0, cp, 'open', ii, 1)
            if np.isfinite(pr): mon.append(dict(und=und, expiry=expiry, split=split, side=cp, dist=d, strike=k, price=pr, payoff=max(settle - k, 0) if cp == 'CE' else max(k - settle, 0), atm_prem=p0))
    # ---- raw volume / OI for E2 and E4
    f = S_.csv(f'normalized/{und.lower()}/options/exp{expiry}_{d0}.csv'); R = raw_arrays(f)
    oi = np.nan_to_num(np.nanmax(np.where(np.arange(375) <= 285, np.nan_to_num(R[('CE', 'open_interest')], nan=-1), -1), axis=1), nan=0) if False else None
    pins = {}
    last = {}
    for cp in ('CE', 'PE'):
        a_ = R[(cp, 'open_interest')][:, :286]; ok = np.isfinite(a_); idx = np.where(ok.any(axis=1), (np.where(ok, np.arange(286), -1)).max(axis=1), -1); last[cp] = np.array([a_[n, idx[n]] if idx[n] >= 0 else 0.0 for n in range(len(a_))])
    tot = last['CE'] + last['PE']; near = np.abs(R['K'] - O0[285]) <= 0.02 * O0[285]
    if near.any() and tot[near].max() > 0: Kp = R['K'][near][int(np.argmax(tot[near]))]; r['pin_strike'] = Kp; r['pin_offset_steps'] = (Kp - O0[285]) / st; r['pin_dist_steps'] = abs(settle - Kp) / st; r['pin_oi_share'] = float(tot[near].max() / tot[near].sum())
    # ---- E4: signed volume vs next-block change in implied variance, D0, 15-minute blocks
    flow = []; blocks = list(range(1, 345, 15)); wb = []; sv = []; r2 = []
    for jb in blocks:
        i = TT.atm_i(o0, O0[jb]); K = o0['K'][i]; ii = int(np.searchsorted(R['K'], K)); s_ = 0.0
        if ii < len(R['K']) and R['K'][ii] == K:
            for cp in ('CE', 'PE'):
                cl = pd.Series(R[(cp, 'close')][ii]).ffill().values; vol = np.nan_to_num(R[(cp, 'volume')][ii]); d = np.sign(np.diff(cl, prepend=cl[0])); s_ += float(np.sum((d * vol)[jb:jb + 15]))
        sv.append(s_); wb.append(TT.w_atm(o0, O0[jb], jb, 'open')); r2.append(float(np.sum(np.diff(np.log(C0[jb - 1:jb + 15])) ** 2)) if jb >= 1 else np.nan)
    wb.append(TT.w_atm(o0, O0[blocks[-1] + 15], blocks[-1] + 15, 'open'))
    for k in range(len(blocks) - 1): flow.append(dict(und=und, expiry=expiry, split=split, block=k, sv=sv[k], dw=wb[k + 1] - wb[k], r2=r2[k], dw_next=wb[k + 2] - wb[k + 1] if k + 2 < len(wb) else np.nan, r2_next=r2[k + 1], dw_next_surprise=(wb[k + 2] - wb[k + 1] + r2[k + 1]) if k + 2 < len(wb) else np.nan, dw_surprise=wb[k + 1] - wb[k] + r2[k]))
    return r, mon, flow
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]; D = {}
    for u, f in (('NIFTY', 'yahoo_daily_NSEI.csv'), ('SENSEX', 'yahoo_daily_BSESN.csv')): d = pd.read_csv(f'{REF}/{f}'); D[u] = d.set_index('date_ist').close
    jobs = [(r.und, r.expiry, r.d0, r.split3, float(D[r.und].loc[r.d0])) for r in T0.itertuples()]
    with Pool(4, initializer=init) as p: res = p.map(one, jobs, chunksize=4)
    C = pd.DataFrame([a for a, _, _ in res]); M = pd.DataFrame([x for _, m, _ in res for x in m]); F = pd.DataFrame([x for _, _, fl in res for x in fl])
    C.to_csv(f'{UN}/prem_cycles.csv', index=False); M.to_csv(f'{UN}/prem_moneyness.csv', index=False); F.to_csv(f'{UN}/prem_flow.csv', index=False)
    print(len(C), 'cycles;', len(M), 'moneyness rows;', len(F), 'flow rows'); print(C[['x_settle', 'x_print', 'gap_settle_print_bp', 'pin_dist_steps', 'pin_oi_share']].describe().round(4).to_string())
