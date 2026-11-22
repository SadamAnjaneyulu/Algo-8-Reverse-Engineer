"""Builds reports/D0_BB_TYPES.md and figures/bl_d0y_summary.png from bl_d0y_*.csv and bl_summary_d0y1/2.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R1 = json.load(open(f'{OUT}/bl_summary_d0y1.json')); R2 = json.load(open(f'{OUT}/bl_summary_d0y2.json'))
T = pd.read_csv(f'{OUT}/bl_d0y_types.csv'); CH = pd.read_csv(f'{OUT}/bl_d0y_chance.csv'); H = pd.read_csv(f'{OUT}/bl_d0y_hours.csv', index_col=0); E = pd.read_csv(f'{OUT}/bl_d0y_entrymix.csv', index_col=0); Q1 = pd.read_csv(f'{OUT}/bl_d0y_q1.csv').set_index('type')
HD = pd.read_csv(f'{OUT}/bl_d0y_hold.csv'); SE = pd.read_csv(f'{OUT}/bl_d0y_sens.csv'); AD = pd.read_csv(f'{OUT}/bl_d0y_other.csv'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); OV = pd.read_csv(f'{OUT}/bl_d0y_overlap.csv', index_col=0)
def table(df, fmt=2):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
t = T.set_index('type'); tot = int(T.lots.sum()); sh = lambda k: t.loc[k, 'share']; mi = lambda k: t.loc[k, 'median_time']
COL = {'1 cycle-stop window': '#718096', '2a clearance 15:10-15:13': '#a0aec0', '2b clearance 15:14': '#4a5568', '2c clearance 15:15+': '#cbd5e0', '3 stop-loss': '#e53e3e', '4 take-profit': '#38a169', '5 partner': '#d69e2e', '6 roll-out': '#9f7aea', '7 burst member': '#3182ce', '8 other': '#ed8936'}
fig, ax = plt.subplots(1, 3, figsize=(20, 6.2)); o = list(T.type)
ax[0].barh(range(len(o)), T.lots, color=[COL[k] for k in o]); ax[0].set_yticks(range(len(o))); ax[0].set_yticklabels(o, fontsize=8); ax[0].invert_yaxis()
for k, (v, s) in enumerate(zip(T.lots, T.share)): ax[0].text(v + 20, k, f'{v:,} ({s:.0%})', va='center', fontsize=8)
ax[0].set_xlim(0, T.lots.max() * 1.3); ax[0].set_title(f'D0 body buy-back lots by reason ({tot:,} lots)', fontsize=10)
for k, nm in enumerate(o):
    g = X[X.type == nm].ratio.clip(upper=3); q = g.quantile([.1, .25, .5, .75, .9]).values; ax[1].plot([q[0], q[4]], [k, k], color=COL[nm], lw=1.5); ax[1].plot([q[1], q[3]], [k, k], color=COL[nm], lw=8, solid_capstyle='butt'); ax[1].plot(q[2], k, 'o', color='white', ms=5, mec='k')
ax[1].axvline(1.0, color='gray', lw=.8, ls=':'); ax[1].axvline(1.4, color='red', lw=.8, ls='--'); ax[1].set_yticks(range(len(o))); ax[1].set_yticklabels([]); ax[1].invert_yaxis(); ax[1].set_xlabel('premium at buy-back ÷ entry premium  (red dashes = 1.4×, dotted = 1.0×; bar = 25–75%, line = 10–90%)'); ax[1].set_title('Price ratio at the buy-back', fontsize=10)
bot = np.zeros(len(H))
for nm in o:
    if nm in H: ax[2].bar(H.index, H[nm].values, bottom=bot, color=COL[nm], label=nm, width=.8); bot += H[nm].values
ax[2].set_xlabel('hour of day'); ax[2].legend(fontsize=7, ncol=2); ax[2].set_title('When they happen', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0y_summary.png'), dpi=115); plt.close()
# scheduled-straddle entries
sch = E.loc[:, [c for c in ('grid_pair', 'offgrid_pair', 'scheduled') if c in E]].sum(axis=1); schs = (sch / sch.sum()).rename('share of scheduled-straddle lots').reset_index(); schs['lots'] = sch.values
ch = CH.set_index('type'); ads = AD.set_index(['type', 'window_min']); roll = R1['rollout_solo_sales_only']; q2 = R1['q2_exact_hold_share']
a5 = lambda ty: ads.loc[(ty, 5)]
reasons = pd.DataFrame([
    ('Stop-loss', f"{sh('3 stop-loss'):.0%}", f"premium high ≥ 1.4× the lot's own entry; median {t.loc['3 stop-loss', 'ratio_median']:.2f}×, {Q1.loc['3 stop-loss', 'ratio_ge_1p4']:.0%} at or above 1.4×, {Q1.loc['3 stop-loss', 'ratio_ge_1p2']:.0%} at or above 1.2×", f"spot moved against the short {a5('3 stop-loss').adverse_move_steps_mean:.2f} steps in 5 min (random minutes {a5('3 stop-loss').null_mean:.2f})", 'Observed (the D-1 stop, refit lower)'),
    ('Take-profit', f"{sh('4 take-profit'):.0%}", f"premium low ≤ 0.1× entry; median {t.loc['4 take-profit', 'ratio_median']:.2f}×; {t.loc['4 take-profit', 'carried_from_D1']:.0%} are lots carried from D-1", 'spot moves slightly the lot\'s way', 'Observed (new on D0)'),
    ('Clearance', f"{sh('2a clearance 15:10-15:13') + sh('2b clearance 15:14') + sh('2c clearance 15:15+'):.0%}", f"from 15:10; mostly in profit (median {t.loc['2b clearance 15:14', 'ratio_median']:.2f}×); 15:14 alone {sh('2b clearance 15:14'):.0%}", 'time only', 'Observed'),
    ('Cycle-stop window', f"{sh('1 cycle-stop window'):.0%}", 'body buy-backs at or after the cycle stop', 'the cycle loss limit', 'Observed (chunk 4)'),
    ('Partner', f"{sh('5 partner'):.0%}", f"other right, same strike, within ±60 s of a stop-loss; {ch.loc['5 partner', 'ratio_vs_10min']:.1f}× chance ({ch.loc['5 partner', 'ratio_vs_15min']:.1f}× with the clock kept)", 'the partner leg of a stopped straddle', 'Observed'),
    ('Burst member', f"{sh('7 burst member'):.0%}", f"in a burst of ≥ 5 lots on one right; median ratio {t.loc['7 burst member', 'ratio_median']:.2f}×, mixed profit and loss", f"mild: {a5('7 burst member').adverse_move_steps_mean:.2f} steps against (random {a5('7 burst member').null_mean:.2f})", 'Unresolved trigger'),
    ('Roll-out', f"{sh('6 roll-out'):.0%}", f"a body sale on the same right within 60 s after; {ch.loc['6 roll-out', 'ratio_vs_10min']:.1f}× chance by ±10 min shift but only {ch.loc['6 roll-out', 'ratio_vs_15min']:.1f}× with the clock kept", 'weak', 'Not kept (below the 1.5× bar)'),
    ('Other', f"{sh('8 other'):.0%}", f"none of the above; ratio {t.loc['8 other', 'ratio_q10']:.2f}–{t.loc['8 other', 'ratio_q90']:.2f}× (10–90%); only {Q1.loc['8 other', 'ratio_ge_1p4']:.1%} reach 1.4×", f"mild: {a5('8 other').adverse_move_steps_mean:.2f} steps against (random {a5('8 other').null_mean:.2f})", 'Unresolved'),
], columns=['reason', 'share of buy-back lots', 'what identifies it', 'market at that minute', 'status'])
txt = f"""# Algo 8 — D0 buy-backs: every reason, open to close

*Plan `D0_BB_TYPES_PLAN.md` (written before the classification; one post-hoc addendum on the chance level). In-sample: D0 of the 30 cycles, {tot:,} body buy-back lots. Figure: `figures/bl_d0y_summary.png`. Scripts `bl_d0y_types.py`, `bl_d0y_other.py`.*

## 0. Result: five reasons explain about two thirds of D0 buy-backs; about a third has no firm reason
{table(reasons)}

* **The 1.2× question.** On D-1 the stop sits at about 1.6×. On D0:
  * the stop-loss type starts at **1.4×** (the fitted threshold). {Q1.loc['3 stop-loss', 'ratio_ge_1p2']:.0%} of stop-loss lots are at or above 1.2×, and {Q1.loc['3 stop-loss', 'ratio_ge_1p6']:.0%} at or above 1.6×;
  * a stop at 1.2× would label {int(SE[SE.threshold == 1.2].stop_loss.iloc[0]):,} lots as stop-loss, against {int(SE[SE.threshold == 1.4].stop_loss.iloc[0]):,} at 1.4× and {int(SE[SE.threshold == 1.6].stop_loss.iloc[0]):,} at 1.6×;
  * lots bought back between 1.0× and 1.4× with no stop-loss reason are the "burst", "roll-out" and "other" lots. They are not a pile-up at 1.0×: {R2['near1']['in_0p95_1p05']:.0%} are within ±5% of entry, against {R2['near1']['in_0p85_0p95']:.0%} and {R2['near1']['in_1p05_1p15']:.0%} in the neighbouring bins.
* **About half of all buy-back lots are not stops.** {Q1.loc['ALL', 'ratio_lt_1']:.0%} are bought back below their entry price (in profit), and {Q1.loc['ALL', 'ratio_lt_0p25']:.0%} below a quarter of it.
  * The reasons are the clearance ({sh('2a clearance 15:10-15:13') + sh('2b clearance 15:14') + sh('2c clearance 15:15+'):.0%}), the take-profit ({sh('4 take-profit'):.0%}) and the partner legs.
* **No fixed holding time.** For the {R1['q2_lots']:,} lots that entered in a scheduled pair on D0, no holding duration stands out.
  * Exactly 5 / 10 / 15 / 30 / 60 minutes are each below 1% of lots.
  * Only buy-backs within 0–2 minutes of the sale are above chance (55 lots, 3%).
* **Buy-backs are not tied to the 5-minute marks.** {R1['q3_in_133s_after_5min_mark']:.0%} fall in the 133 s after a 5-minute mark, against {R1['q3_uniform_expectation']:.0%} expected by chance.
  * Outside the clearance and the stop window, the last and first minute of each 15-minute block hold {R2['q3_core_block_minute14']:.0%} and {R2['q3_core_block_minute0']:.0%} of lots, against 6.7% if uniform.

## 1. All types
{table(T.rename(columns={'ratio_q10': 'ratio 10%', 'ratio_q25': '25%', 'ratio_median': 'median', 'ratio_q75': '75%', 'ratio_q90': '90%', 'held_min_median': 'held (min), median', 'carried_from_D1': 'carried from D-1'})[['type', 'lots', 'share', 'cycles', 'ratio 10%', '25%', 'median', '75%', '90%', 'share_in_loss', 'held (min), median', 'carried from D-1', 'CE_share', 'median_time']])}

*Types are assigned by precedence (stop window, clearance, stop-loss, take-profit, partner, roll-out, burst, other). The overlap of the raw flags is in `bl_d0y_overlap.csv`.*

**Chance levels for the trigger-based types:**

{table(CH, 3)}

* **Partner passes** (3× chance under both shifts).
* **Roll-out does not.** It is 2.0× chance with the ±10-minute shift, but 1.4× once the shift keeps the 15-minute clock. Counting only sales that are not scheduled pairs it is {roll['share']:.0%} against {roll['chance_15min']:.0%} chance (1.5×, borderline).

## 2. The market at the buy-back minute
Mean adverse spot move over the previous 5 / 15 minutes, in strike steps (CE short: spot up; PE short: spot down), against random minutes of the same cycle and hour:

{table(AD, 3)}

* **Stop-loss lots follow an adverse move**: {a5('3 stop-loss').share_adverse:.0%} of them, against {a5('3 stop-loss').null_share_adverse:.0%} for random minutes.
* **Burst and "other" lots show a mild adverse move**, about a fifth of a step. That is too weak to call a trigger.
* **Partner lots follow a favourable move for their own right**, as expected for the other leg of a stopped straddle.

## 3. Scheduled straddles
Reason, for the lots that entered in a scheduled pair or a D0 pair (grid or off-grid):

{table(pd.DataFrame(dict(reason=X.type.unique())).merge(X[X.typ.isin(['grid_pair', 'offgrid_pair', 'scheduled'])].groupby('type').size().rename('lots').reset_index(), left_on='reason', right_on='type', how='left').drop(columns='type').fillna(0).assign(share=lambda d: d.lots / d.lots.sum()).sort_values('reason'), 3)}

Entry mix of every reason (columns = how the lot was sold):

{table(E.reset_index().rename(columns={'type': 'reason'}), 0)}

## 4. Holding time of scheduled-pair lots
{table(HD)}

Only the 1–2 minute bin sits clearly above chance (the quick exits). Everything else is within the null.

## 5. What is not known
* **The trigger of the burst lots** ({sh('7 burst member'):.0%}) and of the "other" lots ({sh('8 other'):.0%}). They are lots bought back at ratios from about 0.3× to 1.3× in groups, with no price level, holding time or clock that identifies them.
  * "Other" is concentrated in the 14:00 hour ({R2['other_hours'].get('14', 0)} of {int(t.loc['8 other', 'lots'])} lots), and {R2['other_entry_mix'].get('solo', 0) / t.loc['8 other', 'lots']:.0%} entered as solo sales.
* **Why the stop-loss threshold is 1.4× on D0 and about 1.6× on D-1.** It is a fitted value, with a graded hazard rather than a wall.
* **Lots carried from D-1.** Their buy-backs are mostly take-profit and clearance, and barely follow their own price (chunk 2).

## Caveats
* **In-sample.** All 30 cycles. Types are assigned lot by lot, so a lot with several possible reasons gets the first by precedence.
* **Ratios use the decision price.** The minute-high and minute-low tests use one-minute bars; the true intraminute path is not observed.
* **Post-hoc.** The clock-preserving chance level, and the near-1.0 and spot-move checks.

## Run order
`bl_d0b_ledger.py` → `bl_d0b_tests.py` (panel) → `bl_d0y_types.py` (~1 min) → `bl_d0y_other.py` → `make_d0y_report.py`.
"""
open(os.path.join(RP, 'D0_BB_TYPES.md'), 'w').write(txt); print('written', len(txt))
