"""Figures for TP01_REPORT.md, drawn only from the analysis CSVs / parquet outputs. python3 tp_reconstruction/scripts/make_figures.py"""
import os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import tp_common as tc
FIG = os.path.join(tc.ANALYSIS, 'figures'); os.makedirs(FIG, exist_ok=True)
COL = {'FIFO': '#1f77b4', 'LIFO': '#d62728', 'AVG': '#2ca02c'}; plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
E = pd.read_parquet(os.path.join(tc.DATA, 'exit_events.parquet')); X = pd.read_parquet(os.path.join(tc.DATA, 'exit_event_consensus.parquet'))
# 1 label counts by convention (units) + stability
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6)); S = pd.read_csv(os.path.join(tc.ANALYSIS, 'profitability_summary.csv')); S = S[S.level == 'closing fill']
w = 0.25
for i, m in enumerate(tc.METHODS):
    s = S[S.method == m].set_index('label').units.reindex(['PROFIT', 'LOSS', 'BREAKEVEN', 'UNRESOLVED']); ax[0].bar(np.arange(4) + i * w, s.values / 1000, w, label=m, color=COL[m])
ax[0].set_xticks(np.arange(4) + w); ax[0].set_xticklabels(['PROFIT', 'LOSS', 'BREAKEVEN', 'UNRESOLVED']); ax[0].set_ylabel("closed units (thousands)"); ax[0].set_title('Closed quantity by label (closing-fill level)'); ax[0].legend(frameon=False)
st = X.groupby('stability').qty_closed.sum(); ax[1].bar(st.index, st.values / 1000, color=['#d62728', '#2ca02c', '#7f7f7f'][:len(st)]); ax[1].set_title('Stability across FIFO / LIFO / average cost'); ax[1].set_ylabel('closed units (thousands)')
for a in ax: a.tick_params(axis='x', rotation=15)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig1_labels_and_stability.png'), dpi=160); plt.close(fig)
# 2 premium decay distribution of profitable short closings
D = pd.read_csv(os.path.join(tc.ANALYSIS, 'premium_decay_distribution.csv')); fig, ax = plt.subplots(figsize=(7, 3.4))
for m in tc.METHODS:
    d = D[(D.method == m) & (D.side == 'PROFIT') & np.isfinite(D.bin_hi_pct)]; ax.step(d.bin_lo_pct + 2.5, d.closing_fills, where='mid', label=m, color=COL[m])
ax.set_xlabel('exit premium as % of entry premium (5-pp bins)'); ax.set_ylabel('profitable short closing fills'); ax.set_title('No recurring decay level: a flat profile plus a floor bin near zero'); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig2_premium_decay_profit_exits.png'), dpi=160); plt.close(fig)
# 3 closing hazard by decay ratio
H = pd.read_csv(os.path.join(tc.ANALYSIS, 'closing_hazard_by_decay.csv')); H = H[(H.und == 'ALL') & (H.rows >= 200)]; fig, ax = plt.subplots(figsize=(7, 3.4))
for m in tc.METHODS:
    h = H[H.convention == m]; ax.plot(h.bin_lo_pct + 2.5, h.hazard_standardised, label=m, color=COL[m])
ax.axvline(100, color='grey', lw=.8, ls=':'); ax.set_xlabel('short inventory mark as % of the reference entry (5-pp bins)'); ax.set_ylabel('P(closing fill within 5 min)')
ax.set_title('Closing hazard vs premium level (standardised for expiry day and clock hour)'); ax.legend(frameon=False); fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig3_closing_hazard_by_decay.png'), dpi=160); plt.close(fig)
# 4 clock minutes of short closings by label
e = E[(E.method == 'FIFO') & (E.direction == -1)]; mm = e.groupby([e.t_fill.dt.strftime('%H:%M'), 'label']).size().unstack(fill_value=0); fig, ax = plt.subplots(figsize=(10, 3.2))
ax.bar(range(len(mm)), mm.get('LOSS', 0), color='#d62728', label='LOSS'); ax.bar(range(len(mm)), mm.get('PROFIT', 0), bottom=mm.get('LOSS', 0), color='#2ca02c', label='PROFIT')
ticks = [i for i, k in enumerate(mm.index) if k.endswith(('00', '30'))]; ax.set_xticks(ticks); ax.set_xticklabels([mm.index[i] for i in ticks], rotation=60); ax.set_ylabel('short closing fills'); ax.set_title('Short closings by clock minute (FIFO labels): scheduled spikes'); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig4_closing_clock_minutes.png'), dpi=160); plt.close(fig)
# 5 holding time by label (shorts)
fig, ax = plt.subplots(figsize=(6, 3.2)); g = [np.log10(e[e.label == l].hold_minutes_mean.clip(lower=0.05)) for l in ('PROFIT', 'LOSS')]
ax.violinplot(g, showmedians=True); ax.set_xticks([1, 2]); ax.set_xticklabels(['PROFIT', 'LOSS']); ax.set_ylabel('log10 holding minutes'); ax.set_title('Holding time of short closings (FIFO)'); fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig5_holding_time.png'), dpi=160); plt.close(fig)
print(sorted(os.listdir(FIG)))
