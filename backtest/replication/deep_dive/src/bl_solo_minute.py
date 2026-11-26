"""Lot-construction step 4: real solo lots per minute (stand-alone, intraday, not within 5 s of a reactive entry) vs the favourable depth beyond the 60-min extreme in that minute (true OHLC, steps), and the same for late solo minutes (after 15:00) vs the 15-min depth.
Linear fits by cycle half (for the simulator sizing). Outputs bl_solo_minute.csv, bl_summary_sm1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}; rows = []
for i, r in enumerate(CY.itertuples()):
    o = OH[(r.und, r.expiry)]; h, l = o.high.values, o.low.values; st = ref.STEP[r.und]; d = SD[SD.cid == i]; rt = d[d.typ == 'reactive'].te.values
    s = d[(d.typ == 'solo') & ~d.deep].copy(); s['att'] = [bool((np.abs(rt - t) <= 5).any()) for t in s.te]; s = s[~s.att]
    for (cp, j), g in s.groupby(['cp', 'j']):
        j = int(j)
        if j < 61 or j > 374: continue
        sg = -1 if cp == 'CE' else 1
        d60 = sg * ((h[j] - h[j - 60:j].max()) if sg > 0 else (l[j] - l[j - 60:j].min())) / st; d15 = sg * ((h[j] - h[j - 15:j].max()) if sg > 0 else (l[j] - l[j - 15:j].min())) / st
        rows.append(dict(cid=i, cp=cp, j=j, late=int(j >= 345), lots=int(g.lots.sum()), depth60=d60, depth15=d15))
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_solo_minute.csv', index=False)
for lab, g, dv in (('intraday', X[X.late == 0], 'depth60'), ('after 15:00', X[X.late == 1], 'depth15')):
    rr = spearmanr(g.lots, g[dv]); print(lab, 'minutes', len(g), 'lots', int(g.lots.sum()), 'mean lots/minute', round(g.lots.mean(), 2), f'rho vs {dv}', round(rr[0], 3), 'p', round(rr[1], 4))
    print('   mean lots by depth:', g.groupby(pd.cut(g[dv], [-9, 0, 0.1, 0.2, 0.4, 0.7, 1, 9]), observed=True).lots.agg(['mean', 'size']).round(2).to_dict('index'))
    for h_ in (0, 1):
        t = g[g.cid % 2 == h_]; b, a = np.polyfit(t[dv].clip(-0.5, 2), t.lots, 1); R[f'{lab}|half{h_}'] = dict(a=float(a), b=float(b)); print('   fit half', h_, 'lots = %.2f + %.2f x depth' % (a, b))
rec('sm1', R)
