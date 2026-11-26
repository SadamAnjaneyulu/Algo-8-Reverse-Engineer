"""Builds reports/BODY_REACTIVE_ACTIVATION.md from computed outputs (bl_act_*, bl_summary_act*.json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); A1, A2, A3, A4 = J('act1'), J('act2'), J('act3'), J('act4')
pct = lambda x, n=1: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
D = pd.read_csv(f'{OUT}/bl_act_dirs.csv'); GA = pd.read_csv(f'{OUT}/bl_act_gap_auc.csv'); GH = pd.read_csv(f'{OUT}/bl_act_gap_hazard.csv'); GB = pd.read_csv(f'{OUT}/bl_act_gb.csv').set_index('model').LOCO_AUC; LG = pd.read_csv(f'{OUT}/bl_act_lags.csv'); SI = pd.read_csv(f'{OUT}/bl_act_single.csv'); FW = pd.read_csv(f'{OUT}/bl_act_forward.csv'); AU = pd.read_csv(f'{OUT}/bl_act_auc.csv'); DN = pd.read_csv(f'{OUT}/bl_act_density.csv')
dd = D.copy(); dd.columns = ['reference X (direction = sign of live spot − X)', 'pairs', 'hit rate', 'first half', 'second half', 'NIFTY', 'SENSEX', 'Δ vs spot 15 min ago', 'CI low', 'CI high']
for c in ('hit rate', 'first half', 'second half', 'NIFTY', 'SENSEX'): dd[c] = dd[c].map(lambda v: pct(v))
dd['Δ vs spot 15 min ago'] = dd['Δ vs spot 15 min ago'].map(lambda v: f'{v * 100:+.1f} pts'); dd['95% CI of Δ'] = [f'{a * 100:+.1f} … {b * 100:+.1f}' for a, b in zip(D.diff_lo, D.diff_hi)]; dd = dd.drop(columns=['CI low', 'CI high'])
ga = GA[['N_min', 'AUC_abs_gap', 'lo', 'hi', 'half1', 'half2', 'AUC_abs_move_L']].round(3); ga.columns = ['N (minutes)', 'AUC of |spot − N-min moving average|', 'CI low', 'CI high', 'half 1', 'half 2', 'AUC of |spot − spot N min ago| (comparison)']
hb = pd.DataFrame(A4['hazard_bins']); hb['absg'] = hb.absg.astype(str); hb = hb[['absg', 'size', 'sum', 'per1000']]; hb.columns = ['|spot − 60-min average| (strike steps)', 'cycle-minutes', 'reactive-pair minutes', 'per 1000']
gh = GH.pivot(index='subset', columns='gap_group', values='per1000').reindex(['all', 'first half', 'second half', 'NIFTY', 'SENSEX'])[['|gap| < 0.1 step', '0.1 - 0.5', '>= 0.5']].round(1).reset_index(); gh.columns = ['subset', '|gap| < 0.1 step', '0.1 – 0.5 step', '≥ 0.5 step']
lg = LG.copy(); lg = lg[['age_of', 'n_events', 'ev<= 60s', 'ctl<= 60s', 'ev<= 300s', 'ctl<= 300s', 'ev<= 900s', 'ctl<= 900s']]; names = {'age_react': 'previous reactive pair', 'age_sell': 'any body sell', 'age_sched': 'timetable wave', 'age_bb': 'body buy-back', 'age_oth': 'hedge / stop / lump module order'}; lg['age_of'] = lg.age_of.map(names)
for c in lg.columns[2:]: lg[c] = lg[c].map(lambda v: pct(v, 0))
lg.columns = ['time since the last …', 'events', 'within 60 s (events)', 'random seconds', 'within 300 s (events)', 'random seconds ', 'within 900 s (events)', 'random seconds  ']
gb = pd.DataFrame([(m, f'{v:.3f}') for m, v in GB.items()], columns=['model (reactive-pair second vs random second, leave-one-cycle-out AUC)', 'AUC'])
si = SI.head(6).round(3); si.columns = ['feature added to clock + ages (causal)', 'AUC gain']; fw = FW.round(3); fw.columns = ['step', 'feature added (greedy)', 'AUC', 'gain']
s = A4; shm = s['share_minutes_small_gap']; she = s['share_events_small_gap']; best = A1['dirs']; dirs = dict(zip(best['reference X (direction = sign of live spot - X)'], best['hit_rate']))
txt = f"""# Algo 8 — reactive pairs: the dynamic reference and what activates a pair

*Investigation only. In-sample, observational (D-1, {A1['n_events']} reactive pairs, {A1['n_controls']:,} random control seconds inside 10:30–15:15). Plan written before the tests: `BODY_REACTIVE_ACTIVATION_PLAN.md`; the moving-average-gap analysis (§2) was added **after** a single-feature diagnostic pointed to it and is labelled post-hoc. Numbers are read from `outputs/bl_act_*` and `bl_summary_act*.json`. Figure: `figures/bl_act_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| Is it a "look-back" or something dynamic? | **Dynamic, yes: the live spot compared with a trailing price level** — either the spot 10–60 minutes ago or a moving average of the last 5–60 minutes. All of these give the same strike side ({pct(min(dirs[k] for k in ('spot 10 min ago', 'spot 15 min ago', 'spot 30 min ago', 'spot 60 min ago', 'SMA 5', 'SMA 10', 'SMA 15', 'SMA 30', 'SMA 60')), 1)}–{pct(max(dirs.values()), 1)} hit rate on the live-spot proxy); none beats the others by more than {max(D.diff_hi.max(), 0) * 100:.1f} points. **Anchors tied to the book or the day** fit clearly worse: short-book centre {pct(dirs['short-book centre'], 0)}, last timetable-pair strike {pct(dirs['last timetable pair strike'], 0)}, day mid-range {pct(dirs['day mid-range'], 0)}, opening ATM {pct(dirs['opening ATM'], 0)}, last sold strike {pct(dirs['last body sell strike'], 0)}, last reactive strike {pct(dirs['last reactive pair strike'], 0)}. So the reference is **recent price level, not the position or a clock anchor**; which exact smoothing (5–60 min, average or earlier price) is not identifiable. | Observed (family); exact form Not identifiable |
| **When does a reactive pair activate?** | Three facts, none a complete rule: **(1) time gate** 10:30–15:15 (earlier study). **(2) Not when the spot sits on its own average:** with |spot − 60-min average| < 0.1 strike step the rate is **{GH[(GH.subset == 'all') & (GH.gap_group == '|gap| < 0.1 step')].per1000.iloc[0]:.1f} per 1000 cycle-minutes**, with the gap at 0.1–0.5 step **{GH[(GH.subset == 'all') & (GH.gap_group == '0.1 - 0.5')].per1000.iloc[0]:.0f}**, and ≥ 0.5 step **{GH[(GH.subset == 'all') & (GH.gap_group == '>= 0.5')].per1000.iloc[0]:.0f}** (only {pct(she, 1)} of pairs occur with a gap < 0.1 step although it covers {pct(shm, 0)} of minutes); the same in both halves and both underlyings. The sign of the gap is the direction of the strike. **(3) Clustering with other orders:** {pct(LG.set_index('age_of').loc['age_sell', 'ev<= 300s'], 0)} of pairs come within 5 minutes of another body sell (random seconds: {pct(LG.set_index('age_of').loc['age_sell', 'ctl<= 300s'], 0)}), {pct(LG.set_index('age_of').loc['age_oth', 'ev<= 60s'], 0)} within 60 s of a hedge/stop/lump-module order (random: {pct(LG.set_index('age_of').loc['age_oth', 'ctl<= 60s'], 0)}), {pct(LG.set_index('age_of').loc['age_bb', 'ev<= 60s'], 0)} within 60 s of a body buy-back (random: {pct(LG.set_index('age_of').loc['age_bb', 'ctl<= 60s'], 0)}). | Observed; rule **Unresolved** |
| So is the gap the trigger? | **Part of it — a necessary-looking condition, not a sufficient one.** "No clear direction (spot ≈ its average) → almost no pair" fits a rule that needs a defined side; but beyond ≈ 0.3 step the rate **saturates** (≈ {hb['per 1000'].iloc[4:8].min():.0f}–{hb['per 1000'].iloc[4:8].max():.0f} per 1000 for gaps of 0.3–1.5 steps) instead of rising, so it does not fire at a threshold crossing and still does not say *when* within the active periods. Causal models (completed bars only) separate pair seconds from random seconds with AUC **{GB['CAUSAL: all blocks']:.2f}** (clock alone {GB['clock only']:.2f}, + order-activity ages {GB['clock + ages']:.2f}, + spot-position block {GB['CAUSAL (completed bars only): clock + ages + spot_position']:.2f}); adding the *current minute's* move (look-ahead) lifts it to {GB['CAUSAL: all blocks + current-minute move (look-ahead)']:.2f} and the live-spot proxy to {GB['LIVE-PROXY all blocks']:.2f}, i.e. part of the activation is a **movement inside the minute that minute bars cannot see**. | Observed (predictive); trigger **Unresolved** |
| How often is it calculated? | **Still not testable.** The strike and the activation are both consistent with a live-spot comparison made at the order moment; continuous evaluation vs evaluation at firing cannot be separated. | Not testable |

## 1. Which reference does the live spot get compared with?
Hit rate of the strike rule "nearest strike to the live spot + 1 step × sign(live spot − X)" for each pre-registered X (live-spot proxy = linear interpolation between the bracketing minute closes at the order second; diagnostic, uses the current minute's close):
{table(dd)}
* Trend-type references (red in the figure) are within a point of each other and hold in both halves and both underlyings; book-based and day-based references lose 10–60 points. **Decision rule:** no candidate beats "spot 15 minutes ago" by ≥ 3 points, so no more specific dynamic reference is supported; the family "live spot vs a trailing price" is.
* Why the book anchors fail (inference): the strike side follows the *market*, not the position — a reactive pair is placed toward where the price has been going, even when that is away from the strikes already held.

## 2. Activation: the gap between the spot and its moving average (post-hoc)
A single-feature diagnostic (leave-one-cycle-out gain over clock + order-activity ages, causal features) ranked the spot's distance from its moving averages first:
{table(si)}
Greedy forward selection adds only {', '.join(f'`{f}`' for f in FW.feature_added)} in turn (AUC {', '.join(f'{v:.3f}' for v in FW.LOCO_AUC)}); the SMA gap carries almost all of the spot-position gain. Events versus random seconds, by control-quintile of the 60-minute gap: the middle quintile (spot within about ±0.1 step of its average) holds {pct(DN[(DN.feature == 'c_d_sma60') & (DN.control_quintile == 3)].share_of_events.iloc[0], 1)} of events against 20% of controls (ratio {DN[(DN.feature == 'c_d_sma60') & (DN.control_quintile == 3)].ratio.iloc[0]:.2f}), the two outer quintiles {DN[(DN.feature == 'c_d_sma60') & (DN.control_quintile == 1)].ratio.iloc[0]:.1f}× and {DN[(DN.feature == 'c_d_sma60') & (DN.control_quintile == 5)].ratio.iloc[0]:.1f}×.
Minute-level, causal (completed bars, 10:30–15:15, no timetable wave; N = averaging window):
{table(ga)}
* |spot − moving average| separates better than the plain move |spot − spot N min ago| at every N from 10 to 90, and peaks on a plateau at N = 15–45 (AUC about 0.65); N = 3–5 and N ≥ 90 are worse. **The averaging length is not sharply identified** (10–60 fits).
Reactive-pair hazard by |spot − 60-minute average|:
{table(hb)}
{table(gh)}
* **Dead zone, then saturation:** the first adjacent step ≥ 2.8× is at 0.1–0.2 step; from 0.3 step on the rate is flat (≈ {hb['per 1000'].iloc[4:8].min():.0f}–{hb['per 1000'].iloc[4:8].max():.0f} per 1000) and falls only beyond 1.5 steps (few minutes). My pre-registered line for a *threshold* (≥ 3× between adjacent bins) is just missed (2.85×), so I call this a **dead zone around the average**, not a threshold. In points: 0.1 step is about 5 points on NIFTY and 10 on SENSEX (≈ 0.02% of the index, the same "flat" level as the earlier moving-vs-flat result).

## 3. Clustering with other order activity (Observed)
Time since the previous event of each kind, for pair seconds vs random seconds inside the active window:
{table(lg)}
* Reactive pairs sit in **bursts of order activity** (other sells, hedge/stop/lump-module orders, buy-backs, a previous reactive pair), not in quiet periods. The hedge-module link is expected: that module reacts to body fills. Whether a common decision loop produces all of these or one causes the other cannot be told apart here.

## 4. Causal vs live-spot
{table(gb)}
* The big jump comes from the spot-position block even with completed bars only ({GB['CAUSAL (completed bars only): clock + ages + spot_position']:.2f} vs {GB['clock + ages']:.2f}); the extra from the current-minute move (+{GB['CAUSAL: all blocks + current-minute move (look-ahead)'] - GB['CAUSAL: all blocks']:.2f}) and the live proxy shows the decision reacting to the spot **within** the minute, consistent with the strike result (live proxy 90% vs completed bar 80%).
* Block shuffles on the live-proxy model: spot position −{GB['LIVE-PROXY all blocks'] - GB['LIVE-PROXY all blocks, spot_position shuffled']:.3f}, order-activity ages −{GB['LIVE-PROXY all blocks'] - GB['LIVE-PROXY all blocks, ages shuffled']:.3f}, ATM dynamics and the move block ≈ 0 once the others are in.

## 5. Evidence register
| Claim | Label | Basis |
|---|---|---|
| The reference is the live spot vs a trailing price level (spot N min ago or a 5–60 min moving average); book/day anchors fit worse | **Observed** | 15 pre-registered references, halves, underlyings |
| The exact reference / averaging length (5–60 min) | **Not identifiable** | plateau |
| Almost no reactive pairs when the spot sits on its moving average (rate ≈ 4 vs 27–41 per 1000) | **Observed** (post-hoc discovery) | both halves, both underlyings |
| The gap fires a pair at a threshold | **Not supported** | saturating, biggest adjacent step 2.85× |
| Pairs cluster with other order activity | **Observed** | events vs random seconds |
| Part of the activation is intra-minute movement | **Inferred** | look-ahead / live-proxy gain |
| What exactly activates a pair | **Unresolved** | no complete rule |
| Whether direction/gap is computed every minute | **Not testable** | — |

## 6. Limits and how this could be wrong
* **Post-hoc discovery:** the SMA-gap finding followed a search over ~27 candidate features; it replicates in both halves and both underlyings and in a separate minute-level panel, but it was found, not pre-registered, and the candidate AUCs are not multiplicity-corrected.
* **Live-spot proxy** uses the current minute's close (linear path); the look-ahead part of the activation result should be read as "there is intra-minute information", not as a causal rule.
* **Controls** are random seconds in the active window (30 per event); a different control scheme (e.g. matched to other-sell times) would change the order-activity result.
* **Collinearity:** moving-average gaps, spot-N-minutes-ago and the day's position move together; the plateau means I cannot name one.
* In-sample; D-1 only; 32 cycles; predictive not causal; no source code or tick data.

## 7. Files
`src/bl_act_build.py` (events, controls, features, direction references) → `bl_act_tests.py` (AUC, blocks, lags) → `bl_act_tests2.py` (single-feature diagnostic) → `bl_act_tests3.py` (SMA gap, minute level) → `bl_act_fig.py` → `make_act_report.py`. Outputs `outputs/bl_act_*`, `bl_summary_act*.json`. Tests `tests/test_bl.py` (`test_act_*`).
"""
open(f'{RP}/BODY_REACTIVE_ACTIVATION.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
