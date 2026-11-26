"""Lot-construction step 2: what sets the size of a solo sell decision? Real stand-alone solo bursts (body solo sells, not attached to a reactive entry, before 15:00, same right within 3 s) and their size,
vs market variables at the decision minute: favourable excursion in the minute beyond the previous minute's extreme (steps), spot distance from the previous body sale on that right (steps and 0.2-step rungs), minute range, minutes since the previous sale on that right, depth beyond the 60-min extreme, time of day, cycle unit.
Spearman per variable; size distribution. Outputs bl_solo_burst.csv, bl_summary_sb1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}; rows = []
for i, r in enumerate(CY.itertuples()):
    o = OH[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values; st = ref.STEP[r.und]; d = SD[(SD.cid == i)].sort_values('te')
    react_t = d[d.typ == 'reactive'].te.values
    for cp in ('CE', 'PE'):
        z = d[(d.cp == cp) & ~d.deep].sort_values('te'); sg = -1 if cp == 'CE' else 1                 # favourable direction: CE sold on falls (-1), PE on rises (+1)
        solo = z[(z.typ == 'solo') & (z.te < 54000)]
        if not len(solo): continue
        # bursts
        b = (solo.te.diff() > 3).cumsum(); 
        for _, g in solo.groupby(b):
            t0 = g.te.iloc[0]; j = int(g.j.iloc[0]); j = min(max(j, 61), 374)
            if (np.abs(react_t - t0) <= 5).any(): continue                                                 # attached to a reactive entry: excluded
            prev = z[z.te < t0 - 3]; jp = int(prev.j.iloc[-1]) if len(prev) else None
            ref_sp = c[max(jp - 1, 0)] if jp is not None else c[j - 1]
            exc = sg * ((h[j] - h[j - 1]) if sg > 0 else (l[j] - l[j - 1])) / st                         # favourable excursion beyond the previous minute's extreme
            dist = sg * ((h[j] if sg > 0 else l[j]) - ref_sp) / st
            dep60 = sg * ((h[j] - h[j - 60:j].max()) if sg > 0 else (l[j] - l[j - 60:j].min())) / st
            rows.append(dict(cid=i, und=r.und, cp=cp, t=t0, size=int(g.lots.sum()), n_orders=len(g), span_s=g.te.iloc[-1] - t0, excursion=exc, dist_prev_sale=dist, rungs=np.floor(dist / 0.2) if dist > 0 else 0, mrange=(h[j] - l[j]) / st,
                             mins_since_prev=(t0 - prev.te.iloc[-1]) / 60 if len(prev) else np.nan, depth60=dep60, hour=t0 / 3600, unit=r.unit))
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_solo_burst.csv', index=False)
print('stand-alone solo decisions', len(X), 'lots', int(X['size'].sum()), 'size distribution', X['size'].value_counts().sort_index().to_dict())
for v in ('excursion', 'dist_prev_sale', 'rungs', 'mrange', 'mins_since_prev', 'depth60', 'hour'):
    rr = spearmanr(X['size'], X[v], nan_policy='omit'); R[v] = [float(rr[0]), float(rr[1])]; print(f'{v:16s} rho {rr[0]:+.3f} p {rr[1]:.4f}')
print(X.groupby(pd.cut(X.depth60, [-9, 0, 0.1, 0.2, 0.4, 0.7, 1, 9])).size_.mean() if False else X.groupby(pd.cut(X.depth60, [-9, 0, 0.1, 0.2, 0.4, 0.7, 1, 9]), observed=True)['size'].agg(['mean', 'size']).round(2).to_string())
print(X.groupby(pd.cut(X.mrange, [0, .2, .4, .6, 1, 9]), observed=True)['size'].agg(['mean', 'size']).round(2).to_string()); rec('sb1', R)
