"""Decoding step 4: full-session targets (all reactive pair-minutes 10:30-15:29, not cut at 15:15) and a minimum break margin mu (index points as a fraction of a strike step) for the true-OHLC machine; end-time variants. Alternating-half selection + random splits.
Outputs bl_dq_tune.csv, bl_dq_tune_grid.csv, bl_summary_dq5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_dq_ohlc.py').read().split("rows = []\nfor nm, kw")[0])
R = {}; JE = 374
for d in CYC:
    g = Pr[(Pr.und == d['und']) & (Pr.expiry == d['expiry']) & Pr.reactive]; jj = ((g.te.values - 33300) // 60).astype(int); d['Afull'] = np.unique(jj[(jj >= J0) & (jj <= JE)])
def mach(d, mu=0.0, jend=JE, K=2):
    out = []; done = set()
    for j in range(J0, jend + 1):
        H, L = chan(d, j, K, 'hl')
        if H != H: continue
        b = (33300 + 60 * j) // 1800; m_ = mu * d['step']
        for s, flag in ((1, d['h'][j] > H + m_), (-1, d['l'][j] < L - m_)):
            if flag and (b, s) not in done: out.append((j, s)); done.add((b, s))
    return out
def sc(cfg, cids, key='Afull'):
    tp = tp0 = nf = na = 0
    for i in cids: d = CYC[i]; F_ = [f for f, _ in mach(d, *cfg)]; tp += match(F_, d[key], 1); tp0 += match(F_, d[key], 0); nf += len(F_); na += len(d[key])
    return 2 * tp / (nf + na), tp / nf, tp / na, 2 * tp0 / (nf + na), nf, na
GR = [(mu, je) for mu in (0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3) for je in (330, 345, 350, 355, 360, 365, 370, 374)]
cache = {cfg: {i: None for i in range(len(CYC))} for cfg in GR}
TP = {}
for cfg in GR:
    for d in CYC: F_ = [f for f, _ in mach(d, *cfg)]; TP[(cfg, d['cid'])] = (match(F_, d['Afull'], 1), len(F_), len(d['Afull']), match(F_, d['Afull'], 0))
ids = list(range(len(CYC)))
def f1(cfg, cids): tp = sum(TP[(cfg, c)][0] for c in cids); nf = sum(TP[(cfg, c)][1] for c in cids); na = sum(TP[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
G = pd.DataFrame([dict(mu_steps=c[0], end_minute=c[1], end_clock=f'{(33300 + 60 * c[1]) // 3600}:{(33300 + 60 * c[1]) % 3600 // 60:02d}', F1=f1(c, ids)) for c in GR]); G.round(4).to_csv(f'{OUT}/bl_dq_tune_grid.csv', index=False); print(G.pivot(index='mu_steps', columns='end_clock', values='F1').round(3).to_string())
rows = []
base = (0, 360); rows.append(dict(variant='base (mu 0, end 15:15), scored on full-session targets', **dict(zip(['F1', 'precision', 'recall', 'F1_same_minute', 'fires', 'targets'], sc(base, ids)))))
full = (0, 374); rows.append(dict(variant='mu 0, end 15:29 (full session)', **dict(zip(['F1', 'precision', 'recall', 'F1_same_minute', 'fires', 'targets'], sc(full, ids)))))
tp = nf = na = tp0 = 0; ch_ = []
for h in (0, 1):
    tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(GR, key=lambda c: f1(c, tr)); ch_.append(b)
    for i in te: t = TP[(b, i)]; tp += t[0]; nf += t[1]; na += t[2]; tp0 += t[3]
rows.append(dict(variant=f'out-of-fold choice of (mu, end): {ch_}', F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na, F1_same_minute=2 * tp0 / (nf + na), fires=nf, targets=na))
r2 = np.random.default_rng(9); sp = []
for s in range(60):
    perm = r2.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:])
    for tr, te in ((a, b_), (b_, a)): sp.append(f1(max(GR, key=lambda c: f1(c, tr)), te))
R['split_F1'] = [float(np.mean(sp)), float(np.quantile(sp, .025)), float(np.quantile(sp, .975))]
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_dq_tune.csv', index=False); print(T.round(3).to_string(index=False)); print('random splits', R['split_F1']); R['rows'] = T.round(4).to_dict('records'); R['best_insample'] = G.sort_values('F1', ascending=False).head(5).round(4).to_dict('records'); rec('dq5', R)
