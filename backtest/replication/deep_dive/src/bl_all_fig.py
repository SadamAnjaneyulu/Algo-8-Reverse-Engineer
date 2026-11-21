"""Figure for the combined D-1 selling reconstruction -> reports/figures/bl_all_sells.png"""
import sys, os, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
exec(open('bl_all_sells.py').read().split("ACT = {d['cid']")[0])
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); T = pd.read_csv(f'{OUT}/bl_all_sells_type.csv'); R1 = json.load(open(f'{OUT}/bl_summary_all1.json'))
fig = plt.figure(figsize=(15, 10)); gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.3]); a = fig.add_subplot(gs[0, 0]); t = T[T.tolerance_min == 1].set_index('sell_type').loc[['scheduled', 'reactive', 'solo']]; x = np.arange(3)
for k, (col, c) in enumerate((('precision', '#1f77b4'), ('recall', '#ff7f0e'), ('F1', '#2ca02c'), ('strike_exact_of_matched', '#9467bd'))): a.bar(x + (k - 1.5) * .2, t[col], .2, color=c, label=col.replace('_', ' '))
for k, v in enumerate(t.F1): a.text(k + .1, v + .02, f'{v:.2f}', fontsize=8, ha='center')
a.set_xticks(x); a.set_xticklabels([f"{s}\n({100 * R1['actual_share'][s]:.0f}% of D-1 sold lots)" for s in t.index]); a.set_ylim(0, 1.1); a.legend(fontsize=7, ncol=2); a.set_title('A. Lot-level match by sell type (±1 minute, same right)')
a = fig.add_subplot(gs[0, 1]); C = pd.read_csv(f'{OUT}/bl_all_sells_combined.csv'); c1 = C[C.tolerance_min == 1].set_index('model'); w = [R1['actual_share'][s] for s in ('scheduled', 'reactive', 'solo')]
a.barh(['scheduled', 'reactive', 'solo'], [w[0] * t.F1['scheduled'], w[1] * t.F1['reactive'], w[2] * t.F1['solo']], color='#2ca02c', label='reproduced (share × F1)'); a.barh(['scheduled', 'reactive', 'solo'], [w[0] * (1 - t.F1['scheduled']), w[1] * (1 - t.F1['reactive']), w[2] * (1 - t.F1['solo'])], left=[w[0] * t.F1['scheduled'], w[1] * t.F1['reactive'], w[2] * t.F1['solo']], color='#d62728', alpha=.6, label='not reproduced'); a.set_xlabel('share of all D-1 sold lots'); a.legend(fontsize=8); a.set_title(f"B. All three rules together: F1 {c1.F1['all three rules vs all D-1 sells']:.2f} (precision {c1.precision['all three rules vs all D-1 sells']:.2f}, recall {c1.recall['all three rules vs all D-1 sells']:.2f})")
a = fig.add_subplot(gs[1, :]); d = [x_ for x_ in CYC if x_['und'] == 'NIFTY' and x_['expiry'] == '2026-09-08'][0]; A = actual(d); Pd = preds(d)
ys = {('actual', 'scheduled'): 6, ('model', 'scheduled'): 5.5, ('actual', 'reactive'): 4, ('model', 'reactive'): 3.5, ('actual', 'solo'): 2, ('model', 'solo'): 1.5}; cols = {'scheduled': '#7f7f7f', 'reactive': '#d62728', 'solo': '#1f77b4'}
for (src, df) in (('actual', A), ('model', Pd)):
    for typ in ('scheduled', 'reactive', 'solo'):
        z = df[df.typ == typ]; a.scatter((33300 + 60 * z.j) / 3600, [ys[(src, typ)]] * len(z), marker='|', s=160, color=cols[typ], alpha=1 if src == 'actual' else .55)
a.set_yticks(list(ys.values())); a.set_yticklabels([f'{s} {t}' for s, t in ys]); a.set_xlim(9.25, 15.5); a.set_xticks(np.arange(9.5, 15.6, .5)); a.set_xticklabels([f'{int(h)}:{int(round((h % 1) * 60)):02d}' for h in np.arange(9.5, 15.6, .5)], fontsize=8); a.set_title('C. NIFTY D-1 2026-09-08: every real sold lot vs the three rules (one tick per lot, CE and PE together)')
plt.tight_layout(); plt.savefig(f'{FIG}/bl_all_sells.png', dpi=125); print('ok')
