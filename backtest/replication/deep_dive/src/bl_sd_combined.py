"""Solo decode step 9: combined model of the reactive + solo streams, parameters fitted on the other cycle half.
Reactive fires = decoded machine (true OHLC, previous two clock candles, first break per side per candle, 10:30-15:15). Size: pairs = 1 + floor(depth / theta_p) (cap 3); attached favourable-side extras = round(a + b * depth) (0-7), depth = break beyond the channel in strike steps within the fire minute (uses the minute's full high/low: mild look-ahead, labelled). Stand-alone solo = spot ladder (X steps beyond the previous sale on that right, gate fresh 60-min extreme).
Scores lots (+-1 min, same right): reactive lots, solo lots, all D-1 sold lots with the scheduled timetable. Outputs bl_sd_combined.csv, bl_summary_sd8.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
OH = bl_ohlc.load(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); W = pd.read_csv(f'{OUT}/bl_react_wave_clock.csv'); F = pd.read_csv(f'{OUT}/bl_sd_reactlots.csv'); R = {}
_s = open('bl_sd_spotladder.py').read(); exec("def sl(" + _s.split("def sl(")[1].split("CF = [")[0])
def fmatch(a, p):
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); tp = int(m.sum()); a -= m; p -= m
    for k in range(len(a)):
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(a) and p[k] > 0 and a[kk] > 0: x = min(p[k], a[kk]); tp += x; p[k] -= x; a[kk] -= x
    return tp
def react_fires(i):
    r = CY.iloc[i]; o = OH[(r.und, r.expiry)]; h, l = o.high.values, o.low.values; step = ref.STEP[r.und]; out = []; done = set()
    for j in range(75, 361):
        clock = 33300 + 60 * j; b0 = (clock // 1800) * 1800; a = int(np.ceil((b0 - 3600 - 33300) / 60)); e = int(np.ceil((b0 - 33300) / 60))
        if e - max(a, 0) < 2: continue
        H, L = h[max(a, 0):e].max(), l[max(a, 0):e].min()
        for s, fl, dep in ((1, h[j] > H, (h[j] - H) / step), (-1, l[j] < L, (L - l[j]) / step)):
            if fl and (b0, s) not in done: out.append((j, s, dep)); done.add((b0, s))
    return out
RF = {i: react_fires(i) for i in range(len(CY))}; LAD = {i: sl(i, 0.2, 60) for i in range(len(CY))}
ACT = {}
for i in range(len(CY)):
    z = D[(D.cid == i) & ~D.deep]
    for t in ('scheduled', 'reactive', 'solo'):
        for cp in ('CE', 'PE'): ACT[(i, t, cp)] = np.bincount(z[(z.typ == t) & (z.cp == cp)].j.clip(0, 375).values.astype(int), weights=z[(z.typ == t) & (z.cp == cp)].lots.values, minlength=377).astype(int)
def predict(i, tp_, a, b, use_size=True, use_extra=True, use_ladder=True):
    pr = {(t, cp): np.zeros(377, int) for t in ('scheduled', 'reactive', 'solo') for cp in ('CE', 'PE')}; r = CY.iloc[i]
    for w in W[W.version == r.version].itertuples():
        j = int((33360 + w.sec_after_0916 - 33300) // 60)
        for cp in ('CE', 'PE'): pr[('scheduled', cp)][j] += 1
    for j, s, dep in RF[i]:
        n = min(1 + int(dep // tp_), 3) if use_size else 1
        for cp in ('CE', 'PE'): pr[('reactive', cp)][j] += n
        if use_extra: pr[('solo', 'PE' if s > 0 else 'CE')][j] += int(np.clip(round(a + b * dep), 0, 7))
    if use_ladder:
        for cp in ('CE', 'PE'): pr[('solo', cp)] += LAD[i][cp]
    return pr
def fit_extra(cids):
    f = F[F.cid.isin(cids)]; b, a = np.polyfit(f.depth.clip(-0.5, 3), f.extra_fav, 1); return a, b
def evaluate(cids, cfg):
    res = {k: [0, 0, 0] for k in ('reactive', 'solo', 'all')}
    for i in cids:
        pr = predict(i, *cfg)
        for cp in ('CE', 'PE'):
            for t in ('reactive', 'solo'): a_ = ACT[(i, t, cp)]; p_ = pr[(t, cp)]; res[t][0] += fmatch(a_, p_); res[t][1] += int(p_.sum()); res[t][2] += int(a_.sum())
            a_ = sum(ACT[(i, t, cp)] for t in ('scheduled', 'reactive', 'solo')); p_ = sum(pr[(t, cp)] for t in ('scheduled', 'reactive', 'solo')); res['all'][0] += fmatch(a_, p_); res['all'][1] += int(p_.sum()); res['all'][2] += int(a_.sum())
    return {k: dict(precision=v[0] / max(v[1], 1), recall=v[0] / max(v[2], 1), F1=2 * v[0] / max(v[1] + v[2], 1), model=v[1], real=v[2]) for k, v in res.items()}
ids = list(range(len(CY))); rows = []
for nm, flags in (('pairs only, 1 per fire; no solo', (False, False, False)), ('+ pairs sized by break depth', (True, False, False)), ('+ attached favourable extras by depth', (True, True, False)), ('+ stand-alone solo ladder (fresh 60-min extreme, 0.2-step ladder)', (True, True, True)), ('stand-alone solo ladder only (no attached extras)', (True, False, True))):
    agg = {k: [0, 0, 0] for k in ('reactive', 'solo', 'all')}; chosen = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; a, b = fit_extra(tr)
        tp_best = max((0.25, 0.4, 0.5, 0.75, 1.0, 1.5), key=lambda tp_: evaluate(tr, (tp_, a, b) + flags)['reactive']['F1']) if flags[0] else 1.0; chosen.append((tp_best, round(a, 2), round(b, 2)))
        ev = evaluate(te, (tp_best, a, b) + flags)
        for k in agg: agg[k][0] += ev[k]['recall'] * ev[k]['real']; agg[k][1] += ev[k]['model']; agg[k][2] += ev[k]['real']
    for k, (tp, nf, na) in agg.items(): rows.append(dict(model=nm, stream=k, real_lots=na, model_lots=nf, precision=tp / max(nf, 1), recall=tp / max(na, 1), F1=2 * tp / max(nf + na, 1), params=str(chosen)))
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_sd_combined.csv', index=False); print(T.drop(columns='params').round(3).to_string(index=False)); print(T.params.unique()); R['rows'] = T.round(4).to_dict('records'); rec('sd8', R)
