"""Builds reports/D0_SCHEDULED_CYCLE.md from bl_summary_d0q2_<cid>.json for the cycles plotted by bl_d0q_cycle.py (4, 15, 26)."""
import sys, os, json; sys.path.insert(0, '.')
import pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = {c: json.load(open(f'{OUT}/bl_summary_d0q2_{c}.json')) for c in (4, 15, 26)}
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
T = pd.DataFrame([{'cycle': f"{j['und']} expiring {j['expiry']} (D-1 {j['d1']})", 'timetable version': j['version'], 'D-1 pairs': j['D1_pairs'], 'D0 pairs': j['D0_pairs'], 'D-1 pairs repeated on D0 (same second ±3 s)': f"{j['D1_pairs_recurring_on_D0']} of {j['D1_pairs']}",
                   'D0 pairs not on D-1': j['D0_extra_pairs'], 'D-1 window': ' → '.join(j['D1_first_last']), 'D0 window': ' → '.join(j['D0_first_last']), 'strike = ATM of previous close, D-1 / D0': f"{j['D1_strike_atm_share']:.0%} / {j['D0_strike_atm_share']:.0%}"} for j in J.values()])
j4 = J[4]
txt = f"""# Algo 8 — D0 scheduled selling, one cycle at a time: is it the same as D-1?

*Plots one real cycle with D-1 and D0 scheduled selling on the same axes. Script `src/bl_d0q_cycle.py <cid>`; figures `figures/bl_d0q_cycle4.png` (main), `bl_d0q_cycle15.png`, `bl_d0q_cycle26.png`. Descriptive: one cycle each, no fitting.*

## What "V1" and "V2" mean
They are not two systems. The D-1 scheduled timetable (the fixed seconds at which the system sells) is one set of clock times for cycles up to 2026-09-09 (**V1**) and a slightly different set from 2026-09-16 onward (**V2**). It is a date split found in the D-1 work. This page uses real cycles and does not need it.

## Result
**NIFTY cycle (expiry 2026-07-28), the main plot: D0 is D-1's clock plus extra waves.**
* **What matches.**
  * Every wave is 1 CE + 1 PE lot at the ATM strike: D-1 {j4['D1_strike_atm_share']:.0%}, D0 {j4['D0_strike_atm_share']:.0%} at the strike nearest the previous minute's close.
  * The day runs from about 09:16 to 14:30 on both days.
  * {j4['D1_pairs_recurring_on_D0']} of the {j4['D1_pairs']} D-1 pairs repeat on D0 at the same second.
* **What differs.**
  * D0 has **{j4['D0_pairs']} pairs against {j4['D1_pairs']}**: {j4['D0_extra_pairs']} extra pairs. Most of them fall one to two minutes after a 15-minute boundary (block minutes 1–2: {j4['D0_extra_block_minute']['1'] + j4['D0_extra_block_minute']['2']} of {j4['D0_extra_pairs']}), and others {', '.join(f'{v}' for k, v in j4['D0_extra_block_minute'].items() if k not in ('1', '2'))} at other fixed points.
  * Four D-1 pairs do not repeat on D0: {', '.join(j4['D1_not_on_D0'])}.
* **So for NIFTY it is not exactly like D-1.** D0 repeats the D-1 clock and adds roughly twice as many waves. The added waves are fixed clock times too: the same seconds appear on the other NIFTY V1 cycles (`D0_SCHEDULED.md`).

**SENSEX is a different story.** On the two SENSEX cycles plotted:
* Expiring 2026-06-25 (V1): D-1 has 33 pairs, **D0 only 11**, and only 2 repeat. D0 sells once per 15 minutes at about +60 s, from 09:32 to 13:49.
* Expiring 2026-09-17 (V2): D-1 has 34 pairs, D0 has 71, and only 12 repeat.
* So for SENSEX the D0 scheduled selling is **not** the D-1 clock.

{table(T)}

## Caveats
* One cycle per group; the patterns hold across the other cycles of the group (`D0_SCHEDULED.md` §1, §5).
* "Same clock time" means within ±3 s of a D-1 pair of the same cycle.
"""
open(os.path.join(RP, 'D0_SCHEDULED_CYCLE.md'), 'w').write(txt); print('written')
