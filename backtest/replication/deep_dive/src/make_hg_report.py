"""Builds reports/D1_LONG_SIDE.md from bl_hg_* outputs and bl_summary_hg*.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); H1, H2, H2b, H345, H6, H6b = J('hg1'), J('hg2'), J('hg2b'), J('hg345'), J('hg6'), J('hg6b')
pct = lambda x: f'{100 * x:.0f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
RO = pd.read_csv(f'{OUT}/bl_hg_inv_roles.csv'); RO = RO[RO.role.isin(['open_long', 'close_long'])]
T2 = pd.read_csv(f'{OUT}/bl_hg_strike2.csv'); T2 = T2.assign(exact=T2.exact.map(pct), within1=T2.within1.map(pct), null_same_slot_exact=T2.null_same_slot_exact.map(pct)); T2.columns = ['reference price', 'k (fold 1/2)', 'exact strike', 'within one strike', 'null exact (reference shuffled in slot)']
T1 = pd.read_csv(f'{OUT}/bl_hg_strike.csv'); t1best = T1.iloc[0]; sig = T1[T1.rule.str.startswith('sigma')].iloc[0]; off = T1[T1.rule.str.startswith('fixed')].iloc[0]
L3, L4 = H345['L3'], H345['L4']; L5 = pd.DataFrame(H345['L5']); L5['L_ge_S_before'] = L5.L_ge_S_before.map(pct); L5['otm_steps_median'] = L5.otm_steps_median.round(1)
LS = pd.DataFrame(H6['size_rules']).round(2); LS.columns = ['candidate size', 'lump ÷ candidate (median)', 'q25', 'q75', 'median abs error % (ratio 1)', 'exact', 'Spearman']
txt = f"""# Algo 8 — D-1 long side (protective wings): what was decoded

*Plan `D1_LONG_SIDE_PLAN.md`, written before the tests. In-sample, D-1 of 32 live cycles. Builds on `BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md`. Steps marked post-hoc were added after seeing results. Figure: `figures/bl_hg_summary.png`.*

## 0. Result: four kinds of long orders on D-1
| # | Long order | Lots on D-1 | Rule | Accuracy | Status |
|---|---|---|---|---|---|
| 1 | **Controller wings** (`h_` buys) | {int(RO[(RO.module == 'h_') & (RO.role == 'open_long')].lots.iloc[0]):,} | After each body sale, buy **exactly the gap S − L** (short lots − long lots on that right, all strikes) about 4 s later. So long lots = short lots on each right all day. | Quantity = gap in **{pct(L3['buy']['equals_gap'])}** of {L3['buy']['waves']:,} buy decisions. Quiet-time L = S in **{pct(H1['quiet_balanced_share'])}** of samples (100% from 09:15 to 13:00). | **Solved (quantity, timing)** |
| 1b | Wing **strike** | | The OTM strike whose premium is nearest **2.5% of the ATM option on the same right** (post-hoc). 2.5% of the sold option's price fits worse. | **{T2.iloc[0, 2]} exact, {T2.iloc[0, 3]} within one strike** (null {T2.iloc[0, 4]}). Sold-option reference: {pct(t1best.exact)} exact. | **Mostly solved** |
| 2 | **Wing releases** (`h_` sells, D-1) | {int(RO[(RO.module == 'h_') & (RO.role == 'close_long')].lots.iloc[0]):,} | When shorts fall (buy-backs), sell exactly the excess longs: {pct(L3['sell']['equals_gap'])} of {L3['sell']['waves']} sell decisions. The wing sold is the **outermost or cheapest** held. | Outermost {pct(L4['outermost'])}, cheapest {pct(L4['cheapest'])}, against chance {pct(L4['chance'])}. Innermost {pct(L4['innermost'])}. | Quantity solved; which wing is only a preference |
| 3 | **Pre-bought opening wings** (body stream, 09:16) | 186 | Before each of the first 3 scheduled straddles, the body stream buys 1 far CE + 1 far PE (median {L5[(L5.role == 'open_long') & (L5.window == '09:15-09:17')].otm_steps_median.iloc[0]} strikes OTM, median premium ₹1.4, 10–90%: ₹0.45–8.6), then sells the straddle a second later. 6 lots per cycle (median 6, range 4–8). They are sold back during the day. | 31 of 32 cycles | **Solved (form)**. Purpose inferred: the hedge is in place before the first sale. |
| 4 | **Overnight lump** (`v_`) | {int(RO[RO.module == 'v_'].lots.iloc[0]):,} | Bought 15:09–15:32 (median first order {H6['first_time_q']['0.5']}), on the **heavier short side** only in {pct(H6['only_heavy_side'])} of cycles, {H6['otm_pct_q']['0.5']:.1f}% OTM (10–90%: {H6['otm_pct_q']['0.1']:.1f}–{H6['otm_pct_q']['0.9']:.1f}%), median ₹{H6['px_q']['0.5']:.1f}. At the D-1 close **L − S = lump lots** in {pct(H1['close_gap_equals_v'])} of cycle-rights: the controller leaves the lump alone. | Size: best candidate is the heavier side's short lots (Spearman {LS.Spearman.iloc[0]}), but the median ratio is {LS.iloc[0, 1]} | **Form solved, size not** (details: `D1_LUMP.md`) |

**Protection logic (inferred from the observed rules):**
* Every short is matched one-for-one by a far-OTM long on the same right. The book is an iron butterfly pooled by right.
* The wings are about 15 (NIFTY) to 19 (SENSEX) strikes OTM, at about ₹4.5. That caps the tail loss of every short sold.
* Before the overnight carry, the heavier side gets an extra layer about 1.6% OTM: a gap move in the dangerous direction then turns the book net long beyond that strike.
* The lump is **not** a delta hedge. It always leans against the book delta ({pct(H6b['share_lump_opposes_book_delta'])} of cycles) but removes only about {H6b['ratio_q']['0.5'] * 100:.0f}% of it (median |delta| {H6b['abs_delta_before_median']:.1f} → {H6b['abs_delta_after_median']:.1f} lots). It works as **gap (tail) protection**, not delta neutrality.

## 1. Inventory (D-1, all long-side orders)
{table(RO)}

## 2. Wing strike (L2)
Sample: {H2['n']:,} simple wing buys (one 1-lot body sale on the right in the previous 1.5–10 s, one 1-lot wing). Wing price ÷ body decision price: median {H2['ratio_q']['0.5']:.4f} (quartiles {H2['ratio_q']['0.25']:.4f}–{H2['ratio_q']['0.75']:.4f}).

The "calibrated" price of a strike is its previous-minute close scaled by the chosen wing's decision price over that wing's own minute close. This removes the common staleness of far-OTM minute bars. k is chosen on one cycle half and scored on the other.

{table(T2)}

* The best rule using the sold option's price: {t1best.rule} on {t1best.wing_price} prices, {pct(t1best.exact)} exact (null {pct(H2['null_exact_best'])}).
* σ-distance rules reach {pct(sig.exact)} exact, and a fixed offset from the sold strike {pct(off.exact)}. **Rejected.**
* So the wing is chosen **by premium (about 2.5% of the ATM premium), not by distance**. The remaining misses are within one strike in most cases. They are probably due to stale minute prices of far-OTM strikes; the real rule likely uses live prices (not testable).

## 3. Releases (L4)
{L4['n']} D-1 wing sells with at least 2 long strikes held:
| sold wing is the… | outermost | cheapest | newest | nearest 2.5% ATM | oldest | innermost | dearest | chance |
|---|---|---|---|---|---|---|---|---|
| share | {pct(L4['outermost'])} | {pct(L4['cheapest'])} | {pct(L4['newest'])} | {pct(L4['near_2p5_atm'])} | {pct(L4['oldest'])} | {pct(L4['innermost'])} | {pct(L4['dearest'])} | {pct(L4['chance'])} |

The algorithm releases from the far, cheap end of the wing stack and keeps the inner (more valuable) protection. The exact choice is not deterministic. *Unresolved.*

## 4. Body-stream wings (L5)
{table(L5)}

## 5. Overnight lump size (L6)
{table(LS)}

* Per cycle, lump ₹ cost: median ₹{H6b['rs_q']['0.5']:,.0f} (10–90%: ₹{H6b['rs_q']['0.1']:,.0f}–₹{H6b['rs_q']['0.9']:,.0f}). The coefficient of variation is {H6b['rs_cv']:.2f}, so it is not a fixed rupee budget either (post-hoc).
* NIFTY lumps are often close to the heavier side's short lots; SENSEX lumps are smaller. *Size: unresolved.*
* Panel (d) of the figure leaves out one cycle with 278 heavier-side shorts and a lump of 0 on that side; that cycle's 40 lump lots went on the lighter side.

## 6. Open items
1. Lump size (and the two-sided lumps in {pct(H6['both_sides'])} of cycles).
2. Which wing is released, beyond the outermost/cheapest preference.
3. The 35% of wing strikes that miss on minute data.
4. D-1 wing behaviour after 15:00, when the lump and the late buy-backs overlap: quiet-time balance drops to {pct(H1['quiet_balanced_by_hour']['15'])} in the 15:00 hour because of the intended over-hedge.

## Evidence labels
* **Observed:** inventory; quantity = gap; quiet balance; lump side and timing; L − S = lump at close; opening wings; release preferences.
* **Post-hoc / observed:** the ATM 2.5% reference; the lump delta and budget tests.
* **Inferred:** the protection logic and the purpose of the opening wings.
* **Not testable:** live prices of far-OTM strikes; broker margin.
"""
open(f'{RP}/D1_LONG_SIDE.md', 'w').write(txt); print('ok')
