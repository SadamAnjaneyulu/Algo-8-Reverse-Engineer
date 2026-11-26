"""Builds reports/D1_ACCURACY_PUSH.md and figures/bl_push_summary.png: the learned-policy results (bl_ml_fit.csv, bl_summary_ml2.json) and a scoreboard of every accuracy attempt on the D-1 reconstruction."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json'))
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
ML = pd.read_csv(f'{OUT}/bl_ml_fit.csv'); P2 = pd.read_csv(f'{OUT}/bl_push2.csv'); LF = pd.read_csv(f'{OUT}/bl_lots_fit.csv'); FW = pd.read_csv(f'{OUT}/bl_fwd.csv'); EV = pd.read_csv(f'{OUT}/bl_ev_overall.csv'); O1 = pd.read_csv(f'{OUT}/bl_fr_overall.csv'); O2 = pd.read_csv(f'{OUT}/bl_fr2_overall.csv').iloc[0]; RP1 = J('rep1'); BS5 = J('bs5'); M2 = J('ml2'); CE = pd.read_csv(f'{OUT}/bl_lots_ceiling.csv')
g = lambda df, s_, m: float(df[(df.setup == s_) & (df.model == m)].F1.iloc[0])
OOF, A, B = 'out-of-fold halves', 'A same version (V1 14->7, V2 7->4)', 'B version change (train V1, test V2)'
base = (float(O1.F1.iloc[0]), g(ML, A, 'baseline'), g(ML, B, 'baseline'))
sc = [('Decoded rules (current simulator)', *base, 'kept'),
      ('Decoded buy-back stop design (minute high ~1.6x)', float(O2.F1), np.nan, np.nan, 'kept (equal)'),
      ('Reactive repeat entries', float(RP1['overall']['F1']), np.nan, np.nan, 'rejected (never chosen)'),
      ('Buy-back: premium AND breakout', float(pd.read_csv(f'{OUT}/bl_fr4_overall.csv').F1.iloc[0]), np.nan, np.nan, 'rejected'),
      ('Buy-back: premium stop OR market exit', float(BS5['free']['overall']['F1']), np.nan, np.nan, 'rejected'),
      ('Rebalancing events (cluster, partner, counter-sell, exits)', float(EV[(EV['mode'] == 'free') & EV.variant.str.startswith('rebal')].F1.iloc[0]), np.nan, np.nan, 'rejected (rule)'),
      ('Lot fixes (solo depth sizing, late rule, counter-sell)', g(LF, OOF, 'fixed'), g(LF, A, 'fixed'), g(LF, B, 'fixed'), 'rejected'),
      ('Learned solo-sell policy', g(ML, OOF, '+ sell policy'), g(ML, A, '+ sell policy'), g(ML, B, '+ sell policy'), 'rejected'),
      ('Learned buy-back policy', g(ML, OOF, '+ buy-back policy'), g(ML, A, '+ buy-back policy'), g(ML, B, '+ buy-back policy'), 'rejected'),
      ('Both learned policies', g(ML, OOF, '+ both policies'), g(ML, A, '+ both policies'), g(ML, B, '+ both policies'), 'rejected'),
      ('Opening-wing closes booked as body-stream closes', g(P2, OOF, '+ opening-wing close relabel'), g(P2, A, '+ opening-wing close relabel'), g(P2, B, '+ opening-wing close relabel'), 'rejected (neutral)'),
      ('Relabel + joint tuning of all simulator parameters', g(P2, OOF, '+ relabel + joint tuning'), g(P2, A, '+ relabel + joint tuning'), g(P2, B, '+ relabel + joint tuning'), 'rejected (overfits)')]
T = pd.DataFrame(sc, columns=['attempt', 'out-of-fold F1', 'unseen F1 (same version)', 'unseen F1 (version change)', 'decision'])
Tf = T.copy()
for c in T.columns[1:4]: Tf[c] = T[c].map(lambda v: '–' if v != v else f'{v:.3f}')
mlt = ML.copy(); mlt[['F1', 'precision', 'recall', 'F1_within1', 'F1_strict']] = mlt[['F1', 'precision', 'recall', 'F1_within1', 'F1_strict']].round(3)
fig, ax = plt.subplots(1, 2, figsize=(15, 5.2)); y = np.arange(len(T))[::-1]
ax[0].barh(y, T['out-of-fold F1'], color=np.where(T.decision.str.startswith('kept'), '#2b6cb0', '#a0aec0')); ax[0].axvline(base[0], color='k', ls='--', lw=.8); ax[0].set_yticks(y); ax[0].set_yticklabels(T.attempt, fontsize=8); ax[0].set_xlim(0.6, 0.72); ax[0].set_xlabel('overall D-1 lot F1, out-of-fold'); ax[0].set_title('(a) Every accuracy attempt vs the decoded rules (dashed)')
cl = CE.copy(); ax[1].bar(range(len(cl)), cl.F1, color=['#2b6cb0'] + ['#cbd5e0'] * (len(cl) - 1)); ax[1].set_xticks(range(len(cl))); ax[1].set_xticklabels(['now', '+ exact lot counts', '+ exact timing', '+ all events', '+ not-modelled'], fontsize=8); ax[1].set_ylim(0, 1.12); ax[1].set_ylabel('lot F1'); ax[1].set_title('(b) What the remaining gap is made of (oracle ceilings)')
for k, v in enumerate(cl.F1): ax[1].text(k, v + .015, f'{v:.2f}', ha='center')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_push_summary.png'), dpi=130)
txt = f"""# Algo 8 — pushing the D-1 reconstruction accuracy: everything tried, and where the limit is

*Plan for the learned policies: `D1_ML_PLAN.md`, written before running. In-sample, D-1 of 32 cycles. "Unseen" = forward splits of `D1_FORWARD.md`. Figure: `figures/bl_push_summary.png`.*

## 0. Result
* **Best reconstruction: the decoded rules.**
  * Lot-level F1 **{base[0]:.3f}** out-of-fold.
  * **{base[1]:.3f}** on unseen cycles of the same version, **{base[2]:.3f}** after a version change.
  * AUC on unseen cycles {FW.AUC_any_forward.iloc[0]:.2f} / {FW.AUC_any_forward.iloc[1]:.2f}.
  * Minute-cell activity F1 0.89 at ±1 minute.
* **Nothing tried beats it on unseen cycles.** This covers 11 attempts: stop-design variants, rebalancing events, quantity fixes, learned (gradient-boosting) policies for solo sells and buy-backs, booking the opening-wing closes as body-stream closes, and joint tuning of every simulator parameter against overall accuracy. Each was chosen on training cycles and validated out-of-fold and on unseen cycles. The best gain on any test is under +0.01, inside the noise, and none improves both out-of-fold and unseen.
* **The learned policies are informative but do not help the whole system.**
  * The solo-sell model ranks sell cells better than the decoded ladder: exact-minute cell F1 {M2['0.1']:.2f} vs {M2['ladder_rule']:.2f} on training cells.
  * In the full free-running simulation it places more lots, the hedge mirrors every extra sell, and overall precision falls as much as recall rises.
  * The learned buy-back policy is less precise than the simple intrabar stop.
* **Where the remaining gap is** (oracle ceilings):
  * exact lot counts at events already found would lift F1 **{CE.F1.iloc[0]:.2f} → {CE.F1.iloc[1]:.2f}**;
  * plus exact timing: {CE.F1.iloc[2]:.2f};
  * plus all events found: {CE.F1.iloc[3]:.2f}.
* **Why the limit is in the data, not the method.** The lot count and the exact minute are set inside the minute: solo lots are dripped over about 5 s, and stops fire on intrabar touches. One-minute bars cannot show this, whatever model is used.

## 1. Scoreboard (overall D-1 lot F1)
{table(Tf)}

## 2. Learned policies (detail)
{table(mlt)}

## 3. Round 2 (after "try again as hard as possible")
* **Opening-wing closes.** 93% of the real body-stream long closes are on the opening-wing contracts, and 81% come within 10 s of a buy-back. The simulator's outermost-first release does close those contracts, but at different moments: only about 24% match in time. Overall effect: neutral.
* **Joint coordinate-descent tuning** of all parameters against overall lot F1, two passes on the training cycles. It raises the training F1 by 0.005–0.018, but on unseen cycles it gains +0.001 (same version) and loses −0.010 (version change). That is overfitting to the training cycles. Rejected.

## 4. Reading for the PM
* **Decisions:** what the system does, when, and on which side is reproduced well. AUC is about 0.92 on unseen days, minute cells 0.89.
* **Execution detail:** how many lots and the exact minute is about 0.63 on unseen days.
* **With this data,** further modelling on the same 32 cycles mainly fits noise. Every extra layer tried in this pass lost out-of-sample.
* **Two ways forward:**
  1. One-second or tick option and spot data for the D-1 sessions. This addresses the +0.16–0.22 gap directly.
  2. More live cycles, for a true holdout and more sell and stop events to learn from.

## Evidence labels
Observed (executed, out-of-fold and forward). The learned-policy thresholds came from an inner cross-fit inside the training cycles.
"""
open(f'{RP}/D1_ACCURACY_PUSH.md', 'w').write(txt); print('ok')
