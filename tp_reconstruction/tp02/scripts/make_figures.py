"""Figures for TP02_REPORT.md from the TP-02 outputs. python3 tp_reconstruction/tp02/scripts/make_figures.py"""
import os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import tp02_common as c
FIG = os.path.join(c.ANALYSIS, 'figures'); os.makedirs(FIG, exist_ok=True); plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
M = pd.read_csv(os.path.join(c.ANALYSIS, 'mechanism_summary.csv')); S = M[M.population == 'short closings (all)'].set_index('item')
# 1 flag rates vs chance
items = ['CLOCK (registered minute)', 'EXPIRY_MGMT (expiry day, 14:30 onward)', 'REPLACEMENT (same right, <= 60 s, registered)', 'WING_LINKED (wing closing same right, +-10 s, registered)', 'BASKET (>= 2 other contracts, +-5 s)']
lab = ['clock', 'expiry mgmt', 'replacement', 'wing-linked', 'basket']; fig, ax = plt.subplots(figsize=(7, 3.4)); x = np.arange(len(items))
ax.bar(x - .2, [S.loc[i, 'share_of_events'] for i in items], .4, label='observed', color='#1f77b4'); ax.bar(x + .2, [S.loc[i, 'chance_rate'] for i in items], .4, label='chance baseline', color='#bbbbbb')
ax.set_xticks(x); ax.set_xticklabels(lab); ax.set_ylabel('share of short closings'); ax.set_title('Registered flags vs their chance baselines (11,716 short closings)'); ax.legend(frameon=False); fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig1_flags_vs_chance.png'), dpi=160); plt.close(fig)
# 2 residue ratios
r = pd.read_csv(os.path.join(c.ANALYSIS, 'h2a_residue_ratios.csv')); fig, ax = plt.subplots(figsize=(7, 3.2)); ax.bar(r.residue_minute_of_15, r.controlled_hazard_ratio, color=['#d62728' if v == r.controlled_hazard_ratio.max() else '#1f77b4' for v in r.controlled_hazard_ratio]); ax.axhline(1, color='grey', lw=.8, ls=':')
ax.set_xlabel('minute of hour modulo 15 (14 = :14 :29 :44 :59)'); ax.set_ylabel('controlled closing hazard ratio'); ax.set_title('Clean profitable body closings cluster at the end of 15-minute blocks'); fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig2_minute_of_15.png'), dpi=160); plt.close(fig)
# 3 hold mod 15 histogram
h = pd.read_csv(os.path.join(c.ANALYSIS, 'h2b_hold_mod15_histogram.csv')); fig, ax = plt.subplots(figsize=(7, 3.2))
for m, col in (('FIFO', '#1f77b4'), ('LIFO', '#d62728')): d = h[h.convention == m]; ax.plot(d.phase_bin_start_s / 60 + .5, d.share, marker='o', label=m, color=col)
ax.axhline(1 / 15, color='grey', lw=.8, ls=':'); ax.set_xlabel('holding time modulo 15 minutes (minutes)'); ax.set_ylabel('share of one-lot closings'); ax.set_title('Holding time mod 15 min: mild concentration, not a per-lot timer at phase 0'); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig3_hold_mod15.png'), dpi=160); plt.close(fig)
# 4 population funnel
P = pd.read_csv(os.path.join(c.ANALYSIS, 'profitable_nonstop_summary.csv')).set_index('population'); X = pd.read_csv(os.path.join(c.ANALYSIS, 'unexplained_range_pop3.csv')).set_index('item').value
T = pd.read_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet')); s = T[T.direction == -1]
steps = [('short closings', len(s)), ('stable PROFIT (Pop 1)', int(P.loc['Pop1 stable PROFIT short', 'events'])), ('clean non-stop body (Pop 3)', int(P.loc['Pop3 clean profitable non-stop body', 'events'])), ('unexplained, strict flags (Pop 4S)', int(P.loc['Pop4S unexplained (strict flags)', 'events'])),
         ('  and not in a batch', int(X['strict unexplained and not in a multi-contract batch (events)'])), ('unexplained, registered flags (Pop 4)', int(P.loc['Pop4 unexplained (registered flags)', 'events']))]
fig, ax = plt.subplots(figsize=(7, 3.2)); ax.barh([a for a, _ in steps][::-1], [b for _, b in steps][::-1], color='#1f77b4')
for i, (a, b) in enumerate(steps[::-1]): ax.text(b + 80, i, f'{b:,}', va='center')
ax.set_xlabel('short closing fills'); ax.set_title('From all short closings to the unexplained profitable body closings'); fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig4_population_funnel.png'), dpi=160); plt.close(fig)
print(sorted(os.listdir(FIG)))
