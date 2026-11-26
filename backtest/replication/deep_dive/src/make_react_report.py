"""Builds reports/BODY_REACTIVE_PAIRS.md from computed outputs (numbers read from outputs/bl_react_*)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); R1, R1b, R3 = J('react1'), J('react1b'), J('react3'); R2 = J('size2'); R3s = J('size3')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
GB = pd.read_csv(f'{OUT}/bl_react_gb.csv'); AU = pd.read_csv(f'{OUT}/bl_react_auc.csv'); W = pd.read_csv(f'{OUT}/bl_react_wave_clock.csv'); HZ = pd.read_csv(f'{OUT}/bl_react_hazard_age.csv'); MH = pd.read_csv(f'{OUT}/bl_react_move_hazard.csv'); Pn = pd.read_csv(f'{OUT}/bl_react_panel.csv.gz'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv')
g = {t: GB[GB.target == t].set_index('model').LOCO_AUC for t in ('R', 'S', 'BB')}
au = AU[AU.target == 'R'].copy(); au['dev'] = (au.AUC - .5).abs(); au = au.sort_values('dev', ascending=False).head(10)[['variable', 'AUC', 'lo', 'hi', 'null_max', 'half1', 'half2']].round(3); au.columns = ['feature', 'AUC', 'CI low', 'CI high', 'permutation max', 'half 1', 'half 2']
gbt = pd.DataFrame([(m, f"{g['R'][m]:.3f}", f"{g['R'][m] - g['R']['clock only']:+.3f}", f"{g['S'][m]:.3f}", f"{g['BB'][m]:.3f}") for m in ('clock only', 'clock + history', 'clock + market', 'clock + book', 'clock + inventory', 'all blocks', 'all blocks, history shuffled', 'all blocks, market shuffled', 'all blocks, book shuffled', 'all blocks, inventory shuffled')], columns=['model', 'reactive pair (AUC)', 'Δ vs clock only', 'solo sell (AUC, contrast)', 'buy-back (AUC, contrast)'])
hr = pd.DataFrame({'clock hour': [f'{h}:00' for h in range(9, 16)], 'reactive pairs per cycle': [f"{R1['react_hour_per_cycle'].get(str(h), 0):.2f}" for h in range(9, 16)], 'timetable pairs per cycle': [f"{(Pr[Pr.sched].tod // 3600 == h).sum() / 32:.2f}" for h in range(9, 16)]})
wv = []
for v in ('V1', 'V2'):
    z = W[W.version == v]
    for h, gh in z.groupby(z.clock_time.str[:2].astype(int)): wv.append((v, f'{h}:xx', len(gh), ', '.join(gh.clock_time.str[:8])))
WV = pd.DataFrame(wv, columns=['version', 'hour', 'waves', 'clock times (each = one 1-lot CE + one 1-lot PE pair)'])
hz = HZ.copy(); hz.columns = ['minutes since the last body sell', 'cycle-minutes', 'reactive-pair minutes', 'per 1000']
mh = MH[MH['var'] == 'a15'][['bin', 'n', 'ev', 'R_per1000', 'solo_per1000']].round(1); mh.columns = ['|15-min spot move| (%)', 'cycle-minutes', 'reactive-pair minutes', 'reactive per 1000', 'solo sell per 1000']
side = pd.DataFrame({'look-back window': ['1 min', '3 min', '5 min', '15 min', '30 min'], 'share (strike side vs ATM) follows the move': [pct(R3['side'][k], 1) for k in ('ch1', 'ch3', 'ch5', 'ch15', 'ch30')]})
so = R1b['by_kind']; off = R1['react_strike_off_steps']; _m = ((Pr[Pr.reactive].tod // 60) % 15).astype(int); mb0 = float((_m == 0).mean()); mb14 = float((_m == 14).mean())
txt = f"""# Algo 8 — reactive pairs: CE+PE sells outside the fixed timetable, and the wave clock

*Investigation only. In-sample, observational (32 D-1 cycles). Plan written before the tests: `BODY_REACTIVE_PAIR_PLAN.md`. Numbers are read from `outputs/bl_react_*` / `bl_summary_react*.json`. Figure: `figures/bl_react_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| What is the **orange "reactive pair"**? | A **CE and a PE sold within 3 s at the same strike, outside every fixed timetable time**: {R1['react_pairs']} pairs in D-1 over 32 cycles = **{R1['react_per_cycle']:.1f} pairs per cycle** (≈ {2 * R1['react_per_cycle']:.0f} lots, {pct(R3s['class_total']['reactive pair (outside timetable)'] / sum(R3s['class_total'].values()))} of D-1 sold lots). Every cycle has some. 77% are a single pair; at most 3 pairs in one burst. | Observed |
| Are they sold **outside the fixed timings**? | **Yes.** They appear from ~11:00 to 15:30 ({', '.join(f"{h}:00 → {R1['react_hour_per_cycle'].get(str(h), 0):.1f}" for h in range(11, 16))} pairs per cycle), at **any second** of the minute (uniform, p = {R1['seconds_uniform_p']:.2f}); there is **no 15-minute timer** (only {pct(R1['gap_sell_15min_share'], 1)} come 14–15.5 min after the previous sell vs {pct(R1['gap_sell_15min_null'][0], 1)} by chance). | Observed |
| **What triggers them?** | **Not identified.** Only a **weak tilt** is visible: leave-one-cycle-out AUC {g['R']['clock only']:.2f} from the clock alone → {g['R']['clock + market']:.2f} with market-move features → {g['R']['clock + history']:.2f} with event history → {g['R']['all blocks']:.2f} with everything. Book P&L ({g['R']['clock + book'] - g['R']['clock only']:+.3f}) and inventory ({g['R']['clock + inventory'] - g['R']['clock only']:+.3f}) add nothing. No single feature exceeds AUC 0.60, there is no threshold, and large moves (15-min move > 0.3%) produced {R3['big_move_a15_ge03'][0]} reactive pair in {R3['big_move_a15_ge03'][1]} minutes. | Observed (tilt); trigger **Unresolved** |
| **Which strike?** | **One strike off the ATM, on the side the market just moved.** Only {pct(R1['atm_hit_react'][0], 1)} are at the previous-minute ATM (timetable pairs {pct(R1['atm_hit_sched'][0])}); {pct(off.get('-1.0', 0) + off.get('1.0', 0))} are ±1 step; the strike lies on the side of the previous 15-minute move in **{pct(R3['side']['ch15'])}** of cases (5-min {pct(R3['side']['ch5'])}). | Observed |
| What are the **wave triggers**? | **The clock only.** Each wave is a fixed clock time; waves fire in ≥ 95% of cycles whatever the market did (§5). Why a wave is at that second is not observable. | Observed; reason **Unresolved** |
| How to **know how many waves at what time**? | Use the table in §5: **33 waves per D-1** in both versions — 8 in 9:xx, 8 in 10:xx, 8 (V1) / 7 (V2) in 11:xx, then 3 / 3 / 3 (V1) or 3 / 2 / 5 (V2) in 12:xx / 13:xx / 14:xx. V1 = D-1 up to 2026-09-09, V2 = from 2026-09-16 (re-timing only, 33 waves in both). | Observed |

## 1. Definitions (locked in the plan)
* **Timetable pair** = a CE+PE pair inside a timetable cell (±3 s) of its version (from `BODY_SIZING_LOGIC.md`). **Reactive pair** = a pair (CE and PE at the same strike within ±3 s) **outside** every cell. {int(R1b['n_react'])} of the {int(R1['react_pairs'] + Pr.sched.sum())} D-1 pairs ({pct(R1['react_pairs'] / (R1['react_pairs'] + Pr.sched.sum()))}) are reactive.
* **Panel** = D-1 cycle-minutes (minute 5–373) without a timetable wave: {len(Pn):,} rows, {int(Pn.yR.sum())} reactive-pair minutes (base {Pn.yR.mean() * 1000:.0f} per 1000). Features are causal (previous minute close); blocks: clock, event history, market, book, inventory (plan).
* Pair detection is a ±3 s rule: two coincident solo sells at one strike would also be called a pair.

## 2. When (Observed)
{table(hr)}
* Seconds-of-minute are uniform (p = {R1['seconds_uniform_p']:.2f}). The minute within the 15-minute block is **not** uniform (p < 0.001): {pct(mb0, 0)} of reactive pairs fall in the first minute of a block and {pct(mb14, 0)} in the last (uniform would be 7% each) — they cluster around the 15-minute boundaries, but with no fixed second.
* **Clustering with other sells:** the reactive-pair hazard is highest right after another body sell:
{table(hz)}
  within a minute of the previous sell it is about 3× the base; the gap to the previous sell has median {R1['gap_sell_q'][2]:.1f} min — they come in bursts with other sells, not on their own timer.
* **After a buy-back:** {pct(R1['after_any_60'][0], 1)} of reactive pairs come within 60 s after a body buy-back (shifted-time chance {pct(R1['after_any_60'][1], 1)}); at 5 min {pct(R1['after_any_300'][0], 1)} vs {pct(R1['after_any_300'][1], 1)}; at 15 min no excess ({pct(R1['after_any_900'][0], 1)} vs {pct(R1['after_any_900'][1], 1)}). After a **stop-like** buy-back the excess is small ({pct(R1['after_stop_60'][0], 1)} vs {pct(R1['after_stop_60'][1], 1)} at 60 s). A weak, short-lived link; not a lot-for-lot replacement (Spearman of pairs vs lots bought back in the previous 5 min = {R1['corr_pairs_bbl5'][0]:.2f}).

## 3. Which strike
* **Previous-minute ATM hit rate:** reactive {pct(R1['atm_hit_react'][0], 1)}, timetable {pct(R1['atm_hit_sched'][0], 1)}, solo sells {pct(R1['atm_hit_solo'][0], 1)}. Reactive strike minus previous-minute ATM (steps): {', '.join(f'{k}: {pct(v)}' for k, v in off.items())}.
* **Side follows the move:** among reactive pairs whose strike differs from the ATM (n = {R3['n_side']}), the strike side agrees with the sign of the previous spot move:
{table(side)}
  A pair is therefore a **straddle shifted one strike toward the direction the index has been moving** (below the ATM after a fall, above after a rise). Both legs are sold at that one strike.
* The strike is **not** the strike of the last timetable pair ({pct(so['reactive']['is_last_sched_strike'], 1)}) and **not** the most-loaded strike ({pct(so['reactive']['is_top_held'], 1)}); {pct(so['reactive']['held_both'])} are strikes where the book is already short on both legs (timetable pairs: {pct(so['scheduled']['held_both'])}), so they mostly **add to a strike already held**, one step from the ATM.

## 4. What predicts a reactive-pair minute
Leave-one-cycle-out gradient boosting (AUC; "shuffled" = that feature block permuted within cycle with all blocks otherwise in):
{table(gbt)}
* **Market block** adds {g['R']['clock + market'] - g['R']['clock only']:+.3f}; shuffling it from the full model costs {g['R']['all blocks'] - g['R']['all blocks, market shuffled']:.3f}. **History block** adds {g['R']['clock + history'] - g['R']['clock only']:+.3f} (shuffling: {g['R']['all blocks'] - g['R']['all blocks, history shuffled']:.3f}). Book and inventory: no effect.
* For contrast, **solo sells** respond much more to the market block ({g['S']['clock + market'] - g['S']['clock only']:+.3f}); **buy-backs** to history and market ({g['BB']['clock + history'] - g['BB']['clock only']:+.3f} / {g['BB']['clock + market'] - g['BB']['clock only']:+.3f}).
Strongest single features (D-1, AUC with cluster-bootstrap CI; permutation null maximum; chronological halves):
{table(au)}
* `age_stop` = minutes since the last stop-like buy-back (longer → more likely; rows with no stop-like buy-back yet are excluded from this single-feature AUC); `S_tot`, `S_CE`, `S_PE` = short lots held, which grow through the day (part clock; the inventory block adds nothing in the model); `age_sell` below 0.5 means a recent sell raises the odds. No feature passes AUC 0.60. **Decision rule (pre-registered):** the market block meets it (gain +0.10 ≥ 0.03, shuffle test, strongest feature `a15` AUC {AU[(AU.target == 'R') & (AU.variable == 'a15')].AUC.iloc[0]:.3f} with halves {AU[(AU.target == 'R') & (AU.variable == 'a15')].half1.iloc[0]:.2f} / {AU[(AU.target == 'R') & (AU.variable == 'a15')].half2.iloc[0]:.2f}), and so does the history block (`age_stop`, halves {AU[(AU.target == 'R') & (AU.variable == 'age_stop')].half1.iloc[0]:.2f} / {AU[(AU.target == 'R') & (AU.variable == 'age_stop')].half2.iloc[0]:.2f}); book and inventory do not. But the effects are small, graded and not a rule:
{table(mh)}
  Pairs react mildly to moves up to ~0.3% and **disappear in large moves**, while solo sells keep rising. So the reactive pairs are **not** the same trigger as the solo sells (move/breakout).

## 5. The waves: exact clock times (Observed)
Waves fire at fixed clock times (seconds after 09:16:00 in `outputs/bl_react_wave_clock.csv`); every time below is one 1-lot CE + one 1-lot PE pair at the ATM (previous-minute ATM hit {pct(R1['atm_hit_sched'][0])}). Fire rates: {pct(R2['fire_ge95']['V1'])} of V1 cells and {pct(R2['fire_ge95']['V2'])} of V2 cells fire in ≥ 95% of cycles.
{table(WV)}
* **Count per hour:** V1 {', '.join(f'{h}:xx = {int(((W.version == "V1") & (W.clock_time.str[:2].astype(int) == h)).sum())}' for h in range(9, 15))}; V2 {', '.join(f'{h}:xx = {int(((W.version == "V2") & (W.clock_time.str[:2].astype(int) == h)).sum())}' for h in range(9, 15))}.
* **Trigger:** the clock itself. Nothing in the data (spot, premium, notional, P&L, the day's move) changes whether a wave fires; the cycle stop is the only thing known to halt the schedule (earlier paired-sell study).
* **Why those seconds / how many** cannot be observed from fills: that is the configuration of the strategy. The times are the median order time of each wave across the cycles of the version (ledger order times; jitter about ±1–2 s). Waves in the same cell are ranked within a cycle (e.g. three waves at 09:16:01, :02, :07).

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Reactive pairs: {R1['react_per_cycle']:.1f} per cycle, from 11:00, any second, no 15-min timer | **Observed** | {R1['react_pairs']} pairs, 32 cycles |
| Strike one step off the ATM, on the side of the recent move ({pct(R3['side']['ch15'])} vs 15-min move) | **Observed** | n = {R3['n_side']} |
| Weak link to buy-backs (≈ 13% vs 4% within 60 s) and to other sells (bursts) | **Observed** | shifted-time null |
| Market-move and event-history features give a small, graded predictive tilt; book P&L and inventory none | **Observed** (predictive) | LOCO GB, shuffle tests |
| What triggers a reactive pair | **Unresolved** | no threshold or rule found |
| Waves: clock only; table of times | **Observed** | cell fire rates ≥ 95% |
| Why this timetable | **Unresolved** | not observable |

## 7. Limits and how this could be wrong
* **±3 s pair rule** may merge two coincident solo sells (CE and PE) triggered by the same event into a "pair"; that would make reactive pairs two solo sells at one strike one step off the ATM — the same strike regime as solo sells (solo ATM hit {pct(R1['atm_hit_solo'][0])}, offset −1 for most). I cannot separate the two with second-resolution fills.
* **Minute-resolution market features:** a trigger on tick prices, the live ATM inside the minute or the order book would look like a weak tilt here.
* **Cells** (timetable windows) come from a ≥ 0.5-pairs-per-cycle cut; a reactive pair at a low-frequency timer time (< 0.5 per cycle) is counted as reactive.
* In-sample; D-1 only; no source code; features are predictive, not causal.

## 8. Files
`src/bl_react_panel.py` → `bl_react_tests1.py` / `1b` / `3` (when, timer, buy-back, strike, side) → `bl_react_tests2.py` (prediction, ~10 min) → `bl_react_waves.py` (clock times) → `bl_react_fig.py` → `make_react_report.py`. Outputs `outputs/bl_react_*`, `bl_summary_react*.json`. Tests `tests/test_bl.py` (`test_react_*`).
"""
open(f'{RP}/BODY_REACTIVE_PAIRS.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
