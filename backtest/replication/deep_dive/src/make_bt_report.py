"""Builds reports/BUYBACK_STOP3.md and figures/bl_bt_summary.png from bl_bt_* outputs and bl_summary_bt1/5/7.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); B1, B5, B7 = J('bt1'), J('bt5'), J('bt7')
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
F = pd.read_csv(f'{OUT}/bl_bt_fresh.csv'); X = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); P = pd.read_pickle(f'{OUT}/bl_bt_react.pkl.gz'); C = pd.read_csv(f'{OUT}/bl_bt_ctx.csv'); PF = pd.read_csv(f'{OUT}/bl_bt_profit.csv'); AD = pd.read_csv(f'{OUT}/bl_bt_adv.csv')
F['held_bin'] = pd.cut(F.mins_held, [0, 5, 10, 15, 30, 60, 120, 400]); fl = F[F.ratio > 1]
tab1 = fl.groupby('held_bin', observed=True).agg(buy_backs=('ratio', 'size'), median_ratio=('ratio', 'median')).round(3).reset_index(); tab1['reactive share'] = fl.groupby('held_bin', observed=True).typ.apply(lambda s: f"{(s == 'reactive').mean():.0%}").values; tab1['scheduled share'] = fl.groupby('held_bin', observed=True).typ.apply(lambda s: f"{(s == 'scheduled').mean():.0%}").values; tab1['held_bin'] = tab1.held_bin.astype(str)
bins = [0, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9]; hz = X[X.typ.isin(['scheduled', 'reactive', 'solo'])].groupby(['typ', pd.cut(X.ratio_h, bins)], observed=True).y.mean().unstack('typ').mul(100).round(2); hz.index = hz.index.astype(str)
r_ = P[(P.typ == 'reactive') & (P.ratio_h > 1)]; s_ = P[(P.typ == 'solo') & (P.ratio_h > 1)]
rc = r_.groupby(pd.cut(r_.move_since_sale, [-9, -2, -1, 0, 0.5, 1, 2, 9]), observed=True).y.mean().mul(100).round(2); sc = s_.groupby(pd.cut(s_.move_since_sale, [-9, -2, -1, 0, 0.5, 1, 2, 9]), observed=True).y.mean().mul(100).round(2)
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
ax[0, 0].bar(range(len(tab1)), tab1.median_ratio, color='#2b6cb0'); ax[0, 0].set_xticks(range(len(tab1))); ax[0, 0].set_xticklabels(tab1.held_bin, fontsize=8); ax[0, 0].set_ylim(1, 1.7); ax[0, 0].set_ylabel('median ratio at buy-back (lots in loss)'); ax[0, 0].set_xlabel('minutes the lot was held'); ax[0, 0].set_title('(a) Low ratios = fresh lots, not a random threshold')
for t, cl in (('scheduled', '#2b6cb0'), ('solo', '#38a169'), ('reactive', '#dd6b20')): ax[0, 1].plot(range(len(hz)), hz[t].values, marker='o', color=cl, label=t)
ax[0, 1].set_xticks(range(len(hz))); ax[0, 1].set_xticklabels([s.replace('(', '').replace(']', '') for s in hz.index], rotation=45, fontsize=7); ax[0, 1].set_ylabel('buy-back hazard % per lot-minute'); ax[0, 1].set_xlabel('minute high ÷ own entry'); ax[0, 1].legend(); ax[0, 1].set_title('(b) Each sell type has its own exit curve')
ax[1, 0].plot(range(len(rc)), rc.values, marker='o', color='#dd6b20', label='reactive lots'); ax[1, 0].plot(range(len(sc)), sc.values, marker='o', color='#38a169', label='solo lots'); ax[1, 0].set_xticks(range(len(rc))); ax[1, 0].set_xticklabels([str(i).replace('(', '').replace(']', '') for i in rc.index], fontsize=8, rotation=30)
ax[1, 0].set_xlabel('spot move since the sale (steps; + = continued in the entry direction)'); ax[1, 0].set_ylabel('buy-back hazard % (lots in loss)'); ax[1, 0].legend(); ax[1, 0].set_title('(c) Reactive: cut on continuation; solo: cut on reversal')
cls = pd.Series(B7['profit_classes']); ax[1, 1].barh(range(len(cls))[::-1], cls.values, color='#805ad5'); ax[1, 1].set_yticks(range(len(cls))[::-1]); ax[1, 1].set_yticklabels(cls.index, fontsize=8); ax[1, 1].set_xlabel('lot buy-backs'); ax[1, 1].set_title('(d) Buy-backs in profit: what happens at the same moment')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_bt_summary.png'), dpi=130)
ct = C.assign(fresh=np.where(C.held <= 10, 'held ≤ 10 min', 'held > 10 min')).groupby(['typ', 'fresh'])[['sec0', 'other_bb_same_right', 'other_bb_other_right', 'new_sell_any', 'new_sell_same_right']].mean().mul(100).round(0).astype(int).astype(str).add('%').reset_index(); ct['n'] = C.assign(fresh=np.where(C.held <= 10, 'a', 'b')).groupby(['typ', 'fresh']).size().values
ct.columns = ['type', 'holding', 'at second :00', 'other strike same right ±5 s', 'buy-back other right ±5 s', 'new sell ±5 s', 'new sell same right ±5 s', 'n']
ad = AD.copy(); ad['F1'] = ad.F1.round(3); ad['precision'] = ad.precision.round(3); ad['recall'] = ad.recall.round(3)
pf = PF.groupby('state')[['partner_same_strike_other_right', 'stop_like_same_right', 'stop_like_other_right', 'sell_same_right', 'sell_other_right', 'sec0']].mean().mul(100).round(0).astype(int).astype(str).add('%').reset_index()
hzt = hz.reset_index().rename(columns={'ratio_h': 'minute high ÷ entry'})
txt = f"""# Algo 8 — D-1 buy-backs, third pass: why some exit at 1.1× and others at 1.7×

*Follow-up to `BUYBACK_DECODE.md` and `BUYBACK_STOP2.md` at the user's request ("they don't choose randomly between 1.2× and 1.7×"). Descriptive and post-hoc, in-sample, D-1 of 32 cycles. Lot ownership: a buy-back removes the open lot with the highest own ratio on that contract. Figure: `figures/bl_bt_summary.png`.*

## 0. Result: the 1.1×–1.7× spread is not random, it is a mix of different exits
1. **Not points but ratio.** The points lost at the buy-back scale with the entry price: log-slope {B1['SENSEX']['slope_logpts_on_logentry']:.2f} (SENSEX) and {B1['NIFTY']['slope_logpts_on_logentry']:.2f} (NIFTY); a fixed-points stop would give about 0. There is no clear time-of-day pattern in the ratio.
2. **Holding time separates them** (ρ {B1['NIFTY']['rho_ratio_mins_held']:.2f} / {B1['SENSEX']['rho_ratio_mins_held']:.2f}). Lots bought back within 10 minutes of their sale exit at about **1.1×**; lots held more than 30 minutes at about **1.55–1.6×**.
3. **The fresh, low-ratio exits are directional lots.** Of buy-backs within 5 minutes, about 55% are reactive lots (they are 17% of all sells). Each sell type has its own exit behaviour:
   * **Scheduled straddle lots: a premium stop.** The hazard is about 0 below 1.5×, then 4% → 15% → 47% per minute above 1.5 / 1.6 / 1.7×. Out-of-fold the threshold is **1.6–1.65× of the lot's own entry** (minute high).
   * **Reactive lots: cut when the breakout continues.** The leg on the break side is bought back while the spot keeps going in the break direction: hazard 2.9% vs 0.3%, and 7.9% per minute at 1–2 steps of continuation. Most of these exits happen within 5 minutes of the sale.
   * **Solo lots: cut when the market reverses.** Hazard 4.8% at 2+ steps of reversal, and 2.0% after an opposite two-candle break, against 0.24%.
4. **Buy-backs are rebalancing events, not isolated stops.**
   * 67–77% come with buy-backs on other strikes of the same right within 5 s.
   * About 30% of the older-lot buy-backs come with a **new solo sell on the other right** within 5 s (base rate 3%): when calls are cut in a rally, puts are sold.
   * About 53–63% are at second :00 (minute-clocked).
5. **In-profit buy-backs (129 lots, about 10%)** are mostly the **partner leg**:
   * 34% are the same-strike partner on the other right (in-loss buy-backs: 6%);
   * 29% happen at the same moment as a stop on the other right, i.e. the straddle is closed together;
   * 18% come with a stop on the same right (cluster);
   * 45% have no coincident event.

**What this does to accuracy (honest):**
* Separate rules per type, out-of-fold, at lot level:
  * scheduled premium stop F1 {AD[(AD.type == 'scheduled') & (AD.family == 'premium only')].F1.iloc[0]:.2f};
  * solo {AD[(AD.type == 'solo') & (AD.family == 'premium only')].F1.iloc[0]:.2f} (premium) and {AD[(AD.type == 'solo') & (AD.family == 'adverse steps only')].F1.iloc[0]:.2f} (spot steps);
  * reactive {AD[(AD.type == 'reactive') & (AD.family == 'premium only')].F1.iloc[0]:.2f} / {AD[(AD.type == 'reactive') & (AD.family == 'adverse steps only')].F1.iloc[0]:.2f}.
* The continuation and reversal exits raise the hazard 5–25× but do not turn into a sharp threshold on steps or ratio. Their exact trigger, probably checked on live prices within the minute, is not recoverable from one-minute bars.
* So the decoded structure explains *why* ratios differ, but the lot-level buy-back accuracy stays at the premium-stop level (about 0.59 on the real book).

## 1. Ratio at buy-back by holding time (lots in loss)
{table(tab1)}

## 2. Hazard per lot-minute (%) by sell type
{table(hzt)}

## 3. Context at the buy-back second
{table(ct)}

## 4. Buy-backs in profit vs in loss (coincident events within 5 s)
{table(pf)}

## 5. Lot-level rules per type (out-of-fold)
{table(ad)}

## Evidence labels
* **Observed:** §0–5.
* **Inferred:** "sub-strategy stops"; the rebalancing reading; the live-price explanation.
* **Unresolved:** the exact trigger of the reactive continuation and solo reversal exits, and 45% of in-profit buy-backs.
* All post-hoc on the same 32 cycles.
"""
open(f'{RP}/BUYBACK_STOP3.md', 'w').write(txt); print('ok')
