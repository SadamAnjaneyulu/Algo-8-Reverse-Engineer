"""Tracker study T4 (POST-HOC): does adding a daily capacity (cap on fires) or a refractory that grows with the number of fires improve the stateful range-edge machine and its count regularity?
Alternating-half selection as before. Outputs bl_trk_cap.csv, bl_summary_trk5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
sys.argv = ['x']; exec(open('bl_trk_sim2.py').read().split("CONFIGS = [")[0])
R = {}; NGc = [60, 70, 80, 90]; KGc = [4, 6, 8, 10, 12, 14, 16, 20]; CAPS = [8, 10, 11, 12, 13, 14, 15, 16, 18, 99]; KAPPA = [0, 0.5, 1.0, 2.0]
def run2(d, N, K0, cap, kap, var='bar'):
    c, hi, lo = get(d, var, N); out = []; last = -999
    for j in range(J0, J1 + 1):
        if len(out) >= cap: break
        s = 1 if c[j] > hi[j] else (-1 if c[j] < lo[j] else 0)
        if s and j - last >= K0 + kap * len(out): out.append((j, s)); last = j
    return out
CF = [(N, K, cap, kap) for N in NGc for K in KGc for cap in CAPS for kap in KAPPA]; R['n_configs'] = len(CF); TP = {}; CNT = {}
for cfg in CF:
    for d in CYC: fi = run2(d, *cfg); TP[(cfg, d['cid'])] = (match([f for f, _ in fi], d['A'], 1), len(fi), len(d['A'])); CNT[(cfg, d['cid'])] = len(fi)
ids = [d['cid'] for d in CYC]
def f1(cfg, cids): tp = sum(TP[(cfg, c)][0] for c in cids); nf = sum(TP[(cfg, c)][1] for c in cids); na = sum(TP[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
rows = []
for name, sub in (('M1 (cap = none, kappa = 0)', [c for c in CF if c[2] == 99 and c[3] == 0]), ('M1 + cap', [c for c in CF if c[3] == 0]), ('M1 + growing refractory', [c for c in CF if c[2] == 99]), ('M1 + cap + growing refractory', CF)):
    tot = dict(tp=0, nf=0, na=0); ch_ = []; cnts = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(sub, key=lambda c: f1(c, tr)); ch_.append(b)
        for i in te: t = TP[(b, i)]; tot['tp'] += t[0]; tot['nf'] += t[1]; tot['na'] += t[2]; cnts.append(CNT[(b, i)])
    rows.append(dict(model=name, configs=len(sub), chosen=' / '.join(map(str, ch_)), precision=tot['tp'] / tot['nf'], recall=tot['tp'] / tot['na'], F1=2 * tot['tp'] / (tot['nf'] + tot['na']), fires_per_cycle=np.mean(cnts), count_var_over_mean=np.var(cnts, ddof=1) / np.mean(cnts), count_sd=np.std(cnts, ddof=1)))
C = pd.DataFrame(rows); C.round(4).to_csv(f'{OUT}/bl_trk_cap.csv', index=False); print(C.round(3).to_string(index=False)); R['rows'] = C.round(4).to_dict('records')
act = [len(d['A']) for d in CYC]; R['actual_pair_minutes_per_cycle'] = dict(mean=float(np.mean(act)), sd=float(np.std(act, ddof=1)), var_over_mean=float(np.var(act, ddof=1) / np.mean(act)))
# split-sample robustness of the best 'with cap' model
rng2 = np.random.default_rng(5); sp = []
sub = CF
for s in range(60):
    perm = rng2.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:])
    for tr, te in ((a, b_), (b_, a)):
        b = max(sub, key=lambda c: f1(c, tr)); sp.append(f1(b, te))
R['random_split_F1_all_extensions'] = [float(np.mean(sp)), float(np.quantile(sp, .025)), float(np.quantile(sp, .975))]; print(R['random_split_F1_all_extensions'], R['actual_pair_minutes_per_cycle']); rec('trk5', R)
