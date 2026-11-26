"""Builds reports/BODY_CLOSE_LOGIC.md from the computed outputs (every number below is read from outputs/*.csv|json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports')
J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json'))
R1, R2, R2b, R3, R5, R6, R7 = J('close1'), J('close2'), J('close2b'), J('close3'), J('close5'), J('close6'), J('close7')
F = pd.read_csv(f'{OUT}/bl_close_orders_flags.csv'); d1 = F[F.day == 'D-1']; P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); P1 = P[P.day == 'D-1']; A = pd.read_csv(f'{OUT}/bl_close_C_auc.csv'); E = pd.read_csv(f'{OUT}/bl_close_E_auc.csv'); GB = pd.read_csv(f'{OUT}/bl_close_E_gb.csv').set_index('model').LOCO_AUC
L = pd.read_csv(f'{OUT}/bl_close_lots.csv'); S = pd.read_csv(f'{OUT}/bl_close_D_strikes.csv'); D0A = A[A.day == 'D0']
pct = lambda x, n=1: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
bins = [0, .8, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 99]; lab = ['≤0.8', '0.8–1.0', '1.0–1.1', '1.1–1.2', '1.2–1.3', '1.3–1.4', '1.4–1.5', '1.5–1.6', '1.6–1.7', '1.7–1.8', '>1.8']
H = pd.DataFrame({'premium ÷ entry': lab}); hz = {}
for rn, nm in (('r_avg', 'average entry'), ('r_low', 'cheapest open entry'), ('r_fifo', 'oldest open entry')):
    t = P1.groupby(pd.cut(P1[rn], bins), observed=False).bb_lots.agg(n='size', ev=lambda s: (s > 0).sum()); hz[rn] = (t.ev / t.n * 1000).values; H[f'{nm}: per 1000 contract-min'] = [f'{v:.1f}' for v in hz[rn]]
H['cheapest-entry events / minutes'] = [f'{int(e)}/{int(n)}' for e, n in zip(P1.groupby(pd.cut(P1.r_low, bins), observed=False).bb_lots.agg(lambda s: (s > 0).sum()), P1.groupby(pd.cut(P1.r_low, bins), observed=False).size())]
steps = hz['r_low'][1:] / hz['r_low'][:-1]; stepdf = pd.DataFrame({'bin → next bin': [f'{lab[i]} → {lab[i + 1]}' for i in range(len(lab) - 1)], 'hazard step (cheapest-entry ref)': [f'{x:.1f}×' for x in steps], 'hazard step (average-entry ref)': [f'{x:.1f}×' for x in hz['r_avg'][1:] / hz['r_avg'][:-1]]})
first3 = next(lab[i] + ' → ' + lab[i + 1] for i in range(len(steps)) if steps[i] >= 3)
pr = pd.DataFrame(R1['D-1_pair_by_r_avg']); pr['paired'] = [pct(x) for x in pr.paired]; pr['partnered'] = [pct(x) for x in pr.partnered]; pr.columns = ['premium ÷ average entry', 'orders', 'paired (same strike, ±3 s)', 'partnered (other right, any strike, ±3 s)']
au = A[(A.day == 'D-1') & A.target.isin(['ce_only', 'pe_only', 'both'])][['target', 'variable', 'n_events', 'AUC', 'lo', 'hi', 'null_max']].copy(); au.columns = ['target', 'variable', 'events', 'AUC', 'CI low', 'CI high', 'permutation max']
lots = []
for cv in ('low', 'fifo', 'high'): lots.append((cv.upper(), pct(R5[f'{cv}_never12_share']), pct(R5[f'{cv}_never12_carried_share']), pct(R5[f'{cv}_ge12_carried_share']), pct(R5[f'{cv}_ge15_closed_share']), pct(R5[f'{cv}_ge17_closed_share']), pct(R5[f'{cv}_early_never12_carried'])))
lots = pd.DataFrame(lots, columns=['lot convention', 'lots that never reach 1.2×', '…of those carried overnight', 'lots reaching ≥1.2×: carried', 'reaching ≥1.5×: closed on D-1', 'reaching ≥1.7×: closed on D-1', 'never-1.2× carried (sold before 12:00 only)'])
bc = R1['D-1_below_classes']; bcdf = pd.DataFrame({'class (first match in this order)': list(bc.keys()), 'orders': list(bc.values())}); bcdf['share of the below-1.2× orders'] = [pct(v / R1['D-1_below_n']) for v in bc.values()]
bal = pd.DataFrame([(k.split('|')[1], v['n'], pct(v['own_larger']), f"{pct(v['lo'])}–{pct(v['hi'])}", pct(v['expected_if_lot_proportional'])) for k, v in R7.items() if k.startswith('D-1')], columns=['buy-back class (cheapest-entry ratio)', 'orders', 'bought-back right has more short lots', 'cluster CI', 'expected if lots drawn at random'])
lo3 = R5['strike_table']; st = pd.DataFrame(lo3); st.columns = ['highest ratio reached (cheapest open entry)', 'strike positions', 'carried (some lot)', 'carried share']; st['carried share'] = [pct(x) for x in st['carried share']]
sd = E[(E.day == 'D-1')].set_index('variable'); sdf = sd.loc[['r_low', 'price', 'abs_itm', 'itm_steps', 'hold_min', 'n_open', 'o_n_open', 'o_r', 'straddle_r', 'tod_min'], ['AUC', 'lo', 'hi', 'null_max']].round(3).reset_index()
gbdf = pd.DataFrame({'model': ['all 12 variables'] + [f'drop {v}' for v in ('o_n_open', 'hold_min', 'itm_steps', 'price', 'straddle_r')], 'LOCO AUC': [round(GB['all'], 3)] + [round(GB[f'drop {v}'], 3) for v in ('o_n_open', 'hold_min', 'itm_steps', 'price', 'straddle_r')]})
def cs(b):
    l = L[(L.conv == 'low') & (L.closed_d1.isin([0, 1]))]; lo, hi = (float(x) for x in b.strip('()[]').split(','))
    x = l[(l.max_ratio > lo) & (l.max_ratio <= hi)]; return f'{pct(1 - x.closed_d1.mean(), 0)} carried (n={len(x)})'
txt = f"""# Algo 8 — body buy-backs: single vs combined, positions below 1.2×, and buy-backs below 1.2×

*Investigation only (no simulator change, no alpha). In-sample, observational: 31 cycles with a D-1 log; the 35 live cycles are not a holdout. Plan: `BODY_CLOSE_LOGIC_PLAN.md` (written before the tests). Every number is read from `outputs/bl_summary_close*.json` / `bl_close_*.csv`. Figure: `figures/bl_close_logic.png`.*

## 0. Answers (D-1)

| Your question | Answer | Evidence level |
|---|---|---|
| Are CE and PE bought back **together** when premium is 1.2–1.7×? | **No — individually.** Only {pct(R1['D-1_paired'])} of the {R1['D-1_n']:,} buy-back orders have a CE/PE counterpart at the same strike within ±3 s (chance: {pct(R1['D-1_pair_null'][0])}); {pct(R1['D-1_partnered'])} have one at any strike. In the 1.2–1.7× average-ratio bins the paired share is {pct(pr['paired (same strike, ±3 s)'].iloc[3:6].map(lambda x: float(x[:-1]) / 100).min(), 0)}–{pct(pr['paired (same strike, ±3 s)'].iloc[3:6].map(lambda x: float(x[:-1]) / 100).max(), 0)}. | Observed |
| Is the trigger **single-leg or combined**? | **Single-leg: the leg's own premium ÷ its own entry.** When only one leg is bought back it is the higher-ratio leg {pct(R2['D-1_single_higher_leg'][1])} of the time (cluster CI {pct(R2['D-1_single_higher_leg'][2])}–{pct(R2['D-1_single_higher_leg'][3])}; 50% = indifferent). The other leg's ratio and the straddle ratio add nothing (leave-one-cycle-out AUC gain ≤ {max(abs(R2['D-1_loco_ce']['gain']), abs(R2['D-1_loco_pe']['gain'])):.4f}). On the *both-legs* events the max-leg ratio does not beat a single leg (ΔAUC {R2b['r_ce'][0]:+.2f}, CI {R2b['r_ce'][1]:+.2f} to {R2b['r_ce'][2]:+.2f}) → combined trigger **not supported** under the pre-registered rule. Both legs ≥ 1.2× at the same strike **never** occurs ({R2['D-1_rows']:,} strike-minutes). | Observed |
| Is **1.2×** a threshold? | **No.** Against the cheapest open entry the buy-back hazard is flat (≈5–7 per 1000 contract-minutes) from 1.0× to 1.4×; the hazard first steps up ≥3× on entering the **{first3.split(' → ')[1]}** bin ({steps[lab.index(first3.split(' → ')[1]) - 1]:.1f}×) and again on entering 1.5–1.6× ({steps[lab.index('1.5–1.6') - 1]:.1f}×); it keeps rising to {hz['r_low'][9]:.0f}/1000 at 1.7–1.8×. | Observed (reference is a convention) |
| Positions that **never reach 1.2×** — closed on D-1 or carried? | **Mostly carried overnight.** {pct(R5['low_never12_share'], 0)} of D-1 sold lots never reach 1.2× on a minute close; {pct(R5['low_never12_carried_share'], 0)} of them are carried ({pct(R5['fifo_never12_carried_share'], 0)} FIFO, {pct(R5['high_never12_carried_share'], 0)} HIGH). Strike-level (ownership-free): {R5['strike_never12_n']} of {R5['strike_n']} positions never reach 1.2×; {pct(R5['strike_never12_carried'], 0)} carried. Overall {pct(R5['low_carried_share'])} of lots are carried. | Observed |
| Do buy-backs happen **below 1.2×**? On what basis? | **Yes: {pct(R1['D-1_below12_r_low'], 0)}–{pct(R1['D-1_below12_r_fifo'], 0)} of orders (depending on the lot convention); {pct(R1['D-1_below12_all3'], 0)} under all three.** About a third of them ({pct(R6['D-1_sub_within3s_of_stop'], 0)}) fall within 3 s of a stop-like (≥1.5×) buy-back (chance {pct(R6['D-1_sub_within3s_null'])}), mostly the **same right but a different strike** ({pct(R6['D-1_join_same_right'], 0)} same right, {pct(R6['D-1_join_same_strike'], 0)} same strike, median {R6['D-1_join_dist_q'][0]:.0f} strikes away): one lot's stop pulls neighbouring same-side lots out with it. The rest has **no identified rule**: {bc['other']}–{R6['D-1_residual_n']} orders = {pct(bc['other'] / R1['D-1_n'], 0)}–{pct(R6['D-1_residual_n'] / R1['D-1_n'], 0)} of all D-1 buy-backs (two yardsticks, §5). | Inferred (cluster) / Unresolved (rest) |

## 1. Data and method (short)
* Order-level table of every D-1 body buy-back ({R1['D-1_n']:,} orders, each 1 lot). **Decision price = limit ÷ 1.15** (all orders are marketable limits ≈ 15% beyond the live price; check: decision price ÷ previous-minute close has median {(d1.dec_px / d1.px_chain).median():.3f}).
* **Entry references** (lot ownership inside a strike is unobserved, so three conventions are shown): *average* open body entry (pro-rata removal), *cheapest open entry* (LOW: buy-backs remove the lowest-entry lot first — the lot with the highest ratio, i.e. what a per-lot stop would hit), *oldest open entry* (FIFO). `HIGH` is used only in the carry test. Each convention keeps its own open set, so the references can differ for the same order.
* **Paired** = other-right body buy-back at the same strike within ±3 s; **partnered** = other-right buy-back at any strike within ±3 s. Chance level from circularly shifting the other right's order times inside the cycle-day (strike kept).
* Hazard = buy-backs per 1000 contract-minutes (contract = a strike/right with body shorts open; ratio = previous-minute close ÷ entry). Minute data only (no bid/ask, no high/low).

## 2. CE and PE: together or individually?
{table(pr)}
* Paired legs (n = {R1['D-1_pairs_n']}): the high leg has median ratio {np.nanmedian(np.maximum(d1[d1.paired].r_avg, d1[d1.paired].pair_ratio)):.2f}, the other {np.nanmedian(np.minimum(d1[d1.paired].r_avg, d1[d1.paired].pair_ratio)):.2f}. One ≥1.2× and the other <1.2×: {pct(R1['D-1_pair_one_ge12_one_lt'], 0)}; both <1.2×: {pct(R1['D-1_pair_both_lt12'], 0)}; both ≥1.2×: {pct(R1['D-1_pair_both_ge12'], 0)}. A pair is therefore a stop-like leg plus a partner that is **not** at the stop level — not two legs hitting a level together.
* Pairing is much more common at ≤0.8× ({pct(float(pr['paired (same strike, ±3 s)'].iloc[0][:-1]) / 100, 0)}), which is where simultaneous clean-up closes sit; it is not a feature of the 1.2–1.7× band.
* Strike-minutes with both legs short ({R2['D-1_rows']:,}): CE bought back {R2['D-1_counts']['ce']}, PE {R2['D-1_counts']['pe']}, both in the same minute {R2['D-1_counts']['both']} ({pct(R2['D-1_both_share_of_any'])} of all buy-back strike-minutes).

**What predicts which leg is bought back (D-1, AUC with cluster-bootstrap CI over cycles; permutation null ≈ 0.5):**
{table(au.round(3))}
* Own-leg ratio AUC ≈ 0.80 for single-leg events; max-leg ≈ 0.72; straddle ratio 0.66–0.73; **other-leg ratio < 0.5** (a higher other-leg ratio goes with this leg being bought back *less* often; plausibly because the other leg is the one under stress — an inference).
* Leave-one-cycle-out logistic: own ratio alone CE {R2['D-1_loco_ce']['own']:.3f} → +other leg {R2['D-1_loco_ce']['own_plus_other']:.3f} (permuted-other max gain {R2['D-1_loco_ce']['null_max']:+.4f}); PE {R2['D-1_loco_pe']['own']:.3f} → {R2['D-1_loco_pe']['own_plus_other']:.3f} (permuted max {R2['D-1_loco_pe']['null_max']:+.4f}). The PE gain {R2['D-1_loco_pe']['gain']:+.4f} is statistically above the permuted maximum but economically negligible.

## 3. Is 1.2× a threshold? (hazard, D-1)
{table(H)}
Adjacent-bin steps (pre-registered rule: call a level a threshold only if the hazard steps ≥3× between adjacent bins under the cheapest-entry reference):
{table(stepdf)}
* **1.2× fails the rule** (step {steps[3]:.1f}× into 1.2–1.3, {steps[4]:.1f}× into 1.3–1.4). The first ≥3× step is on entering {first3.split(' → ')[1]}. Under the average-entry reference the rise is graded (largest step {max(hz['r_avg'][1:] / hz['r_avg'][:-1]):.1f}×); the oldest-entry reference lies in between (largest step {max(hz['r_fifo'][1:] / hz['r_fifo'][:-1]):.1f}×). The hazard is flat from 1.0× to 1.4× — a buy-back is not "slowly started at 1.2×".
* **The sharpness depends on the reference.** Against the cheapest open entry the hazard at 1.7–1.8× is {hz['r_low'][9]:.0f}/1000 (about 2 in 3 minutes); against the average entry only {hz['r_avg'][9]:.0f}/1000. A per-lot premium stop near 1.5–1.7× of the lot's own entry would look like this under LOW and blunter under the others. **That is a consistent reading, not a proof** (ownership is unobserved).
* Distribution of the ratio at the buy-back (figure panel A, cheapest-entry ref): a large mode at 1.5–1.8× and a second mode at 1.0–1.2×. The second mode is what the user sees as "buy-backs below 1.2×".

## 4. Positions that never reach 1.2× — closed or carried?
{table(lots)}
{table(st)}
* The carried share falls with the highest ratio reached (figure panel C; LOW convention): {cs('(0.0, 1.2]')} up to 1.2×, {cs('(1.4, 1.5]')} at 1.4–1.5×, {cs('(1.5, 1.6]')} at 1.5–1.6×, {cs('(1.7, 2.0]')} at 1.7–2.0×. Lots that stay below ~1.4× are mostly kept overnight; FIFO/HIGH curves are higher above 1.5× (panel C).
* **Mechanical-carry check:** lots sold late have little time to reach a ratio. Restricting to lots sold before 12:00 IST leaves {pct(R5['low_early_never12_carried'], 0)}–{pct(R5['high_early_never12_carried'], 0)} of never-1.2× lots carried (LOW–HIGH), against {pct(R5['low_early_carried'], 0)} / {pct(R5['fifo_early_carried'], 0)} / {pct(R5['high_early_carried'], 0)} carried among all early lots.
* Strike-level "carried (some lot)" stays high even when the highest ratio is high because a strike holds several lots and only the stressed ones are closed; the lot-level table is the better reading of the stop behaviour.
* The earlier finding stands: there is no closing time and no selling cut-off on D-1; closes are driven by premium ratio (and the unexplained residual below), not the clock.

## 5. Buy-backs below 1.2× — what are they?
Share of D-1 buy-back orders below 1.2×: average-entry {pct(R1['D-1_below12_r_avg'])}, cheapest {pct(R1['D-1_below12_r_low'])}, oldest {pct(R1['D-1_below12_r_fifo'])}, all three {pct(R1['D-1_below12_all3'])}. Switching reference removes only a part, so the sub-1.2× mode is real.

**Mutually exclusive classification (average-entry ratio < 1.2×, {R1['D-1_below_n']} orders; first match wins; the order of classes was fixed in the code, not tuned):**
{table(bcdf)}
* Classes 1–2 (a ≥1.2× partner leg within 3 s) = {pct((bc['1 same-strike partner leg >=1.2x (paired)'] + bc['2 other-strike partner leg >=1.2x']) / R1['D-1_below_n'], 0)}; class 3 (a lot-level reference ≥1.2×, i.e. the order is a stop under another convention) = {pct(bc['3 a lot-level reference (LOW/FIFO) >=1.2x'] / R1['D-1_below_n'], 0)}; **{bc['other']} orders ({pct(bc['other'] / R1['D-1_below_n'], 0)} of the below-1.2× orders, {pct(bc['other'] / R1['D-1_n'], 0)} of all D-1 buy-backs) stay unexplained** by this yardstick. The cluster test below uses the cheapest-entry yardstick and leaves {R6['D-1_residual_n']} ({pct(R6['D-1_residual_n'] / R1['D-1_n'], 0)} of all). So the unexplained share is **{pct(bc['other'] / R1['D-1_n'], 0)}–{pct(R6['D-1_residual_n'] / R1['D-1_n'], 0)} of all D-1 buy-backs**, depending on the yardstick.

**Clusters (post-hoc, added after the first classification left a large residual and a first look showed sub-1.2× buy-backs next to stop-like ones).** Using the cheapest-entry ratio (stop-like = ≥1.5×; this cut-off was chosen after the hazard table, see §8): {R6['D-1_clusters']} clusters (gap ≤ 3 s); {pct(R6['D-1_cluster_singletons'], 0)} are single orders; {pct(R6['D-1_orders_in_stop_clusters'], 0)} of all orders sit in a cluster with a stop-like member. Of the {R6['D-1_sub_n']} sub-1.2× orders **{pct(R6['D-1_sub_within3s_of_stop'], 0)} are within 3 s of a stop-like order (shifted-time chance {pct(R6['D-1_sub_within3s_null'])})**. Joiners: same right {pct(R6['D-1_join_same_right'], 0)}, same strike {pct(R6['D-1_join_same_strike'], 0)}, distance median {R6['D-1_join_dist_q'][0]:.0f} / 75th pct {R6['D-1_join_dist_q'][1]:.0f} / 90th pct {R6['D-1_join_dist_q'][2]:.0f} strikes. Widening the clustering window to 10 / 30 / 60 s raises the share of sub-1.2× orders whose cluster has a ≥1.5× member to {pct(R6['D-1_window_sensitivity']['10']['ge15'], 0)} / {pct(R6['D-1_window_sensitivity']['30']['ge15'], 0)} / {pct(R6['D-1_window_sensitivity']['60']['ge15'], 0)} (and to {pct(R6['D-1_window_sensitivity']['60']['ge12'], 0)} with a ≥1.2× member at 60 s); {pct(R6['D-1_window_sensitivity']['3']['singleton'], 0)} of the sub-1.2× orders are isolated single orders at 3 s.

**Residual: {R6['D-1_residual_n']} sub-1.2× orders in no stop-like cluster ({pct(R6['D-1_residual_n'] / R1['D-1_n'], 0)} of all D-1 buy-backs).** Tests on **all** D-1 contract-minutes with cheapest-entry ratio < 1.2× — not only the residual — ({R3['D-1_rows']:,} rows, {R3['D-1_events']} buy-back minutes):
{table(sdf)}
* No single variable passes 0.65 AUC. A leave-one-cycle-out gradient-boosting model on all 12 variables reaches AUC {R3['D-1_gb_loco_auc']:.3f} — a diffuse multivariable signal (largest drops when removing the other leg's open lots, holding time, ITM distance, price):
{table(gbdf)}
  This is not a rule; it shows the residual is not pure noise, and it is in-sample.
* **Balance-control hypothesis (rejected).** By analogy with the hedge I tested whether the right bought back is the right with more short lots. For sub-1.2× orders it is ({pct(R7['D-1|sub-1.2x']['own_larger'], 0)}), but that is exactly what random choice of lots would give ({pct(R7['D-1|sub-1.2x']['expected_if_lot_proportional'], 0)} expected). Stop-like orders hit the right with **fewer** short lots ({pct(R7['D-1|stop-like (>=1.5x)']['own_larger'], 0)} vs {pct(R7['D-1|stop-like (>=1.5x)']['expected_if_lot_proportional'], 0)} expected) — the stopped side is the one with fewer lots (descriptive; plausibly earlier stops already reduced it — an inference).
{table(bal)}

## 6. D0 (secondary, for contrast)
* D0 buy-backs are **not** premium-ratio driven: own-leg ratio AUC {D0A[(D0A.variable == 'r_ce') & (D0A.target == 'ce')].AUC.iloc[0]:.2f} (CE) / {D0A[(D0A.variable == 'r_pe') & (D0A.target == 'pe')].AUC.iloc[0]:.2f} (PE) (≈ chance; D-1 ≈ 0.77); among sub-1.2× contract-minutes the minute of day alone has AUC {E[(E.day == 'D0') & (E.variable == 'tod_min')].AUC.iloc[0]:.2f} (clock-driven bulk closing, as found in the lifecycle study).
* Pairing is much more common ({pct(R1['D0_paired'], 0)} of orders paired vs chance {pct(R1['D0_pair_null'][0])}; {pct(R2['D0_both_share_of_any'], 0)} of buy-back strike-minutes close both legs) and {pct(R1['D0_below12_r_avg'], 0)} of orders are below 1.2× (average ref; {pct(R1['D0_below12_all3'], 0)} under all three). Only {pct(R6['D0_sub_within3s_of_stop'], 0)} of sub-1.2× orders sit within 3 s of a stop-like order (chance {pct(R6['D0_sub_within3s_null'])}). D0 needs its own schedule analysis; it is not answered here.

## 7. Evidence register
| Claim | Label | n / basis |
|---|---|---|
| D-1 buy-backs are single-leg; pairing {pct(R1['D-1_paired'])} vs chance {pct(R1['D-1_pair_null'][0])} | **Observed** | {R1['D-1_n']:,} orders, 31 cycles |
| Own-leg premium ratio is the trigger; other-leg / straddle ratio add nothing | **Observed** (predictive, not causal) | {R2['D-1_rows']:,} strike-minutes, LOCO, permutation null |
| No step at 1.2×; hazard rises steeply between 1.4× and 1.8× against the cheapest open entry | **Observed** (reference-dependent) | {int(P1.bb_lots.gt(0).sum())} buy-back minutes |
| Consistent with a per-lot premium stop of ≈1.5–1.7× the lot's own entry | **Inferred** | hazard shape under LOW only; ownership unobserved |
| Lots below ~1.4× are mostly carried overnight; ≥1.7× mostly closed | **Observed** | {R5['low_lots']:,} lots; robust to lot convention and late sales (ranges shown) |
| ≈{pct(R6['D-1_sub_within3s_of_stop'], 0)} of sub-1.2× buy-backs are co-closed with a stop-like buy-back, same right, nearby strikes | **Inferred** (cluster; post-hoc threshold) | {R6['D-1_sub_n']} orders, shifted-time null |
| {pct(bc['other'] / R1['D-1_n'], 0)}–{pct(R6['D-1_residual_n'] / R1['D-1_n'], 0)} of D-1 buy-backs (sub-1.2×, not co-closed) have no identified basis | **Unresolved** | {bc['other']}–{R6['D-1_residual_n']} orders (two yardsticks) |
| Balance control of CE/PE short lots | **Rejected** | lot-proportional null reproduces it |

## 8. Limits, post-hoc items and how this could be wrong
* **Reference dependence.** Entry reference per order is a convention (ownership unobserved); the LOW view is the sharpest and is the one I read as "per-lot". Under average/oldest-entry references the structure is the same but blunter.
* **Minute data.** Ratios use the previous-minute close; intra-minute spikes are invisible. A lot that breached 1.5× inside a minute and was closed will appear as closed at a lower close ratio. This may account for part of the 1.2–1.5× class and some sub-1.2× closes; it cannot be tested without tick data.
* **Post-hoc items** (labelled in the text): the cluster analysis and the stop-like cut-off of 1.5× (chosen after seeing the hazard table; window sensitivity is in §5); the balance test; the gradient-boosting drop-one run; the early-lot robustness check; the pairing window (3 s) is an analysis choice (±10/30/60 s only checked for the cluster share).
* **Plan deviation:** the plan named `bl_close_orders.py` and `bl_close_panel.py`; the code is `bl_close_build.py` (order table, strike-level panel, lot table in one replay) and `bl_close_logic1–7`. The earlier `bl_close_panel.py` is unchanged; both panels agree on the {int(P1.bb_lots.gt(0).sum())} buy-back contract-minutes.
* **What I did not test:** why stop-like closes are not certain once the ratio is high (hazard 672 per 1000 minutes at 1.7–1.8× is not 1000); the residual's rule; D0 schedule slot by slot; any link to hedge/lump events at the moment of a buy-back.
* **In-sample.** All 31 cycles were used for exploration and checks; none is held out.

## 9. Files
`src/bl_close_build.py` → `bl_close_logic1.py` (order-level, pairing, below-1.2× classes, episodes) → `bl_close_logic2.py` / `2b` (single vs combined) → `bl_close_logic3.py` / `4` (sub-1.2× signal) → `bl_close_logic5.py` (carry) → `bl_close_logic6.py` (clusters) → `bl_close_logic7.py` (balance) → `bl_close_fig.py` → `make_close_report.py`. Outputs: `outputs/bl_close_orders*.csv`, `bl_close_panel2.csv.gz`, `bl_close_lots.csv`, `bl_close_C_*`, `bl_close_D_*`, `bl_close_E_*`, `bl_summary_close*.json`. Tests: `tests/test_bl.py` (`test_close_*`).
"""
open(f'{RP}/BODY_CLOSE_LOGIC.md', 'w').write(txt); print(len(txt.splitlines()), 'lines written')
