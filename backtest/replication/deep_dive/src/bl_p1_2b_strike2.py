"""P1-2B-1: addendum rules S8 and S9 (stacking on held strikes), evaluated like P1-2B-0 against S1 on the same orders. No engine change."""
import sys, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_common, bl_fr_sim as S
OUT = bl_common.OUT; D = pd.read_csv(f'{OUT}/phase1/2B_strike_eval.csv'); REAL = S.REAL.copy(); REAL['cyc'] = REAL.und + '|' + REAL.expiry; rows = []
for cyc, z in D.groupby('cyc'):
    R = REAL[REAL.cyc == cyc].sort_values('row')
    for o in z.itertuples():
        pr = R[(R.row < o.row) & (R.cp == o.cp) & (R.role.isin(['open_short', 'cover_short']))]; held = {}
        for r in pr.itertuples(): held[float(r.strike)] = held.get(float(r.strike), 0) + (int(r.lots) if r.role == 'open_short' else -int(r.lots))
        held = {k: v for k, v in held.items() if v > 0}
        if held:
            mx = max(held.values()); top = [k for k, v in held.items() if v == mx]; s8 = min(top, key=lambda k: (abs(k - o.atm_prev), k)); s9 = min(held, key=lambda k: (abs(k - o.atm_prev), k))
        else: s8 = s9 = o.atm_prev
        rows.append((o.Index, s8, s9, len(held)))
X = pd.DataFrame(rows, columns=['i', 'S8', 'S9', 'n_held']).set_index('i'); D['S8'] = X.S8; D['S9'] = X.S9; D['n_held'] = X.n_held
for r in ('S8', 'S9'): D[f'{r}_ex'] = D[r] == D.real; D[f'{r}_w1'] = (D[r] - D.real).abs() <= D.step + 1e-9
P = D[D.has_last]; cycs = sorted(P.cyc.unique()); per = {c: P[P.cyc == c] for c in cycs}; rng = np.random.default_rng(11); res = {'n': int(len(P)), 'S1_exact': float(P.S1_ex.mean()), 'orders_with_any_held_strike': float((P.n_held > 0).mean())}
for X_ in ('S8', 'S9'):
    f = lambda sel: np.concatenate([per[c][f'{X_}_ex'].values for c in sel]).mean() - np.concatenate([per[c]['S1_ex'].values for c in sel]).mean(); bs = [f(list(rng.choice(cycs, len(cycs)))) for _ in range(4000)]
    res[X_] = dict(exact=float(P[f'{X_}_ex'].mean()), within1=float(P[f'{X_}_w1'].mean()), diff_vs_S1=float(f(cycs)), ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], cycles_ge_S1=int(sum(per[c][f'{X_}_ex'].mean() >= per[c]['S1_ex'].mean() for c in cycs)))
    res[X_]['supported'] = bool(res[X_]['diff_vs_S1'] >= 0.05 and res[X_]['ci95'][0] > 0 and res[X_]['cycles_ge_S1'] >= 20)
D.to_csv(f'{OUT}/phase1/2B_strike_eval_with_S8_S9.csv', index=False); json.dump(res, open(f'{OUT}/phase1/2B_strike_eval_S8_S9.json', 'w'), indent=1); print(json.dumps(res, indent=1))
