"""Example-cycle figure: clock-driven paired sales vs single-leg sales, with the premium ratio of each right's short book (current price / average entry) underneath. Usage: python3 bl_trigger_fig.py NIFTY 2026-06-30"""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
u, e = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ('NIFTY', '2026-06-30')
O = load_orders(); S = pd.read_pickle(f'{OUT}/bl_trig_sells_d1.pkl.gz'); S = S[(S.und == u) & (S.expiry == e)]; ch = Chain(); step = ref.STEP[u]; spot = np.array([ch.spot(u, e, 0, j) for j in range(375)]); C = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0)].sort_values(['te', 'row'])
fig, axs = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.6])); ax = axs[0]
for k in range(1, 375, 15): ax.axvline(k, color='0.92', lw=.8, zorder=0)
ax.plot(range(375), spot, color='0.4', lw=1)
for cp, mk, col in (('CE', '^', 'tab:blue'), ('PE', 'v', 'tab:red')):
    g = S[S.cp == cp]; m = (g.tod - ref.OPEN_SEC) / 60
    ax.scatter(m[g.paired], g.strike[g.paired], marker=mk, s=26, color=col, alpha=.85, label=f'{cp} — paired with the other right (clock-driven)')
    ax.scatter(m[~g.paired], g.strike[~g.paired], marker=mk, s=70, facecolors='none', edgecolors='k', linewidths=1.4, zorder=4, label=f'{cp} — single-leg sale (black ring)')
ax.legend(fontsize=7.5, ncol=2, loc='upper right'); ax.set_ylabel('strike'); ax.set_title(f'{u} expiry {e} D-1 — straddle pairs on the 15-minute clock vs single-leg sales (rings)', fontsize=10)
ax2 = axs[1]
for cp, col in (('CE', 'tab:blue'), ('PE', 'tab:red')):
    c = C[C.cp == cp]; xs = []; ys = []
    for j in range(2, 375):
        T = ref.OPEN_SEC + j * 60; pre = c[c.tod < T]; net = pre.groupby('strike').sl.sum(); sh = -net[net < 0]
        if sh.sum() <= 0: continue
        bs = pre[(pre.module == 'num') & (pre.side == 'Sell')]; avg = {k: (g.px_avg * g.lots).sum() / g.lots.sum() for k, g in bs.groupby('strike')}; now = {k: ch.px(u, e, 0, cp, k, j - 1, 'close') for k in sh.index}; ok = [k for k in sh.index if k in avg and now[k] == now[k]]
        if ok: xs.append(j); ys.append(sum(sh[k] * now[k] for k in ok) / sum(sh[k] * avg[k] for k in ok))
    ax2.plot(xs, ys, color=col, label=f'{cp} short book: price now ÷ average entry')
    g = S[(S.cp == cp) & (~S.paired)]; ax2.scatter((g.tod - ref.OPEN_SEC) / 60, [np.interp((t - ref.OPEN_SEC) / 60, xs, ys) for t in g.tod], facecolors='none', edgecolors='k', s=45, zorder=4)
ax2.axhline(1, color='0.5', lw=.8, ls='--'); ax2.set_ylabel('book price ratio\n(<1 = in profit)'); ax2.legend(fontsize=7.5, loc='upper left')
ticks = list(range(0, 376, 30)); ax2.set_xticks(ticks); ax2.set_xticklabels([f'{(555 + t) // 60:02d}:{(555 + t) % 60:02d}' for t in ticks]); ax2.set_xlim(-3, 378); ax2.set_xlabel('time (IST)')
fig.tight_layout(); f = os.path.join(REP, 'figures', f'bl_trigger_{u}_{e}.png'); fig.savefig(f, dpi=140); print(f)
