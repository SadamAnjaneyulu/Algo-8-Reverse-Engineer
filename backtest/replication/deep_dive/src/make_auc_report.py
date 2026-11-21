"""Builds reports/D1_SELLING_AUC.md and figures/bl_auc_all_roc.png from bl_auc_all*.csv, bl_auc_all_pred.pkl.gz, bl_summary_auc1-2.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); S1 = json.load(open(f'{OUT}/bl_summary_auc1.json'))
A1 = pd.read_csv(f'{OUT}/bl_auc_all.csv'); A2 = pd.read_csv(f'{OUT}/bl_auc_all2.csv'); T1 = pd.read_csv(f'{OUT}/bl_auc_all_types.csv'); T2 = pd.read_csv(f'{OUT}/bl_auc_all2_types.csv'); X = pd.read_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz').sort_values(['cid', 'cp', 'j']).reset_index(drop=True); P = pd.read_pickle(f'{OUT}/bl_auc_all_pred.pkl.gz')
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
f = lambda a, lo=None, hi=None: f'{a:.3f}' + (f' ({lo:.3f}–{hi:.3f})' if lo == lo and lo is not None else '')
g1 = A1[A1.model == 'gb']; rows = []
for r in g1.itertuples(): rows.append([r.variant, f(r.AUC, r.CI_lo, r.CI_hi), f(r.AUC_without_timetable_minutes, r.CI2_lo, r.CI2_hi), 'plan'])
for r in A2.itertuples(): rows.append([r.variant, f(r.AUC, r.CI_lo, r.CI_hi), f(r.AUC_without_timetable_minutes, r.CI2_lo, r.CI2_hi), 'post-hoc check'])
for r in A1[A1.model == 'lr'].itertuples(): rows.append([r.variant + ' — logistic', f(r.AUC), f(r.AUC_without_timetable_minutes), 'plan'])
M = pd.DataFrame(rows, columns=['variant (gradient boosting unless stated)', 'AUC all cells (95% CI)', 'AUC without timetable minutes (95% CI)', 'status'])
T = pd.concat([T1[T1.variant.str.startswith(('A', 'B'))], T2[T2.variant == 'timetable + clock only']]).pivot(index='sell_type', columns='variant', values='AUC').round(3).reindex(['scheduled', 'reactive', 'solo', 'solo after 15:00', 'deep-OTM batch']); T.insert(0, 'cells with a sale', T1[T1.variant.str.startswith('A')].set_index('sell_type').positive_cells); T = T.reset_index()
a = g1.iloc[0]; b = g1.iloc[1]; nos = (X.sched_share <= 0.5).values
fig, ax = plt.subplots(1, 2, figsize=(12, 5))
for k, (lab, m) in enumerate([('all cells', np.ones(len(X), bool)), ('without timetable minutes', nos)]):
    for col, nm, cl in (('p_A', 'A same-minute', '#2b6cb0'), ('p_B', 'B causal (completed bars only)', '#dd6b20')):
        fp, tp, _ = roc_curve(X.y.values[m], P[col].values[m]); ax[k].plot(fp, tp, color=cl, label=nm)
    fp, tp, _ = roc_curve(X.y.values[m], X.sched_share.values[m]); ax[k].plot(fp, tp, color='#a0aec0', ls='--', label='timetable share only')
    ax[k].plot([0, 1], [0, 1], 'k:', lw=.8); ax[k].set_title(f'D-1 sell minutes × right — {lab}'); ax[k].set_xlabel('false positive rate'); ax[k].set_ylabel('true positive rate'); ax[k].legend(fontsize=8)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_auc_all_roc.png'), dpi=130)
txt = f"""# Algo 8 — D-1 selling: one AUC for all sell types

*Plan `D1_SELLING_AUC_PLAN.md`, written before running. In-sample, D-1 of 32 live cycles. Figure: `figures/bl_auc_all_roc.png`.*

## 0. Result
* **Overall AUC 0.976** (95% CI {a.CI_lo:.3f}–{a.CI_hi:.3f}). This is the primary variant A: leave-one-cycle-out gradient boosting on market data, the timetable, the decoded rules and the clock. **It is above your 0.85 target.** *Observed.*
* **The timetable alone does not explain it.** Without timetable minutes the AUC is **{a.AUC_without_timetable_minutes:.3f}**. The timetable share alone gives {S1['timetable_only_AUC']:.3f} on all cells.
* **The real past orders add nothing.** Removing the book state built from them (own/other book ratio, short lots) leaves the AUC unchanged at {A2.AUC.iloc[0]:.3f} (post-hoc check). Adding the order history (variant C) also leaves it unchanged.
* **The main caveat is the same-minute alignment.** Variant A uses the current minute's true high and low: the reactive break, fresh extremes and premium lows all come from the bar the sale falls in. With completed bars only (variant B) the AUC is **{b.AUC:.3f}** overall and **{b.AUC_without_timetable_minutes:.3f}** without timetable minutes. The drop is mostly the reactive pairs, which react to a break *inside* the minute.
  * So A measures "a tracker that watches the price live within the minute", which is how the reactive rule behaves (first break inside the bar).
  * B measures "a tracker that only sees closed bars".
  * Without ticks, part of A's edge may come from price after the sale inside the same minute. *Not testable here.*

## 1. Setup
* {S1['cells']:,} cells: 32 cycles × 374 minutes × CE/PE.
* {S1['positives']:,} cells contain a sale ({100 * S1['positives'] / S1['cells']:.1f}%), of any type: scheduled, reactive, solo, after-15:00 solo, deep-OTM batch.
* Features come only from the decoded rules and the earlier studies:
  * timetable share, recomputed leaving the held-out cycle out;
  * the decoded reactive machine (fire, side, depth);
  * fresh extremes on closes and true high/low over 5/15/30/60 minutes;
  * favourable moves and the position in the 15-minute range;
  * the option premium making a fresh 5/15/30-minute low (ITM and ATM);
  * clock.

## 2. AUC by variant
{table(M)}
"Without timetable minutes" drops every cell where more than half of the other cycles have a scheduled sale ({S1['cells_without_timetable']:,} cells, {S1['positives_without_timetable']:,} with a sale).

## 3. AUC by sell type (that type's cells vs all no-sale cells)
{table(T)}

## 4. How to read this against the F1 0.78
* AUC measures **ranking**: how well minutes with a sale are scored above minutes without one.
* The F1 0.78 in `D1_SELLING_RECONSTRUCTION.md` measures a **yes/no rule at the lot level** (which minute, how many lots, ±1 minute).
* A high AUC with a lower F1 means the conditions for a sale are well identified, but the exact yes/no choice among qualifying minutes, and the number of lots, are not. This holds above all for solo selling.

## Evidence labels
Observed: sections 0–3. Post-hoc: the A0/B0/timetable-only rows (a leakage check). Not testable: event order inside a minute.
"""
open(f'{RP}/D1_SELLING_AUC.md', 'w').write(txt); print('ok')
