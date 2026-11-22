"""Builds reports/D0_STOP_CLEAR.md and figures/bl_d0x_summary.png from the chunk-4 outputs (bl_d0x_*.csv, bl_d0x_mtm.pkl.gz, bl_summary_d0x1.json)."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R = json.load(open(f'{OUT}/bl_summary_d0x1.json')); D = pd.read_pickle(f'{OUT}/bl_d0x_mtm.pkl.gz'); MT, SJ = D['MT'], D['STOPJ']
S2 = pd.read_csv(f'{OUT}/bl_d0x_s2.csv'); OO = pd.read_csv(f'{OUT}/bl_d0x_s2_oof.csv'); S3 = pd.read_csv(f'{OUT}/bl_d0x_s3.csv'); C1 = pd.read_csv(f'{OUT}/bl_d0x_c1.csv'); C2 = pd.read_csv(f'{OUT}/bl_d0x_c2.csv'); C3 = pd.read_csv(f'{OUT}/bl_d0x_c3.csv')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
fig, ax = plt.subplots(1, 3, figsize=(18, 5))
for i, js in SJ.items():
    x = MT[i]['close'] / 1e5
    if js is None: ax[0].plot(np.arange(359), x[:359], color='#cbd5e0', lw=.7)
for i, js in SJ.items():
    if js is not None: x = MT[i]['close'] / 1e5; ax[0].plot(np.arange(js + 1), x[:js + 1], color='#e53e3e', lw=1); ax[0].plot(js, x[js], 'o', color='#e53e3e', ms=4)
ax[0].axhline(-R['s2_close_L_bounds_lakh']['nonstop_min_close'] * -1, color='gray', ls=':', lw=.8); ax[0].axhline(-1.29, color='k', ls='--', lw=.8); ax[0].set_xlabel('D0 minute (0 = 09:15)'); ax[0].set_ylabel('cycle MTM since the D-1 open (lakh ₹, minute close)')
ax[0].set_title('Cycle MTM: stop cycles (red, to the stop) vs others (grey)', fontsize=10); ax[0].set_ylim(-3.5, 4)
c = S2[S2.scope == 'cumulative'].pivot(index='L_lakh', columns='mark', values='F1_pm1')
for m, col in (('close', '#2b6cb0'), ('open', '#48bb78'), ('prev_close', '#ed8936'), ('adverse_intrabar', '#9f7aea')): ax[1].plot(c.index, c[m], marker='o', label=m.replace('_', ' '), color=col)
ax[1].set_xlabel('threshold L (lakh ₹)'); ax[1].set_ylabel('cycle-level F1 (stop minute, -1..0)'); ax[1].legend(fontsize=8); ax[1].set_title('Which mark reproduces the stop (cumulative MTM)', fontsize=10); ax[1].set_ylim(0, 1.05)
cc = C1.set_index('minute'); cols = [k for k in cc.columns if k in ('num cover_short', 'num close_long', 'h_ close_long', 'h_ cover_short', 'v_ close_long')]
bottom = np.zeros(len(cc))
for k, col in zip(cols, ('#2b6cb0', '#ed8936', '#48bb78', '#9f7aea', '#e53e3e')): ax[2].bar(range(len(cc)), cc[k].values, bottom=bottom, label=k, color=col); bottom += cc[k].values
ax[2].set_xticks(range(0, len(cc), 5)); ax[2].set_xticklabels(cc.index[::5]); ax[2].legend(fontsize=8); ax[2].set_title('Lots per minute 15:00–15:35 (all cycles)', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0x_summary.png'), dpi=130)
b = R['s2_close_L_bounds_lakh']; oo = OO.groupby('mark')[['TP', 'FP', 'FN']].sum(); c2 = C2.set_index(['lots', 'rule'])
cl = lambda m, L: S2[(S2.scope == 'cumulative') & (S2.mark == m) & (S2.L_lakh == L)].iloc[0]
txt = f"""# Algo 8 — D0 chunk 4: cycle stop and 15:14 clearance

*Plan `D0_STOP_CLEAR_PLAN.md`, written before the tests. In-sample: D0 of the 30 cycles with both logs, {R['stop_cycles']} of them with a stop. Figure: `figures/bl_d0x_summary.png`.*

## 0. Result
* **The cycle stop is a cumulative mark-to-market stop on the whole cycle (D-1 + D0, all modules).** It is checked on live prices within the minute.
  * Marked at the close of the minute, a threshold of **L = 1.20 lakh** reproduces **all {R['stop_cycles']} stops** in the stop minute or the minute before, with **no false alarm** in the 19 cycles without a stop.
  * Chosen on one half and scored on the other: {int(oo.loc['close', 'TP'])} hits, {int(oo.loc['close', 'FP'])} false alarms, {int(oo.loc['close', 'FN'])} misses. *Observed.*
  * **The constant lies between {-b['nonstop_min_close']:.2f} and {-max(b['stop_cycles_close_at_crossing']):.2f} lakh on minute-close marks.** No cycle without a stop went below −{-b['nonstop_min_close']:.2f} lakh, and every stop cycle was at −{-max(b['stop_cycles_close_at_crossing']):.2f} lakh or worse when it stopped. The earlier work's −1.30 to −1.44 lakh is the upper part of the range minute data allow. Ticks would pin it.
* **The stop cannot be timed from completed bars.**
  * With the previous minute's close, it is caught {int(cl('prev_close', 1.2).hits_pm1)}/{R['stop_cycles']} times at 1.20 lakh; with the minute's open, {int(cl('open', 1.2).hits_pm1)}/{R['stop_cycles']}.
  * Marking at the adverse intrabar extreme raises false alarms.
  * Loss measured from the D0 open fails (F1 ≤ {S2[S2.scope == 'D0-only'].F1_pm1.max():.2f}): the stop counts the D-1 loss too.
* **4 of the 11 stops fire before 09:16** (the gap at the open). 8 of 11 are in the first 15 minutes. The `s_` module liquidates the book in a median {S3.s_span_s.median():.0f} s; three stops took 2–5 minutes. After it, body selling stops for the day. During the liquidation, though, the body keeps selling in {int((S3.body_sell_lots_after > 0).sum())} of 11 cycles ({int(S3.body_sell_lots_after.sum())} lots, mostly inside the `s_` window).
* **15:14 clearance: shorts open at 15:09 are bought back before the close.** All but {int(round((1 - c2.loc[('short', 'premium >= p*'), 'closed_share']) * c2.loc[('short', 'premium >= p*'), 'n_lots']))} of {int(c2.loc[('short', 'premium >= p*'), 'n_lots']):,} lots in non-stop cycles ({c2.loc[('short', 'premium >= p*'), 'closed_share']:.2%}). Almost nothing is left to expire.
  * The big wave is at 15:14; the rest follow 15:15–15:34.
  * The 15:14 lots are somewhat dearer: premium AUC {R['c3_auc_px_1514_vs_later']:.2f} against later buy-backs.
* **Longs:** {c2.loc[('long', 'premium >= p*'), 'closed_share']:.0%} of long lots are sold; the rest are kept to expiry. No premium or moneyness rule beats "sell all" ({c2.loc[('long', 'premium >= p*'), 'accuracy_oof']:.0%} vs {c2.loc[('long', 'premium >= p*'), 'majority_class']:.0%}). The kept ones are the cheap ones (premium AUC {c2.loc[('long', 'premium >= p*'), 'AUC_all']:.2f}).

## 1. Stop: which mark and threshold (S2)
Cycle-level F1: a hit is a predicted crossing in the real stop minute or the minute before.

**Cumulative MTM (since the D-1 open):**

{table(S2[S2.scope == 'cumulative'].pivot(index='L_lakh', columns='mark', values='F1_pm1').reset_index(), 2)}

**D0-only MTM (minus the 09:15 open mark):**

{table(S2[S2.scope == 'D0-only'].pivot(index='L_lakh', columns='mark', values='F1_pm1').reset_index(), 2)}

**Out-of-fold (mark fixed, L and scope chosen on the other half):**

{table(OO)}

**MTM at the stop (lakh ₹, minute close)** for each stop cycle: {', '.join(f'{x:.2f}' for x in b['stop_cycles_close_at_crossing'])}. Lowest MTM of the cycles without a stop (before 15:14), most negative first: {', '.join(f"{v['close']:.2f}" for v in sorted(R['min_mtm_nonstop_lakh'].values(), key=lambda v: v['close'])[:5])} …

* **Correction during this chunk.** A first run let predictions fall up to 5 minutes after the real stop. That made causal marks look perfect, because the stop's own liquidation locked in the loss one minute later. Predictions are now limited to the stop minute and earlier.
* Contracts with no D0 price at the open: {R['contracts_missing_price_share_at_open']:.1%} of positions (marked 0).

## 2. What the stop does (S3)
{table(S3, 2)}

* `s_` closes both sides, buying back the shorts and selling the longs. Median {S3.s_span_s.median():.0f} s; three stops took 2–5 minutes.
* **Body sells still occur after the stop** in {int((S3.body_sell_lots_after > 0).sum())} of 11 cycles: {int(S3.body_sell_lots_after.sum())} lots, the last one at most {S3.last_body_sell_after_s.max() / 60:.0f} minutes after the stop. The earlier register noted these post-stop short fills (U8). Whether they are late fills of pending orders or new decisions is **unresolved**.

## 3. Clearance (C1–C3)
**Which open lots at 15:09 are closed later** (cycles without a stop; rules fitted on one half):

{table(C2)}

**15:14 against later buy-backs** (premium at the 15:13 close):

{table(C3, 2)}

* Shorts are bought back by the close (all but one lot). Longs are sold except the cheapest.
* The split between the 15:14 wave and the 15:15–15:34 tail is only weakly linked to price (premium AUC {R['c3_auc_px_1514_vs_later']:.2f}; moneyness {R['c3_auc_itm_1514_vs_later']:.2f}). It looks like order pacing. *Inferred.*

## 4. Kept and rejected
| rule | result | decision | evidence |
|---|---|---|---|
| Cycle stop: cumulative MTM (D-1 + D0, all modules) ≤ −L, live within the minute | 11/11, no false alarm, at L = 1.20 lakh with minute-close marks; out-of-fold the same | kept | Observed |
| Constant L | between {-b['nonstop_min_close']:.2f} and {-max(b['stop_cycles_close_at_crossing']):.2f} lakh on minute closes | bounded, not pinned | Observed |
| Stop timed from completed bars (previous close / open) | at most {int(cl('open', 1.2).hits_pm1)}/11 | rejected (the stop is intrabar) | Observed |
| D0-only loss | F1 ≤ {S2[S2.scope == 'D0-only'].F1_pm1.max():.2f} | rejected | Observed |
| Clearance: buy back every short by the close | {c2.loc[('short', 'premium >= p*'), 'closed_share']:.2%} of lots | kept | Observed |
| Clearance: sell longs except the cheapest | {c2.loc[('long', 'premium >= p*'), 'closed_share']:.0%} sold; no threshold beats "sell all" | kept as "sell all" | Observed |

## 5. Caveats
* **In-sample:** 11 stop cycles. Out-of-fold over halves.
* **LTP MTM without costs.** Marks are minute bars, so the true intraminute trigger price is not observed.
* **The stop decides on live prices.** A minute-bar simulator has to use the close of the minute (a small look-ahead inside the minute) or accept late stops.

## Run order
`bl_d0x_stop.py` → `make_d0x_report.py`. Outputs `outputs/bl_d0x_*`, `bl_summary_d0x1.json`.
"""
open(os.path.join(RP, 'D0_STOP_CLEAR.md'), 'w').write(txt); print('written', len(txt))
