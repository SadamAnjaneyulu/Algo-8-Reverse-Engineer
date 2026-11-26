"""P1-2B-0: teacher-forced strike evaluation of competing solo strike references (reports/PHASE1_GATE2B_PLAN.md). Rules see only information strictly before each real solo sell. No engine change, no fitting except the preregistered S5 constant (leave-one-cycle-out)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_common, bl_fr_sim as S, bl_ohlc
OUT = bl_common.OUT; OPEN_S = 33300; FGRID = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
LR = pd.read_csv(f'{OUT}/bodysell/ledger_real.csv'); solo = LR[LR.inferred_module == 'solo'].copy(); REAL = S.REAL.copy(); REAL['cyc'] = REAL.und + '|' + REAL.expiry
cyc_ix = {f'{r.und}|{r.expiry}': i for i, r in enumerate(S.CY.itertuples())}; PREP = {c: S.prep(i) for c, i in cyc_ix.items()}
def snap(K, x): return float(K[np.argmin(np.abs(K - x))])
rows = []
for cyc, z in solo.groupby('cyc'):
    d = PREP[cyc]; K = d['K']; ki = d['ki']; step = d['step']; op = d['op']; sp = S.OH[tuple(cyc.split('|'))]; close = sp.close.values; opn = sp.open.values; R = REAL[REAL.cyc == cyc].sort_values('row'); sells = R[(R.role == 'open_short')]
    for o in z.itertuples():
        j = int((o.t - OPEN_S) // 60)
        if j < 1: continue
        prev_same = sells[(sells.cp == o.cp) & (sells.row < o.row)]; other = 'PE' if o.cp == 'CE' else 'CE'; prev_oth = sells[(sells.cp == other) & (sells.row < o.row)]
        jp = min(j - 1, len(close) - 1); a0 = snap(K, close[jp]); cand = [float(k) for k in K if abs(k - a0) <= 4 * step]; prem = lambda cp, k: float(op[(cp, 'close')][ki[int(k)], jp])      # bars end at minute 374: later orders use the last bar (as the replay does)
        rec = dict(cyc=cyc, row=int(o.row), cp=o.cp, t=int(o.t), minute=j, real=float(o.strike), step=step, atm_prev=a0, late=bool(o.t >= OPEN_S + 345 * 60), und=cyc.split('|')[0], has_last=len(prev_same) > 0, has_other=len(prev_oth) > 0, in_window=bool(abs(o.strike - a0) <= 4 * step + 1e-9))
        rec['S0'] = a0; rec['S3'] = snap(K, opn[min(j, len(opn) - 1)])
        pr = np.array([prem(o.cp, k) for k in cand])
        for f in FGRID: rec[f'S5_{f}'] = cand[int(np.argmin(np.abs(pr - f * prem(o.cp, a0))))]
        if len(prev_same):
            L = prev_same.iloc[-1]; lp = float(L.px_avg); rec['S1'] = cand[int(np.argmin(np.abs(pr - lp)))]; rec['S1r'] = cand[int(np.argmin(np.abs(np.log(np.clip(pr, 1e-6, None) / lp))))]; rec['S2'] = float(L.strike)
            jl = int((L.t_first - OPEN_S) // 60); al = snap(K, close[min(max(jl - 1, 0), len(close) - 1)]); rec['S4'] = snap(K, a0 + (float(L.strike) - al))
        if len(prev_oth):
            lpo = float(prev_oth.iloc[-1].px_avg); rec['S6'] = cand[int(np.argmin(np.abs(pr - lpo)))]
        rows.append(rec)
D = pd.DataFrame(rows); RULES = ['S0', 'S1', 'S1r', 'S2', 'S3', 'S4', 'S6'] + [f'S5_{f}' for f in FGRID]
for r in RULES: D[f'{r}_ex'] = (D[r] == D.real) & D[r].notna(); D[f'{r}_w1'] = ((D[r] - D.real).abs() <= D.step + 1e-9) & D[r].notna()
D.to_csv(f'{OUT}/phase1/2B_strike_eval.csv', index=False); res = dict(orders=int(len(D)), with_last_same_side=int(D.has_last.sum()), with_last_other=int(D.has_other.sum()), real_within_window=float(D.in_window.mean()))
# common population (all rules defined): has_last and has_other
C = D[D.has_last & D.has_other]; res['common_population'] = int(len(C)); tab = []
for r in RULES: x = D[D[r].notna()]; tab.append(dict(rule=r, n_own=int(len(x)), exact_own=float(x[f'{r}_ex'].mean()), w1_own=float(x[f'{r}_w1'].mean()), exact_common=float(C[f'{r}_ex'].mean()) if C[r].notna().all() else None, w1_common=float(C[f'{r}_w1'].mean()) if C[r].notna().all() else None))
res['rules'] = tab
# cluster bootstrap of exact(X) - exact(S1) on the population with a last same-side sale
P = D[D.has_last]; cycs = sorted(P.cyc.unique()); rng = np.random.default_rng(7); boot = {}
per = {c: P[P.cyc == c] for c in cycs}
def diff(sel, X): 
    a = np.concatenate([per[c][f'{X}_ex'].values for c in sel]).mean(); b = np.concatenate([per[c]['S1_ex'].values for c in sel]).mean(); return a - b
supp = {}
for X in ['S0', 'S1r', 'S2', 'S3', 'S4'] + [f'S5_{f}' for f in FGRID]:
    d0 = diff(cycs, X); bs = [diff(list(rng.choice(cycs, len(cycs))), X) for _ in range(4000)]; better = sum(per[c][f'{X}_ex'].mean() >= per[c]['S1_ex'].mean() for c in cycs)
    supp[X] = dict(diff_exact_vs_S1=float(d0), ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], cycles_ge_S1=int(better))
res['vs_S1_on_orders_with_last_sale'] = supp
# S6 on its own population vs S1 on the same population
Q = D[D.has_last & D.has_other]; res['S6_vs_S1_common'] = dict(n=int(len(Q)), S6=float(Q.S6_ex.mean()), S1=float(Q.S1_ex.mean()))
# S5: leave-one-cycle-out choice of f
chosen = []; hits = n = 0
for c in cycs:
    oth = P[P.cyc != c]; best = max(FGRID, key=lambda f: oth[f'S5_{f}_ex'].mean()); chosen.append(best); hits += int(per[c][f'S5_{best}_ex'].sum()); n += len(per[c])
mod = pd.Series(chosen).value_counts(); res['S5_LOCO'] = dict(chosen_counts={str(k): int(v) for k, v in mod.items()}, modal_share=float(mod.iloc[0] / len(chosen)), heldout_exact=float(hits / n), S1_exact=float(P.S1_ex.mean()), advantage=float(hits / n - P.S1_ex.mean()))
# ceilings: union of S0-S4,S6 and S5 at LOCO-modal f
fm = float(mod.index[0]); union = (D[['S0_ex', 'S1_ex', 'S1r_ex', 'S2_ex', 'S3_ex', 'S4_ex', 'S6_ex', f'S5_{fm}_ex']].any(axis=1)); res['ceilings'] = dict(real_in_window=float(D.in_window.mean()), union_exact=float(union.mean()), union_exact_orders_with_last=float(union[D.has_last].mean()), union_of=['S0', 'S1', 'S1r', 'S2', 'S3', 'S4', 'S6', f'S5_{fm}'])
res['by_group_S1_vs_best'] = {g: {k: float(v) for k, v in D.groupby(g)['S1_ex'].mean().items()} for g in ('und', 'late')}
json.dump(res, open(f'{OUT}/phase1/2B_strike_eval.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
