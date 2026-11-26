"""Clock-gate study: what is the range? Inside the one-fire-per-30-min-clock-block machine (phase 0), compare channel definitions: rolling N minutes vs K completed clock bars (+ current partial bar) vs K completed bars only vs previous-day-style fixed anchors. In-sample F1 (+-1 min) and out-of-fold alternating-half F1 for the best of each family.
Outputs bl_clk_chan.csv, bl_summary_clk3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_clk_sim.py').read().split("CF = [")[0]; sys.argv = ['x']; exec(src)
ids = [d['cid'] for d in CYC]; Lb = 1800
def chan(d, j, kind, p, var='bar'):
    sp = d['sp']; e = j - 1 if var == 'bar' else j; clock = 33300 + 60 * j; b0 = (clock // Lb) * Lb; i_b0 = int(np.ceil((b0 - 33300) / 60))                 # first minute index at or after the current block start
    if kind == 'roll': a = max(e - p, 0)
    elif kind == 'bars_cur': a = max(int(np.ceil((b0 - p * Lb - 33300) / 60)), 0)                                                              # K completed bars + current partial
    elif kind == 'bars_prev': a = max(int(np.ceil((b0 - p * Lb - 33300) / 60)), 0); e = max(i_b0, a + 2)                                          # K completed bars only
    w = sp[a:e]
    return (w.max(), w.min()) if len(w) >= 2 else (np.nan, np.nan)
def run(d, kind, p, var='bar', phi=0):
    out = []; cnt = {}; sp = d['sp']
    for j in range(J0, J1 + 1):
        c = sp[j - 1] if var == 'bar' else sp[j]; hi, lo = chan(d, j, kind, p, var)
        if hi != hi: continue
        s = 1 if c > hi else (-1 if c < lo else 0)
        if s == 0: continue
        b = int((33300 + 60 * j - phi * 60) // Lb)
        if cnt.get(b, 0) >= 1: continue
        out.append((j, s)); cnt[b] = 1
    return out
CF = [('roll', N) for N in (40, 50, 60, 70, 80, 90, 105, 120, 150)] + [('bars_cur', K) for K in (1, 2, 3, 4, 5)] + [('bars_prev', K) for K in (1, 2, 3, 4, 6)]
TPd = {}
for cfg in CF:
    for d in CYC: fi = run(d, *cfg); TPd[(cfg, d['cid'])] = (match([f for f, _ in fi], d['A'], 1), len(fi), len(d['A']))
def f1(cfg, cids): tp = sum(TPd[(cfg, c)][0] for c in cids); nf = sum(TPd[(cfg, c)][1] for c in cids); na = sum(TPd[(cfg, c)][2] for c in cids); return 2 * tp / max(nf + na, 1), tp / max(nf, 1), tp / na, nf
rows = [dict(kind=k, param=p, F1=f1((k, p), ids)[0], precision=f1((k, p), ids)[1], recall=f1((k, p), ids)[2], fires=f1((k, p), ids)[3]) for k, p in CF]
CH = pd.DataFrame(rows); CH.round(4).to_csv(f'{OUT}/bl_clk_chan.csv', index=False); print(CH.round(3).to_string(index=False))
R = {'rows': CH.round(4).to_dict('records')}
# out-of-fold best per family
for fam in ('roll', 'bars_cur', 'bars_prev'):
    sub = [c for c in CF if c[0] == fam]; tp = nf = na = 0; ch_ = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(sub, key=lambda c: f1(c, tr)[0]); ch_.append(b[1])
        for i in te: t = TPd[(b, i)]; tp += t[0]; nf += t[1]; na += t[2]
    R[f'oof_{fam}'] = dict(params=ch_, F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na); print(fam, R[f'oof_{fam}'])
rec('clk3', R)
