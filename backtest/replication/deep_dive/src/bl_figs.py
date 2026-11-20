"""Figures for the Body lifecycle report (reports/figures/bl_*.png)."""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
FIG = os.path.join(REP, 'figures'); os.makedirs(FIG, exist_ok=True); plt.rcParams.update({'font.size': 9, 'figure.dpi': 130})
O = load_orders(); S = O[(O.module == 'num') & (O.role == 'open_short')].copy(); S['itm'] = np.where(S.cp == 'CE', -1, 1) * ((S.strike - S.atm_prev) / S.step).round()
# 1 offset distribution by class, D-1 and D0
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.3), sharey=True)
for ax, d in zip(axs, (0, 1)):
    for cls, col in (('slot_minute', 'C0'), ('other', 'C1'), ('roll_sell', 'C2')):
        g = S[(S.dayno == d) & (S.cls == cls)]; v = g.itm.clip(-3, 3).value_counts(normalize=True).sort_index(); ax.plot(v.index, v.values, 'o-', label=f'{cls} (n={len(g):,})', color=col)
    ax.set_title(['D-1', 'D0'][d] + ': sold strike − ATM(prev close), steps (+ = ITM side)'); ax.set_xlabel('steps (clipped ±3)'); ax.legend(frameon=False, fontsize=7)
axs[0].set_ylabel('share of orders'); fig.tight_layout(); fig.savefig(f'{FIG}/bl_offsets.png'); plt.close(fig)
# 2 reference-lag scan
T = pd.read_csv(f'{OUT}/bl_E2_reflag_scan.csv'); fig, ax = plt.subplots(figsize=(6.5, 3.2))
for (d, cls), g in T.set_index(['day', 'cls']).iterrows() if False else T.iterrows() and []: pass
Tt = T.set_index(['day', 'cls'])
for (d, cls), col, ls in ((0, 'slot_minute'), 'C0', '-'), ((0, 'other'), 'C1', '-'), ((1, 'slot_minute'), 'C0', '--'), ((1, 'other'), 'C1', '--'):
    row = Tt.loc[(d, cls)]; ax.plot([int(k) for k in row.index[:16]], row.values[:16], ls, color=col, marker='o', ms=3, label=f"{['D-1','D0'][d]} {cls}")
ax.set_xlabel('reference = spot close of minute j − k'); ax.set_ylabel('share of sells at the nearest strike'); ax.legend(frameon=False, fontsize=7); ax.set_title('Scheduled entries peak at k = 1 (previous completed minute)'); fig.tight_layout(); fig.savefig(f'{FIG}/bl_reflag.png'); plt.close(fig)
# 3 D-1 sells/covers by 15-min bucket
J = json.load(open(f'{OUT}/bl_summary_d1b.json')) if False else None
import json; J = json.load(open(f'{OUT}/bl_summary_d1b.json')); sb = pd.Series(J['sell_buckets']); cb = pd.Series(J['cover_buckets']).reindex(sb.index).fillna(0); fig, ax = plt.subplots(figsize=(8, 3.2)); x = np.arange(len(sb))
ax.bar(x - .2, sb.values, .4, label='body sells (lots)'); ax.bar(x + .2, cb.values, .4, label='body buy-backs (lots)'); ax.set_xticks(x[::2]); ax.set_xticklabels(sb.index[::2], rotation=45); ax.legend(frameon=False); ax.set_title('D-1: selling continues to the close; buy-backs are spread (no scheduled close)'); fig.tight_layout(); fig.savefig(f'{FIG}/bl_d1_buckets.png'); plt.close(fig)
# 4 D0 hour x class
H = pd.read_csv(f'{OUT}/bl_d0_C_hour_class.csv', index_col=0); fig, ax = plt.subplots(figsize=(7.5, 3.4)); H[['slot_minute', 'minute_before_slot', 'other', 'roll_sell', 'open_long', 'cover_short', 'close_long']].plot.bar(stacked=True, ax=ax, width=.8); ax.set_xlabel('hour (IST)'); ax.set_ylabel('body lots'); ax.legend(frameon=False, fontsize=7, ncol=2); ax.set_title('D0 body activity by hour and class'); fig.tight_layout(); fig.savefig(f'{FIG}/bl_d0_hour_class.png'); plt.close(fig)
# 5 D0 ending
M = pd.read_csv(f'{OUT}/bl_d0_D_close_minutes_pre_post.csv', index_col=0); M = M[(M.index >= '14:30')]; fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.2), sharey=False)
for ax, c, t in zip(axs, ('pre', 'post'), ('D0 date <= 2026-08-20 (no 15:14 flatten)', 'D0 date >= 2026-08-25 (15:14 flatten)')): ax.bar(range(len(M)), M[c].values); ax.set_xticks(range(0, len(M), 5)); ax.set_xticklabels(M.index[::5], rotation=45); ax.set_title(t, fontsize=8); ax.set_ylabel('body closing lots per minute')
fig.suptitle('D0 closing of shorts and longs by minute, 14:30 onwards', fontsize=9); fig.tight_layout(); fig.savefig(f'{FIG}/bl_d0_ending.png'); plt.close(fig); print(sorted(f for f in os.listdir(FIG) if f.startswith('bl_')))
