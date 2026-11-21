"""Builds reports/D1_SELLING_RECONSTRUCTION.md (combined D-1 selling check + verification of the eight stated findings)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); A1, A2, D7, A3, S1, S2 = J('all1'), J('all2'), J('dq7'), J('all3'), J('solo1'), J('solo2')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
T = pd.read_csv(f'{OUT}/bl_all_sells_type.csv'); C = pd.read_csv(f'{OUT}/bl_all_sells_combined.csv'); SR = pd.read_csv(f'{OUT}/bl_all_solo_rules.csv'); WH = pd.read_csv(f'{OUT}/bl_all_solo_where.csv'); CC = pd.read_csv(f'{OUT}/bl_all_sells_cycles.csv')
t1 = T[T.tolerance_min == 1].set_index('sell_type'); c1 = C[C.tolerance_min == 1].set_index('model'); sh = A1['actual_share']; all3 = c1.loc['all three rules vs all D-1 sells']; sr = c1.loc['scheduled + reactive only vs all D-1 sells']
tt = T.copy(); tt = tt.assign(**{k: tt[k].round(3) for k in ('precision', 'recall', 'F1', 'strike_exact_of_matched')}); tt.columns = ['tolerance (min)', 'sell type', 'real lots', 'model lots', 'matched', 'precision', 'recall', 'F1', 'strike exact (matched)']
cc = C.copy(); cc = cc.assign(**{k: cc[k].round(3) for k in ('precision', 'recall', 'F1', 'strike_exact_of_matched')}); cc.columns = ['tolerance (min)', 'model', 'real lots', 'model lots', 'matched', 'precision', 'recall', 'F1', 'strike exact (matched)']
sr_ = SR.copy(); sr_ = sr_.assign(**{k: sr_[k].round(3) for k in ('precision', 'recall', 'F1')}); sr_.columns = ['price used', 'look-back (min)', 'window', 'real solo lots', 'model lots', 'matched', 'precision', 'recall', 'F1']
wh = WH.copy(); wh['share'] = wh.share.map(lambda v: pct(v)); wh['CE_share'] = wh.CE_share.map(lambda v: pct(v)); wh.columns = ['time of day', 'real solo lots', 'share', 'CE share']
C2 = pd.read_csv(f'{OUT}/bl_all2_combined.csv'); T2 = pd.read_csv(f'{OUT}/bl_all2_type.csv'); SRC = pd.read_csv(f'{OUT}/bl_solo_recon.csv'); SST = pd.read_csv(f'{OUT}/bl_solo_strike.csv')
c2 = C2.assign(**{k: C2[k].round(3) for k in ('precision', 'recall', 'F1')}); c2.columns = ['solo model', 'scope', 'real lots', 'model lots', 'matched', 'precision', 'recall', 'F1']
t2 = T2[T2.sell_type == 'solo'].assign(**{k: T2[k].round(3) for k in ('precision', 'recall', 'F1')})[['solo_variant', 'real_lots', 'model_lots', 'matched', 'precision', 'recall', 'F1']]; t2.columns = ['solo model', 'real solo lots (regular)', 'model lots', 'matched', 'precision', 'recall', 'F1']
src_ = SRC.assign(**{k: SRC[k].round(3) for k in ('F1', 'precision', 'recall')}); src_.columns = ['solo model', 'unit', 'F1', 'precision', 'recall', 'parameters (fold 1 / fold 2)']
sst = SST.assign(exact=SST.exact.map(lambda v: pct(v)), within_one_strike=SST.within_one_strike.map(lambda v: '' if v != v else pct(v))); sst.columns = ['solo strike rule', 'exact', 'within one strike']
best2 = C2[C2.scope == 'all D-1 sold lots'].sort_values('F1', ascending=False).iloc[0]; best2x = C2[C2.scope != 'all D-1 sold lots'].sort_values('F1', ascending=False).iloc[0]; sh3 = A3['shares']
best_solo = SR.sort_values('F1', ascending=False).iloc[0]; fe = D7['first_entry']
cy = pd.DataFrame({'sell type': ['scheduled', 'reactive', 'solo'], 'real lots per cycle (mean ± sd)': [f"{CC.actual_scheduled.mean():.1f} ± {CC.actual_scheduled.std():.1f}", f"{CC.actual_reactive.mean():.1f} ± {CC.actual_reactive.std():.1f}", f"{CC.actual_solo.mean():.1f} ± {CC.actual_solo.std():.1f}"], 'model lots per cycle': [f"{CC.pred_scheduled.mean():.1f} ± {CC.pred_scheduled.std():.1f}", f"{CC.pred_reactive.mean():.1f} ± {CC.pred_reactive.std():.1f}", f"{CC.pred_solo.mean():.1f} ± {CC.pred_solo.std():.1f}"], 'Spearman across cycles': [f"{A1['cycle_corr_scheduled'][0]:.2f}" if A1['cycle_corr_scheduled'][0] == A1['cycle_corr_scheduled'][0] else 'n/a (model constant)', f"{A1['cycle_corr_reactive'][0]:.2f}", f"{A1['cycle_corr_solo'][0]:.2f}"]})
txt = f"""# Algo 8 — D-1 selling: how much is reconstructed, all three sell types together

*Check requested before moving to the long side. All D-1 body sell orders of the 32 live cycles ({int(T[T.tolerance_min == 1].actual_lots.sum())} lots). The three decoded rules are run together and every real sold lot is matched one-to-one (same cycle, same right, within ±1 minute). Findings 4–7 (buy-backs) are checked against the earlier reports, not re-run. Figure: `figures/bl_all_sells.png`.*

## 0. Verdict

**D-1 selling is not 100% reconstructed.** First pass (one-line solo rule from your notes): all three rules together reproduce the real D-1 sold lots with **F1 {all3.F1:.2f}** (precision {pct(all3.precision)}, recall {pct(all3.recall)}). **Recalculated with the earlier solo findings (§0A): F1 {best2.F1:.2f}, or {best2x.F1:.2f} excluding deep-OTM batch sells.** By type (first pass):

| Sell type | Share of D-1 sold lots | Lot-level F1 (±1 min) | Status |
|---|---|---|---|
| **1. Scheduled pairs** | {pct(sh['scheduled'])} | **{t1.F1['scheduled']:.2f}** (precision {pct(t1.precision['scheduled'])}, recall {pct(t1.recall['scheduled'])}); strike exact {pct(t1.strike_exact_of_matched['scheduled'])} | **Solved** |
| **2. Reactive pairs** | {pct(sh['reactive'])} | **{t1.F1['reactive']:.2f}** (precision {pct(t1.precision['reactive'])}, recall {pct(t1.recall['reactive'])}); strike exact {pct(t1.strike_exact_of_matched['reactive'])} | **Timing solved, quantity not**: the first entry of each candle-side is reproduced {pct(fe['capture'])} of the time, but repeat entries and the 2–3 lots in some entries are not, so only {pct(t1.recall['reactive'])} of reactive *lots* are matched |
| **3. Solo sells** | {pct(sh['solo'])} | **{t1.F1['solo']:.2f}** with the stated rule (precision {pct(t1.precision['solo'])}, recall {pct(t1.recall['solo'])}); best variant {best_solo.F1:.2f} | **Not solved** — the fresh-extreme rule fires far more often than the real system and misses half the real solo sells |

The scheduled and reactive rules alone are almost never wrong (precision {pct(sr.precision)}), but they cover only {pct(sr.recall)} of the lots sold on D-1. **The open piece is the solo sells — {pct(sh['solo'])} of everything sold on D-1.**

## 0A. Recalculated after recalling the earlier solo studies

The first version of this check scored solo sells with the one-line rule from your notes ("fresh 15-minute high/low"). The earlier studies (`BODY_SELL_TRIGGERS_D1.md`, `BODY_SOLO_SELL_MOVE_TEST.md`, `BODY_SOLO_VARIABLE_SEARCH.md`) found more than that: a **fresh favourable extreme** over 5–60 minutes (CE on a new low, PE on a new high), the **market moving away from that right's shorts**, the **own right's book in profit and the other right's book losing**, repeated **1-lot drips**, and a strike that follows the **premium of the previous sale on that right** rather than ATM. I rebuilt those variables and re-ran the combined check with them (`bl_solo_panel.py`, `bl_solo_recon.py`, `bl_all_sells2.py`). I also separated **deep out-of-the-money batch sells** (≥ 5 strikes from ATM, premiums ₹0.3–5, orders up to 54 lots, all after 14:00, {A3['deep_cycles']} cycles; {pct(sh3['deep-OTM batch'])} of D-1 sold lots) from the regular solo sells — they are a different behaviour that no solo rule describes.

**Recalculated result: all three D-1 sell rules together reach F1 {best2.F1:.2f} on all D-1 sold lots** (precision {pct(best2.precision)}, recall {pct(best2.recall)}; best solo model), **{best2x.F1:.2f} excluding the deep-OTM batches** — up from {all3.F1:.2f} with the one-line solo rule. Scheduled pairs ({pct(sh3['scheduled'])} of lots) F1 {t1.F1['scheduled']:.2f}, reactive pairs ({pct(sh3['reactive'])}) {t1.F1['reactive']:.2f}, **regular solo sells ({pct(sh3['solo'])}) {T2[T2.sell_type == 'solo'].F1.max():.2f}**, deep-OTM batches ({pct(sh3['deep-OTM batch'])}) not modelled.

{table(c2)}
Solo sells alone (regular solo lots, ±1 minute, same right):

{table(t2)}
{table(src_)}
* The earlier variables **rank** minutes very well (gradient-boosting AUC {S1['R2_auc']:.2f} out-of-cycle) but do not turn into a clean yes/no rule: the best rule reaches F1 ≈ 0.43–0.46 by lot and 0.46–0.52 by minute. The best rule out-of-fold is simply a **fresh 60-minute extreme on true highs/lows** (with or without the 30-minute favourable move); the book-ratio thresholds add little.
* Solo strike (all real solo lots with a previous sale on that right):

{table(sst)}
* **So solo selling is understood in direction and context, but not decoded as a rule.** What still separates the solo minutes that sell from the many fresh-extreme minutes that do not, and how many lots each minute gets (the drip and the end-of-day bursts), remain open.

## 1. Your eight findings, checked against the data
| # | Your statement | Verdict | What the data says (source) |
|---|---|---|---|
| 1 | Scheduled: ATM CE+PE every 15 min, no trigger | **Correct on "no trigger"; wrong on "every 15 min"** | A fixed timetable of **33 waves** per D-1 (two versions, V1 to D-1 2026-09-09, V2 from 2026-09-16), each wave = 1 CE + 1 PE lot at the strike nearest the previous minute's close. Waves sit at fixed seconds inside 15-minute blocks, **0–4 waves per block** (lot ladder 3, 2, 3, 1, 4, … per slot), dense in the morning (≈ 8 per hour) and sparse after 12:00 (≈ 2–3 per hour). Each cell fires in ≥ 95% of cycles; no market or book variable changes it (`BODY_SIZING_LOGIC.md`, `BODY_PAIRED_SELL_AND_CLOSE_LOGIC.md`). Reproduced here at F1 {t1.F1['scheduled']:.2f}. |
| 2 | Solo: every minute, fresh low/high of the previous 15 one-minute closes → add a single CE/PE; otherwise nothing | **Direction right, rule incomplete** | A solo **CE follows a fresh low** and a solo **PE a fresh high** (breakout over 5–60 min is the strongest single ingredient; rate 77 vs 9 per 1,000 minutes for 15 min; `BODY_SOLO_VARIABLE_SEARCH.md`), plus the own leg being in profit and the other leg losing (`BODY_SOLO_SELL_MOVE_TEST.md`). But **most fresh extremes get no solo sale**: as a rule it fires {int(t1.loc['solo', 'predicted_lots'])} times against {int(t1.loc['solo', 'actual_lots'])} real solo lots (precision {pct(t1.precision['solo'])}) and still misses {pct(1 - t1.recall['solo'])}. The strike is the premium of the previous sale on that right (48% exact), **not ATM** (strike exact here {pct(t1.strike_exact_of_matched['solo'])}). A quarter of solo lots come after 15:00 and {A2['solo_lots_in_orders_ge3']} lots ({pct(A2['solo_lots_in_orders_ge3'] / t1.loc['solo', 'actual_lots'])} of solo lots) are single orders of ≥ 3 lots (up to 54) — not covered by a per-minute rule. |
| 3 | Lot sizing: controlled in the first half, irregular in the second | **Partly** | Morning selling is the fixed timetable ladder (controlled). After about 12:30 the timetable thins out and reactive pairs (≈ 2.3 per hour) and solo sells (bursts, end-of-day batches) make up most of the volume, so total lots per cycle vary much more (solo {CC.actual_solo.mean():.0f} ± {CC.actual_solo.std():.0f} lots per cycle vs scheduled {CC.actual_scheduled.mean():.0f} ± {CC.actual_scheduled.std():.0f}). "Irregular" is the solo stream, not the pairs (pairs are 1+1 lots in 95% of cases). |
| 4 | Buy-back individually, not as a pair; when premium rises to 1.5–1.7×; 1.7× is the peak | **Individually: correct. "Peak at 1.7": not quite** | Only 8.8% of buy-backs have a same-strike partner within 3 s; the leg's own premium ÷ its own entry decides. The buy-back rate first steps up at **1.4–1.5×** (3.1×) and 1.5–1.6× (4.3×) and **keeps rising** to 672 per 1,000 contract-minutes at 1.7–1.8× — a graded stop that is nearly certain by 1.7–1.8×, not a peak at 1.7 (`BODY_CLOSE_LOGIC.md`). |
| 5 | Positions that never reach 1.2× are mostly carried forward; 61% never reach it | **Correct** | 61% of D-1 sold lots never reach 1.2× on a minute close and 82% of those are carried overnight (`BODY_CLOSE_LOGIC.md`). |
| 6 | 33–40% of buy-backs are below 1.2×; ~36% of them within 3 s of a ≥ 1.5× buy-back, same side, nearby strikes | **Correct** | 33–40% depending on the lot convention; 36% within 3 s of a stop-like buy-back (chance 0.6%), 68% same right, median 2 strikes away (`BODY_CLOSE_LOGIC.md`). |
| 7 | The rest: a sudden adverse move in the previous 1–5 minutes | **Correct as an association, not a rule** | The residual buy-backs follow a fast rise of the lot's own premium / adverse spot move in the last 1–5 min (AUC 0.78–0.85, fading to 0.50 at 60 min); no loss level or % of capital works; 15–21% of all D-1 buy-backs still have **no identified rule** (`BODY_CLOSE_CAPITAL.md`). |
| 8 | Reactive pairs: two-candle breakout | **Correct, with three precisions** | (a) the 30-minute candles are **clock-aligned (hh:00–hh:30, hh:30–hh:00)**, not 09:15-aligned; (b) **once per side per candle** (both sides can fire in the same candle); (c) entries stop at about **15:15**. ATM = the strike nearest the **previous minute's close**. In your example the 11:07 break sells 22,200 CE + PE only if the previous close was nearer 22,150 than 22,200 (e.g. 22,170); with a previous close of 22,180 the ATM is 22,200 and the pair is 22,250. Reproduced: first entry per candle-side {pct(fe['capture'])} ({pct(fe['exact_share'])} exact minute); repeat entries inside a candle (≈ 18% of reactive pair-minutes) and the lot count per entry are **not** decoded (`BODY_REACTIVE_DECODE.md`). |

## 2. Combined match, by type and tolerance
{table(tt)}
{table(cc)}
Lots per cycle, real vs model:

{table(cy)}

## 3. Why solo selling is not done
{table(wh)}
{table(sr_)}
* The fresh-extreme rule, on closes or on true one-minute highs/lows, at any look-back, stays at **F1 ≤ {SR.F1.max():.2f}**: either it fires too often (short look-backs) or misses most sells (long look-backs). The earlier best *probabilistic* model reached AUC 0.86–0.90 — good at ranking minutes, but not a deterministic rule.
* What is missing (from the earlier reports): the own-leg-profit / other-leg-loss conditions, the strike rule (premium of the previous sale on that right), the end-of-day stream after 15:00 ({WH[WH.hour_block == '15:00-15:30'].share.iloc[0]:.0%} of solo lots) and the large batches (up to 54 lots).

## 4. What "D-1 selling done" would need
1. **Solo sells** — a decoded trigger and strike rule (largest gap: {pct(sh['solo'])} of lots).
2. **Reactive quantity** — repeat entries inside a candle and 2–3-lot entries.
3. Nothing further for the scheduled pairs.

## 5. Limits
In-sample; D-1 only; ±1-minute lot matching (exact-minute numbers in §2); lot ownership in a strike is not observable; the scheduled timetable is applied from the observed wave clock of each version (it is a fit of these cycles, not an external specification); findings 4–7 are quoted from earlier reports, not re-run here.

## 6. Files
`src/bl_all_sells.py` (combined simulator and matching) → `bl_all_solo.py` (solo variants, where solo lots sit) → `bl_solo_panel.py` → `bl_solo_recon.py` → `bl_solo_strike.py` (recalled solo findings) → `bl_all_sells2.py` (recalculation) → `bl_all_fig.py` → `make_all_report.py`. Outputs `outputs/bl_all_*`, `bl_summary_all1…2.json`. Tests `tests/test_bl.py` (`test_all_*`).
"""
open(f'{RP}/D1_SELLING_RECONSTRUCTION.md', 'w').write(txt); print(len(txt.splitlines()))
