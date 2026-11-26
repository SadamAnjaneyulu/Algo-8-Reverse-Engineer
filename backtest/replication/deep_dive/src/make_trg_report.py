"""Builds reports/BODY_REACTIVE_TRIGGER.md from computed outputs (bl_trg_*, bl_summary_trg1-5.json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); R1, R2, R3, R4, R5 = J('trg1'), J('trg2'), J('trg3'), J('trg4'), J('trg5')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
S = pd.read_csv(f'{OUT}/bl_trg_bandscan.csv'); BK = pd.read_csv(f'{OUT}/bl_trg_blocks.csv'); EPI = pd.read_csv(f'{OUT}/bl_trg_episode.csv'); RF = pd.read_csv(f'{OUT}/bl_trg_refract.csv'); TR = pd.read_csv(f'{OUT}/bl_trg_tree.csv'); UN = pd.read_csv(f'{OUT}/bl_trg_uni.csv'); RP_ = pd.read_csv(f'{OUT}/bl_trg_repeat.csv'); MV = pd.read_csv(f'{OUT}/bl_trg_move.csv'); LG = pd.read_csv(f'{OUT}/bl_trg_leg.csv'); GP = pd.read_csv(f'{OUT}/bl_trg_gaps.csv'); P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz')
n_cyc = P.cid.nunique(); n_pm = int(P.y.sum()); n_pairs = int(P.n_pairs.sum()); n_min = len(P); bk = (P.bk60 != 0); la = (P.bkLA60 != 0)
cau_rec = (bk & (P.y == 1)).sum() / n_pm; la_rec = (la & (P.y == 1)).sum() / n_pm; cau_prec = (bk & (P.y == 1)).sum() / bk.sum(); la_prec = (la & (P.y == 1)).sum() / la.sum(); in_haz = ((~la) & (P.y == 1)).sum() / (~la).sum() * 1000
# band table
sb = S[S.window.isin(['N20', 'N30', 'N40', 'N45', 'N50', 'N55', 'N60', 'N65', 'N70', 'N80', 'N90', 'N120', 'EXP'])].copy(); sb['window'] = sb.window.replace({'EXP': 'expanding since the open'}).str.replace('N', 'N = ', regex=False)
sb['AUC'] = sb.AUC.round(3); sb['AUC upper edge'] = sb.AUC_upper_edge.round(3); sb['AUC lower edge'] = sb.AUC_lower_edge.round(3); sb['AUC even / odd cycles'] = [f'{a:.3f} / {b:.3f}' for a, b in zip(sb.AUC_half_even, sb.AUC_half_odd)]; sb['share of pairs beyond the band'] = sb.share_events_beyond.map(lambda v: pct(v, 1)); sb['random seconds'] = sb.share_controls_beyond.map(lambda v: pct(v, 1)); sb['difference vs N = 60 (95% CI)'] = [f'{a:+.3f} … {b:+.3f}' for a, b in zip(sb.diff_vs_best_lo, sb.diff_vs_best_hi)]
sb = sb[['window', 'AUC', 'AUC upper edge', 'AUC lower edge', 'AUC even / odd cycles', 'share of pairs beyond the band', 'random seconds', 'difference vs N = 60 (95% CI)']]
# blocks table (look-ahead breakout minutes + causal + all)
def blk(pop, BK=BK):
    d = BK[BK.population.str.startswith(pop) & (BK.features != 'edge only')].copy(); a = d[d.model == 'lr'].set_index('features'); b = d[d.model == 'gb'].set_index('features'); e = BK[BK.population.str.startswith(pop) & (BK.features == 'edge only')].set_index('model')
    t = pd.DataFrame({'block added to the edge features': [f.replace('edge + ', '') for f in a.index], 'logistic AUC': a.AUC.round(3).values, 'logistic gain (95% CI)': [f'{g:+.3f} ({lo:+.3f} … {hi:+.3f})' for g, lo, hi in zip(a.gain_vs_edge_only, a.gain_lo, a.gain_hi)], 'boosting AUC': b.AUC.round(3).values, 'boosting gain (95% CI)': [f'{g:+.3f} ({lo:+.3f} … {hi:+.3f})' for g, lo, hi in zip(b.gain_vs_edge_only, b.gain_lo, b.gain_hi)]})
    return t, e
tl, el = blk('LOOK-AHEAD'); tc, ec = blk('causal breakout'); ta, ea = blk('all minutes'); te_, ee = blk('episode', EPI)
# refractory
age = RF[RF.population == 'LOOK-AHEAD breakout minutes: minutes since last reactive pair'].copy(); order = ['no pair yet', '<2 min', '2-5', '5-10', '10-20', '20-40', '40+']; age['o'] = age.bin.map({k: i for i, k in enumerate(order)}); age = age.sort_values('o')[['bin', 'minutes', 'pair_minutes', 'per1000']]; age.columns = ['minutes since the last reactive pair', 'breakout minutes', 'with a pair', 'pairs per 1000 minutes']
fa = pd.DataFrame(R3['fine_age']).T.reset_index(); fa.columns = ['minutes since the last pair', 'breakout minutes', 'with a pair', 'per 1000']; fa['breakout minutes'] = fa['breakout minutes'].astype(int); fa['with a pair'] = fa['with a pair'].astype(int); fa['per 1000'] = fa['per 1000'].round(0)
allage = RF[RF.population == 'all minutes: minutes since last reactive pair'].copy(); allage['o'] = allage.bin.map({k: i for i, k in enumerate(order)}); allage = allage.sort_values('o')[['bin', 'minutes', 'pair_minutes', 'per1000']]; allage.columns = ['minutes since the last reactive pair', 'all minutes', 'with a pair', 'pairs per 1000 minutes']
ss = RF[RF.population.str.contains('last pair on the same side')].copy(); ss['bin'] = ss.bin.map({'0.0': 'opposite side', '1.0': 'same side'}); ss['population'] = ss.population.str.split(':').str[0]; ss = ss[['population', 'bin', 'minutes', 'pair_minutes', 'per1000']]; ss.columns = ['population', 'last pair vs current breakout side', 'minutes', 'with a pair', 'per 1000']
tre = RP_[RP_.feature == 'tgt_eq_last'].copy(); tre['value'] = tre.value.map({0.0: 'target strike differs from the last pair strike', 1.0: 'target strike = last pair strike'}); tre = tre[['value', 'minutes', 'pair_minutes', 'per1000']]; tre.columns = ['look-ahead breakout minutes', 'minutes', 'with a pair', 'per 1000']
tr = TR.copy(); tr['precision'] = tr.precision.map(lambda v: pct(v, 1)); tr['recall'] = tr.recall.map(lambda v: pct(v, 1)); tr = tr[['rule', 'predicted_minutes', 'precision', 'recall']]; tr.columns = ['rule', 'minutes predicted', 'precision', 'recall of the pair minutes']
un = UN[UN.population == 'LOOK-AHEAD breakout minutes'].head(10)[['feature', 'AUC', 'AUC_even', 'AUC_odd']]; un.columns = ['feature (look-ahead breakout minutes)', 'AUC (pairs vs no pair)', 'even cycles', 'odd cycles']
mu = MV[MV.kind.str.startswith('univariate')][['feature', 'AUC', 'AUC_even', 'AUC_odd']].round(3); mu.columns = ['feature (look-ahead breakout minutes)', 'AUC', 'even cycles', 'odd cycles']; mc = MV[MV.kind.str.startswith('LOCO')][['comparison', 'AUC_a', 'AUC_b', 'diff', 'lo', 'hi']].round(3); mc['difference (95% CI)'] = [f'{a:+.3f} ({b:+.3f} … {c:+.3f})' for a, b, c in zip(mc['diff'], mc.lo, mc.hi)]; mc = mc[['comparison', 'AUC_a', 'AUC_b', 'difference (95% CI)']]; mc.columns = ['comparison (leave-one-cycle-out logistic)', 'AUC first', 'AUC second', 'difference (95% CI)']
lg = LG.copy(); lg.columns = ['leg definition', 'legs', 'leg minutes', 'pair minutes in legs', 'legs with a pair', 'legs with 2+ pair minutes', 'null mean legs with a pair', 'null mean legs with 2+', 'P(null <= observed 2+)', 'null 2.5%', 'null 97.5%']
rr = R2['refract_ratio_LA_breakout_lt5_vs_ge5']; rc = R2['refract_ratio_causal_breakout']; ra = R2['refract_ratio_all']
gq = R3['gaps_q']; best_s = R1['dir_hit_N60']
txt = f"""# Algo 8 — reactive pairs: window, indicator and trigger

*Investigation only. In-sample (D-1 of {n_cyc} cycles with reactive pairs, {n_pairs} reactive pairs in {n_pm} pair-minutes inside 10:30–15:15 of {n_min:,} cycle-minutes; not a holdout). Plan written before the tests: `BODY_REACTIVE_TRIGGER_PLAN.md`. Steps added after the first results are labelled **post-hoc**. Numbers are read from `outputs/bl_trg_*` and `bl_summary_trg1…5.json`. Figure: `figures/bl_trg_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Is a Donchian channel the real indicator?** | **Cannot be proved from behaviour, and I did not prove it.** What the data does is rule alternatives out: a range that expands from the open (AUC {R1['expanding_AUC']:.2f} vs {R1['best_rolling_AUC']:.2f}), every moving-average-gap family (0.76–0.88, previous study), and channels shorter than ~40 or longer than ~70 minutes. It cannot separate "position in the trailing N-minute range", "N-minute high/low breakout" and "stochastic %K": they are the same signal in this data. | Observed (alternatives rejected); identity **Not established** |
| **Which window: 60 or another?** | **A rolling window of about 40–70 minutes; 60 has the highest point estimate (AUC {R1['best_rolling_AUC']:.3f}) but 40, 45, 50, 55, 65 and 70 are statistically indistinguishable from it** (paired CIs include 0). Upper-edge and lower-edge events agree (best N {R1['best_upper'][1:]} and {R1['best_lower'][1:]}; both on the plateau). I cannot narrow it further with minute closes. | Observed (plateau); exact N **Not identifiable** |
| **What does the strike do at the edge?** | Among pairs placed beyond the 60-minute band, **{pct(best_s['beyond'], 1)}** sit one step on the broken side of ATM; among pairs not beyond the band {pct(best_s['not_beyond'], 1)} (n = {best_s['n_beyond']} and {best_s['n_not']}). | Observed |
| **What fires a pair?** | **Not cracked.** The range edge is close to *necessary*: **{pct(la_rec)} of pair-minutes have the current minute's close beyond the previous 60 closes** (look-ahead variant; {pct(cau_rec)} with completed bars only). It is far from *sufficient*: only **{pct(la_prec)}** of those minutes (look-ahead; {pct(cau_prec)} completed-bar) contain a pair. | Observed; trigger **Unresolved** |
| **What explains which breakouts fire?** | Only **elapsed time since the previous reactive pair** (within breakout minutes: AUC {UN[(UN.population == 'LOOK-AHEAD breakout minutes') & (UN.feature == 'age_react')].AUC.iloc[0]:.2f}, same in both halves). Breakouts within 20 minutes of the last pair fire at 53–144 per 1000 minutes; after 20 minutes at 281–347. It is **time, not the spot or ATM move** since that pair. Book state, option premium/volume, market speed and clock add nothing measurable. | Observed (predictive); mechanism **Unresolved** |
| **Is there a simple rule?** | **No.** The best leave-one-cycle-out tree has precision {pct(TR.precision.iloc[0])} and recall {pct(TR.recall.iloc[0])}; pre-registered success needed ≥ 50% on both. | Observed |

## 1. Block A — band definition and window (363 pairs vs 10,890 random seconds)
{table(sb)}
* Plateau, not a peak: 40–70 minutes are inside the 95% paired-bootstrap CI of N = 60; ≤ 35 and ≥ 75 minutes are excluded. Excluded windows: {', '.join(R1['excluded_vs_best'])}.
* **Expanding range since the open is rejected** (AUC {R1['expanding_AUC']:.3f}, difference to N = 60 {R1['expanding_diff_lo_hi'][0]:+.2f} … {R1['expanding_diff_lo_hi'][1]:+.2f}): the band is a *rolling* range, not the day high/low.
* **No crossing signature in the margin**: events beyond the band sit a median {S.median_margin_events_steps[S.window == 'N60'].iloc[0]:.3f} strike-steps beyond it, random seconds beyond the band {S.median_margin_controls_steps[S.window == 'N60'].iloc[0]:.3f}; ≥ 98% of both are within half a step. With minute closes only I cannot see the exact crossing second, so the boundary cannot be located more precisely.

## 2. Block C/D — what separates firing from non-firing breakouts
Populations (all features completed-bar/causal at the minute start; the look-ahead population is defined by the current minute's close and is flagged):
* **{int(bk.sum())} causal breakout minutes** (completed bar closed beyond its previous 60 closes), {int((bk & (P.y == 1)).sum())} with a pair;
* **{int(la.sum())} look-ahead breakout minutes**, {int((la & (P.y == 1)).sum())} with a pair.

**Look-ahead breakout minutes** — AUC gain of each block over the edge-only model (edge-only AUC logistic {el.AUC.iloc[0]:.3f}, boosting {el.AUC.iloc[1]:.3f}):

{table(tl)}
**Causal breakout minutes** (edge-only AUC {ec.AUC.iloc[0]:.3f} / {ec.AUC.iloc[1]:.3f}):

{table(tc)}
**Episode starts** (causal breakout, pair within 3 minutes; {R2['episodes']['n']} episodes, {R2['episodes']['pos']} with a pair; edge-only AUC {ee.AUC.iloc[0]:.3f} / {ee.AUC.iloc[1]:.3f}):

{table(te_)}
**All cycle-minutes** (edge-only AUC {ea.AUC.iloc[0]:.3f} / {ea.AUC.iloc[1]:.3f}; the edge features already carry most of it):

{table(ta)}
* Rule used: a block "explains non-firing" if it adds ≥ 0.03 AUC with a CI excluding 0 in both halves. **Only the order-activity block does** (look-ahead minutes: +0.09 logistic and +0.09 boosting with CIs excluding 0; causal minutes and episodes: +0.05 to +0.11, CIs sometimes include 0). **Clock, book state, option state and market-speed blocks do not** (one small exception: option premium/volume adds +0.012, CI 0.005–0.019, in the all-minutes boosting model, below the 0.03 threshold and absent inside breakout minutes).
* Even the full model reaches only AUC 0.65–0.73 inside breakout minutes: most of the non-firing is unexplained.

## 3. Block E — what inside order activity matters: time since the last pair (**post-hoc drill-down**)
Single features, look-ahead breakout minutes:

{table(un)}
{table(age)}
Finer bins:

{table(fa)}
* The relationship is a **ramp, not a cool-down threshold** (no clean step at any age). Overall (not conditional on a breakout) the pair rate does **not** depend on time since the last pair (ratio {ra[0]:.2f}, CI {ra[1]:.2f}–{ra[2]:.2f}):

{table(allage)}
* **Within breakout minutes** the rate within 5 minutes of the last pair is {rr[0]:.2f}× the rate later (CI {rr[1]:.2f}–{rr[2]:.2f}; causal breakouts {rc[0]:.2f}×, CI {rc[1]:.2f}–{rc[2]:.2f}).
* Side matters too (same side as the last pair is suppressed about 2×), and so does repeating the same strike:

{table(ss)}
{table(tre)}
* **Time or move?** (post-hoc):

{table(mu)}
{table(mc)}
  Adding the spot move or ATM move since the last pair to elapsed time does not help (difference −0.015, CI includes 0); the move alone has no signal. The pacing is **by time**.
* **One pair per leg?** (post-hoc). A leg = consecutive minutes beyond the band on the same side; the null places each cycle's pair-minutes at random among its leg minutes (2,000 draws):

{table(lg)}
  Legs with two or more pair-minutes are fewer than chance (look-ahead legs: {int(LG.legs_with_2plus_pair_minutes.iloc[0])} vs {LG.null_mean_legs_with_2plus.iloc[0]:.1f}, one-sided p = {LG.null_2plus_p_lower.iloc[0]:.3f}), a modest spacing, not a one-per-leg rule: {int(LG.legs_with_a_pair.iloc[0])} of {int(LG.legs.iloc[0])} look-ahead legs have a pair.
* Gaps between consecutive reactive pairs: median {gq['0.5'] / 60:.0f} min, 25th percentile {gq['0.25'] / 60:.1f} min, 10th percentile {gq['0.1']:.0f} s; {pct(R3['share_gap_lt_60s'], 1)} are under 60 s (bursts of pairs placed together exist); {pct(R3['share_repeat_prev_reactive_strike'])} of pairs repeat the previous reactive strike.

## 4. Block F — simplest rule
{table(tr)}
* No rule reaches 50% precision and 50% recall. The look-ahead breakout alone recalls {pct(la_rec)} of pair-minutes but with {pct(la_prec)} precision; learning from all causal features lifts precision to {pct(TR.precision.iloc[0])} but cuts recall to {pct(TR.recall.iloc[0])}.

## 5. What this means
* **Where / when (supported):** a reactive pair is a **range-edge event**: roughly when the live spot has just pushed beyond its trailing ~hour range, on that side (strike one step toward it); this happens mostly inside the minute, so completed-bar data see only {pct(cau_rec)} of them.
* **Which edge events fire (partly supported):** more likely the longer since the previous reactive pair (a time-based ramp), less likely when the previous pair was on the same side/strike. Whether this is a cool-down timer, a rate limit, a per-leg budget, or something else is **not identifiable** here.
* **Unexplained:** about {pct(1 - la_prec)} of look-ahead breakout minutes have no pair and the best model explains little of it. The missing variable may be one the data do not contain: the true intraday high/low, ticks or a second-level crossing time, bid/ask, quantity budget/margin state, or a stochastic element.

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| The band is a rolling range of about 40–70 minutes (60 best point estimate), not an expanding range or an MA-gap | **Observed** | AUC plateau with paired CIs; expanding {R1['expanding_AUC']:.2f} |
| Strike direction follows the broken side ({pct(best_s['beyond'], 1)} beyond the band) | **Observed** | 236 pairs beyond the band |
| Algo 8 is a Donchian channel / any named indicator | **Not established** | equivalent formulations are indistinguishable |
| The exact window (60 vs 40–70) | **Not identifiable** | plateau; minute closes only |
| An edge pair is more likely the longer since the previous reactive pair | **Observed (predictive)** | AUC {UN[(UN.population == 'LOOK-AHEAD breakout minutes') & (UN.feature == 'age_react')].AUC.iloc[0]:.2f}, both halves; ratio {rr[0]:.2f}× (CI {rr[1]:.2f}–{rr[2]:.2f}); post-hoc drill-down |
| The pacing is by elapsed time, not by the spot/ATM move since the last pair | **Observed (predictive)** | post-hoc; time + move vs time only CI includes 0 |
| Book state, option premium/volume, market speed, clock explain non-firing | **Not supported** | gains ≤ +0.03, CIs include 0 |
| What exactly fires each pair | **Unresolved** | no rule with precision and recall ≥ 50%; ~{pct(1 - la_prec)} of look-ahead breakout minutes unexplained |
| Intra-minute crossing time, calculation frequency | **Not testable** | minute data only |

## 7. Limits and how this could be wrong
* **Post-hoc steps:** the time-since-last-pair drill-down, time-vs-move and per-leg tests were added after the pre-registered block C showed activity as the only useful block; they are labelled, replicate in both cycle halves, but are not multiplicity-corrected. Many candidate features (≈ 30) and windows (19) were examined.
* **Look-ahead variant:** it defines the population by the current minute's close; it shows how much of the gap is intra-minute, it is not a causal rule.
* **Closes only:** no spot high/low. The true channel may use highs/lows, which could change which windows fit.
* **Pair minutes, not seconds:** the minute panel cannot see the crossing second; 9 pairs outside 10:30–15:15 and cycles without reactive pairs are excluded; some minutes contain several pairs (counted once).
* In-sample; D-1 only; {n_pm} pair-minutes; predictive not causal; no source code.

## 8. Files
`src/bl_trg_band.py` (block A, B) → `bl_trg_panel.py` (minute panel) → `bl_trg_tests.py` (blocks C–F) → `bl_trg_drill.py` → `bl_trg_move.py` → `bl_trg_leg.py` → `bl_trg_fig.py` → `make_trg_report.py`. Outputs `outputs/bl_trg_*`, `bl_summary_trg1…5.json`. Tests `tests/test_bl.py` (`test_trg_*`).
"""
open(f'{RP}/BODY_REACTIVE_TRIGGER.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
