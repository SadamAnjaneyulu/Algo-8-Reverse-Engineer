"""Builds reports/BODY_SOLO_DECODE.md from outputs bl_sd_*, bl_summary_sd1-9.json."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); S1, S2, S3, S4, S5, S6, S7, S8, S9, S10 = [J(f'sd{i}') for i in range(1, 11)]
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
r3 = lambda df, cs: df.assign(**{c: df[c].round(3) for c in cs})
SC = pd.read_csv(f'{OUT}/bl_sd_scan.csv'); ST = pd.read_csv(f'{OUT}/bl_sd_state_auc.csv'); LD = pd.read_csv(f'{OUT}/bl_sd_ladder.csv'); SL = pd.read_csv(f'{OUT}/bl_sd_spotladder.csv'); RL = pd.read_csv(f'{OUT}/bl_sd_reactlots.csv'); RA = pd.read_csv(f'{OUT}/bl_sd_reactlots_assoc.csv'); CB = pd.read_csv(f'{OUT}/bl_sd_combined.csv'); CL = pd.read_csv(f'{OUT}/bl_sd_classes.csv')
allbest = CB[CB.stream == 'all'].sort_values('F1', ascending=False).iloc[0]; solo_best = CB[(CB.stream == 'solo')].F1.max(); react_best = CB[CB.stream == 'reactive'].F1.max()
sc = r3(SC[SC.unit == 'burst'].sort_values('F1', ascending=False).head(6), ['F1', 'precision', 'recall']).fillna('')[['kind', 'L', 'K', 'N', 'F1', 'precision', 'recall', 'fires']]; sc.columns = ['machine (spot only)', 'candle (min)', 'candles', 'rolling N (min)', 'F1', 'precision', 'recall', 'fires']
nm = {'last_ratio_prev': 'last-sold premium / its sale price (previous close)', 'last_ratio_ext': 'last-sold premium dip inside the minute (low / sale price)', 'min_since_last': 'minutes since the last sale on that side', 'spot_move_since_last': 'favourable spot move since that sale (steps)', 'own_book': 'own side book ratio (mark / entry)', 'other_book': 'other side book ratio', 'delta_toward': 'book delta toward the side', 'imbalance': 'own lots − other lots', 'hour': 'time of day'}
st = ST.copy(); st['variable'] = st.variable.map(nm); st = r3(st, ['AUC', 'AUC_even', 'AUC_odd', 'median_events', 'median_controls']); st.columns = ['state', 'AUC', 'even cycles', 'odd cycles', 'median at solo decisions', 'median at control minutes']
cb = r3(CB, ['precision', 'recall', 'F1']).drop(columns='params'); cb.columns = ['model (parameters out-of-fold)', 'stream', 'real lots', 'model lots', 'precision', 'recall', 'F1']
cl = r3(CL, ['share', 'precision', 'recall', 'F1']); cl['share'] = cl.share.map(lambda v: pct(v)); cl.columns = ['solo class', 'lots', 'share', 'model component', 'model lots', 'precision', 'recall', 'F1']
rl = RL.assign(bin=pd.cut(RL.depth, [-10, 0, 0.1, 0.2, 0.4, 0.7, 1, 10])).groupby('bin', observed=True).agg(entries=('pairs', 'size'), pairs=('pairs', 'mean'), extra_favourable=('extra_fav', 'mean'), total_lots=('total_lots', 'mean')).round(2).reset_index(); rl['bin'] = rl.bin.astype(str); rl.columns = ['break beyond channel (steps)', 'reactive entries', 'pairs per entry', 'extra favourable lots', 'total lots']
ra = RA.groupby('target').head(5).copy(); ra = r3(ra, ['spearman', 'p']); ra.columns = ['quantity', 'variable', 'Spearman', 'p']
txt = f"""# Algo 8 — solo sells decoded (as far as the data allows), and reactive repeat / multi-lot entries

*Investigation; plan `BODY_SOLO_DECODE_PLAN.md`. In-sample, D-1 of 32 live cycles. Regular solo sells = body CE/PE `open_short` lots not in a scheduled or reactive pair and within 4 strikes of ATM: **1,508 lots, all 1-lot orders** (the 287 deep-OTM batch lots in 3 cycles are separate). Steps after the plan's blocks A–D are post-hoc and labelled. Figure: `figures/bl_sd_summary.png`.*

## 0. What was found

| | Finding | Evidence |
|---|---|---|
| **1. Solo decisions come in bursts** | {pct(1 - S1['lots_per_burst']['1'] / sum(S1['lots_per_burst'].values()))} of solo decisions place 2–8 one-lot orders within 3 s ({S1['bursts']} decisions for 1,508 lots). The quantity per decision varies. | Observed |
| **2. A fifth of "solo" lots belong to the reactive entries** | {pct(CL.share.iloc[0])} of solo lots are placed within seconds of a reactive pair, **always on the favourable side**: CE on a downside break (165 of 168), PE on an upside break (150 of 152). A reactive entry is therefore often *unbalanced*: e.g. 1 pair + 2 extra calls on a fall. | Observed |
| **3. Reactive entry size grows with the depth of the break** | Pairs per entry and the extra favourable lots both rise with how far the minute broke through the two-candle channel (Spearman {RA[(RA.target == 'extra_fav') & (RA.variable == 'depth')].spearman.iloc[0]:.2f} for extras, {RA[(RA.target == 'pairs') & (RA.variable == 'depth')].spearman.iloc[0]:.2f} for pairs): from ≈ 3 lots in total for a hair-line break to ≈ 6 for a break of more than a strike step. A graded size, not a fixed ladder. | Observed (association) |
| **4. Intraday stand-alone solo sells ({pct(CL.share.iloc[1])})** | Fire on **fresh favourable extremes** (CE at a new low, PE at a new high; 60-minute on true highs/lows works best) while the **own side is in profit and the other side losing** (book ratio AUC {ST[ST.variable == 'own_book'].AUC.iloc[0]:.2f} / {ST[ST.variable == 'other_book'].AUC.iloc[0]:.2f}), typically **1–2 minutes after the previous sale on that side** with the last-sold premium dipping ≈ 6% inside the minute — a drip. The best rule (spot ladder of 0.2 strike steps from the previous sale, gated by a fresh 60-minute extreme) reaches decision-level F1 {S6['oof_burst']['F1']:.2f} out-of-fold. | Observed (description); rule incomplete |
| **5. After 15:00 ({pct(CL.share.iloc[2])}) a different regime** | Not trend-following (only {pct(S10['late']['heavier_share'])} on the side already heavier vs {pct(S10['intraday']['heavier_share'])} intraday; median favourable move since the open {S10['late']['median_fav_move']:.1f} vs {S10['intraday']['median_fav_move']:.1f} steps), not buy-back replacement ({pct(S10['late']['after_buyback_share'])} within 2 min of a buy-back on that side), spikes in the 15:00, 15:23 and 15:29 minutes. | Observed; rule **Unresolved** |
| **6. Not portfolio balancing or delta hedging** | Premium-value balance between CE and PE shorts (AUC {S3['ratio_V']:.2f}), lot balance ({S3['ratio_L']:.2f}: sells go to the side that is already *bigger*), book delta (AUC {ST[ST.variable == 'delta_toward'].AUC.iloc[0]:.2f}), a tilt target proportional to the day's move (tilt tracks the move, ρ ≈ {S5['pooled_spearman'][0]:.2f}, but it is the *result* of solo selling, not a target it chases). The "portfolio" link is the profit/loss of the two sides, not balance. | Observed (rejected) |
| **Combined accuracy** | All D-1 sells (scheduled + reactive with depth-sized entries + attached extras + stand-alone ladder; deep-OTM batches excluded): **F1 {allbest.F1:.2f}** (precision {pct(allbest.precision)}, recall {pct(allbest.recall)}). Solo stream alone {solo_best:.2f}; reactive lots {react_best:.2f}. | Observed (out-of-fold) |

**Bottom line: solo selling is understood (when, which side, why) but not decoded as a deterministic rule.** The best combined solo model reproduces about {pct(CB[CB.stream == 'solo'].recall.max())} of solo lots with about {pct(CB[(CB.stream == 'solo') & (CB.F1 == solo_best)].precision.iloc[0])} precision; the after-15:00 sells ({pct(CL.share.iloc[2])}) are a separate, unexplained regime.

## 1. Timing structure (block A)
Gaps between consecutive solo sales on the same side: {pct(S1['lots_per_burst']['1'] / sum(S1['lots_per_burst'].values()))} of decisions are single lots; the rest come as bursts (2: {S1['lots_per_burst']['2']}, 3: {S1['lots_per_burst']['3']}, 4: {S1['lots_per_burst']['4']}, 5+: {sum(v for k, v in S1['lots_per_burst'].items() if int(k) >= 5)} decisions). The second of the minute and the half-hour clock show no structure comparable to the reactive pairs.

## 2. Spot-only machines (block D)
{table(sc)}
* Clock-aligned candles and rolling windows, first break or every new extreme: at most F1 ≈ 0.49 at the decision level. Fresh extremes are necessary-looking but most of them get no solo sale.

## 3. State at a solo decision (block C)
{table(st)}

## 4. Ladders (post-hoc)
* **Premium ladder** (sell again when the last-sold contract's minute low is δ below its sale price): best decision-level F1 {LD[LD.unit == 'burst'].F1.max():.2f} (δ = 2%, with the fresh 60-minute extreme gate).
* **Spot ladder** (sell again every X strike steps beyond the spot at the previous sale, gated by a fresh 60-minute extreme): out-of-fold decision F1 {S6['oof_burst']['F1']:.2f}, lot F1 {S6['oof_lot']['F1']:.2f}.

## 5. Reactive repeat and multi-lot entries (block E)
{table(rl)}
{table(ra)}
* Pairs and extras rise together (an entry with 2 pairs usually also has ≥ 2 extra favourable lots). Sizing the pairs by depth adds only a little to the reactive lot match (F1 {CB[(CB.stream == 'reactive')].F1.min():.2f} → {react_best:.2f}); the repeat entries inside a candle (≈ 18% of reactive pair-minutes) remain undecoded.

## 6. Combined model (out-of-fold)
{table(cb)}
{table(cl)}

![summary](figures/bl_sd_summary.png)

## 7. Evidence register
| Claim | Label |
|---|---|
| Solo decisions are bursts of 1-lot orders | Observed |
| ≈ 21% of solo lots are favourable-side extras of reactive entries | Observed |
| Reactive entry size (pairs + extras) grows with the depth of the break | Observed (association, ρ 0.3–0.4) |
| Intraday solo sells = drip at fresh favourable extremes while the own side profits and the other side loses | Observed (description); best rule F1 ≈ 0.5 |
| After-15:00 solo sells: different regime | Observed; **Unresolved** |
| Premium balance, lot balance, delta hedging, tilt target as the trigger | Not supported |
| A deterministic solo rule | **Not found** |

## 8. Limits
In-sample; D-1 only; minute bars (inside-minute order of events not observable; the break depth uses the minute's full high/low — mild look-ahead); ±1-minute lot matching; many candidate rules were tried (selection risk; parameters out-of-fold); the strike of solo sells follows the previous sale's premium only partly (37% exact).

## 9. Files
`src/bl_sd_build.py` (option OHLC cache, solo order table) → `bl_sd_scan.py` → `bl_sd_state.py` → `bl_sd_balance.py` → `bl_sd_ladder.py` → `bl_sd_tilt.py` → `bl_sd_spotladder.py` → `bl_sd_reactlots.py` → `bl_sd_combined.py` → `bl_sd_classes.py` → `bl_sd_late.py` → `bl_sd_fig.py` → `make_sd_report.py`. Outputs `outputs/bl_sd_*`, `bl_summary_sd1…9.json`. Tests `tests/test_bl.py` (`test_sd_*`).
"""
open(f'{RP}/BODY_SOLO_DECODE.md', 'w').write(txt); print(len(txt.splitlines()))
