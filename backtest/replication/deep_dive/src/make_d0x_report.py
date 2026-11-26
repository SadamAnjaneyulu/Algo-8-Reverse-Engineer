"""Builds reports/RECONSTRUCTION_GAP.md from outputs/d0x/* and outputs/postcas/* (entry / exit / sizing gap vs the real Algo 8, and the anti-overfitting protocol)."""
import os, json, numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); DX = f'{OUT}/d0x'; RP = os.path.join(os.path.dirname(OUT), 'reports')
def _md(d):
    f = lambda v: ('' if pd.isna(v) else (f'{v:,.0f}' if isinstance(v, (float, np.floating)) and abs(v) >= 100 else (f'{v:.2f}' if isinstance(v, (float, np.floating)) else str(v))))
    return '| ' + ' | '.join(map(str, d.columns)) + ' |\n|' + '---|' * len(d.columns) + '\n' + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
G = pd.read_csv(f'{DX}/gap_decomposition.csv'); B = pd.read_csv(f'{DX}/book_compare.csv'); FA = pd.read_csv(f'{DX}/fixA_eval.csv'); LF = pd.read_csv(f'{DX}/late_fire_check.csv'); P = pd.read_csv(f'{OUT}/postcas/diag_cycles.csv')
pr = P[P.src == 'real']; inc = pr[~pr.set_index(['und', 'expiry']).index.isin(G.set_index(['und', 'expiry']).index)]
g = G.groupby('era')[['real_total', 'sim_d0_from_real_book', 'freerun', 'gap_total', 'gap_d0_logic', 'gap_d1_book']].mean(); g['cycles'] = G.groupby('era').size(); g = g.reset_index()
cols = ['short_total', 'short_CE', 'short_PE', 'short_offset_mean', 'long_total', 'd1_cash']
bk = pd.concat({s: B.groupby('era')[[f'{c}_{s}' for c in cols]].mean().set_axis(cols, axis=1) for s in ('real', 'sim')}).reset_index().rename(columns={'level_0': 'book'})
lf = LF.groupby('era')[['late_sale_minutes', 'extended_fires', 'fires_after_1515', 'fires_matched', 'random_matched']].sum().reset_index(); lf['precision'] = lf.fires_matched / lf.extended_fires; lf['random precision'] = lf.random_matched / lf.extended_fires
md = f"""# Why the simulator earns less than the real Algo 8 — entry, exit and sizing, and how to stop overfitting

*Exploratory diagnosis on the real log (35 cycles, Jun – Oct 2026) vs the simulator. No rule was adopted in this step. Scripts: `bl_d0x_diag.py`, `bl_d0x_book.py`, `bl_d0x_fixA.py`.*

## 1. The "₹56k vs ₹24.5k" premise was wrong
* The ₹56k real expiry-day figure included **4 post-auction cycles whose real log is missing a whole day** (no D-1 fills, or no D0 fills). Their "real" results are marks, not trades: 11 Aug (+₹3.0 lakh, no D-1 fills), 15 Sep (+₹4.5 lakh, no D-1 fills), 29 Sep (+₹4.9 lakh, no D0 fills), 1 Sep (−₹1.4 lakh, stopped on D-1, no D0 fills).
* On the **19 complete post-auction cycles**, real Algo 8 makes **₹{g.loc[g.era == 'after', 'real_total'].iloc[0]:,.0f} per cycle** (both days). The free-running simulator makes ₹{g.loc[g.era == 'after', 'freerun'].iloc[0]:,.0f}. The gap is real (₹{g.loc[g.era == 'after', 'gap_total'].iloc[0]:,.0f}), but it is half of what the incomplete data suggested.

## 2. Where the gap comes from (complete cycles)
"D0 from real book" = the simulator's expiry-day logic started from the **real** overnight book.
{_md(g.rename(columns={'real_total': 'real (₹)', 'sim_d0_from_real_book': 'sim D0 from real book (₹)', 'freerun': 'sim free-run (₹)', 'gap_total': 'gap real − free-run', 'gap_d0_logic': 'of which D0 logic', 'gap_d1_book': 'of which overnight book'}))}

* **Expiry-day entry / exit logic is not what loses money after the auction**: given the real overnight book it earns **more** than the real system (it gives back ₹{-g.loc[g.era == 'after', 'gap_d0_logic'].iloc[0]:,.0f} of the gap).
* **The overnight book the simulator builds on D-1 is the problem** (₹{g.loc[g.era == 'after', 'gap_d1_book'].iloc[0]:,.0f} per cycle): with the same D0 rules, a different carried book produces a very different expiry day (and a different cycle-stop path).
* Before the auction the errors run the other way and roughly cancel.

## 3. How the overnight books differ (means per cycle at the D-1 close)
{_md(bk.rename(columns={'short_total': 'short lots', 'short_CE': 'short calls', 'short_PE': 'short puts', 'short_offset_mean': 'short strike, steps OTM', 'long_total': 'long lots (wings)', 'd1_cash': 'D-1 premium cash (₹)'}))}

After the auction the real book is **larger (+16 short lots), more call-heavy, placed further out of the money (1.4 vs 0.5 steps) and carries more wings**. The extra size comes from **late D-1 selling**: real short lots per cycle 14:15–14:59 = 16.6 (simulator 13.2), 15:00–15:14 = 7.2 (3.6), **15:15–15:29 = 14.4 (1.7)**, **15:30–15:40 = 6.4 (0)** — options trade until 15:40 since the auction; the simulator's breakout window ends at 15:15 and its data end at 15:29.

## 4. Fix tested: extend the D-1 breakout window after the auction (no fitted parameter)
Decision-level check first (extended breakout fires vs real late sale minutes, ±1 minute):
{_md(lf)}

End-to-end on the complete cycles:
{_md(FA.rename(columns={'real_mean': 'real (₹)', 'sim_mean': 'sim (₹)', 'mae': 'mean abs. error (₹)', 'carried_short_sim': 'carried short sim', 'carried_short_real': 'carried short real', 'late_short_sim': 'late shorts sim', 'late_short_real': 'late shorts real'}))}

**Rejected.** Decisions move towards the real ones (late shorts 5.3 → 11.5 vs 21.6; carried book 91 → 97 vs 107) but the P&L moves away (−₹24.8k → −₹63.1k vs +₹26.0k real). Copying **how much** the real system sells late, without copying **which strikes and sides** it sells, makes things worse. The missing rule is about **strike and side selection in the late session**, not volume.

## 5. Why every fix keeps overfitting — and the protocol that stops it
**Why:** 19 complete post-auction cycles; each cycle's P&L depends on dozens of interacting decisions; any rule tuned to make those 19 P&L numbers match will fit noise. The 16 Sep – 22 Oct cycles have now been inspected cycle by cycle: they are **contaminated** as validation data.

**Protocol for every further reconstruction change (binding from now):**
1. **Fit decisions, never P&L.** Targets are order-level: which minute sells, which side, which strike offset, how many lots, which lots are bought back and when (thousands of observations, not 19).
2. **Teacher-forced scoring.** Each day is simulated from the **real** state at its start (real D-1 open book, real carried book for D0), so a rule is judged on its own decisions, not on compounded earlier errors.
3. **Cross-validation by cycle.** Any constant estimated from data is estimated leave-one-cycle-out; a rule is kept only if its decision accuracy holds out-of-fold.
4. **Complexity budget.** At most one new parameter per rule, each with a market-structure or log-level reason written down before testing.
5. **P&L only at the end, once.** Free-run P&L fidelity is checked after decisions are frozen; it can reject a rule, never tune one.
6. **Clean hold-out from the future.** The 35 real cycles are now development data. The next ≥ 30 real cycles (forward log) are locked as the validation set before anyone looks at them.
7. **Ledger.** Every variant tried is recorded (`outputs/d0x/`, this report) and counted in the Deflated Sharpe / PBO of the final strategy.

## 6. What to do next
* **Late D-1 strike / side rule:** build the decision table for real late sales (minute, side, strike offset from ATM and from the last sale, book imbalance, premium) and fit it teacher-forced with leave-one-cycle-out — this is the most likely missing piece (Section 3).
* **Extend the data cache to 15:39** (raw option bars exist) so the 15:30–15:40 session can be simulated at all.
* **Collect the forward log** for the clean hold-out; until then no reconstruction change can be validated, and the battery verdict (NO-GO) stands.
"""
open(f'{RP}/RECONSTRUCTION_GAP.md', 'w').write(md); print('ok')
