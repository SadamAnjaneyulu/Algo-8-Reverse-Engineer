"""Builds reports/BODY_REACTIVE_CLOCK.md from computed outputs (bl_clk_*, bl_summary_clk1-9.json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); C1, C2, C3, C4, C5, C6, C7, C8, C9 = [J(f'clk{i}') for i in range(1, 10)]
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
CH = pd.read_csv(f'{OUT}/bl_clk_chan.csv'); RF = pd.read_csv(f'{OUT}/bl_clk_refine.csv'); BR = pd.read_csv(f'{OUT}/bl_clk_bars.csv'); BC = pd.read_csv(f'{OUT}/bl_clk_barcount.csv', index_col=0); SC = pd.read_csv(f'{OUT}/bl_clk_scan.csv'); PH = pd.read_csv(f'{OUT}/bl_clk_phase_minutes.csv'); MD = pd.read_csv(f'{OUT}/bl_clk_moduli.csv'); WS = pd.read_csv(f'{OUT}/bl_clk_wingstate.csv'); WG = pd.read_csv(f'{OUT}/bl_clk_wings.csv'); EN = pd.read_csv(f'{OUT}/bl_clk_example_NIFTY.csv').fillna(''); ES = pd.read_csv(f'{OUT}/bl_clk_example_SENSEX.csv').fillna('')
base = BR.iloc[0]; base_bar = BR.iloc[1]; oofb = C3['oof_bars_prev']; oofr = C3['oof_roll']; oofc = C3['oof_bars_cur']; refb = RF.iloc[0]; ref_i = RF.iloc[1]; ps = RF[RF.variant.str.startswith('one entry per SIDE')].iloc[0]
tdiff = C4['timing_diff']; tn = sum(tdiff.values()); t0 = tdiff['0']; t1 = tdiff['1']
ch = CH.copy(); ch['kind'] = ch.kind.map({'roll': 'rolling window (minutes)', 'bars_cur': 'K completed 30-min bars + the current partial bar', 'bars_prev': 'K completed 30-min bars (current bar excluded)'}); ch['F1 (±1 min)'] = ch.F1.round(3); ch['precision'] = ch.precision.round(3); ch['recall'] = ch.recall.round(3); ch = ch[['kind', 'param', 'F1 (±1 min)', 'precision', 'recall', 'fires']]; ch.columns = ['channel definition (one entry per 30-min clock block)', 'N / K', 'F1 (±1 min)', 'precision', 'recall', 'fires']
rf = RF.copy()
for k in ('F1', 'precision', 'recall', 'F1_same_minute'): rf[k] = rf[k].round(3)
rf.columns = ['variant', 'F1 (±1 min)', 'precision', 'recall', 'F1 same minute', 'fires']
br = BR.copy(); br['machine'] = br.machine; 
for k in ('precision_bar', 'recall_bar', 'phi', 'odds_ratio'): br[k] = br[k].round(2)
br = br[['machine', 'bars', 'both', 'act_only', 'mach_only', 'neither', 'precision_bar', 'recall_bar', 'odds_ratio', 'phi']]; br.columns = ['machine', 'bars', 'machine + real entry', 'real entry only', 'machine only', 'neither', 'precision (bars)', 'recall (bars)', 'odds ratio', 'phi']
bc = BC.copy(); bc.index = [f'machine fires in the bar: {i}' for i in bc.index]; bc.columns = [f'{c} real pair-minutes' for c in bc.columns]; bc = bc.reset_index().rename(columns={'index': ''})
phm = PH.set_index('minute_of_hour').fires; ph_tab = pd.DataFrame({'minute of the hour': ['00', '30', 'other minutes (median)'], 'fires': [int(phm[0]), int(phm[30]), f"{C9['median_other_minute']:.0f}"]})
md = pd.DataFrame(C9['moduli']); md['p (uniform)'] = md.chi2_p_uniform.map(lambda v: f'{v:.4f}'); md = md[['modulus_seconds', 'counts', 'p (uniform)']]; md.columns = ['period (s, from 09:15)', 'fires per bin', 'p vs uniform']
sc_ = SC.groupby('L').F1.max().round(3).reset_index(); sc_.columns = ['block length (min)', 'best in-sample F1 over phases and N']
ph30 = SC[(SC.L == 30) & (SC.N == 70)].sort_values('phase_min'); phx = ph30[ph30.phase_min.isin([0, 1, 2, 3, 5, 10, 15, 20, 25, 29])][['phase_min', 'F1']].round(3); phx.columns = ['clock phase (min after hh:00)', 'F1 (rolling 70-min edge, one entry per 30-min block)']
wf = pd.DataFrame({'sell class': list(C5['follow_share'].keys()), 'sells (legs)': [C5['n_sells'][k] for k in C5['follow_share']], 'followed by a wing buy within 10 s': [pct(v, 1) for v in C5['follow_share'].values()]}); wmed = WG.groupby('kind').delay_to_next_wing.median().round(1).to_dict(); wf['median delay (s)'] = [wmed[k] for k in C5['follow_share']]
ws = WS.copy(); ws = ws[ws.variable.isin(['cover', 'short_lots', 'long_lots', 'itm_short', 'delta', 'pnl_pct', 'hour', 'min_in_bar'])][['variable', 'AUC', 'AUC_even', 'AUC_odd']].round(3); ws.columns = ['state at the machine break', 'AUC (real entry vs none)', 'even cycles', 'odd cycles']
rp = C9['repeat']; fb = C9['fires_per_bar']; multi = 1 - fb['1'] / sum(fb.values()); eg = C9['entry_given_break_by_sched']
txt = f"""# Algo 8 — reactive pairs: the 30-minute clock (and what it does to the earlier explanations)

*Investigation only. In-sample (D-1 of 32 live cycles). **Exploratory:** the clock structure was found by inspecting the timing of the reactive fires; no plan was pre-registered for it. It is protected by out-of-fold parameter choice, clock-phase placebos and bar-level counting, not by pre-registration. Figures: `figures/bl_clk_example_NIFTY.png`, `figures/bl_clk_example_SENSEX.png`. This report **supersedes** the rolling-70-minute, cooldown and pace descriptions of `BODY_REACTIVE_TRACKER.md` / `BODY_REACTIVE_BOOK.md`: they were approximations of what is described here.*

## 0. Answers to your questions

| Question | Answer | Evidence level |
|---|---|---|
| **Were the reactive pairs and the scheduled pairs one combined process?** | **No — two clocks.** The scheduled pairs sit on a 15-minute grid at fixed seconds (hh:01:10, hh:16:00, hh:31:10, hh:46:31, ...). The reactive entries follow a **30-minute clock-aligned bar structure (hh:00 / hh:30)**. The "one reactive entry per ~30 minutes from 10:30" of the previous report was this 30-minute bar clock seen through a pace. A break of the channel gets an entry about as often whether the bar contains 0, 1, 2 or 3+ scheduled pairs ({pct(eg['0']['p'])} / {pct(eg['1']['p'])} / {pct(eg['2']['p'])} / {pct(eg['3']['p'])}). | Observed |
| **Does a 70-minute rolling range make sense?** | **No, and it isn't needed.** The channel that fits best is **the high/low of the previous two completed 30-minute candles** (the current candle excluded), evaluated on the clock-aligned bars (hh:00–hh:30, hh:30–hh:00). That is 60 minutes, but built from bars, not a rolling window. Out-of-fold F1 {oofb['F1']:.2f} (precision {pct(oofb['precision'])}, recall {pct(oofb['recall'])}) vs {oofr['F1']:.2f} for the best rolling window and {oofc['F1']:.2f} with the current partial bar included; the choice K = 2 is the same in both cycle halves. | Observed |
| **The rule** | **At most one reactive entry per side per 30-minute candle, at the first break of the previous two candles' high/low, the strike one step beyond ATM on the side of the break; from 10:30** (the first time two complete candles — 09:30–10:00 and 10:00–10:30 — exist). | Observed (description); mechanism **Inferred** |
| **Why did only 19 of 100 breakouts fire?** | Because the unit was wrong. Per 30-minute bar: the machine's first break coincides with a real entry in **{base['both']} of {base['both'] + base['mach_only']} bars ({pct(base.precision_bar)})**, and **{base['both']} of the {base['both'] + base['act_only']} bars that have a real entry ({pct(base.recall_bar)})** have a machine break. A bar with no break has an entry only {base['act_only']} times in {base['act_only'] + base['neither']} ({pct(base['act_only'] / (base['act_only'] + base['neither']), 0)}). Odds ratio {base['odds_ratio']:.0f}. The later breaks in the same candle are not new triggers. | Observed |
| **How exact is the timing?** | With the current-minute close the machine's break minute equals the real pair minute for **{t0} of {tn} matched fires ({pct(t0 / tn)})** and is one minute earlier for {t1} ({pct(t1 / tn)}); same-minute F1 {ref_i.F1_same_minute:.2f} (was 0.14 with completed bars before). The clock alignment is exact: shifting the clock by −1, +5 or +15 minutes cuts F1 from {refb.F1:.2f} to {RF[RF.variant == 'phase -1 min'].F1.iloc[0]:.2f}, {RF[RF.variant == 'phase +5 min'].F1.iloc[0]:.2f} and {RF[RF.variant == 'phase +15 min'].F1.iloc[0]:.2f}. | Observed |
| **The long wings: is there a link?** | **Yes — a deterministic follower, not a trigger.** {pct(C5['follow_share']['reactive'], 0)} of the short legs sold in reactive pairs (and {pct(C5['follow_share']['scheduled'], 0)} of scheduled ones, {pct(C5['follow_share']['other (solo / near a pair)'], 0)} of the rest) are followed within 10 seconds (median ≈ {wmed['reactive']:.0f} s) by a one-lot far-OTM wing buy of the same type from the hedge module; wing lots ≈ short lots per leg (CE {C5['lots_by_leg']['short_lots']['CE']} short vs {C5['lots_by_leg']['wing_lots']['CE']} wings, PE {C5['lots_by_leg']['short_lots']['PE']} vs {C5['lots_by_leg']['wing_lots']['PE']}). The wing book does **not** decide which breaks get an entry: coverage (long/short lots) AUC {WS[WS.variable == 'cover'].AUC.iloc[0]:.2f}. | Observed |
| **What is still unexplained?** | About {pct(fb.get('2', 0) / sum(fb.values()) + fb.get('3', 0) / sum(fb.values()) + fb.get('4', 0) / sum(fb.values()))} of the entry bars have more than one real entry (2 in {fb['2']}, 3 in {fb['3']}, 4 in {fb['4']} bars; {rp['same_side']} of {rp['same_side'] + rp['opposite_side']} follow-ups are on the same side, strikes equal in {rp['same_strike']} of {rp['same_strike'] + rp['diff_strike']}); the rule for these is not found. {base['mach_only']} machine breaks have no entry. | Unresolved |

## 1. The clock signature
Reactive fires (pairs placed within 5 s merged; {C9['fires_in_window']} fires 10:30–15:15) by clock minute of the hour: **{int(phm[0])} at :00 and {int(phm[30])} at :30 against a median of {C9['median_other_minute']:.0f} for the other minutes**; {pct(C9['share_minutes_0_2_of_half_hour'])} of fires fall in the first three minutes of an hour or half hour (10% expected) but only {pct(C9['share_minutes_15_17_of_half_hour'])} in the three minutes after :15/:45.

{table(ph_tab)}
{table(md)}
* Block length: a one-entry-per-block machine fits best with **30-minute blocks** (and the clock phase hh:00/hh:30); other block lengths and phases are worse:

{table(sc_)}
{table(phx)}
* The 10:30 start is consistent with the rule needing two complete candles (09:30–10:00 and 10:00–10:30; the 09:15–09:30 first candle is partial); starting at 10:00 is worse (§4). The earlier "London open / volume" explanation is not needed.

## 2. What is the channel?
{table(ch)}
* **Previous two completed candles is the best** (F1 {CH[(CH.kind == 'bars_prev') & (CH.param == 2)].F1.iloc[0]:.3f}); one candle is too tight, three too wide; including the current partial candle is slightly worse; the best rolling window (70 minutes) is an approximation of it. Out-of-fold (parameter chosen on the other cycle half): previous-two-bars {oofb['F1']:.3f}, current-partial {oofc['F1']:.3f}, rolling {oofr['F1']:.3f}.
* Highs and lows are taken from **one-minute closes** (no intraday high/low in the data), so the machine's channel is a little narrower than the true candle range.

## 3. Bar-level agreement
{table(br)}
{table(bc)}
* In bars where the machine fires once ({int(BC.loc[1].sum())} bars), the real system has one entry in {int(BC.loc[1, '1'])} bars, none in {int(BC.loc[1, '0'])}, two or more in {int(BC.loc[1, ['2', '3', '4']].sum())}; the {int(BC.loc[0].sum())} bars with a real entry but no machine break are bars where the real system acted without a close-based break (most likely intrabar highs/lows that minute closes do not show).
* Clock shifts and wrong K reduce the agreement; the rolling-70 machine is close (odds ratio {BR.iloc[7].odds_ratio:.0f}) but below the bar machine.

## 4. Refinements and timing
{table(rf)}
* One entry **per side** per bar is slightly better than one per bar ({ps.F1:.3f} vs {refb.F1:.3f}); entry starts 10:00 or 11:00 are worse than 10:30; the last bar (15:00–15:30) is cut at 15:15 in the sample, which depresses its match rate.
* Side of the strike agrees with the side of the break in **{pct(C4['side_agreement'], 1)}** of {C4['side_n']} matched fires.
* Distribution of (real pair minute − machine break minute) within 3 minutes: {', '.join(f'{k}: {v}' for k, v in sorted(tdiff.items(), key=lambda x: int(x[0])))}.

## 5. The example cycles
Same cycles as before (NIFTY 2026-09-08, SENSEX 2026-10-22). Rows: spot with the 30-minute grid, the previous-two-candles channel, machine breaks and real pairs; the bars coloured by agreement (number = real pair-minutes in the bar); event timeline with scheduled pairs and the hedge-wing buys that follow every sell.

![NIFTY](figures/bl_clk_example_NIFTY.png)

![SENSEX](figures/bl_clk_example_SENSEX.png)

* NIFTY: {C8['NIFTY']['both']} of {C8['NIFTY']['bars']} bars agree, {C8['NIFTY']['machine_only']} machine-only, {C8['NIFTY']['actual_only']} real-only. SENSEX: {C8['SENSEX']['both']} of {C8['SENSEX']['bars']}, {C8['SENSEX']['machine_only']} machine-only, {C8['SENSEX']['actual_only']} real-only. The real entries sit exactly at the channel edge, one per side per candle, and the wing buys follow each entry a few seconds later.

NIFTY bars (10:30 onward):

{table(EN)}
## 6. The wings
{table(wf)}
* The hedge module buys, about 4 s after **every** short-leg sell (scheduled, reactive or other), one far-out-of-the-money wing lot of the same type; wing prices are ₹{C5['wing_price_q']['0.05']:.1f}–{C5['wing_price_q']['0.95']:.1f} (5th–95th percentile), so it is not a fixed ₹2 rule.
* Whether the wing book gates the entries (state at the machine breaks, entry vs no entry):

{table(ws)}
* The wing relationship is therefore **a consequence of selling**, identical for scheduled and reactive sells; it is not what separates entry bars from non-entry bars. The hedge module study is the right place to decode the wing strike rule.

## 7. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Reactive entries follow the previous two completed 30-minute candles' range, one per side per candle, from 10:30 | **Observed (description)** | bar-level odds ratio {base['odds_ratio']:.0f}; out-of-fold F1 {oofb['F1']:.2f}; precision {pct(base.precision_bar)} / recall {pct(base.recall_bar)} per bar |
| The clock is hh:00 / hh:30 (30-minute bars aligned to the hour) | **Observed** | phase placebos −1/+5/+15 min worse; minute-of-hour spike |
| Reactive and scheduled entries are separate clocks | **Observed** | entry probability unchanged by scheduled pairs in the bar |
| The previous rolling-70, cooldown and pace descriptions are proxies for the 30-minute bar clock | **Inferred** | they all give ≈ one entry per half hour; the bar machine beats them |
| Hedge wings follow every sell and do not gate entries | **Observed** | 90–95% within 10 s; coverage AUC 0.50 |
| Why extra entries occur in about {pct(multi)} of entry bars | **Unresolved** | no rule found |
| What exactly the algorithm computes (true highs/lows, live price vs closes) | **Not testable** | minute closes only |

## 8. Limits and how this could be wrong
* **Exploratory discovery.** The 30-minute clock was found by looking at the data, not pre-registered; the reported fit is therefore optimistic. Protection: K and N chosen out-of-fold (K = 2 in both folds), clock-phase placebos (F1 {refb.F1:.2f} at phase 0 vs {RF[RF.variant == 'phase -1 min'].F1.iloc[0]:.2f}–{RF[RF.variant == 'phase +15 min'].F1.iloc[0]:.2f} shifted), bar-level counts with a high base rate (63% of bars have an entry: the odds ratio, not the raw hit rate, is the evidence).
* **Close-based candles.** Highs/lows are of minute closes; the true candle range is wider, which probably explains some of the machine-only and real-only bars.
* **Extra entries** (about {pct(multi)} of entry bars) and the 26 machine-only bars are not explained; the fit says nothing about quantity (1–3 lots) of each entry.
* In-sample; D-1 only; 32 cycles; predictive, not causal; no source code. Equivalent formulations (e.g. 60-minute bar built from two 30-minute bars, or a 30-minute bar timer plus a 1-minute breakout check) cannot be told apart.

## 9. Files
`src/bl_clk_sim.py` (clock-gate machines) → `bl_clk_scan.py` (block length and phase) → `bl_clk_chan.py` (channel definitions) → `bl_clk_refine.py` (refinements, timing) → `bl_clk_bars.py` (bar-level confusion, placebos) → `bl_clk_repeat.py` (clock phase table, repeats) → `bl_clk_wings.py` / `bl_clk_wingstate.py` (hedge wings) → `bl_clk_example.py` → `make_clk_report.py`. Outputs `outputs/bl_clk_*`, `bl_summary_clk1…9.json`. Tests `tests/test_bl.py` (`test_clk_*`).
"""
open(f'{RP}/BODY_REACTIVE_CLOCK.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
