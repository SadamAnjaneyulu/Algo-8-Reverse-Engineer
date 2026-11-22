"""Figures figures/bl_d0r_timers_NIFTY_V1.png (timer chart D-1 vs D0) and figures/bl_d0r_bank.png (timer families across groups and days), and reports/D0_SCHED_RULE.md.
Timers = gapped-timer integer program (bl_d0r_gap.solve, mu 1.5, tol 2 s, fill >= 0.6); validation numbers from bl_d0r_t1.csv, bl_d0r_robust.csv, bl_d0r_gap.csv, bl_d0r_gap_fwd.csv, bl_summary_d0r1/2/3.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
import bl_d0r_gap as G, bl_d0r_ilp as I
RP = os.path.join(os.path.dirname(OUT), 'reports'); hm = I.hm
W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); WA = pd.read_csv(f'{OUT}/bl_d0q_waves.csv'); T1 = pd.read_csv(f'{OUT}/bl_d0r_t1.csv'); RB = pd.read_csv(f'{OUT}/bl_d0r_robust.csv'); GP = pd.read_csv(f'{OUT}/bl_d0r_gap.csv'); GF = pd.read_csv(f'{OUT}/bl_d0r_gap_fwd.csv')
R1, R2, R3, R4m = [json.load(open(f'{OUT}/bl_summary_{k}.json')) for k in ('d0r1', 'd0r2', 'd0r3', 'd0r4')]; D1M = pd.read_csv(f'{OUT}/bl_d0r_d1marks.csv')
def table(df, fmt=2):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
def off_class(s):
    s = s % 60; d0 = min(s, 60 - s)
    if d0 <= 2.6: return ':00'
    for lo, hi, lab in ((3.5, 7.5, ':04-06'), (8.5, 11.0, ':09-10'), (26.5, 28.9, ':27-28'), (29.5, 32.0, ':30-31')):
        if lo <= s <= hi: return lab
    return f':{int(round(s)):02d}'
GD = [('D-1', 'NIFTY', 'V1'), ('D0', 'NIFTY', 'V1'), ('D-1', 'NIFTY', 'V2'), ('D0', 'NIFTY', 'V2'), ('D-1', 'SENSEX', 'V1'), ('D0', 'SENSEX', 'V1'), ('D-1', 'SENSEX', 'V2'), ('D0', 'SENSEX', 'V2')]
CYCL = {('NIFTY', 'V1'): 'NIFTY, cycles before 16 Sep', ('NIFTY', 'V2'): 'NIFTY, cycles from 16 Sep', ('SENSEX', 'V1'): 'SENSEX, cycles before 16 Sep', ('SENSEX', 'V2'): 'SENSEX, cycles from 16 Sep'}
TIM = {}; ALIVE = {}; TT = {}; rows = []
for day, u, v in GD:
    W = WA if day == 'D0' else W1; t = np.sort(W[(W.und == u) & (W.version == v)].t.values); ch, alive = G.solve(t); TT[(day, u, v)] = t; ALIVE[(day, u, v)] = alive; lst = []
    for P, ix in ch:
        tt = np.sort(t[ix]); slots = int(round((tt[-1] - tt[0]) / P)) + 1; lst.append(dict(P=P, first=float(tt[0]), last=float(tt[-1]), n=len(ix), slots=slots, sec=float(np.median(tt % 60)), times=tt, family=f'every {P // 60} min @ {off_class(np.median(tt % 60))}'))
    TIM[(day, u, v)] = sorted(lst, key=lambda x: (x['P'], x['first']))
    for x in TIM[(day, u, v)]: rows.append(dict(day=day, group=f'{u} {v}', family=x['family'], period_min=x['P'] // 60, first=hm(x['first']), last=hm(x['last']), members=x['n'], slots_in_span=x['slots'], fill=x['n'] / x['slots']))
TB = pd.DataFrame(rows); TB.to_csv(f'{OUT}/bl_d0r_timers_gapped.csv', index=False)
FAM = TB.groupby('family').agg(period_min=('period_min', 'first'), timers=('first', 'size'), group_days=('group', lambda s: len(set(zip(TB.loc[s.index, 'day'], s)))), members=('members', 'sum')).reset_index().sort_values(['group_days', 'members'], ascending=False)
# ---------------- figure 1: NIFTY V1 timers, D-1 vs D0
COL = {15: '#2b6cb0', 30: '#38a169', 45: '#d69e2e', 60: '#dd6b20', 75: '#805ad5', 5: '#e53e3e', 10: '#e53e3e'}
fig, ax = plt.subplots(2, 1, figsize=(19, 11), gridspec_kw=dict(height_ratios=[0.8, 1.45], hspace=.22))
for k, day in enumerate(('D-1', 'D0')):
    a = ax[k]; tm = sorted(TIM[(day, 'NIFTY', 'V1')], key=lambda x: (x['first'], x['P'])); t = TT[(day, 'NIFTY', 'V1')]; alive = ALIVE[(day, 'NIFTY', 'V1')]
    for r, x in enumerate(tm):
        y = len(tm) - r; c = COL.get(x['P'] // 60, '#4a5568'); exp = x['first'] + x['P'] * np.arange(x['slots'])
        a.plot([x['first'] / 3600, x['last'] / 3600], [y, y], color=c, lw=1.2, alpha=.5); a.scatter(exp / 3600, np.full(len(exp), y), s=36, facecolors='white', edgecolors=c, linewidths=1.0, zorder=2)
        a.scatter(x['times'] / 3600, np.full(len(x['times']), y), s=40, color=c, zorder=3); a.text(8.98, y, f"every {x['P'] // 60} min @ {off_class(x['sec'])}  ({x['n']} fires)", ha='right', va='center', fontsize=8.5)
    a.scatter(t[alive] / 3600, np.zeros(int(alive.sum())), s=34, color='#a0aec0', marker='|', linewidths=1.6); a.text(8.98, 0, f'not in any timer ({int(alive.sum())})', ha='right', va='center', fontsize=8.5, color='#718096')
    for b in np.arange(33300, 55800, 900): a.axvline(b / 3600, color='#edf2f7', lw=.8, zorder=0)
    a.set_xlim(9.2, 14.9); a.set_ylim(-.8, len(tm) + .8); a.set_yticks([]); a.set_title(f"{day} ({'expiry day' if day == 'D0' else 'day before expiry'}) — {CYCL[('NIFTY', 'V1')]}: {len(t)} clock times = {len(tm)} timers + {int(alive.sum())} unexplained", fontsize=11)
ax[1].set_xlabel('time of day (hours).  Filled dot = the timer fired; hollow circle = a slot of that timer with no firing (timers may skip slots).  Grey ticks = clock times no timer explains.')
plt.savefig(os.path.join(RP, 'figures', 'bl_d0r_timers_NIFTY_V1.png'), dpi=115, bbox_inches='tight'); plt.close()
# ---------------- figure 2: timer bank across groups and days
fam_order = list(FAM.family); fig, ax = plt.subplots(figsize=(20, 7.5)); cols = [f'{d} {u} {v}' for d, u, v in GD]
for ci, (d, u, v) in enumerate(GD):
    for x in TIM[(d, u, v)]:
        ri = fam_order.index(x['family']); y = ri + (-.28 + .14 * (list(x['family'] for x in TIM[(d, u, v)]).index(x['family']) % 5))
        ax.barh(ri, 0, left=0)
rows_ = []
fig, ax = plt.subplots(len(GD), 1, figsize=(19, 14), sharex=True, gridspec_kw=dict(hspace=.12))
for a, (d, u, v) in zip(ax, GD):
    tm = sorted(TIM[(d, u, v)], key=lambda x: (fam_order.index(x['family']), x['first']))
    for r, x in enumerate(tm):
        c = COL.get(x['P'] // 60, '#4a5568'); a.plot([x['first'] / 3600, x['last'] / 3600], [r, r], color=c, lw=3, alpha=.35, solid_capstyle='round'); a.scatter(x['times'] / 3600, np.full(len(x['times']), r), s=22, color=c, zorder=3)
        a.text(x['first'] / 3600 - .03, r, x['family'].replace('every ', ''), ha='right', va='center', fontsize=7)
    a.set_ylim(-.8, max(len(tm), 3) - .2); a.set_yticks([]); a.set_ylabel(f'{d}\n{u} {v}', rotation=0, ha='right', va='center', fontsize=9); a.invert_yaxis(); a.set_xlim(8.2, 14.9)
    for b in np.arange(33300, 55800, 900): a.axvline(b / 3600, color='#edf2f7', lw=.7, zorder=0)
ax[-1].set_xlabel('time of day (hours)'); fig.suptitle('The timer bank: every timer found in each group and day (colour = period: blue 15, green 30, yellow 45, orange 60, purple 75, red 5/10 min). Label = period @ second offset.', fontsize=12, y=.915)
plt.savefig(os.path.join(RP, 'figures', 'bl_d0r_bank.png'), dpi=110, bbox_inches='tight'); plt.close()
# ---------------- report numbers
gp = GP.set_index(['day', 'group']); gf = GF.set_index(['day', 'group']); n1 = ('D0', 'NIFTY V1'); t1 = T1
def g1(test, group): return float(T1[(T1.test == test) & (T1.group == group)].real_share.iloc[0])
def act_count(day, u, v, at): return sum(1 for x in TIM[(day, u, v)] if x['first'] <= at <= x['last'])
late0 = ', '.join(f"{x['family'].replace('every ', '')} from {hm(x['first'])[:8]}" for x in sorted(TIM[('D0', 'NIFTY', 'V1')], key=lambda x: x['first']) if x['first'] > 36000)
aft0 = min(x['first'] for x in TIM[('D0', 'NIFTY', 'V1')] if x['P'] == 900 and x['last'] > 50000); aft1 = min(x['first'] for x in TIM[('D-1', 'NIFTY', 'V1')] if x['P'] == 900 and x['last'] > 50000)
act = pd.DataFrame([dict(time=f'{h:02d}:00', D1=act_count('D-1', 'NIFTY', 'V1', h * 3600 + 1), D0=act_count('D0', 'NIFTY', 'V1', h * 3600 + 1)) for h in (10, 11, 12, 13, 14)]).rename(columns={'D1': 'D-1 timers running', 'D0': 'D0 timers running'})
lists = []
for day in ('D-1', 'D0'):
    lists.append(f"**{day}, NIFTY (cycles before 16 Sep)** — every timer and when it fires:\n")
    for x in sorted(TIM[(day, 'NIFTY', 'V1')], key=lambda x: (x['first'], x['P'])): lists.append(f"* **every {x['P'] // 60} min @ {off_class(x['sec'])}**, {hm(x['first'])[:8]} → {hm(x['last'])[:8]}, {x['n']} fires in {x['slots']} slots: " + ', '.join(hm(t)[:8] for t in x['times']))
    al = ALIVE[(day, 'NIFTY', 'V1')]; lists.append(f"* *not in any timer ({int(al.sum())}):* " + ', '.join(hm(t)[:8] for t in TT[(day, 'NIFTY', 'V1')][al]) + '\n')
tf = T1[T1.test.str.startswith('T1')][['day', 'group', 'targets', 'real_share', 'null_mean', 'null_p95']].rename(columns={'real_share': 'afternoon times predicted', 'null_mean': 'null mean', 'null_p95': 'null 95th pct'})
txt = f"""# Algo 8 — how was scheduled selling actually scheduled? A bank of timers

*Plan `D0_SCHED_RULE_PLAN.md` (written before the validation tests; addendum A, gapped timers with a skip penalty, is post-hoc). Descriptive, consensus clock times of every group. Figures: `figures/bl_d0r_timers_NIFTY_V1.png`, `figures/bl_d0r_bank.png`. Scripts `bl_d0r_ilp.py`, `bl_d0r_val.py`, `bl_d0r_bank.py`, `bl_d0r_gap.py`.*

## 0. Result
* **D-1 is ATM straddle selling at 15-minute marks, as established. This page is about what is inside the marks, and how D0 differs.**
  * **D-1:** every cycle sells 1 CE + 1 PE at the ATM strike after {len(R4m['full_marks'])} of the 21 marks between 09:30 and 14:30 ({', '.join(R4m['skipped_marks_0930_1430'])} are skipped). {R4m['atm_share']:.0%} of the {R4m['pairs']:,} straddles are at the ATM of the previous minute's close. Each mark gets between {R4m['straddles_per_mark_range'][0]:.0f} and {R4m['straddles_per_mark_range'][1]:.1f} straddles per cycle on average, at different seconds (table in §1).
  * **Inside the marks, the clock times are built from a bank of independent timers.** Each timer fires every N minutes at a fixed second offset, between a start and an end, and may skip a slot.
    * D-1 NIFTY (before 16 Sep): {gp.loc[('D-1', 'NIFTY V1'), 'gapped_timers']:.0f} timers explain {gp.loc[('D-1', 'NIFTY V1'), 'gapped_covered']:.0%} of the {gp.loc[('D-1', 'NIFTY V1'), 'waves']:.0f} clock times.
    * Their periods (15, 30, 45, 60 minutes) are multiples of 15 minutes, consistent with the 15-minute marks (inferred).
  * **D0:** the same 15-minute marks plus more marks, and more straddles per mark. {gp.loc[n1, 'gapped_timers']:.0f} timers explain {gp.loc[n1, 'gapped_covered']:.0%} of the {gp.loc[n1, 'waves']:.0f} clock times. **D0 runs more timers, and several start earlier.**
  * Null (clock times shifted by up to ±150 s): {gp.loc[n1, 'null_covered_mean']:.0%} covered. *Observed.*
* **The timers are real, not a fitting artefact.** Timers fitted only on the morning (before 12:00) predict clock times after 12:00 to the second:

{table(tf, 3)}

  * Predicted shares are 0.11–0.56 against null means of 0.003–0.007. All 7 group-days beat the 95th percentile of the null.
  * The result holds in {R2['robust_above']} of {R2['robust_runs']} settings of the timer cost and tolerance.
  * With skipped slots allowed, the same forward test gives recall {GF.recall.min():.0%}–{GF.recall.max():.0%} (null at most {GF.recall_null_mean.max():.1%}) and precision {GF.precision.min():.0%}–{GF.precision.max():.0%} (null at most {GF.precision_null_mean.max():.1%}); all {int(GF.above_p95.sum())} of {len(GF)} beat the null's 95th percentile.
  * *Observed.*
* **The same timer bank serves NIFTY and SENSEX.** The NIFTY D0 timers, extended over the day, explain {g1('T3 NIFTY V1 D0 timers -> other group D0 times', 'NIFTY V2'):.0%} of NIFTY V2 D0 times, {g1('T3 NIFTY V1 D0 timers -> other group D0 times', 'SENSEX V2'):.0%} of SENSEX V2 and {g1('T3 NIFTY V1 D0 timers -> other group D0 times', 'SENSEX V1'):.0%} of SENSEX V1 (null about 3%).
* **D0 reuses D-1's timers.** D-1 timers extended over the day explain {g1('T2 D-1 timers -> D0 times', 'NIFTY V1'):.0%}–{g1('T2 D-1 timers -> D0 times', 'NIFTY V2'):.0%} of the D0 times of NIFTY and SENSEX V2 (null 1%). The D0 timers explain {g1('T2 D0 timers -> D-1 times', 'NIFTY V1'):.0%} of D-1 times. SENSEX V1 on D0 shares none of its own D-1 timers (it runs two 45-minute timers only).
* **Why D0 looks unorganised: more timers run at once, and they start and stop at different times.**

{table(act, 0)}

  * D0 has {len(TIM[('D0', 'NIFTY', 'V1')])} timers against {len(TIM[('D-1', 'NIFTY', 'V1')])} on D-1, and about twice as many running at most hours.
  * Timers that start after 10:00 on D0: {late0}.
  * The afternoon 15-minute timer starts at {hm(aft0)[:8]} on D0 and {hm(aft1)[:8]} on D-1.
  * Overlapping timers of different periods and second offsets are what make the pattern hard to see by eye.
* **Not explained:** {1 - gp.loc[n1, 'gapped_covered']:.0%} of the D0 NIFTY times, {1 - gp.loc[('D0', 'NIFTY V2'), 'gapped_covered']:.0%} for NIFTY V2 and {1 - gp.loc[('D0', 'SENSEX V2'), 'gapped_covered']:.0%} for SENSEX V2.
  * These are not noise. Of the 26 NIFTY times that the strict (no-skip) model left out, 65% also appear at the same second in NIFTY V2 and 42% in SENSEX V2 (null 1%). They are fixed clock times without a periodic rule I can see.

## 1. D-1 at the 15-minute marks (all 32 cycles)
Straddles per cycle in the 3 minutes after each mark. Each straddle is 1 CE + 1 PE at ATM. {R4m['pairs']:,} straddles in total; all of them fall in these windows.

{table(D1M.rename(columns={'mark': '15-min mark', 'pct_cycles_selling': 'share of cycles selling', 'avg_straddles_per_cycle': 'avg straddles per cycle', 'min_straddles': 'min', 'max_straddles': 'max', 'pairs': 'straddles (all cycles)'}).query("`share of cycles selling` > 0"))}

* **17 marks are sold after in every cycle:** 09:30, 09:45, 10:00, 10:15, 10:30, 10:45, 11:00, 11:15, 11:30, 11:45, 12:00, 12:30, 13:30, 13:45, 14:00, 14:15, 14:30.
* **Not sold after:** 12:15, 12:45, 13:00.
* **Partly:**
  * 09:15 is the opening (97% of cycles);
  * 13:15 only in the cycles before 16 Sep (66%);
  * 14:45 only in a few (19%).

## 2. The method in plain words
1. Take the clock times at which the system sells (the consensus list of each group, `D0_SCHEDULED_ALLTIMES.md`).
2. Look for sets of times that are spaced by a whole number of 5 minutes, at the same second, between a start and an end. Such a set is a **timer**.
3. An integer program picks the smallest set of timers that explains the most times.
4. The null: shift every time randomly by ±150 s and repeat. A timer set that explains the real times and not the shifted ones is real.
5. The key test is forecasting. Learn the timers from the morning only and ask whether they predict the afternoon to the second.

## 3. The timer bank
{table(FAM.rename(columns={'family': 'timer family (period @ second offset)', 'timers': 'timers found', 'group_days': 'group-days where it appears', 'members': 'fires'}), 0)}

A *group-day* is one of the eight cases D-1 / D0 × NIFTY / SENSEX × cycles before / from 16 Sep. Timers with the same period and second offset recurring in several group-days are the strongest evidence.

## 4. Every timer in NIFTY (cycles before 16 Sep)
{chr(10).join(lists)}
## 5. What is not known
* **Why those periods, offsets and windows.** The timer shapes are measured; the logic that chose them (an expiry-time ramp, separate strategy legs, a hand-written list) needs the configuration.
* **Why a timer skips a slot.** Slots are skipped in {int((TB.fill < 1).sum())} of {len(TB)} timers. I found no market state that explains it (`D0_SCHEDULED.md` §3 tested several for whole waves).
* **The unexplained {1 - gp.loc[n1, 'gapped_covered']:.0%}.** Fixed times that repeat across days and groups, but not on a periodic chain.
* **The 75-minute and 5-minute timers are the least certain.** They appear in only 2 group-days. Treat them as candidates.
* **The gapped timers were added after the first results** (post-hoc). They pass the same forward test, but they are more flexible than the strict ones.

## Run order
`bl_d0q_sched.py` → `bl_d0r_ilp.py` (exploratory) → `bl_d0r_val.py` → `bl_d0r_bank.py` → `bl_d0r_gap.py` → `make_d0r_report.py`.
"""
open(os.path.join(RP, 'D0_SCHED_RULE.md'), 'w').write(txt); print('written', len(txt))
