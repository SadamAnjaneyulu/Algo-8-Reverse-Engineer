"""Compact charts for the 6-page Rahul report.  Plots EXISTING result files only (no new experiment).  Run from the repository root:
python3 report/assets/make_compact_charts.py"""
import os
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(OUT))
plt.rcParams.update({'font.size': 6.8, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 220, 'savefig.bbox': 'tight', 'axes.linewidth': 0.6,
                     'xtick.major.width': 0.5, 'ytick.major.width': 0.5, 'font.family': 'DejaVu Sans'})
INK, BLUE, ORANGE, GREY = '#222222', '#2b6cb0', '#c05621', '#9aa5b1'

# A - D-1 first passage (PR #3 first_passage_response_curve.csv)
fp = pd.read_csv(os.path.join(REPO, 'analysis/exit_engine/results/first_passage_response_curve.csv'))
x = fp[(fp.segment == 'D-1 fresh') & (fp.window_min == 1) & fp.k.isin([1.45, 1.55, 1.6, 1.7, 1.8])].sort_values('k')
fig, ax = plt.subplots(figsize=(3.55, 2.05)); xs = np.arange(len(x)); w = 0.38
ax.bar(xs - w / 2, 100 * x.any_exit, w, color=BLUE, label='any buy-back of the contract ≤ 1 min')
ax.bar(xs + w / 2, 100 * x.stop_consistent_exit, w, color=ORANGE, label='stop-consistent buy-back ≤ 1 min')
ax.set_xticks(xs); ax.set_xticklabels([f'{k:.2f}×\nn={int(n)}' for k, n in zip(x.k, x.n)]); ax.set_ylim(0, 112); ax.set_ylabel('% of crossings'); ax.set_xlabel('minute high ÷ cheapest open entry (k)')
ax.legend(frameon=False, fontsize=5.8, loc='upper left', bbox_to_anchor=(0, 1.02)); ax.set_title('D-1 fresh contracts: response after first crossing k × entry', fontsize=7)
fig.savefig(os.path.join(OUT, 'c_first_passage.png')); plt.close(fig)

# B - exit-engine classifiers TEST precision / recall, LightGBM (PR #3 exit_model_metrics.csv)
m = pd.read_csv(os.path.join(REPO, 'analysis/exit_engine/results/exit_model_metrics.csv'))
t = m[(m.split == 'TEST') & (m.algorithm == 'lightgbm') & m.recall.notna() & ~m.model.str.contains('top-1')].copy()
short = {'1 individual lot stop': 'Lot stop', '1b any unscheduled buy-back (label-free)': 'Any unscheduled exit', '2 side-level reduction': 'Side-level',
         '3 basket-level reduction': 'Basket', '4 clock-B contract selection (candidate-level)': 'Clock-B contract', '5 expiry-day carried-position exit (non-salvage, non-final)': 'D0 carried exit',
         '6 expiry-day salvage': 'Salvage', '6b D0 in-profit unscheduled exit (profit-taking)': 'Profit-taking', '7 re-entry (same-side sale within 60 s of a buy-back episode)': 'Re-entry',
         '8 final liquidation (D0 book-minute)': 'Final liquidation (15 events)'}
t['lab'] = t.model.map(short); t = t.sort_values('precision')
fig, ax = plt.subplots(figsize=(3.55, 2.05)); y = np.arange(len(t)); h = 0.38
ax.barh(y + h / 2, t.precision, h, color=BLUE, label='precision'); ax.barh(y - h / 2, t.recall, h, color=ORANGE, label='recall')
ax.axvline(0.8, color=INK, ls='--', lw=0.6); ax.text(0.81, len(t) - 0.4, '80 %', fontsize=5.8, va='bottom')
ax.set_yticks(y); ax.set_yticklabels(t.lab, fontsize=5.9); ax.set_xlim(0, 1.05); ax.set_xlabel('TEST (LightGBM; threshold fixed on VAL)')
ax.legend(frameon=False, fontsize=5.8, loc='center right', bbox_to_anchor=(1.02, 0.42)); ax.set_title('PR #3 exit classifiers: none reaches 80 / 80', fontsize=7)
fig.savefig(os.path.join(OUT, 'c_exit_models.png')); plt.close(fig)

# C - re-sale association vs time-shifted null (PR #5 replacement_association_null.csv)
n = pd.read_csv(os.path.join(REPO, 'analysis/allocation/results/replacement_association_null.csv'))
groups = [('8 clock-B rebalance', 'Clock-B rebalance'), ('1 individual lot stop-loss', 'Lot stop'), ('4 basket-level reduction', 'Basket'), ('3 side-level reduction', 'Side-level')]
wins = ['0-30 s', '30-60 s', '1-5 min', '5-15 min']
fig, ax = plt.subplots(figsize=(3.55, 1.85)); bw = 0.2
for i, (g, lab) in enumerate(groups):
    v = [n[(n.reduction_group == g) & (n.window == w)].excess_ratio.iloc[0] for w in wins]; ax.bar(np.arange(len(wins)) + (i - 1.5) * bw, v, bw, label=lab, color=[BLUE, ORANGE, '#2f855a', GREY][i])
ax.axhline(1.0, color=INK, lw=0.6, ls='--'); ax.set_xticks(range(len(wins))); ax.set_xticklabels(wins); ax.set_ylabel('observed ÷ null'); ax.set_xlabel('time from buy-back to same-right off-grid sale')
ax.legend(frameon=False, fontsize=5.8, ncol=2, loc='upper right'); ax.set_title('Re-sales follow buy-backs only within about a minute', fontsize=7)
fig.savefig(os.path.join(OUT, 'c_resale.png')); plt.close(fig)
print('ok')

# D - readiness by level (audit/ALGO8_RECONSTRUCTION_READINESS.md; subjective, unweighted)
levels = [('Exact (1.0)', [], '#2f855a'),
          ('Approx – high (0.75)', ['Entry timing', 'Initial position', 'Initial quantity', 'Cycle stop', 'Order handling'], BLUE),
          ('Approx (0.5)', ['Strike choice', 'Final flatten'], '#4a90b8'),
          ('Approx – low (0.25)', ['Dynamic quantity', 'Scheduled rebalance', 'Individual stops', 'Clock B', 'Re-entry / replacement', 'Hedge adjustment', 'Carry-forward'], ORANGE),
          ('Not possible yet (0)', ['Intermediate exits', 'Side-level exits', 'Basket exits', 'Contract selection', 'Expiry-day stops'], GREY)]
fig, ax = plt.subplots(figsize=(7.2, 1.12)); left = 0
for lab, items, col in levels:
    w = max(len(items), 0)
    if w == 0:
        ax.text(-2.1, 0.0, 'Exact\n(1.0): 0', ha='left', va='center', fontsize=6.5, color='#2f855a', fontweight='bold'); continue
    ax.barh(0, w, left=left, color=col, edgecolor='white', height=0.9)
    ax.text(left + w / 2, 0.22, (lab.replace(' (', '\n(') if w < 4 else lab) + f': {w}', ha='center', va='center', color='white', fontsize=6.0, fontweight='bold', linespacing=1.05)
    import textwrap
    ax.text(left + w / 2, -0.2, textwrap.fill(' · '.join(items), 30 if w > 4 else 14), ha='center', va='center', color='white', fontsize=5.6, linespacing=1.1)
    left += w
ax.set_xlim(-2.2, 19); ax.set_ylim(-0.5, 0.5); ax.axis('off')
ax.set_title('Reconstruction readiness: 19 components, none exact (index 6.5 / 19 = 34 %, a subjective unweighted score)', fontsize=7, loc='left')
fig.savefig(os.path.join(OUT, 'c_readiness.png')); plt.close(fig)
print('ok2')
