"""Figures for reports/LATE_SALE_RISK.md -> outputs/risk/risk_cycles.png (per-cycle grid) and risk_summary.png. Palette: blue (book state), orange/aqua are not needed; markers carry the meaning (shape = side, fill = delta-reducing)."""
import os, numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
RK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs', 'risk'); SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'; BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK, 'font.size': 8.5, 'axes.titlesize': 9, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'axes.spines.top': False, 'axes.spines.right': False, 'grid.color': GRID, 'axes.grid': True, 'axes.axisbelow': True, 'axes.grid.axis': 'y'})
hm = lambda j: f'{(555 + j) // 60:02d}:{(555 + j) % 60:02d}'
M = pd.read_csv(f'{RK}/minute_risk.csv'); O = pd.read_csv(f'{RK}/orders_risk.csv'); C = pd.read_csv(f'{RK}/cycle_risk.csv'); D = pd.read_csv(f'{RK}/cycle_diagnosis.csv')
O['ratio_b'] = O.delta_rs_pct_b / (O.F * 0.01) / O.gross_delta_b; O['ratio_a'] = O.delta_rs_pct_a / (O.F * 0.01) / O.gross_delta_b; O['cyc'] = O.und + '|' + O.d1; O['reduces'] = O.ratio_a.abs() < O.ratio_b.abs()
ce = M[(M.side == 'CE')].copy(); ce['signed'] = np.sign(ce.delta_pressure) * ce.delta_ratio; ce['cyc2'] = ce.und + '|' + ce.d1
cycles = [c for c in sorted(ce[(ce.era == 'after') & (ce.outlier == 0)].cyc2.unique())]
# ---------------------------------------------------------------- per-cycle grid
n = len(cycles); cols = 6; rows = int(np.ceil(n / cols)); fig, axs = plt.subplots(rows, cols, figsize=(15.5, 2.35 * rows + 0.9), sharey=True); axs = np.atleast_2d(axs)
for ax in axs.ravel(): ax.set_visible(False)
for i, c in enumerate(cycles):
    ax = axs.ravel()[i]; ax.set_visible(True); g = ce[ce.cyc2 == c].sort_values('j'); ax.plot(g.j, g.signed, color=BLUE, lw=1.6); ax.axhline(0, color=INK2, lw=0.8); ax.axvline(359.5, color=GRID, lw=1.2); o = O[(O.cyc == c) & (O.j >= 300)]
    for q in o.itertuples():
        ax.scatter(q.j, q.ratio_b, marker='v' if q.cp == 'CE' else '^', s=26 if q.j >= 360 else 14, facecolor=INK if q.reduces else SURF, edgecolor=INK, lw=0.9, zorder=3, alpha=1.0 if q.j >= 360 else 0.55)
    lab = D[D.cycle == c].label.iloc[0] if (D.cycle == c).any() else ''; ax.set_title(f"{c.replace('NIFTY', 'NIF').replace('SENSEX', 'SEN').replace('|2026-', ' ')}", fontsize=8.5); ax.set_xlim(298, 386); ax.set_ylim(-1.05, 1.05)
    ax.set_xticks([300, 360, 384]); ax.set_xticklabels(['14:15', '15:15', '15:39'], fontsize=7.5)
    if i % cols == 0: ax.set_ylabel('signed delta ÷ gross delta', fontsize=8)
fig.suptitle('Book delta imbalance through the late session, with each real sale (▼ call, ▲ put; filled = reduces |delta|, hollow = increases it)', x=0.01, ha='left', fontweight='bold', fontsize=11.5); fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(f'{RK}/risk_cycles.png', dpi=150); plt.close(fig)
# ---------------------------------------------------------------- summary
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6)); P = O[(O.era == 'after') & (O.outlier == 0) & (O.j >= 360)]; a = ax[0]
for k, (cp, lab, col) in enumerate((('CE', 'call sales', BLUE), ('PE', 'put sales', ORANGE))):
    y = P[P.cp == cp].ratio_b.values; x = k + (np.random.default_rng(1).random(len(y)) - 0.5) * 0.45; a.scatter(x, y, s=16, color=col, alpha=0.65, edgecolor='none'); a.hlines(np.median(y), k - 0.3, k + 0.3, color=INK, lw=2); a.text(k, 1.12, f'{lab}\nn={len(y)}, median {np.median(y):+.2f}', ha='center', fontsize=8.5)
a.axhline(0, color=INK2, lw=0.8); a.set_xlim(-0.6, 1.6); a.set_ylim(-1.1, 1.4); a.set_xticks([]); a.set_ylabel('signed delta ÷ gross delta just before the sale'); a.set_title('If side followed delta, calls would sit above 0 and puts below')
b = ax[1]; Cc = C[(C.outlier == 0)].copy(); Cc['ratio_nolate'] = Cc.delta_nolate_c.abs() / Cc.gross_nolate; Cc = Cc.sort_values('delta_ratio_1415').reset_index(drop=True); x = np.arange(len(Cc))
b.scatter(x, Cc.delta_ratio_1415, color=INK2, s=22, label='14:15', zorder=3); b.scatter(x, Cc.ratio_nolate, marker='s', color=ORANGE, s=22, label='close, without late sales', zorder=3); b.scatter(x, Cc.delta_ratio_end, marker='o', color=BLUE, s=26, label='close (actual)', zorder=3)
for i_, r_ in Cc.iterrows(): b.plot([i_, i_], [r_.delta_ratio_1415, r_.delta_ratio_end], color=GRID, lw=1, zorder=1)
b.set_xticks([]); b.set_xlabel('cycles (sorted by the 14:15 imbalance)'); b.set_ylabel('|net delta| ÷ gross delta'); b.set_title('The book ends more delta-neutral (26 of 29 cycles)'); b.legend(frameon=False, fontsize=8, loc='upper left')
c_ = ax[2]; H5 = C[(C.outlier == 0) & (C.late_orders > 0)].copy(); H5['d'] = (H5.gap_worst_end - H5.gap_worst_nolate) / 1e5; H5 = H5.sort_values('d').reset_index(drop=True)
c_.bar(np.arange(len(H5)), H5.d, color=[ORANGE if v < 0 else AQUA for v in H5.d], width=0.75); c_.axhline(0, color=INK2, lw=0.8); c_.set_xticks([]); c_.set_xlabel('cycles with late sales'); c_.set_ylabel('change in worst gap loss at the D0 open (₹ lakh)'); c_.set_title(f'The late sales deepen the worst gap loss in {(H5.d < 0).sum()} of {len(H5)} cycles')
fig.tight_layout(); fig.savefig(f'{RK}/risk_summary.png', dpi=150); print('ok', len(cycles))
