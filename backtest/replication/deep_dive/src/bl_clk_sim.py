"""Clock-gate study (post-hoc, motivated by the half-hour phase structure of the reactive fires): machines whose eligibility resets at clock-aligned block boundaries, with no pace/cooldown timer.
MC: range edge (N-min rolling) AND minute-of-block < W AND fires in this block < m, block = L minutes aligned to the clock (L=30 -> hh:00/hh:30), phase offset phi minutes (clock alignment test).
Outputs bl_clk_cv.csv, bl_clk_phase.csv, bl_summary_clk1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_trk_sim2.py').read().split("CONFIGS = [")[0]; sys.argv = ['x']; exec(src)
rng = np.random.default_rng(88); R = {}
def runc(d, var, N, L, W, m, phi):
    c, hi, lo = get(d, var, N); out = []; cnt = {}
    for j in range(J0, J1 + 1):
        s = 1 if c[j] > hi[j] else (-1 if c[j] < lo[j] else 0)
        if s == 0: continue
        clock = 33300 + 60 * j; b = int((clock - phi * 60) // (L * 60)); mo = (clock - phi * 60 - b * L * 60) / 60.0
        if mo >= W or cnt.get(b, 0) >= m: continue
        out.append((j, s)); cnt[b] = cnt.get(b, 0) + 1
    return out
CF = [(var, N, L, W, m, phi) for var in ('bar', 'intra') for N in (45, 60, 70, 90) for L in (30,) for W in (1, 2, 3, 5, 8, 12, 20, 30) for m in (1, 2, 3, 99) for phi in (0,)]
CFp = [('bar', 70, 30, W, 1, phi) for W in (3, 5, 10) for phi in range(0, 30, 3)]; R['n_configs'] = len(CF) + len(CFp)
TPd = {}; FId = {}
for cfg in CF + CFp:
    for d in CYC: fi = runc(d, *cfg); FId[(cfg, d['cid'])] = fi; TPd[(cfg, d['cid'])] = (match([f for f, _ in fi], d['A'], 1), len(fi), len(d['A']))
ids = [d['cid'] for d in CYC]
def f1(cfg, cids): tp = sum(TPd[(cfg, c)][0] for c in cids); nf = sum(TPd[(cfg, c)][1] for c in cids); na = sum(TPd[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
rows = []
for var in ('bar', 'intra'):
    sub = [c for c in CF if c[0] == var]; tot = dict(tp=0, nf=0, na=0, t0=0); ch_ = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(sub, key=lambda c: f1(c, tr)); ch_.append(b[1:])
        for i in te: fi = [f for f, _ in FId[(b, i)]]; tot['tp'] += match(fi, CYC[i]['A'], 1); tot['t0'] += match(fi, CYC[i]['A'], 0); tot['nf'] += len(fi); tot['na'] += len(CYC[i]['A'])
    r2 = np.random.default_rng(3); sp = []
    for s in range(60):
        perm = r2.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:])
        for tr, te in ((a, b_), (b_, a)): sp.append(f1(max(sub, key=lambda c: f1(c, tr)), te))
    rows.append(dict(info=var, configs=len(sub), chosen=' / '.join(map(str, ch_)), precision=tot['tp'] / tot['nf'], recall=tot['tp'] / tot['na'], F1=2 * tot['tp'] / (tot['nf'] + tot['na']), F1_same_minute=2 * tot['t0'] / (tot['nf'] + tot['na']), split_F1_mean=np.mean(sp), split_lo=np.quantile(sp, .025), split_hi=np.quantile(sp, .975), insample_best=str(max(sub, key=lambda c: f1(c, ids))[1:]), insample_F1=max(f1(c, ids) for c in sub)))
CV = pd.DataFrame(rows); CV.round(4).to_csv(f'{OUT}/bl_clk_cv.csv', index=False); print(CV.round(3).to_string(index=False))
ph = [dict(W=cfg[3], phase_min=cfg[5], F1=f1(cfg, ids)) for cfg in CFp]; PH = pd.DataFrame(ph); PH.round(4).to_csv(f'{OUT}/bl_clk_phase.csv', index=False); print(PH.pivot(index='phase_min', columns='W', values='F1').round(3).T.to_string())
R['rows'] = CV.round(4).to_dict('records'); R['phase_best'] = PH.sort_values('F1', ascending=False).head(3).round(4).to_dict('records'); rec('clk1', R)
