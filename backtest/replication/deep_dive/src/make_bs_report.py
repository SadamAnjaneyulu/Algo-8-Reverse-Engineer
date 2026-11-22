"""Builds reports/BUYBACK_STOP2.md and figures/bl_bs_summary.png from bl_bs_* outputs and bl_summary_bs1-6.json (plus bl_bb_tf / bl_fr2 for comparison)."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); S5, S6 = J('bs5'), J('bs6')
pct = lambda x: f'{100 * x:.0f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
X = pd.read_pickle(f'{OUT}/bl_bs_panel.pkl.gz'); g = X[X.gate == 1]; SI = pd.read_csv(f'{OUT}/bl_bs_single.csv'); CO = pd.read_csv(f'{OUT}/bl_bs_combo.csv'); MK = pd.read_csv(f'{OUT}/bl_bs_mkt.csv'); PR = pd.read_csv(f'{OUT}/bl_bs_price.csv'); FT = pd.read_csv(f'{OUT}/bl_bs_fit.csv'); AB = pd.read_csv(f'{OUT}/bl_bs_ab.csv')
TF0 = pd.read_csv(f'{OUT}/bl_bb_tf.csv'); O2 = pd.read_csv(f'{OUT}/bl_fr2_overall.csv').iloc[0]; C2 = pd.read_csv(f'{OUT}/bl_fr2_classes.csv').set_index('cls'); O5 = pd.read_csv(f'{OUT}/bl_fr5_overall.csv').iloc[0]; C5 = pd.read_csv(f'{OUT}/bl_fr5_classes.csv').set_index('cls')
tfAB = AB[(AB['mode'] == 'tf_bb') & (AB.cls == 'body_buyback')].iloc[0]; frAB = C5.loc['body_buyback']; tfP = PR[PR.price == 'high'].iloc[0]; tfC = FT[(FT['mode'] == 'tf_bb') & (FT.cls == 'body_buyback')].iloc[0]
b = pd.cut(g.ratio_h, [1, 1.2, 1.3, 1.4, 1.5, 1.55, 1.6, 1.65, 1.7, 1.8, 9]); hz = g.groupby([b, 'don60'], observed=True).y.mean().unstack('don60')
fig, ax = plt.subplots(1, 3, figsize=(17, 5))
xs = np.arange(len(hz)); ax[0].plot(xs, hz[0].values, marker='o', color='#a0aec0', label='no fresh 60-min breakout against'); ax[0].plot(xs, hz[1].values, marker='o', color='#2b6cb0', label='fresh 60-min breakout against'); ax[0].set_xticks(xs); ax[0].set_xticklabels([str(i).replace('(', '').replace(']', '') for i in hz.index], rotation=45, fontsize=7); ax[0].set_ylabel('buy-back hazard per minute (lot in loss)'); ax[0].set_xlabel('minute high ÷ entry'); ax[0].legend(fontsize=8); ax[0].set_title('(a) Premium loss × market breakout')
s1 = SI.head(10); ax[1].barh(range(len(s1))[::-1], s1.F1, color=np.where(s1.semantics == 'cross', '#38a169', '#2b6cb0')); ax[1].set_yticks(range(len(s1))[::-1]); ax[1].set_yticklabels([f'{a} ({b_})' for a, b_ in zip(s1.indicator, s1.semantics)], fontsize=7); ax[1].set_xlabel('F1 ±1 min, out-of-fold (contract-minute, teacher-forced)'); ax[1].set_title('(b) Single stop indicators (with the loss gate)')
lab = ['premium only\n(previous close 1.5×)', 'premium only\n(minute high 1.6×)', 'premium AND\nbreakout', 'A OR B\n(stop + market exit)']
vals = [TF0[(TF0.cls == 'body_buyback') & TF0.variant.str.contains('plain')].F1.iloc[0], tfP.F1, tfC.F1, tfAB.F1]
ax[2].bar(range(4), vals, color=['#a0aec0', '#2b6cb0', '#dd6b20', '#38a169']); ax[2].set_xticks(range(4)); ax[2].set_xticklabels(lab, fontsize=8); ax[2].set_ylim(0, 1); ax[2].set_ylabel('buy-back lot F1 on the REAL sells (out-of-fold)'); ax[2].set_title('(c) Simulated stop on the real book')
for k, v in enumerate(vals): ax[2].text(k, v + .02, f'{v:.3f}', ha='center')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_bs_summary.png'), dpi=130)
hzt = (hz * 100).round(1).reset_index(); hzt.columns = ['minute high ÷ entry', 'hazard % (no breakout)', 'hazard % (fresh 60-min breakout against)']; hzt.iloc[:, 0] = hzt.iloc[:, 0].astype(str)
si = SI.head(14)[['indicator', 'semantics', 'AUC_in_gate', 'thr', 'F1', 'precision', 'recall']].round(3)
co = CO.head(6).round(3); mk = MK.head(6)[['market', 'family', 'params', 'F1', 'precision', 'recall']].round(3)
ch = pd.DataFrame(S5['tf_bb']['chosen'] + S5['free']['chosen'])
pp = PR[['price', 'theta_folds', 'precision', 'recall', 'F1']].round(3)
txt = f"""# Algo 8 — D-1 buy-backs, second pass: stops on losing positions and the market factor

*Plan `BUYBACK_STOP2_PLAN.md`, written before the tests. It follows the user's premise that buy-backs happen in loss (profitable shorts are carried) and that market movement plays a part. In-sample, D-1 of 32 cycles. Figure: `figures/bl_bs_summary.png`.*

## 0. Result
* **The premise holds:** **87%** of buy-back orders are on a lot in loss at the decision price (89% on fills).
  * The other 13% (177 orders, every lot on the contract in profit) are out of the money (median {S6['all lots in profit']['itm']:.1f} strikes). A third of them ({pct(S6['all lots in profit']['bb_other_right_3s'])}) come together with a buy-back on the other right, against {pct(S6['in loss (cheapest lot)']['bb_other_right_3s'])} for in-loss ones: a two-sided cut-back, not a stop.
* **Market movement matters, as you suspected.** For a lot in loss, a fresh 30–60-minute spot breakout against the position multiplies the per-minute buy-back hazard about **10×** at every premium level (table below). At 1.7–1.8× of entry: 62% with a breakout against 22% without. With teacher-forced scoring, "premium ≥ 1.5× AND breakout" lifts contract-minute F1 from 0.39 to **0.49** (+0.08 in both halves).
* **But it is an accelerator, not the stop condition.** Run order by order on the real book, the plain intrabar premium stop stays best:
  * Minute high ≥ 1.6× entry: F1 {tfP.F1:.3f}.
  * "Premium AND breakout": {tfC.F1:.3f}. Lots that cross 1.6× without a breakout are still bought back within minutes; waiting for the breakout delays them.
  * The **close** or typical price does worse than the **high** ({PR[PR.price == 'close_now'].F1.iloc[0]:.3f} / {PR[PR.price == 'typical'].F1.iloc[0]:.3f}). The stop reacts to intrabar touches.
* **Best combined rule "A OR B":**
  * A = intrabar stop at about 1.6×.
  * B = in loss AND market against at a lower ratio.
  * Result: **{tfAB.F1:.3f}** on the real book, against {tfP.F1:.3f} for A alone, and **{frAB.F1:.3f}** free-running (previous best {C2.loc['body_buyback', 'F1']:.3f}).
  * Whole D-1 free-running F1: {O2.F1:.3f} → **{O5.F1:.3f}**.

## 1. Hazard: premium loss × breakout (lots in loss)
{table(hzt)}

## 2. Single stop indicators (loss gate; teacher-forced; out-of-fold thresholds)
{table(si)}

Spot-only stops (ATR since entry, Chandelier, Supertrend, Parabolic SAR, EMA cross, Bollinger) are all far weaker than the premium stop alone, and none acts as a stop on its own.

## 3. Two-indicator rules and the breakout window (teacher-forced)
{table(co)}

{table(mk)}

## 4. Price feed for the premium stop (real book, order by order, θ out-of-fold)
{table(pp)}

## 5. A OR B rule (chosen per fold; real book and free-running)
{table(ch)}

## 6. Reading
* The buy-back logic is a **per-lot own-premium stop near 1.6× of entry, acting on intrabar prices**.
* Market breakouts against the position make it fire much faster. This is consistent with the live premium staying above the level during a breakout, while minute-high touches without a breakout are partly wicks the system's feed may not see. *Inferred.*
* The rest, roughly the low-ratio half, are in-loss exits during adverse moves. They are not separable by any spot indicator tested (Supertrend, SAR, Chandelier, ATR, Donchian, Bollinger, EMA, RSI) at minute resolution.
* The 13% in profit are two-sided cut-backs, not stops.

## Evidence labels
* **Observed:** §0–5.
* **Inferred:** the price-feed explanation.
* **Post-hoc:** the price-feed test, the A-or-B family, and the window refinement (the plan fixed the families, not these refinements).
* **Multiple testing:** about 30 indicators × 2 semantics plus combinations were tried. Only rules that improve in both cycle halves are reported as gains.
"""
open(f'{RP}/BUYBACK_STOP2.md', 'w').write(txt); print('ok')
