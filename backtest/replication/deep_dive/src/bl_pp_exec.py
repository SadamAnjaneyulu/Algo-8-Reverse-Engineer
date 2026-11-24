"""Pre-paper-trading battery (reports/PREPAPER_PLAN.md): B1 costs & execution grid, S2 margin-capped sizing, B5 liquidity & capacity, B4 overnight IV shocks.
Uses the saved fills of the full strategy (identical to outputs/prepaper/var_full.csv: gross reproduced exactly). Output outputs/prepaper/exec_cycles.csv, capacity.csv, exec_summary.json.
Run: OMP_NUM_THREADS=1 python bl_pp_exec.py"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
import bl_bt3_sim as S, bl_pp_costs as PC, bl_arch_margin as AM
OUT = S.OUT; PP = f'{OUT}/prepaper'; RES = f'{OUT}/bt3_results'; CAP = 2e7; S_ = None
def init():
    global S_; import data as D; S_ = D.Src()
def vol_map(und, expiry, d):
    f = S_.csv(f'normalized/{und.lower()}/options/exp{expiry}_{d}.csv'); h = f.datetime.str.slice(11, 16); j = h.str.slice(0, 2).astype(int) * 60 + h.str.slice(3, 5).astype(int) - 555
    f = f.assign(j=j)[(j >= 0) & (j < 375)]; return {(r, int(k), int(jj)): float(v) for r, k, jj, v in zip(f.right, f.strike, f.j, f.volume)}
def one(a):
    und, expiry, d1, d0, split, F, s_cap = a; c = S.load(und, expiry); U = PC.REFU[und]; r = dict(und=und, expiry=expiry, d0=d0, split=split, s_cap=s_cap)
    acc = lambda f, **k: PC.account(f, und, d1, d0, k.pop('unit', U), **k)
    b = acc(F); r.update(gross=b['gross'], net=b['net'], costs=b['costs'], slippage=b['slippage'], orders=b['orders'])
    for nm, kw in (('cost1.5', dict(cost_mult=1.5)), ('cost2', dict(cost_mult=2.0)), ('slip2', dict(slip_mult=2.0)), ('slip3', dict(slip_mult=3.0)), ('slip6', dict(slip_mult=6.0)), ('cost1.5_slip2', dict(cost_mult=1.5, slip_mult=2.0)),
                   ('cost2_slip3', dict(cost_mult=2.0, slip_mult=3.0)), ('nse_03553', dict(nse_late=0.0003553)), ('m0', dict(cost_mult=0.0, slip_mult=0.0)), ('m2', dict(cost_mult=2.0, slip_mult=2.0)),
                   ('size0.5', dict(unit=0.5 * U, slip_mult=0.5)), ('size2', dict(unit=2.0 * U, slip_mult=2.0)), ('capped', dict(unit=s_cap * U))):
        r[f'net_{nm}'] = acc(F, **kw)['net']
    for nm, (mode, d) in (('delay1', ('delay', 1)), ('delay2', ('delay', 2)), ('barpos', ('barpos', 0))): r[f'net_{nm}'] = acc(S.reprice(F, c, mode, d))['net']
    # capacity: fill units / that contract-minute's traded volume
    vm = {0: vol_map(und, expiry, d1), 1: vol_map(und, expiry, d0)}; part = []
    for q in F.itertuples():
        v = vm[q.day].get((q.cp, int(q.strike), int(min(max(q.j, 0), 374))), 0.0); part.append((q.lots * U, v))
    # overnight IV shock (no gap) on the carried book at the D-1 close
    car = F[F.day == 0].assign(q=lambda x: x.side * x.lots).groupby(['cp', 'strike']).q.sum(); car = car[car != 0]
    if len(car):
        o = c['opt1']; o['_j'] = 374; Sx = float(c['spot1'].close.iloc[374]); keys = [(cp, int(k)) for cp, k in car.index]; qq = car.values * U
        K, call, s, p0 = AM.book_state(o, Sx, keys, qq)
        for vm_ in (1.5, 2.0): r[f'iv_shock_{vm_}'] = -float(np.sum(qq * (AM.black(Sx, K, s * vm_, call) - p0)))
    return r, part
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T.ok].sort_values('d0')
    A = pd.read_csv(f'{OUT}/arch/arch_cycles.csv'); A = A[(A.variant == 'full') & (A.psr == 0.093) & (A.vsr == 0.04)][['und', 'expiry', 'peak_margin']]; T = T.merge(A, on=['und', 'expiry'], how='left')
    sc = []                                                                                                    # causal cap: 90th pct of the previous 8 cycles of the same index
    for u, g in T.groupby('und'):
        pm = g.peak_margin.values
        for i in range(len(g)): prev = pm[max(0, i - 8):i]; sc.append((g.index[i], 1.0 if len(prev) < 4 else min(1.0, CAP / np.quantile(prev, .9))))
    T['s_cap'] = pd.Series(dict(sc)); FF = pd.read_csv(f'{RES}/ablate_full_fills.csv.gz'); FG = {k: g for k, g in FF.groupby(['und', 'expiry'])}
    jobs = [(r.und, r.expiry, r.d1, r.d0, r.split3, FG[(r.und, r.expiry)], float(r.s_cap)) for r in T.itertuples()]
    with Pool(4, initializer=init) as p: res = p.map(one, jobs, chunksize=2)
    E = pd.DataFrame([a for a, _ in res]).merge(T[['und', 'expiry', 'peak_margin']], on=['und', 'expiry']); E['peak_margin_capped'] = E.peak_margin * E.s_cap; E.to_csv(f'{PP}/exec_cycles.csv', index=False)
    P = np.array([x for _, pl in res for x in pl]); u, v = P[:, 0], P[:, 1]; rate = np.where(v > 0, u / np.maximum(v, 1), np.inf)
    cap = pd.DataFrame([dict(size=sz, threshold=th, share_of_fill_units_at_or_below=float(u[(rate * sz) <= th].sum() / u.sum()), share_of_fills_at_or_below=float(((rate * sz) <= th).mean())) for sz in (1.0, 2.0) for th in (0.05, 0.10, 0.25)])
    cap.to_csv(f'{PP}/capacity.csv', index=False)
    json.dump(dict(fills=int(len(P)), fills_with_zero_volume=float((v <= 0).mean()), median_participation=float(np.median(rate[np.isfinite(rate)]))), open(f'{PP}/exec_summary.json', 'w'), indent=1)
    pd.set_option('display.width', 250); print(E.filter(like='net').mean().round(0).to_string()); print(cap.round(3).to_string()); print('capped: mean s', E.s_cap.mean().round(3), 'share peak>2cr after cap', (E.peak_margin_capped > CAP).mean().round(3))
