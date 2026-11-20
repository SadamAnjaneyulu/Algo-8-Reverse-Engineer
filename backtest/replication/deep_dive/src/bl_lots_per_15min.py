"""Body short-sale lots per 15-minute clock bucket (09:15-09:30, ...) per cycle, D-1 and D0, across cycles with that day's log. Outputs outputs/bl_lots_per_15min_{d1,d0}.csv (cycle x bucket) and a summary + figure."""
import sys; sys.path.insert(0, '.')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); S = O[(O.module == 'num') & (O.role == 'open_short')].copy()
S['b'] = ((S.tod - ref.OPEN_SEC) // 900).clip(upper=24).astype(int)        # 0 = 09:15-09:30 ... 24 = 15:15-15:30 ; later stamps (15:30+) -> own bucket 25
S.loc[S.tod >= 15 * 3600 + 30 * 60, 'b'] = 25
lab = lambda b: ('15:30-15:35' if b == 25 else f"{(9 * 60 + 15 + 15 * b) // 60:02d}:{(9 * 60 + 15 + 15 * b) % 60:02d}-{(9 * 60 + 30 + 15 * b) // 60:02d}:{(9 * 60 + 30 + 15 * b) % 60:02d}")
res = {}
for d, nm in ((0, 'd1'), (1, 'd0')):
    ok = [(u, e) for u, e, h in zip(cyc.und, cyc.expiry, cyc.has_d1 if d == 0 else cyc.has_d0) if h]; g = S[S.dayno == d]
    M = g.groupby(['und', 'expiry', 'b']).lots.sum().unstack('b').reindex(pd.MultiIndex.from_tuples(ok, names=['und', 'expiry'])).fillna(0).reindex(columns=range(26), fill_value=0); M.columns = [lab(b) for b in M.columns]; M.to_csv(f'{OUT}/bl_lots_per_15min_{nm}.csv'); res[nm] = M
    st = pd.DataFrame(dict(mean=M.mean(), median=M.median(), std=M.std(), cv=M.std() / M.mean(), p25=M.quantile(.25), p75=M.quantile(.75), min=M.min(), max=M.max(), zero_share=(M == 0).mean())).round(2); st.to_csv(f'{OUT}/bl_lots_per_15min_{nm}_summary.csv')
    tot = M.sum(axis=1); print('\n==', nm.upper(), 'cycles', len(M), '| total body short lots per cycle: mean %.1f median %.1f std %.1f CV %.2f min %d max %d' % (tot.mean(), tot.median(), tot.std(), tot.std() / tot.mean(), tot.min(), tot.max()))
    print(st.to_string())
    # variance decomposition: cycle effect vs bucket effect (two-way, no interaction)
    x = M.values; gm = x.mean(); ss_tot = ((x - gm) ** 2).sum(); ss_b = ((x.mean(axis=0) - gm) ** 2).sum() * x.shape[0]; ss_c = ((x.mean(axis=1) - gm) ** 2).sum() * x.shape[1]
    print('variance share: time-of-day bucket %.3f, cycle (size) %.3f, residual %.3f' % (ss_b / ss_tot, ss_c / ss_tot, 1 - (ss_b + ss_c) / ss_tot))
    # NIFTY vs SENSEX
    for u in ('NIFTY', 'SENSEX'): m = M.xs(u, level='und'); print(u, 'cycles', len(m), 'mean lots per bucket %.2f, per cycle %.1f' % (m.values.mean(), m.sum(axis=1).mean()))
    # poisson-like benchmark: CV if lots were independent counts with the same mean = 1/sqrt(mean)
    print('mean of per-bucket CV %.2f ; Poisson benchmark mean of 1/sqrt(mean) %.2f' % ((M.std() / M.mean()).mean(), (1 / np.sqrt(M.mean())).mean()))
fig, axs = plt.subplots(2, 1, figsize=(13, 8))
for ax, (nm, M), t in zip(axs, res.items(), ('D-1', 'D0')):
    cols = list(M.columns); ax.boxplot([M[c].values for c in cols], positions=range(len(cols)), widths=.6, showfliers=True, flierprops=dict(markersize=3), medianprops=dict(color='k'))
    ax.plot(range(len(cols)), M.mean().values, 'o-', color='tab:red', ms=4, label='mean over cycles'); ax.set_xticks(range(len(cols))); ax.set_xticklabels([c[:5] for c in cols], rotation=60, fontsize=7); ax.set_ylabel('body short lots sold'); ax.set_title(f'{t}: lots sold in each 15-minute window, one box = {len(M)} cycles (window starts shown)'); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(REP, 'figures', 'bl_lots_per_15min.png'), dpi=140)
