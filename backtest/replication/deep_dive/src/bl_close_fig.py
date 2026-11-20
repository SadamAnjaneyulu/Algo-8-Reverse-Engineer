"""Figure for the buy-back study -> reports/figures/bl_close_logic.png (4 panels, D-1)."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
import os
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); os.makedirs(FIG, exist_ok=True)
F = pd.read_csv(f'{OUT}/bl_close_orders_flags.csv'); F = F[F.day == 'D-1']; P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); P = P[P.day == 'D-1']; L = pd.read_csv(f'{OUT}/bl_close_lots.csv'); A = pd.read_csv(f'{OUT}/bl_close_C_auc.csv')
fig, ax = plt.subplots(2, 2, figsize=(13, 9)); c = {'r_avg': '#7f7f7f', 'r_low': '#d62728', 'r_fifo': '#1f77b4'}; nm = {'r_avg': 'average open entry', 'r_low': 'cheapest open entry (LOW)', 'r_fifo': 'oldest open entry (FIFO)'}
a = ax[0, 0]; b = np.arange(0.2, 2.15, 0.05)
for k in ('r_avg', 'r_low'): a.hist(F[k].clip(0.2, 2.1), bins=b, alpha=.55, color=c[k], label=nm[k])
a.axvline(1.2, color='k', ls=':', lw=1); a.text(1.21, a.get_ylim()[1] * .92, '1.2×', fontsize=9); a.set_xlabel('premium at buy-back ÷ entry'); a.set_ylabel('buy-back orders (1 lot each)'); a.set_title('A. Where D-1 buy-backs happen (n = %d)' % len(F)); a.legend(fontsize=8)
a = ax[0, 1]; bins = [0, .8, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.5]; mid = [(bins[i] + bins[i + 1]) / 2 for i in range(len(bins) - 1)]
for k in ('r_avg', 'r_low', 'r_fifo'):
    t = P.groupby(pd.cut(P[k], bins), observed=True).bb_lots.agg(n='size', ev=lambda s: (s > 0).sum()); a.plot([mid[i] for i in range(len(t))], t.ev / t.n * 1000, 'o-', color=c[k], label=nm[k])
a.set_yscale('log'); a.axvline(1.2, color='k', ls=':', lw=1); a.set_xlabel('premium ÷ entry at the previous minute close'); a.set_ylabel('buy-backs per 1000 contract-minutes (log)'); a.set_title('B. Hazard per contract-minute: no step at 1.2×'); a.legend(fontsize=8)
a = ax[1, 0]; bb = [0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.0, 99]; lab = ['≤1.0', '1.0–1.1', '1.1–1.2', '1.2–1.3', '1.3–1.4', '1.4–1.5', '1.5–1.6', '1.6–1.7', '1.7–2.0', '>2.0']
for cv, col in (('low', '#d62728'), ('fifo', '#1f77b4'), ('high', '#2ca02c')):
    l = L[L.conv == cv]; t = l.groupby(pd.cut(l.max_ratio, bb), observed=True).closed_d1.agg(['size', 'mean']); a.plot(range(len(t)), 1 - t['mean'], 'o-', color=col, label=f'{cv.upper()} lot convention')
a.set_xticks(range(len(lab))); a.set_xticklabels(lab, rotation=45, fontsize=8); a.set_ylabel('share of D-1 sold lots carried overnight'); a.set_xlabel('highest premium ÷ own entry reached on D-1 (minute closes)'); a.axvline(2.5, color='k', ls=':', lw=1); a.set_ylim(0, 1); a.set_title('C. Lots below ~1.4× are mostly carried; above ~1.6× mostly closed'); a.legend(fontsize=8)
a = ax[1, 1]; s = F.groupby(pd.cut(F.r_avg, [0, .8, 1.0, 1.2, 1.4, 1.55, 1.7, 2.0, 99]), observed=True).agg(n=('paired', 'size'), paired=('paired', 'mean'), part=('partnered', 'mean'))
x = np.arange(len(s)); a.bar(x - .2, s.paired * 100, .4, color='#ff7f0e', label='CE+PE same strike within ±3 s'); a.bar(x + .2, s.part * 100, .4, color='#9467bd', label='other right, any strike, within ±3 s')
a.set_xticks(x); a.set_xticklabels([f'{l}\n(n={n})' for l, n in zip(['≤0.8', '0.8–1.0', '1.0–1.2', '1.2–1.4', '1.4–1.55', '1.55–1.7', '1.7–2.0', '>2.0'], s.n)], fontsize=8); a.set_ylabel('% of buy-back orders'); a.set_xlabel('premium ÷ average entry'); a.set_title('D. Buy-backs are mostly single-leg (paired share %.1f%%, chance 0.1%%)' % (F.paired.mean() * 100)); a.legend(fontsize=8)
fig.suptitle('Algo 8 body buy-backs on D-1 — in-sample, 31 cycles, decision price = limit ÷ 1.15', fontsize=11); fig.tight_layout(); fig.savefig(f'{FIG}/bl_close_logic.png', dpi=140); print('saved')
