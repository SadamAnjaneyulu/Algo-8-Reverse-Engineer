"""Tracker study block T2 (plan BODY_REACTIVE_TRACKER_PLAN.md): forward-simulated per-minute trackers with state reset on fire, scored against the actual reactive pair minutes.
Outputs bl_trk_sim_all.csv (every configuration, in-sample), bl_trk_sim_cv.csv (out-of-fold, parameter chosen on the other cycle half), bl_trk_sim_fires.csv (out-of-fold fire times), bl_summary_trk2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(2026); R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); ch = Chain(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv')
J0, J1 = 75, 360; NB = [30, 45, 60, 90]; KS = [1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 40, 50, 60]; TH = [0.5, 1, 1.5, 2, 3, 4, 5, 6, 8]
CYC = []
for i, r in enumerate(CY.itertuples()):
    c = ch.cyc(r.und, r.expiry); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[r.und]; g = Pr[(Pr.und == r.und) & (Pr.expiry == r.expiry)]
    pa = P[(P.und == r.und) & (P.expiry == r.expiry)]; A = pa[pa.y == 1].j.values.astype(int); side_a = dict(zip(pa[pa.y == 1].j.values.astype(int), pa[pa.y == 1].pair_dir.values)); sched_j = np.unique(((g[g.sched].te.values - 33300) // 60).astype(int))
    d = dict(cid=i, und=r.und, expiry=r.expiry, sp=sp, step=step, A=A, side_a=side_a, sched_j=sched_j)
    for var in ('bar', 'intra'):
        cl = {j: (sp[j - 1] if var == 'bar' else sp[j]) for j in range(J0, J1 + 1)}; d[var + '_c'] = cl
        for N in NB: d[f'{var}_hi{N}'] = {j: sp[max((j - 1 if var == 'bar' else j) - N, 0):(j - 1 if var == 'bar' else j)].max() for j in range(J0, J1 + 1)}; d[f'{var}_lo{N}'] = {j: sp[max((j - 1 if var == 'bar' else j) - N, 0):(j - 1 if var == 'bar' else j)].min() for j in range(J0, J1 + 1)}
    CYC.append(d)
def run(d, fam, var, p):
    """returns list of (minute, side)"""
    out = []; cl = d[var + '_c']; step = d['step']
    if fam in ('M0', 'M1', 'M1ss'):
        N, K = p; last = -999; lside = 0
        for j in range(J0, J1 + 1):
            c = cl[j]; s = 1 if c > d[f'{var}_hi{N}'][j] else (-1 if c < d[f'{var}_lo{N}'][j] else 0)
            if s == 0: continue
            if fam == 'M0' or (fam == 'M1' and j - last >= K) or (fam == 'M1ss' and (j - last >= K or s != lside)): out.append((j, s)); last = j; lside = s
    elif fam in ('M2', 'M2s'):
        th = p[0] * step; Rf = cl[J0]; sj = set(d['sched_j']) if fam == 'M2s' else set()
        for j in range(J0, J1 + 1):
            c = cl[j]
            if j in sj: Rf = c; continue
            if abs(c - Rf) >= th: out.append((j, 1 if c > Rf else -1)); Rf = c
    elif fam == 'M3':
        th = p[0] * step; lo = hi = cl[J0]
        for j in range(J0, J1 + 1):
            c = cl[j]; lo = min(lo, c); hi = max(hi, c)
            if c - lo >= th: out.append((j, 1)); lo = hi = c
            elif hi - c >= th: out.append((j, -1)); lo = hi = c
    elif fam == 'M4':
        th = p[0] * step; lo = hi = cl[J0]; N = 60
        for j in range(J0, J1 + 1):
            c = cl[j]; lo = min(lo, c); hi = max(hi, c); s = 1 if c > d[f'{var}_hi{N}'][j] else (-1 if c < d[f'{var}_lo{N}'][j] else 0)
            if s == 1 and c - lo >= th or s == -1 and hi - c >= th: out.append((j, s)); lo = hi = c
    return out
def match(F, A, tol):
    A = list(A); tp = 0; used = set()
    for f in sorted(F):
        best = None
        for a in A:
            if a in used or abs(a - f) > tol: continue
            if best is None or abs(a - f) < abs(best - f): best = a
        if best is not None: used.add(best); tp += 1
    return tp
def score(d, fires, tol): F = [f for f, _ in fires]; return match(F, d['A'], tol), len(F), len(d['A'])
CONFIGS = []
for var in ('bar', 'intra'):
    for N in NB: CONFIGS.append(('M0', var, (N, 0)))
    for fam in ('M1', 'M1ss'):
        for N in NB:
            for K in KS: CONFIGS.append((fam, var, (N, K)))
    for fam in ('M2', 'M2s', 'M3', 'M4'):
        for t in TH: CONFIGS.append((fam, var, (t,)))
R['n_configs'] = len(CONFIGS); print(len(CONFIGS), 'configurations')
FIRES = {}; rows = []
for cfg in CONFIGS:
    fam, var, p = cfg; res = []
    for d in CYC:
        fi = run(d, fam, var, p); FIRES[(cfg, d['cid'])] = fi; res.append((score(d, fi, 0), score(d, fi, 1)))
    tp0 = sum(r[0][0] for r in res); tp1 = sum(r[1][0] for r in res); nf = sum(r[0][1] for r in res); na = sum(r[0][2] for r in res)
    rows.append(dict(family=fam, info=var, params=str(p), cfg=cfg, fires=nf, actual=na, precision_tol0=tp0 / max(nf, 1), recall_tol0=tp0 / na, precision_tol1=tp1 / max(nf, 1), recall_tol1=tp1 / na, F1_tol1=2 * tp1 / max(nf + na, 1), F1_tol0=2 * tp0 / max(nf + na, 1)))
ALL = pd.DataFrame(rows); ALL.drop(columns='cfg').round(4).to_csv(f'{OUT}/bl_trk_sim_all.csv', index=False)
print(ALL.sort_values('F1_tol1', ascending=False).drop(columns='cfg').head(12).round(3).to_string(index=False))
# cross-validated selection per (family, info): fit params on one cycle half, score on the other half
def fold_scores(cfg, cycs, tol):
    tp = nf = na = 0
    for d in cycs: s = score(d, FIRES[(cfg, d['cid'])], tol); tp += s[0]; nf += s[1]; na += s[2]
    return tp, nf, na
cvrows = []; fire_rows = []
for fam in ['M0', 'M1', 'M1ss', 'M2', 'M2s', 'M3', 'M4']:
    for var in ('bar', 'intra'):
        cfgs = [c for c in CONFIGS if c[0] == fam and c[1] == var]; tot = dict(tp0=0, tp1=0, nf=0, na=0); chosen = []; sel_fires = {}
        for h in (0, 1):
            tr = [d for d in CYC if d['cid'] % 2 == h]; te = [d for d in CYC if d['cid'] % 2 != h]
            best = max(cfgs, key=lambda c: (lambda t: 2 * t[0] / max(t[1] + t[2], 1))(fold_scores(c, tr, 1))); chosen.append(best[2])
            tp0, nf, na = fold_scores(best, te, 0); tp1, _, _ = fold_scores(best, te, 1); tot['tp0'] += tp0; tot['tp1'] += tp1; tot['nf'] += nf; tot['na'] += na
            for d in te: sel_fires[d['cid']] = FIRES[(best, d['cid'])]
        # null: circular shift of each cycle's fire minutes by a random offset
        nl = []
        for _ in range(1000):
            tp1 = 0; nf = 0
            for d in CYC:
                fi = [f for f, _ in sel_fires[d['cid']]]; off = rng.integers(0, J1 - J0 + 1); fs = [J0 + (f - J0 + off) % (J1 - J0 + 1) for f in fi]; tp1 += match(fs, d['A'], 1); nf += len(fs)
            nl.append(2 * tp1 / (nf + tot['na']))
        side_ok = 0; side_n = 0
        for d in CYC:
            for f, s in sel_fires[d['cid']]:
                for a in (f, f - 1, f + 1):
                    if a in d['A']: side_n += 1; side_ok += int(np.sign(d['side_a'][a]) == s); break
        cvrows.append(dict(family=fam, info=var, configs=len(cfgs), chosen_params=' / '.join(map(str, chosen)), fires=tot['nf'], actual=tot['na'], precision_tol0=tot['tp0'] / max(tot['nf'], 1), recall_tol0=tot['tp0'] / tot['na'], precision_tol1=tot['tp1'] / max(tot['nf'], 1), recall_tol1=tot['tp1'] / tot['na'], F1_tol1=2 * tot['tp1'] / (tot['nf'] + tot['na']), null_F1_mean=np.mean(nl), null_F1_p99=np.quantile(nl, .99), side_agreement_matched=side_ok / max(side_n, 1), n_matched_side=side_n,
                           count_var_over_mean=float(np.var([len(sel_fires[d['cid']]) for d in CYC], ddof=1) / max(np.mean([len(sel_fires[d['cid']]) for d in CYC]), 1e-9)), mean_fires_per_cycle=float(np.mean([len(sel_fires[d['cid']]) for d in CYC]))))
        for cid_, fi in sel_fires.items():
            for f, s in fi: fire_rows.append(dict(family=fam, info=var, cid=cid_, minute=f, side=s))
CV = pd.DataFrame(cvrows); CV.round(4).to_csv(f'{OUT}/bl_trk_sim_cv.csv', index=False); pd.DataFrame(fire_rows).to_csv(f'{OUT}/bl_trk_sim_fires.csv', index=False)
print(CV.round(3).to_string(index=False)); R['best_cv'] = CV.sort_values('F1_tol1', ascending=False).head(3)[['family', 'info', 'F1_tol1', 'precision_tol1', 'recall_tol1', 'null_F1_p99']].round(4).to_dict('records'); R['actual_pair_minutes'] = int(sum(len(d['A']) for d in CYC)); rec('trk2', R)
