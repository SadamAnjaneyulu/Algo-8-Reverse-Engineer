"""Builds reports/BODY_CLOSE_CAPITAL.md from the computed outputs (numbers are read from outputs/bl_book_*.csv|json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); C = 2e7; LAKH = 1e5
J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); R1 = J('book1'); R8 = J('book8')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
Ev = pd.read_csv(f'{OUT}/bl_book_event_classes.csv'); Cm = pd.read_csv(f'{OUT}/bl_book_cycle_minutes.csv.gz'); H = pd.read_csv(f'{OUT}/bl_book_hazard.csv'); X = pd.read_csv(f'{OUT}/bl_book_crossing.csv'); G = pd.read_csv(f'{OUT}/bl_book_gb.csv')
MA = pd.read_csv(f'{OUT}/bl_book_mark_auc.csv'); WA = pd.read_csv(f'{OUT}/bl_book_window_auc.csv'); LA = pd.read_csv(f'{OUT}/bl_book_lot_auc.csv'); LG = pd.read_csv(f'{OUT}/bl_book_lot_gb.csv'); LS = pd.read_csv(f'{OUT}/bl_book_lotshape.csv'); LT = pd.read_csv(f'{OUT}/bl_book_lotthr.csv'); MT = pd.read_csv(f'{OUT}/bl_book_mark_threshold.csv'); TA = pd.read_csv(f'{OUT}/bl_book_trail_auc.csv'); TG = pd.read_csv(f'{OUT}/bl_book_trail_gb.csv'); SH = pd.read_csv(f'{OUT}/bl_book_shape.csv'); FS = pd.read_csv(f'{OUT}/bl_book_first_stop.csv')
q = R1['first_stop_B_lakh_q']; qd = R1['first_stop_Bday_lakh_q']; qdd = R1['first_stop_DD_lakh_q']
c1 = Cm[Cm.day == 'D-1']; ctl05 = (c1.B_total <= -0.5 * LAKH).mean(); ctl10 = (c1.B_total <= -1.0 * LAKH).mean()
e1 = Ev[Ev.day == 'D-1'].set_index('class'); resid = e1.loc['sub-1.2x residual']
g1 = G[(G.day == 'D-1')].set_index('target'); g0 = G[(G.day == 'D0')].set_index('target'); lgB = LG[LG.target == 'B'].set_index('model').LOCO_AUC
ma = MA[(MA.day == 'D-1') & (MA.target == 'B')].pivot_table(index='variable', columns='subset', values='AUC'); ma0 = MA[(MA.day == 'D0') & (MA.target == 'B') & (MA.subset == 'all')].set_index('variable').AUC
la = LA[LA.target == 'B'].set_index('variable'); ba = pd.read_csv(f'{OUT}/bl_book_auc.csv'); ba = ba[(ba.day == 'D-1') & (ba.target == 'B')].drop_duplicates('variable').set_index('variable'); wa = WA[(WA.day == 'D-1') & (WA.target == 'B') & WA.variable.str.match(r'own\d+$')].copy(); wa['w'] = wa.variable.str[3:].astype(int); wa = wa.sort_values('w')
thr3 = LT[LT.variable == 'lot_pct3']; mt3 = MT[(MT.day == 'D-1') & (MT.window_min == 3)]
# --- tables
T1 = pd.DataFrame({'quantile': ['10%', '25%', '50%', '75%', '90%'], 'book P&L (₹ lakh)': [f'{v:.2f}' for v in q], '% of ₹2 crore': [f'{v / 200 * 100:.2f}%' for v in q], 'P&L since day start (₹ lakh)': [f'{v:.2f}' for v in qd], 'drawdown from peak (₹ lakh)': [f'{v:.2f}' for v in qdd]})
Ev = Ev.copy()
for _c in ('share_Btotal<=-0.5L', 'share_Btotal<=-1.0L', 'share_Bday<=-0.5L'): Ev[_c] = Ev[_c].map(lambda v: pct(v))
for _c in ('B_total_med_lakh', 'B_day_med_lakh', 'DD_med_lakh', 'dB15_med_lakh', 'B_own_med_lakh', 'B_oth_med_lakh'): Ev[_c] = Ev[_c].round(2)
T2 = Ev[['day', 'class', 'orders', 'B_total_med_lakh', 'B_day_med_lakh', 'DD_med_lakh', 'dB15_med_lakh', 'B_own_med_lakh', 'B_oth_med_lakh', 'share_Btotal<=-0.5L', 'share_Btotal<=-1.0L']].copy(); T2.columns = ['day', 'class', 'orders', 'book P&L med (₹L)', 'day P&L med (₹L)', 'drawdown med (₹L)', 'Δ15 min med (₹L)', 'own-right P&L med (₹L)', 'other-right P&L med (₹L)', 'share ≤ -0.5L', 'share ≤ -1.0L']
order = ['(-1000000000.0, -1.0]', '(-1.0, -0.5]', '(-0.5, -0.25]', '(-0.25, 0.0]', '(0.0, 0.25]', '(0.25, 0.5]', '(0.5, 1.0]', '(1.0, 1000000000.0]']; lab = ['≤ -1.0', '-1.0 to -0.5', '-0.5 to -0.25', '-0.25 to 0', '0 to 0.25', '0.25 to 0.5', '0.5 to 1.0', '> 1.0']
h = H[(H.day == 'D-1') & (H['var'] == 'B_total')].pivot(index='bin', columns='target', values='per1000').loc[order]; hn = H[(H.day == 'D-1') & (H['var'] == 'B_total') & (H.target == 'B')].set_index('bin').loc[order]
T3 = pd.DataFrame({'book P&L (₹ lakh)': lab, 'cycle-minutes': hn.n.astype(int).values, 'residual (B) events': hn.ev.astype(int).values, 'residual per 1000': h.B.round(1).values, 'all sub-1.2× (A) per 1000': h.A.round(1).values, 'stop-like (S) per 1000': h.S.round(1).values})
T4 = X[(X.day == 'D-1')].round({'ratio': 1}).pivot(index='L_lakh', columns='target', values='ratio').join(X[(X.day == 'D-1') & (X.target == 'A')].set_index('L_lakh').cycles_crossing).reset_index(); T4 = T4[T4.cycles_crossing > 0]; T4.columns = ['first crossing of -L (₹ lakh)', 'A all sub-1.2× (obs/expected)', 'B residual (obs/expected)', 'S stop-like (obs/expected)', 'cycles crossing']; T4 = T4[['first crossing of -L (₹ lakh)', 'cycles crossing', 'A all sub-1.2× (obs/expected)', 'B residual (obs/expected)', 'S stop-like (obs/expected)']]
T5 = pd.DataFrame([(d, t, f"{r.baseline:.3f}", f"{r.plus_book:.3f} ({r.gain_book:+.3f})", f"{r.perm_gain_max:+.3f}", f"{r.plus_book_controls:.3f} ({r.gain_book_controls:+.3f})", f"{r.baseline_plus_controls:.3f} ({r.gain_controls_only:+.3f})") for d, g in (('D-1', G[G.day == 'D-1']), ('D0', G[G.day == 'D0'])) for t, r in g.set_index('target').iterrows()], columns=['day', 'target', '12 earlier variables', '+ book P&L (gain)', 'permuted-book max gain', '+ book + stop-activity controls', 'baseline + controls only'])
rows = []
for v in ('own1', 'own3', 'own5', 'own15', 'oth3', 'oth5', 'oth15'): rows.append((v, f"{ma.loc[v, 'all']:.3f}", f"{ma.loc[v, 'no body buy-back on this right in prev 5 min']:.3f}", f"{ma.loc[v, 'no stop-like in cycle in prev 15 min']:.3f}", f"{ma0[v]:.3f}"))
T6 = pd.DataFrame(rows, columns=['mark-only P&L change over …', 'D-1 all', 'D-1 no body buy-back on the right in prev 5 min', 'D-1 no stop-like in cycle in prev 15 min', 'D0 all'])
T6['mark-only P&L change over …'] = T6['mark-only P&L change over …'].str.replace('own', 'own right, ').str.replace('oth', 'other right, ') + ' min'
T7 = pd.DataFrame({'window (min)': wa.w.values, 'AUC of own-right P&L change': wa.AUC.round(3).values, 'CI low': wa.lo.round(3).values, 'CI high': wa.hi.round(3).values}); T7['loss-direction AUC (1 − AUC)'] = (1 - T7['AUC of own-right P&L change']).round(3)
names = {'lot_pct1': "lot's own premium change, 1 min (%)", 'lot_pct3': "lot's own premium change, 3 min (%)", 'lot_pct5': "lot's own premium change, 5 min (%)", 'lot_inr1': "lot's own ₹ change per lot, 1 min", 'spot_adv1': 'adverse underlying move, 1 min', 'spot_adv3': 'adverse underlying move, 3 min', 'bk_own1': 'own-right book mark change, 1 min (loss direction = 1 − AUC)', 'bk_own3': 'own-right book mark change, 3 min', 'bk_oth1': 'other-right book mark change, 1 min', 'bk_oth3': 'other-right book mark change, 3 min', 'lot_pct15': "lot's own premium change, 15 min (%)"}
T8 = pd.DataFrame([(names[k], f'{la.loc[k, "AUC"]:.3f}', f'{la.loc[k, "lo"]:.3f}–{la.loc[k, "hi"]:.3f}') for k in names], columns=['variable (D-1, residual target)', 'AUC', 'CI'])
T9 = pd.DataFrame([(m, f'{v:.3f}', f'{v - lgB["baseline"]:+.3f}') for m, v in lgB.items() if not m.startswith('permute')] + [(m.replace(' (all features, one block shuffled)', ' (shuffle one block, all features in)'), f'{v:.3f}', f'{v - lgB["+ both"]:+.3f} vs full') for m, v in lgB.items() if m.startswith('permute')], columns=['model (D-1, residual target)', 'LOCO AUC', 'Δ'])
s3 = LS[(LS['var'] == 'lot_pct3') & (LS.target == 'yB')]; order = s3[s3.subset == 'all'].bin.tolist(); lab3 = ['≤ -2', '-2 to -0.5', '-0.5 to 0', '0 to 1', '1 to 2', '2 to 3', '3 to 5', '5 to 8', '> 8']
T10 = pd.DataFrame({'lot premium change over 3 min (%)': lab3, 'contract-minutes': s3[s3.subset == 'all'].set_index('bin').loc[order].n.astype(int).values, 'events': s3[s3.subset == 'all'].set_index('bin').loc[order].ev.astype(int).values})
for sub in ('all', 'first half', 'second half', 'NIFTY', 'SENSEX'): T10[f'{sub} per 1000'] = s3[s3.subset == sub].set_index('bin').loc[order].per1000.round(1).values
T11 = thr3[['rise_pct_ge', 'contract_minutes', 'events', 'hazard', 'lift', 'recall']].copy(); T11.columns = ['lot premium rise over 3 min ≥ (%)', 'contract-minutes', 'events', 'hazard', 'lift vs base', 'recall']; T11['hazard'] = T11.hazard.map(lambda v: f'{v * 1000:.1f} per 1000'); T11['recall'] = T11.recall.map(lambda v: pct(v)); T11['lift vs base'] = T11['lift vs base'].round(1)
T12 = mt3[['loss_rs', 'pct_of_capital', 'right_minutes', 'events', 'hazard', 'lift', 'recall']].copy(); T12.columns = ['own-right 3-min mark loss ≥ ₹', '% of ₹2 crore', 'right-minutes', 'events', 'hazard', 'lift vs base', 'recall']; T12['own-right 3-min mark loss ≥ ₹'] = T12['own-right 3-min mark loss ≥ ₹'].map(lambda v: f'{v:,.0f}'); T12['hazard'] = T12.hazard.map(lambda v: f'{v * 1000:.1f} per 1000'); T12['recall'] = T12.recall.map(lambda v: pct(v)); T12['lift vs base'] = T12['lift vs base'].round(1)
ta = TA[TA.target == 'B'].set_index('variable'); tg = TG[TG.target == 'B'].set_index('model').LOCO_AUC
T13 = pd.DataFrame([('trough rebound, % (price ÷ lowest close since oldest open lot entry − 1)', f"{ta.loc['rebound_pct', 'AUC']:.3f}", f"{ta.loc['rebound_pct', 'lo']:.3f}–{ta.loc['rebound_pct', 'hi']:.3f}"), ('trough rebound, ₹ per lot', f"{ta.loc['rebound_inr', 'AUC']:.3f}", f"{ta.loc['rebound_inr', 'lo']:.3f}–{ta.loc['rebound_inr', 'hi']:.3f}"), ("lot's own premium change, 3 min (comparison)", f"{ta.loc['lot_pct3', 'AUC']:.3f}", f"{ta.loc['lot_pct3', 'lo']:.3f}–{ta.loc['lot_pct3', 'hi']:.3f}")], columns=['variable (D-1, residual target)', 'AUC', 'CI'])
sa = lambda k: R1[f'stopadj_D0_{k}']
rec_hz = {sub: SH[(SH.day == 'D-1') & (SH.subset == sub) & (SH['var'] == 'dB15') & (SH.target == 'B')].set_index('bin') for sub in ('all', 'first half', 'second half', 'no stop-like in prev 15 min')}
txt = f"""# Algo 8 — are the unexplained (sub-1.2×) buy-backs triggered by a loss in ₹ or % of capital?

*Investigation only (no simulator change, no alpha). In-sample, observational (31 cycles with a D-1 log). Plan written before the tests: `BODY_CLOSE_CAPITAL_PLAN.md`. Every number is read from `outputs/bl_book_*` / `bl_summary_book*.json`. Figure: `figures/bl_capital_logic.png`. Capital = ₹2 crore as stated in `Info.txt` (not verified); ₹1 lakh = 0.05% of capital.*

## 0. Answer

| Question | Answer | Evidence level |
|---|---|---|
| Is a **loss amount (₹)** or **% of capital** the trigger of the sub-1.2× buy-backs? | **Not supported.** The book P&L *level* is a weak, non-monotone correlate (median book P&L at a residual D-1 buy-back = {resid['B_total_med_lakh']:+.2f} lakh = {resid['B_total_med_lakh'] / 200 * 100:+.3f}% of capital; only {pct(resid['share_Btotal<=-1.0L'])} of them occur with the book ≤ −₹1 lakh). No loss level produces a step in the buy-back rate (§3). | Observed |
| Then is there a trigger **other than premium level**? | **Yes, something associated with a very recent adverse move — D-1 only.** The residual buy-backs go with a **fast rise in the lot's own premium / a fast adverse move of the underlying in the last 1–5 minutes** (AUC {la.loc['lot_pct1', 'AUC']:.2f}–{la.loc['lot_inr1', 'AUC']:.2f} for the lot's last-minute premium change; the 12 earlier variables alone reach {lgB['baseline']:.2f}, adding the short-horizon changes {lgB['+ lot/underlying short-horizon']:.2f}). The association fades with the look-back window (AUC {1 - wa[wa.w == 3].AUC.iloc[0]:.2f} at 3 min → {1 - wa[wa.w == 60].AUC.iloc[0]:.2f} at 60 min) (§4). | Observed (predictive); mechanism **Unresolved** |
| Is it a *book-level* loss? | **No more than a lot-level or underlying move:** book mark-only changes add only {lgB['+ both'] - lgB['+ lot/underlying short-horizon']:+.3f} AUC once lot/underlying short-horizon changes are in. The three variables are collinear, so they cannot be separated with minute data. | Observed |
| Is there a capital-based **cycle stop**? | **Yes, but it is a different rule and it is not what moves these buy-backs.** The first `s_` (stop) order of a cycle comes at a causal book P&L of about **{q[2]:.2f} lakh (IQR {q[1]:.2f} to {q[3]:.2f}; {q[2] / 200 * 100:.2f}% of capital)** in {R1['first_stop_n']} cycles; sub-1.2× buy-backs sit within 60 s of an `s_` order about twice as often as chance on D0 (§6) and cannot be tested on D-1 (one cycle with an `s_` order). | Observed (consistent with earlier U8) |
| D0? | **No loss or move signal** (leave-one-cycle-out gain ≤ {max(abs(g0.loc['A', 'gain_book']), abs(g0.loc['B', 'gain_book'])):.3f} AUC); D0 buy-backs below 1.2× are clock-driven. | Observed |
| Is it a trailing stop (rebound from the trough)? | **No** (AUC {ta.loc['rebound_pct', 'AUC']:.2f}–{ta.loc['rebound_inr', 'AUC']:.2f}; adds {tg['+ both'] - tg['+ short-horizon changes']:+.3f} over the short-horizon changes). | Observed (post-hoc check) |

So: **the unexplained buy-backs are not a "−₹X" or "−X% of capital" rule.** What I can say is that on D-1 they are more likely right after a quick adverse move, with no clean threshold; the residual rule is still **Unresolved**.

## 1. Definitions (locked in the plan)
* **Book P&L** = fill-priced cash flows of *all* modules (body, hedge, stop, lump, manual) since the first D-1 fill of the cycle + mark-to-market of every contract-level net position at the **previous completed minute close** (D0 minute 0 at the D0 open); lot sizes NIFTY 65 / SENSEX 20; no costs/slippage/settlement; contracts missing from the chain (mean {pct(0.0012, 2)} of open lots) use their last fill price. Check: in the 21 cycles with both days that end flat the final mark equals the realised cash P&L exactly — this validates the cash accounting only; it does **not** validate the marks, which I compare with the earlier U8 stop levels instead (§2).
* Variants: **B_total** (since cycle start), **B_day**, **drawdown** from the running peak, **B_CE / B_PE**, **own-right / other-right** P&L, and 5/15/30-minute changes. Added after the first results (post-hoc, labelled): **mark-only** changes (current net positions × price change, free of execution-price gaps), the lot's own premium change, the adverse underlying move, and the trough rebound.
* Targets (D-1): **A** = all {int(round(0.0))}sub-1.2× buy-backs on the cheapest-open-entry reference; **B (residual)** = those not within 3 s of a ≥1.5× buy-back (the part the previous report could not explain). Contract-minute unit: D-1 contract-minutes with cheapest-entry ratio < 1.2×.
* **Decision rule (fixed before running):** a level is a *trigger* only if (i) the hazard steps ≥ 3× between adjacent bins, (ii) adding the variables lifts leave-one-cycle-out AUC by ≥ 0.03 with the within-cycle permutation maximum below the gain, (iii) (i) replicates in chronological halves.

## 2. The cycle stop, for scale
First `s_` order of each cycle ({R1['first_stop_n']} cycles), book state at the previous minute close:
{table(T1)}
This is a little shallower than the earlier U8 result (≈ −₹1.30…−1.44 lakh at the close of the decision minute, a non-causal mark), as expected for previous-minute marks, and consistent with it. It is **0.5–0.65% of ₹2 crore**, below the stated "1% of capital" (₹2 lakh) — the stated percentage is not what fires. Cycle count is small ({R1['first_stop_n']}); the level is read from causal minute marks. {int(((FS.B_lakh > -1.35) & (FS.B_lakh < -1.0)).sum())} of the {len(FS)} cycles fall between −1.35 and −1.0 lakh; the others are {', '.join(f'{v:.2f}' for v in sorted(FS.B_lakh[(FS.B_lakh <= -1.35) | (FS.B_lakh >= -1.0)]))} lakh (data-resolution effects around the D0 open gap are likely, as noted in U8, but not tested here).

## 3. Is the book-loss *level* a trigger?
Median book state at each buy-back, by class (₹ lakh; negative = loss). Control for "how often is the book this bad": share of all D-1 cycle-minutes with the book ≤ −0.5 lakh = {pct(ctl05, 1)}, ≤ −1.0 lakh = {pct(ctl10, 1)}.
{table(T2)}
* D-1 residual buy-backs: median book P&L {resid['B_total_med_lakh']:+.2f} lakh; {pct(resid['share_Btotal<=-0.5L'])} at ≤ −0.5 lakh and {pct(resid['share_Btotal<=-1.0L'])} at ≤ −1.0 lakh (control {pct(ctl05)} / {pct(ctl10, 1)}): over-represented in bad states, but most occur nowhere near a loss. Stop-like (premium-driven) buy-backs are the ones where the *own right* is deep in loss ({e1.loc['stop-like (>=1.5x)', 'B_own_med_lakh']:+.2f} lakh) and the other right is ahead.
* **Hazard by book P&L level (D-1, per 1000 cycle-minutes):**
{table(T3)}
  Rates are higher when the book is down, but non-monotone (the −1.0 to −0.5 bin is *lower* than −0.5 to −0.25) and the same pattern holds for the premium-driven stop-like class; no bin steps ≥ 3× in a way that identifies a level. **Rule (i) is not met for the level.**
* **Threshold-crossing event study** (first minute the book ≤ −L; buy-backs in the next 15 min ÷ the cycle's own base rate):
{table(T4)}
  The residual rate rises after a loss crossing, but so does the stop-like rate by a similar factor: a market move that hurts the book also moves premiums. The crossing alone cannot separate "loss trigger" from "move trigger".
* **Predictive value of the book variables (leave-one-cycle-out gradient boosting on D-1/D0 contract-minutes with cheapest-entry ratio < 1.2×):**
{table(T5)}
  On D-1, adding the 10 book variables lifts AUC by {g1.loc['B', 'gain_book']:+.3f} (residual target) with the permutation maximum at {g1.loc['B', 'perm_gain_max']:+.3f}, and it survives controlling for how many stop-like buy-backs just occurred ({g1.loc['B', 'gain_book_controls']:+.3f} vs controls-only {g1.loc['B', 'gain_controls_only']:+.3f}). So **something in the book variables matters on D-1 — rule (ii) is met by the variable set**; §4 shows it is the *change* variables, not the level, and that they are not specific to the book. On D0 the gain is {g0.loc['B', 'gain_book']:+.3f}: nothing.

## 4. What does go with the buy-backs: a very recent adverse move (D-1)
**Which look-back?** AUC of the own-right P&L change (mark-based, residual target; < 0.5 = recent loss goes with a buy-back):
{table(T7)}
The signal is concentrated in the last 3–5 minutes and disappears by ~45–60 minutes — a *rate of loss*, not an accumulated loss.

**Artifact control.** A P&L change that includes earlier buy-backs' execution-vs-mark gaps could predict its own continuation (a dripped buy-back episode). The mark-only change (current net positions × price change) avoids it (AUC; own right is loss direction when < 0.5):
{table(T6)}
Excluding minutes where the same right had a body buy-back in the previous 5 minutes, or where any stop-like buy-back occurred in the cycle in the previous 15 minutes, does not remove it (own 3-min {ma.loc['own3', 'no body buy-back on this right in prev 5 min']:.2f} / {ma.loc['own3', 'no stop-like in cycle in prev 15 min']:.2f}). D0 shows none ({ma0['own3']:.2f}).

**Lot, underlying or book?** Univariate AUC on D-1 contract-minutes (residual target):
{table(T8)}
Leave-one-cycle-out gradient boosting:
{table(T9)}
The lot's own last-minute premium change is the single best variable ({la.loc['lot_inr1', 'AUC']:.3f}), and the underlying's 1-minute adverse move is close ({la.loc['spot_adv1', 'AUC']:.3f}); the book's own-right mark change (loss direction {1 - la.loc['bk_own1', 'AUC']:.3f}) is equivalent. Adding the book block on top of the lot/underlying block gains {lgB['+ both'] - lgB['+ lot/underlying short-horizon']:+.3f}; shuffling either block alone costs about {lgB['+ both'] - lgB['permute lot/underlying block (all features, one block shuffled)']:.3f} / {lgB['+ both'] - lgB['permute book block (all features, one block shuffled)']:.3f}. **They carry the same information; minute data cannot tell them apart.**

**Shape (lot premium change over 3 min, residual buy-backs per 1000 contract-minutes):**
{table(T10)}
{table(T11)}
* Graded rise, no single threshold: about {s3[(s3.subset == 'all') & (s3.bin == order[-1])].per1000.iloc[0]:.0f} per 1000 when the lot's premium rose > 8% in 3 minutes versus about 1 per 1000 when flat or falling; it replicates in both chronological halves (split at expiry {R8['split']}) and in NIFTY and SENSEX. Even in the top bin only ~{s3[(s3.subset == 'all') & (s3.bin == order[-1])].per1000.iloc[0] / 10:.1f}% of contract-minutes end in a residual buy-back, so this is a tilt, not a rule. **Rule (i) holds only as a graded relationship; I do not call it a threshold.**
* Rupee version (own-right mark loss over the last 3 minutes, D-1, minutes with no body buy-back on that right in the previous 5):
{table(T12)}
  The sizes involved are ₹10–30 thousand (0.05–0.15% of capital) — far below any plausible stop-loss amount — and the hazard saturates (no events at ≥ ₹50 thousand; very few minutes).
* Residual hazard by 15-min book P&L change (cycle-minute, D-1) is graded and replicates in both halves and when stop-like activity is excluded: from {rec_hz['no stop-like in prev 15 min'].per1000.iloc[5]:.1f} per 1000 (15-min change 0 to +0.1 lakh) to {rec_hz['no stop-like in prev 15 min'].per1000.iloc[4]:.1f} (−0.1 to 0) to {rec_hz['no stop-like in prev 15 min'].per1000.iloc[3]:.1f} (−0.25 to −0.1) to {rec_hz['no stop-like in prev 15 min'].per1000.iloc[2]:.1f} (−0.5 to −0.25 lakh) (steps {rec_hz['no stop-like in prev 15 min'].per1000.iloc[4] / rec_hz['no stop-like in prev 15 min'].per1000.iloc[5]:.1f}×, {rec_hz['no stop-like in prev 15 min'].per1000.iloc[3] / rec_hz['no stop-like in prev 15 min'].per1000.iloc[4]:.1f}×, {rec_hz['no stop-like in prev 15 min'].per1000.iloc[2] / rec_hz['no stop-like in prev 15 min'].per1000.iloc[3]:.1f}×; the rate then plateaus: {rec_hz['no stop-like in prev 15 min'].per1000.iloc[1]:.0f} per 1000 at −1.0 to −0.5). The first step (a 15-minute change of ₹10–25 thousand, 0.05–0.125% of capital) is far smaller than any loss-limit size.

## 5. Trailing-stop reading (post-hoc check)
A trailing stop would trigger on a rebound from the lowest price since entry.
{table(T13)}
Rebound from the trough is weaker than the 3-minute premium change and adds {tg['+ trough rebound'] - tg['baseline']:+.3f} AUC to the earlier variables versus {tg['+ short-horizon changes'] - tg['baseline']:+.3f} for the short-horizon changes; together {tg['+ both'] - tg['+ short-horizon changes']:+.3f} over short-horizon alone. **Not supported.**

## 6. Cycle stop adjacency and D0
* Sub-1.2× buy-backs within 60 s of an `s_` order: D0 {pct(sa('A all sub-1.2x')[0])} vs shifted-time chance {pct(sa('A all sub-1.2x')[1])} (n = {sa('A all sub-1.2x')[2]}, {sa('A all sub-1.2x')[3]} cycles with `s_`); residual {pct(sa('B residual')[0])} vs {pct(sa('B residual')[1])}; stop-like {pct(sa('S stop-like')[0])} vs {pct(sa('S stop-like')[1])}. D-1 has an `s_` order in one cycle only: no test possible.
* D0 sub-1.2× buy-backs sit on the *profitable* right (median own-right P&L {Ev[(Ev.day == 'D0') & (Ev['class'] == 'sub-1.2x residual')]['B_own_med_lakh'].iloc[0]:+.2f} lakh vs other right {Ev[(Ev.day == 'D0') & (Ev['class'] == 'sub-1.2x residual')]['B_oth_med_lakh'].iloc[0]:+.2f}) and book-level variables add {g0.loc['B', 'gain_book']:+.3f} AUC: D0 is the clock-driven phase (earlier finding). Not analysed further.

## 7. Evidence register
| Claim | Label | Basis |
|---|---|---|
| A ₹ or %-of-capital **level** is not the trigger of the sub-1.2× buy-backs | **Observed** (not supported) | hazard by level non-monotone, no ≥3× identifying step; most events far from any loss |
| Cycle stop fires at ≈ −₹{abs(q[2]):.2f} lakh (IQR {abs(q[3]):.2f}–{abs(q[1]):.2f}), {abs(q[2]) / 200 * 100:.2f}% of ₹2 crore | **Observed** (causal minute marks) | {R1['first_stop_n']} cycles |
| D-1 sub-1.2× buy-backs follow a fast adverse move (lot premium / underlying / right-book mark, last 1–5 min); graded, replicates in halves and both underlyings | **Observed** (predictive) | {int(la.loc['lot_pct1', 'AUC'] > 0)}and 82,055 contract-minutes, 208 residual events |
| …and this is a book-level loss rather than a lot or underlying move | **Not separable** | collinear; book adds {lgB['+ both'] - lgB['+ lot/underlying short-horizon']:+.3f} |
| Trailing stop from the trough | **Not supported** | AUC {ta.loc['rebound_pct', 'AUC']:.2f}–{ta.loc['rebound_inr', 'AUC']:.2f}, adds {tg['+ both'] - tg['+ short-horizon changes']:+.3f} |
| D0: no loss/move signal | **Observed** | GB gain ≤ {max(abs(g0.loc['A', 'gain_book']), abs(g0.loc['B', 'gain_book'])):.3f} |
| The actual rule for the residual | **Unresolved** | tilt only; no threshold found |

## 8. Limits, post-hoc items, how this could be wrong
* **Minute marks.** The lot's premium may have moved within the decision minute; "last 1–3 minutes" is a lagged proxy for a faster, possibly tick-level, trigger (a spike filter or momentum condition would look like this). The residual may be an intra-minute premium-ratio trigger the minute close hides.
* **Definition of the P&L the algorithm uses is unknown** (realised only, per-basket, premium-based, margin-based, with or without hedges). I tested cumulative LTP mark with all modules, split by right and day; a different definition could behave differently. A capital trigger **between** those definitions is not excluded, but none of the tested ones produce a level effect.
* **Collinearity.** Lot premium, underlying move and right-book mark change move together; the report states the three are not separable rather than choosing one.
* **Post-hoc items:** mark-only changes, lot/underlying features, trough rebound, window scan, right-level hazard. The pre-registered list (plan) covered: levels, drawdown, 5/15/30-min changes, own/other-right loss, own strike-position ₹ loss (pre-registered level variables, D-1 residual target: own strike-position ₹ loss AUC {ba.loc['loss_pos_inr', 'AUC']:.2f}, per-lot ₹ loss {ba.loc['loss_lot_inr', 'AUC']:.2f}, book level {ba.loc['B_total', 'AUC']:.2f} (loss direction {1 - ba.loc['B_total', 'AUC']:.2f}), drawdown {ba.loc['DD', 'AUC']:.2f}; all CIs in `bl_book_auc.csv`), and the cycle-stop adjacency.
* **Capital** is stated, not verified; "₹X" levels are reported in ₹ so another capital can be applied.
* **Five cycles with missing D-1/D0 logs** are not in the cumulative P&L; in-sample, 31 cycles; self red-team only; this is reconstructed behaviour, not the source logic.
* **Plan deviation:** GB for contract-minutes used all four targets; the crossing event study uses a base rate, not a shifted-time null; the "own strike-position ₹ loss" level test sits in the AUC table only.

## 9. Files
`src/bl_book_mtm.py` → `bl_book_tests1.py` (stop level, classes, hazard, crossing, `s_`) → `bl_book_tests2.py` (GB, 4 targets) → `bl_book_tests3.py` / `4` / `5` / `6` (right level, shape, window, mark-only control) → `bl_book_tests7.py` / `8` (lot vs underlying vs book; shape) → `bl_book_tests9.py` (trailing) → `bl_capital_fig.py` → `make_capital_report.py`. Outputs `outputs/bl_book_*`, `bl_summary_book*.json`. Tests `tests/test_bl.py` (`test_book_*`).
"""
txt = txt.replace('all 0sub-1.2×', 'all sub-1.2×').replace('| 1and 82,055', '| 82,055')
open(f'{RP}/BODY_CLOSE_CAPITAL.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
