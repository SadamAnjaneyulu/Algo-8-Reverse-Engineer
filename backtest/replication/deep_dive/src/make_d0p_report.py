"""Builds reports/D0_PAIR.md and figures/bl_d0p_summary.png from the bl_d0p_* outputs."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); C = lambda n: pd.read_csv(f'{OUT}/{n}.csv')
R1, R2, R3 = J('d0p1'), J('d0p2'), J('d0p3')
A0, A2, A3, IMA, H, CT, B1, B2, B3, AB, FW, IMB, B4, B5, B6 = [C(n) for n in ('bl_d0p_a0', 'bl_d0p_a2', 'bl_d0p_a3', 'bl_d0p_a2_imp', 'bl_d0p_a5_hazard', 'bl_d0p_a5_cont', 'bl_d0p_b1', 'bl_d0p_b2', 'bl_d0p_b3', 'bl_d0p_b3_abl', 'bl_d0p_b3_fwd', 'bl_d0p_b3_imp', 'bl_d0p_b4', 'bl_d0p_b5', 'bl_d0p_b6')]
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
sr = R1['sale_rates']; b3 = B3.set_index('model'); g = lambda w, k: A0.set_index('window_s').loc[w, k]; b5 = B5.iloc[0]; b4 = R3['b4']; a4 = R1['a4']; cont = CT.set_index(['outcome', 'model']).auc; pl = A2[A2.model.str.startswith('placebo')].set_index('outcome').auc; allf = A2[A2.model == 'all factors'].set_index('outcome')
b1_ = B1[(B1.theta == 1.4) & (B1.group == 'all lots')].iloc[0]; b2 = B2.set_index(['outcome', 'rule'])
B6['window_min'] = B6.window_min.astype(str); dec = B6[B6.side.str.startswith('sale (decision')].set_index('window_min'); decb = B6[B6.side.str.startswith('buy-back (decision')].set_index('window_min')
# ---------------- figure
fig, ax = plt.subplots(2, 3, figsize=(20, 10.5)); a = ax[0, 0]; x = np.arange(len(A0)); a.bar(x - .2, A0.share_events_real, .4, color='#2b6cb0', label='real'); a.bar(x + .2, A0.share_events_null, .4, color='#cbd5e0', label='chance (shifted 15 min)'); a.set_xticks(x); a.set_xticklabels([f'±{w} s' for w in A0.window_s]); a.set_ylabel('share of stop-loss events with a sale of the other right'); a.legend(fontsize=8); a.set_title('A. The 2/5/10/60 s windows: real vs chance', fontsize=10)
a = ax[0, 1]; a.plot(range(len(H)), H.hazard_per_second, 'o-', color='#2b6cb0'); a.set_yscale('log'); a.set_xticks(range(len(H))); a.set_xticklabels(H.lag, rotation=45, fontsize=8); a.set_ylabel('chance per second that the first sale arrives (given none yet)'); a.set_title('B. After the buy-back the sale arrival rate decays smoothly', fontsize=10)
a = ax[0, 2]; ys = ['sale_2', 'sale_10', 'sale_60']; w = .27
for k, (nm, col) in enumerate((('decision-time factors', '#2b6cb0'), ('+ minute-j bar', '#d69e2e'))): a.bar(np.arange(3) + k * w, [cont[(y, 'decision-time factors' if k == 0 else 'decision-time + minute-j bar')] for y in ys], w, color=col, label=nm)
a.bar(np.arange(3) + 2 * w, [pl[y] for y in ys], w, color='#cbd5e0', label='placebo'); a.set_xticks(np.arange(3) + w); a.set_xticklabels(['sale ≤2 s', 'sale ≤10 s', 'sale ≤60 s']); a.set_ylim(.5, .9); a.set_ylabel('LOCO AUC'); a.legend(fontsize=8, loc='upper left'); a.set_title('C. Does anything decide the sale? Weakly (24 cycles)', fontsize=10)
a = ax[1, 0]; cats = ['bought before crossing', 'same minute', 'next minute', '2–5 min', '6–15 min', 'later (in scope)', 'clearance / stop / never']; cols = ['bought_before_crossing', 'lag0', 'lag1', 'lag2_5', 'lag6_15', 'later_in_scope', 'clearance_stop_or_never']; cc = ['#a0aec0', '#2b6cb0', '#4299e1', '#63b3ed', '#d69e2e', '#ed8936', '#e53e3e']; bt = np.zeros(3); sel = B1[B1.group == 'all lots']
for cn, cl, c_ in zip(cats, cols, cc): a.bar(range(3), sel[cl], bottom=bt, color=c_, label=cn); bt += sel[cl].values
a.set_xticks(range(3)); a.set_xticklabels([f'θ = {t}×' for t in sel.theta]); a.legend(fontsize=7, loc='upper right'); a.set_title('D. What happens to a lot after its premium first crosses θ× entry', fontsize=10)
a = ax[1, 1]; o = [m for m in B3.model if not m.startswith('placebo')][::-1]; v = b3.loc[o]; a.barh(range(len(o)), v.auc, xerr=[v.auc - v.lo, v.hi - v.auc], color='#2b6cb0'); pa = b3.loc[[m for m in B3.model if m.startswith('placebo')][0], 'auc']; a.axvline(pa, color='r', ls='--', lw=1); a.set_yticks(range(len(o))); a.set_yticklabels(o, fontsize=8); a.set_xlim(.5, .95); a.set_xlabel('LOCO AUC inside minutes where some lot is ≥1.4× entry'); a.set_title('E. What picks the buy-back minute', fontsize=10)
a = ax[1, 2]; xs = [str(w) for w in dec.index]; a.plot(xs, dec.rate_when_on, 'o-', color='#2b6cb0', label='sale: close of j−1 at a new low'); a.plot(xs, decb.rate_when_on, 's-', color='#e53e3e', label='buy-back: close of j−1 at a new high'); a.axhline(dec.rate_when_off.mean(), color='#2b6cb0', ls=':', lw=1); a.axhline(decb.rate_when_off.mean(), color='#e53e3e', ls=':', lw=1); a.set_xlabel('lookback window (minutes)'); a.set_ylabel('share of minutes with the action (dotted = condition off)'); a.legend(fontsize=8); a.set_title('F. Mirror images: sells at premium lows, buys back at premium highs', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0p_summary.png'), dpi=110); plt.close()
# ---------------- report
passing = [m for m in ('+G2 spot against the right', '+G3 premium of the right', '+G4 side loss', '+G5 book', '+G6 other right') if b3.loc[m, 'gain_over_G0_G1'] >= 0.03 and b3.loc[m, 'lo'] > 0.55]
txt = f"""# Algo 8 — D0: what else decides the counter-sale, and what triggers the buy-back

*Plan `D0_PAIR_PLAN.md` (addendum at the end lists what changed after the first run, including a leak I fixed). In-sample discovery on D0, 24 cycles with minutes after the opening window. Figure: `figures/bl_d0p_summary.png`. Scripts `bl_d0p_*.py`.*

## 0. Result
**1. The 2 s / 5 s / 10 s / 60 s gaps are not separate stages. They are the waiting time for the next sale after a stop-loss, and I found no extra condition that decides it.**
**2. The buy-back is not fired by the lot crossing 1.4× its entry. It fires when the stopped option's premium is breaking to a new high, the spot has been moving against it, and the same side was bought back a minute or two earlier. That is the mirror image of the sale trigger (premium at a new low).** I could not recover an exact rule.

| Question | Answer | Label |
|---|---|---|
| **Are the four windows real steps?** | No. They are my cumulative cut-offs. Real share minus chance: {g(2,'excess'):.0%} at 2 s, {g(5,'excess'):.0%} at 5 s, {g(10,'excess'):.0%} at 10 s, {g(60,'excess'):.0%} at 60 s. The chance level itself climbs (2.8% → 28%). | Observed |
| **Shape of the delay** | The chance per second that the first sale arrives falls steadily: {H.hazard_per_second[0]:.3f} in the first second, {H.hazard_per_second[3]:.3f} at 5–10 s, {H.hazard_per_second[6]:.4f} at 30–60 s, {H.hazard_per_second.iloc[-1]:.4f} at 5–15 min. No plateaus. | Observed |
| **Does the sale always come?** | Almost. Of the {a4['events_no_sale_60']} events with no sale within 60 s, {a4['share_with_a_later_sale']:.0%} get one later (median wait {a4['wait_min_q'][1]:.1f} min, {a4['within_5min']:.0%} within 5 min). | Observed |
| **Another condition that must hold?** | **None found.** Best out-of-fold AUC for "sale within 10 s" is {allf.loc['sale_10','auc']:.2f} (CI {allf.loc['sale_10','lo']:.2f}–{allf.loc['sale_10','hi']:.2f}; placebo {pl['sale_10']:.2f}). No factor passes the gate test. Adding the minute's own bar lifts it to {cont[('sale_10','decision-time + minute-j bar')]:.2f} (and {cont[('sale_60','decision-time factors')]:.2f} → {cont[('sale_60','decision-time + minute-j bar')]:.2f} for 60 s). The rest is the price path inside the minute. | Observed; rest Not testable |
| **Is the 1.4× crossing the buy-back trigger?** | No. Of lots that crossed 1.4× at some point, only {b1_.lag0:.0%} were bought back in the same minute, {b1_.lag1:.0%} in the next, and {b1_.clearance_stop_or_never:.0%} not before the clearance/stop or never. For stop-loss lots the median gap between first crossing and buy-back is {b4['median']:.0f} minutes ({b4['lag_le1']:.0%} within 1 min, {b4['lag_gt15']:.0%} over 15). {R3['panel']['crossing_share']:.0%} of all right-minutes already have some lot above 1.4×, and only {b5.crossing_only_precision:.0%} of those minutes see a buy-back. | Observed |
| **What does pick the minute?** | In minutes where a lot is ≥1.4×, adding spot (+{b3.loc['+G2 spot against the right','gain_over_G0_G1']:.2f} AUC), premium of the stopped right (+{b3.loc['+G3 premium of the right','gain_over_G0_G1']:.2f}) and recent buy-backs on that side (+{b3.loc['+G5 book','gain_over_G0_G1']:.2f}) each clear my bar; side loss (+{b3.loc['+G4 side loss','gain_over_G0_G1']:.2f}) does not. The top single feature is "premium makes a new 60-minute high in the minute". | Observed |
| **Mirror image** | Sale: close of the previous minute at a new low → sale in {dec.loc['15','rate_when_on']:.0%} of minutes at a 15-minute window ({dec.loc['60','rate_when_on']:.0%} at 60), against {dec.loc['15','rate_when_off']:.0%} otherwise. Buy-back: close at a new high (lots ≥1.4×) → {decb.loc['15','rate_when_on']:.0%} ({decb.loc['60','rate_when_on']:.0%} at 60), against {decb.loc['15','rate_when_off']:.0%}. Both curves have the same shape and no sharp window. | Observed |
| **Exact buy-back rule** | **Not recovered.** Best tree: precision {b5.tree_precision:.0%} (against {b5.crossing_only_precision:.0%} for crossing alone, {b5.precision_ratio:.1f}×) but recall {b5.tree_recall:.0%}, F1 {b5.tree_F1:.2f}, bar 0.50. | Unresolved |
| **How it ties together** | When spot moves, one option's premium goes to a new high (buy-back) and the other's to a new low (sale) in the same seconds. That would give the same-second pairs without either action triggering the other. | Inferred |

## 1. Part A — the timing of the sale
**A0 — real vs chance** (all stop-loss events; chance = buy-back times shifted ±15 minutes):

{table(A0)}
**A5 — arrival rate of the first sale at or after the buy-back** (events at risk = no sale yet; {R1['events_in_panel']} events in the panel):

{table(H)}
The decay is smooth. A mix of event types can produce the same curve, so this does not prove one process.

**A2 — can the factors predict the sale?** Outcome = a solo sale of the other right **at or after** the buy-back second (see the addendum for why not before). LOCO AUC:

{table(A2[A2.outcome == 'sale_10'].drop(columns='outcome'))}
Largest permutation-importance drops (outcome ≤10 s):

{table(IMA.head(8))}
Rates for the main candidate conditions: at a 60-minute premium low {R1['low60_rates']['1.0']['sale_10']:.0%} (sale within 10 s) against {R1['low60_rates']['0.0']['sale_10']:.0%} when not; a solo sale on the same right in the previous 60 s {R1['recent_sale_rates']['True']['sale_10']:.0%} against {R1['recent_sale_rates']['False']['sale_10']:.0%}. The "ladder step" (price now ÷ price at the last sale of the same contract) shows only mild gradients:

{table(pd.DataFrame(R1['ladder_bins']).T.reset_index().rename(columns={'index':'ratio'}), 3)}
**A3 — gate test.** A factor is a gate only if the sale follows within 10 s at least 60% of the time when it is on and at most 20% when off. The stumps fitted on training cycles never switched on at a level that meets this (no gate accepted):

{table(A3)}
**With the minute's own bar** (post-hoc, diagnostic):

{table(CT)}

## 2. Part B — what triggers the buy-back
**B1 — what happens after a lot first crosses θ× its entry** (high of its contract):

{table(B1)}
**B4 — stop-loss lots, minutes from first crossing of 1.4× to the buy-back:** {b4['lots']:,} lots, median {b4['median']:.0f}, same minute {b4['lag0']:.0%}, within 5 minutes {b4['lag_le5']:.0%}, over 15 minutes {b4['lag_gt15']:.0%}.

**B2 — which reference price, exact-cell F1 (out-of-fold, threshold on the training cycles).** Cell outcome `y_bb` = any in-scope body buy-back on the right in the minute; `y_loss` = one with a decision ratio ≥1.2. Flag-everything floor and a ±15-minute shifted version are shown:

{table(B2)}
The per-lot rule on bar j beats its shifted version for `y_loss` ({b2.loc[('y_loss','own entry, bar j'),'F1']:.2f} vs {b2.loc[('y_loss','own entry, bar j'),'shifted_15min_F1']:.2f}) but with precision {b2.loc[('y_loss','own entry, bar j'),'precision']:.0%}. For all buy-backs (`y_bb`) no rule beats the flag-everything floor ({b2.loc[('y_bb','own entry, bar j'),'flag_all_F1']:.2f}). Strike-average and side-level references do not do better than the lot's own entry.

**B3 — the main test:** only minutes where some lot is ≥1.4× entry ({int(b3.loc['G0 baseline','cells']):,} cells, positive rate {b3.loc['G0 baseline','positive_rate']:.1%}):

{table(B3)}
* Families that clear my bar (+0.03 over G0+G1 and CI lower bound above 0.55): **{', '.join(passing)}**.
* Ablation (all families minus one): {', '.join(f"{r.dropped} {r.auc:.3f}" for r in AB.itertuples())} against all {b3.loc['all families','auc']:.3f}. Each family is partly redundant with the others.
* Forward check (first 16 cycles → last 8): {', '.join(f"{r.model.split(' ')[0]} {r.auc:.2f}" for r in FW.itertuples())}.

Top permutation importances:

{table(IMB.head(10))}
`prem_high60_c` is the premium making a new 60-minute high inside the minute (bar j). `bb_own_5` is lots bought back on the same side in the previous 5 minutes: **buy-backs come in clusters**.

**B5 — rule.** Depth-3 tree inside crossing-present minutes: {table(B5)}
Accepted only with F1 ≥ 0.50: **not met**. The in-sample tree splits first on "premium at a new 60-minute high in the minute", then on a buy-back on the same side within the last minute with a ≥12% premium rise, or on the 60-minute spot move against the right (`outputs/bl_d0p_b5_tree.txt`).

**B6 (post-hoc) — lookback window of the premium breakout.** Each side at bar j and at the decision time (close of j−1):

{table(B6)}
No window stands out. Shorter windows flag more minutes at about 30%; longer windows fewer at about 70%.

## 3. What is not known
* **What decides, second by second, whether the sale follows.** The minute's bar adds a lot. Tick data would be needed. **Not testable here.**
* **Whether the premium-breakout reading is the real mechanism or a proxy** for something I have not built (for example a level in the underlying, an indicator on the spot, or the vendor's own signal). The decision-time versions are weaker than the contemporaneous ones.
* **The exact buy-back rule.** Precision 44%, recall 32% is not a rule.
* **The remaining ~35% of non-stop buy-backs** (burst members, roll-outs, others) are not separately explained here.

## Addendum — changes after the first run
1. **Leak fixed.** The first version of the Part A models used the outcome "sale within ±W s" together with the feature "seconds since the last solo sale". A sale just before the buy-back made the feature reveal the outcome (AUC 0.86, a spurious gate with 100%). The outcome is now "at or after the buy-back"; the ±W shares remain only as descriptive numbers (A0). The plan's A-part should be read that way.
2. **Post-hoc, after seeing results:** the hazard table and the minute-j bar check (A5), the lookback-window comparison (B6), and its decision-time version, added to rule out the fill of the order itself printing the new high or low.
3. B1–B5 as planned. The cell outcome `y_loss` (decision ratio ≥1.2) was added next to `y_bb` as a secondary view.
4. The events here are grouped by lots flagged stop-loss, so counts differ slightly from `D0_COUNTER.md`.

## Caveats
* In-sample, one-minute bars, 24 cycles, cycle-bootstrap CIs. No untouched data.
* The contemporaneous bar contains the algo's own fills. The decision-time versions show the same pattern, weaker.
* Lot state uses the ledger convention (highest-ratio lot removed).

## Run order
`bl_d0p_a.py` (~3 min) → `bl_d0p_a2.py` → `bl_d0p_b.py` (~3 min) → `bl_d0p_b6.py` → `make_d0p_report.py`.
"""
open(os.path.join(RP, 'D0_PAIR.md'), 'w').write(txt); print('written')
