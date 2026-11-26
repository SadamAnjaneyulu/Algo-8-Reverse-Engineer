"""Which underlying did the real system trade on during the closing auction? (reports/D1_CLOSING_TIME.md)
Same rules, underlyings after 15:15 on post-auction days: X = published index (indicative auction values), XF = frozen at 15:15, XU = index future minus basis, XS = synthetic
index from options (put-call parity); plus XSA, XUA = XS, XU + Fix A (breakouts allowed to the session end). Scored first on decisions vs the real D-1 log:
late-sale timing (minute and side, +-1 minute) in 15:00-15:40 and in 15:15-15:40, late short lots, carried book, stop agreement. P&L last, complete
result plus stop-flip breakdown. Output outputs/cas/*."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_pp_costs as PC, bl_d0x_diag as DG
OUT = S.OUT; CS = f'{OUT}/cas'; os.makedirs(CS, exist_ok=True); CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
VAR = {'X': ('bt3x', False), 'XF': ('bt3f', False), 'XS': ('bt3s', False), 'XSA': ('bt3s', True), 'XU': ('bt3u', False), 'XUA': ('bt3u', True)}
def match(pred, real):
    tp = sum(1 for x in pred if any((x[0] + d, x[1]) in real for d in (-1, 0, 1))); hit = sum(1 for x in real if any((x[0] + d, x[1]) in pred for d in (-1, 0, 1))); return tp, len(pred), hit, len(real)
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; B = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(B.und, B.expiry))
    real = pd.read_csv(f'{OUT}/postcas/diag_cycles.csv'); real = real[real.src == 'real'].set_index(['und', 'expiry']).total
    ctl = pd.read_csv('../../../../risk_rule_validation/results/cycle_stop_control.csv').set_index(['und', 'expiry']).stop
    O = DG.real_orders(); rows = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep or r.d0 < CAS: continue
        row = r._asdict(); g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; tl = (g.t_last // 60 - 555).astype(int)
        out = dict(und=r.und, expiry=r.expiry, d1=r.d1, real=float(real.loc[(r.und, r.expiry)]), real_stop=bool(ctl.loc[(r.und, r.expiry)]))
        for w, j0 in (('w1500', 345), ('w1515', 360)):
            rs = g[(g.role == 'open_short') & (tl >= j0)]; out[f'real_{w}_lots'] = int(rs.lots.sum()); out[f'_rset_{w}'] = {(int(j), cp) for j, cp in zip(tl[rs.index], rs.cp)}
        for name, (d, fixa) in VAR.items():
            os.environ['BT3_DIR'] = f'{OUT}/{d}'; v = {'d1_set': {'breakout_end_min': 384}} if fixa else {}
            F, info = S.run_cycle(row, 'B/V2', S.P_FROZEN, True, v); d1 = F[F.day == 0]; acc = PC.account(F, r.und, r.d1, r.d0, float(r.unit))
            pos = d1.assign(q=d1.side * d1.lots).groupby(['cp', 'strike']).q.sum()
            out.update({f'{name}_gross': acc['gross'], f'{name}_net': acc['net'], f'{name}_stop': info.get('stop_j') is not None, f'{name}_carried_short': float(-pos[pos < 0].sum())})
            for w, j0 in (('w1500', 345), ('w1515', 360)):
                ls = d1[(d1.side < 0) & (d1.j >= j0) & (d1.cls == 'body_sell')]; tp, npred, hit, nreal = match({(int(j), cp) for j, cp in zip(ls.j, ls.cp)}, out[f'_rset_{w}'])
                out.update({f'{name}_{w}_lots': float(ls.lots.sum()), f'{name}_{w}_tp': tp, f'{name}_{w}_npred': npred, f'{name}_{w}_hit': hit, f'{name}_{w}_nreal': nreal})
        rows.append({k: v for k, v in out.items() if not k.startswith('_')})
    R = pd.DataFrame(rows); R.to_csv(f'{CS}/cas_cycles.csv', index=False); rng = np.random.default_rng(11)
    def pr(g, n, w): return g[f'{n}_{w}_tp'].sum() / max(g[f'{n}_{w}_npred'].sum(), 1), g[f'{n}_{w}_hit'].sum() / max(g[f'{n}_{w}_nreal'].sum(), 1)
    ev = []
    for n in VAR:
        e = dict(sim=n, cycles=len(R), sim_mean=R[f'{n}_gross'].mean(), real_mean=R.real.mean(), mae=(R[f'{n}_gross'] - R.real).abs().mean(), stops_agree=int((R[f'{n}_stop'] == R.real_stop).sum()), carried_short=R[f'{n}_carried_short'].mean())
        for w in ('w1500', 'w1515'):
            p, rc = pr(R, n, w); x = R[~((R.und == OUTLIER[0]) & (R.d1 == OUTLIER[1]))]
            e.update({f'{w}_precision': p, f'{w}_recall': rc, f'{w}_sim_lots': R[f'{n}_{w}_lots'].mean(), f'{w}_real_lots_ex_outlier': x[f'real_{w}_lots'].mean(), f'{w}_sim_lots_ex_outlier': x[f'{n}_{w}_lots'].mean()})
        ev.append(e)
    E = pd.DataFrame(ev); E.to_csv(f'{CS}/cas_eval.csv', index=False)
    # paired bootstrap of decision differences vs X, and P&L with flips
    res = {}
    for n in ('XF', 'XS', 'XSA', 'XU', 'XUA'):
        Bt = []
        for _ in range(4000):
            g = R.iloc[rng.integers(0, len(R), len(R))]; a = pr(g, 'X', 'w1515'); b = pr(g, n, 'w1515'); Bt.append((b[0] - a[0], b[1] - a[1]))
        Bt = np.array(Bt); a = pr(R, 'X', 'w1515'); b = pr(R, n, 'w1515'); d = R[f'{n}_gross'] - R['X_gross']; fl = R[f'{n}_stop'] != R['X_stop']
        res[n] = dict(precision_change=[b[0] - a[0], *np.quantile(Bt[:, 0], [.025, .975])], recall_change=[b[1] - a[1], *np.quantile(Bt[:, 1], [.025, .975])],
                      pnl_mean=d.mean(), pnl_median=d.median(), flips=int(fl.sum()), flip_sum=d[fl].sum(), nonflip_mean=d[~fl].mean(), nonflip_median=d[~fl].median())
    json.dump(res, open(f'{CS}/cas_compare.json', 'w'), indent=1, default=float)
    pd.set_option('display.width', 300); pd.set_option('display.max_columns', 40); print(E.round(3).to_string()); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
