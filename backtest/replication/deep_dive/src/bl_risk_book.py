"""Book-risk reconstruction for the late-sale investigation (plan: reports/LATE_SALE_RISK_PLAN.md). EXPLORATORY; nothing here touches the frozen rule.
For every complete real cycle the D-1 order log is replayed into a position book; at every minute the whole chain is valued with Black-76 (r = 0) from the PREVIOUS minute's closes; book Greeks and the
D0-open gap P&L (spot gaps of -3..+3%, full revaluation at the D0-open time to expiry, vols held) are additive across legs, so each late sale gets its exact state before, after, and after the mirror sale.
Outputs outputs/risk/orders_risk.csv, minute_risk.csv, cycle_risk.csv."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.special import ndtr
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; RK = f'{OUT}/risk'; os.makedirs(RK, exist_ok=True); GAPS = np.array([-0.03, -0.02, -0.01, 0.01, 0.02, 0.03]); T_OPEN = 6.25 / 24.0 / 365.0; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
def bs(F, K, T, s, call):
    sq = s * np.sqrt(T); d1 = (np.log(F / K) + 0.5 * s * s * T) / sq; d2 = d1 - sq
    return np.where(call, F * ndtr(d1) - K * ndtr(d2), K * ndtr(-d2) - F * ndtr(-d1))
def iv_vec(p, F, K, T, call):
    p = np.asarray(p, float); intr = np.where(call, np.maximum(F - K, 0), np.maximum(K - F, 0)); ok = np.isfinite(p) & (p > 0.05) & (p > intr + 1e-6); lo = np.full(p.shape, 1e-3); hi = np.full(p.shape, 4.0)
    for _ in range(60):
        mid = 0.5 * (lo + hi); pm = bs(F, K, T, mid, call); hi = np.where(pm > p, mid, hi); lo = np.where(pm > p, lo, mid)
    iv = 0.5 * (lo + hi); iv = np.where(ok, iv, np.nan)
    if ok.sum() == 0: return None
    idx = np.arange(len(K)); return np.interp(idx, idx[ok], iv[ok])                       # invalid legs take the interpolated vol of valid neighbours
def leg_values(Kc, Pc, Pp, F, T):
    """per-leg values for ONE lot unit at one minute: columns [delta, gamma(delta change per 1% move), vega(per vol pt), theta(per day), pnl at each gap]. Shape (nK, 2, 4 + len(GAPS))"""
    out = np.zeros((len(Kc), 2, 4 + len(GAPS)))
    for ci, call in enumerate((True, False)):
        p = Pc if call else Pp; iv = iv_vec(p, F, Kc, T, call)
        if iv is None: return None
        sq = iv * np.sqrt(T); d1 = (np.log(F / Kc) + 0.5 * iv * iv * T) / sq; nd = np.exp(-0.5 * d1 * d1) / np.sqrt(2 * np.pi); base = bs(F, Kc, T, iv, call)
        out[:, ci, 0] = ndtr(d1) if call else ndtr(d1) - 1.0; out[:, ci, 1] = nd / (F * sq) * F * F * 0.01 * 0.01; out[:, ci, 2] = F * nd * np.sqrt(T) * 0.01; out[:, ci, 3] = -F * nd * iv / (2 * np.sqrt(T)) / 365.0
        for gi, g in enumerate(GAPS): out[:, ci, 4 + gi] = bs(F * (1 + g), Kc, T_OPEN, iv, call) - base
    return out
def parity_forward(Kc, Pc, Pp, centre):
    ok = np.isfinite(Pc) & np.isfinite(Pp) & (Pc > 0) & (Pp > 0); idx = np.where(ok)[0]
    if len(idx) == 0: return None
    near = idx[np.argsort(np.abs(Kc[idx] - centre))[:3]]; return float(np.median(Kc[near] + Pc[near] - Pp[near]))
def state(pos, V, F, unit):
    """book state from positions pos (nK, 2) in lots and leg values V; units in contracts"""
    q = pos * unit; agg = np.einsum('kc,kcf->f', q, V); gross = float((np.abs(q) * np.abs(V[:, :, 0])).sum()); gp = agg[4:]
    return dict(delta=float(agg[0]), delta_rs_pct=float(agg[0] * F * 0.01), gamma=float(agg[1]), vega=float(agg[2]), theta=float(agg[3]), gap_pnl=gp, gap_worst=float(gp.min()), asym=float(gp[4] - gp[1]), gross_delta=gross)
def vwap_dev(und, d1, step, nmin):
    import data as D
    try:
        f = D.Src().csv(f'normalized/{und.lower()}/underlying/futures/{d1}.csv'); f = f[f.expiry_date == sorted(f.expiry_date.unique(), key=lambda x: pd.to_datetime(x))[0]]
        h = f.datetime.str.slice(11, 16); j = (h.str.slice(0, 2).astype(int) * 60 + h.str.slice(3, 5).astype(int) - 555); f = f.assign(j=j)[(j >= 0) & (j < nmin)].drop_duplicates('j').set_index('j').reindex(range(nmin)).ffill()
        tp = (f.high + f.low + f.close) / 3; vol = f.volume.fillna(0); vw = (tp * vol).cumsum() / vol.cumsum().replace(0, np.nan); dev = (f.close - vw) / step; return dev.values, f.close.values
    except Exception: return np.full(nmin, np.nan), np.full(nmin, np.nan)
def run():
    O = DG.real_orders(); O = O.assign(jj=(O.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); orows, mrows, crows = [], [], []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_last', 'row']).reset_index(drop=True)
        if not len(g): continue
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); op = cx['opt1']; Kc = op['K']; kidx = {int(k): i for i, k in enumerate(Kc)}; nmin = op[('CE', 'close')].shape[1]; spot = cx['spot1'].close.values; unit = float(r.unit); step = 50.0 if r.und == 'NIFTY' else 100.0
        post = r.d0 >= CAS; vdev, fclose = vwap_dev(r.und, r.d1, step, nmin); d0_close = pd.Timestamp(r.d0) + pd.Timedelta(hours=15, minutes=30); cache = {}
        def Vj(j):
            if j in cache: return cache[j]
            jp = min(max(j - 1, 0), nmin - 1); Pc = op[('CE', 'close')][:, jp]; Pp = op[('PE', 'close')][:, jp]; F = parity_forward(Kc, Pc, Pp, spot[jp])
            if F is None: cache[j] = None; return None
            now = pd.Timestamp(r.d1) + pd.Timedelta(hours=9, minutes=15 + j); Tt = max((d0_close - now).total_seconds() / 86400.0 / 365.0, 1e-5); V = leg_values(Kc, Pc, Pp, F, Tt)
            cache[j] = None if V is None else (V, F); return cache[j]
        pos = np.zeros((len(Kc), 2)); nsh = lambda p, c: float(-p[p[:, c] < 0, c].sum()); nlg = lambda p, c: float(p[p[:, c] > 0, c].sum()); late_idx = []
        # replay all orders; at each late sale record states
        snaps = {}
        for i, q in g.iterrows():
            j = int(q.jj); k = kidx.get(int(q.strike)); c = 0 if q.cp == 'CE' else 1
            if k is None: continue
            if q.role == 'open_short' and 300 <= j < nmin:
                vv = Vj(j)
                if vv is not None:
                    V, F = vv; before = state(pos, V, F, unit); a = pos.copy(); a[k, c] -= q.lots; after = state(a, V, F, unit)
                    c2 = 1 - c; k2 = int(np.argmin(np.abs(Kc - (2 * F - Kc[k])))); m = pos.copy(); m[k2, c2] -= q.lots; mir = state(m, V, F, unit)
                    row = dict(und=r.und, d1=r.d1, expiry=r.expiry, era='after' if post else 'before', outlier=int((r.und, r.d1) == OUTLIER), j=j, ts=float(q.t_last), cp=q.cp, strike=float(q.strike), lots=int(q.lots), px=float(q.px_avg), F=F, vwap_dev=float(vdev[min(max(j - 1, 0), nmin - 1)]),
                               SC=nsh(pos, 0), SP=nsh(pos, 1), LC=nlg(pos, 0), LP=nlg(pos, 1))
                    for nm, st in (('b', before), ('a', after), ('m', mir)):
                        for key in ('delta_rs_pct', 'asym', 'gap_worst', 'gamma', 'vega', 'theta', 'gross_delta'): row[f'{key}_{nm}'] = st[key]
                    orows.append(row)
            pos[k, c] += q.sg * q.lots
        # per-minute states (position at the START of each minute, prices of the previous minute) for the hazard test, window 300..nmin-1
        gt = g.assign(tm=g.t_last); evs = [(float(q.t_last), kidx.get(int(q.strike)), 0 if q.cp == 'CE' else 1, q.sg * q.lots) for _, q in g.iterrows() if kidx.get(int(q.strike)) is not None]; pos2 = np.zeros((len(Kc), 2)); ptr = 0
        sold = g[(g.role == 'open_short')]; cum_prem = 0.0
        for j in range(0, nmin):
            tstart = (555 + j) * 60.0
            while ptr < len(evs) and evs[ptr][0] < tstart: pos2[evs[ptr][1], evs[ptr][2]] += evs[ptr][3]; ptr += 1
            if j < 300: continue
            vv = Vj(j)
            if vv is None: continue
            V, F = vv; st = state(pos2, V, F, unit); prem = float((sold[sold.t_last < tstart].lots * sold[sold.t_last < tstart].px_avg).sum() * unit); y = {(cp): int(((sold.jj == j) & (sold.cp == cp)).any()) for cp in ('CE', 'PE')}
            for cp, ci in (('CE', 0), ('PE', 1)):
                o = 1 - ci; sh = (nsh(pos2, ci), nsh(pos2, o)); lg = (nlg(pos2, ci), nlg(pos2, o)); sg_ = 1.0 if cp == 'CE' else -1.0
                mrows.append(dict(cyc=f'{r.und}|{r.expiry}', und=r.und, d1=r.d1, era='after' if post else 'before', outlier=int((r.und, r.d1) == OUTLIER), j=j, side=cp, y=y[cp], delta_pressure=sg_ * st['delta_rs_pct'], abs_delta=abs(st['delta_rs_pct']), short_gamma=-st['gamma'], vega=st['vega'], theta=st['theta'], gap_worst=-st['gap_worst'],
                                  asym_pressure=sg_ * st['asym'], lighter_side=sh[1] - sh[0], uncovered_same=sh[0] - lg[0], vwap_dev_trend=-sg_ * float(vdev[max(j - 1, 0)]), cum_premium=prem, delta_ratio=st['delta'] * 0 + (abs(st['delta']) * 1.0 / st['gross_delta'] if st['gross_delta'] > 0 else np.nan)))
        # cycle level: end-of-session book with and without the late sales (prices of the last minute)
        jend = nmin - 1; vv = Vj(jend); v0 = Vj(300)
        if vv is not None and v0 is not None:
            late_ev = g[(g.role == 'open_short') & (g.jj >= 360)]; posA = np.zeros((len(Kc), 2)); posB = np.zeros((len(Kc), 2)); pos300 = np.zeros((len(Kc), 2)); lateset = set(late_ev.index)
            for i, q in g.iterrows():
                k = kidx.get(int(q.strike)); c = 0 if q.cp == 'CE' else 1
                if k is None: continue
                posA[k, c] += q.sg * q.lots
                if i not in lateset: posB[k, c] += q.sg * q.lots
                if q.jj < 300: pos300[k, c] += q.sg * q.lots
            V, F = vv; sA, sB = state(posA, V, F, unit), state(posB, V, F, unit); s300 = state(pos300, v0[0], v0[1], unit)
            crows.append(dict(und=r.und, d1=r.d1, expiry=r.expiry, era='after' if post else 'before', outlier=int((r.und, r.d1) == OUTLIER), late_orders=len(late_ev), late_lots=int(late_ev.lots.sum()),
                              **{f'{k}_end': sA[k] for k in ('delta_rs_pct', 'asym', 'gap_worst', 'gross_delta')}, **{f'{k}_nolate': sB[k] for k in ('delta_rs_pct', 'asym', 'gap_worst')}, delta_ratio_end=abs(sA['delta']) / sA['gross_delta'] if sA['gross_delta'] else np.nan,
                              delta_ratio_1415=abs(s300['delta']) / s300['gross_delta'] if s300['gross_delta'] else np.nan, delta_rs_1415=s300['delta_rs_pct'], delta_end_c=sA['delta'], delta_nolate_c=sB['delta'], gross_nolate=sB['gross_delta'], delta_1415_c=s300['delta']))
        print(r.und, r.d1, 'late orders', len(late_ev) if vv is not None and v0 is not None else '-', flush=True)
    pd.DataFrame(orows).to_csv(f'{RK}/orders_risk.csv', index=False); pd.DataFrame(mrows).to_csv(f'{RK}/minute_risk.csv', index=False); pd.DataFrame(crows).to_csv(f'{RK}/cycle_risk.csv', index=False)
if __name__ == '__main__': run()
