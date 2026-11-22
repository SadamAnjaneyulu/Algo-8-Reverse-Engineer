"""Builds reports/D0_FREE_RUN.md (chunk 5 + one-page D0 overview) and figures/bl_d0fr_summary.png from bl_d0_fr_*.csv, bl_d0_fr_params.json, bl_fwd.csv / bl_fr_overall.csv (D-1 reference) and the chunk 1-4 summaries."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda k: json.load(open(f'{OUT}/bl_summary_{k}.json'))
OV = pd.read_csv(f'{OUT}/bl_d0_fr_score.csv'); CL = pd.read_csv(f'{OUT}/bl_d0_fr_class.csv'); AU = pd.read_csv(f'{OUT}/bl_d0_fr_auc.csv'); ST = pd.read_csv(f'{OUT}/bl_d0_fr_stops.csv'); PAR = json.load(open(f'{OUT}/bl_d0_fr_params.json'))
FW = pd.read_csv(f'{OUT}/bl_fwd.csv'); FR = pd.read_csv(f'{OUT}/bl_fr_overall.csv'); d1_oof = float(FR[FR.variant == 'FR free-running (primary)'].F1.iloc[0]) if 'F1' in FR.columns else float('nan')
s4, s1, s2, b2, h1, x1 = J('d0s4'), J('d0s2'), J('d0b3'), J('d0b2'), J('d0h1'), J('d0x1')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
o = OV.set_index('split'); a = AU.set_index('split'); oof, fa, fb = 'OOF (cycle halves)', 'forward A (same version, later cycles)', 'forward B (train V1, test V2)'
fig, ax = plt.subplots(1, 3, figsize=(18, 5))
cp_ = CL.pivot(index='cls', columns='split', values='F1')[[oof, fa, fb]]; xx = np.arange(len(cp_))
for k, (sp, col) in enumerate(((oof, '#2b6cb0'), (fa, '#48bb78'), (fb, '#ed8936'))): ax[0].bar(xx + (k - 1) * .27, cp_[sp].values, .27, label=sp.split(' (')[0], color=col)
ax[0].set_xticks(xx); ax[0].set_xticklabels(cp_.index, fontsize=8); ax[0].legend(fontsize=8); ax[0].set_ylim(0, 1); ax[0].set_title('D0 free-running: lot F1 by class (minute ±1)', fontsize=10)
lab = ['D-1 out-of-fold', 'D-1 unseen A', 'D-1 unseen B', 'D0 out-of-fold', 'D0 unseen A', 'D0 unseen B']; f1s = [d1_oof, FW.F1_forward.iloc[0], FW.F1_forward.iloc[1], o.loc[oof, 'F1'], o.loc[fa, 'F1'], o.loc[fb, 'F1']]
aus = [float(FW.AUC_any_out_of_fold_same_cycles.iloc[0]), FW.AUC_any_forward.iloc[0], FW.AUC_any_forward.iloc[1], a.loc[oof, 'AUC_model'], a.loc[fa, 'AUC_model'], a.loc[fb, 'AUC_model']]
ax[1].bar(range(6), f1s, color=['#a0aec0'] * 3 + ['#2b6cb0'] * 3)
for k, v in enumerate(f1s): ax[1].text(k, v + .01, f'{v:.2f}', ha='center')
ax[1].set_xticks(range(6)); ax[1].set_xticklabels(lab, fontsize=8, rotation=20); ax[1].set_ylim(0, 1); ax[1].set_title('Lot F1, all modelled classes: D-1 vs D0', fontsize=10)
ax[2].bar(range(6), aus, color=['#a0aec0'] * 3 + ['#2b6cb0'] * 3)
for k, v in enumerate(aus): ax[2].text(k, v + .005, f'{v:.3f}', ha='center')
ax[2].set_xticks(range(6)); ax[2].set_xticklabels(lab, fontsize=8, rotation=20); ax[2].set_ylim(.5, 1); ax[2].set_title('Any-activity AUC: D-1 vs D0', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0fr_summary.png'), dpi=130)
sg = ST.groupby(['split', 'agree']).size().unstack(fill_value=0)
wv = s1['waves_all']; byc = CL[CL.split == oof].set_index('cls')
txt = f"""# Algo 8 — D0 chunk 5: free-running reconstruction, and D0 overview

*Plan `D0_FREE_RUN_PLAN.md`, written before the tests. In-sample: D0 of the 30 cycles with both logs. The simulator starts from the real book carried from D-1. Every fitted part is refit on the training cycles of each split. Figure: `figures/bl_d0fr_summary.png`.*

## 0. Result
* **How accurately D0 is reconstructed:**

| split | cycles | lot F1 | precision | recall | F1, exact strike | null (+15 min) | AUC any activity (95% CI) |
|---|---|---|---|---|---|---|---|
| out-of-fold (cycle halves) | {int(o.loc[oof, 'cycles'])} | **{o.loc[oof, 'F1']:.3f}** | {o.loc[oof, 'precision']:.3f} | {o.loc[oof, 'recall']:.3f} | {o.loc[oof, 'F1_strict']:.3f} | {o.loc[oof, 'null_shift15_F1']:.3f} | **{a.loc[oof, 'AUC_model']:.3f}** ({a.loc[oof, 'ci_lo']:.3f}–{a.loc[oof, 'ci_hi']:.3f}) |
| unseen A: same version, later cycles | {int(o.loc[fa, 'cycles'])} | **{o.loc[fa, 'F1']:.3f}** | {o.loc[fa, 'precision']:.3f} | {o.loc[fa, 'recall']:.3f} | {o.loc[fa, 'F1_strict']:.3f} | {o.loc[fa, 'null_shift15_F1']:.3f} | **{a.loc[fa, 'AUC_model']:.3f}** ({a.loc[fa, 'ci_lo']:.3f}–{a.loc[fa, 'ci_hi']:.3f}) |
| unseen B: train V1, test V2 | {int(o.loc[fb, 'cycles'])} | **{o.loc[fb, 'F1']:.3f}** | {o.loc[fb, 'precision']:.3f} | {o.loc[fb, 'recall']:.3f} | {o.loc[fb, 'F1_strict']:.3f} | {o.loc[fb, 'null_shift15_F1']:.3f} | **{a.loc[fb, 'AUC_model']:.3f}** ({a.loc[fb, 'ci_lo']:.3f}–{a.loc[fb, 'ci_hi']:.3f}) |

* **D0 is reconstructed less well than D-1.** D-1 reached lot F1 {FW.F1_forward.iloc[0]:.2f} / {FW.F1_forward.iloc[1]:.2f} and AUC {FW.AUC_any_forward.iloc[0]:.2f} / {FW.AUC_any_forward.iloc[1]:.2f} on unseen cycles. *Observed.*
* **The weak links** are solo selling (70% of D0 sells), the size and timing of buy-back bursts, and the stop.
  * Errors compound: the hedge classes follow simulated body orders, and a stop missed or added changes the rest of the day.
* **The stop** in free running agrees on {int(sg.loc[oof, 'both'] + sg.loc[oof, 'neither'])} of 30 cycles (out-of-fold): {int(sg.loc[oof, 'both'])} found, {int(sg.loc[oof, 'real only'])} missed, {int(sg.loc[oof, 'sim only'])} false. These follow differences between simulated and real P&L.

## 1. By class (out-of-fold)
{table(CL[CL.split == oof][['cls', 'real_lots', 'sim_lots', 'matched', 'precision', 'recall', 'F1', 'F1_strict', 'F1_within1']])}

* `body_long` is only partly modelled: the 09:15 opening wings and the clearance. The body-stream long trades during the day are not ({int(byc.loc['body_long', 'real_lots']):,} real lots against {int(byc.loc['body_long', 'sim_lots'])} simulated).
* Not modelled: {int(o.loc[oof, 'not_modelled_lots'])} lots (`h_` shorts and covers, `v_` shorts and buys, `m_`).

**Unseen cycles, by class:**

{table(CL[CL.split != oof].pivot(index='cls', columns='split', values='F1').reset_index())}

## 2. AUC
{table(AU)}

`AUC_raw_simulator` scores each cell by the simulator's own activity alone (no fitted model).

## 3. Fitted parts per split
{table(pd.DataFrame([dict(split=k, train=len(v['train']), test=len(v['test']), theta=v['k3']['theta'], tp=v['k3'].get('tp', '—'), ladder=str(v['m1']), counter_r=v['r'], opening_wings=v['ow'], waves=v['waves']) for k, v in PAR.items()]))}

## 4. D0 decoded: overview of chunks 1–5
| part | rule found | accuracy (out-of-fold unless stated) | status |
|---|---|---|---|
| Pair sells | **Fixed timetable per underlying × version** (seconds repeat across cycles); strike nearest the previous close | pair-lot F1 0.805, precision 96%, strike 99% | Observed |
| Pairs off the timetable | Opening burst around 09:16; re-centring after buy-backs; D-1 two-candle breakout | breakout F1 0.375 vs placebo ≤ 0.10 | Observed, partial |
| Solo sells (70%) | D0 spot ladder (0.05 step, lots = steps crossed, fresh 60-min extreme) + counter-sell after other-right buy-backs | F1 0.38–0.40 | Observed, weak |
| D0 selling AUC | market + rules | {s4['auc']['A same-minute market + rules']:.3f} (causal {s4['auc']['B causal (market lagged 1 min)']:.3f}) | Observed |
| Buy-back stop | own premium ≥ 1.4× entry on the minute high (D-1: 1.6×) | lot F1 0.39 (null 0.22) | Observed |
| Take-profit | premium ≤ 0.1× entry | raises deep-profit recall to 30% | Observed |
| Buy-back bursts | side-level cut of about 10% of the right's lots, across 3 strikes | trigger not found (no AUC ≥ 0.70) | Unresolved |
| Carried-lot buy-backs | not tied to their own premium (D-1 entry or D0 open) | AUC ≈ 0.55 | Unresolved |
| Buy-back AUC | market + book | {s2['auc']['A same-minute market + book']:.3f} (causal {s2['auc']['B completed bars (causal)']:.3f}) | Observed |
| Hedge controller | buy the gap S − L about 4 s after the body order; lump counts as hedge on D0 | waves = gap {h1['H1']['buy']['equals_gap']:.0%} | Observed |
| Wing strike | premium nearest 2.5% of ATM | exact 38%, ±1 69% (chance 10% / 30%) | Observed, weaker than D-1 |
| Lump salvage | released by the controller when L > S | 99.9% of lots while L > S | Observed; wing vs lump choice unresolved |
| Cycle stop | cumulative MTM (D-1 + D0) ≤ −L, checked live | 11/11, no false alarm (minute close); L between 1.17 and 1.29 lakh | Observed |
| 15:14 clearance | buy back all shorts (99.95%), sell longs | — | Observed |
| **Complete D0** | all of the above, free-running | lot F1 {o.loc[oof, 'F1']:.2f} / {o.loc[fa, 'F1']:.2f} / {o.loc[fb, 'F1']:.2f}; AUC {a.loc[oof, 'AUC_model']:.2f} / {a.loc[fa, 'AUC_model']:.2f} / {a.loc[fb, 'AUC_model']:.2f} | Observed |

## 5. Caveats
* **In-sample.** All structure was found on these 30 cycles. Unseen splits test parameters, not the discovery itself.
* **The stop uses the minute close**, a look-ahead of less than one minute, because the real stop acts on live prices.
* **Sale prices** in the simulator are the previous minute's close. Buy-backs and wing trades use the minute's close for cash.
* **The chained variant** (D0 started from the simulated D-1 book) is **not built** in this chunk. Errors would compound further.
* **Unseen split B** uses V1 waves for V2 cycles. The timetable differs by version, so pair sells degrade there.

## Run order
`bl_d0_fr.py` (~20 s) → `bl_d0_fr_score.py` (~40 s) → `make_d0fr_report.py`. Needs the chunk 1–4 outputs.
"""
open(os.path.join(RP, 'D0_FREE_RUN.md'), 'w').write(txt); print('written', len(txt))
