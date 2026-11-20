"""Figures for the Body/Hedge report (reports/figures/bh_*.png), all from computed outputs."""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bh_common import *
FIG = os.path.join(REP, 'figures'); os.makedirs(FIG, exist_ok=True); plt.rcParams.update({'font.size': 9, 'figure.dpi': 130})
H = pd.read_csv(f'{OUT}/bh_h1_lag_hist.csv'); fig, ax = plt.subplots(figsize=(6.5, 3.2)); x = (H.lag_lo + H.lag_hi) / 2
ax.bar(x, H.real, width=.45, label='real hedge orders (decision stamp − body first-fill second)'); ax.plot(x, H.null_per_shift, 'r-', lw=1.3, label='time-shift null (mean of 4 shifts)'); ax.set_xlabel('lag, seconds'); ax.set_ylabel('count per 0.5 s'); ax.set_xlim(-5, 20); ax.legend(frameon=False, fontsize=7); ax.set_title('Hedge response lag: nothing before ~2.5 s, peak 3.5–4 s'); fig.tight_layout(); fig.savefig(f'{FIG}/bh_lag_hist.png'); plt.close(fig)
G = pd.read_csv(f'{OUT}/bh_h3c_wing_orders.csv'); c = G[G.complete]; fig, axs = plt.subplots(1, 2, figsize=(9, 3.3))
for (d, s), g in c.groupby(['dayno', 'side']):
    pass
t = c.assign(exact=(c.sw == c.gap_before), sign=(np.sign(c.sw) == np.sign(c.gap_before))).groupby(['dayno', 'side'])[['exact', 'sign']].mean(); lab = [f"{['D-1','D0'][d]}\n{s}" for d, s in t.index]
axs[0].bar(np.arange(len(t)) - .2, t.exact, .4, label='|order lots| = S−L exactly'); axs[0].bar(np.arange(len(t)) + .2, t.sign, .4, label='sign agrees with S−L'); axs[0].set_xticks(range(len(t))); axs[0].set_xticklabels(lab); axs[0].set_ylim(0, 1.3); axs[0].legend(frameon=False, fontsize=7, loc='upper center', ncol=1); axs[0].set_title('Hedge order size = book gap (30 complete cycles)')
Q = pd.read_csv(f'{OUT}/bh_h3b_quiet.csv'); vc = Q.assign(g=Q.gap_all.clip(-5, 5)).groupby(['dayno', 'g']).size().unstack(0).fillna(0); vc = vc / vc.sum(); vc.plot.bar(ax=axs[1], width=.8); axs[1].set_xlabel('S − L at body order + 30 s (clipped ±5)'); axs[1].set_ylabel('share of quiet samples'); axs[1].legend(['D-1', 'D0'], frameon=False); axs[1].set_title('Quiet-time balance of the book (7,564 samples)'); fig.tight_layout(); fig.savefig(f'{FIG}/bh_level_control.png'); plt.close(fig)
S = pd.read_csv(f'{OUT}/bh_h2_simple_final.csv'); fig, ax = plt.subplots(figsize=(6.5, 3.2))
for d, col in ((0, 'C0'), (1, 'C1')): ax.hist(S[S.dayno == d].ratio_ref.clip(0, .08), bins=np.arange(0, .0805, .002), alpha=.6, label=['D-1', 'D0'][d], color=col)
ax.axvline(.025, color='k', ls='--'); ax.set_xlabel('wing decision price ÷ body decision price (from limit prices)'); ax.set_ylabel('simple wing buys'); ax.legend(frameon=False); ax.set_title('Wing premium ≈ 2.5 % of the sold option (D-1 tight, D0 diffuse)'); fig.tight_layout(); fig.savefig(f'{FIG}/bh_wing_ratio.png'); plt.close(fig)
O = order_table(); fig, ax = plt.subplots(figsize=(6.5, 3.2))
for m, side, col in (('num', 'Sell', 'C0'), ('num', 'Buy', 'C1'), ('h_', 'Buy', 'C2')):
    g = O[(O.module == m) & (O.side == side) & (O.px_first >= 3)]; r = (g.lim_px / g.px_first) if side == 'Buy' else (g.lim_px / g.px_first); ax.hist(r.clip(.7, 1.3), bins=np.arange(.7, 1.3, .005), alpha=.55, label=f"{ {'num':'body','h_':'hedge'}[m]} {side}", color=col)
ax.axvline(.85, color='k', ls=':'); ax.axvline(1.15, color='k', ls=':'); ax.set_xlabel('limit price ÷ first fill price'); ax.set_ylabel('orders'); ax.legend(frameon=False, fontsize=7); ax.set_title('All three streams: marketable limit ≈ 15 % beyond the live price'); fig.tight_layout(); fig.savefig(f'{FIG}/bh_limit_cushion.png'); plt.close(fig)
print(sorted(os.listdir(FIG)))
