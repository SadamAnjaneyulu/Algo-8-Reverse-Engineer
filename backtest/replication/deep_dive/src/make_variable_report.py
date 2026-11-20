"""Render reports/BODY_SOLO_VARIABLE_SEARCH.md from the bl_var_* / bl_shape_* / bl_breakout_* / bl_final_models / bl_tilt_* outputs."""
import sys; sys.path.insert(0, '.')
from bl_common import *
rd = lambda f, **k: pd.read_csv(f'{OUT}/{f}', **k); pct = lambda x, d=1: f'{100 * float(x):.{d}f} %'
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
FM = rd('bl_final_models.csv'); BS = rd('bl_breakout_scan.csv'); HV = rd('bl_breakout_halves.csv'); INC = rd('bl_var_incremental.csv'); UNI = rd('bl_var_univariate.csv'); IMP = rd('bl_var_gb_importance.csv'); SH = rd('bl_shape_results.csv'); TL = rd('bl_tilt_results.csv'); F = rd('bl_breakout_panel.csv'); F = F[F.tslot != 0]
fm = lambda d, m, k: FM[(FM.day == d) & (FM.model.str.startswith(m)) & (FM.kind == k)].AUC.iloc[0]
q1 = F[F.day == 'D-1']; q0 = F[F.day == 'D0']
def rate(Q, f): on = Q[f] == 1; return Q[on].ep.mean() * 1000, Q[~on].ep.mean() * 1000
bs = BS.set_index(['day', 'feature']); sh = SH.set_index(['day', 'feature']); inc = INC.set_index(['day', 'feature']); uni = UNI.set_index(['day', 'feature'])
step = q1.groupby(pd.cut(q1.pos15, [0, .2, .4, .6, .8, .95, 1.0])).ep.mean() * 1000
L = []; w = L.append
w('# Search for the variable behind solo (single-leg) sells\n')
w(f"*In-sample, observational; plan `BODY_SOLO_VARIABLE_SEARCH_PLAN.md` written before fitting. Episode starts: {int(q1.ep.sum())} on D-1 (32 cycles), {int(q0.ep.sum())} on D0 (25 cycles with episodes) in non-slot minutes (slot minutes dropped: they only enter the panel when a solo sale happens, a design leak I found and removed). All numbers are leave-one-cycle-out (LOCO) out-of-sample AUCs unless stated. The breakout variable below was found **after** seeing flexible-model importances (exploratory); it is checked with a permutation null, both rights, both indices and chronological halves, but it is not a holdout test.*\n")
w('## 1. Answer\n')
w(f"""**There is no single hidden variable, but one important missing ingredient was found: a *fresh favourable extreme* (breakout).** On D-1, a solo CE sale is far more likely in the minute after the spot's last close is the **lowest close of the last N minutes**, and a solo PE sale after a **highest** close, N from 5 to 60 minutes (strongest AUC gain for 5–30).

| D-1, LOCO AUC | logistic | gradient boosting |
|---|---|---|
| baseline: 30-min favourable move + own-leg and other-leg book price ratios | {fm('D-1', '1 ', 'lr'):.3f} | {fm('D-1', '1 ', 'gb'):.3f} |
| + multi-horizon spot moves (5/15/60 min) | {fm('D-1', '2 ', 'lr'):.3f} | {fm('D-1', '2 ', 'gb'):.3f} |
| **+ breakout variables** (new 5–60-minute extreme, position in the 15-min range) | **{fm('D-1', '3 ', 'lr'):.3f}** | **{fm('D-1', '3 ', 'gb'):.3f}** |
| + Greeks (net delta, gamma, vega) | {fm('D-1', '5 ', 'lr'):.3f} | {fm('D-1', '5 ', 'gb'):.3f} |
| + volatility proxies (ATM IV, its changes, straddle %; no VIX series in the repo) | {fm('D-1', '6 ', 'lr'):.3f} | {fm('D-1', '6 ', 'gb'):.3f} |
| + inventory (shorts / wings per right, share, distance to book) | {fm('D-1', '7 ', 'lr'):.3f} | {fm('D-1', '7 ', 'gb'):.3f} |
| + activity history (time since last sale, recent solo lots) | {fm('D-1', '8 ', 'lr'):.3f} | {fm('D-1', '8 ', 'gb'):.3f} |
| all market variables (spot + breakout + Greeks + vol + inventory) | {fm('D-1', '9 ', 'lr'):.3f} | {fm('D-1', '9 ', 'gb'):.3f} |
| everything incl. activity and clock | {fm('D-1', '10 ', 'lr'):.3f} | {fm('D-1', '10 ', 'gb'):.3f} |

Even the richest model leaves much unexplained (AUC 0.86–0.90, and only a few percent of minutes with a breakout carry a solo sale — §3), so the mechanism is **multi-variable and not fully identified**, as you suspected.
""")
w('![summary](figures/bl_breakout_summary.png)\n')
w('## 2. What was tested and how each candidate fared (D-1)\n')
cand = [('spot move over 30 min, own-leg book ratio, other-leg book ratio', 'baseline', f"AUC {uni.loc[('D-1', 'fav30')].AUC:.2f} / {uni.loc[('D-1', 'own_ratio')].AUC:.2f} / {uni.loc[('D-1', 'other_ratio')].AUC:.2f}", 'Supported (previous test)'),
        ('fresh favourable extreme over 15 minutes (bk15)', 'breakout', f"rate {bs.loc[('D-1', 'bk15')].rate_on:.0f} vs {bs.loc[('D-1', 'bk15')].rate_off:.0f} per 1,000 min; AUC gain over baseline {bs.loc[('D-1', 'bk15')].AUC_gain_over_baseline:+.3f} ({bs.loc[('D-1', 'bk15')].lo:+.3f}..{bs.loc[('D-1', 'bk15')].hi:+.3f})", '**Supported, strongest addition**'),
        ('same over 5 / 30 / 60 minutes', 'breakout', f"gain {bs.loc[('D-1', 'bk5')].AUC_gain_over_baseline:+.3f} / {bs.loc[('D-1', 'bk30')].AUC_gain_over_baseline:+.3f} / {bs.loc[('D-1', 'bk60')].AUC_gain_over_baseline:+.3f}; 90 min +{bs.loc[('D-1', 'bk90')].AUC_gain_over_baseline:.3f}, day extreme {bs.loc[('D-1', 'bk_day')].AUC_gain_over_baseline:+.3f}", 'Supported for 5–60 min; no sharp N'),
        ('net delta of the whole book (delta to neutralise)', 'Greeks', f"alone AUC {uni.loc[('D-1', 'delta_need')].AUC:.2f}; gain over baseline {inc.loc[('D-1', 'delta_need')].AUC_gain:+.3f} ({inc.loc[('D-1', 'delta_need')].lo:+.3f}..{inc.loc[('D-1', 'delta_need')].hi:+.3f}); GB-model gain +{fm('D-1', '5 ', 'gb') - fm('D-1', '1 ', 'gb'):.3f}", '**Not a trigger** (alone ≈ chance); small add-on'),
        ('volatility proxies (ATM IV level, 15/30-min change, straddle % of spot)', 'vol', f"all-vol gain {inc.loc[('D-1', '[ALL vol]')].AUC_gain:+.3f} ({inc.loc[('D-1', '[ALL vol]')].lo:+.3f}..{inc.loc[('D-1', '[ALL vol]')].hi:+.3f}); GB importance of atm_iv {IMP[(IMP.day == 'D-1') & (IMP.feature == 'atm_iv')].auc_drop.iloc[0]:+.4f}", 'Not supported (no VIX series available)'),
        ('CE/PE tilt of the book vs the cumulative move', 'inventory', f"tilt tracks the day's move (Spearman 0.85) but tilt-gap alone AUC {TL[(TL.day == 'D-1') & (TL.item == 'fav_open') & (TL.metric == 'tilt gap alone AUC')].value.iloc[0]:.2f}; gain {TL[(TL.day == 'D-1') & (TL.item == 'fav_open') & (TL.metric.str.contains('gain'))].value.iloc[0]:+.3f} (CI includes 0)", 'Tilt is an outcome, not a trigger'),
        ('distance of spot from the last paired (clock) strike', 'position', f"AUC {sh.loc[('D-1', 'dev_pair')].univariate_AUC:.2f}; gain {sh.loc[('D-1', 'dev_pair')].AUC_gain:+.3f}", 'Rejected'),
        ('inventory levels (shorts / wings per right)', 'position', f"best single gain {INC[(INC.day == 'D-1') & (INC.family == 'position')].AUC_gain.max():+.3f}, below the breakout variables; mechanism unclear", 'Weak / unclear'),
        ('combined book P&L (% of ₹2 Cr)', 'pnl', f"AUC {uni.loc[('D-1', 'mtm_tot')].AUC:.2f}", 'Rejected'),
        ('time of day', 'clock', f"episode-start rate per 1,000 minutes by hour: {', '.join(f'{int(h)}h {r:.0f}' for h, r in (pd.read_csv(f'{OUT}/bl_shape_hour_D-1.csv').assign(r=lambda d: d['sum'] / d['size'] * 1000).set_index('hour').r.items()))}", 'Mild (end-of-day bursts)')]
w(table(pd.DataFrame(cand, columns=['Candidate', 'Family', 'Result', 'Verdict'])).replace('last hour rate see §4', 'higher rate in the last hour (end-of-day bursts)')); w('')
w('## 3. The breakout effect in detail (D-1)\n')
w(f"""* **Rate when the previous close is the most favourable close of the last N minutes** (per 1,000 minutes, on vs off): {', '.join(f"N={n}: {bs.loc[('D-1', f'bk{n}')].rate_on:.0f} vs {bs.loc[('D-1', f'bk{n}')].rate_off:.0f}" for n in (5, 10, 15, 30, 60))}.
* **A step, not a slope:** the rate by the position of the previous close within the last 15 closes is {', '.join(f'{v:.1f}' for v in step.values)} (bins 0–.2, .2–.4, .4–.6, .6–.8, .8–.95, .95–1): it jumps only at the extreme itself.
* **Timing:** the start rate is {q1[q1.since_bk15 == 0].ep.mean() * 1000:.0f} per 1,000 minutes in the minute right after a 15-minute extreme and {q1[q1.since_bk15 == 1].ep.mean() * 1000:.0f} one minute later — the reaction is immediate.
* **Not just the baseline in disguise:** at any 30-minute move the extreme multiplies the rate ({', '.join(f"{lab}: {q1[(q1.fb if 'fb' in q1 else pd.cut(q1.fav30, [-100, 0, .1, 100], labels=['<=0', '0-.1', '>.1'])) == lab].pipe(lambda d: d[d.bk15 == 1].ep.mean() * 1000):.0f} vs {q1[(pd.cut(q1.fav30, [-100, 0, .1, 100], labels=['<=0', '0-.1', '>.1'])) == lab].pipe(lambda d: d[d.bk15 == 0].ep.mean() * 1000):.0f}" for lab in ('<=0', '0-.1', '>.1'))} for fav30 ≤ 0 / 0–0.1 % / > 0.1 %).
* **Recall and strength:** {', '.join(f"bk{n} flags {pct(q1[f'bk{n}'].mean(), 0)} of minutes and holds {pct((q1[f'bk{n}'] * q1.ep).sum() / q1.ep.sum(), 0)} of episode starts" for n in (5, 15, 30, 60))}; yet only {pct(q1[q1.bk15 == 1].solo.mean())} of 15-minute-breakout minutes (and {pct(q1[q1.bk60 == 1].solo.mean())} of 60-minute-breakout minutes) contain a solo sale, versus {pct(q1[q1.bk15 == 0].solo.mean())} otherwise.
* **Robustness:** calls (new lows) rate {rate(q1[q1.cp == 'CE'], 'bk15')[0]:.0f} vs {rate(q1[q1.cp == 'CE'], 'bk15')[1]:.0f}; puts (new highs) {rate(q1[q1.cp == 'PE'], 'bk15')[0]:.0f} vs {rate(q1[q1.cp == 'PE'], 'bk15')[1]:.0f}; NIFTY {rate(q1[q1.und == 'NIFTY'], 'bk15')[0]:.0f} vs {rate(q1[q1.und == 'NIFTY'], 'bk15')[1]:.0f}; SENSEX {rate(q1[q1.und == 'SENSEX'], 'bk15')[0]:.0f} vs {rate(q1[q1.und == 'SENSEX'], 'bk15')[1]:.0f}.
* **Chronological halves (D-1):** first half bk15 {HV[(HV.day == 'D-1') & (HV.feature == 'bk15')].iloc[0].rate_on:.0f} vs {HV[(HV.day == 'D-1') & (HV.feature == 'bk15')].iloc[0].rate_off:.0f}, second half {HV[(HV.day == 'D-1') & (HV.feature == 'bk15')].iloc[1].rate_on:.0f} vs {HV[(HV.day == 'D-1') & (HV.feature == 'bk15')].iloc[1].rate_off:.0f}.
* **Range size:** within 15-minute-breakout minutes the rate by the 15-minute range (%) is {', '.join(f'{k}: {v:.0f}' for k, v in (q1[q1.bk15 == 1].groupby(pd.cut(q1[q1.bk15 == 1].range15, [0, .05, .1, .15, .25, 5])).ep.mean() * 1000).items())} per 1,000 minutes: a break out of a larger range counts more, but the largest-range bin is small and not monotone.
""")
w('## 4. D0\n')
w(f"""The same variable is weak on D0 overall (bk15: rate {bs.loc[('D0', 'bk15')].rate_on:.0f} vs {bs.loc[('D0', 'bk15')].rate_off:.0f}; gain {bs.loc[('D0', 'bk15')].AUC_gain_over_baseline:+.3f}). The D0 models are driven by activity history ('time since the last sale on the right': AUC {fm('D0', '8 ', 'gb'):.2f} with activity vs {fm('D0', '1 ', 'gb'):.2f} baseline), i.e. D0 solo selling is a continuous, self-sustaining process rather than a market-triggered one. In the second chronological half (D0 from 2026-08-13) the breakout effect is much stronger (bk15 {HV[(HV.day == 'D0') & (HV.feature == 'bk15')].iloc[1].rate_on:.0f} vs {HV[(HV.day == 'D0') & (HV.feature == 'bk15')].iloc[1].rate_off:.0f}) than in the first ({HV[(HV.day == 'D0') & (HV.feature == 'bk15')].iloc[0].rate_on:.0f} vs {HV[(HV.day == 'D0') & (HV.feature == 'bk15')].iloc[0].rate_off:.0f}) — a regime change around the same weeks as the 15:14-flatten break (**Inferred / not tested**).
""")
w('## 5. Conclusion and what remains\n')
w(f"""* **Best-supported description (Inferred):** on D-1 the algorithm adds a single leg (call into a falling market, put into a rising one) when the previous close is a **fresh extreme in the favourable direction**, while the own-leg book is in profit and the other leg is losing. The sale is a 1-lot add; repeated new extremes give the 'drip'.
* **Not supported as drivers:** net delta (alone), implied-vol/VIX-like proxies, ₹ P&L of the whole book, CE/PE tilt gap, distance from the last straddle strike, inventory level.
* **Unresolved:** the exact lookback N (5–60 min all work; no sharp optimum); what else gates the sale (only {pct(q1[q1.bk15 == 1].solo.mean(), 0)} of 15-minute-breakout minutes carry one); intra-minute extremes (only minute closes are available); why D0 differs; the real VIX/IV series was never available.
* **Status:** the breakout variable is an exploratory finding that survived out-of-cycle validation, permutation nulls and a chronological split; it is not an independent holdout. Reconstructed behaviour is not the original source logic.
""")
open(os.path.join(REP, 'BODY_SOLO_VARIABLE_SEARCH.md'), 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
