"""Builds reports/BODY_REACTIVE_LOOKBACK.md from computed outputs (bl_lb_*, bl_summary_lb*.json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); L1, L2, L3 = J('lb'), J('lb2'), J('lb3')
pct = lambda x, n=1: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
SM = pd.read_csv(f'{OUT}/bl_lb_sample.csv'); DF = pd.read_csv(f'{OUT}/bl_lb_defs.csv'); MG = pd.read_csv(f'{OUT}/bl_lb_magnitude.csv'); SE = pd.read_csv(f'{OUT}/bl_lb_live.csv'); HZ = pd.read_csv(f'{OUT}/bl_lb_hazard.csv'); LS = pd.read_csv(f'{OUT}/bl_lb_live_scan.csv'); SC = pd.read_csv(f'{OUT}/bl_lb_scan.csv')
od = L1['offset_dist']; ol = L3['live_offset_dist']; sc = L1['scan_hit_at']; ls = LS.set_index('L_min').hit_rate_live_proxy
sm = SM.copy(); sm['match'] = sm.match.map({True: 'yes', False: 'no'}); sm.columns = ['D-1 date', 'underlying', 'order time', 'previous-minute ATM', 'spot 15 min earlier', 'spot now (prev-minute close)', '15-min move (points)', 'predicted strike', 'actual strike', 'match']
df = DF.copy(); df['hit_rate'] = df.hit_rate.map(lambda v: pct(v)); 
for c in ('minute_0_4', 'minute_5_9', 'minute_10_14'): df[c] = df[c].map(lambda v: pct(v, 0))
df['95% CI'] = [f'{a * 100:.0f}–{b * 100:.0f}%' for a, b in zip(DF.ci_lo, DF.ci_hi)]; df = df[['direction definition', 'n', 'hit_rate', '95% CI', 'minute_0_4', 'minute_5_9', 'minute_10_14']]; df.columns = ['direction definition', 'n', 'hit rate', '95% CI', 'minutes 0–4 of the block', '5–9', '10–14']
mg = MG.copy(); mg['mb'] = ['|move| < 0.001 step', '0 – 0.1 step', '0.1 – 0.25', '0.25 – 0.5', '0.5 – 1', '1 – 2', '> 2'][:len(mg)] if len(mg) == 7 else mg.mb; mg['hit'] = mg.hit.map(lambda v: pct(v)); mg['mean_offset_in_direction'] = mg.mean_offset_in_direction.round(2); mg.columns = ['|15-min move| in strike steps', 'pairs', 'hit rate', 'mean strike offset in the move direction (steps)']
se = SE.copy(); se['sb'] = ['0–9', '10–19', '20–29', '30–39', '40–49', '50–59']; se = se[['sb', 'n', 'hit_bar', 'hit_live_proxy']]; se['hit_bar'] = se.hit_bar.map(lambda v: pct(v, 0)); se['hit_live_proxy'] = se.hit_live_proxy.map(lambda v: pct(v, 0)); se.columns = ['second of the minute', 'pairs', 'rule on the last completed minute close', 'rule on the live-spot proxy']
scan = pd.DataFrame({'look-back L (min)': [3, 5, 10, 15, 20, 30, 45, 60, 90], 'last completed close': [pct(sc[str(L)]) if str(L) in sc else pct(SC.set_index('L_min').hit_rate.loc[L]) for L in (3, 5, 10, 15, 20, 30, 45, 60, 90)], 'live-spot proxy': [pct(ls.loc[L]) for L in (3, 5, 10, 15, 20, 30, 45, 60, 90)]})
hz = HZ[HZ.kind == 'signed 15-min move'][['group', 'size', 'sum', 'per1000']]; hz.columns = ['15-min move before the minute', 'cycle-minutes', 'reactive-pair minutes', 'per 1000']
dd = L1['defs']; best_anch = max(h for d, h in zip(dd['direction definition'], dd['hit_rate']) if not d.startswith('rolling'))
txt = f"""# Algo 8 — is "ATM + 1 step toward the 15-minute move" correct, and how is the look-back taken?

*Investigation only. In-sample, observational (D-1, {L1['n']} reactive pairs with a complete 15-minute look-back). Plan written before the tests: `BODY_REACTIVE_LOOKBACK_PLAN.md`. Numbers are read from `outputs/bl_lb_*` and `bl_summary_lb*.json`. Figure: `figures/bl_lb_logic.png`.*

## 0. Verdict on your explanation

| Your statement | Verdict | Evidence |
|---|---|---|
| Direction = spot now vs spot 15 minutes earlier (up / down / ~unchanged) | **Correct in substance, with two refinements:** (a) "spot now" is best read as the **live spot at the order second** (rule on the last completed minute close {pct(L1['hit15'])}; on a live-spot proxy **{pct(L2['live_hit'])}**); (b) **15 minutes is not special** — any look-back from 10 to 60 minutes fits equally (§3). | Observed |
| Strike = previous-minute ATM + 1 strike interval toward the move (24,100 → 24,150 up / 24,050 down) | **Correct for {pct(L1['hit15'], 0)} of pairs on the stated rule** ({pct(L1['hit15_und']['NIFTY'], 0)} NIFTY, {pct(L1['hit15_und']['SENSEX'], 0)} SENSEX); **{pct(L2['live_hit'], 0)}** with the live-spot proxy. The rest: +2 steps ({pct(od['2.0'], 0)}; {pct(ol['2.0'], 0)} live), the ATM itself ({pct(od['0.0'], 0)}), the opposite side ({pct(od['-1.0'] + od['-2.0'], 0)}). Your worked example holds in {L1['sample_matches']} of 10 pre-selected pairs (§1). | Observed |
| The 15-minute move decides WHERE, not WHETHER, a pair is sold | **Mostly correct.** The pair rate is **{L2['hazard_ratio_moving_vs_flat'][0]:.1f}×** higher when the 15-minute move is non-flat (CI {L2['hazard_ratio_moving_vs_flat'][1]:.1f}–{L2['hazard_ratio_moving_vs_flat'][2]:.1f}), but it does **not** depend on the direction (up {L2['hazard_up_down'][0]:.0f} vs down {L2['hazard_up_down'][1]:.0f} per 1000) or on the size of the move, and flat markets still produce pairs ({HZ[HZ.group == 'flat (< 0.02%)'].per1000.iloc[0]:.1f} per 1000). So the move is **not** what fires a pair. | Observed |
| "We have not established that it checks every minute from open" | **Correct, and it stays that way.** The strike is consistent with a **rolling** window that ends at the order moment — not anchored to a 15-minute grid, the previous block, the open, or the last sell — but minute data cannot tell whether the algorithm computes it every minute or only when it places a pair; both give identical strikes (§3). | Observed (rolling); frequency **not testable** |

## 1. The stated rule and your worked example
Rule: strike = nearest strike to the previous-minute close + step × sign(close[j−1] − close[j−16]); step 50 NIFTY / 100 SENSEX.
* Hit rate **{pct(L1['hit15'])}** ({pct(L1['hit15_half']['True'])} first half, {pct(L1['hit15_half']['False'])} second half). (The earlier report's 79.1% used {368} pairs including 5 before 09:35 whose look-back is clipped at the open; this study uses {L1['n']}.)
* Offset of the sold strike from the ATM, in the move direction: {', '.join(f'{k.replace(".0", "")}: {pct(v)}' for k, v in od.items())}. No 15-minute move was exactly zero.
* **Ten pre-selected pairs** (the first reactive pair of the first ten D-1 cycles by date), written out like your example:
{table(sm)}
* The two misses are informative: **2026-07-06** has a 15-minute move of −0.1 point (effectively flat, so the sign is arbitrary) and **2026-07-08** is a +2-step case.

## 2. Direction means a rolling trend, not a 15-minute block
Hit rate of the rule with different direction definitions (all causal; "rolling L" = close[j−1] vs close[j−1−L]):
{table(df)}
* **Anchored definitions fail:** the previous completed 15-minute block gives {pct(DF.set_index('direction definition').loc['previous 15-min block (open to close)', 'hit_rate'], 0)} overall and **{pct(L1['disagree_block_hit'])}** where it disagrees with the rolling direction ({L1['disagree_n']} pairs; the rolling direction is right in {pct(L1['disagree_rolling_hit'], 0)} of them). "Current block so far" is only {pct(DF.set_index('direction definition').loc['current block so far', 'minute_0_4'], 0)} in the first five minutes of a block (little history) and reaches ~79% later — a window that restarts at block boundaries would behave like that; a rolling one does not. Since-open, since-last-sell and latest-extreme are worse; the best anchored one (since the previous timetable wave, {pct(best_anch, 0)}) is still below every rolling window.
* **The rolling windows are indistinguishable from each other** (10, 15, 20, 30, 60 minutes: {pct(DF.set_index('direction definition').loc['rolling 60', 'hit_rate'], 0)}–{pct(DF.hit_rate.max(), 0)}).

## 3. Is 15 minutes special? Is it computed every minute?
Hit rate of the rule for look-back L:
{table(scan)}
* **No.** The curve is a broad plateau from 10 to 60 minutes (about 80% on the last completed close, about 90% on the live-spot proxy); on the live proxy L = 15 is at most {max(-LS.set_index('L_min').diff_vs_L15_lo.loc[[10, 12, 14, 16, 18, 20, 25, 30, 40, 45, 60]].min(), 0) * 100:.1f} points better than any L in 10…60 and the paired cluster-bootstrap CIs reach 0; on the last-completed-close version L = {int(SC.sort_values('hit_rate').L_min.iloc[-1])} is the highest ({pct(SC.hit_rate.max())} vs {pct(sc['15'])} at L = 15). L ≤ 7 and L = 90 are worse. **The data say "recent trend over roughly 10–60 minutes", not "15 minutes".** The 15 in your example (and in my earlier wording) is a convenient choice, not an identified parameter.
* **Constant every-minute look-back?** What I can test is what information the strike is consistent with. It is consistent with the spot at the order second and the spot L minutes before **that second** — a window that *ends when the order is placed*. It is not consistent with a direction frozen at a clock time (previous block, open, extreme, last sell). Whether Algo 8 recomputes that comparison every minute (or every second) and a pair fires on some other condition, or computes it only when a pair is placed, **cannot be separated**: both produce the same strike. The firing times themselves are spread uniformly over the seconds of the minute (earlier study), so the firing is not tied to a bar close.

## 4. Live spot, not the last completed bar
Hit rate by the second of the minute at which the order is placed (rule on the last completed minute close vs on a live-spot proxy = linear interpolation between the previous and the current minute close at that second):
{table(se)}
* The rule on the last completed close **falls late in the minute** (Spearman with the second: {L2['bar_vs_sec_rho']:.2f}; {pct(L2['late_bar'], 0)} for seconds ≥ 40, n = {L2['late_n']}) as the live spot drifts away from it; the live proxy is flat ({L2['live_vs_sec_rho']:.2f}) and {pct(L2['late_live'], 0)} late in the minute. Overall {pct(L2['bar_hit'], 0)} → {pct(L2['live_hit'], 0)} (difference CI {L2['live_minus_bar_ci'][0] * 100:+.0f} to {L2['live_minus_bar_ci'][1] * 100:+.0f} points). **Inference:** the strike is chosen from the live spot at the moment of the order. *Caveat:* the proxy uses the current minute's close (not available at decision time) and a straight-line path; it is a diagnostic of what the decision-time spot looked like, not a causal rule.

## 5. Size of the move and ties
{table(mg)}
* The sign decides the side; the **size does not**: moves from 0.1 to 2 steps all give about +1 step and 79–84% hits. For essentially flat moves (< 0.1 step, n = {int(MG.n.iloc[0])}) the side is a coin flip-ish ({pct(MG.hit.iloc[0], 0)} hits) — the case of the 2026-07-06 example. There is no visible dead-band: tiny moves still shift the strike by one step.

## 6. The move and the trigger (your distinction) — hazard of a reactive pair, 10:30–15:15
{table(hz)}
* Pairs are **{L2['hazard_ratio_moving_vs_flat'][0]:.1f}×** more likely in a moving than in a flat 15-minute window (the flat group is {pct(L2['flat_share_of_minutes'], 0)} of minutes), but direction and size beyond that do not matter, and a direction flip in the last 5 minutes does not raise the rate ({HZ[(HZ.kind != 'signed 15-min move') & (HZ.group.astype(str) == 'True')].per1000.iloc[0]:.0f} vs {HZ[(HZ.kind != 'signed 15-min move') & (HZ.group.astype(str) == 'False')].per1000.iloc[0]:.0f} per 1000). Together with the weak predictive tilt found earlier this supports your distinction: **direction → strike; the cause of firing remains unknown.**

## 7. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Strike = ATM + 1 step toward the recent move: {pct(L1['hit15'], 0)} (bar) / {pct(L2['live_hit'], 0)} (live proxy) | **Observed** | {L1['n']} pairs, halves, underlyings |
| Look-back length 10–60 minutes fits equally; 15 not special | **Observed** | scan with paired bootstrap |
| Direction is a rolling window ending at the order moment, not anchored to a block / open / event | **Observed** | {pct(L1['disagree_block_hit'])} vs {pct(L1['disagree_rolling_hit'], 0)} on {L1['disagree_n']} disagreements |
| The decision-time spot is the live spot at the order second | **Inferred** | live proxy vs completed bar, by second |
| Whether Algo 8 recomputes the direction every minute | **Not testable** | same strike either way |
| The move itself fires the pair | **Not supported** | rate ×{L2['hazard_ratio_moving_vs_flat'][0]:.1f} moving vs flat, none with direction or size |
| What fires a pair | **Unresolved** | earlier studies |

## 8. Limits and how this could be wrong
* **Live-spot proxy** is an interpolation using the current minute's close; if the true intraminute path is far from a straight line the true hit rate could differ. The qualitative result (the bar-based rule degrades late in the minute, the proxy does not) is robust to that.
* **Look-back identification** is limited by 363 pairs and by strongly overlapping windows; "10–60 minutes" is a plateau of statistically equal rules, not a measured parameter.
* **Reactive-pair labels** use the ±3 s pairing and the timetable cells; mislabelled pairs would lower hit rates.
* **Frequency of evaluation** is not testable with these data; sub-second fills or logs would be needed.
* In-sample; D-1 only; no source code.

## 9. Files
`src/bl_lb_tests.py` (rule, definitions, scan, magnitude, seconds, hazard) → `bl_lb_tests2.py` (live proxy, hazard ratio) → `bl_lb_tests3.py` (live scan) → `bl_lb_fig.py` → `make_lb_report.py`. Outputs `outputs/bl_lb_*`, `bl_summary_lb*.json`. Tests `tests/test_bl.py` (`test_lb_*`).
"""
open(f'{RP}/BODY_REACTIVE_LOOKBACK.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
