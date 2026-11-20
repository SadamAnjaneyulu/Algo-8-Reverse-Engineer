"""Figure for the sizing study -> reports/figures/bl_size_logic.png"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); os.makedirs(FIG, exist_ok=True)
Cc = pd.read_csv(f'{OUT}/bl_size_cells.csv'); BU = pd.read_csv(f'{OUT}/bl_size_buildup.csv'); H = pd.read_csv(f'{OUT}/bl_size_solo_hour.csv', index_col=0); ND = pd.read_csv(f'{OUT}/bl_size_notional_dates.csv'); ST = pd.read_csv(f'{OUT}/bl_size_state.csv')
fig, ax = plt.subplots(2, 2, figsize=(13.5, 9.5))
a = ax[0, 0]; w = .4
for i, (v, col) in enumerate((('V1', '#1f77b4'), ('V2', '#d62728'))):
    t = Cc[Cc.version == v].groupby('k').ce_mode.sum().reindex(range(22), fill_value=0); a.bar(np.arange(22) + (i - .5) * w, t.values, w, color=col, label=f'{v} (pairs of 1 CE + 1 PE lot per block)')
a.set_xticks(range(22)); a.set_xticklabels([f'{9 + (16 + 15 * k) // 60}:{(16 + 15 * k) % 60:02d}' for k in range(22)], rotation=70, fontsize=7); a.set_ylabel('scheduled pairs in the 15-min block'); a.set_title('A. Not 1 lot per 15 min: a fixed timetable of 1-lot pairs (0-4 per block)'); a.legend(fontsize=8)
a = ax[0, 1]; g = BU.groupby('clock_hour')[['sold', 'sold_scheduled', 'bought_back', 'net_short_body']]; med = g.median(); q1 = g.quantile(.25); q3 = g.quantile(.75); x = med.index.values
for c, col, nm in (('sold', '#7f7f7f', 'cumulative sold'), ('sold_scheduled', '#2ca02c', 'of which timetable'), ('net_short_body', '#d62728', 'net short (sold - bought back)')): a.plot(x, med[c], 'o-', color=col, label=nm); a.fill_between(x, q1[c], q3[c], color=col, alpha=.15)
a.set_xticks(x); a.set_xticklabels(['10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '15:30'], fontsize=8); a.set_ylabel('body lots (both rights), median and IQR over cycles'); a.set_title('B. Build-up through D-1'); a.legend(fontsize=8)
a = ax[1, 0]; cols = {'scheduled cell': '#2ca02c', 'reactive pair (outside timetable)': '#ff7f0e', 'solo': '#9467bd'}; bot = np.zeros(len(H))
for c in ('scheduled cell', 'reactive pair (outside timetable)', 'solo'): a.bar(H.index.astype(int), H[c], bottom=bot, color=cols[c], label=c.replace(' (outside timetable)', '')); bot += H[c].values
a.set_xlabel('clock hour (IST)'); a.set_ylabel('mean D-1 sold lots per cycle'); a.set_title('C. Where the lots come from: timetable, reactive pairs, solo sells'); a.legend(fontsize=8)
a = ax[1, 1]; ND['d'] = pd.to_datetime(ND.d1)
for v, col in (('V1', '#1f77b4'), ('V2', '#d62728')):
    for u, mk in (('NIFTY', 'o'), ('SENSEX', 's')): z = ND[(ND.version == v) & (ND.und == u)]; a.scatter(z.d, z.notional_lakh, color=col, marker=mk, label=f'{u} {v}')
a.axvspan(pd.Timestamp('2026-09-09'), pd.Timestamp('2026-09-16'), color='k', alpha=.12); a.axhline(15, color='k', ls=':', lw=1); a.text(pd.Timestamp('2026-06-25'), 15.03, '₹15 lakh', fontsize=8); a.set_ylabel('unit × spot at D-1 open (₹ lakh per lot)'); a.set_title('D. Lot unit unchanged; the schedule edit falls in the shaded window'); a.legend(fontsize=7, ncol=2); plt.setp(a.get_xticklabels(), rotation=30, fontsize=8)
fig.suptitle('Algo 8 body sizing on D-1 — in-sample, 32 cycles with a D-1 log', fontsize=11); fig.tight_layout(); fig.savefig(f'{FIG}/bl_size_logic.png', dpi=140); print('saved')
