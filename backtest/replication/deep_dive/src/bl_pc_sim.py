"""Pace-tracker study (POST-HOC to the book study, motivated by the pace-deficit finding): forward-simulated machines with NO cooldown timer.
M10: fire when beyond the trailing N-min range AND (target cumulative reactive pairs T(t) = (t - t0)/D) - (own fires so far) >= theta.
M11: same with a target for ALL pairs: T_tot(t) = (t - t0)/D vs (scheduled pairs placed so far [actual times, exogenous] + own fires).
M12: non-parametric target = mean cumulative reactive pairs of the OTHER cycles at that time (leave-one-out), fire when edge AND deficit >= theta.
Baselines: M0 stateless edge, M1 edge + refractory K. Selection on alternating halves, 100 random splits, cross-instrument, null by random shifts. Outputs bl_pc_cv.csv, bl_pc_splits.csv, bl_pc_cross.csv, bl_pc_fires.csv, bl_summary_pc1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_trk_sim2.py').read().split("CONFIGS = [")[0]; sys.argv = ['x']; exec(src)
rng = np.random.default_rng(1212); R = {}
for d in CYC:
    g = Pr[(Pr.und == d['und']) & (Pr.expiry == CY.expiry.iloc[d['cid']])]; d['sched_j'] = np.sort(((g[g.sched].te.values - 33300) // 60).astype(int)); d['react_j'] = np.sort(((g[g.reactive].te.values - 33300) // 60).astype(int))
# leave-one-out mean cumulative reactive pairs by minute
cumR = np.array([[np.sum(d['react_j'] <= j) for j in range(J0, J1 + 1)] for d in CYC], dtype=float); cumRtot = np.array([[np.sum(d['react_j'] <= j) + np.sum(d['sched_j'] <= j) for j in range(J0, J1 + 1)] for d in CYC], dtype=float)
LOO = {d['cid']: (cumR.sum(0) - cumR[i]) / (len(CYC) - 1) for i, d in enumerate(CYC)}; LOOT = {d['cid']: (cumRtot.sum(0) - cumRtot[i]) / (len(CYC) - 1) for i, d in enumerate(CYC)}
def runp(d, fam, var, N, p1, th):
    c, hi, lo = get(d, var, N); out = []; n_own = 0; sj = d['sched_j']
    for j in range(J0, J1 + 1):
        s = 1 if c[j] > hi[j] else (-1 if c[j] < lo[j] else 0)
        if s == 0: continue
        if fam == 'M10': target = max(0.0, (j - J0) / p1)
        elif fam == 'M11': target = max(0.0, (j - 15) / p1)                  # all pairs from the first wave minute (09:30)
        elif fam == 'M12': target = LOO[d['cid']][j - J0]
        elif fam == 'M13': target = LOOT[d['cid']][j - J0]
        own = n_own if fam in ('M10', 'M12') else n_own + int(np.sum(sj <= j))
        if fam == 'M13': own = n_own + int(np.sum(sj <= j))
        if target - own >= th: out.append((j, s)); n_own += 1
    return out
GR = dict(M10=[(N, D_, th) for N in (45, 60, 70, 90) for D_ in (8, 10, 12, 15, 18, 22, 26, 30, 40) for th in (0.5, 1.0)], M11=[(N, D_, th) for N in (45, 60, 70, 90) for D_ in (5, 6, 7, 8, 9, 10, 12) for th in (0.5, 1.0, 2.0)], M12=[(N, 0, th) for N in (45, 60, 70, 90) for th in (0, 0.25, 0.5, 0.75, 1.0, 1.5)], M13=[(N, 0, th) for N in (45, 60, 70, 90) for th in (0, 0.5, 1.0, 1.5, 2.0, 3.0)])
CONFIGS = [(fam, var, *p) for fam, ps in GR.items() for var in ('bar', 'intra') for p in ps]; R['n_configs'] = len(CONFIGS); print(len(CONFIGS), 'pace configurations')
FI = {}; TP = {}
for cfg in CONFIGS:
    for d in CYC: fi = runp(d, *cfg); FI[(cfg, d['cid'])] = fi; TP[(cfg, d['cid'])] = (match([f for f, _ in fi], d['A'], 1), len(fi), len(d['A']))
ids = [d['cid'] for d in CYC]
def f1(cfg, cids): tp = sum(TP[(cfg, c)][0] for c in cids); nf = sum(TP[(cfg, c)][1] for c in cids); na = sum(TP[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
def best(cfgs, cids): return max(cfgs, key=lambda c: f1(c, cids))
rows = []; fire_rows = []
for fam in GR:
    for var in ('bar', 'intra'):
        cfgs = [c for c in CONFIGS if c[0] == fam and c[1] == var]; tot = dict(t0=0, t1=0, t2=0, nf=0, na=0); chosen = []; sel = {}
        for h in (0, 1):
            tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = best(cfgs, tr); chosen.append(b[2:])
            for i in te:
                fi = [f for f, _ in FI[(b, i)]]; A = CYC[i]['A']; tot['t0'] += match(fi, A, 0); tot['t1'] += match(fi, A, 1); tot['t2'] += match(fi, A, 2); tot['nf'] += len(fi); tot['na'] += len(A); sel[i] = FI[(b, i)]
        nl = []
        for _ in range(500):
            tp1 = 0; nf = 0
            for d in CYC:
                fi = [f for f, _ in sel[d['cid']]]; off = rng.integers(0, J1 - J0 + 1); fs = [J0 + (f - J0 + off) % (J1 - J0 + 1) for f in fi]; tp1 += match(fs, d['A'], 1); nf += len(fs)
            nl.append(2 * tp1 / (nf + tot['na']))
        cnt = [len(sel[i]) for i in ids]; ins = best(cfgs, ids)
        rows.append(dict(family=fam, info=var, configs=len(cfgs), chosen=' / '.join(map(str, chosen)), fires=tot['nf'], actual=tot['na'], precision_tol1=tot['t1'] / tot['nf'], recall_tol1=tot['t1'] / tot['na'], F1_tol1=2 * tot['t1'] / (tot['nf'] + tot['na']), F1_tol0=2 * tot['t0'] / (tot['nf'] + tot['na']), F1_tol2=2 * tot['t2'] / (tot['nf'] + tot['na']), null_p99=np.quantile(nl, .99), fires_per_cycle=np.mean(cnt), count_var_over_mean=np.var(cnt, ddof=1) / np.mean(cnt), insample_best=str(ins[2:]), insample_F1=f1(ins, ids)))
        for i, fi in sel.items():
            for f, s in fi: fire_rows.append(dict(family=fam, info=var, cid=i, minute=f, side=s))
CV = pd.DataFrame(rows); CV.round(4).to_csv(f'{OUT}/bl_pc_cv.csv', index=False); pd.DataFrame(fire_rows).to_csv(f'{OUT}/bl_pc_fires.csv', index=False); print(CV.round(3).drop(columns=['configs']).to_string(index=False))
top = CV.sort_values('F1_tol1', ascending=False).iloc[0]; fam, var = top['family'], top['info']; cfgs = [c for c in CONFIGS if c[0] == fam and c[1] == var]; sp = []
for s in range(100):
    perm = rng.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:])
    for tr, te in ((a, b_), (b_, a)):
        b = best(cfgs, tr); tp = sum(TP[(b, i)][0] for i in te); nf = sum(TP[(b, i)][1] for i in te); na = sum(TP[(b, i)][2] for i in te); sp.append(dict(split=s, prm=str(b[2:]), precision=tp / nf, recall=tp / na, F1=2 * tp / (nf + na)))
SP = pd.DataFrame(sp); SP.round(4).to_csv(f'{OUT}/bl_pc_splits.csv', index=False); R['top'] = dict(family=fam, info=var); R['splits'] = dict(F1_mean=float(SP.F1.mean()), F1_q=[float(SP.F1.quantile(.025)), float(SP.F1.quantile(.975))], precision=float(SP.precision.mean()), recall=float(SP.recall.mean())); print(R['splits'])
cr = []
for a_, b_ in (('NIFTY', 'SENSEX'), ('SENSEX', 'NIFTY'), ('V1', 'V2'), ('V2', 'V1')):
    if a_ in ('NIFTY', 'SENSEX'): tr = [d['cid'] for d in CYC if d['und'] == a_]; te = [d['cid'] for d in CYC if d['und'] == b_]
    else: tr = [d['cid'] for d in CYC if d['ver'] == int(a_[1]) - 1]; te = [d['cid'] for d in CYC if d['ver'] == int(b_[1]) - 1]
    b = best(cfgs, tr); tp = sum(TP[(b, i)][0] for i in te); nf = sum(TP[(b, i)][1] for i in te); na = sum(TP[(b, i)][2] for i in te); cr.append(dict(fit_on=a_, scored_on=b_, params=str(b[2:]), precision=tp / nf, recall=tp / na, F1=2 * tp / (nf + na)))
CR = pd.DataFrame(cr); CR.round(4).to_csv(f'{OUT}/bl_pc_cross.csv', index=False); print(CR.round(3).to_string(index=False)); R['cross'] = CR.round(4).to_dict('records'); R['table'] = CV.round(4).to_dict('records'); rec('pc1', R)
