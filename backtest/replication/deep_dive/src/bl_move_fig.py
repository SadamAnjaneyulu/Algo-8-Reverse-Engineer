"""Figure: the six largest favourable 60-minute moves (D-1; calls sold into falls, puts into rises) with the solo (single-leg) sales of that right and their running count."""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
P = pd.read_csv(f'{OUT}/bl_move_panel.csv'); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); ch = Chain()
Q = P[P.day == 'D-1'].sort_values('fav60', ascending=False).drop_duplicates(['und', 'expiry', 'cp']).head(6)
fig, axs = plt.subplots(3, 2, figsize=(13, 10.5)); axs = axs.ravel()
for ax, r in zip(axs, Q.itertuples()):
    s = np.array([ch.spot(r.und, r.expiry, 0, j) for j in range(375)]); a = max(r.j - 45, 0); z = min(r.j + 75, 374); x = np.arange(a, z + 1); sgn = 1 if r.cp == 'CE' else -1; col = 'tab:blue' if r.cp == 'CE' else 'tab:red'
    ax.plot(x, s[a:z + 1], color='0.35'); ax.set_ylabel('spot'); g = ALL[(ALL.und == r.und) & (ALL.expiry == r.expiry) & (ALL.cp == r.cp) & (ALL.dayno == 0)]; g = g[(((g.tod - ref.OPEN_SEC) / 60) >= a) & (((g.tod - ref.OPEN_SEC) / 60) <= z)]
    solo = g[~g.paired]; pr = g[g.paired]; ax.scatter((pr.tod - ref.OPEN_SEC) / 60, [np.interp((t - ref.OPEN_SEC) / 60, x, s[a:z + 1]) for t in pr.tod], color='0.65', s=12, label=f'{r.cp} sold in a pair (clock)', zorder=2)
    ax.scatter((solo.tod - ref.OPEN_SEC) / 60, [np.interp((t - ref.OPEN_SEC) / 60, x, s[a:z + 1]) for t in solo.tod], color=col, s=34, label=f'{r.cp} solo sale (1 lot)', zorder=3, edgecolors='k', linewidths=.5)
    ax2 = ax.twinx(); cum = solo.sort_values('tod'); ax2.step((cum.tod - ref.OPEN_SEC) / 60, cum.lots.cumsum(), where='post', color=col, alpha=.5); ax2.set_ylabel('solo lots so far', color=col)
    t0 = (555 + a); ax.set_xticks(list(range(a - a % 15 + 15, z, 15))); ax.set_xticklabels([f'{(555 + t) // 60:02d}:{(555 + t) % 60:02d}' for t in range(a - a % 15 + 15, z, 15)], fontsize=7)
    ax.set_title(f'{r.und} {r.expiry} D-1, {r.cp}: {"fall" if r.cp == "CE" else "rise"} of {r.fav60:.2f} % in 60 min (to {(555 + r.j) // 60:02d}:{(555 + r.j) % 60:02d})', fontsize=8.5); ax.legend(fontsize=7, loc='best')
fig.tight_layout(); f = os.path.join(REP, 'figures', 'bl_move_drip_examples.png'); fig.savefig(f, dpi=140); print(f, Q[['und', 'expiry', 'cp', 'j', 'fav60']].round(2).to_string(index=False))
