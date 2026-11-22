"""Builds reports/D0_BUYBACKS.md and figures/bl_d0b_summary.png from the chunk-2 outputs (bl_d0b_*.csv, bl_summary_d0b0..4.json)."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda k: json.load(open(f'{OUT}/bl_summary_{k}.json'))
R0, R1, R2, R3, R4, R5, R6 = J('d0b0'), J('d0b1'), J('d0b2'), J('d0b3'), J('d0b4'), J('d0b5'), J('d0b6')
HZ = pd.read_csv(f'{OUT}/bl_d0b_hazard.csv'); HH = pd.read_csv(f'{OUT}/bl_d0b_hazard_hour.csv'); B3 = pd.read_csv(f'{OUT}/bl_d0b_b3.csv'); B4 = pd.read_csv(f'{OUT}/bl_d0b_b4.csv'); MA = pd.read_csv(f'{OUT}/bl_d0b_mach.csv')
AU = pd.read_csv(f'{OUT}/bl_d0b_auc.csv'); AT = pd.read_csv(f'{OUT}/bl_d0b_auc_type.csv'); SA = pd.read_csv(f'{OUT}/bl_d0b_side_auc.csv'); SS = pd.read_csv(f'{OUT}/bl_d0b_side_size.csv'); SM = pd.read_csv(f'{OUT}/bl_d0b_side_mach.csv')
CH = json.load(open(f'{OUT}/bl_d0b_mach_chosen.json'))
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
m = MA.set_index('machine'); k1 = m.loc['K1 D-1 stop unchanged (high >= 1.6x)']; k2 = m.loc['K2a refit theta and price']; k3 = m.loc['K3 + take-profit']; k5 = m.loc['K5 + block clock']
nsh = m.loc['null: final machine shifted +15 min']; nrd = m.loc['null: rate-matched random minutes']; own = m.loc['secondary: final machine, own-book semantics']
A = AU.set_index('variant'); sa = SA[SA.timing == 'same-minute close'].set_index('variable'); sl = SA[SA.timing != 'same-minute close'].set_index('variable'); sm = SM.set_index('machine')
hzr = HZ[(HZ.price == 'rh') & (HZ.origin == 'all')].set_index('ratio_bin').hazard_pct; g = lambda b: float(hzr[b])
best_side = sa.AUC.idxmax(); HHt = HH.pivot(index='rg', columns='hb', values='hazard_pct').reset_index().rename(columns={'rg': 'ratio (high/entry)'}); grp = R1['by_group']
# ---------------- figure
fig, ax = plt.subplots(2, 2, figsize=(15, 10))
h = HZ[(HZ.price == 'rh')]
for org, c_ in (('all', '#2b6cb0'), ('D-1', '#ed8936'), ('D0', '#48bb78')):
    x = h[h.origin == org]; ax[0, 0].plot(range(len(x)), x.hazard_pct, marker='o', label={'all': 'all lots', 'D-1': 'carried from D-1', 'D0': 'sold on D0'}[org], color=c_)
ax[0, 0].set_xticks(range(len(x))); ax[0, 0].set_xticklabels([b.replace('(', '').replace(']', '').replace(', ', '–') for b in x.ratio_bin], rotation=60, fontsize=7); ax[0, 0].set_ylabel('% of open lot-minutes bought back')
ax[0, 0].set_xlabel('lot premium (minute high) / entry'); ax[0, 0].legend(fontsize=8); ax[0, 0].set_title('Buy-back hazard by the lot\'s own premium ratio (D0, before 15:10)', fontsize=10)
b = [('D-1 stop\nunchanged 1.6x', k1.F1), ('refit\n1.4x', k2.F1), ('+ take-profit\n0.1x', k3.F1), ('side band\n+ K3 (own book)', float(sm.loc['band + K3'].F1)), ('K3 own book', float(sm.loc['K3 alone (own-book, reference)'].F1)), ('null:\n+15 min', nsh.F1), ('null:\nrandom minutes', nrd.F1)]
ax[0, 1].bar(range(len(b)), [x[1] for x in b], color=['#a0aec0', '#2b6cb0', '#2b6cb0', '#2b6cb0', '#2b6cb0', '#cbd5e0', '#cbd5e0']); ax[0, 1].set_xticks(range(len(b))); ax[0, 1].set_xticklabels([x[0] for x in b], fontsize=8)
for k, x in enumerate(b): ax[0, 1].text(k, x[1] + .01, f'{x[1]:.2f}', ha='center')
ax[0, 1].set_ylim(0, .7); ax[0, 1].set_title('Buy-back machines: out-of-fold lot F1 (minute ±1)', fontsize=10)
v = list(sa.index); ax[1, 0].barh(range(len(v)), sa.AUC.values, color='#2b6cb0', label='same-minute'); ax[1, 0].barh(np.arange(len(v)) + .4, sl.loc[v].AUC.values, .4, color='#90cdf4', label='previous close')
ax[1, 0].axvline(.5, color='k', lw=.8, ls='--'); ax[1, 0].axvline(.7, color='r', lw=.8, ls=':'); ax[1, 0].set_yticks(np.arange(len(v)) + .2); ax[1, 0].set_yticklabels(v, fontsize=8); ax[1, 0].legend(fontsize=8)
ax[1, 0].set_title('What starts a buy-back burst (>= 3 lots): single-variable AUC', fontsize=10); ax[1, 0].set_xlim(.3, 1)
vv = ['clock only', 'A book ratios only (no market)', 'B completed bars (causal)', 'A same-minute market + book']; ax[1, 1].bar(range(len(vv)), [A.loc[k, 'AUC'] for k in vv], color=['#cbd5e0', '#90cdf4', '#90cdf4', '#2b6cb0'])
for k, kk in enumerate(vv): ax[1, 1].text(k, A.loc[kk, 'AUC'] + .005, f'{A.loc[kk, "AUC"]:.3f}', ha='center')
ax[1, 1].set_xticks(range(len(vv))); ax[1, 1].set_xticklabels(['clock', 'book ratios', 'B causal', 'A same-minute'], fontsize=9); ax[1, 1].set_ylim(.5, 1); ax[1, 1].set_title('D0 buy-back AUC (leave-one-cycle-out)', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0b_summary.png'), dpi=130)
txt = f"""# Algo 8 — D0 chunk 2: body buy-backs

*Plan `D0_BUYBACKS_PLAN.md` (addendum 2b written after B1–B5, before its tests). In-sample: D0 of 30 cycles. Out-of-fold = cycle halves by parity. Figure: `figures/bl_d0b_summary.png`.*

## 0. Result
* **D0 buy-backs rank at AUC {A.loc['A same-minute market + book', 'AUC']:.3f}** (CI {A.loc['A same-minute market + book', 'ci_lo']:.3f}–{A.loc['A same-minute market + book', 'ci_hi']:.3f}; causal **{A.loc['B completed bars (causal)', 'AUC']:.3f}**). Lower than selling (0.932).
* **The stop on the lot's own premium carries over from D-1, refit lower.**
  * The hazard climbs steadily with the lot's premium high / entry: {g('(1.0, 1.1]'):.1f}% per minute at 1.0–1.1×, {g('(1.5, 1.6]'):.1f}% at 1.5–1.6×, {g('(1.7, 1.8]'):.0f}% at 1.7–1.8×.
  * The best single threshold is **1.4× on the minute high** (D-1: 1.6×). Out-of-fold lot F1 {k2.F1:.3f}, against {k1.F1:.3f} for the D-1 stop unchanged.
* **A take-profit exists on D0** (not on D-1): a lot whose premium falls to 0.1× of entry is bought back. With it, lot F1 is **{k3.F1:.3f}** (recall of deep-profit lots {k3.recall_deep:.0%}), against nulls of {nsh.F1:.3f} (+15 min) and {nrd.F1:.3f} (random minutes).
* **Most D0 buy-back lots come in bursts that cut a side, not one lot at a time.** {{ADD_BURST}}
* **Straddle partners again.** {B4[(B4.group == 'mid-profit') & (B4.context == 'partner')].share.iloc[0]:.0%} of mid-profit buy-backs have a same-strike loss buy-back on the other right within ±60 s (null {B4[(B4.group == 'mid-profit') & (B4.context == 'partner')].null.iloc[0]:.0%}), as on D-1. But a partner rule adds nothing to lot F1.
* **Only half of all D0 buy-back lots are in loss** ({R0['in_loss']:.0%}; D-1: 87%). The rest:
  * the 15:10+ clearance (chunk 4);
  * afternoon cover-backs of decayed lots;
  * partners.

## 1. Population
* {R0['bb_lots']:,} D0 body buy-back lots, {R0['by_origin']['D-1']:,} of them on lots carried from D-1.
* In scope (before 15:10 and before the cycle's stop): {R1['lots_in_scope']:,} lots:
  * loss {grp['loss']:,};
  * mid-profit {grp['mid-profit']:,};
  * deep-profit {grp['deep-profit']:,}.
* **Lot convention.** The highest-ratio open lot on the contract is removed (D-1 convention). FIFO assigns a different origin for {1 - R0['origin_agree_fifo']:.0%} of lots, and gives {R0['in_loss_fifo']:.0%} in loss instead of {R0['in_loss']:.0%}.

## 2. Hazard by the lot's own premium (B1)
{table(HZ[(HZ.price == 'rh') & (HZ.origin == 'all')][['ratio_bin', 'hazard_pct', 'lot_minutes', 'events']], 2)}

**By hour block and ratio (hazard % per lot-minute):**

{table(HHt, 2)}

* The hazard is **graded**: there is no single wall.
* Above 2× in the afternoon it reaches 19% per minute.
* Below 0.25× it is near zero until 13:00, then 0.6%. This is the take-profit.

## 3. Machines (B2)
* Teacher-forced on the real book: real sells, and lots leave at their real buy-back.
* Out-of-fold, cycle halves. Lot F1 at ±1 minute.

{table(MA[['machine', 'F1', 'ci_lo', 'ci_hi', 'precision', 'recall', 'sim_lots', 'real_lots', 'recall_loss', 'recall_mid', 'recall_deep']])}

* Chosen per half: {' ; '.join(CH['K5 + block clock'])}.
* Per-hour-block θ and per-origin θ do not help out-of-fold. The partner and block-clock steps were not chosen on either training half.
* `recall_*` = recall of that group's lots against all predictions (optimistic per group).
* Own-book semantics (a lot leaves only at the machine's own exit, as in a simulator) gives {own.F1:.3f}.

## 4. Clock (B3) and context (B4)
{table(B3)}

{table(B4)}

* **Clocking is moderate.** About 11–12% of lots fall in the last minute of a 15-minute block and 12% in the first minute of the next, against 6.7% uniform. 13% are at second :00.
* **Mid-profit lots are often partners or rolls.** Partner {B4[(B4.group == 'mid-profit') & (B4.context == 'partner')].share.iloc[0]:.0%} vs {B4[(B4.group == 'mid-profit') & (B4.context == 'partner')].null.iloc[0]:.0%}; same-right sale within 60 s {B4[(B4.group == 'mid-profit') & (B4.context == 'roll')].share.iloc[0]:.0%} vs {B4[(B4.group == 'mid-profit') & (B4.context == 'roll')].null.iloc[0]:.0%}. The two overlap.

## 5. Bursts and side-level triggers (addendum 2b)
**What starts a burst (≥ 3 lots), single-variable AUC:**

{table(SA)}

**Burst size (Spearman):**

{table(SS)}

**Rebalancing band machine** (own-book semantics; band and fraction fitted on one half):

{table(SM)}

{{ADD_SIDE}}

## 5b. Lots carried from D-1 (addendum 2c, post-hoc)
* **Carried lots barely follow their own premium.** Their hazard is flat (about 1–3.7% per minute from 1.5× upward), against 15–26% for lots sold on D0.
* **Re-basing their stop to the D0 opening premium does not help.**
  * The single-variable AUC on carried lot-minutes is {R6['auc_vs_d0_open']:.3f} against the D0 open and {R6['auc_vs_d1_entry']:.3f} against the D-1 entry (difference CI {R6['auc_diff_ci'][0]:+.3f} to {R6['auc_diff_ci'][1]:+.3f}).
  * Out-of-fold machine F1 is {R6['F1_d0_open']:.3f} against {R6['F1_d1_entry']:.3f} (paired difference CI {R6['F1_diff_ci'][0]:+.3f} to {R6['F1_diff_ci'][1]:+.3f}). **Rejected.**
* What drives carried-lot buy-backs is unresolved. {R5['origin_D1_share_by_time']['09:15-09:30']:.0%} of all D0 buy-back lots in 09:15–09:30 are carried lots, against {R5['origin_D1_share_by_time']['12:00-14:00']:.0%} in 12:00–14:00. Their AUC is near chance on either reference.

{table(pd.read_csv(f'{OUT}/bl_d0b_carry_hz.csv').pivot(index='ratio_bin', columns='reference', values='hazard_pct').reset_index(), 2)}

## 6. One ranking number (B5)
{table(AU)}

**By group:**

{table(AT)}

## 7. Kept and rejected
{{ADD_DEC}}

## 8. Caveats
* **In-sample.** 30 cycles. The structure was found on the same cycles. Scores are out-of-fold over halves.
* **Lot convention.** Buy-backs remove the highest-ratio lot. FIFO would change the lot ratios (Section 1).
* **Teacher-forced.**
  * The book is real (real sells and, in B2, real removals).
  * The stop time is real (chunk 4 decodes it).
  * The 15:10+ clearance is excluded (chunk 4).
* **Matcher.** Lot F1 uses minute and right only (histogram matcher: exact minute, then ±1).
* **Post-hoc.** Addendum 2b was written after B1–B5 and a descriptive look at bursts; addendum 2c after the B1 figure.

## Run order
`bl_d0b_ledger.py` → `bl_d0b_tests.py` (~2 min) → `bl_d0b_mach.py` → `bl_d0b_auc.py` (~1 min) → `bl_d0b_side.py` (~7 min) → `bl_d0b_burst.py` → `bl_d0b_carry.py` (~3 min) → `make_d0b_report.py`. Outputs `outputs/bl_d0b_*`, `bl_summary_d0b0…6.json`.
"""
bs = SS[(SS.bursts == 'bursts >= 3 lots')].set_index('variable').spearman; bm = sm.loc['band + K3']; ka = sm.loc['K3 alone (own-book, reference)']; ba = sm.loc['band alone']
EXTRA = dict(
 ADD_BURST=f"Bursts of 5+ lots ({R5['big_bursts']}) carry {R5['big_lot_share']:.0%} of in-scope buy-back lots. A typical one spans {R5['big_strikes_q'][0]:.0f} strikes (90th percentile {R5['big_strikes_q'][1]:.0f}) and takes {R5['big_share_open_q'][1]:.0%} of the right's open lots (IQR {R5['big_share_open_q'][0]:.0%}–{R5['big_share_open_q'][2]:.0%}). {R5['big_mixed_profit_loss']:.0%} contain both profit and loss lots, and a burst takes only {R5['big_completeness_q'][1]:.0%} (median) of the lots above its lowest ratio. **What starts a burst is not found:** the best single variable is the adverse 5-minute spot move (AUC {sa.loc['adv_mv5', 'AUC']:.2f}; halves {sa.loc['adv_mv5', 'AUC_half_even']:.2f} / {sa.loc['adv_mv5', 'AUC_half_odd']:.2f}). Premium imbalance, delta share and the side's loss do not reach 0.70. *Unresolved.*",
 ADD_SIDE=f"* **No side-level trigger.** No variable reaches the pre-set AUC 0.70 in both halves. The adverse spot move ({sa.loc['adv_mv5', 'AUC']:.3f}) and premium imbalance ({sa.loc['prem_imb', 'AUC']:.3f}) are the strongest; the side's unrealised loss is at chance ({sa.loc['unreal_loss', 'AUC']:.3f}).\n* **Burst size** follows the number of lots above 1.4× (ρ {bs['n_above14']:.2f}) and premium imbalance (ρ {bs['prem_imb']:.2f}), not the open lots (ρ {bs['n_open']:.2f}).\n* **The band machine adds nothing.** With K3, F1 {bm.F1:.3f}, against K3 alone {ka.F1:.3f} (both own-book). Alone it scores {ba.F1:.3f}.\n* **Reading (Inferred).** The bursts are where several lots cross the stop together during an adverse move. The size of each cut is a separate decision that these variables do not recover.",
 ADD_DEC=table(pd.DataFrame([
  ('Own-premium stop, D-1 level 1.6× unchanged', f"F1 {k1.F1:.3f}", 'carries over (weaker)', 'Observed'),
  ('Own-premium stop refit: 1.4× on the minute high', f"F1 {k2.F1:.3f}", 'kept', 'Observed'),
  ('Take-profit: premium ≤ 0.1× entry', f"F1 {k3.F1:.3f} (deep-profit recall {k3.recall_deep:.0%})", 'kept', 'Observed'),
  ('θ per hour block / per origin', 'no out-of-fold gain', 'rejected', 'Observed'),
  ('Same-strike partner buy-back', f"context {B4[(B4.group == 'mid-profit') & (B4.context == 'partner')].share.iloc[0]:.0%} vs null {B4[(B4.group == 'mid-profit') & (B4.context == 'partner')].null.iloc[0]:.0%}; no F1 gain", 'structure kept, rule rejected', 'Observed'),
  ('Block clock (minutes 14 / 0)', '~1.8× uniform; no F1 gain', 'descriptive only', 'Observed'),
  ('Side-level trigger (imbalance, delta, side loss, spot move)', 'no AUC ≥ 0.70 in both halves', 'rejected / unresolved', 'Observed'),
  ('Carried lots: stop re-based to the D0 open (post-hoc)', f"F1 {R6['F1_d0_open']:.3f} vs {R6['F1_d1_entry']:.3f}", 'rejected', 'Observed'),
  ('Final machine vs nulls', f"{k5.F1:.3f} vs {nsh.F1:.3f} (+15 min) / {nrd.F1:.3f} (random)", 'passes (1.8× random)', 'Observed'),
 ], columns=['rule', 'result', 'decision', 'evidence'])))
for k in ('ADD_BURST', 'ADD_SIDE', 'ADD_DEC'): txt = txt.replace('{' + k + '}', EXTRA[k])
open(os.path.join(RP, 'D0_BUYBACKS.md'), 'w').write(txt); print('written', len(txt))
