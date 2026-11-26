"""Decoding step 2b: re-entry rules inside a 30-min candle on top of the true-OHLC machine (first break of the previous two candles' high/low, per side).
Ladder: after an entry at trigger level X (side s), the next entry when the minute's high (low) exceeds X + s*delta*step; X updates to that level. Gap: next entry at a new candle extreme at least g minutes after the previous entry. Cap: at most m entries per side per candle.
Alternating-half selection + 60 random splits. Outputs bl_dq_repeat_sim.csv, bl_summary_dq3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_dq_ohlc.py').read().split("rows = []\nfor nm, kw")[0])
R = {}
def mach2(d, rule, delta=1.0, g=3, m=99, K=2, ref_='trigger'):
    out = []; st = {}
    for j in range(J0, J1 + 1):
        H, L = chan(d, j, K, 'hl')
        if H != H: continue
        b = (33300 + 60 * j) // 1800; b_start = int((b * 1800 - 33300) // 60)
        for s in (1, -1):
            key = (b, s); hit = d['h'][j] > H if s > 0 else d['l'][j] < L
            if key not in st:
                if hit: out.append((j, s)); st[key] = dict(n=1, lvl=(H if s > 0 else L), last=j, px=d['c'][j])
                continue
            S_ = st[key]
            if S_['n'] >= m: continue
            if rule == 'none': continue
            if rule == 'ladder':
                base = S_['lvl'] if ref_ == 'trigger' else S_['px']; lvl = base + s * delta * d['step']
                if (d['h'][j] > lvl if s > 0 else d['l'][j] < lvl): out.append((j, s)); S_.update(n=S_['n'] + 1, lvl=lvl, last=j, px=d['c'][j])
            elif rule == 'gap':
                run = d['h'][b_start:j].max() if s > 0 else d['l'][b_start:j].min()
                if j - S_['last'] >= g and (d['h'][j] > run if s > 0 else d['l'][j] < run): out.append((j, s)); S_.update(n=S_['n'] + 1, last=j)
            elif rule == 'ladder_gap':
                lvl = S_['lvl'] + s * delta * d['step']
                if j - S_['last'] >= g and (d['h'][j] > lvl if s > 0 else d['l'][j] < lvl): out.append((j, s)); S_.update(n=S_['n'] + 1, lvl=lvl, last=j)
    return out
CF = [('none', 0, 0, 99, 'trigger')] + [('ladder', dl, 0, m, rf) for dl in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0) for m in (2, 3, 4, 99) for rf in ('trigger', 'entry_close')] + [('gap', 0, g, m, 'trigger') for g in (1, 2, 3, 5, 8, 12, 15) for m in (2, 3, 4, 99)] + [('ladder_gap', dl, g, 99, 'trigger') for dl in (0.25, 0.5, 1.0) for g in (2, 3, 5, 8)]
TP = {}
for cfg in CF:
    for d in CYC: fi = mach2(d, cfg[0], cfg[1], cfg[2], cfg[3], ref_=cfg[4]); F_ = [f for f, _ in fi]; TP[(cfg, d['cid'])] = (match(F_, d['A'], 1), len(F_), len(d['A']), match(F_, d['A'], 0))
ids = [d['cid'] for d in CYC]
def f1(cfg, cids, k=0): tp = sum(TP[(cfg, c)][k] for c in cids) if k == 0 else sum(TP[(cfg, c)][3] for c in cids); nf = sum(TP[(cfg, c)][1] for c in cids); na = sum(TP[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1)
rows = []
for fam in ('none', 'ladder', 'gap', 'ladder_gap'):
    sub = [c for c in CF if c[0] == fam]; tp = nf = na = tp0 = 0; ch_ = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(sub, key=lambda c: f1(c, tr)); ch_.append(b[1:])
        for i in te: t = TP[(b, i)]; tp += t[0]; nf += t[1]; na += t[2]; tp0 += t[3]
    r2 = np.random.default_rng(4); sp = []
    for s in range(60):
        perm = r2.permutation(ids); a, b_ = list(perm[:16]), list(perm[16:])
        for tr, te in ((a, b_), (b_, a)): sp.append(f1(max(sub, key=lambda c: f1(c, tr)), te))
    ins = max(sub, key=lambda c: f1(c, ids))
    rows.append(dict(rule=fam, configs=len(sub), chosen=' / '.join(map(str, ch_)), precision=tp / nf, recall=tp / na, F1=2 * tp / (nf + na), F1_same_minute=2 * tp0 / (nf + na), split_F1_mean=np.mean(sp), split_lo=np.quantile(sp, .025), split_hi=np.quantile(sp, .975), insample_best=str(ins[1:]), insample_F1=f1(ins, ids)))
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_dq_repeat_sim.csv', index=False); print(S.round(3).to_string(index=False)); R['rows'] = S.round(4).to_dict('records'); R['n_configs'] = len(CF); rec('dq3', R)
