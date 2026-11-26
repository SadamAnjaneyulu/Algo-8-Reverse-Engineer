"""Figure for the after-15:00 solo study: reports/figures/bl_sl_summary.png"""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); Z = pd.read_csv(f'{OUT}/bl_sl_class.csv'); P = pd.read_csv(f'{OUT}/bl_sl_prem.csv'); B = pd.read_csv(f'{OUT}/bl_sl_blocks.csv'); S1 = json.load(open(f'{OUT}/bl_summary_sl1.json')); S4 = json.load(open(f'{OUT}/bl_summary_sl4.json'))
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
pl = Z.prem_newlow15.fillna(False).astype(bool); E = Z.E.astype(bool); Bb = (Z.Bb | Z.Ba).astype(bool)
Z['c'] = np.select([E, ~E & pl, ~E & ~pl & Bb], ['spot fresh 15-min extreme', 'premium fresh 15-min low only', 'cross-right buy-back ±10 s only'], 'unexplained'); Z['m'] = (Z.j - 345).clip(0, 30)
t = Z.pivot_table(index='m', columns='c', values='lots', aggfunc='sum').fillna(0).reindex(range(31), fill_value=0); cols = ['spot fresh 15-min extreme', 'premium fresh 15-min low only', 'cross-right buy-back ±10 s only', 'unexplained']; col = ['#2b6cb0', '#38a169', '#dd6b20', '#a0aec0']
bot = np.zeros(31)
for c, k in zip(cols, col):
    v = t[c].values if c in t else np.zeros(31); ax[0, 0].bar(t.index, v, bottom=bot, color=k, label=c); bot += v
ax[0, 0].set_xticks(range(0, 31, 5)); ax[0, 0].set_xticklabels([f'15:{m:02d}' for m in range(0, 31, 5)]); ax[0, 0].set_ylabel('late solo lots'); ax[0, 0].legend(fontsize=8); ax[0, 0].set_title('(a) Late solo lots by minute and by what coincides with them')
q = P.set_index(['window', 'variable']); lab = ['bk15', 'pl15_itm WITHOUT bk15', 'bk15 OR pl15_itm']; nice = ['spot fresh 15-min extreme', 'premium 15-min low, no spot extreme', 'either (R3)']; x = np.arange(3)
for o, (w, k) in enumerate([('intraday 10:30-14:59', '#718096'), ('late 15:00-15:29', '#2b6cb0')]):
    ax[0, 1].bar(x + (o - .5) * .38, [q.loc[(w, v), 'hazard_if'] for v in lab], .38, color=k, label=f'{w}: P(sale | condition)')
for o, w in enumerate(['intraday 10:30-14:59', 'late 15:00-15:29']): ax[0, 1].axhline(q.loc[(w, 'bk15 OR pl15_itm'), 'hazard_not'], ls=':', color=['#718096', '#2b6cb0'][o], label=f'{w}: P(sale | neither)')
ax[0, 1].set_xticks(x); ax[0, 1].set_xticklabels(nice, fontsize=8); ax[0, 1].legend(fontsize=7); ax[0, 1].set_title('(b) Sale probability per minute × right, by condition')
b = B.pivot(index='block', columns='model', values='AUC').reindex(['market', 'history', 'clock', 'micro', 'volatility', 'inventory', 'greeks', 'flow', 'all']); b.plot.barh(ax=ax[1, 0], color=['#2b6cb0', '#a0aec0']); ax[1, 0].axvline(.5, color='k', lw=.8); ax[1, 0].set_xlim(.4, .9); ax[1, 0].set_xlabel('leave-one-cycle-out AUC (late minute × right panel)'); ax[1, 0].set_title('(c) Which block of variables predicts late solo minutes')
v = [S1['intraday']['share_reduce_abs_delta'], S1['late']['share_reduce_abs_delta'], S4['H3']['lot_share_on_lighter_side'], S4['H3']['share_cycles_imb_shrinks']]
ax[1, 1].bar(range(4), v, color=['#718096', '#2b6cb0', '#2b6cb0', '#2b6cb0']); ax[1, 1].axhline(.5, ls='--', color='k', lw=.8); ax[1, 1].set_xticks(range(4)); ax[1, 1].set_xticklabels(['intraday solo:\nreduces |book delta|', 'late solo:\nreduces |book delta|', 'late solo lot on the\nlighter CE/PE side', 'cycles where CE/PE\nimbalance shrinks 15:00→15:30'], fontsize=8); ax[1, 1].set_ylim(0, 1); ax[1, 1].set_title('(d) Portfolio-shaping hypotheses: all near a coin flip (rejected)')
for i, y in enumerate(v): ax[1, 1].text(i, y + .02, f'{y:.0%}', ha='center')
plt.tight_layout(); plt.savefig(f'{FIG}/bl_sl_summary.png', dpi=130); print('ok')
