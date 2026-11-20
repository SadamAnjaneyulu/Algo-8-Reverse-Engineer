"""Builds reports/BODY_REACTIVE_INDICATOR.md from computed outputs (bl_ind_*, bl_summary_ind*.json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); I1, I2, I3 = J('ind'), J('ind2'), J('ind3')
pct = lambda x, n=1: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
F = pd.read_csv(f'{OUT}/bl_ind_family_cv.csv'); B = pd.read_csv(f'{OUT}/bl_ind_boot.csv').set_index('family'); NR = pd.read_csv(f'{OUT}/bl_ind_norm.csv'); CB = pd.read_csv(f'{OUT}/bl_ind_combo.csv'); FN = pd.read_csv(f'{OUT}/bl_ind_fine.csv'); RB = pd.read_csv(f'{OUT}/bl_ind_robust.csv'); BD = pd.read_csv(f'{OUT}/bl_ind_bands.csv'); EP = pd.read_csv(f'{OUT}/bl_ind_episode.csv'); S = pd.read_csv(f'{OUT}/bl_ind_scores.csv').set_index('indicator')
ft = F[['family', 'n_params', 'D_crossvalidated', 'best_D_param', 'A_crossvalidated', 'best_A_param', 'params_within_0.01_A']].copy(); ft['D_crossvalidated'] = ft.D_crossvalidated.map(lambda v: pct(v)); ft['A_crossvalidated'] = ft.A_crossvalidated.round(3)
ft['A: paired bootstrap difference vs the best (95% CI)'] = [f"{B.loc[f, 'A_diff_vs_best_lo']:+.3f} … {B.loc[f, 'A_diff_vs_best_hi']:+.3f}" for f in F.family]; ft['D: difference vs the best D family (95% CI)'] = [f"{B.loc[f, 'D_diff_vs_best_lo'] * 100:+.1f} … {B.loc[f, 'D_diff_vs_best_hi'] * 100:+.1f} pts" for f in F.family]
ft.columns = ['indicator family', 'parameters tested', 'direction hit (cross-validated)', 'best N / parameter for direction', 'activation AUC (cross-validated)', 'best N / parameter for activation', 'parameters within 0.01 AUC of best', 'activation: paired bootstrap difference vs the best (95% CI)', 'direction: difference vs the best direction family (95% CI)']
ft = ft[['indicator family', 'direction hit (cross-validated)', 'direction: difference vs the best direction family (95% CI)', 'activation AUC (cross-validated)', 'activation: paired bootstrap difference vs the best (95% CI)', 'best N / parameter for activation', 'parameters within 0.01 AUC of best']]
nr = NR.copy(); nr.columns = ['N (minutes)', 'AUC of abs(spot − SMA) in steps', 'AUC of abs(Bollinger z)', 'AUC of abs(spot − SMA) / ATR', 'direction hit of SMA gap']
cb = CB.copy(); cb.columns = ['model (leave-one-cycle-out logistic on |values|)', 'AUC', 'gain vs the leading indicator alone']
fn = FN.copy(); fn['AUC'] = fn.AUC.round(3); fn['95% CI'] = [f'{a:.3f}–{b:.3f}' for a, b in zip(FN.lo, FN.hi)]; fn['difference vs N = 60'] = [f'{a:+.3f} … {b:+.3f}' for a, b in zip(FN.diff_vs_60_lo, FN.diff_vs_60_hi)]; fn['direction hit'] = fn.direction_hit.map(lambda v: pct(v)); fn = fn[['N_min', 'AUC', '95% CI', 'difference vs N = 60', 'direction hit']]; fn.columns = ['channel length N (min)', 'activation AUC', '95% CI', 'difference vs N = 60 (95% CI)', 'direction hit']
rb = RB.copy(); rb.columns = ['subset', 'pairs', 'activation AUC (N = 60)', 'direction hit']; rb['direction hit'] = rb['direction hit'].map(lambda v: pct(v)); rb['activation AUC (N = 60)'] = rb['activation AUC (N = 60)'].round(3)
bd = BD.copy(); bd['share_of_events'] = bd.share_of_events.map(lambda v: pct(v)); bd['share_of_control_seconds'] = bd.share_of_control_seconds.map(lambda v: pct(v)); bd['ratio'] = bd.ratio.round(1); bd['rate_per1000_min'] = bd.rate_per1000_min.round(0); bd.iloc[:, 0] = bd.iloc[:, 0].str.replace('|pos|', 'abs position', regex=False)
bd.columns = ['state of the live spot vs the previous 60 completed closes', 'share of pairs', 'share of random seconds', 'ratio', 'implied pair rate per 1000 min']
st = pd.DataFrame(I2['state']); st = st[['N_min', 'share_of_minutes_in_breakout_state', 'hazard_in_state_per1000', 'hazard_outside_per1000', 'ratio', 'share_of_events_in_state']]; st['share_of_minutes_in_breakout_state'] = st.share_of_minutes_in_breakout_state.map(lambda v: pct(v)); st['share_of_events_in_state'] = st.share_of_events_in_state.map(lambda v: pct(v)); st = st.round(1); st.columns = ['N (min)', 'share of minutes in the state', 'pair rate in the state (per 1000)', 'outside', 'ratio', 'share of pair-minutes in the state']
sn = pd.DataFrame(I2['since']); sn['sb'] = ['not in breakout', 'minute 1', 'minute 2', 'minute 3', 'minutes 4–5', 'minutes 6–10'][:len(sn)]; sn = sn[['sb', 'size', 'sum', 'per1000']]; sn.columns = ['minutes since the 60-min breakout began', 'cycle-minutes', 'pair minutes', 'per 1000']
LV = F[F.family.isin(['Donchian position','EMA z','Bollinger z','CCI-like gap/MAD','gap/ATR','EMA gap','WMA gap','SMA gap','Donchian mid gap','momentum','momentum/sigma','MACD'])].D_crossvalidated
topA = F.iloc[0]; nxt = F.iloc[1]; zone = I1['zone']; dec = pd.DataFrame(zone['deciles']); top10 = dec.share_events.iloc[-1]; low = dec.share_events.iloc[:5].sum()
inner = BD[BD.iloc[:, 0].str.startswith('inner')]; beyond = BD.iloc[0]
txt = f"""# Algo 8 — reactive pairs: which indicator best reproduces the behaviour?

*Investigation only. In-sample, observational (D-1, {len(RB) and int(RB.events.iloc[0])} reactive pairs, 10,890 random control seconds inside 10:30–15:15). Plan written before the tests: `BODY_REACTIVE_INDICATOR_PLAN.md`; the range-/MAD-/RSI-based relatives and the breakout reading (§4–§5) were added **after** the first search and are labelled post-hoc. Numbers are read from `outputs/bl_ind_*` and `bl_summary_ind*.json`. Figure: `figures/bl_ind_logic.png`. Everything below is about what *explains* the behaviour; **it does not show that Algo 8 uses this (or any named) indicator.***

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Which indicator best reproduces it?** | **The position of the live spot inside its own trailing high–low range of the last ~45–65 minutes** (a Donchian-channel / stochastic-type position: v = (spot − low)/(high − low) − 0.5, the high and low taken over the previous N completed one-minute closes). Its side (above or below the middle of the range) gives the strike direction, and its distance from the middle gives the activation: **{pct(top10, 0)} of pairs fall in the top decile of abs(v) (spot at or beyond the edge of the range) against 10% of random seconds**; only {pct(inner.share_of_events.iloc[0] if len(inner) else 0.033)} of pairs occur with the spot in the inner half of the range ({pct(inner.share_of_control_seconds.iloc[0] if len(inner) else 0.432, 0)} of random seconds). Activation AUC **{topA.A_crossvalidated:.3f}** (parameter chosen on the other half of the cycles) vs {nxt.A_crossvalidated:.3f} for the best moving-average-type indicator ({nxt.family}) and **{F[F.family == 'SMA gap'].A_crossvalidated.iloc[0]:.3f} for the plain SMA gap**. | Observed (best-fitting indicator); not a statement about Algo 8's code |
| Is the SMA / trend-with-neutral-zone idea right? | **Partly.** For the **direction** every level-type indicator (SMA/EMA/WMA gap, momentum, Bollinger z, Donchian position, MACD) gives the same {pct(LV.min(), 0)}–{pct(LV.max(), 0)} hit rate, so direction **cannot** distinguish them; SMA cross-overs, regression slopes and RSI/efficiency ratio are somewhat worse. For the **neutral zone** the standard SMA gap is a poor description (AUC {S.loc['SMA gap|10', 'activation_AUC']:.2f}); normalising the distance by volatility helps (z-score {NR.A_abs_bollinger_z.max():.2f}) and normalising by the **range** helps most ({FN.AUC.max():.2f}). So the neutral zone is **relative**, not a fixed distance from an average. | Observed |
| Which window? | **About 45–65 minutes, most likely 60** (AUC plateau {FN[FN.N_min == 45].AUC.iloc[0]:.3f}–{FN.AUC.max():.3f}; CIs of 45–65 vs 60 include 0; ≤ 35 and ≥ 75 minutes are worse). A 60-minute window is a natural choice but 45–65 are statistically equal. | Observed (plateau); exact N Not identifiable |
| Is it a breakout? | **Yes in the sense that matters:** {pct(beyond.share_of_events, 0)} of pairs are placed while the live spot is **beyond the previous 60-minute high or low** (random seconds {pct(beyond.share_of_control_seconds, 1)}); with completed bars only, a close beyond the previous 60 closes lifts the pair rate {I2['state']['ratio'][3]:.1f}× ({I2['state']['hazard_in_state_per1000'][3]:.0f} vs {I2['state']['hazard_outside_per1000'][3]:.0f} per 1000 minutes) and the rate is highest in the first minute after it ({I2['since']['per1000'][1]:.0f} per 1000). **But a breakout does not fire a pair every time:** only {pct(I2['episodes_with_pair'], 0)} of the {I2['episodes']} completed-bar breakout episodes contain a pair minute, and {pct(1 - I2['pair_minutes_in_episodes'], 0)} of pair minutes have no completed-bar breakout (the breakout is happening inside the minute). | Observed; trigger **Unresolved** |
| Anything that adds to it? | **No.** Adding the SMA gap, Bollinger/EMA z, gap/ATR, momentum, SMA cross, MACD, regression drift, RSI or a second (15-minute) range position to the 60-minute range position changes leave-one-cycle-out AUC by at most {CB.gain_vs_alone.iloc[1:].abs().max():+.4f} (alone: {CB.LOCO_AUC.iloc[0]:.3f}): the range position subsumes the other indicator-like variables. | Observed |

## 1. What was tested
Families and parameter grids were fixed in the plan (SMA/EMA/WMA gap, momentum, regression drift and line, SMA cross-over, MACD-like, Donchian mid-gap, Bollinger z, gap/ATR; N or span 3–120 minutes). **Post-hoc additions** after Bollinger z led: CCI-like gap/MAD, momentum/σ, Donchian **position**, RSI minus 50, efficiency ratio, EMA z. Indicators use completed one-minute closes of the spot (no spot high/low or volume exists in the data, so Supertrend, SAR, ATR from ranges and VWAP are not testable); the live spot is the linear interpolation between the two bracketing closes at the order second (diagnostic proxy). **Direction metric** = share of pairs whose strike equals nearest(live spot) + one step × sign(indicator). **Activation metric** = AUC of |indicator| for pair seconds vs random seconds. **Selection:** the parameter of each family is chosen on one half of the cycles and scored on the other half, both ways.

## 2. Family ranking
{table(ft)}

* **Direction:** the level-type families are within about 1.5 points of each other and indistinguishable (paired CIs reach 0 for {', '.join(I1['indistinguishable_D'][:7])}); **SMA cross-over ({pct(F[F.family == 'SMA cross'].D_crossvalidated.iloc[0], 0)}), regression line gap ({pct(F[F.family == 'regression line gap'].D_crossvalidated.iloc[0], 0)}), regression drift ({pct(F[F.family == 'regression drift'].D_crossvalidated.iloc[0], 0)}) and RSI/efficiency ratio ({pct(F[F.family == 'RSI minus 50'].D_crossvalidated.iloc[0], 0)}) are clearly worse**.
* **Activation:** **Donchian position beats every other family** (paired bootstrap differences all negative with CIs excluding 0; the closest, EMA z, is {B.loc['EMA z', 'A_diff_vs_best_lo']:+.3f} … {B.loc['EMA z', 'A_diff_vs_best_hi']:+.3f} below). **Pre-registered rule:** "identified" only if the family wins both metrics; it wins activation decisively but the direction metric cannot discriminate, so strictly the answer is **identified on activation, undecidable on direction**.
* **Normalising helps:** at the same N the volatility-scaled distances beat the absolute gap in steps (Bollinger z − absolute gap: {I1['norm_boot']['z_minus_abs'][2]:+.3f} AUC, CI {I1['norm_boot']['z_minus_abs'][0]:+.3f} … {I1['norm_boot']['z_minus_abs'][1]:+.3f}; gap/ATR: {I1['norm_boot']['atr_minus_abs'][2]:+.3f}, CI {I1['norm_boot']['atr_minus_abs'][0]:+.3f} … {I1['norm_boot']['atr_minus_abs'][1]:+.3f}; N = {I1['norm_boot']['N']}):

{table(nr)}

  A neutral band fixed in index points or strike steps is therefore not the right description; one scaled by recent volatility or by the recent range is.

## 3. Channel length (Donchian position, fine grid)
{table(fn)}

* Plateau 45–65 minutes. CIs of 45, 50, 55 and 65 vs 60 include 0; 40 and 70 touch 0; ≤ 35 and ≥ 75 are clearly worse. The direction hit is flat ({pct(FN.direction_hit.min(), 0)}–{pct(FN.direction_hit.max(), 0)}) across N.

## 4. Robustness and the neutral zone
{table(rb)}

* Holds in both halves, both underlyings and both schedule versions. Neutral zone in range units (deciles of the absolute distance of the position from the middle, defined on random seconds): the lowest five deciles hold {pct(low, 1)} of pairs; the top decile holds {pct(top10, 0)} (the implied pair rate is ≈ {dec.rate_per1000_min.iloc[-1]:.0f} per 1000 minutes at the edge vs ≈ {dec.rate_per1000_min.iloc[:4].mean():.0f} in the lower deciles). **The neutral zone is "the inside of the range", not a band around an average.**

{table(bd)}


## 5. Breakout reading (post-hoc; completed bars only, no live proxy)
{table(st)}
{table(sn)}

* Breakout episodes (N = 60, runs of consecutive completed-bar breakout minutes): {I2['episodes']} episodes, median length {I2['episode_len_q'][1]:.0f} minute(s); **{pct(I2['episodes_with_pair'], 0)} contain a pair minute**; median delay to the first pair {I2['first_pair_delay_q'][1]:.0f} minutes; {pct(I2['pair_minutes_in_episodes'], 0)} of the {I2['pair_minutes_total']} pair minutes fall inside an episode.
* Reading: reactive pairs are placed **when the live spot is at or beyond the edge of its trailing ~hour range, toward that edge**, but being at the edge is **not sufficient** (most breakouts have no pair) and not always visible on completed bars (60% of pair minutes). Whatever else is required (the time gate, a refractory/throttle, order-activity clustering found earlier) is still unknown.
* This links to the earlier solo-sell finding (solo sells follow fresh favourable extremes): the same kind of range-edge information appears to drive both order types, with different strike and size rules.

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Best-fitting indicator: position of the live spot in its trailing 45–65-minute high–low range (activation AUC {topA.A_crossvalidated:.2f}, cross-validated) | **Observed** | 17 families, parameter chosen out of fold, paired bootstrap |
| Direction cannot distinguish level-type indicators (SMA gap, EMA, momentum, Bollinger z, Donchian position, MACD) | **Observed** | {pct(LV.min(), 1)}–{pct(LV.max(), 1)} cross-validated; paired CIs reach 0 |
| The neutral zone is relative (volatility- or range-scaled), not a fixed distance from an SMA | **Observed** | normalised vs absolute AUC differences |
| Pairs are placed at/beyond the range edge, toward the edge; not every breakout fires one | **Observed** | 65% beyond the band vs 6.5% of random seconds; 17% of episodes |
| Algo 8 uses a Donchian channel (or any named indicator) | **Not established** | best-fitting description only; custom calculation possible |
| The exact window (60 vs 45–65) | **Not identifiable** | plateau |
| What exactly fires a pair | **Unresolved** | breakout is necessary-looking, not sufficient |

## 7. Limits and how this could be wrong
* **Selection among many candidates:** 17 families × parameters; parameters were chosen out of fold and family differences use paired cluster bootstrap, but the range-/MAD-/RSI additions followed the first result (post-hoc) and no multiplicity correction is applied. The margin of Donchian position over EMA z is {-B.loc['EMA z', 'A_diff_vs_best_hi']:.3f}–{-B.loc['EMA z', 'A_diff_vs_best_lo']:.3f} AUC (paired CI excludes 0) but is modest, and the 0.91 value is the best of a post-hoc-extended search.
* **Closes only:** the "high" and "low" are highs and lows of one-minute **closes** (no intraday high/low data). Indicators that need true highs/lows (ATR, Supertrend, SAR) could not be tested and might fit as well.
* **Live-spot proxy** (uses the current minute's close); the completed-bar results in §5 are the proxy-free check and are weaker (40% of pair minutes vs 65% of events beyond the band) because many breakouts occur inside the minute.
* **Equivalent formulations:** "position in the N-minute range", "new N-minute high/low breakout" and "stochastic %K − 50" are the same signal here; I cannot tell which Algo 8 would call it.
* In-sample; D-1 only; 363 events; predictive, not causal; no source code.

## 8. Files
`src/bl_ind_build.py` (indicator values for events and controls) → `bl_ind_tests.py` (scores, cross-validated families, bootstrap, normalisation, zone, combinations) → `bl_ind_break.py` (robustness, bands, completed-bar breakout, episodes) → `bl_ind_fine.py` (channel length) → `bl_ind_fig.py` → `make_ind_report.py`. Outputs `outputs/bl_ind_*`, `bl_summary_ind*.json`. Tests `tests/test_bl.py` (`test_ind_*`).
"""
open(f'{RP}/BODY_REACTIVE_INDICATOR.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
