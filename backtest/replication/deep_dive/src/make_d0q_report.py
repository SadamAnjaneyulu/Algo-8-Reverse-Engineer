"""Builds reports/D0_SCHEDULED.md and figures/bl_d0q_summary.png from bl_d0q_*.csv and bl_summary_d0q1.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R = json.load(open(f'{OUT}/bl_summary_d0q1.json'))
W = pd.read_csv(f'{OUT}/bl_d0q_waves.csv'); W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); SE = pd.read_csv(f'{OUT}/bl_d0q_startend.csv'); AU = pd.read_csv(f'{OUT}/bl_d0q_auc.csv'); SK = pd.read_csv(f'{OUT}/bl_d0q_strike.csv'); DI = pd.read_csv(f'{OUT}/bl_d0q_disagree.csv'); MT = pd.read_csv(f'{OUT}/bl_d0q_d1match.csv'); EE = pd.read_csv(f'{OUT}/bl_d0q_earlyend.csv')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'
G = ['NIFTY V1', 'NIFTY V2', 'SENSEX V1', 'SENSEX V2']; W['g'] = W.und + ' ' + W.version; W1['g'] = W1.und + ' ' + W1.version; W['bm'] = ((W.t - 33300) // 60 % 15).astype(int)
fig, ax = plt.subplots(1, 3, figsize=(19, 5.2), gridspec_kw=dict(width_ratios=[2.2, 1, 1]))
for k, g in enumerate(G):
    a = W[W.g == g]; b = W1[W1.g == g]; ax[0].scatter((a.t - 33300) / 3600 + 9.25, np.full(len(a), k + .12), s=18, color='#2b6cb0', label='D0 wave' if k == 0 else None); ax[0].scatter((b.t - 33300) / 3600 + 9.25, np.full(len(b), k - .18), s=18, facecolors='none', edgecolors='#ed8936', label='D-1 wave' if k == 0 else None)
for x in np.arange(9.25, 15.3, .25): ax[0].axvline(x, color='#edf2f7', lw=.6, zorder=0)
ax[0].set_yticks(range(4)); ax[0].set_yticklabels(G); ax[0].set_xlabel('time (hours; grid = 15-min blocks from 09:15)'); ax[0].legend(fontsize=8, loc='upper right'); ax[0].set_title('Scheduled pair waves: D0 (filled) vs D-1 (hollow), each 1 CE + 1 PE lot', fontsize=10)
lab = {'prev_close': 'nearest prev.\nminute close', 'minute_open': 'nearest\nminute open', 'minute_close': 'nearest minute\nclose (non-causal)', 'any_atm_in_minute': 'ATM at any time\nin the minute', 'straddle_min_abs_ce_pe': 'straddle\n|CE−PE| min', 'synthetic_forward': 'synthetic\nforward', 'previous_sched_strike': 'previous\nscheduled strike'}
ax[1].barh(range(len(SK)), SK.exact_share, color=['#2b6cb0' if c in ('prev_close', 'any_atm_in_minute') else '#a0aec0' for c in SK.candidate]); ax[1].set_yticks(range(len(SK))); ax[1].set_yticklabels([lab[c] for c in SK.candidate], fontsize=7); ax[1].set_xlim(.7, 1.0)
for k, v in enumerate(SK.exact_share): ax[1].text(v + .003, k, f'{v:.1%}', va='center', fontsize=8)
ax[1].set_title('Strike sold = candidate (exact)', fontsize=10)
bm = W.groupby(['g', 'bm']).size().unstack(fill_value=0).reindex(columns=range(15), fill_value=0)
for g, col in zip(G, ('#2b6cb0', '#63b3ed', '#ed8936', '#f6ad55')): ax[2].plot(range(15), bm.loc[g].values / bm.loc[g].sum(), marker='o', label=g, color=col)
ax[2].set_xticks(range(15)); ax[2].set_xlabel('minute within the 15-min block (0 = :15/:30/:45/:00)'); ax[2].set_ylabel('share of waves'); ax[2].legend(fontsize=8); ax[2].set_title('Where in the 15-min block the waves fall', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0q_summary.png'), dpi=130)
tl = []
for g in G:
    a = W[W.g == g].sort_values('t'); a['slot'] = ((a.t - 33360) // 900).astype(int)
    tl.append(dict(group=g, cycles_with_sales=int(SE[(SE.und + ' ' + SE.version == g) & (SE.sched_lots > 0)].shape[0]), waves=len(a), first=hm(a.t.min()), last=hm(a.t.max()), waves_per_15min_median=float(a.groupby('slot').size().median()), lots_per_wave='1 CE + 1 PE', share_in_block_min_0_or_1=float(a.bm.isin([0, 1]).mean())))
TL = pd.DataFrame(tl); sk = SK.set_index('candidate'); di = DI.set_index('alternative'); m = R['T4_misses']; er = R['T2_end_reasons']; at = R['T3_attendance']; mt = MT.set_index('group')
ex = W.copy(); ex['blk'] = [f'{int((33360 + 900 * s) // 3600):02d}:{int((33360 + 900 * s) % 3600 // 60):02d}' for s in ((ex.t - 33360) // 900).astype(int)]
lines = []
for g in G:
    a = ex[ex.g == g].sort_values('t'); lines.append(f"**{g}** ({len(a)} waves): " + '; '.join(f"{b}: " + ' '.join(hm(t)[3:] for t in x.t) for b, x in a.groupby('blk')))
txt = f"""# Algo 8 — D0 step 1b: scheduled selling in depth

*Plan `D0_SCHEDULED_PLAN.md`, written before the tests. In-sample: D0 of the 30 cycles with both logs. Figure: `figures/bl_d0q_summary.png`.*

## 0. Result
* **What it is.** A clock. At fixed seconds the system sells **1 CE + 1 PE lot at the ATM strike**, a straddle. The clock is different for each underlying × version and identical across the days of a group, to within 1–3 s.
  * {R['sched_pairs_all_timetable']:,} pairs, {R['sched_lots_all_timetable']:,} lots ({R['sched_lots_all_timetable'] / 8336:.0%} of D0 sell lots).
* **When it starts and ends:**

{table(TL)}

* **What ends it.** Every cycle sells until its group's last wave unless the cycle stop fires first. Two exceptions, both SENSEX V1:
  * one cycle skipped only the last wave; it had the highest MTM of its group (+₹{EE.mtm_lakh.max():.1f} L);
  * one cycle stopped scheduled selling at 10:32 with nothing unusual in its MTM or book.
  * *Unresolved* (one case each).
* **Trigger.**
  * The trigger is the clock. While the cycle is active, {R['T3_attendance_all']:.0%} of waves are executed (out-of-fold timetable).
  * No state variable explains the few skips: MTM, book size, spot move, distance to the strike midpoint, straddle premium and recent buy-backs all fall short of AUC 0.70 in both halves.
* **Strike chosen: the ATM of the live spot price.**
  * It is the strike nearest the previous minute's close in **{sk.loc['prev_close', 'exact_share']:.1%}** of pairs.
  * In **{sk.loc['any_atm_in_minute', 'exact_share']:.0%}** it was the ATM strike at some moment inside the sale minute.
  * A premium-based ATM is ruled out. Where the straddle ATM (|CE − PE| smallest) or the synthetic forward picks a different strike, the real strike follows the spot ATM in {di.loc['straddle_min_abs_ce_pe', 'real_equals_prev_close']:.0%} / {di.loc['synthetic_forward', 'real_equals_prev_close']:.0%} of cases.
  * The {m['share']:.0%} that differ from the previous close happen when spot sits near the midpoint between two strikes (median {m['mid_frac_q'][1]:.2f} step from ATM, against {m['all_mid_frac_q'][1]:.2f} overall). There the spot crossed the midpoint inside the minute. This fits an ATM taken from the live price at the second of the sale. *Inferred.*
* **Same scheduler as D-1, for NIFTY.**
  * {mt.loc['NIFTY V1', 'D1_waves_matching_a_D0_wave']:.0%} (V1) and {mt.loc['NIFTY V2', 'D1_waves_matching_a_D0_wave']:.0%} (V2) of the D-1 NIFTY waves recur on D0 at the same second.
  * D0 adds about twice as many waves on top, mostly at the 15-minute block boundary (block minutes 0 and 1) and at +5, +7, +10 and +13/14 minutes of a block.
  * SENSEX runs a different D0 clock: V1 sells once per block at +60 s and shares {mt.loc['SENSEX V1', 'D1_waves_matching_a_D0_wave']:.0%} of its waves with D-1; V2 shares {mt.loc['SENSEX V2', 'D1_waves_matching_a_D0_wave']:.0%}.

## 1. The timetable (every wave = 1 CE + 1 PE lot at ATM)
Times are mm:ss within each 15-minute slot.

""" + '\n\n'.join(lines) + f"""

**Stability.** For each group, the share of waves learned on one cycle half that are also found on the other (±3 s):

{table(pd.DataFrame([dict(group=k, **v) for k, v in R['T1_stability'].items()]))}

NIFTY V2 has only two usable cycles (two others stopped at the open), and both are in the same half. Its timetable can only be learned in-sample.

## 2. Start and end per cycle
{table(SE)}

**Early ends, compared with the cycles of the same group that sold the same wave:**

{table(EE, 2)}

## 3. Attendance and skips (out-of-fold waves, active cycles)
* Attendance by group: {', '.join(f'{k} {v:.0%}' for k, v in at.items())}.

**Single-variable AUC for skipping a wave:**

{table(AU)}

## 4. Strike candidates
{table(SK)}

**Where the candidates disagree:**

{table(DI)}

**The {m['n']} pairs not at the previous-close ATM:**
* every one was ATM at some point inside the minute;
* {m['miss_equals_minute_close']:.0%} match the minute-close ATM;
* {m['miss_equals_previous_sched']:.0%} repeat the previous scheduled strike.

## 5. D-1 vs D0 waves
{table(MT)}

## 6. Caveats
* **In-sample.** The timetable in §1–2 and §4 is learned on all cycles (descriptive). The out-of-fold version gives the same picture (§1 stability) except for NIFTY V2.
* **Minute bars.** The strike rule is checked on minute bars. The exact second-level spot at the sale is not observed, so "live ATM" is inferred from the midpoint cases.
* **One case each** for the two early ends.

## Run order
`bl_d0q_sched.py` → `make_d0q_report.py` (needs chunk 1–4 outputs).
"""
open(os.path.join(RP, 'D0_SCHEDULED.md'), 'w').write(txt); print('written', len(txt))
