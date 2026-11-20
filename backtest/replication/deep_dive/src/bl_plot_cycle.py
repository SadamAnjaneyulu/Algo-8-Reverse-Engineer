"""Per-cycle D-1 (or D0) plot of body SHORT sales only (no long wings, no hedges): time vs strike, CE and PE separately, with spot and slot clock.
Usage: python3 bl_plot_cycle.py [und expiry [D-1|D0]]  -> reports/figures/cycles/bl_sold_<und>_<expiry>_<day>.png and outputs/cycles/bl_sold_<und>_<expiry>_<day>.csv ; no args = every cycle"""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, matplotlib.dates as mdates
from bl_common import *
O = load_orders(); ch = Chain(); FIGD = os.path.join(REP, 'figures', 'cycles'); CSVD = os.path.join(OUT, 'cycles'); os.makedirs(FIGD, exist_ok=True); os.makedirs(CSVD, exist_ok=True)
def tmin(t): return (t - ref.OPEN_SEC) / 60          # minutes since 09:15
def lab(m): h = 9 * 60 + 15 + m; return f'{int(h // 60):02d}:{int(h % 60):02d}'
def plot(und, exp, day):
    d = 0 if day == 'D-1' else 1; S = O[(O.und == und) & (O.expiry == exp) & (O.dayno == d) & (O.module == 'num') & (O.role == 'open_short')].sort_values(['te', 'row'])
    if S.empty: return None
    step = ref.STEP[und]; spot = np.array([ch.spot(und, exp, d, j) for j in range(375)]); x = np.arange(375)
    lo = min(S.strike.min(), np.nanmin(spot)) - 2 * step; hi = max(S.strike.max(), np.nanmax(spot)) + 2 * step
    fig, axs = plt.subplots(3, 1, figsize=(13, 9.5), sharex=True, gridspec_kw=dict(height_ratios=[4, 1.3, 1.6]))
    ax = axs[0]
    for k in range(0, 375, 15):                                   # slot clock 09:16 + 15k  (minute index 1 + 15k)
        ax.axvline(1 + k, color='0.9', lw=.8, zorder=0)
    ax.plot(x, spot, color='0.35', lw=1.1, label='spot (minute close)', zorder=1)
    for cp, mk, col in (('CE', '^', 'tab:blue'), ('PE', 'v', 'tab:red')):
        g = S[S.cp == cp]; sched = g.cls == 'slot_minute'
        for sel, fill in ((sched, True), (~sched, False)):
            h = g[sel]
            if h.empty: continue
            ax.scatter(tmin(h.tod), h.strike, s=18 + 22 * (h.lots - 1).clip(upper=6), marker=mk, facecolors=col if fill else 'none', edgecolors=col, linewidths=1.1, alpha=.85, zorder=3, label=f'{cp} sell — ' + ('scheduled slot minute' if fill else 'other time'))
    ax.set_ylim(lo, hi); ax.set_ylabel('strike'); ax.set_title(f'{und} expiry {exp} — {day}: body SHORT sales only (no long wings, no hedges). Marker size ∝ lots; light vertical lines = slot minutes 09:16 + 15 k', fontsize=10)
    ax.legend(loc='upper left', fontsize=7.5, ncol=3, frameon=True)
    ax2 = axs[1]; w = S.groupby([S.cp, (S.tod // 60 - 555 - 0).astype(int)]).lots.sum()
    for cp, col, off in (('CE', 'tab:blue', -.2), ('PE', 'tab:red', .2)):
        if cp in w.index.get_level_values(0): s_ = w[cp]; ax2.bar(s_.index.values + off, s_.values, .4, color=col)
    ax2.set_ylabel('lots sold\nper minute')
    ax3 = axs[2]; E = O[(O.und == und) & (O.expiry == exp)].sort_values(['te', 'row']); net = {}; ts = []; ce = []; pe = []
    for r in E.itertuples():
        net[(r.cp, r.strike)] = net.get((r.cp, r.strike), 0) + r.sl
        if r.dayno == d: ts.append(tmin(r.tod)); ce.append(sum(-v for (c, k), v in net.items() if c == 'CE' and v < 0)); pe.append(sum(-v for (c, k), v in net.items() if c == 'PE' and v < 0))
    ax3.step(ts, ce, where='post', color='tab:blue', label='CE short lots (all modules, contract level)'); ax3.step(ts, pe, where='post', color='tab:red', label='PE short lots'); ax3.set_ylabel('short lots held'); ax3.legend(fontsize=7.5, loc='upper left')
    ticks = list(range(0, 376, 30)); ax3.set_xticks(ticks); ax3.set_xticklabels([lab(t) for t in ticks]); ax3.set_xlim(-3, 378); ax3.set_xlabel('time (IST)')
    fig.tight_layout(); f = f'{FIGD}/bl_sold_{und}_{exp}_{day}.png'; fig.savefig(f, dpi=140); plt.close(fig)
    T = S[['time_IST', 'cp', 'strike', 'lots', 'ref_px', 'atm_prev', 'cls']] if 'time_IST' in S else S.assign(time_IST=[f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}' for t in S.tod])[['time_IST', 'cp', 'strike', 'lots', 'ref_px', 'atm_prev', 'cls']]
    T = T.assign(offset_steps=((T.strike - T.atm_prev) / step).round(0)).rename(columns={'cp': 'right', 'ref_px': 'price_at_decision', 'atm_prev': 'ATM_prev_close', 'cls': 'class'}); T.to_csv(f'{CSVD}/bl_sold_{und}_{exp}_{day}.csv', index=False); return f, len(T)
if __name__ == '__main__':
    if len(sys.argv) >= 3: print(plot(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'D-1'))
    else:
        n = 0
        for (u, e), _ in O.groupby(['und', 'expiry']):
            for day in ('D-1', 'D0'):
                r = plot(u, e, day); n += r is not None
        print('plots', n)
