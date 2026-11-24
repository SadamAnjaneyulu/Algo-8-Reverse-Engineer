"""Extended session (15:30-15:39 after the closing auction) and Fix A re-scored (reports/EXTENDED_SESSION_FIXA.md).
Variants on the complete real cycles: base = old cache (session to 15:29); X = extended cache, identical rules (the D-1 rules simply keep running
to the exchange close: stops on option highs 15:30-15:39, the 15:30 lump priced at its own minute); XA = X + Fix A (breakout window to the session
end after the auction; no fitted parameter). Decisions are scored against the real D-1 log first; P&L last, complete result plus stop-flip breakdown.
Real totals: outputs/postcas/diag_cycles.csv; with official settlement (last index close) re-computed for the check. Output outputs/xs/*."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_pp_costs as PC, bl_d0x_diag as DG
OUT = S.OUT; XS = f'{OUT}/xs'; os.makedirs(XS, exist_ok=True); CAS = '2026-08-03'
COLS = ['day', 'j', 'cp', 'strike', 'side', 'lots', 'price', 'cls', 'n_orders']
def f1(pred, real):
    tp = sum(1 for x in pred if any((x[0] + d, x[1]) in real for d in (-1, 0, 1))); hit = sum(1 for x in real if any((x[0] + d, x[1]) in pred for d in (-1, 0, 1)))
    return tp, len(pred), hit, len(real)
def run(row, name, cas):
    os.environ['BT3_DIR'] = f'{OUT}/bt3' if name == 'base' else f'{OUT}/bt3x'
    v = {'d1_set': {'breakout_end_min': 384}} if (name == 'XA' and cas) else {}
    f, info = S.run_cycle(row, 'B/V2', S.P_FROZEN, True, v); return f, info
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; B = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(B.und, B.expiry))
    real = pd.read_csv(f'{OUT}/postcas/diag_cycles.csv'); real = real[real.src == 'real'].set_index(['und', 'expiry']).total
    ctl = pd.read_csv('../../../../risk_rule_validation/results/cycle_stop_control.csv').set_index(['und', 'expiry']).stop
    O = DG.real_orders(); rows = []; dec = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep: continue
        row = r._asdict(); cas = r.d1 >= CAS; g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; tl = g.t_last // 60 - 555
        rs = g[(g.role == 'open_short') & (tl >= 345)]; rset = {(int(t // 60 - 555), cp) for t, cp in zip(rs.t_last, rs.cp)}
        out = dict(und=r.und, expiry=r.expiry, d1=r.d1, era='after' if r.d0 >= CAS else 'before', real=float(real.loc[(r.und, r.expiry)]), real_stop=bool(ctl.loc[(r.und, r.expiry)]),
                   real_late_short=int(rs.lots.sum()), real_cover_after_1530=int(g[(g.role == 'cover_short') & (tl >= 375)].lots.sum()),
                   real_lump_lots=int(g[(g.module == 'v_') & (g.side == 'Buy')].lots.sum()), real_lump_px=float(np.average(g[(g.module == 'v_') & (g.side == 'Buy')].px_avg, weights=g[(g.module == 'v_') & (g.side == 'Buy')].lots)) if ((g.module == 'v_') & (g.side == 'Buy')).any() else np.nan)
        for name in ('base', 'X', 'XA'):
            f, info = run(row, name, cas); F = f; d1 = F[F.day == 0]
            acc = PC.account(F[COLS], r.und, r.d1, r.d0, float(r.unit)); pos = d1.assign(q=d1.side * d1.lots).groupby(['cp', 'strike']).q.sum()
            ls = d1[(d1.side < 0) & (d1.j >= 345) & (d1.cls == 'body_sell')]; pset = {(int(j), cp) for j, cp in zip(ls.j, ls.cp)}; tp, npred, hit, nreal = f1(pset, rset)
            lump = d1[d1.cls == 'lump']
            out.update({f'{name}_gross': acc['gross'], f'{name}_net': acc['net'], f'{name}_stop': info.get('stop_j') is not None, f'{name}_carried_short': float(-pos[pos < 0].sum()),
                        f'{name}_late_short': float(ls.lots.sum()), f'{name}_d1_stops_after_1530': float(d1[(d1.cls == 'body_buyback') & (d1.j >= 375)].lots.sum()),
                        f'{name}_lump_lots': float(lump.lots.sum()), f'{name}_lump_px': float(np.average(lump.price, weights=lump.lots)) if len(lump) else np.nan, f'{name}_lump_j': float(lump.j.min()) if len(lump) else np.nan,
                        f'{name}_tp': tp, f'{name}_npred': npred, f'{name}_hit': hit, f'{name}_nreal': nreal})
        rows.append(out)
    R = pd.DataFrame(rows); R.to_csv(f'{XS}/rescore_cycles.csv', index=False)
    # summaries
    def flips(a, b, g): d = g[f'{b}_gross'] - g[f'{a}_gross']; fl = g[f'{a}_stop'] != g[f'{b}_stop']; return dict(mean=d.mean(), median=d.median(), flips=int(fl.sum()), flip_sum=d[fl].sum(), nonflip_mean=d[~fl].mean() if (~fl).any() else np.nan, nonflip_median=d[~fl].median() if (~fl).any() else np.nan)
    ev = []; res = {}
    for era, g in R.groupby('era'):
        for n in ('base', 'X', 'XA'):
            err = g[f'{n}_gross'] - g.real; fl = g[f'{n}_stop'] != g.real_stop
            ev.append(dict(era=era, sim=n, cycles=len(g), real_mean=g.real.mean(), sim_mean=g[f'{n}_gross'].mean(), sim_net_mean=g[f'{n}_net'].mean(), mae=err.abs().mean(), median_abs_err=err.abs().median(),
                           mae_stop_agree_cycles=err[~fl].abs().mean(), stops_agree=int((~fl).sum()), spearman=g[[f'{n}_gross', 'real']].corr('spearman').iloc[0, 1],
                           late_short_sim=g[f'{n}_late_short'].mean(), late_short_real=g.real_late_short.mean(), carried_short=g[f'{n}_carried_short'].mean(),
                           late_precision=g[f'{n}_tp'].sum() / max(g[f'{n}_npred'].sum(), 1), late_recall=g[f'{n}_hit'].sum() / max(g[f'{n}_nreal'].sum(), 1),
                           d1_stops_after_1530=g[f'{n}_d1_stops_after_1530'].mean(), real_covers_after_1530=g.real_cover_after_1530.mean(),
                           lump_px_sim=g[f'{n}_lump_px'].mean(), lump_px_real=g.real_lump_px.mean()))
        res[era] = {'X_vs_base': flips('base', 'X', g), 'XA_vs_X': flips('X', 'XA', g), 'XA_vs_base': flips('base', 'XA', g)}
    E = pd.DataFrame(ev); E.to_csv(f'{XS}/rescore_eval.csv', index=False); json.dump(res, open(f'{XS}/rescore_flips.json', 'w'), indent=1, default=float)
    pd.set_option('display.width', 300); pd.set_option('display.max_columns', 40); print(E.round(2).to_string()); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 0)))
