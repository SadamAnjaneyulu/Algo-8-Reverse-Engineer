"""Builds reports/D0_SCHEDULED_WHY.md from bl_d0q_detail4.csv / bl_d0q_why_cycle.csv / bl_d0q_why_boundaries.csv / bl_d0q_loo.csv and bl_summary_d0q3.json, bl_summary_d0q4.json."""
import sys, os, json; sys.path.insert(0, '.')
import pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R3 = json.load(open(f'{OUT}/bl_summary_d0q3.json')); R4 = json.load(open(f'{OUT}/bl_summary_d0q4.json')); c = R3['cycle']; lo = R3['loo_pooled']
D = pd.read_csv(f'{OUT}/bl_d0q_why_cycle.csv'); BD = pd.read_csv(f'{OUT}/bl_d0q_why_boundaries.csv'); L = pd.read_csv(f'{OUT}/bl_d0q_loo.csv')
def table(df, fmt=3):
    cc = list(df.columns); s = '| ' + ' | '.join(map(str, cc)) + ' |\n|' + '|'.join('---' for _ in cc) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
dec = R4['decomposition']; g = lambda k: dec[[x for x in dec if x.startswith(k)][0]]; ex = pd.DataFrame(R4['exceptions']); ex['midpoint'] = (ex.strike + ex.ATM_of_prev_close) / 2; ex['spot_minus_midpoint'] = (ex.spot_prev_min_close - ex.midpoint).round(1); md = ex.spot_minus_midpoint.abs()
grp = L.groupby('group').apply(lambda d: pd.Series(dict(pairs=str(len(d)), recur_in_other_cycles=f'{d.recurs_in_other_cycles.mean():.0%}', shifted_null=f'{d.null_shift137.mean():.0%}'))).reset_index()
b = BD[(BD.D1_cycles_with_pair > 0) | (BD.D0_cycles_with_pair > 0)].copy(); b = b.assign(kind=['15-min boundary' if x else 'extra 5-min boundary' for x in b.is_15min])[['boundary', 'kind', 'D1_pairs_per_cycle', 'D0_pairs_per_cycle', 'D1_cycles_with_pair', 'D0_cycles_with_pair']]
b.columns = ['boundary', 'kind', 'D-1 pairs per cycle', 'D0 pairs per cycle', 'D-1: share of cycles', 'D0: share of cycles']
full = D[['time', 'CE_order', 'PE_order', 'strike', 'lots_CE', 'lots_PE', 'px_CE', 'px_PE', 'spot_prev_min_close', 'ATM_of_prev_close', 'strike_is_that_ATM', 'on_D1_clock', 'recurs_in_other_cycles', 'category']].copy(); full['category'] = full.category.str[0]; full.insert(0, '#', range(1, len(full) + 1))
txt = f"""# Algo 8 — D0 scheduled selling: why 83 pairs on D0 against 33 on D-1

*One cycle: NIFTY expiring {c['expiry']} (D-1 = 2026-07-27). Scripts `bl_d0q_detail.py`, `bl_d0q_why.py`. Figures `figures/bl_d0q_why.png` (all NIFTY cycles side by side) and `figures/bl_d0q_cycle4.png`. Descriptive; the recurrence test is leave-one-cycle-out.*

## 0. Answers
1. **Is it really 83 scheduled pairs? Yes, as a clock.**
   * {c['recur_in_other_cycles']} of the 83 fall at the same second in the **other** NIFTY cycles. Across all 30 cycles, {lo['recur']:.0%} of D0 pairs recur at the same second in other cycles; the same test with the times shifted by 137 s gives {lo['null']:.0%}.
   * The 5 that do not recur are the burst at 09:16:19–21, whose size changes from cycle to cycle.
2. **Lots per scheduled pair: exactly 1 CE lot + 1 PE lot.** All {c['pairs']} pairs are 1 + 1. They are {c['lots_in_scheduled_pairs']} lots out of this cycle's {c['total_D0_body_sell_lots']} D0 body sell lots ({c['lots_in_scheduled_pairs'] / c['total_D0_body_sell_lots']:.0%}).
   * Several pairs can fire in the same second: {', '.join(f'{v} at {k}' for k, v in c['same_second_groups'].items())}.
3. **How it executes.**
   * The CE order and the PE order are sent within the same second (median gap {c['ce_to_pe_gap_s_median']:.0f} s) at the same strike, 1 lot each.
   * So each pair is one short straddle at that strike.
4. **"Previous-minute strike selection".** It is my measuring stick, in plain words:
   * at the second of a sale, take the spot index level as of the last **completed** 1-minute candle (for a sale at 09:31:10, the 09:30 candle's close, 24009.0), and find the strike nearest to it (24000);
   * that strike is sold on both CE and PE;
   * it matches {c['strike_is_ATM']} of {c['pairs']} pairs.
   * The system presumably reads the live spot at the exact second. I only have minute candles, so the previous candle's close is the nearest thing I can test.
   * The {c['pairs'] - c['strike_is_ATM']} misses are the cases that support this: the previous candle's close was only {md.min():.1f}–{md.max():.1f} points from the midpoint between two strikes, so the live price had probably crossed it. Table in §3.
5. **Why 83 on D0 and 33 on D-1.**
   * D-1 fires after **{R4['D1_boundaries_used']} marks on the clock**, all of them 15-minute boundaries (09:30, 09:45, …; the timetable skips a few, such as 12:15, 12:45 and 13:00), about {R4['pairs_per_boundary_both_D1']:.1f} pairs after each.
   * D0 fires after **all {R4['D1_boundaries_used']} of those** and **{len(R4['extra_boundaries_D0_only'])} more marks**:
     * 12 are 5-minute marks between the 15-minute boundaries: {', '.join(x for x in R4['extra_boundaries_D0_only'] if x not in ('12:45', '13:00'))};
     * 2 are 15-minute boundaries that D-1 skips: 12:45 and 13:00.
   * D0 also fires more pairs at the shared boundaries (about {R4['pairs_per_boundary_both_D0']:.1f} against {R4['pairs_per_boundary_both_D1']:.1f}).

| the 83 D0 pairs of this cycle | pairs |
|---|---|
| A. same second as a D-1 pair of this cycle | {g('A')} |
| B. at a boundary D-1 also uses, but another second | {g('B')} |
| C. at one of the {len(R4['extra_boundaries_D0_only'])} marks D-1 does not use | {g('C')} |
| E. recur on other days but sit off the 5-minute grid (10:17:58, 12:37:27, 12:37:58, 13:49:01, 14:07:28, 14:27:58) | {g('E')} |
| D. the opening burst at 09:16:19–21 (does not recur) | {g('D')} |
| **total** | **{c['pairs']}** |

The raster (`bl_d0q_why.png`) shows it: the same stripes on every day.

## 1. The recurrence test, by group
Learned without the cycle itself (waves from the other cycles of the group, ±3 s).

{table(grp)}

NIFTY V2 has only 2 usable cycles, so its recurrence cannot be tested this way (low rates there reflect too little data, not a failure).

## 2. Boundary table (NIFTY, timetable V1)
Share of cycles with a pair in the 133 s after each 5-minute mark. Only marks used by D-1 or D0 are listed. `kind` says whether the mark is a 15-minute boundary.

{table(b, 2)}

## 3. Strike: the {c['pairs'] - c['strike_is_ATM']} pairs not at the previous-candle ATM
{table(ex)}

The midpoint between strikes 24000 and 24050 is 24025. In all three the previous close was within {md.max():.1f} points of it (see `spot_minus_midpoint`). That is the signature of a strike read from the live price a few seconds later.

## 4. All {c['pairs']} pairs, in time order
Columns:
* `time`: first order of the pair.
* `px_*`: fill price.
* `spot_prev_min_close`: the spot used for the strike check.
* `on_D1_clock`: same second as a D-1 pair of this cycle (±3 s).
* `recurs`: same second recurs in other cycles.
* Category letters are the table in §0.

{table(full.rename(columns={'recurs_in_other_cycles': 'recurs', 'strike_is_that_ATM': 'is_ATM'}), 1)}

## 5. Not known yet
* **Why exactly these {len(R4['extra_boundaries_D0_only'])} extra marks**, and why D0 fires more pairs per boundary. The times are fixed and repeat on every day, but I have not found the rule that picks them.
* **The size of the 09:16 burst.** It varies by cycle.
* **Whether the extra D0 waves belong to a separate scheduler** (for example a D0-only timer set) **or are the D-1 timer set running at a finer grid.** The data cannot separate the two.

## Run order
`bl_d0q_sched.py` (first) → `bl_d0q_detail.py 4` → `bl_d0q_why.py` → `make_d0qw_report.py`.
"""
open(os.path.join(RP, 'D0_SCHEDULED_WHY.md'), 'w').write(txt); print('written', len(txt))
