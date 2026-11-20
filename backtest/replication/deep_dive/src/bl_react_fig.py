"""Figure for the reactive-pair study -> reports/figures/bl_react_logic.png"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT, load_orders, ref
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); os.makedirs(FIG, exist_ok=True)
Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); GB = pd.read_csv(f'{OUT}/bl_react_gb.csv'); MH = pd.read_csv(f'{OUT}/bl_react_move_hazard.csv'); So = pd.read_csv(f'{OUT}/bl_size_solo.csv'); So = So[So.day == 'D-1']; O = load_orders(); O1 = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)][['und', 'expiry', 'te', 'cp', 'strike', 'atm_prev']].drop_duplicates(['und', 'expiry', 'te', 'cp', 'strike'])
So = So.merge(O1, on=['und', 'expiry', 'te', 'cp', 'strike'], how='left', suffixes=('', '_o')); n = 32
fig, ax = plt.subplots(2, 2, figsize=(13, 9.2))
a = ax[0, 0]; hh = np.arange(9, 16); r = Pr[Pr.reactive].assign(h=lambda d: (d.tod // 3600).astype(int)).groupby('h').size().reindex(hh, fill_value=0) / n; s = Pr[Pr.sched].assign(h=lambda d: (d.tod // 3600).astype(int)).groupby('h').size().reindex(hh, fill_value=0) / n
a.bar(hh - .2, s.values, .4, color='#2ca02c', label='timetable pairs'); a.bar(hh + .2, r.values, .4, color='#ff7f0e', label='reactive pairs'); a.set_xlabel('clock hour (IST)'); a.set_ylabel('pairs per cycle'); a.set_title('A. Reactive pairs: after 11:00, spread over the hour'); a.legend(fontsize=8)
a = ax[0, 1]; bins = np.arange(-3.5, 4, 1)
def off(df, step_col='und'): return ((df.strike - df.atm_prev) / df[step_col].map(ref.STEP)).dropna()
for df, nm, col in ((Pr[Pr.sched], 'timetable pairs', '#2ca02c'), (Pr[Pr.reactive], 'reactive pairs', '#ff7f0e'), (So, 'solo sells', '#9467bd')):
    o = off(df); a.hist(o.clip(-3, 3), bins=bins, weights=np.ones(len(o)) / len(o) * 100, alpha=.55, color=col, label=nm)
a.set_xlabel('sold strike minus previous-minute ATM (steps)'); a.set_ylabel('% of sells'); a.set_title('B. Reactive pairs are almost never at the ATM: one strike off'); a.legend(fontsize=8)
a = ax[1, 0]; h = MH[MH['var'] == 'a15']; x = np.arange(len(h)); a.bar(x - .2, h.R_per1000, .4, color='#ff7f0e', label='reactive pair'); a.bar(x + .2, h.solo_per1000, .4, color='#9467bd', label='solo sell'); a.set_xticks(x); a.set_xticklabels([b.replace('(', '').replace(']', '').replace(',', ' to ') for b in h.bin]); a.set_xlabel('absolute 15-minute spot move (%)'); a.set_ylabel('events per 1000 cycle-minutes'); a.set_title('C. Moves matter little for pairs (and big moves have none)'); a.legend(fontsize=8)
a = ax[1, 1]; g = GB[GB.target == 'R'].set_index('model').LOCO_AUC; labs = ['clock\nonly', '+ event\nhistory', '+ market\nmoves', '+ book\nP&L', '+ inventory', 'all\nblocks']; vals = [g['clock only'], g['clock + history'], g['clock + market'], g['clock + book'], g['clock + inventory'], g['all blocks']]
a.bar(range(6), vals, color=['#7f7f7f', '#1f77b4', '#d62728', '#8c564b', '#e377c2', '#000000']); a.set_ylim(.55, .85); a.set_xticks(range(6)); a.set_xticklabels(labs, fontsize=8); a.set_ylabel('leave-one-cycle-out AUC (reactive-pair minute)'); a.set_title('D. What predicts a reactive-pair minute')
for i, v in enumerate(vals): a.text(i, v + .004, f'{v:.3f}', ha='center', fontsize=8)
fig.suptitle('Algo 8 D-1 reactive pairs (CE+PE outside the timetable) — in-sample, 32 cycles', fontsize=11); fig.tight_layout(); fig.savefig(f'{FIG}/bl_react_logic.png', dpi=140); print('saved')
