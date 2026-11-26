"""Trigger study part 1 (D-1): pairing structure and clock structure of body short sales.
paired = a sale on the OTHER right at the SAME strike within 3 s (a straddle leg pair); single = no such partner.
Outputs outputs/bl_trig_pairing.csv, bl_trig_timing.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = load_orders(); S = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)].copy().reset_index(drop=True); S['paired'] = False
for (u, e, k), g in S.groupby(['und', 'expiry', 'strike']):
    ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']
    if not len(ce) or not len(pe): continue
    pt = np.sort(pe.tt_first.values); ct = np.sort(ce.tt_first.values)
    for i in ce.index: t = S.at[i, 'tt_first']; j = np.searchsorted(pt, t - 3); S.at[i, 'paired'] = j < len(pt) and pt[j] <= t + 3
    for i in pe.index: t = S.at[i, 'tt_first']; j = np.searchsorted(ct, t - 3); S.at[i, 'paired'] = j < len(ct) and ct[j] <= t + 3
S['mo'] = ((S.tod - (9 * 3600 + 16 * 60)) // 60) % 15; S['sec'] = S.tod % 60
t = S.groupby(['cls', 'paired']).lots.sum().unstack(fill_value=0); t['single_share_lots'] = (t[False] / (t[False] + t[True])).round(3); t.to_csv(f'{OUT}/bl_trig_pairing.csv'); print('lots by class x paired (False = single leg):'); print(t.to_string())
print('single-leg share of all D-1 sold lots: %.3f ; by right: %s' % (S[~S.paired].lots.sum() / S.lots.sum(), (S[~S.paired].groupby('cp').lots.sum() / S.groupby('cp').lots.sum()).round(3).to_dict()))
# minute offset from the slot clock, single vs paired
print('minute-of-15 (0 = slot minute) share of ORDERS:'); mt = pd.DataFrame({'single': S[~S.paired].mo.value_counts(normalize=True).sort_index(), 'paired': S[S.paired].mo.value_counts(normalize=True).sort_index()}).round(3); mt.to_csv(f'{OUT}/bl_trig_timing.csv'); print(mt.T.to_string())
# Rayleigh concentration of the sale times over candidate periods (seconds), single-leg sales NOT in slot minute / minute-before
def ray(x, P): z = np.exp(2j * np.pi * (x % P) / P); return abs(z.mean())
g = S[(~S.paired)]; print('Rayleigh R of single-leg sale times (n=%d) by period: ' % len(g) + ', '.join('%ds %.3f' % (P, ray(g.tod.values, P)) for P in (30, 60, 120, 300, 600, 900)) + '  | paired (n=%d): ' % int(S.paired.sum()) + ', '.join('%ds %.3f' % (P, ray(S[S.paired].tod.values, P)) for P in (30, 60, 120, 300, 600, 900)))
print('second-of-minute of single-leg sales (10 s bins):', pd.cut(g.sec, range(0, 61, 10), right=False).value_counts(normalize=True).sort_index().round(3).to_dict())
# time since previous sale on the same right
S = S.sort_values(['und', 'expiry', 'cp', 'te', 'row']); S['gap_prev'] = S.groupby(['und', 'expiry', 'cp']).tt_first.diff()
print('gap to previous sale on same right (s) quantiles, single / paired:', S[~S.paired].gap_prev.quantile([.1, .25, .5, .75, .9]).round(0).tolist(), S[S.paired].gap_prev.quantile([.1, .25, .5, .75, .9]).round(0).tolist())
S.to_pickle(f'{OUT}/bl_trig_sells_d1.pkl.gz')
