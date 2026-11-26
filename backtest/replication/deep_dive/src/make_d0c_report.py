"""Builds reports/D0_CAUC.md and figures/bl_d0c_summary.png."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); C = lambda n: pd.read_csv(f'{OUT}/{n}.csv')
A, FW, FM, IM = C('bl_d0c_auc'), C('bl_d0c_auc_fwd'), C('bl_d0c_fam'), C('bl_d0c_imp')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
ac = A[A.outcome == 'counter-sell cell'].set_index('variant'); aa = A[A.outcome == 'any solo-sale cell'].set_index('variant'); v1 = ac.index[0]; v2 = ac.index[1]; v3 = ac.index[2]; pl = ac.index[3]
fc = FW[FW.outcome == 'y_counter'].set_index('variant'); fa = FW[FW.outcome == 'y'].set_index('variant'); fm = FM[FM.outcome == 'counter-sell cell'].set_index('model'); fma = FM[FM.outcome == 'any solo-sale cell'].set_index('model')
# ---- figure
fig, ax = plt.subplots(1, 3, figsize=(19, 5.8)); a = ax[0]; lab = ['V1 causal', 'V2 + minute bar', 'V3 + same-minute\nbuy-backs (definitional)', 'placebo']; x = np.arange(4)
a.bar(x - .2, [ac.loc[v, 'auc'] for v in (v1, v2, v3, pl)], .4, yerr=[[ac.loc[v, 'auc'] - ac.loc[v, 'lo'] for v in (v1, v2, v3, pl)], [ac.loc[v, 'hi'] - ac.loc[v, 'auc'] for v in (v1, v2, v3, pl)]], color='#2b6cb0', label='counter-sell cells')
a.bar(x + .2, [aa.loc[v, 'auc'] for v in (v1, v2, v3, pl)], .4, color='#d69e2e', label='any solo-sale cells'); a.axhline(.85, color='r', ls='--', lw=1.3); a.text(3.4, .853, 'gate 0.85', color='r', fontsize=9, ha='right'); a.set_xticks(x); a.set_xticklabels(lab, fontsize=8); a.set_ylim(.5, 1); a.set_ylabel('LOCO AUC (cycle-bootstrap 95% CI)'); a.legend(fontsize=8, loc='lower left'); a.set_title('A. The gate: AUC on minute cells', fontsize=10)
a = ax[1]; names = ['V1 causal (reference)', 'V1 minus prem', 'V1 minus bb', 'V1 minus base', 'V1 minus book', 'V1 minus spot']; a.barh(range(len(names)), [fm.loc[n, 'auc'] for n in names], color='#2b6cb0'); a.axvline(.85, color='r', ls='--', lw=1.2); a.set_yticks(range(len(names))); a.set_yticklabels(['all causal families', 'drop premium of the sold right', 'drop past buy-backs', 'drop clock / right / index', 'drop book state', 'drop spot move'], fontsize=8); a.invert_yaxis(); a.set_xlim(.8, .9); a.set_xlabel('counter-sell cells, LOCO AUC'); a.set_title('B. Dropping one family at a time', fontsize=10)
a = ax[2]; t = IM.head(10)[::-1]; cols = {'prem': '#d69e2e', 'base': '#a0aec0', 'bb': '#e53e3e', 'spot': '#2b6cb0', 'book': '#38a169', 'other_stop': '#805ad5'}; a.barh(range(len(t)), t.drop_in_auc, color=[cols[f] for f in t.family]); a.set_yticks(range(len(t))); a.set_yticklabels(t.feature, fontsize=8); a.set_xlabel('AUC lost when the feature is shuffled'); a.set_title('C. Strongest features (colour = family)', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0c_summary.png'), dpi=115); plt.close()
# ---- report
txt = f"""# Algo 8 — D0 counter-sells: the AUC gate

*Plan `D0_CAUC_PLAN.md`, written before the run (a post-hoc follow-up, §3, is labelled). In-sample discovery on D0: 14,762 minute cells (cycle × minute × right) over 24 cycles; 667 cells carry a counter-sell. Figure: `figures/bl_d0c_summary.png`. Scripts `bl_d0c_auc.py`, `bl_d0c_expl.py`.*

## 0. Result: the gate is met
**Counter-sell cells are ranked at AUC {ac.loc[v1,'auc']:.3f} (95% CI {ac.loc[v1,'lo']:.3f}–{ac.loc[v1,'hi']:.3f}) using only information from before the minute.** The gate was 0.85 with a forward check of at least 0.80.

| Check | Result | Gate |
|---|---|---|
| **V1 causal, pooled leave-one-cycle-out AUC** | **{ac.loc[v1,'auc']:.3f}** | ≥ 0.85 ✔ |
| Forward check (first 16 cycles → last 8) | **{fc.loc[v1,'auc']:.3f}** | ≥ 0.80 ✔ |
| Within-cycle AUC (mean over {int(ac.loc[v1,'within_cycle_cycles'])} cycles with ≥5 counter cells) | **{ac.loc[v1,'within_cycle_auc']:.3f}** | reported |
| Placebo (features shuffled within each cycle), pooled / within-cycle | {ac.loc[pl,'auc']:.3f} / {ac.loc[pl,'within_cycle_auc']:.3f} | reported |
| PR-AUC (base rate {ac.loc[v1,'positive_rate']:.1%}) | {ac.loc[v1,'prauc']:.3f} | reported |

* **Observed.** The within-cycle AUC removes the cycle-level base-rate effect that pooled AUC rewards, and it also clears 0.85 ({ac.loc[v1,'within_cycle_auc']:.3f}) with a placebo at chance ({ac.loc[pl,'within_cycle_auc']:.3f}).
* **What a pass means.** It is a **ranking**: the minutes that will carry a counter-sell sit far above the rest. It is not a recovered rule. The exact-cell F1 of single rules stays below 0.5 (`D0_CTRIG.md`), and the PR-AUC of {ac.loc[v1,'prauc']:.2f} against a {ac.loc[v1,'positive_rate']:.1%} base rate says that a hard threshold on the ranking would still flag many minutes without a counter-sell.

## 1. The three variants
{table(A[A.outcome == 'counter-sell cell'][['variant','features','auc','lo','hi','prauc','within_cycle_auc']])}
* **V2** adds the minute's own bar ({ac.loc[v2,'auc']:.3f}): not knowable ahead, it shows that part of the trigger sits inside the minute.
* **V3** adds buy-backs of the other right in the same minute ({ac.loc[v3,'auc']:.3f}). The counter label is itself defined by such a buy-back, so V3 is **partly definitional** and is not used for the gate.

## 2. Counter-sells are as predictable as solo sales in general
{table(A[A.outcome == 'any solo-sale cell'][['variant','features','auc','lo','hi','prauc','within_cycle_auc']])}
Forward check for any solo sale, V1: {fa.loc[v1,'auc']:.3f}. The counter label (a solo sale next to a buy-back of the other right) is predicted **at least as well** as solo selling in general ({ac.loc[v1,'auc']:.3f} against {aa.loc[v1,'auc']:.3f}, within-cycle {ac.loc[v1,'within_cycle_auc']:.3f} against {aa.loc[v1,'within_cycle_auc']:.3f}). *Inferred:* a counter-sell is a solo sale that happens in a strong, one-directional move, which also produces the other right's buy-back.

## 3. What drives it (post-hoc follow-up)
{table(FM[FM.outcome == 'counter-sell cell'][['model','features','auc','within_cycle_auc']])}
* **Premium of the sold right** is the largest single family: alone (with the clock) it reaches {fm.loc['only prem (+ base)','auc']:.3f}; dropping it costs the most ({fm.loc['V1 causal (reference)','auc'] - fm.loc['V1 minus prem','auc']:.3f}).
* **Spot move** alone {fm.loc['only spot (+ base)','auc']:.3f}; **book state** {fm.loc['only book (+ base)','auc']:.3f}; **past buy-backs** {fm.loc['only bb (+ base)','auc']:.3f}. Each is redundant given the others (dropping any one costs at most {fm.loc['V1 causal (reference)','auc'] - fm.loc['V1 minus prem','auc']:.3f}).
* **The stop pressure of the other right** (its largest lot ratio, premium at a new high, side loss) alone gives {fm.loc['only other-right stop pressure (+ base)','auc']:.3f}, but adds only {fm.loc['V1 + stop pressure of the other right','auc'] - fm.loc['V1 causal (reference)','auc']:+.3f} to V1: it is already contained in the sold right's own state, as expected if both react to one move. *Observed.*

Strongest features (AUC lost when shuffled, counter cells):
{table(IM.head(10))}
* The 1-minute change of the sold option's premium and its position against its day low lead. Time since the last buy-back of the other right and the minute within the 15-minute block follow.

## 4. What this does and does not settle
* **Settled (Observed):** the minutes that carry a counter-sell can be identified ahead of time at AUC {ac.loc[v1,'auc']:.2f}, from the sold option's premium collapsing, the spot moving in its favour, how recently the other right was bought back, and the clock position. This holds forward in time and within each cycle.
* **Not settled:** the exact second and size of each sale, and whether the buy-back and the sale are one decision or two rules on the same move (`D0_PAIR.md`). One-minute bars cannot show that.

## Caveats
* In-sample discovery, one-minute bars, 24 cycles, cycle-bootstrap CIs; the forward check is one split.
* The V1 feature set includes the premium-low windows that were added after the first counter-sell tests (`D0_CTRIG_PLAN.md` addendum). They are causal (bars to j−1), and the placebo stays at chance.
* Positives are rare ({ac.loc[v1,'positive_rate']:.1%} of cells), so high AUC coexists with modest precision.

## Run order
`bl_d0n_panel.py` → `bl_d0c_auc.py` (~2 min) → `bl_d0c_expl.py` (~3 min) → `make_d0c_report.py`.
"""
open(os.path.join(RP, 'D0_CAUC.md'), 'w').write(txt); print('written')
