"""Reactive-pair study: exact clock times of the timetable waves per version (answers 'how many waves at what time').
For every timetable cell, the observed pairs of each cycle in the cell window (+-3 s) are sorted by time and ranked; the wave time = median over cycles of the rank-i pair time. Outputs outputs/bl_react_wave_clock.csv, bl_react_wave_hour.csv"""
import sys; sys.path.insert(0, '.')
import pandas as pd, numpy as np
from bl_common import OUT
C = pd.read_csv(f'{OUT}/bl_size_cells.csv'); Pr = pd.read_csv(f'{OUT}/bl_size_pairs.csv'); Pr = Pr[Pr.day == 'D-1'].merge(pd.read_csv(f'{OUT}/bl_size_cycles.csv')[['und', 'expiry', 'version']], on=['und', 'expiry']); rows = []
def clock(sec): t = 9 * 3600 + 16 * 60 + int(round(sec)); return f'{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}'
for c in C.itertuples():
    z = Pr[(Pr.version == c.version) & (Pr.k == c.k) & (Pr.off >= c.lo - 3) & (Pr.off <= c.hi + 3)].sort_values('te'); z['rank'] = z.groupby(['und', 'expiry']).cumcount()
    for i in range(int(c.ce_mode)):
        w = z[z['rank'] == i]; off = float(w.off.median()) if len(w) else (c.lo + c.hi) / 2; rows.append((c.version, int(c.k), 900 * c.k + off, clock(900 * c.k + off), round(off), c.fire_ce, len(w)))
W = pd.DataFrame(rows, columns=['version', 'block', 'sec_after_0916', 'clock_time', 'offset_in_block_s', 'cell_fire_rate', 'cycles_with_this_wave']).sort_values(['version', 'sec_after_0916']); W['wave_no'] = W.groupby('version').cumcount() + 1; W.to_csv(f'{OUT}/bl_react_wave_clock.csv', index=False)
W['hour'] = W.clock_time.str[:2].astype(int); H = W.groupby(['version', 'hour']).size().unstack(0, fill_value=0); H.to_csv(f'{OUT}/bl_react_wave_hour.csv'); print(H.to_string()); print(W.groupby('version').size().to_dict()); print(W[W.version == 'V1'].clock_time.tolist())
