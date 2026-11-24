"""Event table for the late D-1 sale trigger (plan: reports/D0_CLEAR_AND_LATE_TRIGGER_PLAN.md). One row per (cycle, minute j, side CE/PE) in the window
j = 360..384 (post-auction; 15:15-15:39) or 360..374 (pre-auction). y = a real open_short on that side in that minute. Features use information through the minute's own
bar (as the engine's ladder does); lag-1 variants are computed for the robustness check only. Underlyings: FEED (published index), FUT (future minus basis, bt3u), OPT
(option-implied, bt3s); pre-auction only FEED (the index is a valid price then). Output outputs/trig/event_table.csv.gz."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; TR = f'{OUT}/trig'; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); KS = (1, 3, 5, 10); GS = (5, 15, 30, 60)
def ufeat(name, h, l, c, j, side, step, jl_ref, tag=''):
    """features of one underlying for (minute j, side); side CE favourable = fall, PE favourable = rise. tag '' = through minute j, 'L' = through j-1"""
    jj = j - (1 if tag else 0); f = {}; sg = -1 if side == 'CE' else 1
    for k in KS:
        f[f'{name}{tag}_mv{k}'] = sg * (c[jj] - c[jj - k]) / step; f[f'{name}{tag}_abs{k}'] = abs(c[jj] - c[jj - k]) / step
    for G in GS:
        f[f'{name}{tag}_ext{G}'] = float((l[jj] < l[jj - G:jj].min()) if side == 'CE' else (h[jj] > h[jj - G:jj].max()))
    ref = c[max(jl_ref - 1, 0)]; f[f'{name}{tag}_exc'] = ((ref - l[jj]) if side == 'CE' else (h[jj] - ref)) / step
    return f
if __name__ == '__main__':
    O = DG.real_orders(); O = O.assign(jj=(O.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]
    B = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(B.und, B.expiry)); rows = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep: continue
        post = r.d0 >= CAS; step = 50.0 if r.und == 'NIFTY' else 100.0; g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; sells = g[g.role == 'open_short']; covers = g[g.role == 'cover_short']
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); opt = cx['opt1']; ki = {int(k): i for i, k in enumerate(opt['K'])}
        U = {'FEED': cx['spot1']}
        if post: U['FUT'] = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1']; U['OPT'] = pd.read_pickle(f'{OUT}/bt3s/{r.und}_{r.expiry}.pkl.gz')['spot1']
        arr = {k: (v.high.values.astype(float), v.low.values.astype(float), v.close.values.astype(float)) for k, v in U.items()}; jmax = 384 if post else 374
        for j in range(360, jmax + 1):
            prev_any = sells[sells.jj < j]; mins_since = float(j - prev_any.jj.max()) if len(prev_any) else float(j)
            for side in ('CE', 'PE'):
                ys = sells[(sells.cp == side) & (sells.jj == j)]; ps = sells[(sells.cp == side) & (sells.jj < j)]; jl = int(ps.jj.max()) if len(ps) else 0
                row = dict(und=r.und, expiry=r.expiry, d1=r.d1, era='after' if post else 'before', j=j, side=side, y=int(len(ys) > 0), lots=int(ys.lots.sum()), mins_since_sale=mins_since, outlier=int((r.und, r.d1) == OUTLIER))
                for nm, (h, l, c) in arr.items():
                    row.update(ufeat(nm, h, l, c, j, side, step, jl)); row.update(ufeat(nm, h, l, c, j, side, step, jl, 'L'))
                shc = lambda s: int(sells[(sells.cp == s) & (sells.jj < j)].lots.sum() - covers[(covers.cp == s) & (covers.jj < j)].lots.sum()); other = 'PE' if side == 'CE' else 'CE'
                row['imb'] = shc(side) - shc(other)
                if len(ps):
                    lastr = ps.sort_values('t_last').iloc[-1]; i = ki.get(int(lastr.strike)); cur = opt[(side, 'close')][i, min(j - 1, opt[(side, 'close')].shape[1] - 1)] if i is not None else np.nan
                    row['prem_ratio'] = float(np.log(max(cur, 0.05) / max(lastr.px_avg, 0.05))) if cur == cur else np.nan
                else: row['prem_ratio'] = np.nan
                rows.append(row)
    D = pd.DataFrame(rows); D.to_csv(f'{TR}/event_table.csv.gz', index=False)
    print(D.groupby(['era']).agg(rows=('y', 'size'), events=('y', 'sum'), cycles=('expiry', lambda s: len(set(zip(D.loc[s.index, 'und'], s))))).to_string()); print(D.groupby(['era', 'side']).y.sum().to_string()); print(D.shape)
