"""Builds reports/D0_REPL.md and figures/bl_d0e_summary.png."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); C = lambda n: pd.read_csv(f'{OUT}/{n}.csv'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json'))
E1, MS, LG, E2, E3, FW, HR, CD, SEP, PXD, LAD, CK1, CKA, SMR, TT, FA, RLB = [C(n) for n in ('bl_d0e_e1', 'bl_d0e_e1_mech', 'bl_d0e_e1_lag', 'bl_d0e_e2', 'bl_d0e_e3', 'bl_d0e_e3_fwd', 'bl_d0e_hours', 'bl_d0e_cond', 'bl_d0e_sep', 'bl_d0e_px', 'bl_d0e_ladder', 'bl_d0e_clock1', 'bl_d0e_clock_auc', 'bl_d0e_str_summary', 'bl_d0e_str_tt', 'bl_d0e_fin_auc', 'bl_d0e_fin_relabel')]
R4, R5 = J('d0e4'), J('d0e5'); PR = C('bl_d0e_str_pairs'); STR = PR[PR.dk == 2]
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
fa = FA.set_index('model').loc[:, :]; sA = FA[FA.outcome == 'y_strangle'].set_index('model'); e3 = E3.set_index(['slice', 'variant']); fw = FW.set_index(['slice', 'variant']); v1 = 'V1 causal (bars to j-1, orders before minute j)'
cks = CK1.set_index('slice'); tto = R4['timetable_oof']
# ---------------- figure
fig, ax = plt.subplots(2, 2, figsize=(17, 11)); a = ax[0, 0]; g = PR[PR.dk == 2]; cyc = {c: n for n, c in enumerate(sorted(g.cid.unique()))}; a.scatter(g.tod / 3600, g.cid.map(cyc), s=6, color='#2b6cb0'); a.set_xlabel('time of day (hours)'); a.set_ylabel('cycle (SENSEX, before 16 Sep)'); a.set_title('A. The strangle clock: the same seconds in every cycle', fontsize=10)
a = ax[0, 1]; H = HR[['counter-sell solo', 'replacement solo', 'other solo', 'far-OTM solo']]; bt = np.zeros(len(H)); col = {'counter-sell solo': '#2b6cb0', 'replacement solo': '#e53e3e', 'other solo': '#d69e2e', 'far-OTM solo': '#805ad5'}
for k in H.columns: a.bar(HR.hour, H[k], bottom=bt, color=col[k], label=k); bt += H[k].values
a.legend(fontsize=8); a.set_xlabel('hour of day'); a.set_ylabel('lots'); a.set_title('B. When: replacement is an afternoon stream, other solo is midday', fontsize=10)
a = ax[1, 0]; rows = [('strangle cells\n(V1 + clock)', sA.loc['V1 + clock feature']), ('replacement solo\n(V1)', None), ('counter-sell\n(no strangle legs)', FA[FA.outcome == 'y_counter_ns'].iloc[0]), ('other solo\n(no strangle legs)', FA[FA.outcome == 'y_other_ns'].iloc[0]), ('far-OTM solo\n(V1)', None)]
vals = [sA.loc['V1 + clock feature', 'auc'], e3.loc[('replacement solo', v1), 'auc'], FA[FA.outcome == 'y_counter_ns'].auc.iloc[0], FA[FA.outcome == 'y_other_ns'].auc.iloc[0], e3.loc[('far-OTM solo', v1), 'auc']]; fwd = [sA.loc['V1 + clock feature', 'forward_auc'], fw.loc[('replacement solo', v1), 'auc'], FA[FA.outcome == 'y_counter_ns'].forward_auc.iloc[0], FA[FA.outcome == 'y_other_ns'].forward_auc.iloc[0], np.nan]
a.bar(np.arange(5) - .2, vals, .4, color='#2b6cb0', label='leave-one-cycle-out'); a.bar(np.arange(5) + .2, fwd, .4, color='#d69e2e', label='forward (first 16 → last 8)'); a.axhline(.85, color='r', ls='--'); a.set_xticks(range(5)); a.set_xticklabels([r[0] for r in rows], fontsize=8); a.set_ylim(.5, 1); a.legend(fontsize=8, loc='lower left'); a.set_ylabel('AUC, causal'); a.set_title('C. The 0.85 gate (far-OTM: cycle-level, no forward test)', fontsize=10)
a = ax[1, 1]; r = RLB.set_index('slice'); order = ['other solo', 'counter-sell solo', 'replacement solo', 'opening solo', 'extreme solo', 'far-OTM solo']; a.barh(range(len(order)), [r.loc[s, 'not a strangle leg'] for s in order], color='#a0aec0', label='not a strangle leg'); a.barh(range(len(order)), [r.loc[s, 'strangle leg'] for s in order], left=[r.loc[s, 'not a strangle leg'] for s in order], color='#e53e3e', label='strangle leg'); a.set_yticks(range(len(order))); a.set_yticklabels(order, fontsize=9); a.invert_yaxis(); a.legend(fontsize=8); a.set_xlabel('D0 sell lots'); a.set_title('D. Where the strangle legs were hiding (1,252 lots)', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0e_summary.png'), dpi=115); plt.close()
# ---------------- report
e1 = E1.set_index('reason'); mech = MS.set_index('group'); m1 = mech.iloc[0]; m0 = mech.iloc[1]; sep = SEP.head(5); px = PXD.set_index('group')
txt = f"""# Algo 8 — D0 solo selling after the counter-sells: a hidden strangle timetable, and the replacement stream

*Plan `D0_REPL_PLAN.md` (with an addendum for the post-hoc steps and one error caught on the way). In-sample discovery on D0, 24 cycles with minutes after the opening window (14,762 minute cells). Figure: `figures/bl_d0e_summary.png`. Scripts `bl_d0e_*.py`.*

## 0. Result
**1. About 15% of all D0 sell lots are a second scheduled timetable that we had mislabelled as solo selling.** In the SENSEX version before 16 Sep, at recurring seconds, the system sells **a call one step above ATM and a put one step below ATM within about a second of each other**: a strangle. 626 such pairs, **{R4['strangle_lots']:,} lots = {R4['share_of_d0_sell_lots']:.1%} of D0 sell lots**, in 10 cycles. The pair detector had required the same strike, so these legs fell into "other solo", "counter-sell", "replacement" and "opening solo". *Observed.*

| | Result | Label |
|---|---|---|
| **Strikes** | CE at ATM + 1 step and PE at ATM − 1 step (ATM of the previous minute's close): exact in **{R4['strike_rule_exact']:.0%}** of {R4['strangle_pairs']} pairs; the legs are {STR.lag.abs().quantile(.95):.0f} s apart or less in 95%. | Observed |
| **Clock** | The same seconds in every cycle (Figure A). Timetable learned on one half of the cycles and scored on the other: precision **{tto['precision']:.0%}**, recall **{tto['recall']:.0%}**, F1 **{tto['f1']:.2f}** (pair timing ±3 s). The learned timetable has {int(TT.waves.iloc[1])}–{int(TT.waves.iloc[0])} waves. | Observed |
| **AUC gate (strangle cells)** | **{sA.loc['V1 + clock feature','auc']:.3f}** (CI {sA.loc['V1 + clock feature','lo']:.3f}–{sA.loc['V1 + clock feature','hi']:.3f}), within-cycle {sA.loc['V1 + clock feature','within_cycle_auc']:.3f}, forward **{sA.loc['V1 + clock feature','forward_auc']:.3f}**; the clock alone gives {sA.loc['clock feature only (strangle times of other cycles)','auc']:.3f}; placebo {sA.loc['placebo (clock + position shuffled within cycle)','auc']:.2f}. **Gate met.** | Observed |
| **Where it was hiding** | {R5['strangle_by_slice'].get('other solo',0)} of the 1,105 "other solo" lots (64%), plus {R5['strangle_by_slice'].get('counter-sell solo',0)} counter-sell, {R5['strangle_by_slice'].get('replacement solo',0)} replacement, {R5['strangle_by_slice'].get('opening solo',0)} opening-solo and {R5['strangle_by_slice'].get('extreme solo',0)} extreme-solo lots. It is {R5['sensex_v1_strangle_share']:.0%} of all solo lots of that version. | Observed |
| **Counter-sell result survives** | With the strangle legs removed from the outcome the causal counter-sell AUC is **{FA[FA.outcome=='y_counter_ns'].auc.iloc[0]:.3f}** (CI {FA[FA.outcome=='y_counter_ns'].lo.iloc[0]:.3f}–{FA[FA.outcome=='y_counter_ns'].hi.iloc[0]:.3f}), within-cycle {FA[FA.outcome=='y_counter_ns'].within_cycle_auc.iloc[0]:.3f}, forward {FA[FA.outcome=='y_counter_ns'].forward_auc.iloc[0]:.3f} (`D0_CAUC.md`: 0.882). | Observed |
| **Replacement solo** | AUC **{e3.loc[('replacement solo', v1),'auc']:.3f}** (CI {e3.loc[('replacement solo', v1),'lo']:.3f}–{e3.loc[('replacement solo', v1),'hi']:.3f}), within-cycle {e3.loc[('replacement solo', v1),'within_cycle_auc']:.3f}, forward **{fw.loc[('replacement solo', v1),'auc']:.3f}**: **gate met.** It is an **afternoon stream inside buy-back clusters**, not a one-for-one replacement (§2). | Observed |
| **Other solo that is left** | {R4['other_solo_left_lots']} lots ({R4['other_solo_left_lots']/8336:.1%} of D0 sells). Causal AUC **{FA[FA.outcome=='y_other_ns'].auc.iloc[0]:.3f}** (CI {FA[FA.outcome=='y_other_ns'].lo.iloc[0]:.3f}–{FA[FA.outcome=='y_other_ns'].hi.iloc[0]:.3f}), within-cycle {FA[FA.outcome=='y_other_ns'].within_cycle_auc.iloc[0]:.3f}: **gate not met.** | Observed; Unresolved |
| **Far-OTM roll-out** | Not judged. 12 cycles, mostly SENSEX before 16 Sep; the pooled AUC (0.958) is a cycle-level effect (placebo {e3.loc[('far-OTM solo','placebo (V1 features shuffled within cycle)'),'auc']:.2f}, within-cycle {e3.loc[('far-OTM solo', v1),'within_cycle_auc']:.2f}) and no test cycle has one. | Unresolved |

## 1. The strangle timetable (post-hoc finding)
* **How it was found.** The "other solo" slice repeated at the same clock seconds across cycles ({cks.loc['other solo','ratio']:.1f}× the shifted-time chance, pooled; the recurrence is concentrated in SENSEX before 16 Sep, so only {int(cks.loc['other solo','cycles_above_null'])} of {int(cks.loc['other solo','cycles'])} cycles are above chance), while the market conditions that drive other solo sales were absent (spot fresh extreme in 2.6% of them). In SENSEX before 16 Sep, 73% had an opposite-right sale within 3 s. In all 304 pairs examined first, the call strike was exactly two steps above the put strike.
* **Detection.** Near-simultaneous CE/PE solo sales with different strikes: strike gap in steps (CE strike minus PE strike), SENSEX before 16 Sep: **2 steps in {int(SMR[(SMR.und=='SENSEX') & (SMR.version=='V1') & (SMR.dk==2)].pairs.sum())} of {int(SMR[(SMR.und=='SENSEX') & (SMR.version=='V1')].pairs.sum())} near-simultaneous pairs**; no other gap has more than 17.

{table(SMR[(SMR.und=='SENSEX') & (SMR.version=='V1') & (SMR.dk.isin([1,2,3,6]))])}
* **Strikes** are the live ATM ± 1 step on the previous minute's close; {R4['both_legs_one_step_otm']:.0%} exact.
* **Timetable** (learned on each half, SENSEX before 16 Sep; first clock times): {TT.clock.iloc[0][:230]} …

## 2. Replacement solo: what it is
* **Not one-for-one.** After a same-right buy-back the sale is at the **same strike as the bought lot in {m1.same_strike_share:.0%}** of cases, the same as for a random same-right solo sale ({m0.same_strike_share:.0%}); further out of the money in {m1.further_otm_share:.0%} ({m0.further_otm_share:.0%} by chance). The premium sold ÷ premium bought has a median {m1.px_ratio_median:.2f} against {m0.px_ratio_median:.2f} by chance, but is spread widely (quartiles {px.loc['all kept reasons','q25']:.2f}–{px.loc['all kept reasons','q75']:.2f}; within ±10% in {px.loc['all kept reasons','within_10pct']:.0%}). Lots sold ÷ lots bought, median {m1.lots_ratio_median:.1f}. *Observed.*
* **Which buy-backs are followed by a same-right sale** (within 60 s, against the same times shifted ±10 and ±15 minutes; kept at ≥1.5× both):

{table(E1)}
  * **Partner legs** ({e1.loc['5 partner','share_with_same_right_sale_0_60s']:.0%} against about 20–25%) and the **cycle-stop window** follow. The "roll-out" row is definitional (the type is a same-right sale within 60 s after the buy-back); "burst" and "other" are 0 by construction for the same reason.
  * **Stop-loss ({e1.loc['3 stop-loss','ratio_10']:.2f}× / {e1.loc['3 stop-loss','ratio_15']:.2f}×), take-profit and clearance buy-backs are not** followed by a same-right sale more than chance. So the stop-loss "replacement" is not a rule.
* **When.** {HR['replacement solo'][HR.hour >= 14].sum()/HR['replacement solo'].sum():.0%} of replacement lots are at 14:00 or later (other solo: {HR['other solo'][HR.hour >= 14].sum()/HR['other solo'].sum():.0%}). Replacement sales happen where buy-backs of both rights are recent (same right in {CD.set_index('slice').loc['replacement solo','bb_own_recent']:.0%}, other right in {CD.set_index('slice').loc['replacement solo','bb_other_recent']:.0%} of its minutes, against 36% of all minutes) and the sold premium is at its low in {CD.set_index('slice').loc['replacement solo','prem_low_60']:.0%} (9% of all minutes).
* **What separates replacement from other solo** (market and book state only): AUC {E2.set_index('slice').loc['replacement solo','auc']:.3f}, driven mostly by the **time of day** (the minute index alone costs {SEP.iloc[0].drop_in_auc:.2f} AUC when shuffled; next features {SEP.iloc[1].drop_in_auc:.3f}). By my rule (CI lower bound above 0.65) every slice is "distinct", but this is largely a time-of-day difference.
* **AUC gate** (cells with a replacement sale):

{table(E3[E3.slice=='replacement solo'][['variant','cells','auc','lo','hi','within_cycle_auc']])}
  Forward (first 16 → last 8 cycles): V1 {fw.loc[('replacement solo', v1),'auc']:.3f}. With the strangle legs removed from the outcome: {FA[FA.outcome=='y_repl_ns'].auc.iloc[0]:.3f} (forward {FA[FA.outcome=='y_repl_ns'].forward_auc.iloc[0]:.3f}). Adding ladder-state features (post-hoc) changes nothing ({LAD[(LAD.slice=='replacement solo')].auc.iloc[1]:.3f}).

## 3. Other solo and the far-OTM roll-out
{table(E3[E3.slice.isin(['other solo','far-OTM solo'])][['slice','variant','cells','auc','lo','hi','within_cycle_auc']])}
* **Other solo (before relabelling)** looks like it passes (V1 {e3.loc[('other solo', v1),'auc']:.3f}), but its forward check is {fw.loc[('other solo', v1),'auc']:.3f} and most of the signal is the strangle clock. Adding the clock feature lifts it to {CKA.iloc[3].auc:.3f} (forward {CKA.iloc[3].forward_auc:.3f}); once the strangle legs are taken out, what is left scores {FA[FA.outcome=='y_other_ns'].auc.iloc[0]:.3f}.
* **Far-OTM roll-out:** after a same-right buy-back 64% of its lots are sold at a farther strike (`D0_SELL_TYPES.md`). It is concentrated in a few cycles, so the AUC cannot be separated from the cycle.

## 4. What this settles and what it leaves
* **Settled (Observed):** SENSEX before 16 Sep has a strangle timetable that explains 15% of D0 sell lots (AUC {sA.loc['V1 + clock feature','auc']:.2f}, timetable F1 {tto['f1']:.2f}); the counter-sell AUC survives its removal; replacement solo is rankable at AUC {e3.loc[('replacement solo', v1),'auc']:.2f} (forward {fw.loc[('replacement solo', v1),'auc']:.2f}) as an afternoon stream within buy-back clusters.
* **Not settled:** the remaining other solo ({R4['other_solo_left_lots']} lots, AUC {FA[FA.outcome=='y_other_ns'].auc.iloc[0]:.2f}); the far-OTM roll-out; why the replacement stream sells at a premium similar to what was bought back; what the strangle is for (the data show the rule, not the reason).
* **Corrections to earlier D0 reports:** the "SENSEX V1: 12 scheduled waves" of `D0_SELLS.md` describes only the straddles; its main scheduled stream is this strangle. The "unexplained 30%" of `D0_SELL_TYPES.md` shrinks by {R4['other_solo_in_strangles']} lots here, and 206 counter-sell, 172 replacement and 104 opening-solo lots were strangle legs.

## Caveats
* In-sample discovery, one-minute bars, 24 cycles, one forward split. Post-hoc: the strangle detection, timetable and relabel (labelled in the plan addendum).
* The strangle timetable is learned from the same cycles it is scored on only through the out-of-fold halves (parity); the AUC clock feature uses other cycles only.
* The detector's strike-gap rule (2 steps) is itself a finding of this step, so the 626 pairs are selected by it; the strike rule's 83% is therefore conditional on that selection.

## Run order
`bl_d0n_panel.py` → `bl_d0e_repl.py` (~4 min) → `bl_d0e_more.py` (~3 min) → `bl_d0e_clock.py` (~2 min) → `bl_d0e_strangle.py` → `bl_d0e_final.py` (~3 min) → `make_d0e_report.py`.
"""
open(os.path.join(RP, 'D0_REPL.md'), 'w').write(txt); print('written')
