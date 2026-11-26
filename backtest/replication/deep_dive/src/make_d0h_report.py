"""Builds reports/D0_HEDGE.md and figures/bl_d0h_summary.png from the chunk-3 outputs (bl_d0h_*.csv, bl_summary_d0h1/2.json)."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R1 = json.load(open(f'{OUT}/bl_summary_d0h1.json')); R2 = json.load(open(f'{OUT}/bl_summary_d0h2.json'))
H2 = pd.read_csv(f'{OUT}/bl_d0h_h2.csv'); H2B = pd.read_csv(f'{OUT}/bl_d0h_h2b.csv'); H6 = pd.read_csv(f'{OUT}/bl_d0h_h6.csv'); AU = pd.read_csv(f'{OUT}/bl_d0h_auc.csv'); W = pd.read_csv(f'{OUT}/bl_d0h_waves.csv'); LP = pd.read_csv(f'{OUT}/bl_d0h_lump.csv')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
h1 = R1['H1']; h3 = R1['H3']; h2 = R1['H2']; t1 = R2['3b_T1']; h6 = R1['H6']; h7 = R1['H7']; h5 = R1['H5']; A = AU.set_index(['target', 'variant']).AUC
tf = 'teacher-forced: gap at minute start + same-minute body lots + clock'; ca = 'causal: gap and body lots of the previous minute + clock'
# ---------------- figure
fig, ax = plt.subplots(1, 3, figsize=(17, 5))
b = [('buy waves\n= gap S−L', h1['buy']['equals_gap']), ('buy waves = gap\n(lump not in L)', h1['buy']['equals_gap_excl_v']), ('sell waves\n= gap', h1['sell']['equals_gap']), ('lump sale lots\nwhile L > S', t1['v_']['lots_while_L_gt_S']), ('lump waves\n≤ excess L−S', t1['v_']['le_excess'])]
ax[0].bar(range(len(b)), [x[1] for x in b], color=['#2b6cb0', '#cbd5e0', '#2b6cb0', '#48bb78', '#48bb78']); ax[0].set_xticks(range(len(b))); ax[0].set_xticklabels([x[0] for x in b], fontsize=8)
for k, x in enumerate(b): ax[0].text(k, x[1] + .01, f'{x[1]:.0%}', ha='center')
ax[0].set_ylim(0, 1.1); ax[0].set_title('Hedge controller on D0 (long lots = short lots per right)', fontsize=10)
x = H2[~H2.X.astype(str).str.contains('OOF')].copy(); x['X'] = x.X.astype(float); ax[1].plot(x.X * 100, x.exact, marker='o', label='exact strike'); ax[1].plot(x.X * 100, x.within1, marker='o', label='within one strike'); ax[1].axhline(.1, color='gray', ls=':', lw=.8); ax[1].axhline(.3, color='gray', ls='--', lw=.8)
ax[1].set_xlabel('wing premium target, % of the ATM same-right premium'); ax[1].legend(fontsize=8); ax[1].set_title('Wing strike: premium nearest X% of ATM (chance dotted/dashed)', fontsize=10)
lp = LP.assign(h=(LP.tod // 3600).astype(int)).groupby('h').lots.sum(); ax[2].bar(lp.index, lp.values, color='#ed8936'); ax[2].set_xlabel('hour (D0)'); ax[2].set_ylabel('lump lots sold'); ax[2].set_title(f"Lump salvage (v_ sells): {h6['lots']} lots, median {h6['ratio_q'][2]:.0%} of D-1 cost", fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0h_summary.png'), dpi=130)
oo = h2['oof']; dec = pd.DataFrame([
    ('Controller: buy the gap S − L per right (D-1 rule unchanged)', f"buy waves = gap {h1['buy']['equals_gap']:.0%}, sell waves {h1['sell']['equals_gap']:.0%}; sign {h1['buy']['sign_right']:.0%} / {h1['sell']['sign_right']:.0%}", 'kept', 'Observed'),
    ('Lump longs count in L on D0', f"{h1['buy']['equals_gap']:.0%} with the lump in L vs {h1['buy']['equals_gap_excl_v']:.0%} without", 'kept (differs from D-1)', 'Observed'),
    ('Controller delay', f"median {R1['H4_dt_body_q_buy'][2]:.1f} s after the body order (IQR {R1['H4_dt_body_q_buy'][1]:.1f}–{R1['H4_dt_body_q_buy'][3]:.1f})", 'kept', 'Observed'),
    ('Wing strike: premium nearest 2.5% of ATM', f"exact {h2['d1_rule_2p5']['exact']:.0%}, ±1 {h2['d1_rule_2p5']['within1']:.0%} (chance 10% / 30%); refit picks 2.5% in both halves", 'kept, weaker than D-1 (65% / 93%)', 'Observed'),
    ('Wing strike: fixed ₹, fixed steps, % of last sold premium (post-hoc)', ' / '.join(f"{r.reference} {r.exact_oof:.0%}" for r in H2B.itertuples() if r.reference != 'pct_atm'), 'rejected', 'Observed'),
    ('Release: outermost or cheapest wing', f"{h3['outermost']:.0%} / {h3['cheapest']:.0%} vs chance {h3['chance']:.0%}", 'kept as preference', 'Observed'),
    ('Lump sales are controller releases (post-hoc)', f"{t1['v_']['lots_while_L_gt_S']:.1%} of lump lots sold while L > S; waves ≤ excess {t1['v_']['le_excess']:.0%}", 'kept', 'Observed'),
    ('Lump timing rules (clock, first L > S, end of body)', f"F1 ≤ {H6.F1.max():.2f}", 'rejected: which long is released (wing vs lump) is unresolved', 'Observed'),
], columns=['rule', 'result', 'decision', 'evidence'])
txt = f"""# Algo 8 — D0 chunk 3: hedge wings, lump salvage, body-stream longs

*Plan `D0_HEDGE_PLAN.md` (addendum 3b written after H1–H7, before its tests). In-sample: D0 of the 30 cycles with both logs. Positions include the book carried from D-1. Figure: `figures/bl_d0h_summary.png`.*

## 0. Result
* **The D-1 hedge controller runs unchanged on D0.**
  * Every long-buy wave equals the gap S − L on its right in **{h1['buy']['equals_gap']:.0%}** of {h1['buy']['waves']:,} waves; sell waves {h1['sell']['equals_gap']:.0%}.
  * It acts a median **{R1['H4_dt_body_q_buy'][2]:.1f} s** after the body order (D-1: about 4 s).
  * Hedge AUC: **{A[('h_ buy', tf)]:.3f}** (buys) and **{A[('h_ sell', tf)]:.3f}** (sells) given the real body orders; **{A[('h_ buy', ca)]:.3f} / {A[('h_ sell', ca)]:.3f}** using only the previous minute.
* **One change from D-1: on D0 the overnight lump counts as hedge.**
  * The gap matches with the lump longs in L ({h1['buy']['equals_gap']:.0%}), not without them ({h1['buy']['equals_gap_excl_v']:.0%}).
  * **The lump is sold off by the controller.** {t1['v_']['lots_while_L_gt_S']:.1%} of lump lots are sold while long lots exceed short lots on that right; 99% of lump sale waves are no larger than that excess.
  * It goes in {h6['orders_per_cycle_q'][1]:.0f} pieces per cycle (median), at a median {h6['ratio_q'][2]:.0%} of its D-1 cost.
  * *When* a lump lot is released rather than a wing is **unresolved**: simple timing rules score F1 ≤ {H6.F1.max():.2f}.
* **Wing strike:** the 2.5%-of-ATM rule still fits best, but less tightly than on D-1. Exact {h2['d1_rule_2p5']['exact']:.0%} and ±1 strike {h2['d1_rule_2p5']['within1']:.0%} (D-1: 65% / 93%; chance 10% / 30%).
* **Releases** prefer the outermost or cheapest wing ({h3['outermost']:.0%} / {h3['cheapest']:.0%} vs chance {h3['chance']:.0%}), as on D-1.
* **Body-stream longs:**
  * D0 opens with pre-bought far wings, as D-1 does: {h7['09:15-09:17_open_long']['lots']} lots in {h7['09:15-09:17_open_long']['cycles']} cycles, median {h7['09:15-09:17_open_long']['otm_steps_med']:.0f} steps OTM;
  * body-stream long sales during the day: {h7['other_close_long']['lots']} lots (median {h7['other_close_long']['otm_steps_med']:.0f} steps OTM);
  * {h7['15:09+_close_long']['lots']:,} lots are sold at 15:09+ (chunk 4).

## 1. Controller (H1, H4)
| wave | waves | lots | = gap S − L | = gap, lump not in L | sign right |
|---|---|---|---|---|---|
| buy | {h1['buy']['waves']:,} | {h1['buy']['lots']:,} | {h1['buy']['equals_gap']:.1%} | {h1['buy']['equals_gap_excl_v']:.1%} | {h1['buy']['sign_right']:.1%} |
| sell | {h1['sell']['waves']:,} | {h1['sell']['lots']:,} | {h1['sell']['equals_gap']:.1%} | {h1['sell']['equals_gap_excl_v']:.1%} | {h1['sell']['sign_right']:.1%} |

* By hour, buy waves equal the gap in {min(h1['by_hour_equals_gap'].values()):.0%}–{max(h1['by_hour_equals_gap'].values()):.0%} of cases.
* Delay after the body order (10/25/50/75/90%):
  * buys {', '.join(f'{v:.1f}' for v in R1['H4_dt_body_q_buy'])} s;
  * sells {', '.join(f'{v:.1f}' for v in R1['H4_dt_body_q_sell'])} s.

## 2. Wing strike (H2, addendum 3b-T2)
{table(H2)}

**Other references** (refit on one half, exact share on the other):

{table(H2B)}

## 3. Releases (H3) and lump salvage (H6, 3b-T1)
* **Release choice** ({h3['n']:,} sells with ≥ 2 long strikes held), share by rule:
  * outermost {h3['outermost']:.0%}, cheapest {h3['cheapest']:.0%};
  * oldest {h3['oldest']:.0%}, newest {h3['newest']:.0%};
  * nearest 2.5% {h3['near_2p5_atm']:.0%}, innermost {h3['innermost']:.0%}, dearest {h3['dearest']:.0%};
  * chance {h3['chance']:.0%}.
* **Lump sales:**
  * {h6['lots']} lots in {h6['cycles']} cycles, of {R2['lump_carried_lots']:,} lump lots carried. The rest leave in the clearance or the stop (chunk 4).
  * First sale per cycle: 10/50/90% at {', '.join(f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}' for t in h6['first_sale_q'])}.
  * Sale price / D-1 cost (10/50/90%): {h6['ratio_q'][0]:.1%} / {h6['ratio_q'][2]:.1%} / {h6['ratio_q'][4]:.1%}.
* **Are lump sales controller releases?**

| module | sell waves | lots | wave = excess L − S | wave ≤ excess | lots sold while L > S |
|---|---|---|---|---|---|
| h_ (wings) | {t1['h_']['waves']:,} | {t1['h_']['lots']:,} | {t1['h_']['equals_excess']:.0%} | {t1['h_']['le_excess']:.0%} | {t1['h_']['lots_while_L_gt_S']:.1%} |
| v_ (lump) | {t1['v_']['waves']:,} | {t1['v_']['lots']:,} | {t1['v_']['equals_excess']:.0%} | {t1['v_']['le_excess']:.0%} | {t1['v_']['lots_while_L_gt_S']:.1%} |

**Lump timing rules:**

{table(H6)}

* The rules fail because the controller releases wings **and** lump lots from the same excess. Which one it picks is the unresolved part.

## 4. `h_` shorts (H5) and body-stream longs (H7)
* **`h_` shorts and covers.** {h5['by_role'].get('open_short', 0)} short lots and {h5['by_role'].get('cover_short', 0)} cover lots, in {h5['cycles']} cycles. The shorts are almost all in the 09:00 hour; the covers are at 09:xx and after 14:00. *Descriptive.*
* **Body-stream longs:**

| window | role | lots | orders | median steps OTM | cycles |
|---|---|---|---|---|---|
""" + ''.join(f"| {k.rsplit('_', 2)[0] if k.count('_') > 1 else k} | {'buy' if k.endswith('open_long') else 'sell'} | {v['lots']} | {v['orders']} | {v['otm_steps_med']:.1f} | {v['cycles']} |\n" for k, v in h7.items()) + f"""
## 5. Hedge AUC (H8)
{table(AU)}

## 6. Kept and rejected
{table(dec)}

## 7. Caveats
* **In-sample:** 30 cycles. Out-of-fold for the wing-strike refits.
* **Teacher-forced:** the H8 AUC uses the real gap and the real body orders.
* **Post-hoc:** addendum 3b (lump as release, other strike references) was written after H1–H7.

## Run order
`bl_d0h_tests.py` → `bl_d0h_more.py` (~2 min) → `make_d0h_report.py`. Outputs `outputs/bl_d0h_*`, `bl_summary_d0h1/2.json`.
"""
open(os.path.join(RP, 'D0_HEDGE.md'), 'w').write(txt); print('written', len(txt))
