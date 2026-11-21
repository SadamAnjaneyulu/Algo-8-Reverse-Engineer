"""Decoding figures: reports/figures/bl_dq_example_NIFTY.png, bl_dq_example_SENSEX.png (true 30-min candles, channel, machine breaks, real pairs) and bl_dq_summary.png (variants incl. placebos, error budget, first-entry capture, entries vs book delta)."""
import sys, os, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from bl_common import *
exec(open('bl_dq_final.py').read().split("rows = []\nfor nm, fn")[0])
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); ch = Chain()
def ex(und, e):
    d = [x for x in CYC if x['und'] == und and x['expiry'] == e][0]; fi = machv(d); K_ = np.array(ch.cyc(und, e)['strikes'], float)
    g = Pr[(Pr.und == und) & (Pr.expiry == e)]; rp = g[g.reactive]; fig, ax = plt.subplots(2, 1, figsize=(15, 9.5), sharex=True, gridspec_kw=dict(height_ratios=[3.4, 1])); a = ax[0]
    for b in range(33300 // 1800, 55800 // 1800):
        i0 = max(int(np.ceil((b * 1800 - 33300) / 60)), 0); i1 = min(int(np.ceil(((b + 1) * 1800 - 33300) / 60)), 375)
        if i1 - i0 < 1: continue
        o, h, l, c = d['o'][i0], d['h'][i0:i1].max(), d['l'][i0:i1].min(), d['c'][i1 - 1]; x0 = b * 1800 / 3600; col = '#2ca02c' if c >= o else '#d62728'
        a.add_patch(Rectangle((x0 + 0.05, min(o, c)), 0.4, max(abs(c - o), 0.5), color=col, alpha=.25)); a.vlines(x0 + 0.25, l, h, color=col, alpha=.5, lw=1); a.axvline(x0, color='#ccc', lw=.5, ls=':')
        i_a = max(int(np.ceil((b * 1800 - 3600 - 33300) / 60)), 0)
        if i1 > i0 and i0 - i_a >= 2 and b * 1800 >= 37800: a.hlines([d['h'][i_a:i0].max(), d['l'][i_a:i0].min()], x0, x0 + 0.5, color='#1f77b4', lw=1.6)
    xm = (33300 + 60 * np.arange(375)) / 3600; a.plot(xm, d['c'], color='#333', lw=.8)
    for f, s in fi: a.plot((33300 + 60 * f) / 3600, d['h'][f] if s > 0 else d['l'][f], 'x', color='k', ms=10, mew=2, zorder=6)
    for r in rp.itertuples():
        j = int((r.te - 33300) // 60)
        if j > 374: continue
        up = r.strike > K_[np.argmin(np.abs(K_ - d['c'][max(j - 1, 0)]))]; a.plot(r.te / 3600, d['h'][j] if up else d['l'][j], '^' if up else 'v', color='#d62728' if up else '#1f77b4', ms=9, zorder=5)
    a.plot([], [], color='#1f77b4', lw=1.6, label='high/low of the previous two 30-min candles (true highs/lows)'); a.plot([], [], 'x', color='k', mew=2, label='machine: first intrabar break, per side per candle'); a.plot([], [], '^', color='#d62728', label='real reactive pair (strike above ATM)'); a.plot([], [], 'v', color='#1f77b4', label='real reactive pair (strike below ATM)'); a.legend(fontsize=7, loc='lower left', ncol=2)
    a.axvspan(10.5, 15.25, color='#ffd54f', alpha=.06); a.set_ylabel('spot (30-min candles; line = 1-min close)'); a.set_title(f'{und} D-1 {e}: reactive pairs and the two-candle breakout (true one-minute highs/lows)')
    a = ax[1]; ev_ = [('real reactive pairs', rp.te.values / 3600, '#d62728'), ('machine breaks', (33300 + 60 * np.array([f for f, _ in fi])) / 3600, 'k'), ('scheduled pairs', g[g.sched].te.values / 3600, '#7f7f7f')]
    for i, (nm, tt, col) in enumerate(ev_): a.scatter(tt, [len(ev_) - i] * len(tt), marker='|', s=150, color=col)
    a.set_yticks(range(1, len(ev_) + 1)); a.set_yticklabels([n for n, _, _ in ev_][::-1], fontsize=8); a.set_ylim(.3, len(ev_) + .7); a.set_xlim(9.25, 15.5); a.set_xticks(np.arange(9.5, 15.6, .5)); a.set_xticklabels([f'{int(h)}:{int(round((h % 1) * 60)):02d}' for h in np.arange(9.5, 15.6, .5)], fontsize=8); a.set_xlabel('clock time (D-1)')
    plt.tight_layout(); plt.savefig(f'{FIG}/bl_dq_example_{und}.png', dpi=125); plt.close()
ex('NIFTY', '2026-09-08'); ex('SENSEX', '2026-10-22')
T = pd.read_csv(f'{OUT}/bl_dq_final.csv'); B = pd.read_csv(f'{OUT}/bl_dq_error_budget.csv'); S7 = json.load(open(f'{OUT}/bl_summary_dq7.json')); G = pd.read_csv(f'{OUT}/bl_dq_gate_first_rows.csv'); C8 = json.load(open(f'{OUT}/bl_summary_dq8.json'))
fig, ax = plt.subplots(2, 2, figsize=(14, 9.5)); a = ax[0, 0]; t = T.iloc[::-1]; cols = ['#d62728' if m.startswith('FINAL') else ('#bbbbbb' if 'placebo' in m else '#7f7f7f') for m in t.machine]; a.barh(range(len(t)), t.F1, color=cols); a.set_yticks(range(len(t))); a.set_yticklabels([m[:60] for m in t.machine], fontsize=7); a.set_xlim(0, 1); a.set_xlabel('F1 (±1 minute), all reactive pair-minutes 10:30-15:29')
for i, v in enumerate(t.F1): a.text(v + .01, i, f'{v:.2f}', va='center', fontsize=7)
a.set_title('A. True highs/lows + clock-aligned candles; placebos fail')
a = ax[0, 1]; bb = B.iloc[:6]; a.bar(range(len(bb)), bb['count'], color=['#555', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#d62728']); a.set_xticks(range(len(bb))); a.set_xticklabels(['all real\npair-minutes', 'matched', 'repeat inside\nthe candle', 'after 15:15', 'first entry,\ntiming off', 'no machine\nbreak'], fontsize=8)
for i, v in enumerate(bb['count']): a.text(i, v + 2, int(v), ha='center', fontsize=8)
a.set_title('B. Error budget: what is left is mostly repeat entries')
a = ax[1, 0]; fe = S7['first_entry']; vals = [fe['exact_share'], fe['capture'] - fe['exact_share'], 1 - fe['capture']]; a.bar([0], [vals[0]], color='#2ca02c', label='exact minute'); a.bar([0], [vals[1]], bottom=[vals[0]], color='#98df8a', label='±1 minute'); a.bar([0], [vals[2]], bottom=[vals[0] + vals[1]], color='#d62728', label='missed'); a.set_xticks([]); a.set_ylim(0, 1); a.legend(fontsize=8, loc='lower right')
a.text(0, vals[0] / 2, f"{100 * vals[0]:.0f}% exact minute", ha='center', color='w', fontsize=10); a.text(0, vals[0] + vals[1] / 2, f"+{100 * vals[1]:.0f}% ±1 min", ha='center', fontsize=9); a.set_title(f"C. First entry of each candle-side: {100 * fe['capture']:.0f}% reproduced ({fe['candle_sides_with_real_entry']} candle-sides)"); a.set_xlim(-1.5, 1.5)
a = ax[1, 1]; cnt = [];  
F = pd.read_csv(f'{OUT}/bl_dq_gate_first_rows.csv'); cnt = []
for d in CYC:
    A = sorted(d['Afull'])
    for f, s in machine(d): b = (33300 + 60 * f) // 1800; cnt.append(sum(1 for a_ in A if (33300 + 60 * a_) // 1800 == b and a_ >= f - 1))
F['n'] = cnt[:len(F)]; G = F[F.y == 1]; grp = G.groupby(G.n.clip(upper=3)).delta_vs_side.apply(list)
a.boxplot([grp.get(1, []), grp.get(2, []), grp.get(3, [])], tick_labels=['1', '2', '3+']); a.axhline(0, color='k', lw=.6); a.set_xlabel('real entries in the candle-side'); a.set_ylabel('book delta against the move at the first break (lots)'); a.set_title('D. More entries when the book is already short the move (ρ = 0.26)')
plt.tight_layout(); plt.savefig(f'{FIG}/bl_dq_summary.png', dpi=130); print('ok')
