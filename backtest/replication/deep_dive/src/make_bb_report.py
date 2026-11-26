"""Builds reports/BUYBACK_DECODE.md and figures/bl_bb_summary.png from bl_bb_*, bl_fr*_overall/classes, bl_sell_err, bl_summary_bb1-8/rep1."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); B1, B2, B3, B4, B5, B6, B7, B8, RP1 = [J(x) for x in ('bb1', 'bb2', 'bb3', 'bb4', 'bb5', 'bb6', 'bb7', 'bb8', 'rep1')]
pct = lambda x: f'{100 * x:.0f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
G = pd.read_csv(f'{OUT}/bl_bb_eventlevel.csv'); V = pd.read_csv(f'{OUT}/bl_bb_vel.csv'); C1 = pd.read_csv(f'{OUT}/bl_fr_classes.csv'); C1 = C1[C1.variant.str.startswith('FR free')].set_index('cls'); C2 = pd.read_csv(f'{OUT}/bl_fr2_classes.csv').set_index('cls'); O1 = pd.read_csv(f'{OUT}/bl_fr_overall.csv').iloc[0]; O2 = pd.read_csv(f'{OUT}/bl_fr2_overall.csv').iloc[0]
TF = pd.read_csv(f'{OUT}/bl_bb_tf.csv'); SE = pd.read_csv(f'{OUT}/bl_sell_err.csv'); LOW = pd.read_csv(f'{OUT}/bl_bb_low.csv')
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
bins = np.arange(0.5, 2.21, 0.05); ax[0, 0].hist(G.r_first.clip(0.5, 2.2), bins=bins, color='#2b6cb0'); ax[0, 0].axvline(1.45, ls='--', color='k', lw=.8); ax[0, 0].set_xlabel('buy-back decision price ÷ cheapest open entry (decision prices)'); ax[0, 0].set_ylabel('buy-back events'); ax[0, 0].set_title('(a) Two populations: stop-like (≥1.45×, mode 1.5–1.7×) and low-ratio')
for v, cl in (('rc_min', '#a0aec0'), ('rh_min', '#2b6cb0')):
    h = B3[f'hazard_{v}'] if f'hazard_{v}' in B3 else None
    if h: k = list(h); ax[0, 1].plot(range(len(k)), [h[x][0] for x in k], marker='o', color=cl, label={'rc_min': 'previous close ÷ entry', 'rh_min': 'minute high ÷ entry'}[v])
ax[0, 1].set_xticks(range(len(k))); ax[0, 1].set_xticklabels([x.replace('(', '').replace(']', '') for x in k], rotation=45, fontsize=7); ax[0, 1].set_ylabel('buy-back hazard per contract-minute'); ax[0, 1].legend(fontsize=8); ax[0, 1].set_title('(b) The stop is graded, not a step (1.5× → 1.8×)')
lw = LOW.head(8); ax[1, 0].barh(range(len(lw))[::-1], lw.AUC, color='#38a169'); ax[1, 0].set_yticks(range(len(lw))[::-1]); ax[1, 0].set_yticklabels(lw.variable, fontsize=8); ax[1, 0].axvline(.5, color='k', lw=.8); ax[1, 0].set_xlim(.3, .9); ax[1, 0].set_title('(c) Low-ratio buy-backs: premium speed ranks best (AUC)')
cls = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'lump']; x = np.arange(len(cls)); ax[1, 1].bar(x - .2, [C1.loc[c, 'F1'] for c in cls], .4, color='#a0aec0', label=f'before (overall F1 {O1.F1:.3f})'); ax[1, 1].bar(x + .2, [C2.loc[c, 'F1'] for c in cls], .4, color='#2b6cb0', label=f'after (overall F1 {O2.F1:.3f})')
ax[1, 1].set_xticks(x); ax[1, 1].set_xticklabels(cls, fontsize=8); ax[1, 1].set_ylim(0, 1); ax[1, 1].legend(fontsize=8); ax[1, 1].set_title('(d) Free-running D-1 F1 by class, before vs after')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_bb_summary.png'), dpi=130)
v = V.copy(); v = v.assign(AUC=v.AUC.round(3), F1_pm1_oof=v.F1_pm1_oof.round(3)); v.columns = ['variable', 'AUC', 'threshold (fold 1/2)', 'F1 ±1 min (out-of-fold)']
tf = TF[['variant', 'cls', 'real_lots', 'sim_lots', 'precision', 'recall', 'F1']].round(3)
se = SE.round(3)
b6 = pd.DataFrame(B6['chosen']); b6['F1_train'] = b6.F1_train.round(3)
txt = f"""# Algo 8 — D-1 body buy-backs: decoding the stop (and what limits accuracy)

*Plan `BUYBACK_DECODE_PLAN.md`, written before the tests. In-sample, D-1 of 32 live cycles: 1,324 buy-back lots (all 1-lot orders) in 841 events (same contract, within 3 s). Ratios use the order's limit-implied **decision price** (the price the algorithm saw), not minute bars, wherever the ledger allows. Figure: `figures/bl_bb_summary.png`.*

## 0. Result
| Question | Answer | Evidence |
|---|---|---|
| Is there a stop on the lot's own premium? | **Yes, for about half of the events.** {(G.r_first >= 1.45).sum()} of {len(G)} events have decision price ÷ cheapest open entry ≥ 1.45×, mode 1.5–1.7×, almost nothing above 1.8× (median {B1['q_r_ref_min']['0.5']:.2f}×). | Observed |
| Is it a fixed threshold? | **No, it is graded.** The hazard per contract-minute rises 2% → 9% → 24% → 41% across 1.4–1.8× and does not jump at one level. The same holds in every underlying, version and cycle, so it is not a mix of different settings. The intrabar version (minute high ÷ entry) ranks best: AUC {V[V.variable == 'rh_min'].AUC.iloc[0]:.2f}, out-of-fold threshold about 1.61–1.66×. | Observed |
| How many lots per stop? | The open lots on that contract that are above about 1.55× (71% within one lot). Not the whole contract: only 18% of stops close all lots on it. | Observed |
| Clocked checks? | No. Buy-back minutes are spread evenly across the hour (mild :00 and :05 excess). 48% fill at second :00. | Observed |
| Right-level controller (whole CE or PE book)? | Rejected. Right-level ratio before a buy-back ranges 0.74–1.45×; after it, it is not pinned to a level. | Observed |
| The other half (low-ratio, near ATM)? | **Fast adverse moves.** The best variable is the 3-minute premium rise (AUC {LOW.iloc[0].AUC:.2f}, same in both halves). Not delta control (AUC {LOW[LOW.variable == 'delta_short_dir'].AUC.iloc[0]:.2f}), not a strike breach ({LOW[LOW.variable == 'breach3'].AUC.iloc[0]:.2f}), not side balance (larger side 69% = chance). No threshold separates them (tree F1 {B8['tree']['F1']:.2f}). Followed by a re-sale (roll) in only 14–22% of cases. | Observed; trigger unresolved |
| Ceiling of the decoded rule | Run on the **real** sells, the best stop design gives buy-back F1 **{TF[(TF.cls == 'body_buyback') & TF.variant.str.contains('decoded')].F1.iloc[0]:.3f}** (plain close ≥ 1.5×: {TF[(TF.cls == 'body_buyback') & TF.variant.str.contains('plain')].F1.iloc[0]:.3f}). The limit is the rule, not inherited sell errors. Timing tolerance ±3 minutes lifts it only to about 0.62 (free-running). | Observed |

**Accuracy impact (free-running, out-of-fold):** buy-backs {C1.loc['body_buyback', 'F1']:.3f} → **{C2.loc['body_buyback', 'F1']:.3f}**, wing sells {C1.loc['wing_sell', 'F1']:.3f} → {C2.loc['wing_sell', 'F1']:.3f}, overall {O1.F1:.3f} → **{O2.F1:.3f}**. A small gain. The decoded structure is right, but half of the buy-backs have no recoverable trigger at one-minute resolution.

## 1. Stop variables tested (contract-minute panel, {len(pd.read_pickle(f'{OUT}/bl_bb_panel.pkl.gz')):,} rows, label = buy-back in the minute)
{table(v)}

OR-combinations (entry stop OR premium speed) reach F1 0.43–0.44 out-of-fold (±1 minute, contract-minute), against 0.40 for the entry stop alone.

## 2. Stop design chosen in the simulator (out-of-fold, objective = buy-back lot F1)
{table(b6)}

Both folds choose an entry stop near **1.55–1.6×**. Fold 1 prefers the intrabar high, fold 0 the previous close plus a 3-minute speed trigger. Neither chooses the same-right cluster add-on.

## 3. The rule on the real sells (isolates the stop rule)
{table(tf)}

## 4. After the buy-back: what limits the whole D-1 reconstruction now
Body-sell errors, free-running, by real sell type (recall) and by simulated type (precision):
{table(se)}

* Scheduled pairs are essentially exact.
* The losses come from **solo intraday** (49% reproduced, simulated precision 53%), **reactive lot counts** (66%; the rule is 97% precise but under-sizes) and two classes not modelled (after-15:00 solo, deep-OTM batches).
* **Reactive repeat entries** (a new running-candle extreme beyond the channel after the first entry) were added and **rejected**: out-of-fold, both folds choose zero repeats, and the overall F1 stays at {RP1['overall']['F1']:.3f}.

## 5. Why this is close to the limit of this data (quant view)
* A stop that is sharp in the real system looks graded at one-minute resolution when the trigger price is a **tick or quote we cannot see** (LTP vs bid/ask), when checks are asynchronous, or when the entry reference differs slightly per lot. The decision prices in the ledger narrow this (mode 1.5–1.7×) but cannot remove it.
* The low-ratio half reacts to **speed**, which needs intrabar paths (ticks or seconds) to turn a ranking (AUC 0.80) into a rule.
* Everything here is in-sample on 32 cycles. More rule mining on the same data mainly fits noise: every extra condition tried (cluster, speed variants, repeats) gains less than 0.01 out-of-fold.
* What would raise accuracy: **tick or one-second option data** for the stop and speed triggers, and **more cycles** (out-of-sample) to separate real rules from chance.

## Evidence labels
* **Observed:** sections 0–4.
* **Inferred:** the price-feed explanation in §5.
* **Unresolved:** the exact trigger of the low-ratio half, reactive lot sizes, solo selection.
* **Not testable:** intrabar sequencing, quotes, original risk inputs.
"""
open(f'{RP}/BUYBACK_DECODE.md', 'w').write(txt); print('ok')
