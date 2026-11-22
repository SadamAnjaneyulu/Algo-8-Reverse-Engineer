"""Builds reports/D0_CTRIG.md and figures/bl_d0n_summary.png from the bl_d0n_* outputs."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); C = lambda n: pd.read_csv(f'{OUT}/{n}.csv')
R1, R2, R3, R4, R5 = J('d0n1'), J('d0n2'), J('d0n3'), J('d0n4'), J('d0n5')
N2, AB, FW, IM, N1, N3, N4, DC, EX, HR, M15, N6, TS = C('bl_d0n_n2'), C('bl_d0n_n2_abl'), C('bl_d0n_n2_fwd'), C('bl_d0n_n2_imp'), C('bl_d0n_n1'), C('bl_d0n_n3'), C('bl_d0n_n4'), C('bl_d0n_decomp'), C('bl_d0n_decomp_excl'), C('bl_d0n_hour'), C('bl_d0n_minute15'), C('bl_d0n_n6'), C('bl_d0n_tight_sum')
PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
n2 = N2.set_index('model'); plc = R1['placebo_all']; ex = EX.set_index('why'); dc = DC.set_index('condition'); nb = {r['window_s']: r for r in R2['n4b']}; n4 = R2['n4']; n5 = R2['n5']; bu = R2['bursts']; h7 = {r['set']: r for r in R2['h7']}; n1 = N1.set_index('model')
# ---------------- figure
fig, ax = plt.subplots(2, 3, figsize=(20, 10.5)); a = ax[0, 0]
o = list(N2.model)[::-1]; v = n2.loc[o]; a.barh(range(len(o)), v.auc, xerr=[v.auc - v.auc_lo, v.auc_hi - v.auc], color='#2b6cb0'); a.axvline(plc['auc'], color='r', ls='--', lw=1.2); a.text(plc['auc'] + .003, len(o) - .6, 'placebo\n(cycle-permuted)', color='r', fontsize=8); a.set_yticks(range(len(o))); a.set_yticklabels(o, fontsize=8); a.set_xlim(.5, .95); a.set_xlabel('leave-one-cycle-out AUC (pooled), 95% cycle-bootstrap CI'); a.set_title('A. What predicts a solo sale in a minute (14,762 cells)', fontsize=10)
a = ax[0, 1]; s = N4[N4.bb == 'stop-loss buy-backs']; a.bar(s.lag_s, s.orders, .85, color='#2b6cb0', label='real'); a.step(s.lag_s, s.null, where='mid', color='#718096', label='null (shifted 15 min)'); a.axvline(0, color='r', lw=1, ls='--'); a.set_xlabel('seconds: sale on the other right minus stop-loss buy-back'); a.legend(fontsize=8); a.set_title('B. Same-second coupling, both sides of zero', fontsize=10)
a = ax[0, 2]; b = pd.cut(PN.prem_vs_daymin, [0, 1.0001, 1.02, 1.05, 1.1, 1.2, 1.5, 3, 100], labels=['at low', '≤1.02×', '≤1.05×', '≤1.1×', '≤1.2×', '≤1.5×', '≤3×', '>3×']); g = PN.groupby(b, observed=True).y.agg(['mean', 'size']); a.bar(range(len(g)), g['mean'], color='#d69e2e'); [a.text(k, y + .01, f'n={n}', ha='center', fontsize=7) for k, (y, n) in enumerate(zip(g['mean'], g['size']))]; a.set_xticks(range(len(g))); a.set_xticklabels(g.index, fontsize=8); a.set_ylabel('share of minutes with a solo sale'); a.set_xlabel("ATM premium of the sold right ÷ its day low so far (previous close)"); a.set_title('C. Sales when the premium sits at its low', fontsize=10)
a = ax[1, 0]; e = EX.set_index('why'); bot = np.zeros(2); cols = ['#2b6cb0', '#d69e2e', '#38a169', '#805ad5', '#cbd5e0']
for k, (w, r) in enumerate(e.iterrows()): a.bar([0, 1], [r.counter_labelled_share, r.other_solo_share], bottom=bot, color=cols[k], label=w); bot += [r.counter_labelled_share, r.other_solo_share]
a.set_xticks([0, 1]); a.set_xticklabels(['counter-labelled', 'other solo']); a.legend(fontsize=7, loc='upper right'); a.set_title('D. First condition each sale meets (share of lots)', fontsize=10)
a = ax[1, 1]; x = M15.m15; a.bar(x - .2, M15.counter_labelled_share, .4, color='#2b6cb0', label='counter-labelled'); a.bar(x + .2, M15.other_solo_share, .4, color='#d69e2e', label='other solo'); a.axhline(1 / 15, color='k', ls=':', lw=1); a.set_xlabel('minute within the 15-minute block (0 = the :00/:15/:30/:45 minute)'); a.legend(fontsize=8); a.set_title('E. When in the 15-minute block', fontsize=10)
a = ax[1, 2]; a.bar(HR.hour - .2, HR.counter_lots, .4, color='#2b6cb0', label='counter-labelled lots'); a.bar(HR.hour + .2, HR.solo_lots - HR.counter_lots, .4, color='#d69e2e', label='other solo lots'); a.set_xlabel('hour of day'); a.legend(fontsize=8); a.set_title('F. When in the day', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0n_summary.png'), dpi=110); plt.close()
# ---------------- report
tb = R3['by_other_premium_at_low']; b3 = N3.set_index('rule'); hr = b3.loc['hand rule (post-hoc): ATM premium at 60-min low']; hj = b3.loc['hand rule (post-hoc, uses bar j): ATM premium makes new day low in minute j']; tr = b3.loc['tree: all market/book']; fa = R4['flag_all']
abl_drop = (n2.loc['all decision-time', 'auc'] - AB.auc).max()
txt = f"""# Algo 8 — D0 counter-sells: how they happen, when, and what triggers them

*Plan `D0_CTRIG_PLAN.md` (with an addendum written after the results). In-sample discovery on D0: 14,762 minute cells over 24 of the 30 cycles (the other 6 stop out in the opening minutes), 5,413 solo sale orders. Figure: `figures/bl_d0n_summary.png`. Scripts `bl_d0n_*.py`.*

## 0. Result
**A counter-sell is a solo sale of the right whose premium has just fallen to a new low. It often lands in the same second as a stop-loss buy-back of the other right, most likely because both react to the same spot move. Nothing here shows that the buy-back triggers it.** I could not turn this into an exact rule with one-minute bars.

| Question | Answer | Evidence | Label |
|---|---|---|---|
| **What is it?** | Solo sale of R′ (one lot in the median order) near the live ATM (35% exact, 82% within one step), mostly at strikes already short. "Counter" = another-right buy-back within ±60 s. | {h7['counter-labelled solo']['orders']:,} counter-labelled orders | Observed |
| **Main trigger** | The sold right's ATM premium is at its low. {dc.loc['prem_low_60','counter_labelled']:.0%} of counter-labelled lots are at a 60-minute premium low, against {dc.loc['prem_low_60','all_panel_cells_chance']:.0%} of all minutes ({dc.loc['prem_low_60','counter_labelled']/dc.loc['prem_low_60','all_panel_cells_chance']:.1f}×) and {dc.loc['prem_low_60','other_solo']:.0%} of other solo lots. | N2, N7 | Observed |
| **Same-second coupling to a buy-back** | {R3['stop_loss_events_with_tight_sale']:.0%} of stop-loss buy-backs have a sale on the other right within 2 s. In the ±2 s bins sales are {n4['ratio']:.0f}× the shifted null (CI {n4['ratio_ci'][0]:.0f}–{n4['ratio_ci'][1]:.0f}). **{nb[2]['share_counter_lots']:.0%} of counter-labelled lots** have a buy-back within 2 s (chance {nb[2]['null_share_all_lots']:.0%}). | N4 | Observed |
| **Is the buy-back the cause?** | Not shown. Among same-second pairs the sale comes first or in the same second in {R3['share_sale_before_or_same']:.0%} of them, and after the buy-back in {1 - R3['share_sale_before_or_same']:.0%}. Past buy-backs add {n2.loc['all decision-time','auc'] - AB.set_index('dropped').loc['bb','auc']:.3f} AUC once market state is known. The simplest reading is one tick feeding two rules. | N2, N4 | Inferred |
| **Loss recovery?** | No. Premium sold vs loss on the stopped lots: Spearman {n5['spearman_loss_vs_sold_premium']:.2f} (CI {n5['ci'][0]:.2f}–{n5['ci'][1]:.2f}), bar was 0.3; the shifted null is {n5['null_spearman'][0]:.2f}/{n5['null_spearman'][1]:.2f}. | N5 | Observed |
| **Quantity** | Not proportional to lots bought (Spearman {R3['spearman_sold_vs_bought_lots']:.2f} in same-second pairs). Burst size vs the favourable spot move: Spearman {bu['lots_vs_move_spearman']:.2f}. | N5 | Observed |
| **Clock** | No. Counter-labelled sale times recur on other cycles' times at {h7['counter-labelled solo']['ratio']:.1f}× chance (bar 3×); other solo sales {h7['other solo (not counter)']['ratio']:.1f}×. | H7 | Observed |
| **When** | All day, every hour from 09 to 15. Counter-labelled lots by hour 09–15: {', '.join(str(int(x)) for x in HR.counter_lots)}; the largest hour is 14:00. Minute 1 of the 15-minute block is high for other solo sales ({M15.other_solo_share[1]:.0%} of lots) and only mildly for counter-labelled ({M15.counter_labelled_share[1]:.0%}). | N7 | Observed |
| **Exact rule** | **Not recovered.** Best out-of-fold exact-cell F1 {tr.exact_F1:.2f} (bar 0.50). The simple "premium at its 60-minute low" gives F1 {hr.exact_F1:.2f}: precision {hr.exact_precision:.0%}, recall {hr.exact_recall:.0%}. Adding the minute's own bar lifts AUC {n2.loc['all decision-time','auc']:.2f} → {n2.loc['all + bar j (contemporaneous)','auc']:.2f}, so the trigger sits inside the minute. | N2, N3 | Unresolved |

## 1. Hypotheses and verdicts
| # | Hypothesis | Verdict |
|---|---|---|
| H1 | The counter label is an artifact (counter and other solo cannot be told apart by market and book state) | **Not killed.** AUC {n1.loc['all market/book (no buy-back features)','auc']:.2f} (CI {n1.loc['all market/book (no buy-back features)','auc_lo']:.2f}–{n1.loc['all market/book (no buy-back features)','auc_hi']:.2f}); my bar to kill it was a CI lower bound above 0.55. But counter-labelled sales do differ on two simple conditions (premium low {dc.loc['prem_low_60','counter_labelled']:.0%} vs {dc.loc['prem_low_60','other_solo']:.0%}; same-second buy-back {dc.loc['bb_2s','counter_labelled']:.0%} vs {dc.loc['bb_2s','other_solo']:.0%}). They look like the premium-low ladder in the strongest moves. |
| H2 | Spot move | **Associated, not sufficient.** +{n2.loc['+ spot','gain_over_baseline']:.2f} AUC over baseline. |
| H3 | Premium state | **Strongest group.** +{n2.loc['+ premium','gain_over_baseline']:.2f} AUC. |
| H4 | Book state | **Associated.** +{n2.loc['+ book','gain_over_baseline']:.2f} AUC; each group is redundant given the others (dropping any one costs at most {abl_drop:.3f}). |
| H5 | Loss recovery | **Rejected** (N5). |
| H6 | Same-instant coupling | **Accepted** (≥3× null, CI above 1×). Cause not shown. |
| H7 | Clock | **Rejected** for counter-labelled sales. |

## 2. N1 — counter-labelled vs other solo sales (market and book state only)
{table(N1)}
The last row uses past buy-backs, so it partly rebuilds the label itself. It should not be read as a trigger.

## 3. N2 — what predicts a solo sale in a minute
{table(N2)}
* **Placebo** (features shuffled within each cycle): AUC {plc['auc']:.3f} (CI {plc['auc_lo']:.3f}–{plc['auc_hi']:.3f}). It is well above 0.5 because the pooled AUC also rewards the level differences between cycles (underlying, version). **Read the gains against the baseline and the placebo, not against 0.5.**
* **Contemporaneous check:** adding the minute's own bar lifts PR-AUC from {n2.loc['all decision-time','prauc']:.2f} to {n2.loc['all + bar j (contemporaneous)','prauc']:.2f}. The sale reacts to a move inside the same minute.
* **Forward check** (first 16 cycles → last 8): baseline {FW.auc[0]:.2f}, premium {FW.auc[2]:.2f}, all decision-time {FW.auc[6]:.2f}, with bar j {FW.auc[7]:.2f}.

Ablation (all decision-time minus one group):
{table(AB)}
Largest permutation-importance drops (LOCO, in AUC):
{table(IM.head(8))}
`min_in_15` (position in the 15-minute block) and `prem_vs_daymin` (premium ÷ its day low) dominate. **Past buy-back features rank low.**

## 4. N3 — from predictors to a rule
{table(N3, 3)}
* **Acceptance bar** (out-of-fold F1 at least 0.50 and 3× placebo): **not met by any rule.** Best out-of-fold tree {tr.exact_F1:.2f}; placebo {tr.exact_placebo_F1:.2f}.
* **Flag-everything floor:** exact-cell F1 {fa['exact_F1']:.2f}, ±1-minute F1 {fa['tol_F1']:.2f}. The ±1-minute column therefore flatters every rule (see the addendum). Use the exact-cell columns.
* **Hand rules were chosen after the fact** (labelled post-hoc, not fitted). With the minute's own bar ("premium makes a new day low in minute j") the exact F1 is {hj.exact_F1:.2f} (precision {hj.exact_precision:.0%}, recall {hj.exact_recall:.0%}).
* Fitted on all cycles (in-sample), the tree's first split is "premium at a 60-minute low"; below it, "premium fell more than 29% in 3 minutes" or minute 0/1 of the block (`outputs/bl_d0n_n3_tree.txt`).

## 5. N4 — same-second coupling
Stop-loss buy-backs (R) against solo sales on R′, lag in seconds (sale minus buy-back), 1 s bins:

{table(N4[N4.bb == 'stop-loss buy-backs'].drop(columns='bb'), 2)}
Share of solo lots with an other-right buy-back (any reason) within the window:

{table(pd.DataFrame(R2['n4b']), 3)}
* **By buy-back reason**, the share of events with a sale within 2 s:

{table(TS, 3)}
Only stop-loss (and, weakly, burst, roll-out and cycle-stop) go with a same-second sale. Take-profit (2.5%) and partner (4.7%) do not.
* **Direction:** of {R3['n_tight_orders']} same-second sale orders, {R3['share_lag_zero']:.0%} are in the very same second, {R3['share_sale_before_or_same'] - R3['share_lag_zero']:.0%} come before the buy-back and {1 - R3['share_sale_before_or_same']:.0%} after. Order inside a second is not observable.
* **Size and price:** median 1 lot sold per 1 lot bought; the same strike in {R3['same_strike']:.0%} of pairs; premium sold ÷ premium bought median {R3['px_ratio_q'][2]:.2f}.
* **Which stop-loss events have a sale:** the share is the same whatever the lots bought ({', '.join(f'{v:.0%}' for v in R3['tight_by_lots_bought'].values())}), and higher when the other right's premium is at its low ({tb['True']['sale_within_60s']:.0%} within ±60 s against {tb['False']['sale_within_60s']:.0%} otherwise; within 2 s {tb['True']['sale_within_2s']:.0%} against {tb['False']['sale_within_2s']:.0%}). This is consistent with a shared market state rather than a fixed paired action. *Inferred.*

## 6. N5 — quantity and loss recovery
* **Loss recovery rejected:** {n5['events']} stop-loss events; premium sold in the next 60 s vs the realised loss, Spearman {n5['spearman_loss_vs_sold_premium']:.2f}. Median sold premium ₹{n5['median_sold_premium_rs']:,.0f}, median loss ₹{n5['median_loss_rs']:,.0f}, no proportionality.
* **Bursts:** {bu['n']:,} bursts (same right, gaps ≤30 s). Median {bu['orders_median']:.0f} order, lots 10/50/90% = {bu['lots_q'][0]:.0f}/{bu['lots_q'][1]:.0f}/{bu['lots_q'][2]:.0f}. Bursts of 5+ lots hold {bu['share_lots_in_5plus']:.0%} of lots. {bu['share_bursts_with_counter_label']:.0%} of bursts contain a counter-labelled order.

## 7. N6 — mechanics
{table(N6)}
Counter-labelled sales sit at the exact ATM more often ({N6.exact_atm[0]:.0%} vs {N6.exact_atm[1]:.0%}) and at a higher premium relative to the ATM ({N6.median_px_over_atm[0]:.2f} vs {N6.median_px_over_atm[1]:.2f}), but the strike offset median is 0 steps for both, and {N6.carried_strike[0]:.0%} / {N6.carried_strike[1]:.0%} go to strikes already short from D-1.

## 8. N7 (post-hoc) — what each counter-labelled sale satisfies
Share of orders meeting each condition (a sale can meet several), against the share of all minutes:
{table(DC)}
First condition met, in this order (share of lots):
{table(EX)}
**{1 - ex.loc['5 none of these','counter_labelled_share']:.0%} of counter-labelled lots meet at least one**, against at most {1 - R5['none_share_shifted_cells_ex_bb']:.0%} for the same sales moved ±10–15 minutes (the shifted check leaves out the buy-back condition, so it is an upper bound). The premium low covers a further {ex.loc['2 R′ premium at 60-min low','counter_labelled_share']:.0%} of counter-labelled lots that have no same-second buy-back.

## 9. What is not known
* **The exact trigger.** Premium lows explain about {hr.exact_recall:.0%} of sale minutes at best. The minute's own bar adds a lot, so the rule fires on intraminute moves that one-minute bars cannot show. **Not testable here.**
* **Whether the buy-back and the sale are one decision or two rules on the same tick.** The data fit the second, and I can't separate them without tick data.
* **Why a premium low sometimes does not sell** (precision 45–58%).
* **The remaining sale minutes** (premium not at a low): minute-of-block structure (minute 1 and 14) belongs to the other solo types.

## Addendum — changes made after seeing results (all labelled in the text)
1. **Panel starts at minute 4 (09:19)**, not 09:16: opening solo is its own type and the feature windows are incomplete before that. 24 of 30 cycles remain.
2. **Gradient boosting** is the histogram version, which has no row subsampling (the plan's 0.8 could not be used); other settings as planned.
3. **N3 metric:** the plan said lot-level F1. A cell-level F1 with ±1 minute tolerance was run first and has a high floor (flag-everything {fa['tol_F1']:.2f}), so **exact-cell F1 is the reported metric** and the threshold is picked on it. Lot-level F1 needs a size rule and is not computed.
4. **Post-hoc:** the premium-low features (`phx_*`), the hand rules, the same-second follow-up (N4b) and the condition table (N7) were added after N2.
5. N1's baseline model includes cycle-level features (underlying, version), so cycle-level differences in selling can leak into the pooled AUC. The placebo row shows how much.

## Caveats
* **In-sample discovery**, one-minute bars, 24 cycles. Cycle-bootstrap CIs. No untouched data, so none of this is out-of-sample evidence.
* Order within a second cannot be observed.

## Run order
`bl_d0n_panel.py` → `bl_d0n_model.py` (~3 min) → `bl_d0n_more.py` → `bl_d0n_tight.py` → `bl_d0n_rule.py` (~3 min) → `bl_d0n_decomp.py` → `make_d0n_report.py`.
"""
open(os.path.join(RP, 'D0_CTRIG.md'), 'w').write(txt); print('written')
