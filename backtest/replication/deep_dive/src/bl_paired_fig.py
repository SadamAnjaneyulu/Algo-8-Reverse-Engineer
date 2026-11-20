"""Figures for the paired-sell study: scheduled ladder by cycle (D-1), D0 slot execution grid with cycle-stop marks, close hazard vs price/entry and |delta| (D-1 and D0)."""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
O = load_orders(); P = pd.read_csv(f'{OUT}/bl_slot_panel.csv'); H = pd.read_csv(f'{OUT}/bl_close_hazard.csv')
fig = plt.figure(figsize=(14, 10.5)); gs = fig.add_gridspec(2, 2, height_ratios=[1.35, 1])
ax = fig.add_subplot(gs[0, 0]); D1 = P[(P.day == 'D-1') & (P.cp == 'CE') & (P.k <= 23)]; W = D1.pivot_table(index=['expiry', 'und'], columns='k', values='lots_paired').sort_index(); im = ax.imshow(W.values, aspect='auto', cmap='Blues', vmin=0, vmax=4); ax.set_yticks(range(len(W))); ax.set_yticklabels([f'{e[5:]} {u[:1]}' for e, u in W.index], fontsize=6)
ax.set_xticks(range(0, 24, 2)); ax.set_xticklabels([f'{(9 * 60 + 16 + 15 * k) // 60:02d}:{(9 * 60 + 16 + 15 * k) % 60:02d}' for k in range(0, 24, 2)], rotation=60, fontsize=7); ax.set_title('D-1: paired lots per right at each slot (rows = cycles by expiry, N/S = index)', fontsize=9); plt.colorbar(im, ax=ax, fraction=.04)
ax.axhline(np.where(W.index.get_level_values(0) >= '2026-09-17')[0][0] - .5, color='r', lw=1.2); ax.text(23.4, np.where(W.index.get_level_values(0) >= '2026-09-17')[0][0] - .2, 'schedule\nchange', color='r', fontsize=7, va='top')
ax = fig.add_subplot(gs[0, 1]); D0 = P[(P.day == 'D0') & (P.cp == 'CE') & (P.k <= 23)]; W0 = D0.assign(ex=(D0.lots_paired > 0).astype(int)).pivot_table(index=['expiry', 'und'], columns='k', values='ex').sort_index(); ax.imshow(W0.values, aspect='auto', cmap='Greens', vmin=0, vmax=1)
st = O[(O.module == 's_') & (O.dayno == 1)].groupby(['und', 'expiry']).tod.min()
for i, (e, u) in enumerate(W0.index):
    if (u, e) in st.index: kk = (st[(u, e)] - (9 * 3600 + 16 * 60)) / 900; ax.plot([kk - .5, kk - .5], [i - .5, i + .5], color='r', lw=2)
ax.set_yticks(range(len(W0))); ax.set_yticklabels([f'{e[5:]} {u[:1]}' for e, u in W0.index], fontsize=6); ax.set_xticks(range(0, 24, 2)); ax.set_xticklabels([f'{(9 * 60 + 16 + 15 * k) // 60:02d}:{(9 * 60 + 16 + 15 * k) % 60:02d}' for k in range(0, 24, 2)], rotation=60, fontsize=7); ax.set_title('D0: slot executed (green); red tick = first cycle-stop order: nothing is sold after it', fontsize=9)
ax = fig.add_subplot(gs[1, 0]); 
for day, col in (('D-1', 'C0'), ('D0', 'C1')):
    h = H[(H.day == day) & (H.feature == 'ratio')]; ax.plot(range(len(h)), h.rate_per_1000.values, 'o-', color=col, label=day)
labs = H[(H.day == 'D-1') & (H.feature == 'ratio')].bin.str.replace(r'\((.*), (.*)\]', r'\2', regex=True).values; ax.set_xticks(range(len(labs))); ax.set_xticklabels(labs, fontsize=7); ax.set_xlabel('price now ÷ average entry price of the contract (upper edge of bin)'); ax.set_ylabel('buy-backs per 1,000 contract-minutes'); ax.set_yscale('log'); ax.legend(frameon=False); ax.set_title('Closing: D-1 follows the premium move (log scale); D0 does not', fontsize=9)
ax = fig.add_subplot(gs[1, 1])
for day, col in (('D-1', 'C0'), ('D0', 'C1')):
    h = H[(H.day == day) & (H.feature == 'abs_delta')]; ax.plot(range(len(h)), h.rate_per_1000.values, 'o-', color=col, label=day)
labs = H[(H.day == 'D-1') & (H.feature == 'abs_delta')].bin.str.replace(r'\((.*), (.*)\]', r'\2', regex=True).values; ax.set_xticks(range(len(labs))); ax.set_xticklabels(labs, fontsize=7); ax.set_xlabel('|delta| of the short contract (upper edge of bin)'); ax.set_ylabel('buy-backs per 1,000 contract-minutes'); ax.legend(frameon=False); ax.set_title('No delta limit: no step at any delta, falls for deep ITM', fontsize=9)
fig.tight_layout(); f = os.path.join(REP, 'figures', 'bl_paired_schedule.png'); fig.savefig(f, dpi=140); print(f)
