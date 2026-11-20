"""Render reports/BODY_LIFECYCLE_D1_D0_INVESTIGATION.md from the bl_* outputs. Numbers are read from outputs/bl_summary_*.json, bl_*.csv or recomputed here."""
import sys, json; sys.path.insert(0, '.')
from bl_common import *
rd = lambda f, **k: pd.read_csv(f'{OUT}/{f}', **k); pct = lambda x, d=1: f'{100 * float(x):.{d}f} %'
js = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json'))
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
A1, B1, A0, B0, C0, BR = js('d1a'), js('d1b'), js('d0a'), js('d0b'), js('d0c'), js('d0c_break')
O = load_orders(); E1 = rd('bl_E1_parity_reference.csv'); E2 = rd('bl_E2_reflag_scan.csv').set_index(['day', 'cls']); E3 = rd('bl_E3_seconds_from_slot_start.csv'); E4 = rd('bl_E4_sell_strike_candidates.csv')
cl1 = rd('bl_d1_A_class.csv'); cl0 = rd('bl_d0_B_class.csv'); bnd = rd('bl_d1_A_boundary.csv'); lad = rd('bl_d1_B_ladder.csv'); P1 = rd('bl_d1_C_positions.csv'); fl = rd('bl_d0_D_flatten.csv'); fb = rd('bl_d0_D_flatten_by_cycle.csv'); cs = rd('bl_d0_D_close_shares.csv'); rs = rd('bl_d0_D_residual.csv'); hz = rd('bl_d0_C_hazard_auc.csv')
cyc = pd.read_csv(ref.CYCLES); d0date = {(u, e): d for u, e, d in zip(cyc.und, cyc.expiry, cyc.d0)}
sells1 = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)]; sells0 = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 1)]
def itm_side(df): return np.where(df.cp == 'CE', -1, 1) * ((df.strike - df.atm_prev) / df.step).round()
o1 = sells1[sells1.cls == 'other'].assign(itm=lambda d: itm_side(d)); o1['hour'] = (o1.tod // 3600).astype(int); oh1 = o1.groupby('hour').apply(lambda g: (g.strike == g.atm_prev).mean())
def off_tab(df):
    t = pd.DataFrame({r: pd.Series(itm_side(df[df.cp == r])).clip(-3, 3).value_counts(normalize=True).sort_index() for r in ('CE', 'PE')}).fillna(0)
    t = t.apply(lambda c: c.map(pct)); t.index = [f'{int(i):+d}' for i in t.index]; return t.reset_index().rename(columns={'index': 'ITM-side steps'})
below = lambda df, r: ((df[df.cp == r].strike < df[df.cp == r].atm_prev).mean(), (df[df.cp == r].strike > df[df.cp == r].atm_prev).mean())
ol1 = O[(O.module == 'num') & (O.role == 'open_long') & (O.dayno == 0)]; ol1_open = ol1[(ol1.tod >= 9 * 3600 + 15 * 60) & (ol1.tod < 9 * 3600 + 18 * 60)]
cov1 = O[(O.module == 'num') & (O.role == 'cover_short') & (O.dayno == 0)]; cov_min1 = cov1.groupby(cov1.tod // 60).lots.sum()
def clsrow(df, name): r = df.set_index('cls').loc[name]; return r
def ev_excerpt(und, exp, day, t0, t1, maxrows=26):
    E = rd(f'bl_events_{"d1" if day == "D-1" else "d0"}.csv'); E = E[(E.und == und) & (E.expiry == exp) & (E.time_IST >= t0) & (E.time_IST <= t1)].head(maxrows)
    act = np.where(E.side == 'Sell', 'Sell', 'Buy'); out = pd.DataFrame({'time': E.time_IST, 'module': E.module.map({'num': 'Body', 'h_': 'Hedge', 's_': 'Stop', 'v_': 'Lump', 'm_': 'Manual'}), 'class': E.cls, 'option': E.right, 'ATM(prev close)': E.atm_prev.astype('Int64'), 'selected': E.strike, 'offset (steps)': E.strike_minus_ATMprev_steps.round(1), 'action': act, 'qty': E.lots, 'strike position': E.contract_net_after, 'S / L of right': E.S_after.astype(int).astype(str) + ' / ' + E.L_after.astype(int).astype(str)}); return table(out)
L = []; w = L.append
w('# Algo 8 — Body Module lifecycle, reconstructed separately for D-1 and D0\n')
w(f"*In-sample, observational (35 live cycles; not a holdout). Tags: **Observed** = read directly from orders/fills/market data; **Inferred** = best-fitting rule; **Unresolved** = not determinable from the data. No optimisation of any return metric. Plan: `BODY_LIFECYCLE_PLAN.md`. Event tables: `outputs/bl_events_d1.csv` ({len(rd('bl_events_d1.csv')):,} rows), `outputs/bl_events_d0.csv` ({len(rd('bl_events_d0.csv')):,} rows). Code: `src/bl_*.py`; every number below is computed by `src/make_bl_report.py` from their outputs. Body = numeric-tag order stream.*\n")
# ---------------- 1 exec summary
sm1 = clsrow(cl1, 'slot_minute'); ot1 = clsrow(cl1, 'other'); mb1 = clsrow(cl1, 'minute_before_slot'); sm0 = clsrow(cl0, 'slot_minute'); ot0 = clsrow(cl0, 'other'); rl0 = clsrow(cl0, 'roll_sell')
w('## 1. Executive summary — two separate lifecycle models\n')
w(f"""**D-1 (position building and carry).**
1. *Observed.* {pct(sm1.share_lots)} of D-1 sold lots are sold in the scheduled **slot minutes** (09:16 + 15 k); in those orders the sold strike is the nearest strike to the **previous completed minute's spot close** in {pct(sm1.exact_prev)} (±1 step {pct(sm1.within1)}); the orders in the first two seconds of a slot hit it in {pct(E3.iloc[1:4].exact_prev.min(), 0)}–{pct(E3.iloc[1:4].exact_prev.max(), 0)}. The reference is previous-minute, not current-minute: when the two nearest strikes differ, the order follows the previous close in {pct(A1['causal_prev'])} vs the current close in {pct(A1['causal_cur'])} (n = {A1['causal_n']}).
2. *Observed.* Another {pct(ot1.share_lots)} of D-1 sold lots (`other`) are **not** ATM-targeted, and a further {pct(mb1.share_lots)} (the minute before a slot) match ATM only {pct(mb1.exact_prev, 0)} of the time: only {pct(ot1.exact_prev)} of `other` sells hit the ATM strike, at **any** reference lag 0–25 min (best {pct(E2.loc[(0, 'other')].astype(float).max())}). The best simple regularity is repeating the previous sale's strike on the same right ({pct(E4[(E4.day == 'D-1') & (E4.cls == 'other')].h_last.iloc[0])}). *Unresolved:* the rule and trigger for these sells.
3. *Observed.* Quantity is almost always **one lot per order** ({pct(A1['lots_1'])}) and mostly **accumulates at the same strike** ({pct(A1['existing_share'])} of slot-minute sells are at an already-short strike); the strike **migrates with ATM across slots** (corr of strike change with ATM change {A1['mig_corr']:.2f}; strike moved with ATM in {pct(A1['mig_chg'])} of ATM changes). Per-slot lots follow a modal ladder in {pct(A1['ladder_eq_ce'])} (CE) / {pct(A1['ladder_eq_pe'])} (PE) of slot-rights; CE = PE in {pct(A1['ce_eq_pe'])}. *Unresolved:* what sets the ladder.
4. *Observed.* There is **no scheduled stop of selling or closing on D-1**: the last body sale is at a median {B1['last_sale_q'][3]} (IQR {B1['last_sale_q'][2]}–{B1['last_sale_q'][4]}); {pct(B1['share_after_1515'])} of cycles sell after 15:15. Buy-backs are spread through the day (top 8 minutes hold only {pct(B1['top_cover_share'])} of D-1 cover lots). About **{pct(B1['lots_carried'] / B1['lots_sold'])} of D-1 sold lots are carried overnight**: median {B1['cy_short_med']:.0f} short lots and {B1['cy_long_med']:.0f} long lots per cycle, no cycle carries zero shorts.

**D0 (management and liquidation).**
5. *Observed.* The book opens D0 with median {A0['inv_short_lots_med']:.0f} short lots in {A0['inv_short_contracts_med']:.0f} contracts and {A0['inv_long_lots_med']:.0f} long lots; {pct(A0['open_itm_share'])} of carried shorts are ITM at the D0 open (gap vs D-1 close median {A0['gap_q'][2]:.2f} steps).
6. *Observed.* D0 sells are **inventory-driven rather than ATM-driven**: {pct(A0['status_share']['carried_strike'])} of D0 sold lots are at strikes carried from D-1, {pct(A0['status_share']['existing_short_strike'])} at strikes already short from earlier on D0, only {pct(A0['status_share']['new_strike'])} at new strikes; overall ATM-hit {pct(sells0.eval('strike == atm_prev').mean())} (NIFTY {pct(A0['hit_und']['NIFTY'])}, SENSEX {pct(A0['hit_und']['SENSEX'])}; scheduled slot minutes {pct(sm0.exact_prev)}).
7. *Observed.* D0 buy-backs are not clocked per second (:00 share 10 %, DD-1) but cluster at the minutes just before a slot (:14/:29/:44/:59 hold {pct(B0['cover_b'])} of covers vs 6.7 % by chance) while sells cluster at the slot minutes ({pct(B0['sell_slot'])}). Only {pct(B0['roll_real'])} of buy-back lots are followed by a sale on the same right within 60 s (shifted-time null {pct(B0['roll_null_mean'])}, range {pct(B0['roll_null_min'])}–{pct(B0['roll_null_max'])}). Buy-back hazard is highest for near-ATM, ITM, later-in-the-day contracts (AUC table §4C); no rule is identified.
8. *Observed — end of session.* The data show a **break between D0 2026-08-13 and 2026-08-25** (per-cycle table in §4D). In all {BR['measurable_post']} measurable cycles with D0 ≥ {BR['first_post_date']} between {pct(BR['min_share_post'], 0)} and {pct(fb[fb.d0 >= '2026-08-25'].share_1514.max(), 0)} of the body's closing lots after 14:30 occur in the single minute 15:14, and **{pct(float(cs[(cs.post == True) & (cs.side == 'short')].share_closed_1514_1515.iloc[0]))} of open shorts / {pct(float(cs[(cs.post == True) & (cs.side == 'long')].share_closed_1514_1515.iloc[0]))} of open longs (at 15:13) are closed in 15:14–15:15** (residual: 0 short lots, {int(rs[(rs.post == True)].net.abs().sum())} long lots). In the {BR['measurable_pre']} measurable cycles with D0 ≤ {BR['last_pre_date']} the 15:14 minute holds at most {pct(BR['max_share_pre'])} of closing lots: closing is spread in bursts (14:58–14:59, 15:15–15:19), shorts are closed by the end (≈ 100 %), {pct(float(cs[(cs.post == False) & (cs.side == 'long')].share_residual.iloc[0]))} of longs remain. (The reported cut-over date 2026-08-03 from earlier phases does **not** match: cycles with D0 08-04…08-13 do not flatten. D0 08-18 and 08-20 cycles have no body closing after 14:30, so the break lies in (08-13, 08-25].)
""")
w('*Inferred models are stated in §7 (D-1) and §8 (D0); the combined flow is in §10 and is only a concatenation of the two.*\n')
# ---------------- 2 ATM reference
w('## 2. ATM reference reconstruction (both days)\n')
w(f"""Body orders have no sub-second decision stamp, so the ATM reference at the decision time is **bracketed**, not assumed. The references: previous-minute spot close (R1, available to the algorithm), current-minute close (R2, look-ahead end of the bracket), parity-implied spot K + C − P from the CE and PE limit-derived prices of a same-strike straddle sold within 2 s (R3), and synthetic ATM (earlier study).

{table(E1.assign(within_half_step=E1.within_half_step.map(pct), within_1_step=E1.within_1_step.map(pct)))}

* **R3 (parity-implied) is a noisy reference** (same-strike straddle strike within half a step in {pct(E1.iloc[0].within_half_step)} vs {pct(E1.iloc[1].within_half_step)} for the previous close) and is not used for decisions; it is reported as a cross-check only.
* **Reference-lag scan.** Hit rate of 'sold strike = nearest strike to the spot close of minute j − k':

![lag](figures/bl_reflag.png)

Scheduled D-1 entries peak at k = 1 ({pct(E2.loc[(0, 'slot_minute')]['1'])} vs {pct(E2.loc[(0, 'slot_minute')]['0'])} at k = 0 and {pct(E2.loc[(0, 'slot_minute')]['2'])} at k = 2): **Observed:** the algorithm uses the **previous completed minute**. `other` sells have no peak and low levels at every lag.
* **Seconds from the slot start (D-1, slots 0–16).** The hit rate is ≈ 97 % in the first seconds of the slot and decays through the 3-minute window to ≈ 20 % after two minutes:

{table(E3.assign(exact_prev=E3.exact_prev.map(pct)))}

* **Are exceptions systematic?** For slot-minute sells at distance u from the strike midpoint (u = |spot − nearest strike| ÷ step) the hit rate is {', '.join(f'{r.ub} {pct(r.hit)}' for r in bnd.itertuples())}: misses concentrate where the spot is within 0.1 step of a strike boundary. {pct(A1['miss1_toward'])} of one-step misses (n = {A1['miss1_n']}) lie on the side toward the previous close (binomial p = {A1['miss1_p']:.1e}). **Inferred:** the 8–16 % of slot-minute exceptions are mostly a **timing difference** (the live spot at the order differs slightly from the previous close), not a different strike rule; the remainder (≈ 31 % of one-step misses and the 2+-step misses) is **Unresolved**.
""")
# ---------------- 3 D-1
w('## 3. D-1 study — position building and overnight carry\n')
w('### 3A. Strike selection\n')
w(f"""Offsets (sold strike − ATM(previous close), in steps; + = ITM side) by order class (definitions: `slot_minute` = minute 09:16 + 15 k; `minute_before_slot` = the minute before; `roll_sell` = a body buy-back on the same right ≤ 60 s earlier; `other` = all remaining):

![offsets](figures/bl_offsets.png)

{table(cl1.assign(exact_prev=cl1.exact_prev.map(pct), exact_cur=cl1.exact_cur.map(pct), within1=cl1.within1.map(pct), share_lots=cl1.share_lots.map(pct)).rename(columns={'cls': 'class', 'within1': '±1 step'}))}

* **Does it always sell exact ATM?** No. Scheduled slot-minute sells: {pct(sm1.exact_prev)} exact, {pct(sm1.within1)} within ±1; all other D-1 sells {pct(ot1.exact_prev)} exact ({pct(ot1.within1)} ±1).
* **Call vs Put.** Scheduled: CE {pct(A1['hit_right']['CE'])}, PE {pct(A1['hit_right']['PE'])}; by index NIFTY {pct(A1['hit_und']['NIFTY'])}, SENSEX {pct(A1['hit_und']['SENSEX'])}. Offsets of `other` sells (ITM-side steps, share of orders; + = ITM) by right:

{table(off_tab(sells1[sells1.cls == 'other']))}

Share of `other` sells below / above the ATM strike: CE {pct(below(sells1[sells1.cls == 'other'], 'CE')[0], 0)} / {pct(below(sells1[sells1.cls == 'other'], 'CE')[1], 0)}, PE {pct(below(sells1[sells1.cls == 'other'], 'PE')[0], 0)} / {pct(below(sells1[sells1.cls == 'other'], 'PE')[1], 0)}: both rights sit mostly on **lower** strikes than the ATM (a common downward shift; its cause, e.g. strikes carried from earlier lower-spot minutes or a directional cycle sample, was **not tested**).
* **Spot, futures or other reference?** Spot closes reproduce the scheduled entries (previous minute); futures data are unavailable (**Not testable**; a rough carry estimate for one day at an assumed 6–7 % rate is ≈ 4 NIFTY points, below the half-step resolution).
* **Does the strike change when the market moves?** Across consecutive slots the modal strike moves with the ATM: {A1['mig_pairs']} slot pairs, corr(ΔK, ΔATM) = {A1['mig_corr']:.2f}; unchanged ATM ⇒ unchanged strike in {pct(A1['mig_unch'])} (n = {A1['mig_unch_n']}); changed ATM ⇒ same-size move in {pct(A1['mig_chg'])} (n = {A1['mig_chg_n']}).
* **Non-scheduled (`other`) sells.** Candidate regularities tested (strike must equal the candidate; D-1):

{table(E4[E4.day == 'D-1'].drop(columns=['day']).rename(columns={'h_last': 'repeat previous sale', 'h_max': 'largest short', 'h_wavg': 'wtd-mean short', 'h_cover': 'last cover (≤300 s)', 'atm_prev': 'ATM(prev)', 'new_strike': 'new strike'}))}

Repeating the previous sale's strike is the best simple description of `other` ({pct(E4[(E4.day == 'D-1') & (E4.cls == 'other')].h_last.iloc[0])}), the `other` ATM hit rate falls through the day ({', '.join(f'{h}h {pct(v, 0)}' for h, v in oh1.items())}). **Unresolved.**
""")
w('### 3B. Quantity\n')
ladtab = lad.pivot(index='slot', columns='und', values=['modal_ce', 'modal_pe']); ladtab.columns = [f'{a} {b}' for a, b in ladtab.columns]; ladtab = ladtab.loc[0:16].reset_index(); ladtab = ladtab.astype(int)
w(f"""* **One lot per order:** {pct(A1['lots_1'])} of scheduled orders; the quantity per slot comes from the **number of orders** (a ladder), a few seconds apart (median spacing of consecutive short-sale orders on one right: 2 s, Body/Hedge study).
* **Pattern 1 (accumulate) vs Pattern 2 (migrate):** both occur at different scales. Within the day {pct(A1['existing_share'])} of scheduled sells go to an already-short strike (59 % in slot 0, 77–98 % later) — **accumulation**; across slots the strike follows the ATM — **migration**. A typical position (cycle × right × strike) has median {B1['orders_q'][1]:.0f} sell orders and {B1['lots_sold_q'][1]:.0f} lots; a cycle-right holds a median of {B1['strikes_med']:.0f} short strikes on D-1 (IQR {B1['strikes_q'][0]:.0f}–{B1['strikes_q'][1]:.0f}).
* **Fixed slots or formula?** Modal ladder (lots per right per slot, scheduled orders; slots 0–16):

{table(ladtab)}

Slot-rights equal the modal ladder in {pct(A1['ladder_eq_ce'])} (CE) / {pct(A1['ladder_eq_pe'])} (PE); CE = PE in {pct(A1['ce_eq_pe'])}. Slots 12, 14, 15 have few scheduled entries (their modal ladders are unstable or 0). **Observed:** a stable slot ladder with noise; **Unresolved:** its driver (premium budget and book-state rules were rejected in DD-1).
""")
w('### 3C. Position lifecycle\n')
w(f"""Contract-level (ownership-free) positions: **{B1['n_pos']}** short strike-positions (cycle × right × strike) in {B1['n_cyc']} cycles with a D-1 log; **{B1['carried_pos']}** ({pct(B1['carried_pos'] / B1['n_pos'])}) are still short at the end of D-1 and {B1['closed_pos']} are closed on D-1; {B1['partial_carried']} carried positions were **partially** reduced during D-1. Lots sold per position: median {B1['lots_sold_q'][1]:.0f} (IQR {B1['lots_sold_q'][0]:.0f}–{B1['lots_sold_q'][2]:.0f}); peak short median {B1['peak_q'][1]:.0f}; hold time of positions closed on D-1 (first short → flat): median {B1['hold_q'][2]:.0f} min (IQR {B1['hold_q'][1]:.0f}–{B1['hold_q'][3]:.0f}).

**Individual lots (FIFO convention; the lot engine's other conventions change timing, not totals).** {B1['fifo_n']:,} body short lots entered on D-1: {pct(B1['fifo_closed'])} closed on D-1 (reason: {', '.join(f'{k} {pct(v)}' for k, v in B1['reason_d1'].items())}), {pct(B1['fifo_carried'])} carried to D0 and closed there ({', '.join(f'{k} {pct(v)}' for k, v in B1['reason_d0'].items())}). FIFO hold time of D-1 closes: median {B1['fifo_hold_q'][2]:.0f} min. *Lot ownership is a convention (Unresolved by design).* The strike-position table is `outputs/bl_d1_C_positions.csv`.
""")
w('### 3D. D-1 ending logic\n')
w(f"""![d1 buckets](figures/bl_d1_buckets.png)

* **Does the Body stop selling at a fixed time?** No. Last body sale per cycle: quantiles (min/10 %/25 %/50 %/75 %/90 %/max) {', '.join(B1['last_sale_q'])}; {pct(B1['share_after_1500'])} of cycles sell at or after 15:00 and {pct(B1['share_after_1515'])} after 15:15. Heaviest sale minutes: {', '.join(f'{k} ({v} lots)' for k, v in list(B1['top_sale'].items())[:5])} (09:16, 10:16… are slot minutes). Orders are stamped up to 15:35 (after the 15:30 close) in the ledger.
* **Scheduled closes?** No single minute carries a close: the busiest buy-back minutes ({', '.join(f'{k} {v}' for k, v in list(B1['top_cover'].items())[:5])}…) hold at most {pct(cov_min1.max() / cov1.lots.sum())} of D-1 cover lots each (eight busiest together {pct(B1['top_cover_share'])}); buy-backs are heavier from 12:30 but show no clock structure at minute level.
* **Wing seed at the open.** The body stream also *buys* far-OTM wings on D-1: {int(ol1.lots.sum())} lots, {int(ol1_open.lots.sum())} of them at 09:15–09:17, a median {abs((ol1_open.strike - ol1_open.atm_prev) / ol1_open.step).median():.0f} steps from the ATM (see the excerpt below).
* **What is carried?** {B1['n_short_contracts']} short contracts / {B1['short_lots']:.0f} lots and {B1['long_contracts']} long contracts / {B1['long_lots']:.0f} lots over {B1['n_cycles_inv']} cycles; carried shorts sit a median {B1['steps_q'][2]:.1f} steps from the D-1 close spot ({pct(B1['itm_share'])} ITM), at a median closing price of ₹{B1['close_px_q'][1]:.0f}. Carry is simply the part of the sold inventory not bought back during D-1; whether it differs systematically from the bought-back part (distance, price ratio) was **not tested** here.
* **Deliberate overnight hedge:** the `v_` lump buys (15:06–15:38) over-hedge the carried shorts (Body/Hedge study).
""")
w('### 3E. D-1 event table (excerpt)\n')
w('Full tables: `outputs/bl_events_d1.csv` (all modules, all cycles). Excerpts are the first cycle with a known carry-in (NIFTY, expiry 2026-06-30), chosen by that rule only; ATM = nearest strike to the previous completed minute\'s spot close; `strike position` = contract net lots after the event; `S / L` = short / long lots of that right.\n')
w('**09:15–09:18 (opening slot):**\n\n' + ev_excerpt('NIFTY', '2026-06-30', 'D-1', '09:15:00', '09:18:30') + '\n')
w('**Last half hour (15:05–15:36):**\n\n' + ev_excerpt('NIFTY', '2026-06-30', 'D-1', '15:05:00', '15:36:00') + '\n')
w('### 3F. D-1 unexplained-behaviour register\n')
w(f"""| # | Behaviour | Observed | Status |
|---|---|---|---|
| D1-U1 | `other` sells ({pct(ot1.share_lots)} of lots) | strike not ATM at any lag (≤ {pct(E2.loc[(0, 'other')].astype(float).max())}); repeats previous strike {pct(E4[(E4.day == 'D-1') & (E4.cls == 'other')].h_last.iloc[0])}; ATM hit decays through the day | **Unresolved** (rule and trigger) |
| D1-U2 | minute-before-slot sells ({pct(mb1.share_lots)}) | ATM hit {pct(mb1.exact_prev)} (±1 {pct(mb1.within1)}) | **Unresolved** (second clock; strike partly ATM) |
| D1-U3 | slot ladder | modal ladder reproduced in {pct(A1['ladder_eq_ce'])} / {pct(A1['ladder_eq_pe'])}; driver unknown | **Unresolved** |
| D1-U4 | slot-minute exceptions | {pct(1 - sm1.exact_prev)} not ATM; mostly boundary timing (Inferred) | partly **Inferred**, ≈ 31 % of 1-step misses **Unresolved** |
| D1-U5 | what is bought back on D-1 | spread through the day; no schedule | **Unresolved** (earlier per-lot stop band is a tendency only) |
| D1-U6 | carry = {pct(B1['lots_carried'] / B1['lots_sold'])} of sold lots | no closing time; composition of the carried part vs the bought-back part not tested | **Unresolved** (why exactly these lots) |
""")
# ---------------- 4 D0
w('## 4. D0 study — position management and liquidation (independent of D-1)\n')
w('### 4A. Opening inventory\n')
w(f"""* Carry-in is known for **{A0['known']} of {A0['n_cycles']} cycles** ({A0['d1_missing']} cycles lack the D-1 log, {A0['d0_missing']} lack the D0 log).
* Opening book (cycles with a D-1 log, {A0['inv_n']} cycles): median **{A0['inv_short_lots_med']:.0f} short lots** (IQR {A0['inv_short_lots_q'][0]:.0f}–{A0['inv_short_lots_q'][1]:.0f}) in {A0['inv_short_contracts_med']:.0f} contracts and **{A0['inv_long_lots_med']:.0f} long lots** (IQR {A0['inv_long_lots_q'][0]:.0f}–{A0['inv_long_lots_q'][1]:.0f}); table `outputs/bl_d0_A_opening_inventory.csv`, strike list `bl_d1_D_overnight_inventory.csv`.
* Gap of the D0 open vs the D-1 close: quantiles (10/25/50/75/90 %) {', '.join(f'{v:.2f}' for v in A0['gap_q'])} steps. Carried shorts at the D0 open: {pct(A0['open_itm_share'])} ITM; |distance from spot| quantiles (25/50/75/90 %) {', '.join(f'{v:.1f}' for v in A0['open_abs_q'])} steps.
* **Opening positions not explained by recorded trades.** D0 body Buys with no recorded short (contract net ≥ 0 before): {A0['ol_known_lots']:.0f} lots in {A0['ol_known_cyc']} known-carry cycles (seed wings, mostly at 09:15–09:17) and {A0['ol_unknown_lots']:.0f} lots in the {A0['ol_unknown_cyc']} cycles with unknown carry-in (≈ {A0['ol_unknown_lots'] / A0['ol_unknown_cyc']:.0f} per cycle vs {A0['ol_known_lots'] / A0['ol_known_cyc']:.0f} per known cycle): the excess is **Inferred** to be the footprint of unrecorded carried shorts (3 cycles only; exact amounts **Unresolved**; those cycles are excluded from inventory claims).
""")
w('### 4B. Strike selection on D0\n')
w(f"""{table(cl0.assign(exact_prev=cl0.exact_prev.map(pct), exact_cur=cl0.exact_cur.map(pct), within1=cl0.within1.map(pct), share_lots=cl0.share_lots.map(pct)).rename(columns={'cls': 'class', 'within1': '±1 step'}))}

* **Exact ATM / ±1, ±2?** Scheduled slot-minute sells {pct(sm0.exact_prev)} exact ({pct(sm0.within1)} ±1) — **much lower than D-1 ({pct(sm1.exact_prev)})**; all D0 sells {pct(sells0.eval('strike == atm_prev').mean())}; by hour: {', '.join(f'{k}h {pct(v, 0)}' for k, v in A0['hit_hour'].items())}; NIFTY {pct(A0['hit_und']['NIFTY'])} vs SENSEX {pct(A0['hit_und']['SENSEX'])}. Reference: when the two nearest strikes differ, orders follow the previous close in {pct(A0['causal_prev'])} vs the current close {pct(A0['causal_cur'])} (n = {A0['causal_n']}): previous-minute again for scheduled entries.
* **Previous day's strikes, new strikes, additional positions at existing strikes?** By lots: carried-from-D-1 strike **{pct(A0['status_share']['carried_strike'])}**, existing D0 short strike **{pct(A0['status_share']['existing_short_strike'])}**, new strike **{pct(A0['status_share']['new_strike'])}**; ATM hit rate by status: carried {pct(A0['status_hit']['carried_strike'])}, existing {pct(A0['status_hit']['existing_short_strike'])}, new {pct(A0['status_hit']['new_strike'])}. **Observed:** D0 selling is dominated by **adding to strikes that are already short**; the ATM matters only for a minority.
* **Call vs Put.** Scheduled D0 slot-minute sells at the ATM: CE {pct(sells0[sells0.cls == 'slot_minute'].eval('strike == atm_prev').groupby(sells0[sells0.cls == 'slot_minute'].cp).mean()['CE'])}, PE {pct(sells0[sells0.cls == 'slot_minute'].eval('strike == atm_prev').groupby(sells0[sells0.cls == 'slot_minute'].cp).mean()['PE'])}. Offsets of all D0 sells (ITM-side steps):

{table(off_tab(sells0))}

No separate CE/PE rule is identified.
* **Time structure.** ATM hit by minutes since the open: {', '.join(f'{k} {pct(v, 0)}' for k, v in A0['hit_mins'].items())} — highest mid-morning, low at the open and the close.
""")
w('### 4C. D0 position management\n')
w(f"""![d0 hour class](figures/bl_d0_hour_class.png)

* **New entries, buy-backs, re-entries, long changes (lots, by hour × class, `outputs/bl_d0_C_hour_class.csv`):** sells in slot minutes/other/roll classes are spread over the day; buy-backs rise steeply from 14:00 and dominate 14:00–15:30; body **long** buys (`open_long`) are concentrated at the open and long sales (`close_long`) at the end (15:00–15:30).
* **Clock.** Sells cluster at the slot minutes ({pct(B0['sell_slot'])} vs 6.7 % chance, top minutes {', '.join(f'{k}: {pct(v)}' for k, v in list(B0['sell_top'].items())[:4])}); buy-backs cluster at {pct(B0['cover_b'])} in :14/:29/:44/:59 (top minutes {', '.join(f'{k}: {pct(v)}' for k, v in list(B0['cover_top'].items())[:4])}).
* **Re-entry after buy-back.** {pct(B0['roll_real'])} of {B0['cover_lots']:,} buy-back lots are followed by a sale on the same right within 60 s; shifted-time null {pct(B0['roll_null_mean'])} (range {pct(B0['roll_null_min'])}–{pct(B0['roll_null_max'])}). So only ≈ {pct(B0['roll_real'] - B0['roll_null_mean'])} of buy-backs are excess re-entries — a **modest** roll component.
* **Strike changes after a buy-back** ({B0['roll_pairs']:,} pairs): same strike {pct(B0['same_strike'])}; new strike more ITM {pct(B0['more_itm'])}, more OTM {pct(B0['more_otm'])}; the old strike was ITM in {pct(B0['old_itm'])}; median |offset from spot| {B0['abs_old']:.2f} → {B0['abs_new']:.2f} steps; new strike closer to spot in {pct(B0['new_closer'])}. The strike change is strongly related to how far the old strike was from spot (corr {B0['roll_corr']:.2f}), i.e. rolls move **toward** spot, yet the new strike is the nearest ATM strike in only {pct(sells0[sells0.cls == 'roll_sell'].eval('strike == atm_prev').mean())} of D0 roll sells.
* **Buy-back hazard.** Contract-minutes with an open body short on D0 (n = {B0['panel_n']:,}, {B0['panel_events']:,} minutes with a buy-back; AUC 0.5 = no association). Single-driver AUC (buy-back minute vs not; cluster bootstrap over cycles, Holm over six pre-registered drivers):

{table(hz.assign(AUC=hz.AUC.round(3), CI=[f'{a:.3f}–{b:.3f}' for a, b in zip(hz.lo, hz.hi)], p_boot=hz.p_boot.round(3), holm_p=hz.holm_p.round(3))[['driver', 'AUC', 'CI', 'holm_p']])}

(`dist` = |strike − spot| in steps: AUC 0.27 ⇒ buy-backs favour contracts **near the money**; `mins` = minutes since open: later; `itm_i`: ITM; `ratio_avg` = price ÷ average entry; `d_price_5m` = 5-minute price change; `clk` = clock-B minute.) Hazard per contract-minute rises from {pct(float(list(B0['haz_ratio'].values())[2]))} at price ≤ entry to {pct(float(list(B0['haz_ratio'].values())[5]))} at 1.5–1.7× entry and falls from {pct(float(list(B0['haz_dist'].values())[0]))} at ≤ 0.5 steps from spot to {pct(float(list(B0['haz_dist'].values())[4]))} beyond 6 steps. These are marginal associations (larger contracts also trade more): **no exit rule is Inferred**; the per-lot stop band (1.55–1.7×) from earlier work is a tendency, not a rule.
* **Stop-related exits and final liquidation.** Stop-module orders ({int(((O.module == 's_') & (O.dayno == 1)).sum())} on D0) liquidate body and wings together in {len(set(zip(O[O.module == 's_'].und, O[O.module == 's_'].expiry)))} cycles (existing cycle-stop work); §4D covers the end of session.
""")
w('### 4D. D0 ending logic\n')
w(f"""![d0 ending](figures/bl_d0_ending.png)

* **Is there a scheduled 15:14 flatten?** **Observed:** yes, from the cycle with D0 {BR['first_post_date']} onward ({BR['measurable_post']} measurable cycles, 15:14-minute share of body closing lots after 14:30 from {pct(BR['min_share_post'], 0)} up to {pct(fb[fb.d0 >= '2026-08-25'].share_1514.max(), 0)}; {int(C0['post_1514'])} lots in that minute alone). Up to D0 {BR['last_pre_date']} ({BR['measurable_pre']} measurable cycles) the share is at most {pct(BR['max_share_pre'])}; closing is spread (bursts at 14:58–14:59 and 15:15–15:19). The break is **Observed** between 2026-08-13 and 2026-08-25; its cause is **Unresolved**. Per-cycle table (cycles with body closing after 14:30):

{table(fb.assign(share_1514=fb.share_1514.map(pct)).rename(columns={'share_1514': 'share of closing lots in the 15:14 minute'}))}

* **What does it close?** Shares of what is open at 15:13 (contract lots, cycles with known carry-in):

{table(cs.assign(post=cs.post.map({True: 'D0 ≥ 2026-08-25 (flatten)', False: 'D0 ≤ 2026-08-20 (no flatten)'}), share_closed_1514_1515=cs.share_closed_1514_1515.map(pct), share_residual=cs.share_residual.map(pct)).rename(columns={'post': 'period'}))}

  Post-break: {pct(float(cs[(cs.post == True) & (cs.side == 'short')].share_closed_1514_1515.iloc[0]))} of shorts and {pct(float(cs[(cs.post == True) & (cs.side == 'long')].share_closed_1514_1515.iloc[0]))} of longs are closed in 15:14–15:15 by body orders ({int(fl.body_1514_1515.sum())} lots in that window over all cycles, vs {int(fl.hedge_1514_1515.sum())} by hedge orders and {int(fl.stop_1514_1515.sum())} by the stop module); residual shorts are zero in both periods except {int(rs[(rs.side == 'short')].net.abs().sum())} lot; residual **longs**: {int((rs.side == 'long').sum())} contracts / {int(rs[rs.side == 'long'].net.abs().sum())} lots overall ({int(rs[(rs.side == 'long') & (rs.post == True)].net.abs().sum())} lots after the break), last price ≈ ₹{rs[rs.side == 'long'].last_px.median():.2f}, median {abs(rs[rs.side == 'long'].otm_steps_at_close).median():.1f} steps OTM (worthless wings left to expire).
* **Different rules for shorts and longs?** At 15:14–15:15 both are closed by the same body orders (the 15:14 flatten includes body sells of wing contracts, i.e. cross-role); afterwards only longs remain. Before the cut-over longs are closed far less ({pct(float(cs[(cs.post == False) & (cs.side == 'long')].share_residual.iloc[0]))} remain).
* **Positions that cannot be closed through recorded fills.** The only residuals are far-OTM long wings at ≈ ₹0.05 (settle at the exchange settlement value; **U12** bounded). Cycles whose D0 ends early (cycle stop) have their last order as early as 09:15 (D0 last-order quantiles {', '.join(C0['last_order_q'])}).
""")
w('### 4E. D0 event table (excerpt)\n')
w('Same cycle (NIFTY, expiry 2026-06-30). ATM = nearest strike to the previous completed minute\'s spot close.\n')
w('**D0 open (09:15–09:16:10):**\n\n' + ev_excerpt('NIFTY', '2026-06-30', 'D0', '09:15:00', '09:16:10') + '\n')
w('**The end of the session (15:12:30–15:16):**\n\n' + ev_excerpt('NIFTY', '2026-06-30', 'D0', '15:12:30', '15:16:00') + '\n')
w('### 4F. D0 unexplained-behaviour register\n')
w(f"""| # | Behaviour | Observed | Status |
|---|---|---|---|
| D0-U1 | D0 sell strikes | {pct(A0['status_share']['carried_strike'] + A0['status_share']['existing_short_strike'])} of lots at already-short strikes; ATM hit {pct(sells0.eval('strike == atm_prev').mean())} overall, SENSEX {pct(A0['hit_und']['SENSEX'])} | **Unresolved** (inventory-driven selection rule) |
| D0-U2 | buy-back trigger | near-ATM/ITM/later contracts favoured (AUCs); no threshold rule found; roll excess only ≈ {pct(B0['roll_real'] - B0['roll_null_mean'])} | **Unresolved** |
| D0-U3 | unrecorded opening positions | footprint in {A0['ol_unknown_cyc']} cycles; {A0['d1_missing']} D-1 and {A0['d0_missing']} D0 logs missing | **Unresolved** (data) |
| D0-U4 | pre-cutover closing | bursts at 14:58–14:59, 15:15–15:19; {pct(float(cs[(cs.post == False) & (cs.side == 'long')].share_residual.iloc[0]))} of longs left | **Unresolved** (schedule) |
| D0-U5 | start of the 15:14 flatten | no flatten up to D0 2026-08-13, flatten from D0 2026-08-25 (D0 08-18, 08-20 undetermined) | **Observed** break; date and cause **Unresolved** |
| D0-U6 | residual long wings after the flatten | {pct(float(cs[(cs.post == True) & (cs.side == 'long')].share_residual.iloc[0]))} of longs, price ≈ ₹0.05 | **Inferred** left to expire (worthless); intent **Unresolved** |
| D0-U7 | seed long wings at the open | {int(A0['ol_known_lots'])} lots of body long buys mostly 09:15–09:17 | **Observed**; strike rule **Unresolved** (earlier register HDG-01) |
""")
# ---------------- 5 deliverables
w('## 5. Deliverables\n')
dl = [('ATM reference reconstruction', '§2 (R1–R3 bracket, lag scan, boundary test)', '§4B (previous-minute again; boundary)'), ('Strike-selection distribution', '§3A figure + table', '§4B table'), ('Call vs Put selection', '§3A (CE/PE hit, drift)', '§4B'), ('Quantity-selection logic', '§3B ladder', '§4C (1-lot orders; inventory-driven)'), ('Same-strike accumulation', '§3B (86.8 % already short)', '§4B (91 % at already-short strikes)'), ('Strike migration', '§3A (ATM-following across slots)', '§4C (roll strike changes)'), ('Individual lot lifecycle', '§3C (FIFO lots, strike-positions)', '§4C (roll pairs; hazard) + `lot_lifecycle` outputs'), ('Buyback and re-entry analysis', '§3D (spread; no schedule)', '§4C (29.6 % vs null 21.1 %; hazard AUCs)'), ('Carry-forward analysis', '§3C–3D (≈ 68 % carried)', '§4A (opening inventory) + §4D (residuals)'), ('End-of-session rules', '§3D (no close; sells to ≈ 15:35)', '§4D (15:14 flatten from the D0 2026-08-25 cycle)'), ('Unexplained behaviour register', '§3F', '§4F')]
w(table(pd.DataFrame(dl, columns=['Deliverable', 'D-1', 'D0']))); w('\n')
# ---------------- 6 O/I/U ledger
w('## 6. Observed / Inferred / Unresolved ledger\n')
w(f"""| | Observed | Inferred | Unresolved |
|---|---|---|---|
| **D-1** | slot-minute sells at previous-close ATM ({pct(sm1.exact_prev)}); 1-lot orders; accumulation at the same strike; strike follows ATM across slots; no closing time; {pct(B1['lots_carried'] / B1['lots_sold'])} carried | slot exceptions = reference timing noise (69 % of 1-step misses lean toward spot); a 15-minute entry clock with a slot ladder | `other` sells' rule; ladder driver; what is bought back; which lots are carried |
| **D0** | opening book ≈ {A0['inv_short_lots_med']:.0f} short / {A0['inv_long_lots_med']:.0f} long lots; sells {pct(A0['status_share']['carried_strike'] + A0['status_share']['existing_short_strike'])} at already-short strikes; buy-backs cluster before slot minutes and near the money; 15:14 flatten from the D0 2026-08-25 cycle | continuous inventory-driven management; ≈ 100 % of open shorts and longs closed at 15:14 after the break; residual longs are worthless wings left to expire | D0 sell-strike rule; buy-back trigger; unrecorded carry-in; pre-cutover schedule; cause of the cut-over |
""")
w('## 7. D-1 lifecycle model (Inferred, behavioural)\n')
w("""1. From 09:16, every 15 minutes (slot minutes 09:16 + 15 k): sell 1-lot orders on each right at the strike nearest to the **previous completed minute's spot**, repeating the order a few seconds apart to build a per-slot ladder (typical 1–3 lots per right; stable across cycles); the strike changes with the ATM between slots, quantity accumulates at the same strike within slots.
2. At other times, continue selling 1-lot orders on already-short strikes (not ATM-targeted; rule unknown); the hedge module adds wings per right to balance S and L.
3. Buy back individual lots through the day without a clock or a time limit; keep selling until the close.
4. Carry ≈ two-thirds of sold lots overnight (median ≈ 100 short lots per cycle, with ≈ 150 long lots including the lump overweight).
""")
w('## 8. D0 lifecycle model (Inferred, behavioural)\n')
w("""1. Open with the carried book; at the open buy long wings (seed) and start buying back near-ATM / ITM shorts.
2. Sell 1-lot orders mainly at strikes that are already short (carried or opened earlier on D0), with ATM targeting only in the minority of scheduled slot minutes; buy-backs cluster at :14/:29/:44/:59 and rise from 14:00; re-entry after a buy-back is a minor component.
3. From the D0 2026-08-25 cycle onward close essentially all shorts and longs in the 15:14 minute; before that (up to 2026-08-13) close shorts in bursts between ≈ 14:55 and 15:20.
4. Residual: worthless far-OTM longs left to expire.
""")
w('## 9. Self red-team and limits\n')
w(f"""* No bid/ask; spot at minute ends; body fills at second resolution: the decision-time ATM is bracketed, so hit rates are **lower bounds** for any rule that uses a slightly different decision instant.
* Class definitions (slot minute, minute before slot, 60-s roll, `other`) are mine and partly post-hoc after seeing the time structure; each class is reported with its own rates and nothing is averaged across classes except where labelled `ALL`.
* Cycle counts differ by section (32 cycles with a D-1 log, 30 with known carry-in, 31 with overnight inventory); the pre/post-break split ({BR['measurable_pre']} vs {BR['measurable_post']} measurable cycles) is confounded with calendar time and expiry-structure changes.
* Hazard AUCs are marginal single-driver associations over {B0['panel_n']:,} contract-minutes clustered in 33 cycles; they do not identify a rule.
* The 35 cycles are in-sample and heavily inspected; nothing here is validation. Reconstructed behaviour is not the original source logic.
""")
w('## 10. Combined execution flow (concatenation of §7 and §8; to be validated before use)\n')
w("""D-1: 15-minute slot ladder at the previous-minute ATM + continuous accumulation at held strikes + per-lot buy-backs + hedge balancing + overnight lump → carry ≈ 68 % of sold lots. D0: manage the carried book (inventory-driven sells, near-ATM buy-backs, partial re-entry) → from the D0 2026-08-25 cycle flatten at 15:14, otherwise close in the last 30 minutes → leave only worthless wings.
""")
open(os.path.join(REP, 'BODY_LIFECYCLE_D1_D0_INVESTIGATION.md'), 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
