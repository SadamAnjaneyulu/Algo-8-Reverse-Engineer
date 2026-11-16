"""TP-03 Phase 1 figures (from the analysis CSVs only)."""
import os, sys
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); TP03 = os.path.dirname(HERE); A = os.path.join(TP03, 'analysis'); F = os.path.join(TP03, 'figures'); os.makedirs(F, exist_ok=True)
E = pd.read_csv(os.path.join(A, 'p1_e1_window_rates.csv')); O = pd.read_csv(os.path.join(A, 'p1_e5_offsets.csv'))
fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
p = E[(E.kind == 'PRE') & (E.view == 'V2')].sort_values('window'); col = ['#d95f02' if c else '#1b9e77' for c in p.control_window]
ax[0].bar(p.window, p.action_rate, color=col); ax[0].set_ylim(0, 1.05); ax[0].set_title('Pre-expiry: share of sessions with a new body short pair\n(green = 17 registered windows, orange = 4 control windows; V2)', fontsize=9); ax[0].tick_params(axis='x', rotation=90, labelsize=7)
d = E[(E.kind == 'D0') & (E.view == 'V2')].sort_values('window'); ax[1].bar(d.window, d.action_rate, color='#7570b3'); ax[1].set_ylim(0, 1.05); ax[1].set_title('Expiry day: action rate among applicable windows (V2)', fontsize=9); ax[1].tick_params(axis='x', rotation=90, labelsize=7)
x = O[O.reference == 'R1'].copy(); x['lab'] = x.und.str[:3] + ' ' + x.day_type + '\n' + x.event_class.str.replace('_ACTION', '').str.replace('INITIAL_ENTRY', 'INITIAL'); ax[2].bar(range(len(x)), x.exact, color=['#1b9e77' if 'WINDOW' in e and 'OFF' not in e else ('#d95f02' if 'OFF' in e else '#7570b3') for e in x.event_class]); ax[2].set_xticks(range(len(x))); ax[2].set_xticklabels(x.lab, fontsize=6, rotation=90); ax[2].axhline(0.236, color='k', ls='--', lw=1); ax[2].text(0, 0.25, 'chance 23.6%', fontsize=7); ax[2].set_ylim(0, 1.05); ax[2].set_title('Strike = ATM of last completed close (R1): exact-match rate by order class', fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(F, 'p1_entry_overview.png'), dpi=140); print('saved')
