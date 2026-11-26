"""P1-9-A0: decision-level test of H6 (premium-extreme vs spot-extreme indicator of real solo sells). Plan reports/PHASE1_LOOP2_A_PLAN.md (fixed before this ran)."""
import sys, os, json, warnings; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d1_strategy', '../../../..', '..', '../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S
OUT = bl_common.OUT; OD = f'{OUT}/phase1/9'; os.makedirs(OD, exist_ok=True); CY = S.CY; N = 60
LR = pd.read_csv(f'{OUT}/bodysell/ledger_real.csv'); LR['minute'] = LR.minute.astype(int)
rng = np.random.default_rng(0); cells = []
for i, r in enumerate(CY.itertuples()):
    cyc = f'{r.und}|{r.expiry}'; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']; K = np.asarray(d['K'], float); sl = o.low.values; sh = o.high.values; sc = o.close.values; n = len(sc)
    z = LR[LR.cyc == cyc]; solo = {(cp, int(m)) for cp, m in zip(z[z.inferred_module == 'solo'].cp, z[z.inferred_module == 'solo'].minute)}; other = {(cp, int(m)) for cp, m in zip(z[z.inferred_module != 'solo'].cp, z[z.inferred_module != 'solo'].minute)}
    miss = {(cp, int(m)) for cp, m, c in zip(z[z.inferred_module == 'solo'].cp, z[z.inferred_module == 'solo'].minute, z[z.inferred_module == 'solo'].category) if c != 'matched'}
    for cp in ('CE', 'PE'):
        low = op[(cp, 'low')]
        for j in range(1, min(375, n)):
            if (cp, j) in other and (cp, j) not in solo: continue
            lo = max(j - N, 0)
            Sv = bool(sl[j] < sl[lo:j].min()) if cp == 'CE' else bool(sh[j] > sh[lo:j].max())
            c = int(np.argmin(np.abs(K - sc[j - 1]))); Pv = bool(low[c, j] < np.nanmin(low[c, lo:j])) if np.isfinite(low[c, j]) and np.isfinite(low[c, lo:j]).any() else False
            cells.append((cyc, cp, j, int((cp, j) in solo), int((cp, j) in miss), int(Sv), int(Pv)))
D = pd.DataFrame(cells, columns=['cyc', 'cp', 'j', 'y', 'missed', 'S', 'P']); D['U'] = D.S | D.P; D['SP'] = D.S & D.P; D.to_csv(f'{OD}/A_cells.csv', index=False)
def prf(df, col):
    tp = int(((df[col] == 1) & (df.y == 1)).sum()); fp = int(((df[col] == 1) & (df.y == 0)).sum()); fn = int(((df[col] == 0) & (df.y == 1)).sum())
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1); return dict(tp=tp, fp=fp, fn=fn, precision=p, recall=r, F1=2 * p * r / max(p + r, 1e-12), base_rate=float((df[col] == 1).mean()))
res = dict(cells=int(len(D)), real_solo_cells=int(D.y.sum()), b1_missed_solo_cells=int(D.missed.sum()), pooled={c: prf(D, c) for c in ('S', 'P', 'U', 'SP')})
cyc_ids = D.cyc.unique(); B = {c: [] for c in ('P', 'U')}; g = {k: v for k, v in D.groupby('cyc')}
for _ in range(4000):
    pick = rng.choice(cyc_ids, len(cyc_ids)); X = pd.concat([g[k] for k in pick]); fs = prf(X, 'S')
    for c in B: B[c].append(prf(X, c)['F1'] - fs['F1'])
res['bootstrap_dF1_vs_S'] = {c: dict(mean=float(np.mean(v)), lo=float(np.percentile(v, 2.5)), hi=float(np.percentile(v, 97.5))) for c, v in B.items()}
m = D[D.missed == 1]; res['coverage_of_b1_missed'] = {c: float(m[c].mean()) for c in ('S', 'P', 'U')}; res['lift_on_missed'] = {c: float(m[c].mean() / max(D[c].mean(), 1e-9)) for c in ('S', 'P', 'U')}
pS, pP, pU = (res['pooled'][c] for c in ('S', 'P', 'U')); bs = res['bootstrap_dF1_vs_S']
res['criteria'] = dict(PA1=dict(dF1=pP['F1'] - pS['F1'], ci_lo=bs['P']['lo'], passed=bool(pP['F1'] - pS['F1'] >= 0.03 and bs['P']['lo'] > 0)), PA2=dict(coverage=res['coverage_of_b1_missed']['P'], lift=res['lift_on_missed']['P'], passed=bool(res['coverage_of_b1_missed']['P'] >= 0.40 and res['lift_on_missed']['P'] >= 3)), PA3=dict(prec_ratio=pP['precision'] / max(pS['precision'], 1e-9), passed=bool(pP['precision'] >= 0.8 * pS['precision'])),
    U=dict(dF1=pU['F1'] - pS['F1'], ci_lo=bs['U']['lo'], d_recall=pU['recall'] - pS['recall'], prec_ratio=pU['precision'] / max(pS['precision'], 1e-9), passed=bool(pU['F1'] - pS['F1'] >= 0.03 and bs['U']['lo'] > 0 and pU['recall'] >= pS['recall'] + 0.10 and pU['precision'] >= 0.8 * pS['precision'])))
res['P_supported'] = all(res['criteria'][k]['passed'] for k in ('PA1', 'PA2', 'PA3')); res['U_supported'] = res['criteria']['U']['passed']
json.dump(res, open(f'{OD}/A_analytic.json', 'w'), indent=1, default=float); print(json.dumps({k: v for k, v in res.items() if k != 'pooled'}, indent=1, default=float)); print({c: {k: round(v, 4) for k, v in x.items()} for c, x in res['pooled'].items()})
