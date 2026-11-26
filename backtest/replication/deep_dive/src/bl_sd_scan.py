"""Solo decode step 2: solo decisions (bursts = regular solo lots on the same right within 3 s) vs breakout machines on true one-minute OHLC.
Machines (favourable side only: CE on a downside break, PE on an upside break): (a) clock-aligned candles of L minutes, channel = previous K completed candles, first intrabar break per side per candle; (b) same but every new extreme of the running candle beyond the channel (ladder); (c) rolling N-minute fresh extreme (intrabar) every minute.
Scored at the decision level (bursts) and lot level (1 lot per fire), +-1 minute. Outputs bl_sd_scan.csv, bl_sd_bursts.pkl.gz, bl_summary_sd1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
OH = bl_ohlc.load(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); R = {}
S = D[(D.typ == 'solo') & ~D.deep].sort_values(['cid', 'cp', 'te']).copy(); S['burst'] = (S.groupby(['cid', 'cp']).te.diff().fillna(999) > 3).cumsum()
B = S.groupby('burst').agg(cid=('cid', 'first'), cp=('cp', 'first'), te=('te', 'first'), j=('j', 'first'), lots=('lots', 'sum'), strike=('strike', 'first')).reset_index(drop=True); B.to_pickle(f'{OUT}/bl_sd_bursts.pkl.gz')
print('solo lots', int(S.lots.sum()), 'bursts', len(B), 'lots per burst', B.lots.value_counts().sort_index().head(8).to_dict()); R['bursts'] = len(B); R['lots_per_burst'] = {int(k): int(v) for k, v in B.lots.value_counts().sort_index().items()}
AB = {}; AL = {}
for i in range(len(CY)):
    for cp in ('CE', 'PE'):
        b = B[(B.cid == i) & (B.cp == cp)]; AB[(i, cp)] = np.bincount(b.j.clip(0, 375).values.astype(int), minlength=377); l = S[(S.cid == i) & (S.cp == cp)]; AL[(i, cp)] = np.bincount(l.j.clip(0, 375).values.astype(int), minlength=377)
def fmatch(a, p):
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); tp = int(m.sum()); a -= m; p -= m
    for k in range(len(a)):
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(a) and p[k] > 0 and a[kk] > 0: x = min(p[k], a[kk]); tp += x; p[k] -= x; a[kk] -= x
    return tp
def machine(i, kind, L=30, K=2, N=15, j0=1, j1=374):
    r = CY.iloc[i]; o = OH[(r.und, r.expiry)]; h, l = o.high.values, o.low.values; out = {'CE': np.zeros(377, int), 'PE': np.zeros(377, int)}; done = set(); ext = {}
    for j in range(j0, j1 + 1):
        if kind == 'roll':
            if j - N < 0: continue
            if l[j] < l[j - N:j].min(): out['CE'][j] += 1
            if h[j] > h[j - N:j].max(): out['PE'][j] += 1
            continue
        clock = 33300 + 60 * j; b0 = (clock // (L * 60)) * L * 60; a = int(np.ceil((b0 - K * L * 60 - 33300) / 60)); e = int(np.ceil((b0 - 33300) / 60))
        if a < 0 or e - a < 2: continue
        H, Lo = h[a:e].max(), l[a:e].min(); bs = max(e, 0)
        for cp, brk, lvl in (('PE', h[j] > H, None), ('CE', l[j] < Lo, None)):
            if not brk: continue
            key = (b0, cp)
            if kind == 'first':
                if key in done: continue
                out[cp][j] += 1; done.add(key)
            elif kind == 'ladder':
                prev = ext.get(key)
                cur = h[j] if cp == 'PE' else l[j]
                if prev is None or (cur > prev if cp == 'PE' else cur < prev): out[cp][j] += 1; ext[key] = cur
    return out
def score(kind, unit, **kw):
    tp = nf = na = 0
    for i in range(len(CY)):
        m = machine(i, kind, **kw)
        for cp in ('CE', 'PE'):
            a = AB[(i, cp)] if unit == 'burst' else AL[(i, cp)]; tp += fmatch(a, m[cp]); nf += int(m[cp].sum()); na += int(a.sum())
    return dict(F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na, fires=nf, targets=na)
rows = []
for L in (5, 10, 15, 30, 60):
    for K in (1, 2, 3):
        for kind in ('first', 'ladder'):
            for unit in ('burst', 'lot'): rows.append(dict(kind=kind, L=L, K=K, N=np.nan, unit=unit, **score(kind, unit, L=L, K=K)))
for N in (5, 10, 15, 20, 30, 45, 60, 90):
    for unit in ('burst', 'lot'): rows.append(dict(kind='roll', L=np.nan, K=np.nan, N=N, unit=unit, **score('roll', unit, N=N)))
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_sd_scan.csv', index=False)
print(T[T.unit == 'burst'].sort_values('F1', ascending=False).head(12).round(3).to_string(index=False)); print(T[T.unit == 'lot'].sort_values('F1', ascending=False).head(6).round(3).to_string(index=False))
R['best_burst'] = T[T.unit == 'burst'].sort_values('F1', ascending=False).head(5).round(4).to_dict('records'); rec('sd1', R)
