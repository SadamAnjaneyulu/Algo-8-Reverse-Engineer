"""Charts for the research report.  Plots EXISTING result files only (no new experiment, no re-computation of any metric).
python3 report/assets/make_charts.py  (run from the repository root)"""
import os
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(OUT))
plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150, 'savefig.bbox': 'tight'})
INK, BLUE, ORANGE, GREY = '#222222', '#2b6cb0', '#c05621', '#9aa5b1'

# Figure 1 - D-1 first-passage response (PR #3, first_passage_response_curve.csv, D-1 fresh)
fp = pd.read_csv(os.path.join(REPO, 'analysis/exit_engine/results/first_passage_response_curve.csv'))
x = fp[(fp.segment == 'D-1 fresh') & (fp.window_min == 1) & (fp.k.isin([1.45, 1.55, 1.6, 1.7, 1.8]))].sort_values('k')
fig, ax = plt.subplots(figsize=(6.2, 2.8)); w = 0.38; xs = np.arange(len(x))
ax.bar(xs - w / 2, 100 * x.any_exit, w, color=BLUE, label='any buy-back of the contract within 1 min (exit association)')
ax.bar(xs + w / 2, 100 * x.stop_consistent_exit, w, color=ORANGE, label='stop-consistent buy-back within 1 min')
for xi, n in zip(xs, x.n): ax.text(xi, 101, f'{int(n)} crossings', ha='center', va='bottom', fontsize=7, color=INK)
ax.set_xticks(xs); ax.set_xticklabels([f'{k:.2f}×' for k in x.k]); ax.set_ylim(0, 112); ax.set_ylabel('% of crossings')
ax.set_xlabel('minute high ÷ cheapest open entry (threshold k)'); ax.legend(frameon=False, fontsize=7, loc='upper center', bbox_to_anchor=(0.5, -0.24), ncol=2)
ax.set_title('D-1 fresh contracts: response after the premium first crosses k × entry (DEV + VAL)', fontsize=9)
fig.savefig(os.path.join(OUT, 'fig1_first_passage.png')); plt.close(fig)

# Figure 2 - exit-engine model TEST precision / recall (PR #3, exit_model_metrics.csv)
m = pd.read_csv(os.path.join(REPO, 'analysis/exit_engine/results/exit_model_metrics.csv'))
t = m[(m.split == 'TEST') & m.algorithm.isin(['lightgbm', 'catboost']) & m.recall.notna() & ~m.model.str.contains('top-1')].copy()
short = {'1 individual lot stop': 'lot stop', '1b any unscheduled buy-back (label-free)': 'any unscheduled', '2 side-level reduction': 'side-level', '3 basket-level reduction': 'basket',
         '4 clock-B contract selection (candidate-level)': 'Clock-B contract', '5 expiry-day carried-position exit (non-salvage, non-final)': 'D0 carried exit', '6 expiry-day salvage': 'salvage',
         '6b D0 in-profit unscheduled exit (profit-taking)': 'profit-taking', '7 re-entry (same-side sale within 60 s of a buy-back episode)': 're-entry', '8 final liquidation (D0 book-minute)': 'final liq. (15 events)'}
t['lab'] = t.model.map(short)
fig, ax = plt.subplots(figsize=(6.2, 3.6))
for alg, mk, col in (('lightgbm', 'o', BLUE), ('catboost', 's', ORANGE)):
    s = t[t.algorithm == alg]; ax.scatter(s.recall, s.precision, marker=mk, color=col, label=alg, s=26, zorder=3)
for _, r in t[t.algorithm == 'lightgbm'].iterrows(): ax.annotate(r.lab, (r.recall, r.precision), fontsize=6.5, xytext=(4, -9) if r.lab in ('any unscheduled', 'Clock-B contract') else (4, 3), textcoords='offset points', color=INK)
ax.axvline(0.8, color=GREY, ls='--', lw=0.8); ax.axhline(0.8, color=GREY, ls='--', lw=0.8); ax.fill_between([0.8, 1.02], 0.8, 1.02, color='#e6f4ea', zorder=0); ax.text(0.81, 0.97, 'target 80 / 80', fontsize=7, color='#2f7d32')
ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02); ax.set_xlabel('recall (TEST)'); ax.set_ylabel('precision (TEST)'); ax.legend(frameon=False, fontsize=7, loc='lower left')
ax.set_title('Exit-engine classifiers on TEST (PR #3; thresholds fixed on VAL): none reaches 80 / 80', fontsize=9)
fig.savefig(os.path.join(OUT, 'fig2_exit_models_test.png')); plt.close(fig)

# Figure 3 - recovered decision quote / lowest open entry at actual stop buy-backs (PR #5 phase 2, stop_ref_exit_ratio_quantiles.csv)
q = pd.read_csv(os.path.join(REPO, 'analysis/allocation/results/stop_ref_exit_ratio_quantiles.csv'))
q = q[(q.conv == 'cheap') & (q.pool == 'S') & (q.ref == 'cheapest open entry') & q.segment.isin(['D-1 fresh', 'D0 fresh', 'D0 carried'])]
order = [(s, sp) for s in ('D-1 fresh', 'D0 fresh', 'D0 carried') for sp in ('DEV', 'VAL', 'TEST')]
fig, ax = plt.subplots(figsize=(6.2, 3.0)); y = np.arange(len(order))[::-1]
for yi, (s, sp) in zip(y, order):
    r = q[(q.segment == s) & (q.split == sp)].iloc[0]
    ax.plot([r['5%'], r['95%']], [yi, yi], color=GREY, lw=1); ax.plot([r['25%'], r['75%']], [yi, yi], color=BLUE, lw=5, solid_capstyle='butt'); ax.plot(r['50%'], yi, 'o', color=INK, ms=3.5)
    ax.text(3.75, yi, f'n={int(r["count"])}', va='center', fontsize=7)
ax.axvline(1.5, color=ORANGE, ls='--', lw=0.9); ax.text(1.51, len(order) - 0.6, '1.5×', color=ORANGE, fontsize=7)
ax.set_yticks(y); ax.set_yticklabels([f'{s} · {sp}' for s, sp in order], fontsize=7); ax.set_xlim(0.8, 4.0)
ax.set_xlabel("algo's recovered decision quote ÷ lowest open entry (5–25–50–75–95 % quantiles)")
ax.set_title('Where actual stop buy-backs happen (PR #5 phase 2; cheapest-first convention)', fontsize=9)
fig.savefig(os.path.join(OUT, 'fig3_stop_quote_ratio.png')); plt.close(fig)

# Figure 4 - re-sale association vs time-shifted null (PR #5 phase 3, replacement_association_null.csv)
n = pd.read_csv(os.path.join(REPO, 'analysis/allocation/results/replacement_association_null.csv'))
groups = ['8 clock-B rebalance', '1 individual lot stop-loss', '4 basket-level reduction', '2 same-contract partial buy-back', '3 side-level reduction', '6 clock-based exit (clock B, no replacement)']
labels = ['Clock-B rebalance', 'lot stop', 'basket', 'partial', 'side-level', 'Clock-B no replacement']
wins = ['0-30 s', '30-60 s', '1-5 min', '5-15 min', '> 15 min']
fig, ax = plt.subplots(figsize=(6.2, 3.0)); bw = 0.13
for i, (g, lab) in enumerate(zip(groups, labels)):
    v = [n[(n.reduction_group == g) & (n.window == w)].excess_ratio.iloc[0] for w in wins]
    ax.bar(np.arange(len(wins)) + (i - 2.5) * bw, v, bw, label=lab)
ax.axhline(1.0, color=INK, lw=0.8, ls='--'); ax.text(4.45, 1.05, 'null = 1', fontsize=7)
ax.set_xticks(range(len(wins))); ax.set_xticklabels(wins); ax.set_ylabel('observed ÷ null pairs'); ax.set_xlabel('time from buy-back to a same-right off-grid sale')
ax.legend(frameon=False, fontsize=6.5, ncol=3, loc='upper right'); ax.set_title('Re-sales follow buy-backs only within about one minute (PR #5 phase 3)', fontsize=9)
fig.savefig(os.path.join(OUT, 'fig4_resale_association.png')); plt.close(fig)

# Figure 5 - readiness matrix scores (audit/ALGO8_RECONSTRUCTION_READINESS.md; subjective index)
comp = [('Entry timing', .75), ('Initial position construction', .75), ('Initial quantity', .75), ('Cycle stops', .75), ('Execution and order handling', .75), ('Strike selection', .5),
        ('Final flattening', .5), ('Dynamic quantity', .25), ('Scheduled rebalancing', .25), ('Individual stops', .25), ('Clock B', .25), ('Re-entry and replacement', .25),
        ('Hedge adjustment', .25), ('Carry-forward logic', .25), ('Intermediate exits', 0), ('Side-level exits', 0), ('Basket-level exits', 0), ('Contract selection', 0), ('Expiry-day stops', 0)]
fig, ax = plt.subplots(figsize=(6.2, 3.6)); y = np.arange(len(comp))[::-1]
ax.barh(y, [c[1] for c in comp], color=[BLUE if c[1] >= .5 else (ORANGE if c[1] > 0 else GREY) for c in comp], height=0.65)
for yi, c in zip(y, comp): ax.text(c[1] + 0.01, yi, f'{c[1]:.2f}', va='center', fontsize=7)
ax.set_yticks(y); ax.set_yticklabels([c[0] for c in comp], fontsize=7); ax.set_xlim(0, 1.0); ax.set_xticks([0, .25, .5, .75, 1.0])
ax.set_xticklabels(['not possible', 'approx – low', 'approx', 'approx – high', 'exact'], fontsize=7)
ax.set_title('Reconstruction readiness by component (PR #4; mean 6.5 / 19 = 34 %, none exact)', fontsize=9)
fig.savefig(os.path.join(OUT, 'fig5_readiness.png')); plt.close(fig)
print('charts written to', OUT)
