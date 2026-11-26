"""Builds reports/D0_COUNTER.md and figures/bl_d0k_summary.png from bl_d0k_*.csv and bl_summary_d0k1.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R = json.load(open(f'{OUT}/bl_summary_d0k1.json'))
C1 = pd.read_csv(f'{OUT}/bl_d0k_c1.csv'); C2 = pd.read_csv(f'{OUT}/bl_d0k_c2.csv'); C3 = pd.read_csv(f'{OUT}/bl_d0k_c3.csv'); C3b = pd.read_csv(f'{OUT}/bl_d0k_c3b.csv'); C4 = pd.read_csv(f'{OUT}/bl_d0k_c4.csv'); C6 = pd.read_csv(f'{OUT}/bl_d0k_c6.csv')
def table(df, fmt=2):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
c1 = C1.set_index('reason'); sl = c1.loc['3 stop-loss']; c2 = R['c2']; c4 = R['c4']; c5 = R['c5']; g = lambda s, f: float(C3b[(C3b.sl == s) & (C3b.fe == f)].sold.iloc[0])
fig, ax = plt.subplots(1, 3, figsize=(19, 5.6))
o = list(C1.reason); ax[0].barh(range(len(o)), C1.sales_per_event, color='#2b6cb0', label='real'); ax[0].barh(np.arange(len(o)) + .38, C1.null_15min_clock_kept, .38, color='#cbd5e0', label='null (shifted 15 min)'); ax[0].set_yticks(range(len(o))); ax[0].set_yticklabels(o, fontsize=8); ax[0].invert_yaxis(); ax[0].legend(fontsize=8); ax[0].set_title('Other-right solo sale orders within ±90 s, per buy-back event', fontsize=10)
x = (C2.lag_from_s + C2.lag_to_s) / 2; ax[1].bar(x, C2.orders, 4.2, color='#2b6cb0', label='around stop-loss events'); ax[1].plot(x, C2.null_15min, color='#718096', lw=1.5, label='null (shifted 15 min)'); ax[1].axvline(0, color='r', lw=1, ls='--'); ax[1].set_xlabel('seconds from the stop-loss buy-back (sale time − buy-back time)'); ax[1].legend(fontsize=8); ax[1].set_title('Timing: sales come as often before as after', fontsize=10)
lab = ['neither', 'stop only', 'fresh extreme only', 'both']; v = [g(False, False), g(True, False), g(False, True), g(True, True)]; ax[2].bar(range(4), v, color=['#cbd5e0', '#e53e3e', '#d69e2e', '#805ad5'])
for k_, y in enumerate(v): ax[2].text(k_, y + .05, f'{y:.2f}', ha='center')
ax[2].set_xticks(range(4)); ax[2].set_xticklabels(lab, fontsize=9); ax[2].set_ylabel('R′ solo lots sold in the minute and the next'); ax[2].set_title('What the other right responds to', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0k_summary.png'), dpi=115); plt.close()
txt = f"""# Algo 8 — D0 counter-sells: what they are

*Plan `D0_COUNTER_PLAN.md`, written before the tests. In-sample: D0 of 30 cycles, {R['events_stop_loss']:,} stop-loss buy-back events, solo sales of the other right. Figure: `figures/bl_d0k_summary.png`. Script `bl_d0k_counter.py`.*

## 0. Result: no sign that the buy-back itself triggers the counter-sell
* **Stop-loss buy-backs go together with other-right sales.** Around a stop-loss, {sl.sales_per_event:.1f} solo sale orders land on the other right within ±90 s per event, against {sl.null_15min_clock_kept:.1f} for times shifted by 15 minutes ({sl.ratio_vs_15:.1f}×). {sl.share_events_with_sale_0_60s:.0%} of events have a sale in the next 60 s (null {sl.null_share_15min:.0%}).
  * By the plan's rule (at least 1.5× both chance levels) the reasons that go with sales are: **stop-loss, cycle-stop window, burst member, roll-out and "other"** ({c1.loc['3 stop-loss','ratio_vs_10']:.1f}/{c1.loc['3 stop-loss','ratio_vs_15']:.1f}×, {c1.loc['1 cycle-stop window','ratio_vs_10']:.1f}/{c1.loc['1 cycle-stop window','ratio_vs_15']:.1f}×, {c1.loc['7 burst member','ratio_vs_10']:.1f}/{c1.loc['7 burst member','ratio_vs_15']:.1f}×, {c1.loc['6 roll-out','ratio_vs_10']:.1f}/{c1.loc['6 roll-out','ratio_vs_15']:.1f}×, {c1.loc['8 other','ratio_vs_10']:.1f}/{c1.loc['8 other','ratio_vs_15']:.1f}×, against the two chance levels).
  * **Take-profit ({c1.loc['4 take-profit', 'ratio_vs_15']:.1f}×), partner ({c1.loc['5 partner','ratio_vs_10']:.1f}/{c1.loc['5 partner', 'ratio_vs_15']:.1f}×) and clearance do not** (clearance 15:10–15:13 passes one chance level and fails the other). *Observed.*
* **But the sales are not shown to be caused by the buy-back.** They come as often before it as after: {c2['before_30s']:,} orders in the 30 s before and {c2['after_30s']:,} in the 30 s after (null {c2['null_before']}–{c2['null_after']}). A trigger would show them after. *Observed.*
* **The spot move accounts for much of it.** When the other right's short is at a fresh 60-minute favourable extreme (spot making new lows for a CE short, new highs for a PE short), it sells {g(False, True):.1f} lots in the minute, against {g(False, False):.2f} without it.
  * A stop-loss on the first right goes with that move: {C3.fav_ext_share_with.iloc[-1]:.0%} of stop minutes in the biggest adverse bin are also fresh extremes for the other right, against {C3.fav_ext_share_without.iloc[-1]:.0%} of other minutes.
  * The stop adds a smaller lift: stop-only minutes sell {g(True, False):.2f} lots against {g(False, False):.2f} (neither); extreme-only {g(False, True):.2f}; both together {g(True, True):.2f}. The "fresh extreme" gate is my 60-minute definition, so stop-only minutes may contain other spot moves it misses.
  * Within the same size of adverse move, stop-loss minutes still sell more in the larger-move bins, with a CI that excludes zero in {R['c3']['bins_positive_ci']} of the {R['c3']['bins']} bins that have enough stop minutes. **That does not meet my 8-of-10-bin bar**, so I keep it as a common cause with a possible extra effect of the stop, not as a trigger.
* **The quantity does not follow the lots bought.** Sold lots in the next 60 s are about 2 to 2.6 whatever the number of lots bought back (Spearman {c4['spearman']:.2f}). The median is 1 lot. It is not a one-for-one replacement.
* **The strike is the live ATM, not the stopped strike.** {c5['exact_atm']:.0%} are at the ATM of the previous minute's close and {c5['within1']:.0%} within one step. Only {c5['same_strike_as_stopped']:.0%} are at the stopped strike. The premium sold is a median {c5['px_ratio_q'][2]:.2f}× the premium bought back.
* **Which stop events lead to a sale cannot be predicted** from lots bought, hour or time of day (AUC 0.49, 0.49, 0.49, all CIs include 0.5); the buy-back ratio is weak (AUC {C6.set_index('variable').loc['ratio', 'AUC']:.2f}).

**So the "counter-sell" lots (20% of D0 sell lots) look largely like the fresh-extreme solo ladder firing in the same minutes as stop-losses, with a smaller possible extra effect of the stop itself.** *Inferred; the share is not quantified.*

## 1. C1 — which buy-backs go with other-right sales
{table(C1)}
Rates are solo sale orders on the other right within ±90 s per event. Why roll-out, burst and "other" buy-backs also sit above chance was not tested here.

## 2. C2 — timing
{table(C2, 0)}

## 3. C3 — cause or common cause
Minute panel, within bins of the adverse 5-minute spot move (the lowest bins have too few stop minutes):

{table(C3, 2)}

Sold lots, split by stop and by fresh extreme:

{table(C3b, 2)}

## 4. C4 — quantity, C5 — strike, C6 — which events lead to a sale
{table(C4)}

{table(C6, 3)}

## 5. What is not known
* **The exact trigger of the ladder.** The step size and gate were fitted in `D0_SELLS.md` (0.05 step, fresh 60-minute extreme, F1 about 0.38). Nothing here improves that.
* **Whether the stop has its own effect.** The stop-only lift is modest and cannot be separated from intraminute extremes with one-minute bars.
* **Order inside the minute.** Minute bars cannot say whether the sale or the buy-back came first; the 5 s histogram shows the sales spread on both sides.

## Caveats
* **In-sample.** One-minute market bars. Cycle-bootstrap CIs.
* The 8-of-10-bin acceptance bar in the plan was not met (4 of 6 evaluable bins).

## Run order
`bl_d0s_label.py` → `bl_d0y_types.py` → `bl_d0k_counter.py` (~1 min) → `make_d0k_report.py`.
"""
open(os.path.join(RP, 'D0_COUNTER.md'), 'w').write(txt); print('written')
