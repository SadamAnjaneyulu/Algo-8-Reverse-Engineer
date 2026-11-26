"""Solo decode step 5 (post-hoc): premium-ladder machine. Per right, reference = the last body sale on that right (any type, from the real order stream up to now = teacher-forced exogenous scheduled/reactive sales; own simulated solo sales update it too). Each minute: if the reference contract's minute LOW (CE/PE price) <= ref_price x (1 - delta) -> sell 1 lot of that right at the strike whose previous-minute close is nearest ref_price; the new sale becomes the reference. Optional gates: own-right book ratio <= a (book in profit), fresh favourable extreme. Scored on solo decisions (bursts) and lots, +-1 min; delta chosen on the other cycle half.
Outputs bl_sd_ladder.csv, bl_summary_sd4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc, bl_sd_build
OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); B = pd.read_pickle(f'{OUT}/bl_sd_bursts.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); R = {}
exec(open('bl_sd_scan.py').read().split("def machine(")[0].split("OH = bl_ohlc.load()")[1].split("S = D[")[0]) if False else None
S = D[(D.typ == 'solo') & ~D.deep]; AB = {}; AL = {}
for i in range(len(CY)):
    for cp in ('CE', 'PE'):
        b = B[(B.cid == i) & (B.cp == cp)]; AB[(i, cp)] = np.bincount(b.j.clip(0, 375).values.astype(int), minlength=377); l = S[(S.cid == i) & (S.cp == cp)]; AL[(i, cp)] = np.bincount(l.j.clip(0, 375).values.astype(int), minlength=377)
def fmatch(a, p):
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); tp = int(m.sum()); a -= m; p -= m
    for k in range(len(a)):
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(a) and p[k] > 0 and a[kk] > 0: x = min(p[k], a[kk]); tp += x; p[k] -= x; a[kk] -= x
    return tp
def ladder(i, delta, src='any', gate_ext=0, maxper=1, j1=374):
    r = CY.iloc[i]; op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; o = OH[(r.und, r.expiry)]; h, l = o.high.values, o.low.values
    ex = D[(D.cid == i) & ~D.deep & ((D.typ != 'solo') if src == 'any' else (D.typ == 'none'))].sort_values('te')       # exogenous sales that reset the reference
    out = {'CE': np.zeros(377, int), 'PE': np.zeros(377, int)}
    for cp in ('CE', 'PE'):
        exc = ex[ex.cp == cp]; ref_k = None; ref_p = None; ptr = 0; ev = list(exc.itertuples())
        for j in range(1, j1 + 1):
            T0 = 33300 + 60 * j
            while ptr < len(ev) and ev[ptr].te < T0: ref_k = ev[ptr].strike; ref_p = ev[ptr].px; ptr += 1
            if ref_k is None or ref_k not in ki: continue
            lowp = op[(cp, 'low')][ki[ref_k], j]
            if not (lowp == lowp): continue
            if gate_ext and not ((l[j] < l[max(j - gate_ext, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - gate_ext, 0):j].max())): continue
            n = 0
            while lowp <= ref_p * (1 - delta) and n < maxper:
                out[cp][j] += 1; n += 1
                pc = op[(cp, 'close')][:, j]; ok = ~np.isnan(pc); nk = int(K[ok][np.argmin(np.abs(pc[ok] - ref_p))]); ref_k = nk; lowp = op[(cp, 'low')][ki[nk], j]
                if not (lowp == lowp): break
    return out
def score(cfg, cids, unit):
    tp = nf = na = 0
    for i in cids:
        m = MEMO[(cfg, i)]
        for cp in ('CE', 'PE'): a = AB[(i, cp)] if unit == 'burst' else AL[(i, cp)]; tp += fmatch(a, m[cp]); nf += int(m[cp].sum()); na += int(a.sum())
    return 2 * tp / max(nf + na, 1), tp / max(nf, 1), tp / max(na, 1), nf
CF = [(dl, src, g, mp) for dl in (0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.2) for src in ('any', 'solo_only') for g in (0, 15, 60) for mp in (1, 3)]
MEMO = {(cfg, i): ladder(i, *cfg) for cfg in CF for i in range(len(CY))}
ids = list(range(len(CY))); rows = []
for unit in ('burst', 'lot'):
    for cfg in CF: f, p, r_, nf = score(cfg, ids, unit); rows.append(dict(unit=unit, delta=cfg[0], reset_by=cfg[1], fresh_extreme_gate=cfg[2], max_lots_per_minute=cfg[3], F1=f, precision=p, recall=r_, fires=nf))
    tp = nf = na = 0; ch_ = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; b = max(CF, key=lambda c: score(c, tr, unit)[0]); ch_.append(b)
        for i in te:
            for cp in ('CE', 'PE'): a = AB[(i, cp)] if unit == 'burst' else AL[(i, cp)]; m = MEMO[(b, i)][cp]; tp += fmatch(a, m); nf += int(m.sum()); na += int(a.sum())
    R[f'oof_{unit}'] = dict(chosen=[list(map(str, c)) for c in ch_], F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na)
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_sd_ladder.csv', index=False); print(T.sort_values('F1', ascending=False).groupby('unit').head(6).round(3).to_string(index=False)); print(R); rec('sd4', R)
