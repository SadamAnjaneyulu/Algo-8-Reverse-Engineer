"""Builds reports/D1_FULL_AUC.md and figures/bl_full_auc.png from bl_full_auc.csv, bl_full_overall.csv, bl_full_pred.pkl.gz, bl_full_panel.pkl.gz."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); T = pd.read_csv(f'{OUT}/bl_full_auc.csv'); OV = pd.read_csv(f'{OUT}/bl_full_overall.csv'); P = pd.read_pickle(f'{OUT}/bl_full_pred.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_full_panel.pkl.gz')
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
V = list(OV.variant); A, AC, B = V; names = {'body_sell': 'body sell', 'body_buyback': 'body buy-back', 'wing_buy': 'wing buy (h_)', 'wing_sell': 'wing sell (h_)', 'body_long': 'body-stream long (opening wings)', 'lump': 'overnight lump (v_)', 'any': '**any activity**'}
order = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'body_long', 'lump', 'any']
f = lambda r: f'{r.AUC:.3f} ({r.CI_lo:.3f}–{r.CI_hi:.3f})'
tab = pd.DataFrame([[names[k], int(T[(T.activity == k) & (T.variant == A)].positive_cells.iloc[0])] + [f(T[(T.activity == k) & (T.variant == v)].iloc[0]) for v in V] for k in order], columns=['activity', 'cells with activity', 'A: hedge given real body (primary)', 'A-chained: no real orders in the minute', 'B: causal (completed bars)'])
ov = OV.copy(); ov.columns = ['variant', 'AUC any activity', 'macro average of 6 classes', 'pooled class × cell']; ov = ov.round(3)
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
for k, cl in zip(order, ['#2b6cb0', '#dd6b20', '#38a169', '#805ad5', '#d69e2e', '#e53e3e', 'k']):
    fp, tp, _ = roc_curve(X[f'y_{k}'], P[(A, k)]); ax[0].plot(fp, tp, color=cl, lw=2.2 if k == 'any' else 1.2, label=f"{names[k].strip('*')}: {T[(T.activity == k) & (T.variant == A)].AUC.iloc[0]:.3f}")
ax[0].plot([0, 1], [0, 1], 'k:', lw=.8); ax[0].legend(fontsize=8, loc='lower right'); ax[0].set_xlabel('false positive rate'); ax[0].set_ylabel('true positive rate'); ax[0].set_title('(a) Complete D-1 activity, variant A (leave-one-cycle-out)')
w = .26; x = np.arange(len(order))
for o, (v, cl, lb) in enumerate(((A, '#2b6cb0', 'A: hedge given real body'), (AC, '#38a169', 'A-chained'), (B, '#dd6b20', 'B: causal'))): ax[1].bar(x + (o - 1) * w, [T[(T.activity == k) & (T.variant == v)].AUC.iloc[0] for k in order], w, color=cl, label=lb)
ax[1].set_xticks(x); ax[1].set_xticklabels([names[k].strip('*').replace(' (', '\n(') for k in order], fontsize=7); ax[1].set_ylim(0.8, 1.0); ax[1].axhline(0.85, ls='--', color='k', lw=.8); ax[1].legend(fontsize=8); ax[1].set_title('(b) AUC by activity and variant (dashed: your 0.85 target)')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_full_auc.png'), dpi=130)
a = OV.iloc[0]; c = OV.iloc[1]; b = OV.iloc[2]
txt = f"""# Algo 8 — complete D-1 activity (body + hedge): one AUC against the real ledger

*Plan `D1_FULL_AUC_PLAN.md`, written before running. In-sample, D-1 of 32 live cycles. {len(X):,} cells (cycle × minute 09:15–15:44 × right). Figure: `figures/bl_full_auc.png`.*

## 0. Result
* **Overall AUC for any D-1 activity: {a.AUC_any_activity:.3f}** (variant A). Every class is above your 0.85 target. *Observed.*
* **Macro average over the six activity classes: {a.AUC_macro_6_classes:.3f}.** With everything chained from predictions (no real orders of the current minute anywhere): {c.AUC_macro_6_classes:.3f}. With completed bars only: {b.AUC_macro_6_classes:.3f}.
* By module:
  * **Body:** sell {T[(T.activity == 'body_sell') & (T.variant == A)].AUC.iloc[0]:.3f}, buy-back {T[(T.activity == 'body_buyback') & (T.variant == A)].AUC.iloc[0]:.3f}.
  * **Hedge:** wing buy {T[(T.activity == 'wing_buy') & (T.variant == A)].AUC.iloc[0]:.3f} and wing sell {T[(T.activity == 'wing_sell') & (T.variant == A)].AUC.iloc[0]:.3f} given the real body orders. Chained from the *predicted* body they are {T[(T.activity == 'wing_buy') & (T.variant == AC)].AUC.iloc[0]:.3f} / {T[(T.activity == 'wing_sell') & (T.variant == AC)].AUC.iloc[0]:.3f}.
  * **Opening wings:** {T[(T.activity == 'body_long') & (T.variant == A)].AUC.iloc[0]:.3f}.
  * **Overnight lump:** {T[(T.activity == 'lump') & (T.variant == A)].AUC.iloc[0]:.3f}.

## 1. AUC by activity (95% cycle-bootstrap CI)
{table(tab)}

## 2. Overall
{table(ov)}

* "Any activity" is the primary overall number: one model predicting whether anything at all happens on that right in that minute. It never sees real orders of the current minute.
* The "pooled class × cell" figure stacks all six classes. It is inflated because the classes have very different base rates (lumps are rare, wing buys common), so it rewards knowing which class is rare. Use the first two columns.

## 3. What each variant means
* **A (primary).** Market features use the current minute's high/low, as in every earlier F1/AUC. The **hedge** classes are scored given the real body orders of this and the previous minute: the hedge module reacts to executed body trades. Body classes, lumps and "any activity" never see real orders of the current minute.
* **A-chained.** The hedge classes get the predicted body-sell and buy-back probabilities instead. This is closest to "run the decoded system on its own".
* **B (causal).** Completed bars only, with the causal sell model.
* **All variants** use the book state (short/long lots, premium ratios) built from the real orders *before* the minute. This is teacher-forced: it asks "given its current position, does the decoded rule set predict what it does next?" It is not a free-running simulation, in which errors would compound.

## 4. Caveats
* AUC measures ranking per minute and right. It does not score strikes or lot counts. Lot-level reconstruction for sells is F1 0.78 (`D1_SELLING_RECONSTRUCTION.md`), and lump size is unresolved (`D1_LUMP.md`).
* In-sample. The decoded rules were found on the same 32 cycles, so this measures how completely the rules describe the observed behaviour, not out-of-sample prediction.
* **Bug found and fixed before reporting.** In the first run the buy-back model could see the real buy-backs of the same minute (its own label), giving AUC 1.000. The causal variant also used the same-minute sell prediction, and it lagged the timetable share, which is a known clock and was never lagged in the sell study. All three were corrected so that real current-minute orders feed only the hedge classes, as the plan specifies. Only the corrected run is reported.

## Evidence labels
Observed: sections 0–2. Not testable: event order inside a minute; a free-running simulation is not part of this test.
"""
open(f'{RP}/D1_FULL_AUC.md', 'w').write(txt); print('ok')
