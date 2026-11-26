"""Builds reports/BODY_REACTIVE_DECODE.md from outputs bl_dq_* and bl_summary_dq1-8.json."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); D1, D2, D3, D4, D5, D6, D7, D8 = [J(f'dq{i}') for i in range(1, 9)]
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
r3 = lambda df, cols: df.assign(**{c: df[c].round(3) for c in cols})
FN = pd.read_csv(f'{OUT}/bl_dq_final.csv'); SB = pd.read_csv(f'{OUT}/bl_dq_final_subsets.csv'); OH = pd.read_csv(f'{OUT}/bl_dq_ohlc.csv'); TG = pd.read_csv(f'{OUT}/bl_dq_tune_grid.csv'); RS = pd.read_csv(f'{OUT}/bl_dq_repeat_sim.csv'); RG = pd.read_csv(f'{OUT}/bl_dq_repeat_gate.csv'); GF = pd.read_csv(f'{OUT}/bl_dq_gate_first.csv'); GR = pd.read_csv(f'{OUT}/bl_dq_gate_repeat.csv'); GM = pd.read_csv(f'{OUT}/bl_dq_gate_models.csv'); CT = pd.read_csv(f'{OUT}/bl_dq_count.csv'); FR = pd.read_csv(f'{OUT}/bl_dq_gate_first_rows.csv')
fin = FN.iloc[0]; fe = D7['first_entry']; bud = D7['budget']; fu = D7['fires_unmatched']; oof = [r for r in D5['rows'] if r['variant'].startswith('out-of-fold')][0]; sp = D5['split_F1']
fn = r3(FN, ['F1', 'precision', 'recall', 'F1_same_minute', 'bar_precision', 'bar_recall'])[['machine', 'F1', 'precision', 'recall', 'F1_same_minute', 'bar_precision', 'bar_recall', 'fires']]; fn.columns = ['machine', 'F1 (±1 min)', 'precision', 'recall', 'F1 same minute', 'bar precision', 'bar recall', 'fires']
oh = r3(OH, ['F1', 'precision', 'recall', 'F1_same_minute', 'bar_precision', 'bar_recall'])[['machine', 'F1', 'precision', 'recall', 'F1_same_minute', 'bar_precision', 'bar_recall']]; oh.columns = ['what changed (targets 10:30-15:15)', 'F1', 'precision', 'recall', 'F1 same minute', 'bar precision', 'bar recall']
sb = r3(SB, ['F1', 'precision', 'recall', 'F1_same_minute', 'bar_precision', 'bar_recall'])[['subset', 'cycles', 'F1', 'precision', 'recall', 'F1_same_minute', 'bar_precision', 'bar_recall']]; sb.columns = ['subset', 'cycles', 'F1', 'precision', 'recall', 'F1 same minute', 'bar precision', 'bar recall']
tg = TG.pivot(index='mu_steps', columns='end_clock', values='F1').round(3).reset_index(); tg = tg[tg.mu_steps.isin([0, 0.02, 0.04, 0.06, 0.1, 0.2])]; tg = tg.rename(columns={'mu_steps': 'minimum break margin (strike steps)'})
rs = r3(RS, ['precision', 'recall', 'F1', 'split_F1_mean'])[['rule', 'configs', 'chosen', 'precision', 'recall', 'F1', 'split_F1_mean']]; rs.columns = ['re-entry rule inside a candle', 'configs', 'parameters chosen (fold 1 / fold 2)', 'precision', 'recall', 'F1 (out-of-fold)', 'F1 random splits']
rg = r3(RG, ['F1', 'precision', 'recall']).fillna(''); rg = rg[['rule', 'F1', 'precision', 'recall']]; rg.columns = ['repeat gate (one feature, threshold out-of-fold)', 'F1', 'precision', 'recall']
names = {'ext_beyond_channel': 'penetration beyond the channel (steps)', 'minute_range': 'minute high-low range (steps)', 'ret5': '5-min move in the break direction', 'ret15': '15-min move in the break direction', 'chan_width': 'channel width (steps)', 'min_in_candle': 'minute within the candle', 'min_since_first': 'minutes since the first entry', 'min_since_last': 'minutes since the last entry', 'n_prev_in_candle': 'entries already in the candle', 'hour': 'time of day', 'vol_net_prev': 'target-strike option volume, previous minute, net of Algo 8', 'vol_rel': 'same, relative to its 30-min mean', 'prem_chg5': 'target pair premium change, 5 min', 'prem_tgt': 'target pair premium', 'short_lots': 'open short lots', 'delta_vs_side': 'book delta against the break side', 'itm_short': 'in-the-money short lots', 'pnl': 'MTM P&L', 'pnl_chg15': 'P&L change, 15 min', 'cover': 'wing coverage (long/short lots)'}
gr = GR.head(10).copy(); gr['variable'] = gr.variable.map(names).fillna(gr.variable); gr = gr.round(3); gr.columns = ['variable (repeat candidates)', 'AUC', 'even cycles', 'odd cycles']
gf = GF.head(8).copy(); gf['variable'] = gf.variable.map(names).fillna(gf.variable); gf = gf.round(3); gf.columns = ['variable (first breaks: entry vs none)', 'AUC', 'even cycles', 'odd cycles']
gm = GM.round(3); gm.columns = ['feature block (repeat candidates)', 'model', 'AUC (leave-one-cycle-out)']
ct = CT.head(8).copy(); ct['variable'] = ct.variable.map(names).fillna(ct.variable); ct = ct.round(4); ct.columns = ['state at the first break', 'Spearman with number of entries in the candle-side', 'p']
neg = FR[FR.y == 0]; n15 = int((neg.hour >= 15).sum()); ntiny = int(((neg.hour < 15) & (neg.ext_beyond_channel < 0.1)).sum())
bt = pd.DataFrame([('real reactive pair-minutes 10:30-15:29', bud['targets']), ('reproduced by the machine (±1 min)', bud['matched']), ('repeat entries inside a candle-side', bud['repeat_in_candle']), ('after 15:15 (machine stops at 15:15)', bud['after_1515']), ('first entry of the candle-side, but more than 1 min from the break', bud['first_entry_timing_off']), ('no machine break in that candle-side', bud['no_machine_break']), ('machine fires with no real entry in that candle-side', fu['no_real_entry_in_candle_side']), ('machine fires in the right candle-side but > 1 min off', fu['timing_off'])], columns=['item', 'count'])
txt = f"""# Algo 8 — reactive pairs decoded: the two-candle breakout (true highs/lows), and what is left

*Investigation only. In-sample (D-1 of 32 live cycles; 274 reactive pair-minutes 10:30–15:29). Exploratory decoding after `BODY_REACTIVE_CLOCK.md`; steps after the first OHLC result are labelled post-hoc. Figures: `figures/bl_dq_example_NIFTY.png`, `figures/bl_dq_example_SENSEX.png`, `figures/bl_dq_summary.png`. Everything here describes behaviour; it does not show Algo 8's source code.*

## 0. Result

| | Number |
|---|---|
| **The rule** | **At each minute from 10:30 to 15:15: if the minute's high breaks above the highest high of the previous two completed clock-aligned 30-minute candles (hh:00–hh:30, hh:30–hh:00), or its low breaks below their lowest low, sell a CE+PE pair one strike beyond ATM on that side — once per side per candle.** No margin, no timer, no indicator. |
| **Accuracy on all reactive pair-minutes** | **F1 {fin.F1:.2f}: precision {pct(fin.precision)}, recall {pct(fin.recall)}**; exact-minute F1 {fin.F1_same_minute:.2f}. Out-of-fold (end time and margin chosen on the other cycle half) {oof['F1']:.2f}; 60 random half-splits {sp[0]:.2f} ({sp[1]:.2f}–{sp[2]:.2f}). |
| **The first entry of each candle-side** | **{fe['machine_within_1min']} of {fe['candle_sides_with_real_entry']} reproduced ({pct(fe['capture'])}), {fe['exact_minute']} at the exact minute ({pct(fe['exact_share'])})**. |
| **Per 30-minute candle** | a real entry in {pct(fin.bar_precision)} of the candles where the machine fires; {pct(fin.bar_recall)} of candles with a real entry have a machine break. |
| **Stable across** | NIFTY {SB[SB.subset == 'NIFTY'].F1.iloc[0]:.2f}, SENSEX {SB[SB.subset == 'SENSEX'].F1.iloc[0]:.2f}, schedule V1 {SB[SB.subset.str.startswith('V1')].F1.iloc[0]:.2f}, V2 {SB[SB.subset.str.startswith('V2')].F1.iloc[0]:.2f}, first/second half of cycles {SB[SB.subset == 'first half of cycles'].F1.iloc[0]:.2f} / {SB[SB.subset == 'second half of cycles'].F1.iloc[0]:.2f}. |
| **What was missing before** | **True one-minute highs and lows.** The earlier work used one-minute closes only (F1 0.64); the full OHLC bars are in the same Breeze dataset. With them the channel is the real candle range and the break is seen inside the minute. |
| **What is left** | **Repeat entries inside a candle-side ({bud['repeat_in_candle']} of {bud['targets']} pair-minutes)** — no price, volume, premium or portfolio rule reproduces them; their number rises when the book is already short the move (ρ ≈ 0.26). Plus {bud['after_1515']} pairs after 15:15 and {fu['no_real_entry_in_candle_side']} machine breaks without an entry (about {n15} of the first-break misses are in the 15:00 candle). |

## 1. What changed the result
{table(oh)}
* Using the true candle high/low for the channel **and** the minute's high/low for the break lifts F1 from 0.65 to 0.83 at once; either change alone does not (0.57–0.64), because a close-based channel is narrower than the real one while a close-based break is late.
* Two candles is the right look-back (one 0.60, three 0.74); one entry per side per candle beats one per candle.

## 2. Final machine, variants and placebos (targets 10:30–15:29)
{table(fn)}
* Shifting the clock by −1, +5 or +15 minutes (the last = candles aligned to 09:15 like the exchange's) destroys the fit: the candles are **hh:00/hh:30-aligned**.
* **No margin:** requiring the break to exceed the channel by even 0.02 strike steps (1 NIFTY point) lowers F1 sharply — the system acts on any break of the level, so its price feed matches this data closely:

{table(tg)}
* The entries effectively stop at about 15:15 (end times 15:00–15:15 are best; extending to 15:29 adds false fires).

## 3. Robustness
{table(sb)}

## 4. Error budget
{table(bt)}
* Of the {fu['no_real_entry_in_candle_side']} machine breaks without an entry, {n15} are in the 15:00–15:30 candle and {ntiny} others are breaks by less than 0.1 strike step; neither a margin nor an earlier end time removes them without losing real entries.

## 5. The repeat entries (post-hoc search for the "other factor")
Repeat = a real entry after the first one in the same candle-side. Descriptively: {pct(D2['new_bar_extreme'])} occur at a **new extreme of the running candle**, {pct(D2['still_beyond_channel'])} while still beyond the channel, {pct(D2['same_side'])} on the same side, {pct(D2['same_strike'])} at the same strike; median gap {D2['gap_q'][2]:.1f} min.
* **Price ladders and timers do not reproduce them** ({D3['n_configs']} configurations, out-of-fold):

{table(rs)}
* **Single-variable gates** on the {D4['n_rep']} eligible minutes (new candle extreme beyond the channel after a first entry; {D4['n_rep_entry']} real repeats):

{table(gr)}
{table(gm)}
{table(rg)}
* **What the number of entries is linked to:** at the first break, more entries follow when the book is already short the move, has more in-the-money short lots and the channel is narrow (19 variables tested; the top three survive a Bonferroni correction):

{table(ct)}
  This fits your "portfolio" idea — the system adds more pairs into a move that is already hurting the book — but it is an association (ρ ≈ 0.25), not a rule; it does not tell *which* new extreme gets the extra pair.
* **Option volume** at the target strike (net of Algo 8's own fills), premium changes, MTM P&L and wing coverage do not separate repeats from non-repeats (AUC 0.45–0.58 in at least one half).

## 6. First breaks without an entry
{table(gf)}
* Few cases ({len(neg)}); the strongest differences are time (the last candle) and the minute within the candle; nothing portfolio-related is consistent across halves.

## 7. The examples
![NIFTY](figures/bl_dq_example_NIFTY.png)

![SENSEX](figures/bl_dq_example_SENSEX.png)

![summary](figures/bl_dq_summary.png)

## 8. Evidence register
| Claim | Label | Basis |
|---|---|---|
| First reactive entry per side per 30-min candle = first intrabar break of the previous two candles' true high/low, from 10:30 to ~15:15 | **Observed (description)** | F1 {fin.F1:.2f}, first entries {pct(fe['capture'])} (exact minute {pct(fe['exact_share'])}); placebos and alternatives worse; stable in all subsets |
| Candles are aligned to hh:00/hh:30, no break margin | **Observed** | clock shifts and margins reduce F1 |
| Number of entries in a candle-side rises with book stress (delta against the move, ITM shorts) and narrow channels | **Observed (association, post-hoc)** | Spearman 0.22–0.26, Bonferroni-significant |
| Which extra extremes get a repeat entry | **Unresolved** | no rule beats the base machine out-of-fold |
| Option volume, premium, P&L, wings gate the entries | **Not supported** | AUC ≈ 0.5 or inconsistent across halves |
| The algorithm computes exactly this | **Not established** | behaviourally equivalent formulations (60-min bar, 30-min timer + 1-min check) |

## 9. Limits and how this could be wrong
* **Exploratory and in-sample.** The 30-minute clock and the OHLC upgrade were found by looking at this data; out-of-fold choices, random splits, subsets and placebos reduce but do not remove optimism. Parameters actually fitted: two candles, one entry per side, 10:30–15:15, no margin — small and stable.
* **±1-minute tolerance** for the headline F1; the exact-minute F1 is {fin.F1_same_minute:.2f}.
* **Feed differences:** a different spot source (or the algorithm using LTP ticks) could move some borderline breaks; the no-margin result suggests the feed is close.
* **Repeat entries and lot sizes** are not decoded; 1–3 lots per entry are not predicted.
* D-1 only; 32 cycles; no source code.

## 10. Files
`src/bl_ohlc.py` (true OHLC loader) → `bl_dq_ohlc.py` (machine with true highs/lows, error decomposition) → `bl_dq_repeat_desc.py` / `bl_dq_repeat_sim.py` (repeats) → `bl_dq_gates.py` (feature gates) → `bl_dq_tune.py` (margin, end time) → `bl_dq_repeat_gate.py` → `bl_dq_final.py` (final evaluation) → `bl_dq_count.py` → `bl_dq_fig.py` → `make_dq_report.py`. Outputs `outputs/bl_dq_*`, `bl_summary_dq1…8.json`. Tests `tests/test_bl.py` (`test_dq_*`).
"""
open(f'{RP}/BODY_REACTIVE_DECODE.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
