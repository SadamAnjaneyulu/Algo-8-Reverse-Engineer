"""Summary figure for the solo-sell variable search: model AUCs, the step at a fresh extreme, and an example cycle."""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
M = pd.read_csv(f'{OUT}/bl_final_models.csv'); F = pd.read_csv(f'{OUT}/bl_breakout_panel.csv'); F = F[F.tslot != 0]; ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); ch = Chain()
fig = plt.figure(figsize=(14, 9)); gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1])
ax = fig.add_subplot(gs[0, 0]); m = M[(M.day == 'D-1')].pivot(index='model', columns='kind', values='AUC').sort_index(ascending=False); y = np.arange(len(m)); ax.barh(y + .2, m.lr, .4, label='logistic'); ax.barh(y - .2, m.gb, .4, label='gradient boosting'); ax.set_yticks(y); ax.set_yticklabels([s[:46] for s in m.index], fontsize=7); ax.set_xlim(.65, .93); ax.axvline(.5, color='k'); ax.set_xlabel('leave-one-cycle-out AUC (D-1)'); ax.legend(frameon=False, fontsize=7); ax.set_title('How much each variable group adds', fontsize=9)
ax = fig.add_subplot(gs[0, 1])
for day, col in (('D-1', 'C0'), ('D0', 'C1')):
    Q = F[F.day == day]; t = Q.groupby(pd.cut(Q.pos15, [0, .2, .4, .6, .8, .95, 1.0])).ep.mean() * 1000; ax.plot(range(len(t)), t.values, 'o-', color=col, label=day)
ax.set_xticks(range(6)); ax.set_xticklabels(['0-.2', '.2-.4', '.4-.6', '.6-.8', '.8-.95', '.95-1\n(at the extreme)']); ax.set_ylabel('solo-episode starts per 1,000 minutes'); ax.set_xlabel('position of the previous close within the last 15 closes (1 = most favourable)'); ax.legend(frameon=False); ax.set_title('A step at the fresh extreme', fontsize=9)
ax = fig.add_subplot(gs[1, :]); u, e, cp = 'NIFTY', '2026-06-30', 'CE'; s = np.array([ch.spot(u, e, 0, j) for j in range(375)]); sg = 1; v = -s
bk = [j for j in range(16, 375) if v[j - 1] >= np.nanmax(v[j - 16:j]) - 1e-9]; g = ALL[(ALL.und == u) & (ALL.expiry == e) & (ALL.cp == cp) & (ALL.dayno == 0)]; solo = g[~g.paired]; pr = g[g.paired]
ax.plot(range(375), s, color='0.4', lw=1); ax.scatter([j - 1 for j in bk], s[[j - 1 for j in bk]], marker='v', s=14, color='tab:green', alpha=.7, label='close = new 15-minute low (favourable extreme for a call)')
ax.scatter((pr.tod - ref.OPEN_SEC) / 60, [np.interp((t - ref.OPEN_SEC) / 60, range(375), s) for t in pr.tod], s=14, color='0.6', label='CE sold in a pair (clock)', zorder=3); ax.scatter((solo.tod - ref.OPEN_SEC) / 60, [np.interp((t - ref.OPEN_SEC) / 60, range(375), s) for t in solo.tod], s=60, facecolors='none', edgecolors='tab:blue', linewidths=1.6, label='CE solo sale', zorder=4)
ticks = list(range(0, 376, 30)); ax.set_xticks(ticks); ax.set_xticklabels([f'{(555 + t) // 60:02d}:{(555 + t) % 60:02d}' for t in ticks]); ax.set_ylabel('spot'); ax.legend(fontsize=7.5, loc='upper right'); ax.set_title('NIFTY 2026-06-30 D-1: solo call sales cluster on the minutes after fresh 15-minute lows', fontsize=9)
fig.tight_layout(); f = os.path.join(REP, 'figures', 'bl_breakout_summary.png'); fig.savefig(f, dpi=140); print(f)
