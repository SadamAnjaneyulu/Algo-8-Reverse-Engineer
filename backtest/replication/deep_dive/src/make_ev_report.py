"""Builds reports/BUYBACK_EVENTS.md and figures/bl_ev_summary.png from bl_ev_*.csv and bl_summary_ev1.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); C = pd.read_csv(f'{OUT}/bl_ev_classes.csv'); OV = pd.read_csv(f'{OUT}/bl_ev_overall.csv'); FT = pd.read_csv(f'{OUT}/bl_ev_fit.csv')
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
g = lambda mode, var, cls, col='F1': float(C[(C['mode'] == mode) & (C.variant == f'{var} ({mode})') & (C.cls == cls)][col].iloc[0])
gov = lambda mode, var, col='F1': float(OV[(OV['mode'] == mode) & (OV.variant == f'{var} ({mode})')][col].iloc[0])
PL, EV = 'plain stop (reference)', 'rebalancing events'; cls = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'lump']
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8)); x = np.arange(len(cls))
for k, (mode, ttl) in enumerate((('tf_bb', 'on the real sells'), ('free', 'free-running'))):
    a = [g(mode, PL, c_) for c_ in cls]; b = [g(mode, EV, c_) for c_ in cls]
    ax[k].bar(x - .2, a, .4, color='#a0aec0', label=f'plain stop (overall {gov(mode, PL):.3f})'); ax[k].bar(x + .2, b, .4, color='#2b6cb0', label=f'rebalancing events (overall {gov(mode, EV):.3f})')
    ax[k].set_xticks(x); ax[k].set_xticklabels(cls, fontsize=8); ax[k].set_ylim(0, 1.05); ax[k].legend(fontsize=8); ax[k].set_title(f'D-1 lot F1 by class — {ttl} (out-of-fold)')
    if mode == 'tf_bb': ax[k].text(0, 1.01, 'real sells = input', ha='center', fontsize=7)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_ev_summary.png'), dpi=130)
rows = []
for mode in ('tf_bb', 'free'):
    for var in (PL, EV):
        rows.append([{'tf_bb': 'real sells', 'free': 'free-running'}[mode], var, f"{g(mode, var, 'body_buyback'):.3f}", f"{g(mode, var, 'body_buyback', 'precision'):.3f}", f"{g(mode, var, 'body_buyback', 'recall'):.3f}", f"{g(mode, var, 'wing_sell'):.3f}", f"{g(mode, var, 'body_sell'):.3f}", f"{gov(mode, var):.3f}"])
T = pd.DataFrame(rows, columns=['mode', 'model', 'buy-back F1', 'buy-back precision', 'buy-back recall', 'wing-sell F1', 'body-sell F1', 'overall D-1 F1'])
ft = FT[FT.variant == EV].drop(columns='variant')
d_bb_tf = g('tf_bb', EV, 'body_buyback') - g('tf_bb', PL, 'body_buyback'); d_ov_fr = gov('free', EV) - gov('free', PL); d_bb_fr = g('free', EV, 'body_buyback') - g('free', PL, 'body_buyback')
verdict = 'improves' if (d_bb_tf > 0 and d_ov_fr > 0) else 'does not improve'
txt = f"""# Algo 8 — D-1 buy-backs modelled as rebalancing events: accuracy

*Plan `BUYBACK_EVENTS_PLAN.md`, written before running. In-sample, D-1 of 32 cycles. The event parts were chosen on one cycle half and scored on the other. Figure: `figures/bl_ev_summary.png`.*

## 0. Result: the event model {verdict} accuracy
* On the real sells, buy-back F1 {g('tf_bb', PL, 'body_buyback'):.3f} → **{g('tf_bb', EV, 'body_buyback'):.3f}** ({d_bb_tf:+.3f}).
* Free-running: buy-back F1 {g('free', PL, 'body_buyback'):.3f} → **{g('free', EV, 'body_buyback'):.3f}** ({d_bb_fr:+.3f}); overall D-1 F1 {gov('free', PL):.3f} → **{gov('free', EV):.3f}** ({d_ov_fr:+.3f}).
* Decision rule from the plan: the model counts as an improvement only if both the buy-back F1 on the real sells and the overall free-running F1 rise. **Verdict: {verdict}.**

## 1. Scores
{table(T)}

## 2. Event parts chosen (per fold)
{table(ft)}

## 3. Reading
* Parts chosen in both folds are reproducible rules; parts chosen in only one fold are not stable on 16 cycles.
* Lot-level accuracy is limited because a modelled event must fall in the same minute (±1) as the real one, on the same right, with the same number of lots. The decoded structure (who is exited with whom) is right more often than the exact minute.

## Evidence labels
Observed (executed, out-of-fold). In-sample: the event structure was found on the same 32 cycles (`BUYBACK_STOP3.md`).
"""
open(f'{RP}/BUYBACK_EVENTS.md', 'w').write(txt); print('ok', verdict)
