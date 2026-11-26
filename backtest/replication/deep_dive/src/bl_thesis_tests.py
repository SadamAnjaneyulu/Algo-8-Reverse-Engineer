"""Market-level tests of the candidate design beliefs (plan reports/DESIGN_THESIS_PLAN.md). Uses only the 3-year D-1/D0 minute chains (outputs/bt3/*.pkl.gz),
not the strategy simulator. T1 segment short straddles + realised/implied variance; T2 15-minute block decay; T3 ladder-trigger continuation; T4 call vs put.
Output outputs/thesis/thesis_{t1,t2,t3_events,t3_cycles,t4}.csv and thesis_summary.json. Run: OMP_NUM_THREADS=1 python bl_thesis_tests.py"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.special import ndtr
from multiprocessing import Pool
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); BT3 = f'{OUT}/bt3'; TH = f'{OUT}/thesis'; os.makedirs(TH, exist_ok=True)
LOT = {'NIFTY': 65.0, 'SENSEX': 20.0}; KSTEP = {'NIFTY': 50.0, 'SENSEX': 100.0}; END0 = 359; END1 = 374; GATE = 60
def total_std(price, S, K, is_call):
    """Black (r = 0) total standard deviation s = sigma*sqrt(T) implied by one option price; clock-free. NaN if below intrinsic + 0.05."""
    intr = max(S - K, 0) if is_call else max(K - S, 0)
    if not np.isfinite(price) or price - intr < 0.05: return np.nan
    lo, hi = 1e-6, 0.5
    for _ in range(60):
        s = 0.5 * (lo + hi); d1 = (np.log(S / K) + 0.5 * s * s) / s; d2 = d1 - s
        p = S * ndtr(d1) - K * ndtr(d2) if is_call else K * ndtr(-d2) - S * ndtr(-d1)
        lo, hi = (s, hi) if p < price else (lo, s)
    return 0.5 * (lo + hi)
def atm_i(o, S):
    K = o['K']; return int(np.argmin(np.abs(K - S)))
def px(o, cp, field, i, j):
    v = o[(cp, field)][i, j]; return float(v) if np.isfinite(v) and v > 0 else np.nan
def w_atm(o, S, j, field='close'):
    """implied total variance at the ATM strike (mean of CE and PE implied total std, squared)"""
    i = atm_i(o, S); K = o['K'][i]; s = [total_std(px(o, cp, field, i, j), S, K, cp == 'CE') for cp in ('CE', 'PE')]; s = [x for x in s if np.isfinite(x)]
    return np.mean(s) ** 2 if s else np.nan
def straddle(o, i, j, field):
    a, b = px(o, 'CE', field, i, j), px(o, 'PE', field, i, j); return a + b if np.isfinite(a) and np.isfinite(b) else np.nan
def one(args):
    und, expiry, split = args; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); s1, s0, o1, o0 = c['spot1'], c['spot0'], c['opt1'], c['opt0']; L = LOT[und]
    O1, C1, H1, L1 = (s1[k].values.astype(float) for k in ('open', 'close', 'high', 'low')); O0, C0, H0, L0 = (s0[k].values.astype(float) for k in ('open', 'close', 'high', 'low'))
    base = dict(und=und, expiry=expiry, split=split)
    # ---- T1: segment straddles and variance ratio
    t1 = []
    def seg(name, oa, ja, fa, Sa, ob, jb, fb, Sb, rv):
        ia = atm_i(oa, Sa); K = oa['K'][ia]; ib = int(np.searchsorted(ob['K'], K)); ok = ib < len(ob['K']) and ob['K'][ib] == K
        pin = straddle(oa, ia, ja, fa); pout = straddle(ob, ib, jb, fb) if ok else np.nan
        wa = w_atm(oa, Sa, ja, fa); wb = w_atm(ob, Sb, jb, fb)
        t1.append(dict(base, segment=name, strike=K, prem_in=pin, prem_out=pout, pnl_pts=pin - pout, pnl_rs=(pin - pout) * L, pnl_pct=(pin - pout) / pin, iv_used=wa - wb, rv=rv))
    r1 = np.concatenate([[np.log(C1[1] / O1[1])], np.diff(np.log(C1[1:END1 + 1]))]); seg('D-1 day', o1, 1, 'open', O1[1], o1, END1, 'close', C1[END1], float(np.sum(r1 ** 2)))
    seg('overnight', o1, END1, 'close', C1[END1], o0, 1, 'open', O0[1], float(np.log(O0[1] / C1[END1]) ** 2))
    seg('overnight (D0 09:15 open)', o1, END1, 'close', C1[END1], o0, 0, 'open', O0[0], float(np.log(O0[0] / C1[END1]) ** 2))
    r0 = np.concatenate([[np.log(C0[1] / O0[1])], np.diff(np.log(C0[1:END0])), [np.log(O0[END0] / C0[END0 - 1])]]); seg('D0 day', o0, 1, 'open', O0[1], o0, END0, 'open', O0[END0], float(np.sum(r0 ** 2)))
    # ---- T2: 15-minute blocks
    t2 = []
    for sess, (o, O, C, jmax) in (('D-1', (o1, O1, C1, END1)), ('D0', (o0, O0, C0, END0))):
        for ja in range(1, jmax - 14, 15):
            i = atm_i(o, O[ja]); pin = straddle(o, i, ja, 'open'); pout = straddle(o, i, ja + 14, 'close')
            t2.append(dict(base, session=sess, block_start=ja, pnl_pct=(pin - pout) / pin, pnl_pts=pin - pout, abs_move_bp=1e4 * abs(np.log(C[ja + 14] / O[ja]))))
    # ---- T3: ladder-trigger events (new 60-minute extreme at least one ladder step beyond the last event of that side)
    t3 = []
    for sess, (o, O, C, H, Lw, jmax, stp) in (('D-1', (o1, O1, C1, H1, L1, END1, 0.2 * KSTEP[und])), ('D0', (o0, O0, C0, H0, L0, END0, 0.05 * KSTEP[und]))):
        ref = {'dn': O[0], 'up': O[0]}
        for j in range(1, jmax):
            lo, hi = max(j - GATE, 0), j
            for side in ('dn', 'up'):
                hit = (Lw[j] < Lw[lo:hi].min() and ref['dn'] - Lw[j] > stp) if side == 'dn' else (H[j] > H[lo:hi].max() and H[j] - ref['up'] > stp)
                if not hit: continue
                ref[side] = Lw[j] if side == 'dn' else H[j]; sg = -1.0 if side == 'dn' else 1.0; S = C[j]; e = dict(base, session=sess, j=j, side=side)
                for h in (15, 30, 60):
                    e[f'fwd{h}_bp'] = sg * 1e4 * np.log(C[j + h] / S) if j + h <= jmax else np.nan
                Send = O[END0] if sess == 'D0' else C[END1]; e['fwd_end_bp'] = sg * 1e4 * np.log(Send / S)
                i = atm_i(o, S); K = o['K'][i]; lad, opp = ('CE', 'PE') if side == 'dn' else ('PE', 'CE')
                fe = 'open' if sess == 'D0' else 'close'; je = END0 if sess == 'D0' else END1
                e['lad_pts'] = px(o, lad, 'close', i, j) - px(o, lad, fe, i, je); e['opp_pts'] = px(o, opp, 'close', i, j) - px(o, opp, fe, i, je)
                if sess == 'D-1':                                                                                  # D-1 event held to D0 15:14
                    i0 = int(np.searchsorted(o0['K'], K)); okk = i0 < len(o0['K']) and o0['K'][i0] == K
                    e['lad_pts_toD0'] = px(o, lad, 'close', i, j) - px(o0, lad, 'open', i0, END0) if okk else np.nan
                    e['opp_pts_toD0'] = px(o, opp, 'close', i, j) - px(o0, opp, 'open', i0, END0) if okk else np.nan
                e['lot'] = L; t3.append(e)
    # ---- T4: short ATM call vs short ATM put, D-1 09:16 open -> D0 15:14 open
    i = atm_i(o1, O1[1]); K = o1['K'][i]; i0 = int(np.searchsorted(o0['K'], K)); okk = i0 < len(o0['K']) and o0['K'][i0] == K; t4 = dict(base, strike=K, spot_in=O1[1], spot_out=O0[END0])
    for cp in ('CE', 'PE'):
        a = px(o1, cp, 'open', i, 1); b = px(o0, cp, 'open', i0, END0) if okk else np.nan; t4[f'{cp}_prem'] = a; t4[f'{cp}_pts'] = a - b; t4[f'{cp}_rs'] = (a - b) * L
    return t1, t2, t3, t4
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]
    with Pool(4) as p: res = p.map(one, [(r.und, r.expiry, r.split3) for r in T0.itertuples()], chunksize=4)
    T1 = pd.DataFrame([x for r in res for x in r[0]]); T2 = pd.DataFrame([x for r in res for x in r[1]]); T3 = pd.DataFrame([x for r in res for x in r[2]]); T4 = pd.DataFrame([r[3] for r in res])
    for n, d in (('t1', T1), ('t2', T2), ('t3_events', T3), ('t4', T4)): d.to_csv(f'{TH}/thesis_{n}.csv', index=False)
    print('cycles', len(T4), 'T3 events', len(T3)); print(T1.groupby('segment')[['pnl_pts', 'pnl_pct', 'pnl_rs']].mean().round(3))
