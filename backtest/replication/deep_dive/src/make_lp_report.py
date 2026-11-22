"""Builds reports/D1_LUMP.md from bl_lp_* outputs and bl_summary_lp2-6.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); L2, L3, L5, L6 = J('lp2'), J('lp3'), J('lp5'), J('lp6'); H6b = J('hg6b')
pct = lambda x: f'{100 * x:.0f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv').reset_index().rename(columns={'index': 'cid'}); D = pd.read_csv(f'{OUT}/bl_lp_dec.csv').merge(CY[['cid', 'd1']], on='cid'); M = D[D.main == 1]; T = D[D.main == 0]
reg = lambda d: 'until 2026-08-05' if d <= '2026-08-05' else ('2026-08-12 to 08-19' if d <= '2026-08-19' else 'from 2026-08-24')
M = M.assign(regime=M.d1.map(reg)); tm = M.groupby('regime', sort=False).agg(cycles=('cid', 'size'), first=('hhmmss', 'min'), last=('hhmmss', 'max')).reset_index()
SZ = pd.read_csv(f'{OUT}/bl_lp_size.csv'); SZ = SZ.assign(median_abs_err_pct=SZ.median_abs_err_pct.round(0), MAE_lots=SZ.MAE_lots.round(1), within_5_lots=SZ.within_5_lots.map(pct), within_10_lots=SZ.within_10_lots.map(pct))
ST = pd.read_csv(f'{OUT}/bl_lp_strike.csv'); ST = ST.assign(exact=ST.exact.map(pct), within1=ST.within1.map(pct)); ST['rule'] = ST.rule.map({'pct': '% OTM of spot', 'sigma': 'σ√T units (ATM straddle)', 'premium': 'premium = k × ATM same-right price', 'delta': 'delta target'})
rat = M.assign(r=M.lots / M.S_h).groupby('und').r.median(); Q = pd.read_csv(f'{OUT}/bl_lp_d0.csv'); f = lambda h: f'{int(h):02d}:{int(round((h % 1) * 60)):02d}'
txt = f"""# Algo 8 — the overnight lump (`v_`): trigger, structure, size and fate

*Exploratory follow-up of `D1_LONG_SIDE.md`, done at the user's request. **No plan was written before these steps**, so every result here is post-hoc and in-sample: {len(M)} cycles with a lump, out of 32. Figure: `figures/bl_lp_summary.png`.*

## 0. Result
| Question | Answer | Evidence |
|---|---|---|
| **Trigger: when** | A **clock**, with three regimes that change on fixed dates: 15:06–15:14 until 2026-08-05, 15:23–15:24 for 2026-08-12 to 08-19, and **15:30–15:35 from 2026-08-24**. These look like code or config changes, not a market signal. | Observed (date steps) |
| **Trigger: whether** | A lump is placed when shorts are carried overnight. The two cycles without one: a book already flat at 14:46 (stopped out), and a book with only 34 heavy-side shorts. Other small heavy sides also got tiny lumps (34 → 1 lot, 35 → 9 lots). | Observed |
| **Which side** | The **heavier short side** (more short lots), only that side in 80% of cycles. | Observed |
| **Order structure** | One decision, split into exchange freeze-quantity chunks: **27 lots for NIFTY (27 × 65 = 1,755) and 50 lots for SENSEX (50 × 20 = 1,000)**. All are IOC at one strike, sometimes with 1–2 small top-ups later ({len(T)} top-ups). | Observed |
| **Strike** | About **2.2 σ√T OTM** using the ATM straddle (median {M.otm_pct.median():.1f}% of spot). Best rule: {ST.iloc[1].exact} exact, {ST.iloc[1].within1} within one strike. A fixed % of spot gives {ST.iloc[0].exact}. | Observed, rule partial |
| **Size** | Roughly **{rat['NIFTY']:.2f} × heavy-side shorts (NIFTY), {rat['SENSEX']:.2f} × (SENSEX)**. No tested rule does better than about **±13 lots (≈ 24% median error)** out-of-cycle. | **Unresolved** |
| **What it does** | Before the lump, a move in the heavy direction loses a median ₹{-L2['median']['worst_pre'] / 1e5:.0f} L within 6% (intrinsic). After it, the worst loss is a median ₹{-L2['median']['worst_post'] / 1e5:.0f} L: the tail is roughly halved and becomes much more uniform across cycles (coefficient of variation {L2['cv']['worst_pre']:.2f} → {L2['cv']['worst_post']:.2f}). It is **not** a delta hedge (it removes about {H6b['ratio_q']['0.5'] * 100:.0f}% of book delta). | Observed |
| **D0 fate** | The `v_` module itself sells lump lots on D0 in **{int((Q.sold_d0 > 0).sum())} of {len(Q)} cycles** ({pct(L6['d0']['share_sold_d0'])} of lump lots), from {f(L6['d0']['first_sale_q']['0.5'])} (median first sale) to {f(L6['d0']['last_sale_q']['0.5'])} (median last), at a median **{L6['d0']['sell_over_buy_median'] * 100:.0f}% of the purchase price**, never above it. Modules share contracts: counting every module, {pct(L6['d0_contracts']['fully_closed_any_module'])} of lump contracts are fully closed on D0. So the remaining lots are sold by the body, hedge or stop streams; they do not expire. | Observed |

**Reading (inferred):** the lump is end-of-day **gap insurance** on the side that would lose most from an overnight move. It is placed at a clock time, about 2 σ√T out, and sized roughly in proportion to the heavy-side shorts. It costs about ₹{H6b['rs_q']['0.5'] / 1e3:.0f}k per cycle (median) and in every cycle where `v_` sold it, it recovered at most about half its premium (median 7%): the cost of protection against a gap that did not happen in this sample.

## 1. Timing regimes (main decisions)
{table(tm)}

## 2. Size: everything tried (none decodes it)
| Hypothesis | Result |
|---|---|
| Fixed share of heavy-side shorts | NIFTY {rat['NIFTY']:.2f}, SENSEX {rat['SENSEX']:.2f}; leave-one-cycle-out error about 14 lots |
| Subset of heavy-side shorts (by sell type, moneyness or time sold; non-negative weights) | MAE 13.5–14 lots; no subset gets weight ≈ 1 with the others ≈ 0 |
| Rupee budget (MTM P&L, gross/net premium, heavy-side premium or mark) | spend ÷ budget coefficient of variation ≥ 0.44: rejected |
| Fixed worst-case loss cap (loss after the lump) | tighter (CV {L2['cv']['worst_post']:.2f}) but ₹10–21 L: not a fixed cap |
| Equalising the heavy and light tails (margin-style) | after the lump, the heavy tail is still about {L5['R4']['post_over_light_median']:.1f}× the light tail: rejected |
| Overnight delta neutralisation | removes about {H6b['ratio_q']['0.5'] * 100:.0f}% of book delta: rejected |

Log-linear size models, leave-one-cycle-out:

{table(SZ)}

The strongest single association is the **intrinsic loss at the lump strike** (Spearman 0.80 with lots). That is the loss the book would take if the spot moved exactly to the lump strike. As a model it still leaves about ±13 lots. The real input is probably something the ledger does not contain, such as broker margin (SPAN) or a risk figure from the algorithm's own valuation. *Not testable.*

## 3. Strike rule (out-of-fold, all decisions)
{table(ST)}

## 4. D0 fate (`v_` module's own sales; other modules also close these contracts, see §0)
{table(Q.assign(first_sale=Q.first_sale.map(lambda h: f(h) if h == h else ''), last_sale=Q.last_sale.map(lambda h: f(h) if h == h else '')).round(2))}

## Evidence labels
* **Observed:** timing regimes, side, chunking, D0 fate, tail effect.
* **Inferred:** the gap-insurance purpose; code-change regimes.
* **Unresolved:** exact size and exact strike.
* **Not testable:** broker margin and the system's own risk numbers.
* Everything here is post-hoc and in-sample.
"""
open(f'{RP}/D1_LUMP.md', 'w').write(txt); print('ok')
