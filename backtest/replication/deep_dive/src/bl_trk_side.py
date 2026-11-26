"""Tracker study T5 (POST-HOC): side-specific refractory (K_same after a fire on the same side, K_opp after a fire on the opposite side) on the range-edge machine. Alternating-half selection + 60 random splits. Outputs bl_trk_side.csv, bl_summary_trk7.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
sys.argv = ['x']; exec(open('bl_trk_sim2.py').read().split("CONFIGS = [")[0])
R = {}; NGc = [60, 70, 80, 90]; KS = [2, 4, 6, 8, 12, 16, 20, 30, 40]; KO = [1, 2, 4, 6, 8, 12, 16, 20]
def run3(d, N, ks, ko, var='bar'):
    c, hi, lo = get(d, var, N); out = []; last = -999; ls = 0
    for j in range(J0, J1 + 1):
        s = 1 if c[j] > hi[j] else (-1 if c[j] < lo[j] else 0)
        if s and j - last >= (ks if s == ls else ko): out.append((j, s)); last = j; ls = s
    return out
CF = [(N, ks, ko) for N in NGc for ks in KS for ko in KO]; TP = {}
for cfg in CF:
    for d in CYC: fi = run3(d, *cfg); TP[(cfg, d['cid'])] = (match([f for f, _ in fi], d['A'], 1), len(fi), len(d['A']))
ids = [d['cid'] for d in CYC]
def f1(cfg, cids): tp = sum(TP[(cfg, c)][0] for c in cids); nf = sum(TP[(cfg, c)][1] for c in cids); na = sum(TP[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
def evalsub(sub, name):
    tot = dict(tp=0, nf=0, na=0); ch_ = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(sub, key=lambda c: f1(c, tr)); ch_.append(b)
        for i in te: t = TP[(b, i)]; tot['tp'] += t[0]; tot['nf'] += t[1]; tot['na'] += t[2]
    r2 = np.random.default_rng(9); sp = []
    for s in range(60):
        perm = r2.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:])
        for tr, te in ((a, b_), (b_, a)): sp.append(f1(max(sub, key=lambda c: f1(c, tr)), te))
    return dict(model=name, configs=len(sub), chosen=' / '.join(map(str, ch_)), precision=tot['tp'] / tot['nf'], recall=tot['tp'] / tot['na'], F1=2 * tot['tp'] / (tot['nf'] + tot['na']), split_F1_mean=np.mean(sp), split_F1_lo=np.quantile(sp, .025), split_F1_hi=np.quantile(sp, .975))
rows = [evalsub([c for c in CF if c[1] == c[2]], 'one refractory K for both sides (K_same = K_opp)'), evalsub(CF, 'side-specific refractory (K_same, K_opp)')]
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_trk_side.csv', index=False); print(S.round(3).to_string(index=False)); R['rows'] = S.round(4).to_dict('records'); R['n_configs'] = len(CF)
b = max(CF, key=lambda c: f1(c, ids)); R['insample_best'] = dict(cfg=b, F1=f1(b, ids)); print('in-sample best', b, round(f1(b, ids), 3)); rec('trk7', R)
