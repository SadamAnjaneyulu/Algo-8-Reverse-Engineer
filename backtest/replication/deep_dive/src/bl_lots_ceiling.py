"""Lot-construction step 6: (a) oracle ceilings of the overall D-1 lot F1 (out-of-fold primary reconstruction): what F1 would be if each error cause were fixed perfectly (from the lot-level error budget);
(b) within-minute structure of real multi-lot sells: are the lots of one minute placed in one burst (same second, a sized decision) or spread over seconds (one lot per new extreme print = per-tick tracker)? Seconds between consecutive orders of the same right inside a minute, by sell type.
Outputs bl_lots_ceiling.csv, bl_lots_intra.csv, bl_summary_lc1.json"""
import sys; sys.path.insert(0, '.')
from bl_common import *
E_ = pd.read_pickle(f'{OUT}/bl_err_lots.pkl.gz'); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}
real = E_[E_.side == 'real']; sim = E_[E_.side == 'sim']; R_ = len(real); TP = int((real.cause == 'matched').sum()); S_ = TP + len(sim)
rc = real.cause.value_counts(); sc = sim.cause.value_counts(); f = lambda tp, s, r: 2 * tp / (s + r)
rows = [dict(scenario='current (out-of-fold, lump at ±1 min)', TP=TP, sim=S_, F1=f(TP, S_, R_))]
tp, s = TP + rc['quantity shortfall'], S_ - sc['quantity excess'] + rc['quantity shortfall']; rows.append(dict(scenario='+ perfect lot count at every event found', TP=tp, sim=s, F1=f(tp, s, R_)))
tp2, s2 = tp + min(rc['timing (2-5 min)'], sc['timing (2-5 min)']), s; rows.append(dict(scenario='+ perfect timing (2–5 min errors corrected)', TP=tp2, sim=s2, F1=f(tp2, s2, R_)))
tp3, s3 = tp2 + rc['missed event'], s2 + rc['missed event'] - sc['spurious event']; rows.append(dict(scenario='+ every event found, no spurious events', TP=tp3, sim=s3, F1=f(tp3, s3, R_)))
tp4, s4 = tp3 + rc['not modelled'], s3 + rc['not modelled']; rows.append(dict(scenario='+ not-modelled classes', TP=tp4, sim=s4, F1=f(tp4, s4, R_)))
C = pd.DataFrame(rows); C['F1'] = C.F1.round(3); C.to_csv(f'{OUT}/bl_lots_ceiling.csv', index=False); print(C.to_string(index=False))
# (b) within-minute spacing of real sells
SD['sub'] = np.where(SD.deep, 'deep', np.where((SD.typ == 'solo') & (SD.te >= 54000), 'late', SD.typ)); rows = []
for (cid, cp, j), g in SD.groupby(['cid', 'cp', 'j']):
    if g.lots.sum() < 2: continue
    t = np.sort(np.repeat(g.te.values, g.lots.values.astype(int))); gaps = np.diff(t)
    rows.append(dict(sub=g['sub'].mode().iloc[0], lots=int(g.lots.sum()), span_s=float(t[-1] - t[0]), share_same_second=float((gaps < 0.5).mean()), median_gap=float(np.median(gaps))))
I = pd.DataFrame(rows); I.to_csv(f'{OUT}/bl_lots_intra.csv', index=False)
T = I.groupby('sub').agg(minutes=('lots', 'size'), lots_mean=('lots', 'mean'), span_s_median=('span_s', 'median'), same_second_share=('share_same_second', 'mean'), median_gap_s=('median_gap', 'median')).round(2); print(T.to_string())
R['ceiling'] = C.to_dict('records'); R['intra'] = T.reset_index().to_dict('records'); rec('lc1', R)
