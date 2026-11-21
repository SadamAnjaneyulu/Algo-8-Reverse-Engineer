"""Builds reports/BODY_SOLO_LATE.md from outputs bl_sl_*, bl_summary_sl1-8.json."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); S = {i: J(f'sl{i}') for i in range(1, 9)}
pct = lambda x, n=0: f'{100 * x:.{n}f}%'; f2 = lambda x: f'{x:.2f}'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
Z = pd.read_csv(f'{OUT}/bl_sl_class.csv'); P = pd.read_csv(f'{OUT}/bl_sl_prem.csv').set_index(['window', 'variable']); B = pd.read_csv(f'{OUT}/bl_sl_blocks.csv'); U = pd.read_csv(f'{OUT}/bl_sl_auc.csv'); R2 = pd.read_csv(f'{OUT}/bl_sl_rule2.csv'); CD = pd.read_csv(f'{OUT}/bl_sl_cond.csv')
lots = int(Z.lots.sum()); cyc = Z.cid.nunique(); pl = Z.prem_newlow15.fillna(False).astype(bool); E = Z.E.astype(bool); cov = S[7]['lot_coverage']
L, I = 'late 15:00-15:29', 'intraday 10:30-14:59'
hz = pd.DataFrame([[n, pct(P.loc[(I, v), 'base_rate']), pct(P.loc[(I, v), 'hazard_if']), pct(P.loc[(I, v), 'recall']), pct(P.loc[(L, v), 'base_rate']), pct(P.loc[(L, v), 'hazard_if']), pct(P.loc[(L, v), 'recall'])] for n, v in [('spot fresh 15-min extreme (same minute)', 'bk15'), ('ITM premium fresh 15-min low (same minute)', 'pl15_itm'), ('premium low **without** spot extreme', 'pl15_itm WITHOUT bk15'), ('either (R3)', 'bk15 OR pl15_itm')]], columns=['condition (on the right)', 'intraday: minutes with it', 'intraday: P(sale)', 'intraday: share of sales', 'late: minutes with it', 'late: P(sale)', 'late: share of sales'])
neither_i, neither_l = P.loc[(I, 'bk15 OR pl15_itm'), 'hazard_not'], P.loc[(L, 'bk15 OR pl15_itm'), 'hazard_not']
bl = B.pivot(index='block', columns='model', values='AUC').round(3).reindex(['market', 'history', 'clock', 'micro', 'volatility', 'inventory', 'greeks', 'flow', 'all']).reset_index(); bl.columns = ['block', 'boosting AUC', 'logistic AUC']
r2 = R2.copy(); r2['rule'] = r2.rule.map({'bk15': 'R1 spot fresh 15-min extreme', 'pl15_itm': 'R2 ITM premium fresh 15-min low', 'R3': 'R3 = R1 or R2', 'bk15_prev': 'R1 on previous minute (causal)', 'pl15_itm_prev': 'R2 on previous minute (causal)', 'R3_prev': 'R3 on previous minute (causal)'}); r2 = r2.round(3)
cd = CD.head(6).round(3)
sp = pd.DataFrame(S[4]['spikes']); sp['bk15_same'] = sp.bk15_same.map(pct)
mm = lambda m: ((Z.j == m) if m < 374 else (Z.j >= 374)); spk = {m: (int(Z.lots[mm(m)].sum()), pct(E[mm(m)].mean()), pct((E | pl)[mm(m)].mean()), pct(Z.bb60[mm(m)].astype(bool).mean())) for m in (345, 368, 374)}
txt = f"""# Algo 8 — after-15:00 solo sells: what drives them

*Investigation; plan `BODY_SOLO_LATE_PLAN.md`, written before the tests. In-sample: D-1 of 32 live cycles. "Late solo" means regular solo lots at or after 15:00: body `open_short` lots that are not part of a scheduled or reactive pair and are within 4 strikes of ATM. That is **{lots} lots, all single-lot orders, in {cyc} cycles**. Deep-OTM batch lots are excluded. Steps 6–8 were added after seeing results and are labelled post-hoc. Figure: `figures/bl_sl_summary.png`.*

## 0. Result

* **The late regime uses the same trigger as the intraday solo drip, with one extra input.** {pct(cov['spot extreme (E)'])} of late solo lots are sold in a minute where the spot makes a fresh 15-minute extreme on the favourable side (CE on a new low, PE on a new high). Adding the sold option's **own premium making a fresh 15-minute low** brings this to **{pct(cov['E or premium low'])}** of late lots (post-hoc). *Observed.*
* **Why it looks like a different regime.** Into the close, time decay and the fall in implied volatility push option premiums to new lows **without** a spot extreme. Late, such a minute is followed by a sale {pct(P.loc[(L, 'pl15_itm WITHOUT bk15'), 'hazard_if'])} of the time. Intraday the figure is {pct(P.loc[(I, 'pl15_itm WITHOUT bk15'), 'hazard_if'])}. Minutes with **neither** condition carry a sale {pct(neither_l, 1)} of the time late, against {pct(neither_i, 1)} intraday. So the late book reacts to the premium falling, not only to the spot. *The data observe this; the mechanism is inferred.*
* **Model.** Among the blocks fitted leave-one-cycle-out, **market variables alone reach AUC {B[(B.block == 'market') & (B.model == 'lr')].AUC.iloc[0]:.2f}**. Adding every other block (clock, history, option volume, volatility, inventory, Greeks, order flow) lifts this only to {B[(B.block == 'all') & (B.model == 'gb')].AUC.iloc[0]:.2f}. Greeks, inventory and order flow are each at chance (about 0.5) when used alone. *Observed.*
* **As a rule** with no fitted parameter, R3 ("spot fresh 15-minute extreme OR premium fresh 15-minute low") gives **F1 {R2.set_index('rule').F1['R3']:.2f}** (precision {R2.set_index('rule').precision['R3']:.2f}, recall {R2.set_index('rule').recall['R3']:.2f}, ±1 minute). This is **below the 0.70 "decoded" bar**. Recall is high, but about half of the qualifying minutes have no sale. Nothing tested separates them well: earlier minutes, higher option volume and a recent sale only reach AUC 0.6. *Unresolved.*
* **Rejected:** overnight delta shaping (H1), financing the wings (H2), CE/PE inventory balancing (H3), and replacing a bought-back leg (H4). *Observed.*

## 1. Description (test 1)
* Late solo lots by minute show three spikes: **15:00 ({spk[345][0]} lots)**, **15:23 ({spk[368][0]})** and **15:29–15:30 ({spk[374][0]})**. Share at a spot extreme: {spk[345][1]} / {spk[368][1]} / {spk[374][1]}. Share at a spot extreme or premium low: {spk[345][2]} / {spk[368][2]} / {spk[374][2]}. Share with a body buy-back within 60 s: {spk[345][3]} / {spk[368][3]} / {spk[374][3]}.
* The 15:00 spike is the drip itself: the first late minute picks up spot extremes. At 15:23 the lots not at a spot extreme ({int(Z.lots[(Z.j == 368) & ~E].sum())}) come from {Z.cid[(Z.j == 368) & ~E].nunique()} cycles; most of these lots ({pct(Z.bb60[(Z.j == 368) & ~E].astype(bool).mean())}) have a body buy-back within 60 s. In those cycles the sold premiums are at fresh lows but the spot is not at an extreme.
* Late solo lots: CE {pct((Z.cp == 'CE').mean())} of orders. The usual strike is 1 strike in the money.

## 2. Same trigger, stronger response late (test 4; premium rows post-hoc)
{table(hz)}
P(sale) is per minute × right. Minutes with neither condition: P(sale) {pct(neither_i, 1)} intraday, {pct(neither_l, 1)} late.

Reading the table:
* Late sales still follow the market signal.
* Late, the response to the **premium** signal is about 5 times stronger.
* Late, the "no signal" sale probability is 10 times higher.

That pattern fits a tracker that watches the sold contract's premium as well as the spot. Into the close the premium decays even when the spot does not move.

Caveats:
* Both conditions use the **same minute's** true one-minute high/low. Inside a minute we cannot tell whether the extreme came before or after the sale (no ticks).
* The causal versions, using the previous minute, give recall {pct(P.loc[(L, 'bk15_prev'), 'recall'])} for the spot extreme and {pct(P.loc[(L, 'pl15_itm_prev'), 'recall'])} for the premium low. So the same-minute alignment matters.
* Only {pct(S[6]['own_fill_at_low_share'])} of late sales are priced within 0.2% of the minute low, so Algo 8's own fills are not what makes the premium lows.

## 3. Block models (test 5): late minute × right panel, 15:00–15:29, {S[3]['n']} cells, {S[3]['pos']} with a sale
{table(bl)}
Strongest single variables (AUC): {', '.join(f"{r.variable} {r.AUC:.2f}" for r in U.head(6).itertuples())}. These are fresh 15- and 5-minute extremes, position in the 60-minute range, the favourable 30-minute move and RSI. All of them are directional.

## 4. Linked to pairs, wings and buy-backs? (tests 2 and 5)
* **Wings follow, they do not lead.** A wing (`h_`) order follows within 10 s after {pct(Z.Wa.astype(bool).mean())} of late solo sales. That is the known deterministic follower, about 4 s after every sell. A wing order *before* the sale is rare and does not separate anything.
* **Buy-backs.** A cross-right body buy-back comes within 10 s of {pct((Z.Bb | Z.Ba).astype(bool).mean())} of late solo lots. Earlier work counted the cross-right pairings: PE covered and CE sold, 231 order rows; CE covered and PE sold, 56; never the same right. Every one of those lots is already explained by a spot extreme or a premium low.
* **Per cycle.** Late solo lots rise with late buy-backs (ρ {S[2]['rho_buyback_lots'][0]:.2f}), wing closes ({S[2]['rho_wing_close_lots'][0]:.2f}), late reactive lots ({S[2]['rho_react_lots_late'][0]:.2f}) and lumps ({S[2]['rho_lump_lots'][0]:.2f}). *Inferred:* that is the common driver, a moving market late in the day, which feeds every module. Inside the minute panel the order-flow block is at chance (AUC {B[(B.block == 'flow') & (B.model == 'lr')].AUC.iloc[0]:.2f}).

## 5. Portfolio hypotheses (H1–H4): rejected
| hypothesis | test | result |
|---|---|---|
| H1 overnight delta shaping | does the sale reduce whole-book |delta| (all modules)? | {pct(S[1]['late']['share_reduce_abs_delta'])} late (intraday {pct(S[1]['intraday']['share_reduce_abs_delta'])}); sale side opposes the book delta {pct(S[1]['late']['share_side_opposes_book_delta'])}; |delta| is not driven toward 0 into 15:30 |
| H2 financing the wings | late solo ₹ vs late long-premium ₹ per cycle | ρ {S[4]['H2']['rho_rs_solo_vs_long'][0]:.2f} (p {S[4]['H2']['rho_rs_solo_vs_long'][1]:.2f}); solo ₹ is a median {S[4]['H2']['median_ratio_solo_to_long']:.1f}× the long ₹, so there is no matching |
| H3 CE/PE inventory target | sale on the lighter side? imbalance shrinks into the close? | lighter side {pct(S[4]['H3']['lot_share_on_lighter_side'])}; imbalance shrinks in {pct(S[4]['H3']['share_cycles_imb_shrinks'])} of cycles; median |imbalance| {S[4]['H3']['abs_imb_1500_median']:.2f} → {S[4]['H3']['abs_imb_1530_median']:.2f} |
| H4 leg replacement | same-right roll after a buy-back? | none; cross-right pairings are all already explained by the extreme/premium-low trigger |
| H6 clock | fixed late times | the spikes at 15:00, 15:23 and 15:29 are explained by the trigger (section 1); clock block AUC {B[(B.block == 'clock') & (B.model == 'gb')].AUC.iloc[0]:.2f} |

## 6. Rules (post-hoc; no fitted parameter; ±1 minute per cycle and right)
{table(r2)}
Within R3-minutes, the variables that best separate sale from no sale (post-hoc):
{table(cd)}

## 7. What this means for the D-1 reconstruction
* The after-15:00 class was scored F1 0 in the combined reconstruction. A single rule, R3, would cover it at about F1 {R2.set_index('rule').F1['R3']:.2f}. That share of lots is small, so the combined D-1 F1 would barely move. The combined numbers in `D1_SELLING_RECONSTRUCTION.md` were **not** changed: R3 is post-hoc and was not pre-registered.
* **Still unknown:** which qualifying minutes get a sale (about half do), and how many lots each burst sells.

## Evidence labels
Observed: sections 1, 2 (tables), 3, 4 (counts), 5. Inferred: the premium decay / vol crush explanation, and the common market driver behind the per-cycle correlations. Unresolved: the selection among qualifying minutes, and burst size. Not testable: order of events inside a minute (no ticks); the algorithm's true internal premium reference.
"""
open(f'{RP}/BODY_SOLO_LATE.md', 'w').write(txt); print('ok', len(txt))
