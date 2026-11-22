"""Check of the 14 extra D0 marks (NIFTY, cycles before 16 Sep): offset from the earlier 15-minute marks D0 sells at, strike = ATM of the previous minute's close, lots per pair, seconds after the mark.
Outputs bl_d0r_extra10.csv, bl_summary_d0r5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); K = pd.read_csv(f'{OUT}/bl_d0q_pairs.csv'); nif = [i for i in range(len(CY)) if CY.iloc[i].und == 'NIFTY' and CY.iloc[i].version == 'V1']
sec = lambda s: int(s[:2]) * 3600 + int(s[3:]) * 60
extra = ['10:25', '10:55', '11:10', '11:55', '12:05', '12:25', '12:35', '12:55', '13:05', '13:25', '13:35', '13:55', '12:45', '13:00']
m15 = ['09:30', '09:45', '10:00', '10:15', '10:30', '10:45', '11:00', '11:15', '11:30', '11:45', '12:00', '12:15', '12:30', '12:45', '13:00', '13:15', '13:30', '13:45', '14:00', '14:15', '14:30']; sold15 = {sec(x) for x in m15 if x not in ('12:15',)}
rows = []; off = []
for m in extra:
    b = sec(m); z = K[K.cid.isin(nif) & (K.tod >= b - 3) & (K.tod <= b + 130)]; off += list(z.tod - b); earlier = max(x for x in [sec(y) for y in m15] if x < b)
    rows.append(dict(mark=m, minutes_after_earlier_15min_mark=(b - earlier) // 60, earlier_mark=f'{earlier // 3600:02d}:{earlier % 3600 // 60:02d}', ten_after_a_15min_mark=(b - 600) in {sec(y) for y in m15}, ten_after_a_SOLD_15min_mark=(b - 600) in sold15, pairs=len(z), strike_is_prev_close_ATM=float(z.hit_prev_close.mean()), lots_per_pair=float(z.lots.mean())))
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/bl_d0r_extra10.csv', index=False); five = T[~T.mark.isin(['12:45', '13:00'])]
allp = pd.concat([K[K.cid.isin(nif) & (K.tod >= sec(m) - 3) & (K.tod <= sec(m) + 130)] for m in extra])
R = dict(extra_5min_marks=len(five), exactly_10_after_a_15min_mark=int(five.ten_after_a_15min_mark.sum()), exactly_10_after_a_sold_15min_mark=int(five.ten_after_a_SOLD_15min_mark.sum()), five_after_a_15min_mark=int((five.minutes_after_earlier_15min_mark == 5).sum()),
         pairs=len(allp), atm_prev_close=float(allp.hit_prev_close.mean()), atm_within_minute=float(allp.hit_any_atm_in_minute.mean()), lots_per_pair=float(allp.lots.mean()), secs_after_mark_q=np.percentile(off, [10, 50, 90]).tolist(), pairs_12_45=int(T[T.mark == '12:45'].pairs.iloc[0]), pairs_13_00=int(T[T.mark == '13:00'].pairs.iloc[0]))
rec('d0r5', R); print(R); print(T.round(2).to_string(index=False))
