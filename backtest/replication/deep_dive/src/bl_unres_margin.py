"""Plan reports/UNRESOLVED_THREE_PLAN.md, M2 / M3 / G1: margin on the REAL book (rebuilt from the real orders) and gap stress of real and simulated carried books.
Margin rule: 16-scenario risk (price scan = max(6*sqrt2*sigma_daily, 9.3%), vol scan = max(0.25*IV, 4 points)) + 2% extreme-loss margin on short notional (+2% on D0 from 20 Nov 2024).
Outputs outputs/unres/real_margin_cycles.csv, real_margin_samples.csv, gap_stress.csv. Run: OMP_NUM_THREADS=1 python bl_unres_margin.py"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
import bl_thesis_tests as TT
import bl_arch_margin as AM
OUT = TT.OUT; BT3 = TT.BT3; RES = f'{OUT}/bt3_results'; UN = f'{OUT}/unres'; os.makedirs(UN, exist_ok=True)
GAPS = [-0.15, -0.13, -0.10, -0.07, -0.05, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.13, 0.15]; VMS = [1.0, 1.5, 2.0]
def real_fills():
    o = pd.read_pickle(f'{OUT}/bl_all_orders.pkl.gz'); o = o[o.status_last.isin(['Filled', 'PartiallyFilled'])].copy()
    m = (o.t_last // 60 - 555).clip(0, 374).astype(int)
    return pd.DataFrame(dict(und=o.und, expiry=o.expiry, day=o.dayno.astype(int), j=m, cp=o.cp, strike=o.strike.astype(int), side=np.where(o.side == 'Buy', 1, -1), lots=o.lots.astype(float), price=o.px_avg, t=o.t_last, row=o.row))
def positions(F, U):
    keys = sorted({(r.cp, int(r.strike)) for r in F.itertuples()}); ki = {k: n for n, k in enumerate(keys)}; dq = np.zeros((len(keys), 750))
    np.add.at(dq, ([ki[(cp, int(k))] for cp, k in zip(F.cp, F.strike)], (F.day.values * 375 + F.j.values).astype(int)), F.side.values * F.lots.values); return keys, np.cumsum(dq, axis=1) * U
def evaluate(c, keys, pos, post, iv, tag, psr_rules, gap_books):
    samples = [(0, j) for j in list(range(1, 362, 15)) + [374]] + [(1, j) for j in list(range(1, 347, 15)) + [358]]; rows = []; gaps = []
    for day, j in samples:
        tt = day * 375 + j; q = pos[:, tt]; nz = q != 0
        if not nz.any(): continue
        o = c['opt1'] if day == 0 else c['opt0']; o['_j'] = j; S = float((c['spot1'] if day == 0 else c['spot0']).close.iloc[j]); kk = [keys[n] for n in np.where(nz)[0]]; qq = q[nz]
        K, call, s, p0 = AM.book_state(o, S, kk, qq); T = max(750 - tt, 1) / 93750.0; short_units = float(-qq[qq < 0].sum()); elm = (0.02 + (0.02 if (day == 1 and post) else 0.0)) * S * short_units
        r = dict(book=tag, day=day, j=j, short_units=short_units, long_units=float(qq[qq > 0].sum()), spot=S)
        for nm, (psr, vsr) in psr_rules(iv).items(): r[f'margin_{nm}'] = AM.scen_loss(S, K, call, s, p0, qq, T, psr, vsr) + elm
        rows.append(r)
        if day == 0 and j == 374 and tag in gap_books:
            for g in GAPS:
                for vm in VMS: gaps.append(dict(book=tag, gap=g, vm=vm, loss=-float(np.sum(qq * (AM.black(S * (1 + g), K, s * vm, call) - p0))), short_units=short_units, long_units=float(qq[qq > 0].sum())))
    return rows, gaps
def rules(iv): return {'nse': (max(6 * np.sqrt(2) * iv / np.sqrt(250), 0.093), max(0.25 * iv, 0.04)), 'floor93': (0.093, 0.04)}
def one(a):
    und, expiry, d0, U, iv, kind, F, Fsim = a; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); post = d0 >= '2024-11-20'; rows = []; gaps = []
    if kind == 'real':
        keys, pos = positions(F, U); r, g = evaluate(c, keys, pos, post, iv, 'real', rules, {'real'}); rows += r; gaps += g
        Fn = F[F.side == -1]; Fk = F.copy(); keys2, pos2 = positions(F, U); neg = np.array([cp for cp, k in keys2])                                       # real book with its long legs removed at the D-1 close
        pos3 = np.where(pos2 > 0, 0.0, pos2); r, g = evaluate(c, keys2, pos3, post, iv, 'real_no_longs', rules, {'real_no_longs'}); gaps += g
    if Fsim is not None:
        for v, Fv in Fsim.items():
            keys, pos = positions(Fv, U); r, g = evaluate(c, keys, pos, post, iv, f'sim_{v}', rules, {f'sim_{v}'}); rows += r; gaps += g
    for r in rows: r.update(und=und, expiry=expiry)
    for r in gaps: r.update(und=und, expiry=expiry)
    return rows, gaps
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok].set_index(['und', 'expiry']); IV = pd.read_csv(f'{RES}/alpha_iv_cycles.csv').set_index(['und', 'expiry']).iv_D1_open
    R = real_fills(); R = R[[(u, e) in T0.index for u, e in zip(R.und, R.expiry)]]; Rg = {k: g for k, g in R.groupby(['und', 'expiry'])}
    SIMV = ['full', 'd1_no_wings', 'd1_no_lump']; SF = {v: dict(list(pd.read_csv(f'{RES}/ablate_{v}_fills.csv.gz').groupby(['und', 'expiry']))) for v in SIMV}; jobs = []
    for (u, e), r in T0.iterrows():
        U = AM.REFU[u]; iv = float(IV.get((u, e), np.nan))
        if not np.isfinite(iv): iv = 0.12
        fs = {v: SF[v][(u, e)] for v in SIMV if (u, e) in SF[v]}
        jobs.append((u, e, r.d0, U, iv, 'sim', None, fs))
        if (u, e) in Rg: jobs.append((u, e, r.d0, float(r.unit), iv, 'real', Rg[(u, e)], None))
    with Pool(4) as p: res = p.map(one, jobs, chunksize=2)
    S = pd.DataFrame([x for rs, _ in res for x in rs]); G = pd.DataFrame([x for _, gs in res for x in gs]); S.to_csv(f'{UN}/real_margin_samples.csv', index=False); G.to_csv(f'{UN}/gap_stress.csv', index=False)
    cyc = S.groupby(['book', 'und', 'expiry']).agg(peak_nse=('margin_nse', 'max'), peak_floor93=('margin_floor93', 'max'), share_over_2cr=('margin_nse', lambda x: (x > 2e7).mean()), peak_short_units=('short_units', 'max')).reset_index()
    cyc['margin_d1_close'] = [S[(S.book == b) & (S.und == u) & (S.expiry == e) & (S.day == 0) & (S.j == 374)].margin_nse.max() for b, u, e in zip(cyc.book, cyc.und, cyc.expiry)]; cyc.to_csv(f'{UN}/real_margin_cycles.csv', index=False)
    pd.set_option('display.width', 220); print(cyc.groupby('book')[['peak_nse', 'peak_floor93', 'share_over_2cr', 'margin_d1_close']].describe().T.round(-3).to_string()); print('real cycles', (cyc.book == 'real').sum())
    print(G.groupby(['book', 'gap', 'vm']).loss.mean().unstack('book').loc[(slice(None), 1.5), :].round(-3).to_string())
