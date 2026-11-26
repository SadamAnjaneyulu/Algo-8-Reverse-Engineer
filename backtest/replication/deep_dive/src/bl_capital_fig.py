"""Figure for the capital-loss study -> reports/figures/bl_capital_logic.png (D-1)."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); os.makedirs(FIG, exist_ok=True)
H = pd.read_csv(f'{OUT}/bl_book_hazard.csv'); S = pd.read_csv(f'{OUT}/bl_book_lotshape.csv'); G = pd.read_csv(f'{OUT}/bl_book_gb.csv'); W = pd.read_csv(f'{OUT}/bl_book_window_auc.csv'); GL = pd.read_csv(f'{OUT}/bl_book_lot_gb.csv')
fig, ax = plt.subplots(2, 2, figsize=(13, 9))
a = ax[0, 0]; h = H[(H.day == 'D-1') & (H['var'] == 'B_total') & (H.target == 'B')].reset_index(drop=True); lab = ['≤ -1.0', '-1.0 to -0.5', '-0.5 to -0.25', '-0.25 to 0', '0 to 0.25', '0.25 to 0.5', '0.5 to 1.0', '> 1.0']
order = ['(-1000000000.0, -1.0]', '(-1.0, -0.5]', '(-0.5, -0.25]', '(-0.25, 0.0]', '(0.0, 0.25]', '(0.25, 0.5]', '(0.5, 1.0]', '(1.0, 1000000000.0]']; h = h.set_index('bin').loc[order]
a.bar(range(8), h.per1000, color='#7f7f7f'); a.set_xticks(range(8)); a.set_xticklabels(lab, rotation=40, fontsize=8); a.set_xlabel('cumulative book P&L, ₹ lakh (₹2 crore = 200 lakh)'); a.set_ylabel('residual buy-backs per 1000 cycle-minutes'); a.set_title('A. Book P&L level: higher when losing, but no single step')
for i, (n, e) in enumerate(zip(h.n, h.ev)): a.text(i, h.per1000.iloc[i] + 1, f'{int(e)}/{int(n)}', ha='center', fontsize=7)
a = ax[0, 1]; s = S[(S['var'] == 'lot_pct3') & (S.target == 'yB')]; order = s[s.subset == 'all'].bin.tolist(); lab = ['≤ -2', '-2 to -0.5', '-0.5 to 0', '0 to 1', '1 to 2', '2 to 3', '3 to 5', '5 to 8', '> 8']
for sub, col in (('all', 'k'), ('first half', '#1f77b4'), ('second half', '#d62728')): t = s[s.subset == sub].set_index('bin').loc[order]; a.plot(range(len(order)), t.per1000, 'o-', color=col, label=sub)
a.set_xticks(range(len(order))); a.set_xticklabels(lab, rotation=40, fontsize=8); a.set_xlabel("lot's own premium change over the last 3 min (%)"); a.set_ylabel('residual buy-backs per 1000 contract-minutes'); a.set_title('B. Fast premium RISE: graded, replicates in both halves'); a.legend(fontsize=8)
a = ax[1, 0]; w = W[(W.day == 'D-1') & (W.target == 'B') & W.variable.str.match(r'own\d+$')].copy(); w['m'] = w.variable.str[3:].astype(int); w = w.sort_values('m'); xs = np.arange(len(w)); a.errorbar(xs, 1 - w.AUC, yerr=[w.AUC - w.lo, w.hi - w.AUC], fmt='o-', color='#2ca02c', capsize=3); a.axhline(.5, color='k', ls=':'); a.set_xticks(xs); a.set_xticklabels(w.m.tolist()); a.set_xlabel('look-back window (min)'); a.set_ylabel('AUC (loss on own right → buy-back)'); a.set_title('C. The effect lives in the last few minutes, not in accumulated loss')
a = ax[1, 1]; g = GL[GL.target == 'B'].set_index('model').LOCO_AUC; gb = G[(G.day == 'D-1') & (G.target == 'B')].iloc[0]; labs = ['12 earlier\nvariables', '+ book P&L\n(level, DD, ΔB)', '+ lot / underlying\nshort-horizon', '+ book mark-only\nchanges', '+ both']; vals = [gb.baseline, gb.plus_book, g['+ lot/underlying short-horizon'], g['+ book mark-only'], g['+ both']]
a.bar(range(5), vals, color=['#7f7f7f', '#ff7f0e', '#2ca02c', '#9467bd', '#1f77b4']); a.set_ylim(.6, .9); a.set_xticks(range(5)); a.set_xticklabels(labs, fontsize=8); a.set_ylabel('leave-one-cycle-out AUC'); a.set_title('D. Residual buy-backs: what adds predictive power')
for i, v in enumerate(vals): a.text(i, v + .004, f'{v:.3f}', ha='center', fontsize=8)
fig.suptitle('Algo 8 D-1 sub-1.2× buy-backs: capital-loss hypothesis vs short-horizon adverse move — in-sample, 31 cycles', fontsize=11); fig.tight_layout(); fig.savefig(f'{FIG}/bl_capital_logic.png', dpi=140); print('saved')
