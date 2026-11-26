"""Tracker study T2 extension (POST-HOC, added after M1 matched the pairs): finer M1 grid, edge-triggered (M7) and band-reset (M5) variants, 100 random half-splits, cross-instrument validation (fit on NIFTY -> score SENSEX and back), tolerance 0/1/2.
Outputs bl_trk_sim2_cv.csv, bl_trk_sim2_splits.csv, bl_trk_sim2_cross.csv, bl_trk_sim2_fires.csv, bl_summary_trk3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(77); R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); ch = Chain(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv')
J0, J1 = 75, 360; NG = [20, 30, 40, 50, 60, 70, 80, 90, 105, 120, 150]; KG = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 40]
CYC = []
for i, r in enumerate(CY.itertuples()):
    c = ch.cyc(r.und, r.expiry); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; pa = P[(P.und == r.und) & (P.expiry == r.expiry)]
    CYC.append(dict(cid=i, und=r.und, sp=sp, A=pa[pa.y == 1].j.values.astype(int), ver=int(pa.v2.iloc[0])))
def bands(sp, var, N):
    off = 1 if var == 'bar' else 0; hi = np.full(375, np.nan); lo = np.full(375, np.nan); c = np.full(375, np.nan)
    for j in range(J0 - 1, J1 + 1):
        e = j - off + 0; w = sp[max(e - N, 0):e]; hi[j] = w.max(); lo[j] = w.min(); c[j] = sp[e]
    return c, hi, lo
CACHE = {}
def get(d, var, N):
    k = (d['cid'], var, N)
    if k not in CACHE: CACHE[k] = bands(d['sp'], var, N)
    return CACHE[k]
def run(d, fam, var, N, K):
    c, hi, lo = get(d, var, N); out = []; last = -999; prev = 0
    for j in range(J0, J1 + 1):
        if fam == 'M5':
            e = j - (1 if var == 'bar' else 0); st = max(e - N, 0, last - (1 if var == 'bar' else 0) if last > 0 else 0); w = d['sp'][st:e]
            if len(w) < max(K, 2): continue
            s = 1 if c[j] > w.max() else (-1 if c[j] < w.min() else 0)
            if s: out.append((j, s)); last = j
            continue
        s = 1 if c[j] > hi[j] else (-1 if c[j] < lo[j] else 0)
        ok = s != 0 and (j - last >= K) and (fam == 'M1' or prev != s)
        if ok: out.append((j, s)); last = j
        prev = s
    return out
def match(F, A, tol):
    used = set(); tp = 0
    for f in sorted(F):
        best = None
        for a in A:
            if a in used or abs(a - f) > tol: continue
            if best is None or abs(a - f) < abs(best - f): best = a
        if best is not None: used.add(best); tp += 1
    return tp
CONFIGS = [(f, v, N, K) for f in ('M1', 'M7', 'M5') for v in ('bar', 'intra') for N in NG for K in KG]; R['n_configs'] = len(CONFIGS); print(len(CONFIGS), 'configs')
FI = {}; TP = {}   # per config per cycle: fires, tp at tol 1
for cfg in CONFIGS:
    for d in CYC: fi = run(d, *cfg); FI[(cfg, d['cid'])] = fi; TP[(cfg, d['cid'])] = (match([f for f, _ in fi], d['A'], 1), len(fi), len(d['A']))
def f1(cfg, cids): tp = sum(TP[(cfg, c)][0] for c in cids); nf = sum(TP[(cfg, c)][1] for c in cids); na = sum(TP[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
def best_cfg(cfgs, cids): return max(cfgs, key=lambda c: f1(c, cids))
ids = [d['cid'] for d in CYC]; rows = []
for fam in ('M1', 'M7', 'M5'):
    for var in ('bar', 'intra'):
        cfgs = [c for c in CONFIGS if c[0] == fam and c[1] == var]; tot = dict(t0=0, t1=0, t2=0, nf=0, na=0); chosen = []
        for h in (0, 1):
            tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = best_cfg(cfgs, tr); chosen.append(b[2:])
            for i in te:
                fi = [f for f, _ in FI[(b, i)]]; A = CYC[i]['A']; tot['t0'] += match(fi, A, 0); tot['t1'] += match(fi, A, 1); tot['t2'] += match(fi, A, 2); tot['nf'] += len(fi); tot['na'] += len(A)
        ins = best_cfg(cfgs, ids)
        rows.append(dict(family=fam, info=var, configs=len(cfgs), chosen_params=' / '.join(map(str, chosen)), fires=tot['nf'], actual=tot['na'], precision_tol1=tot['t1'] / tot['nf'], recall_tol1=tot['t1'] / tot['na'], F1_tol1=2 * tot['t1'] / (tot['nf'] + tot['na']), F1_tol0=2 * tot['t0'] / (tot['nf'] + tot['na']), F1_tol2=2 * tot['t2'] / (tot['nf'] + tot['na']), insample_best=str(ins[2:]), insample_F1_tol1=f1(ins, ids)))
CV = pd.DataFrame(rows); CV.round(4).to_csv(f'{OUT}/bl_trk_sim2_cv.csv', index=False); print(CV.round(3).to_string(index=False))
# 100 random half splits for the best family/info (decided by the alternating split result, reported)
top = CV.sort_values('F1_tol1', ascending=False).iloc[0]; fam, var = top['family'], top['info']; cfgs = [c for c in CONFIGS if c[0] == fam and c[1] == var]; sp_rows = []
for s in range(100):
    perm = rng.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:]); 
    for tr, te in ((a, b_), (b_, a)):
        b = best_cfg(cfgs, tr); tp = sum(TP[(b, i)][0] for i in te); nf = sum(TP[(b, i)][1] for i in te); na = sum(TP[(b, i)][2] for i in te); sp_rows.append(dict(split=s, N=b[2], K=b[3], precision=tp / nf, recall=tp / na, F1=2 * tp / (nf + na)))
SP = pd.DataFrame(sp_rows); SP.round(4).to_csv(f'{OUT}/bl_trk_sim2_splits.csv', index=False); R['splits'] = dict(family=fam, info=var, F1_mean=float(SP.F1.mean()), F1_q=[float(SP.F1.quantile(.025)), float(SP.F1.quantile(.975))], precision_mean=float(SP.precision.mean()), recall_mean=float(SP.recall.mean()), N_mode=int(SP.N.mode()[0]), K_mode=int(SP.K.mode()[0]), N_share=SP.N.value_counts(normalize=True).round(3).to_dict(), K_share=SP.K.value_counts(normalize=True).round(3).to_dict())
print(SP[['precision', 'recall', 'F1']].describe().round(3)); print(R['splits'])
# cross-instrument: fit on one underlying, score the other (frozen)
cr = []
for a_, b_ in (('NIFTY', 'SENSEX'), ('SENSEX', 'NIFTY'), ('V1', 'V2'), ('V2', 'V1')):
    if a_ in ('NIFTY', 'SENSEX'): tr = [d['cid'] for d in CYC if d['und'] == a_]; te = [d['cid'] for d in CYC if d['und'] == b_]
    else: tr = [d['cid'] for d in CYC if d['ver'] == int(a_[1]) - 1]; te = [d['cid'] for d in CYC if d['ver'] == int(b_[1]) - 1]
    b = best_cfg(cfgs, tr); tp = sum(TP[(b, i)][0] for i in te); nf = sum(TP[(b, i)][1] for i in te); na = sum(TP[(b, i)][2] for i in te)
    # stateless baseline for the same N on the target
    b0 = (fam, var, b[2], 1); base = 'n/a'
    cr.append(dict(fit_on=a_, scored_on=b_, N=b[2], K=b[3], cycles_scored=len(te), precision=tp / nf, recall=tp / na, F1=2 * tp / (nf + na), same_N_K1_F1=f1((fam, var, b[2], 1), te)))
CR = pd.DataFrame(cr); CR.round(4).to_csv(f'{OUT}/bl_trk_sim2_cross.csv', index=False); print(CR.round(3).to_string(index=False)); R['cross'] = CR.round(4).to_dict('records')
# fires of the alternating-half-selected best machine (for the example plots)
fr = []
for h in (0, 1):
    tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = best_cfg(cfgs, tr)
    for i in te:
        for f, s in FI[(b, i)]: fr.append(dict(cid=i, minute=f, side=s, family=b[0], info=b[1], N=b[2], K=b[3]))
pd.DataFrame(fr).to_csv(f'{OUT}/bl_trk_sim2_fires.csv', index=False); R['top'] = top.to_dict(); rec('trk3', R)
