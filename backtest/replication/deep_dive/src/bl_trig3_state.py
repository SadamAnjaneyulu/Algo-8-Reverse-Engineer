"""Focused late-sale tests (plan: reports/LATE_SALE_FOCUSED_PLAN.md), step 1: per-minute table for BOTH eras with the pre-registered features, all strictly before the minute:
STR15 (15-min change of the ATM straddle), PP (book MTM / premium collected), GB (MTM minus running peak), FUT5L (price move j-6 -> j-1, oriented so that + favours the contrarian side),
OPT5 (side's ATM-premium % change over the same 5 minutes), sold_deficit. Price series: futures (bt3u) post-auction, published index (bt3x) pre-auction. Output outputs/trig3/state_{after,before}.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, bl_risk_book as B
OUT = S.OUT; T3 = f'{OUT}/trig3'; os.makedirs(T3, exist_ok=True); CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
def build(era):
    O = DG.real_orders(); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); rows = []
    for r in Tc.itertuples():
        post = r.d0 >= CAS
        if (r.und, r.expiry) not in keep or (era == 'after') != post or (r.und, r.d1) == OUTLIER: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row']).reset_index(drop=True)
        if not len(g): continue
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); op = cx['opt1']; Kc = op['K']; kidx = {int(k): i for i, k in enumerate(Kc)}; Pcl, Ppl = op[('CE', 'close')], op[('PE', 'close')]; nmin = Pcl.shape[1]; unit = float(r.unit)
        pr = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1'].close.values.astype(float) if post else cx['spot1'].close.values.astype(float); spot = cx['spot1'].close.values.astype(float)
        cyc = f'{r.und}|{r.d1}'; t = g.t_first.values.astype(float); k = np.array([kidx.get(int(s), -1) for s in g.strike]); c = (g.cp == 'PE').astype(int).values; q = (g.sg * g.lots).values.astype(float); px = g.px_avg.values; role = g.role.values; jj = (t // 60 - 555).astype(int)
        Fprev = spot[300]
        def prices(j): jp = min(max(j - 1, 0), nmin - 1); return Pcl[:, jp], Ppl[:, jp]
        def straddle(j):
            nonlocal Fprev
            Pc, Pp = prices(j); F = B.parity_forward(Kc, Pc, Pp, Fprev)
            if F is None: return np.nan
            Fprev = F; i = int(np.argmin(np.abs(Kc - F))); return float(Pc[i] + Pp[i])
        def book_at(ts):
            pos = np.zeros((len(Kc), 2)); cash = 0.0
            for ti, ki, ci, qi, pi_ in zip(t, k, c, q, px):
                if ti >= ts: break
                if ki >= 0: pos[ki, ci] += qi; cash += -qi * pi_ * unit
            return pos, cash
        def mtm(j):
            pos, cash = book_at((555 + j) * 60.0); Pc, Pp = prices(j); return cash + (np.nansum(pos[:, 0] * np.nan_to_num(Pc)) + np.nansum(pos[:, 1] * np.nan_to_num(Pp))) * unit
        stg = {j: straddle(j) for j in range(300, nmin)}; path = np.array([mtm(j) for j in range(0, nmin)]); peak = np.maximum.accumulate(path)
        for j in range(360, nmin):
            ts = (555 + j) * 60.0; pos, cash = book_at(ts); sold = (role == 'open_short') & (t < ts); prem = float((g.lots.values[sold] * px[sold]).sum() * unit); up = pr[j - 1] - pr[j - 6]; ka = int(np.argmin(np.abs(Kc - pr[j - 6]))); y = {cp: int(((role == 'open_short') & (g.cp.values == cp) & (jj == j)).any()) for cp in ('CE', 'PE')}
            so = {cp: float(g.lots.values[sold & (g.cp.values == cp)].sum()) for cp in ('CE', 'PE')}
            for cp, ci in (('CE', 0), ('PE', 1)):
                P_ = Pcl if ci == 0 else Ppl; opt5 = float(P_[ka, j - 1] / P_[ka, j - 6] - 1) if P_[ka, j - 6] > 0 else np.nan; oth = 'PE' if cp == 'CE' else 'CE'
                rows.append(dict(cyc=cyc, und=r.und, d1=r.d1, expiry=r.expiry, era=era, j=j, side=cp, y=y[cp], STR15=float(stg[j] / stg[j - 15] - 1) if np.isfinite(stg[j]) and np.isfinite(stg[j - 15]) and stg[j - 15] > 0 else np.nan, PP=path[j] / prem if prem > 0 else np.nan, GB=float(path[j] - peak[j - 1]),
                                 FUT5L=float((-up if cp == 'CE' else up) / (50.0 if r.und == 'NIFTY' else 100.0)), OPT5=opt5, sold_deficit=so[oth] - so[cp]))
        print(era, cyc, len(rows), flush=True)
    M = pd.DataFrame(rows); M.to_csv(f'{T3}/state_{era}.csv', index=False); return M
if __name__ == '__main__':
    for e in (sys.argv[1:] or ['after', 'before']): build(e)
