"""Analysis of bl_d0v_sizing.py runs (plan reports/D0_SIZING_PLAN.md). Metrics fixed in the plan: lot F1, lots per class, peak short lots, cycle cash P&L, stop agreement, cycle-bootstrap CIs.
Outputs bl_d0v_f1.csv, bl_d0v_f1_class.csv, bl_d0v_book.csv, bl_d0v_pnl.csv, bl_d0v_scale.csv, bl_d0v_stop.csv, bl_d0v_cycles.csv, bl_summary_d0v.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
import bl_d0v_sizing as Z
R = pd.read_pickle(f'{OUT}/bl_d0v_runs.pkl.gz'); D = pd.DataFrame([{k: v for k, v in r.items() if k not in ('f1', 'lots')} for r in R])
for c in Z.NMOD: D['lots_' + c] = [r['lots'][c] for r in R]
for c in Z.NMOD: D['real_' + c] = [r['f1'][c][0] if r['f1'] else np.nan for r in R]; D['sim_' + c] = [r['f1'][c][1] if r['f1'] else np.nan for r in R]; D['tp_' + c] = [r['f1'][c][2] if r['f1'] else np.nan for r in R]
REAL = {i: Z.real_info(i) for i in Z.D0C}; RI = pd.DataFrame(REAL).T; RI.index.name = 'cid'; Rj = {}; RI['null_pnl'] = pd.Series({i: Z.null_pnl(i) for i in Z.D0C})
SPL = {'OOF (cycle halves)': (['OOF half 0 test', 'OOF half 1 test'], None), 'forward A (same version, later cycles)': (['forward A (same version, later cycles)'], None), 'forward B (train V1, test V2)': (['forward B (train V1, test V2)'], None)}
TRT = [('M0 reference', 'M0', 'ratio'), ('A draw', 'A', 'ratio'), ('B fixed median', 'B', 'ratio'), ('A draw, oldest-first', 'A', 'fifo'), ('B fixed, oldest-first', 'B', 'fifo')]
D1 = D[D.s == 1.0]
def agg_cycle(d):
    """average repetitions per cycle (class counts and P&L)"""
    num = [c for c in D.columns if c.startswith(('real_', 'sim_', 'tp_', 'lots_'))] + ['pnl', 'peak_CE', 'peak_PE']
    g = d.groupby('cid')[num].mean(); st = d.groupby('cid').stop_j.apply(lambda s: float(s.notna().mean())); g['stop_share'] = st; return g
# ---------- F1 (s = 1)
def f1_of(g, classes=Z.NMOD):
    tp = sum(g['tp_' + c].sum() for c in classes); a = sum(g['sim_' + c].sum() for c in classes); b = sum(g['real_' + c].sum() for c in classes); return 2 * tp / max(a + b, 1)
def boot(gs, fn, nb=500, seed=11):
    """cycle bootstrap; gs = list of per-cycle frames with the same index"""
    rng = np.random.default_rng(seed); idx = gs[0].index.values; out = []
    for _ in range(nb):
        ii = rng.choice(idx, len(idx)); out.append(fn([g.loc[ii] for g in gs]))
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))
rows = []; crow = []; CYC = {}
for sp, (sps, _) in SPL.items():
    d = D1[D1.split.isin(sps)]
    for nm, mode, order in TRT:
        dd = d[(d['mode'] == mode) & (d.order == order)]
        if dd.empty: continue
        g = agg_cycle(dd); CYC[(sp, nm)] = g
        reps = dd.groupby('rep').apply(lambda x: f1_of(x.set_index('cid'))) if mode == 'A' else pd.Series([f1_of(g)])
        rows.append(dict(split=sp, treatment=nm, cycles=len(g), reps=dd.rep.nunique(), F1=f1_of(g), F1_rep_mean=float(reps.mean()), F1_rep_sd=float(reps.std()) if len(reps) > 1 else 0.0, sim_lots=float(sum(g['sim_' + c].sum() for c in Z.NMOD)), real_lots=float(sum(g['real_' + c].sum() for c in Z.NMOD)),
                         F1_body_sell=f1_of(g, ['body_sell']), F1_body_buyback=f1_of(g, ['body_buyback']), F1_wing_buy=f1_of(g, ['wing_buy']), F1_wing_sell=f1_of(g, ['wing_sell']), F1_stop=f1_of(g, ['stop'])))
F1T = pd.DataFrame(rows)
for sp in SPL:
    base = CYC[(sp, 'M0 reference')]
    for nm in ('A draw', 'B fixed median'):
        lo, hi = boot([CYC[(sp, nm)], base], lambda gs: f1_of(gs[0]) - f1_of(gs[1])); F1T.loc[(F1T.split == sp) & (F1T.treatment == nm), 'dF1_vs_M0'] = f1_of(CYC[(sp, nm)]) - f1_of(base); F1T.loc[(F1T.split == sp) & (F1T.treatment == nm), 'dF1_lo'] = lo; F1T.loc[(F1T.split == sp) & (F1T.treatment == nm), 'dF1_hi'] = hi
    lo, hi = boot([CYC[(sp, 'A draw')], CYC[(sp, 'B fixed median')]], lambda gs: f1_of(gs[0]) - f1_of(gs[1])); F1T.loc[(F1T.split == sp) & (F1T.treatment == 'A draw'), 'dF1_vs_B'] = f1_of(CYC[(sp, 'A draw')]) - f1_of(CYC[(sp, 'B fixed median')]); F1T.loc[(F1T.split == sp) & (F1T.treatment == 'A draw'), 'dF1_vs_B_lo'] = lo; F1T.loc[(F1T.split == sp) & (F1T.treatment == 'A draw'), 'dF1_vs_B_hi'] = hi
F1T.round(4).to_csv(f'{OUT}/bl_d0v_f1.csv', index=False)
# class table for OOF
cl = []
for nm, mode, order in TRT[:3]:
    g = CYC[('OOF (cycle halves)', nm)]
    for c in Z.NMOD: cl.append(dict(treatment=nm, cls=c, real=float(g['real_' + c].sum()), sim=float(g['sim_' + c].sum()), matched=float(g['tp_' + c].sum()), F1=f1_of(g, [c]), precision=float(g['tp_' + c].sum() / max(g['sim_' + c].sum(), 1)), recall=float(g['tp_' + c].sum() / max(g['real_' + c].sum(), 1))))
pd.DataFrame(cl).round(4).to_csv(f'{OUT}/bl_d0v_f1_class.csv', index=False)
# ---------- book, P&L, stop (every scale, OOF cycles for s < 1; all splits at s = 1)
def pnl_stats(g, ri, s):
    real = ri.pnl.reindex(g.index).values * s; sim = g.pnl.values; ok = np.isfinite(real) & np.isfinite(sim)
    rho = stats.spearmanr(sim[ok], real[ok]).correlation if ok.sum() > 3 else np.nan
    return dict(cycles=int(ok.sum()), spearman=float(rho), median_err_lakh=float(np.median(sim[ok] - real[ok]) / 1e5), sum_ratio=float(sim[ok].sum() / real[ok].sum()) if real[ok].sum() else np.nan, same_sign=float((np.sign(sim[ok]) == np.sign(real[ok])).mean()), sim_sum_lakh=float(sim[ok].sum() / 1e5), real_sum_lakh=float(real[ok].sum() / 1e5), sim_median_lakh=float(np.median(sim[ok]) / 1e5), real_median_lakh=float(np.median(real[ok]) / 1e5))
pr = []; bk = []; sr = []
for (sp, sps) in [(k, v[0]) for k, v in SPL.items()]:
    for nm, mode, order in TRT:
        for s in sorted(D.s.unique(), reverse=True):
            if s < 1 and sp != 'OOF (cycle halves)': continue
            dd = D[(D.split.isin(sps)) & (D['mode'] == mode) & (D.order == order) & (D.s == s)]
            if dd.empty: continue
            g = agg_cycle(dd); ps = pnl_stats(g, RI, s); pr.append(dict(split=sp, treatment=nm, s=s, **ps))
            pk = (g.peak_CE + g.peak_PE) / 2; rp = ((RI.peak_CE + RI.peak_PE) / 2).reindex(g.index) * s; ok = np.isfinite(pk) & np.isfinite(rp)
            bk.append(dict(split=sp, treatment=nm, s=s, cycles=int(ok.sum()), peak_ratio_median=float(np.median(pk[ok] / rp[ok])), peak_spearman=float(stats.spearmanr(pk[ok], rp[ok]).correlation), sim_peak_median=float(np.median(pk[ok])), real_peak_x_s_median=float(np.median(rp[ok]))))
            rl = {c: float(g['lots_' + c].sum() / max(s * RI.pnl.reindex(g.index).notna().sum() * 0 + s * sum(Z.REAL[i][Z.REAL[i].cls == c].lots.sum() for i in g.index), 1)) for c in Z.NMOD}; bk[-1].update({'lots_ratio_' + c: v for c, v in rl.items()})
            rs = RI.stop_j.reindex(g.index); both = ((g.stop_share > 0.5) & rs.notna()).sum(); sr.append(dict(split=sp, treatment=nm, s=s, cycles=len(g), real_stop=int(rs.notna().sum()), sim_stop=int((g.stop_share > 0.5).sum()), both=int(both), real_only=int((rs.notna() & ~(g.stop_share > 0.5)).sum()), sim_only=int((rs.isna() & (g.stop_share > 0.5)).sum())))
PNL = pd.DataFrame(pr); BK = pd.DataFrame(bk); STP = pd.DataFrame(sr); PNL.round(4).to_csv(f'{OUT}/bl_d0v_pnl.csv', index=False); BK.round(4).to_csv(f'{OUT}/bl_d0v_book.csv', index=False); STP.to_csv(f'{OUT}/bl_d0v_stop.csv', index=False)
# bootstrap: P&L Spearman difference A or B vs M0 (OOF, s = 1)
def sp_diff(gs, ri=RI):
    a, b = gs; ra = ri.pnl.reindex(a.index).values; return stats.spearmanr(a.pnl.values, ra).correlation - stats.spearmanr(b.pnl.values, ra).correlation
Rsum = {}
for nm in ('A draw', 'B fixed median'):
    for sp in SPL:
        gs = [CYC[(sp, nm)], CYC[(sp, 'M0 reference')]]; lo, hi = boot(gs, sp_diff); Rsum[f'pnl_spearman_diff_{nm}_{sp}'] = dict(diff=float(sp_diff(gs)), lo=lo, hi=hi)
# ---------- scale: H4 (OOF cycles)
sc = []
for nm, mode, order in TRT[:3]:
    base = agg_cycle(D[(D.split.isin(SPL['OOF (cycle halves)'][0])) & (D['mode'] == mode) & (D.order == order) & (D.s == 1.0)]).pnl
    for s in sorted(D.s.unique(), reverse=True):
        dd = D[(D.split.isin(SPL['OOF (cycle halves)'][0])) & (D['mode'] == mode) & (D.order == order) & (D.s == s)]
        g = agg_cycle(dd); rep = dd.groupby('cid').pnl.std() if dd.rep.nunique() > 1 else pd.Series(0.0, index=g.index); ratio = (g.pnl / (s * base)).replace([np.inf, -np.inf], np.nan)
        sc.append(dict(treatment=nm, s=s, median_ratio_to_s_x_P1=float(ratio.median()), sum_ratio=float(g.pnl.sum() / (s * base.sum())), between_rep_sd_lakh=float(rep.median() / 1e5), noise_per_real_size_lakh=float(rep.median() / 1e5 / s), peak_ratio=float(((g.peak_CE + g.peak_PE) / 2).median() / (s * ((RI.peak_CE + RI.peak_PE) / 2).reindex(g.index).median()))))
SC = pd.DataFrame(sc); SC.round(4).to_csv(f'{OUT}/bl_d0v_scale.csv', index=False)
# per-cycle P&L table at s = 1 OOF
cy = RI[['pnl', 'null_pnl', 'peak_CE', 'peak_PE', 'stop_j']].copy()
for nm, mode, order in TRT[:3]: cy['pnl_' + nm.split()[0]] = CYC[('OOF (cycle halves)', nm)].pnl.reindex(cy.index)
cy.to_csv(f'{OUT}/bl_d0v_cycles.csv'); Rsum['real_pnl_lakh_oof'] = dict(sum=float(RI.pnl.sum() / 1e5), median=float(RI.pnl.median() / 1e5), cycles=int(RI.pnl.notna().sum()), resid_share=float((RI.resid.abs().sum() / RI.pnl.abs().sum())))
ok_ = RI.pnl.notna() & RI.null_pnl.notna(); Rsum['null_hold_carried_book'] = dict(spearman=float(stats.spearmanr(RI.null_pnl[ok_], RI.pnl[ok_]).correlation), median_err_lakh=float(np.median(RI.null_pnl[ok_] - RI.pnl[ok_]) / 1e5), sum_lakh=float(RI.null_pnl[ok_].sum() / 1e5), real_sum_lakh=float(RI.pnl[ok_].sum() / 1e5), same_sign=float((np.sign(RI.null_pnl[ok_]) == np.sign(RI.pnl[ok_])).mean()), cycles=int(ok_.sum()))
Rsum['real_pnl_spread_lakh'] = dict(std=float(RI.pnl.std() / 1e5), mad=float((RI.pnl - RI.pnl.median()).abs().median() / 1e5))
rec('d0v', Rsum); pd.set_option('display.width', 250)
print(F1T.round(3).to_string()); print(pd.DataFrame(cl).round(3).to_string()); print(PNL.round(3).to_string()); print(BK.round(3).to_string()); print(STP.to_string()); print(SC.round(3).to_string()); print(json.dumps(Rsum, indent=1)[:2500])
