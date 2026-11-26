"""Figures figures/bl_d0q_alltimes_<und>_<ver>.png (one per group: D-1 clock times, D0 clock times, average lots per 5-minute slot) and reports/D0_SCHEDULED_ALLTIMES.md,
from bl_d0q_alltimes.csv, bl_d0q_slots.csv, bl_d0q_daytotals.csv, bl_summary_d0q5.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); A = pd.read_csv(f'{OUT}/bl_d0q_alltimes.csv'); SL = pd.read_csv(f'{OUT}/bl_d0q_slots.csv'); DT = pd.read_csv(f'{OUT}/bl_d0q_daytotals.csv'); R = json.load(open(f'{OUT}/bl_summary_d0q5.json'))
GR = [('NIFTY', 'V1'), ('NIFTY', 'V2'), ('SENSEX', 'V1'), ('SENSEX', 'V2')]; COL = {'D-1': '#ed8936', 'D0': '#2b6cb0'}; hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'
CYC = {('NIFTY', 'V1'): 'NIFTY, cycles up to 2026-09-09', ('NIFTY', 'V2'): 'NIFTY, cycles from 2026-09-16', ('SENSEX', 'V1'): 'SENSEX, cycles up to 2026-09-09', ('SENSEX', 'V2'): 'SENSEX, cycles from 2026-09-16'}
def table(df, fmt=2):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
for und, ver in GR:
    ymax = max(5.0, A[(A.und == und) & (A.version == ver)].avg_lots_per_active_cycle.max() * 1.3)
    fig, ax = plt.subplots(3, 1, figsize=(21, 12.5), gridspec_kw=dict(height_ratios=[1.1, 1.1, 1.0], hspace=.32))
    for k, day in enumerate(('D-1', 'D0')):
        a = ax[k]; d = A[(A.und == und) & (A.version == ver) & (A.day == day)].sort_values('seconds'); x = d.seconds.values / 3600
        a.vlines(x, 0, d.avg_lots_per_active_cycle.values, color=COL[day], lw=2.2); a.scatter(x, d.avg_lots_per_active_cycle.values, s=14, color=COL[day], zorder=3)
        last = -1e9
        for t_, h_, s_ in zip(d.seconds, d.avg_lots_per_active_cycle, d.time):
            if t_ - last >= 70: a.text(t_ / 3600, h_ + .12, s_, rotation=90, fontsize=5.6, ha='center', va='bottom'); last = t_
        for b in np.arange(33300, 55800, 900): a.axvline(b / 3600, color='#e2e8f0', lw=.8, zorder=0)
        n_c = int(d.cycles_active.max()); a.set_xlim(9.2, 15.0); a.set_ylim(0, ymax); a.set_ylabel('avg lots executed\n(CE + PE) per cycle')
        t_ = DT[(DT.und == und) & (DT.version == ver) & (DT.day == day)].iloc[0]
        a.set_title(f"{day}{' (expiry day)' if day == 'D0' else ' (day before expiry)'} — {CYC[(und, ver)]} — {int(t_.clock_times)} clock times, {int(t_.waves)} straddles (1 CE + 1 PE each), avg {t_.avg_lots_per_active_cycle_per_day:.0f} lots per cycle per day  (up to {n_c} cycles)", fontsize=10.5)
    a = ax[2]; w = .38; marks = np.arange(33300, 53700, 300)
    for day, off in (('D-1', -w / 2), ('D0', w / 2)):
        s = SL[(SL.und == und) & (SL.version == ver) & (SL.day == day)].set_index('seconds').reindex(marks); a.bar(np.arange(len(marks)) + off, s.avg_lots.fillna(0).values, w, color=COL[day], label=day)
        for xi, v in enumerate(s.avg_lots.fillna(0).values):
            if v >= 0.6: a.text(xi + off, v + .08, f'{v:.1f}', ha='center', va='bottom', fontsize=5.8, rotation=90)
    a.set_xticks(range(len(marks))); a.set_xticklabels([hm(m)[:5] for m in marks], rotation=90, fontsize=6.5); a.legend(fontsize=9)
    for xi, m in enumerate(marks):
        if (m - 33300) % 900 == 0: a.axvline(xi, color='#e2e8f0', lw=.8, zorder=0)
    a.set_xlim(-1, len(marks)); a.set_ylabel('avg lots per cycle in the\n133 s after each 5-min mark'); a.set_title('Average lots executed per slot (the 133 s after every 5-minute mark; grey lines = 15-minute boundaries)', fontsize=10.5)
    ax[1].set_xlabel('time of day (hours)')
    fig.suptitle(f'Scheduled selling — every clock time, D-1 vs D0 — {CYC[(und, ver)]}.  Stem height = average lots executed at that clock time per active cycle (2 = one straddle, 4 = two).  Time labels shown where space allows; full list in D0_SCHEDULED_ALLTIMES.md', fontsize=11.5, y=.935)
    plt.savefig(os.path.join(RP, 'figures', f'bl_d0q_alltimes_{und}_{ver}.png'), dpi=115, bbox_inches='tight'); plt.close()
# ---------------- report
def block_lines(d):
    d = d.sort_values('seconds').copy(); d['blk'] = [hm(33300 + 900 * int((t - 33300) // 900))[:5] for t in d.seconds]; out = []
    for b, g in d.groupby('blk'): out.append(f"{b}: " + ', '.join(f"{t[3:]} ({v:.1f})" if abs(v - round(v)) > .05 else f"{t[3:]} ({int(round(v))})" for t, v in zip(g.time, g.avg_lots_per_active_cycle)))
    return '\n'.join(out)
dtw = DT.rename(columns={'clock_times': 'clock times', 'waves': 'straddles', 'expected_lots_per_day': 'lots if every one fires', 'avg_lots_per_active_cycle_per_day': 'avg lots per cycle per day', 'max_lots_in_one_clock_time': 'max avg lots at one clock time', 'slots_used(5-min marks with lots)': '5-min slots used', 'avg_lots_per_used_slot': 'avg lots per used slot'})
dtw['group'] = dtw.und + ' ' + dtw.version; dtw = dtw[['group', 'day', 'clock times', 'straddles', 'lots if every one fires', 'avg lots per cycle per day', 'max avg lots at one clock time', '5-min slots used', 'avg lots per used slot']]
hist = R['lots_per_clock_time_hist']
parts = [f"""# Algo 8 — scheduled selling: every clock time on D-1 and D0, and the lots executed at each

*Figures: `figures/bl_d0q_alltimes_NIFTY_V1.png`, `..._NIFTY_V2.png`, `..._SENSEX_V1.png`, `..._SENSEX_V2.png` (one per group; D-1 on top, D0 in the middle, average lots per 5-minute slot at the bottom). Data: `outputs/bl_d0q_alltimes.csv` (every clock time), `bl_d0q_slots.csv` (every slot), `bl_d0q_daytotals.csv`. Descriptive, all cycles.*

## 0. How to read this
* **A group** is an underlying with a timetable version. The version is only a date split: V1 = cycles up to 2026-09-09, V2 = cycles from 2026-09-16.
* **A clock time** is a second of the day at which the system sells. At it, it sells one **straddle**: 1 CE lot + 1 PE lot at the same ATM strike.
* **A wave** is one straddle. Where two or more fire in the same second (within 3 s), they stack and the stem is taller.
* **Lots at a clock time** = the average lots executed per cycle that was still running at that time (2 = one straddle, 4 = two).
* **A slot** is the 133 s after a 5-minute mark. Its value is the average lots executed in it per cycle.

## 1. Answer: yes, they come in waves, mostly of one straddle
* **Most clock times are a single straddle, 2 lots.**
  * D-1 NIFTY V1: {hist['NIFTY V1 D-1'].get('1', 0)} of {sum(hist['NIFTY V1 D-1'].values())} clock times are one straddle, {hist['NIFTY V1 D-1'].get('2', 0)} are two and {hist['NIFTY V1 D-1'].get('3', 0)} is three.
  * D0 NIFTY V1: {hist['NIFTY V1 D0'].get('1', 0)} of {sum(hist['NIFTY V1 D0'].values())} are one straddle, {hist['NIFTY V1 D0'].get('2', 0)} are two.
* **Bigger stacks are rare.** On D-1 the most is 3 straddles in one second. On D0 it is 2, except for the opening bursts at 09:16 of the V2 groups (up to 9 straddles), which come from few cycles.
* **A day in total** (average lots per cycle):

{table(dtw)}

* **D0 has about 2.3 times the lots of D-1** for NIFTY V1 ({DT[(DT.und == 'NIFTY') & (DT.version == 'V1') & (DT.day == 'D0')].avg_lots_per_active_cycle_per_day.iloc[0]:.0f} against {DT[(DT.und == 'NIFTY') & (DT.version == 'V1') & (DT.day == 'D-1')].avg_lots_per_active_cycle_per_day.iloc[0]:.0f}), and about 2× for NIFTY V2 and SENSEX V2. SENSEX V1 is the exception: D0 has fewer ({DT[(DT.und == 'SENSEX') & (DT.version == 'V1') & (DT.day == 'D0')].avg_lots_per_active_cycle_per_day.iloc[0]:.0f}).
* **Lots per slot.** A used 5-minute slot carries about 3.3 lots on D-1 and 4–5 on D0 (NIFTY V1: {DT[(DT.und == 'NIFTY') & (DT.version == 'V1') & (DT.day == 'D0')].avg_lots_per_used_slot.iloc[0]:.1f}).
"""]
for und, ver in GR:
    parts.append(f"## {und} {ver}: {CYC[(und, ver)]}\n![{und} {ver}](figures/bl_d0q_alltimes_{und}_{ver}.png)\n")
    for day in ('D-1', 'D0'):
        d = A[(A.und == und) & (A.version == ver) & (A.day == day)]; parts.append(f"**{day} clock times** (mm:ss within each 15-minute block, then average lots executed in brackets; {len(d)} clock times):\n\n```\n{block_lines(d)}\n```\n")
parts.append("""## Caveats
* **Wave lists are learned from the data.** A clock time is listed when at least half of the group's running cycles have a straddle at that second (±3 s).
* **NIFTY V2 and the SENSEX groups have few cycles** (NIFTY V2: 4, of which 2 usable on D0). Their D0 lists are less certain.
* **Averages count only cycles still running.** A cycle stopped by the cycle stop drops out from that time on.
* **The opening bursts at 09:16 on D0 (V2)** vary by cycle. They are shown as one tall stem.

## Run order
`bl_d0q_sched.py` → `bl_d0q_alltimes.py` → `make_d0qa_report.py`.
""")
open(os.path.join(RP, 'D0_SCHEDULED_ALLTIMES.md'), 'w').write('\n'.join(parts)); print('written')
