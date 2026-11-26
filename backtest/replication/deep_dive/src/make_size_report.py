"""Builds reports/BODY_SIZING_LOGIC.md from the computed outputs (numbers read from outputs/bl_size_*.csv|json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import *
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); R1, R2, R3 = J('size1'), J('size2'), J('size3')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
Cc = pd.read_csv(f'{OUT}/bl_size_cells.csv'); U = pd.read_csv(f'{OUT}/bl_size_unit.csv'); CP = pd.read_csv(f'{OUT}/bl_size_changepoint.csv'); H = pd.read_csv(f'{OUT}/bl_size_solo_hour.csv', index_col=0); SD = pd.read_csv(f'{OUT}/bl_size_state_tests.csv'); ND = pd.read_csv(f'{OUT}/bl_size_notional_dates.csv'); BU = pd.read_csv(f'{OUT}/bl_size_buildup.csv'); ST = pd.read_csv(f'{OUT}/bl_size_state.csv'); AD = pd.read_csv(f'{OUT}/bl_size_v1_v2_diff.csv'); LC = pd.read_csv(f'{OUT}/bl_size_lot_classes.csv'); CC = pd.read_csv(f'{OUT}/bl_size_class_cycle.csv')
clock = lambda k: f'{9 + (16 + 15 * k) // 60}:{(16 + 15 * k) % 60:02d}'
def cellstr(v, k):
    z = Cc[(Cc.version == v) & (Cc.k == k)].sort_values('lo'); 
    if z.empty: return '—'
    return ', '.join(f'{int(r.ce_mode)}×@{int(r.lo):+d}s' if r.lo == r.hi else f'{int(r.ce_mode)}×@{int(r.lo):+d}…{int(r.hi):+d}s' for r in z.itertuples())
rows = []
for k in range(22):
    n1 = int(Cc[(Cc.version == 'V1') & (Cc.k == k)].ce_mode.sum()); n2 = int(Cc[(Cc.version == 'V2') & (Cc.k == k)].ce_mode.sum()); rows.append((clock(k), n1, cellstr('V1', k), n2, cellstr('V2', k)))
TT = pd.DataFrame(rows, columns=['block (IST)', 'V1 pairs', 'V1 waves (lots @ seconds after block start)', 'V2 pairs', 'V2 waves'])
unit = U.pivot(index='month', columns='und', values='gcd').reset_index(); unit['NIFTY min / max qty'] = [f"{int(a)} / {int(b)}" for a, b in zip(U[U.und == 'NIFTY'].min_qty, U[U.und == 'NIFTY'].max_qty)]; unit['SENSEX min / max qty'] = [f"{int(a)} / {int(b)}" for a, b in zip(U[U.und == 'SENSEX'].min_qty, U[U.und == 'SENSEX'].max_qty)]; unit.columns = ['month', 'NIFTY gcd (qty)', 'SENSEX gcd (qty)', 'NIFTY min / max order qty', 'SENSEX min / max order qty']
cp = CP.head(4).copy(); cp.columns = ['last D-1 in early group', 'first D-1 in late group', 'cycles early', 'within-group cost']
loss_k = sorted(int(k) for k, d in zip(AD.k, AD['diff']) for _ in range(max(-d, 0))); gain_k = sorted(int(k) for k, d in zip(AD.k, AD['diff']) for _ in range(max(d, 0)))
ad = AD[AD['diff'] != 0].copy(); ad['block'] = ad.k.map(clock); ad = ad[['block', 'lo', 'V1', 'V2', 'diff']]; ad.columns = ['block (IST)', 'offset (s after block start)', 'V1 CE lots in cell', 'V2 CE lots in cell', 'change']
cc = CC.groupby('version')[['scheduled cell', 'reactive pair (outside timetable)', 'solo', 'total']].agg(['mean', 'median', 'min', 'max']).round(1); cc.columns = [f'{a} {b}' for a, b in cc.columns]; cc = cc.reset_index()
cl = pd.DataFrame({'class': ['scheduled (timetable cell)', 'reactive pair (outside timetable)', 'solo'], 'lots per cycle (mean)': [f"{R3['class_per_cycle_mean'][k]:.1f}" for k in ('scheduled cell', 'reactive pair (outside timetable)', 'solo')], 'median': [f"{R3['class_per_cycle_median'][k]:.0f}" for k in ('scheduled cell', 'reactive pair (outside timetable)', 'solo')], 'share of D-1 sold lots': [pct(R3['class_total'][k] / sum(R3['class_total'].values())) for k in ('scheduled cell', 'reactive pair (outside timetable)', 'solo')]})
hh = H.copy(); hh.index = [f'{int(i)}:00' for i in hh.index]; hh = hh[['scheduled cell', 'reactive pair (outside timetable)', 'solo']].round(1).reset_index(); hh.columns = ['clock hour', 'scheduled', 'reactive pair', 'solo']
bt = BU.groupby('clock_hour')[['sold', 'sold_scheduled', 'bought_back', 'net_short_body']].median().round(1).reset_index(); bt['clock_hour'] = ['10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '15:30']; bt.columns = ['by clock time', 'sold', 'of which timetable', 'bought back', 'net short']
sd = SD.sort_values('perm_p').head(5).copy(); nt = len(SD); sd['Holm-adjusted p (x%d tests)' % nt] = (sd.perm_p * nt).clip(upper=1).round(3); sd = sd[['target', 'state_variable', 'subset', 'n', 'spearman', 'perm_p', 'Holm-adjusted p (x%d tests)' % nt]].round(3)
ndr = ND[(ND.d1 >= '2026-08-31') & (ND.d1 <= '2026-09-30')][['d1', 'und', 'version', 'notional_lakh']]; ndr.columns = ['D-1 date', 'underlying', 'version', '₹ lakh per lot (unit × spot at D-1 open)']
# premium/notional context
S = LC.merge(load_orders()[(load_orders().module == 'num') & (load_orders().role == 'open_short') & (load_orders().dayno == 0)][['und', 'expiry', 'te', 'cp', 'strike', 'px_avg']].drop_duplicates(['und', 'expiry', 'te', 'cp', 'strike']), on=['und', 'expiry', 'te', 'cp', 'strike'], how='left'); S['prem'] = S.lots * S.px_avg * S.und.map(ref.LOT)
pc = S.groupby(['und', 'expiry', 'cls3']).prem.sum().unstack(fill_value=0); pc['sched_pct_capital'] = pc['scheduled cell'] / 2e7 * 100; pc['all_pct_capital'] = pc.sum(axis=1) / 2e7 * 100
ns = BU[BU.clock_hour == 15.5].merge(ST[['und', 'expiry', 'notional_per_lot']], on=['und', 'expiry']); ns['gross_notional_cr'] = ns.net_short_body * ns.notional_per_lot / 1e7
bt1 = BU[BU.version == 'V1'].groupby('clock_hour').net_short_body.median(); bt2 = BU[BU.version == 'V2'].groupby('clock_hour').net_short_body.median()
st3 = R3['state_tests']; stdf = pd.DataFrame(st3)
sch = R2['sched_total']; mod = R2['modal_cell_lots']
txt = f"""# Algo 8 — body position sizing on D-1: how many lots, when, and did the lot-size change matter?

*Investigation only (no simulator change). In-sample, observational: 32 cycles with a D-1 log (21 in version V1, 11 in V2). Plan written before the tests: `BODY_SIZING_PLAN.md`. Every number is read from `outputs/bl_size_*` / `bl_summary_size*.json`. Figure: `figures/bl_size_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| Did the **lot size change in September**? | **Not in the ledger.** Every order quantity in every month June–October 2026 is a multiple of **65 (NIFTY) / 20 (SENSEX)**; minimum order = 1 lot throughout. Public sources show the last NIFTY revision (75→65) took effect **30 Dec 2025** and was computed from **September 2025** prices (probably the "September" you remember); I found no report of a September 2026 revision (I did not read the exchange circulars myself). | Observed (ledger); external check unverified at source |
| Is it exactly **1 lot of CE+PE every 15 min**? | **No.** Each *wave* is exactly one 1-lot CE + one 1-lot PE pair at the same strike (94.7% of all pairs, D-1 and D0, are 1+1), but there are **0–4 waves per 15-minute block**, at **fixed seconds inside the block**, on a fixed timetable (§3). Over D-1 the timetable sells **{R2['modal_cell_lots']['V1'][0]} CE + {R2['modal_cell_lots']['V1'][1]} PE lots (V1)**; observed {sch['V1']['ce'][0]:.1f} ± {sch['V1']['ce'][1]:.1f} CE / {sch['V1']['pe'][0]:.1f} ± {sch['V1']['pe'][1]:.1f} PE lots per cycle. | Observed |
| What is the **trigger** for more than 1 lot? | **Only the clock.** The extra lots are additional waves at other seconds of the same block; each timetable cell fires in ≥95% of cycles ({pct(R2['fire_ge95']['V1'])} of V1 cells, {pct(R2['fire_ge95']['V2'])} of V2 cells; median fire rate {pct(R2['fire_median']['V1'])}); both legs are empty in only {R2['cell_misses']} of {R2['cell_obs']} cell-cycle observations. The scheduled total shows **no relation to spot, notional per lot, straddle premium or the day's move** (best Holm-adjusted p over all {nt} tests = {sd['Holm-adjusted p (x%d tests)' % nt].min():.2f}, for reactive pairs; for the scheduled total itself {min(1, SD[SD.target == 'sched_total'].perm_p.min() * nt):.2f}). Why that particular timetable (33 pairs per day, those seconds) cannot be observed. | Observed (clock); reason **Unresolved** |
| What changed in September? | **A re-timing, not a re-sizing.** Between D-1 2026-09-09 and 2026-09-16 (both underlyings) {R2['v_diff_cells']} cells changed, net **{R2['v_diff_net']} lots**: seven waves were re-timed (each addition sits at or after a removal, i.e. consistent with moving waves later, from seconds up to about an hour; the one-to-one matching is not unique); the scheduled total stayed at ≈ 33–34 pairs. Notional per lot fell ~5% (15.4–15.7 → 14.5–15.2 ₹ lakh) but lots did not rise or fall. SENSEX crossed ₹15 lakh per lot at the change (15.00 → 14.89), NIFTY did not (15.50 → 15.19): a lot-value rule would not give a common date. | Observed; cause **Unresolved** |
| **How many lots in total** are added over D-1? | Median **{BU[BU.clock_hour == 15.5].sold.median():.0f} lots sold** (both rights) in D-1 by 15:30, **{BU[BU.clock_hour == 15.5].net_short_body.median():.0f} net short** after buy-backs: timetable {R3['class_per_cycle_median']['scheduled cell']:.0f}, reactive pairs {R3['class_per_cycle_median']['reactive pair (outside timetable)']:.0f}, solo {R3['class_per_cycle_median']['solo']:.0f} (medians per cycle). | Observed |
| **Single-option (solo) sells** in between? | **{R3['class_total']['solo']:,} lots = {pct(R3['class_total']['solo'] / sum(R3['class_total'].values()))} of D-1 sold lots, {R3['class_per_cycle_median']['solo']:.0f} per cycle (median), {pct(R3['solo_by_right']['CE'] / (R3['solo_by_right']['CE'] + R3['solo_by_right']['PE']))} on the CE side.** 78% are single 1-lot orders; 90% of bursts are ≤ 2 lots; the largest burst is {R3['solo_burst_size_q'][3]:.0f} lots. About {pct(H.loc[15, 'solo'] / H.solo.sum())} of solo lots come after 15:00. Their trigger was studied earlier (breakout, own profit, other leg's loss) and is not re-tested here. | Observed |

## 1. Definitions (locked in the plan)
* **Pair** = body `open_short` CE and PE at the same strike within ±3 s. **Solo** = body `open_short` not in a pair. **Block k** = 15 minutes starting 09:16:00 + 900·k s; **offset** = seconds after the block start. **Cell** = (block, offset window) in which a version's modal timetable has ≥ 0.5 pairs per cycle; the cell quantity of a cycle = body CE (PE) lots sold in the window ±3 s, any strike.
* **Versions** V1 / V2: the best single change-point of the D-1 cell-count vectors (below), not assumed.
* D-1 only; D0 is not analysed here.

## 2. The contract unit (Observed)
{table(unit)}
The gcd of all order quantities is the contract unit every month, so there is **no change of unit in the ledger**. All order sizes in this study are therefore in lots of 65 / 20 throughout.

## 3. The timetable: waves at fixed seconds inside each 15-minute block
Pairs per block and the in-block offsets of the waves (V1 = until D-1 2026-09-09, V2 = from 2026-09-16; "2×@+0s" means two 1-lot pairs about 0–2 s after the block start):
{table(TT)}
* **It is a timetable, not a ladder with a trend.** The pairs per block are 3, 2, 3, 1, 4 (V1) / 3, 2, 3, 1, 3 (V2), then 1, 2, 2, 2, 1, 3, 1, 0, 2, 0, 0, 2 …; the same fixed seconds recur across blocks (about +0 s, +10 s, +31 s, +58 s, +66 s, +91 s, and +840 s = the last minute before the next block). Blocks 12, 14 and 15 have **no** scheduled waves (12:16, 12:46, 13:01).
* The timetable is **independent of NIFTY vs SENSEX** (same lots, same seconds) and **the same for CE and PE**.
* The cell quantities are constant across cycles (mode share of cell-cycles, median over cells {pct(Cc.ce_eq_mode.median())}); the misses are {R2['misses_by_block']} (cell-cycles with both legs empty, by block: the opening block of NIFTY 2026-10-06, and the last cell (14:45) in five NIFTY V2 cycles and no SENSEX cycle).

## 4. V1 → V2 (the September edit)
Change-point scan over D-1 dates (lowest cost = best single split of the cell-count vectors; the early-group / late-group labels are the D-1 dates on each side):
{table(cp)}
The best split is **after D-1 2026-09-09 / before 2026-09-16**, but the cost is only marginally lower than the next candidates (a coarse metric on 32 cycles), so I treat the change window as **2026-09-10 … 09-16** and V1/V2 membership as above (the earlier paired-sell study found the same window).

Cells whose modal quantity differs V1 → V2:
{table(ad)}
Net change {R2['v_diff_net']} lots: seven cells lose a wave and seven gain one, so waves are **re-timed**, not added or removed. Sorted by block, every gain is at or after the corresponding loss (blocks {'/'.join(f'{a}→{b}' for a, b in zip(loss_k, gain_k))}), which is consistent with moving waves **later**; the one-to-one matching is not unique. Notional per lot around the change:
{table(ndr)}
* **Lot unit: unchanged.** **Total scheduled lots: unchanged** (V1 {sch['V1']['ce'][0]:.1f} / V2 {sch['V2']['ce'][0]:.1f} CE lots per cycle) although notional per lot fell by about 5%. So the schedule is **not sized from lot value**; and a SEBI lot-size revision cannot be the reason because the unit did not move.
* The two underlyings switch together although SENSEX's lot value crossed ₹15 lakh at the change and NIFTY's did not — consistent with a **common dated configuration edit**, not a market-state rule. Cause: **Unresolved**.

## 5. Is the timetable sized or triggered by something other than the clock?
Spearman correlation across cycles (n = 32; permutation p; strongest five of {nt} tests):
{table(sd)}
* No test survives Holm correction. The scheduled total, the reactive pairs and the solo lots show no reliable dependence on notional per lot, spot level, the opening straddle premium or the day's spot move. (The nominal p = {SD.perm_p.min():.3f} for reactive pairs vs the opening straddle premium becomes {min(1, SD.perm_p.min() * nt):.2f} after Holm.)
* **Decision rules:** "fixed timetable" — met for V1 (all {R2['cells']['V1']} cells ≥ 95%; scheduled total std {sch['V1']['ce'][1]:.1f} lots on {sch['V1']['ce'][0]:.0f}) and essentially for V2 ({int(round(R2['fire_ge95']['V2'] * R2['cells']['V2']))} of {R2['cells']['V2']} cells ≥ 95%; the exceptions are the two block-0 cells, where one cycle (NIFTY 2026-10-06) has no pair in the opening block (10 of 11), and one 14:31 cell (6 of 11)); "sized from notional/capital" — **not supported** (no |ρ| ≥ 0.4 surviving the null).

## 6. How quantity builds up through D-1
Median over cycles (both rights, body lots):
{table(bt)}
* Roughly **16 timetable lots per hour until ~12:00** (about 8 pairs per hour), then ~6 per hour until 15:00 and none after; reactive pairs and solo lots add the rest, and buy-backs remove about a quarter of what is sold by the end of the day. The net short book grows by about **20 lots per hour in the morning** and about **10 per hour afterwards**.
* Context only (not margin): timetable premium = {pc.sched_pct_capital.median():.2f}% of ₹2 crore per cycle (median), all body sells {pc.all_pct_capital.median():.2f}%; the net short body at 15:30 is **{ns.gross_notional_cr.median():.1f} crore of option notional** (median; {ns.gross_notional_cr.median() / 2:.1f}× the stated capital; lots × unit × spot).

## 7. Lots by class and by hour (mean lots per cycle)
{table(cl)}
{table(hh)}
* The **timetable dominates before 12:00**; reactive pairs (a CE and a PE at one strike seconds apart, outside the timetable) and solo sells dominate afterwards. **15:00–15:30 is almost entirely solo sells** ({H.loc[15, 'solo']:.1f} lots per cycle) with no timetable.
* Solo lots per cycle by version: V1 mean {CC[CC.version == 'V1'].solo.mean():.0f} (median {CC[CC.version == 'V1'].solo.median():.0f}), V2 mean {CC[CC.version == 'V2'].solo.mean():.0f} (median {CC[CC.version == 'V2'].solo.median():.0f}; one V2 cycle sells {CC.solo.max():.0f} solo lots, which pulls the mean up).
* **Replacement?** Of the non-timetable sells, {pct(R3['replace_within60'][0])} come within 60 s after a body buy-back in the same cycle (shifted-time chance {pct(R3['replace_within60'][1])}): a link exists, but the lots sold are not matched to the lots bought back (Spearman {R3['replace_corr'][0]:.2f} on {R3['replace_corr'][1]} buy-back minutes). Not a lot-for-lot replacement.

## 8. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Contract unit constant at 65 / 20 in every month Jun–Oct 2026 | **Observed** | gcd and minimum order quantity by month (§2) |
| No September 2026 lot revision found in public sources; last revision effective 30 Dec 2025 | **Not verified at source** | web search only |
| D-1 CE+PE sells are 1-lot waves on a fixed in-block timetable (0–4 per block) | **Observed** | {R2['cell_obs']} cell-cycle observations, {pct(R2['fire_ge95']['V1'])}/{pct(R2['fire_ge95']['V2'])} cells ≥95% |
| About 33 pairs (66 lots) scheduled per D-1, same in V1 and V2 | **Observed** | {sch['V1']['ce'][0]:.1f} / {sch['V2']['ce'][0]:.1f} CE lots per cycle |
| September edit re-times 7 waves, net 0 lots, between 2026-09-09 and 09-16 | **Observed** | cell diff + change-point scan |
| Scheduled quantity does not depend on notional, premium, spot or the day's move | **Observed** (not supported) | 36 tests (3 targets × 4 state variables × 3 subsets), none after Holm |
| Why this timetable / why the edit | **Unresolved** | clock facts only |
| Solo sells: {pct(R3['class_total']['solo'] / sum(R3['class_total'].values()))} of D-1 lots, CE-heavy, mostly single lots | **Observed** | {R3['solo_orders']} orders |

## 9. Limits and how this could be wrong
* **Pair detection is a ±3 s rule**; two coincident solo sells at one strike would be called a pair. The timetable cells are stable enough (fire ≥ 95%) that this is unlikely to matter for them, but it can inflate "reactive pairs".
* **Timetable cells** are the modal cells chosen with a ≥ 0.5 pairs-per-cycle cut (a threshold chosen after seeing the cluster table); the V1→V2 diff and totals depend on it only mildly (cells are all ~1.0).
* **Version membership** (V1/V2) comes from a coarse change-point; a cycle could be misassigned near 09-09 / 09-16.
* **Why** a timetable has these seconds and totals cannot be recovered from fills; the instructions behind it (config / code release) are not in the data. A date-based edit in mid-September coincides with nothing I could identify in the ledger.
* **External check:** the "no September revision" point rests on a web search, not on NSE/BSE circulars; the ledger itself shows no unit change either way.
* In-sample; D-1 only; the 5 cycles without D-1/D0 logs are excluded; reconstructed behaviour, not source logic.

## 9b. Files
`src/bl_size_build.py` (unit, pairs, solo, change-point) → `bl_size_tests.py` (cells, totals, V1/V2 diff, misses) → `bl_size_tests2.py` (classes, build-up, solo, replacement, state, notional) → `bl_size_fig.py` → `make_size_report.py`. Outputs `outputs/bl_size_*`, `bl_summary_size*.json`. Tests `tests/test_bl.py` (`test_size_*`).
"""
open(f'{RP}/BODY_SIZING_LOGIC.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
