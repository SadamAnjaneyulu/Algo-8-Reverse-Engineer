"""Solo decode step 7 (post-hoc): spot ladder from the previous sale on that right. Reference = spot (previous close) at the last body sale on the right (any type; own simulated solo sales update it). Fire 1 lot of CE when the minute's low < reference - X points (PE: high > reference + X); the new reference = that trigger level. Optional gate: fresh favourable 60-min extreme. X in strike steps. Scored on solo decisions (bursts) and lots, +-1 min; X chosen on the other cycle half.
Outputs bl_sd_spotladder.csv, bl_summary_sd6.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
_src = open('bl_sd_ladder.py').read(); exec(_src.split("def ladder(")[0]); exec("def score(" + _src.split("def score(")[1].split("CF = [")[0])
def sl(i, X, gate, scope='any'):
    r = CY.iloc[i]; o = OH[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values; st = ref.STEP[r.und] * X; out = {'CE': np.zeros(377, int), 'PE': np.zeros(377, int)}
    ex = D[(D.cid == i) & ~D.deep & ((D.typ != 'solo') if scope == 'any' else (D.typ == 'none'))].sort_values('te')
    for cp in ('CE', 'PE'):
        ev = list(ex[ex.cp == cp].itertuples()); ptr = 0; refp = None
        for j in range(1, 375):
            T0 = 33300 + 60 * j
            while ptr < len(ev) and ev[ptr].te < T0: refp = c[max(int((ev[ptr].te - 33300) // 60) - 1, 0)]; ptr += 1
            if refp is None: continue
            if gate and not ((l[j] < l[max(j - gate, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - gate, 0):j].max())): continue
            if cp == 'CE' and l[j] < refp - st: out[cp][j] += 1; refp = refp - st * max(1, int((refp - l[j]) // st))
            elif cp == 'PE' and h[j] > refp + st: out[cp][j] += 1; refp = refp + st * max(1, int((h[j] - refp) // st))
    return out
CF = [(X, g) for X in (0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0) for g in (0, 15, 60)]
MEMO = {(cfg, i): sl(i, *cfg) for cfg in CF for i in range(len(CY))}; ids = list(range(len(CY))); rows = []
for unit in ('burst', 'lot'):
    for cfg in CF: f, p, r_, nf = score(cfg, ids, unit); rows.append(dict(unit=unit, X_steps=cfg[0], fresh_extreme_gate=cfg[1], F1=f, precision=p, recall=r_, fires=nf))
    tp = nf = na = 0; ch_ = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; b = max(CF, key=lambda c: score(c, tr, unit)[0]); ch_.append(b)
        for i in te:
            for cp in ('CE', 'PE'): a = AB[(i, cp)] if unit == 'burst' else AL[(i, cp)]; m = MEMO[(b, i)][cp]; tp += fmatch(a, m); nf += int(m.sum()); na += int(a.sum())
    R[f'oof_{unit}'] = dict(chosen=[list(map(str, c)) for c in ch_], F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na)
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_sd_spotladder.csv', index=False); print(T.sort_values('F1', ascending=False).groupby('unit').head(5).round(3).to_string(index=False)); print(R); rec('sd6', R)
