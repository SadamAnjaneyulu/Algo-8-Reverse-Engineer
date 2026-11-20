"""Reactive-pair study: exact clock times of the timetable waves per version (answers 'how many waves at what time') -> outputs/bl_react_wave_clock.csv, bl_react_wave_hour.csv"""
import sys; sys.path.insert(0, '.')
import pandas as pd, numpy as np
from bl_common import OUT
C = pd.read_csv(f'{OUT}/bl_size_cells.csv'); rows = []
def clock(sec): t = 9 * 3600 + 16 * 60 + int(round(sec)); return f'{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}'
for r in C.itertuples():
    for i in range(int(r.ce_mode)): rows.append((r.version, int(r.k), 900 * r.k + (r.lo + r.hi) / 2, clock(900 * r.k + (r.lo + r.hi) / 2), int(r.lo), int(r.hi), r.fire_ce))
W = pd.DataFrame(rows, columns=['version', 'block', 'sec_after_0916', 'clock_time', 'offset_lo', 'offset_hi', 'fire_rate']).sort_values(['version', 'sec_after_0916']); W['wave_no'] = W.groupby('version').cumcount() + 1; W['cum_pairs'] = W.wave_no; W.to_csv(f'{OUT}/bl_react_wave_clock.csv', index=False)
W['hour'] = W.clock_time.str[:2].astype(int); H = W.groupby(['version', 'hour']).size().unstack(0, fill_value=0); H.to_csv(f'{OUT}/bl_react_wave_hour.csv'); print(H.to_string()); print(W.groupby('version').size().to_dict())
