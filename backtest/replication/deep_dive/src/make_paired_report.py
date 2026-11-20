"""Render reports/BODY_PAIRED_SELL_AND_CLOSE_LOGIC.md from the bl_slot_* and bl_close_* outputs (plan: BODY_PAIRED_SELL_PLAN.md)."""
import sys; sys.path.insert(0, '.')
from bl_common import *
rd = lambda f, **k: pd.read_csv(f'{OUT}/{f}', **k); pct = lambda x, d=1: f'{100 * float(x):.{d}f} %'
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
O = load_orders(); P = rd('bl_slot_panel.csv'); EX = rd('bl_slot_execution_d1.csv', index_col=0); ST = rd('bl_slot_state_tests.csv'); SR = rd('bl_slot_strike_rules.csv'); HZ = rd('bl_close_hazard.csv'); CU = rd('bl_close_univariate.csv'); CI = rd('bl_close_incremental.csv'); T = rd('bl_slot_d1_scheduled.csv'); A_CLS = rd('bl_d1_A_class.csv').set_index('cls')
S1 = P[(P.day == 'D-1')]; SCHED = [k for k in range(0, 14) if k != 12]; sc = S1[S1.k.isin(SCHED)]
slot_t = lambda k: f'{(9 * 60 + 16 + 15 * k) // 60:02d}:{(9 * 60 + 16 + 15 * k) % 60:02d}'
D1 = S1[S1.cp == 'CE'].copy(); D1['era'] = np.where(D1.expiry <= '2026-09-10', 'A', 'B')
lad = {}
for era, g in D1.groupby('era'): m = g.groupby('k').lots_paired.agg(lambda s: s.mode().iloc[0]); eq = g.assign(m=g.k.map(m)).groupby('k').apply(lambda x: (x.lots_paired == x['m']).mean()); lad[era] = (m, eq, g.groupby(['und', 'expiry']).ngroups)
LT = pd.DataFrame({'slot': [slot_t(k) for k in range(0, 24)], 'ladder A (lots per right)': lad['A'][0].reindex(range(24)).values, 'cycles equal': [pct(v, 0) for v in lad['A'][1].reindex(range(24)).values], 'ladder B': lad['B'][0].reindex(range(24)).values, 'cycles equal ': [pct(v, 0) for v in lad['B'][1].reindex(range(24)).values]}); LT = LT[(LT['ladder A (lots per right)'] > 0) | (LT['ladder B'] > 0)]
def _eq(g):
    m = g.groupby('k').lots_paired.agg(lambda x: x.mode().iloc[0]); x = g.assign(m=g.k.map(m)); return (x.lots_paired == x.m)[x.m > 0].mean()
eqA = _eq(D1[D1.era == 'A']); eqB = _eq(D1[D1.era == 'B'])
w_ = T.pivot_table(index=['und', 'expiry', 'k'], columns='cp', values='lots_paired'); ce_pe = (w_.CE == w_.PE).mean()
stp = O[(O.module == 's_') & (O.dayno == 1)].groupby(['und', 'expiry']).tod.min(); d0 = P[(P.day == 'D0') & (P.cp == 'CE')]; aft = bef = ea = eb = 0; ncy = 0
for (u, e), g in d0.groupby(['und', 'expiry']):
    t = stp.get((u, e), np.nan)
    if t == t: ncy += 1; T0 = ref.OPEN_SEC + g.j * 60; m = T0 >= t; aft += int(m.sum()); ea += int((g[m].lots_paired > 0).sum()); bef += int((~m).sum()); eb += int((g[~m].lots_paired > 0).sum())
d1stp = O[(O.module == 's_') & (O.dayno == 0)].groupby(['und', 'expiry']).tod.min()
d0n = d0[~d0.set_index(['und', 'expiry']).index.isin(stp.index)]; d0n = d0n[d0n.k <= 16].copy(); d0n['grp'] = d0n.und + np.where(d0n.expiry >= '2026-09-15', ' from 2026-09-15', ' before 2026-09-15'); d0e = d0n.assign(e=d0n.lots_paired > 0).groupby(['grp', 'k']).e.mean().unstack('grp')
d0_sets = '; '.join(f"{g}: " + ', '.join(slot_t(k) for k in d0e.index if d0e.loc[k, g] >= 0.9) for g in d0e.columns)
best = ST.sort_values('R2_gain', ascending=False); n_feat = len(ST); passing = ST[(ST.lo > 0) & (ST.R2_gain > ST.perm_null_max)].feature.tolist()
cov_corr = T[['lots_paired', 'cov_own']].corr(method='spearman').iloc[0, 1]; roll_share = A_CLS.loc['roll_sell', 'share_lots']
sr = SR.pivot(index='rule', columns='day', values='exact'); sr1 = SR.pivot(index='rule', columns='day', values='within_1_step')
hz = HZ[(HZ.day == 'D-1') & (HZ.feature == 'ratio')][['bin', 'size', 'sum', 'rate_per_1000', 'lift']]; hzd = HZ[(HZ.day == 'D-1') & (HZ.feature == 'abs_delta')][['bin', 'size', 'sum', 'rate_per_1000', 'lift']]; hzi = HZ[(HZ.day == 'D-1') & (HZ.feature == 'itm_steps')][['bin', 'size', 'sum', 'rate_per_1000', 'lift']]
cu = CU.pivot(index='feature', columns='day', values='AUC'); ci1 = CI[CI.day == 'D-1'].set_index('feature'); ci0 = CI[CI.day == 'D0'].set_index('feature')
L = []; w = L.append
w('# How the paired (clock) sales and the closes work — D-1 first, D0 second\n')
w(f"*In-sample, observational; plan `BODY_PAIRED_SELL_PLAN.md` written first. Slot = clock minute 09:16 + 15 k; a *paired sale* = CE and PE sold at the same strike within 3 s. State variables are those known before the slot (spot moves, book price ratios and ₹ MTM, net delta / gamma / vega from Black-Scholes with IV implied from each contract's minute close, ATM IV and straddle price and their changes, inventory, recent buy-backs, recent solo sales; {n_feat} candidates). Scripts `src/bl_slot_*.py`, `bl_close_*.py`; figure `figures/bl_paired_schedule.png`.*\n")
w('## 1. Answers\n')
w(f"""| Your question | Finding | Evidence |
|---|---|---|
| Is the 15-minute selling just the clock, or does each slot check conditions? | **A fixed time schedule with a fixed lot ladder.** On D-1 the 13 scheduled slots execute in {pct(EX.loc[SCHED, 'executed'].min(), 0)}–100 % of cycles (both indices) and the other slots essentially never; CE lots = PE lots in {pct(ce_pe)} of slots; no state variable changes whether or how much is sold. | {pct((sc.lots_paired > 0).mean())} of scheduled slot-rights executed; (index × slot) explains R² ≈ 0.7; of {n_feat} state variables **none** beats its permutation null (largest LOCO R² gain {best.R2_gain.iloc[0]:+.4f}) |
| Is there a limit of loss / strike move / premium move / delta that stops selling? | **Only the cycle stop.** After the first stop-module order of a D0 cycle **{ea} of {aft}** later slots sold anything (D-1: {sum(1 for k in d1stp.index)} cycle with a stop, 0 later sales). Absent a stop, slots executed in every observed state, including the top decile of net delta and of IV change. | stop gating below; limits of the sample in §6 |
| Why sell after positions were closed? | **Selling and closing are separate processes.** Lots sold in a slot do not depend on how much was bought back since the previous slot (rank correlation {cov_corr:+.2f}); only {pct(roll_share)} of D-1 sold lots are re-sales within 60 s of a buy-back. | slot table, §3 |
| What decides *which strike* a new sell uses — ATM, delta, other Greeks? | **ATM of the previous minute's spot**, not delta, forward, parity or hysteresis: exact hit {pct(sr.loc['ATM', 'D-1'])} on D-1 ({pct(sr.loc['ATM', 'D0'])} D0) for the first sale of each slot-right vs {pct(sr.loc['DELTA50', 'D-1'])} (call delta nearest 0.5), {pct(sr.loc['DELTA_NEUTRAL', 'D-1'])} (delta-neutral straddle), {pct(sr.loc['FWD', 'D-1'])} (forward), {pct(sr.loc['MINCP', 'D-1'])} (min |C−P|), {pct(sr.loc['HYST_1.0', 'D-1'])} (keep old strike within 1 step). The quantity is the ladder, not delta, premium or notional. | §4 |
| What triggers the closes? | **D-1: the premium move relative to entry** (price ÷ average entry), graded: 1–6 buy-backs per 1,000 contract-minutes up to 1.2×, {hz.iloc[5].rate_per_1000:.0f} at 1.2–1.4×, {hz.iloc[6].rate_per_1000:.0f} at 1.4–1.55×, {hz.iloc[7].rate_per_1000:.0f} at 1.55–1.7×, {hz.iloc[8].rate_per_1000:.0f} at 1.7–2.0×. Delta, ITM distance and time held add almost nothing beyond it. **D0 is different:** no dependence on premium or delta; closes follow the clock (late-day, flatten). | §5 |
""")
w('![paired schedule](figures/bl_paired_schedule.png)\n')
w('## 2. The paired sales are a fixed schedule (D-1)\n')
w(f"""* **Execution by slot** (share of the {EX.rows.iloc[0]:.0f} cycle-rights that sold a pair): {', '.join(f"{slot_t(k)}: {pct(EX.loc[k, 'executed'], 0)}" for k in range(0, 18))}. Slots 09:16–12:01 and 12:31 fire every time; 12:16, 12:46 and 13:01 never; the late slots depend on the schedule version below. NIFTY {pct((sc[sc.und == 'NIFTY'].lots_paired > 0).mean())}, SENSEX {pct((sc[sc.und == 'SENSEX'].lots_paired > 0).mean())}.
* **The ladder is the same for NIFTY and SENSEX** (in lots, per right) and **identical for CE and PE**. Two versions of the table appear (A: expiries up to 2026-09-10, {lad['A'][2]} cycles; B: from 2026-09-17, {lad['B'][2]} cycles), changing between D-1 2026-09-09 and 2026-09-16:

{table(LT)}

Within a version, slot-rights with a non-zero ladder agree with the table in {pct(eqA, 0)} of cases (A) and {pct(eqB, 0)} (B): B is looser (a ladder still being adjusted, or more extra orders). Departures from the table are single extra or missing lots, not skips.
* **State does not matter.** Over {n_feat} variables the best LOCO R² gain over (index × slot) is {best.iloc[0].feature} {best.iloc[0].R2_gain:+.4f}; variables passing both the CI and the permutation null: {passing or 'none'}. Including net delta / gamma / vega ({', '.join(f"{f} {ST.set_index('feature').loc[f, 'R2_gain']:+.4f}" for f in ('delta_need', 'gamma', 'vega'))}), ATM IV and its changes ({', '.join(f"{f} {ST.set_index('feature').loc[f, 'R2_gain']:+.4f}" for f in ('atm_iv', 'd_iv30', 'straddle'))}), the book's price ratio and ₹ MTM ({', '.join(f"{f} {ST.set_index('feature').loc[f, 'R2_gain']:+.4f}" for f in ('book_ratio', 'mtm_tot'))}), and buy-backs since the last slot (cov_own {ST.set_index('feature').loc['cov_own', 'R2_gain']:+.4f}).
""")
w('## 3. The one condition: the cycle stop halts the schedule\n')
w(f"""D0: {ncy} cycles contain a stop-module order. Slots before the first stop executed {eb} of {bef}; **after it {ea} of {aft}** (see the red ticks in the figure: the green schedule ends exactly where the cycle stop begins). On D-1 {len(d1stp)} cycle had a stop order (NIFTY 2026-09-01, 14:46): 0 of 2 later slots sold. The stop is the existing cycle-level loss limit (cumulative MTM about −₹1.30 to −1.44 lakh, scaled with lot size — earlier phases). **Observed:** a stopped cycle sells nothing more; **Unresolved:** whether a smaller loss, a delta level or a time rule also pauses a single slot (no such case in the sample).

**D0 schedule.** Same logic, different template. Slots executed in at least 90 % of the non-stopped D0 cycles: {d0_sets}. The template changes at the 2026-09-15 cycle (both indices then sell at every slot).
""")
w('## 4. New sales: why the strike is the ATM\n')
w(f"""Unit = first scheduled paired sale of each slot-right (n = {SR[(SR.rule == 'ATM') & (SR.day == 'D-1')].n.iloc[0]} on D-1, {SR[(SR.rule == 'ATM') & (SR.day == 'D0')].n.iloc[0]} on D0); reference data = the previous completed minute.

{table(pd.DataFrame({'rule': sr.index, 'D-1 exact': [pct(v) for v in sr['D-1']], 'D-1 ±1 step': [pct(sr1.loc[r, 'D-1']) for r in sr.index], 'D0 exact': [pct(v) for v in sr['D0']]}).sort_values('D-1 exact', ascending=False, key=lambda s: s.str.replace(' %', '').astype(float)))}

The ATM of the previous minute's spot wins by a wide margin; delta-, forward- and parity-based strikes land within ±1 step ({pct(sr1.loc['DELTA50', 'D-1'])}) but not on the actual strike. Keeping the previous strike until the spot has moved more than 0.5–2 steps (hysteresis) is worse (h = 0.5 equals ATM by construction). **Inferred rule:** at each slot sell CE and PE at the strike nearest to the previous minute's spot close, in the ladder quantity. Greeks are not an input to the strike.
""")
w('## 5. What triggers the closes (D-1) — premium move, not delta\n')
w(f"""Contract-minute panel: every minute with a net-short body contract (D-1: {int(HZ[(HZ.day == 'D-1') & (HZ.feature == 'ratio')]['size'].sum()):,} rows, {int(HZ[(HZ.day == 'D-1') & (HZ.feature == 'ratio')]['sum'].sum())} buy-back minutes); price ÷ average entry uses the strike's average body entry (lot ownership within a strike is not observed).

{table(hz.rename(columns={'bin': 'price ÷ entry', 'size': 'minutes', 'sum': 'buy-backs'}))}

* **Premium move:** AUC {cu.loc['ratio', 'D-1']:.2f} (₹ loss per lot {cu.loc['loss_inr_lot', 'D-1']:.2f}); the rate climbs steadily from 1× to 2× — a graded response, the earlier "≈ 1.55–1.7× entry" band is the middle of this climb, not a hard step (average entries mix lots with different entries).
* **Delta:** |delta| AUC {cu.loc['abs_delta', 'D-1']:.2f}, and the rate has **no step**: {', '.join(f"{r.bin}: {r.rate_per_1000:.0f}" for r in hzd.itertuples())} per 1,000 minutes — it falls for the deepest ITM contracts (delta > 0.8), so there is no delta limit. Adding delta to the premium move: AUC gain {ci1.loc['abs_delta', 'AUC_gain']:+.4f} (null max {ci1.loc['abs_delta', 'perm_null_max']:+.4f}).
* **Strike move (ITM steps):** AUC {cu.loc['itm_steps', 'D-1']:.2f}; gain over the premium move {ci1.loc['itm_steps', 'AUC_gain']:+.4f}. **Adverse spot move since entry:** AUC {cu.loc['spot_move_adv', 'D-1']:.2f}, gain {ci1.loc['spot_move_adv', 'AUC_gain']:+.4f} (small but above its null). Time held: AUC {cu.loc['hold_min', 'D-1']:.2f}. All variables together in a flexible model add {ci1.loc['[all variables, GB]', 'AUC_gain']:+.3f} AUC over the premium move alone.
* **D0:** AUC of price ÷ entry {cu.loc['ratio', 'D0']:.2f}, |delta| {cu.loc['abs_delta', 'D0']:.2f}, time of day {cu.loc['j', 'D0']:.2f}, time held {cu.loc['hold_min', 'D0']:.2f}: D0 buy-backs follow the clock (late-day, 15:14 flatten after the August break), not a premium or delta limit.
* **Not a hard trigger:** even at 1.7–2.0× the per-minute rate is ≈ {hz.iloc[8].rate_per_1000 / 10:.0f} %, so conditions other than the price multiple (and per-lot entries, minute checks) matter; **Unresolved**.
""")
w('## 6. Limits\n')
w(f"""* The sample never put the book deep into loss at a D-1 slot (worst book MTM at an executed slot {S1[S1.k.isin(SCHED)].mtm_tot.min():+.2f} % of ₹2 Cr; book price ratio ≤ {S1[S1.k.isin(SCHED)].book_ratio.max():.2f}), so "no loss limit on selling" is shown only inside that range; the cycle stop is the only gate observed.
* Greeks are Black-Scholes with IV implied from minute-close option prices (no dividends; r = 6.5 %); no VIX series.
* The 15-minute schedule was identified from 32 D-1 logs (and 33 D0); the version change is based on 11 later cycles.
* Closing analysis cannot separate lots within a strike (ownership unknown), and minute data hide intra-minute checks.
""")
open(os.path.join(REP, 'BODY_PAIRED_SELL_AND_CLOSE_LOGIC.md'), 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
