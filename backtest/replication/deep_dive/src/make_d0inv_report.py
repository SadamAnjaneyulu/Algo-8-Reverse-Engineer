"""Builds reports/D0_INVENTORY.md from bl_d0_inv_roles.csv, bl_d0_timetable.csv, bl_summary_d0inv.json."""
import sys, os, json; sys.path.insert(0, '.')
import pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R = json.load(open(f'{OUT}/bl_summary_d0inv.json')); RO = pd.read_csv(f'{OUT}/bl_d0_inv_roles.csv'); TT = pd.read_csv(f'{OUT}/bl_d0_timetable.csv'); HR = pd.read_csv(f'{OUT}/bl_d0_inv_hour.csv', header=[0, 1], index_col=0)
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
tot = int(RO.lots.sum()); g = lambda m, r_: int(RO[(RO.module == m) & (RO.role == r_)].lots.sum())
cb = R['carried_book_median']
txt = f"""# Algo 8 — D0 (expiry day): inventory and what carries over from D-1

*Step 1 of `D0_PLAN.md`. In-sample, D0 of 32 live cycles. One-minute spot and option OHLC for all 32 D0 sessions were built (`bl_d0_data.py`).*

## 0. Result
* **D0 is the busy day.** {tot:,} lots on D0, against 13,655 on D-1. The main flows:
  * body sells {g('num', 'open_short'):,} and body buy-backs {g('num', 'cover_short'):,};
  * hedge wing buys {g('h_', 'open_long'):,} and wing sells {g('h_', 'close_long'):,};
  * body-stream long buys and sells {g('num', 'open_long'):,} / {g('num', 'close_long'):,};
  * stop module {g('s_', 'close_long') + g('s_', 'cover_short') + g('s_', 'open_short'):,} lots in {R['stop_cycles']} cycles;
  * lump salvage (`v_` sells) {g('v_', 'close_long'):,}.
* **Carried into D0 (median per cycle):** {cb['S_CE']:.0f} CE and {cb['S_PE']:.0f} PE short lots, {cb['L_CE']:.0f} / {cb['L_PE']:.0f} long lots, the lump being the long excess.
* **What carries over from D-1:**
  * **The hedge controller does.** Long lots equal short lots at {R['quiet_balanced']:.0%} of quiet moments (D-1: 99%; the 15:00 hour drops to {R['quiet_by_hour']['15']:.0%} with the clearance).
  * *Correction (D0 chunk 1, `D0_SELLS.md` §2): this test pooled NIFTY and SENSEX. Per underlying and version, D0 has a fixed pair timetable (out-of-fold pair-lot F1 0.805). The line below holds only for the pooled view.*
  * **The D-1 timetable does not.** On D0 only {TT.minutes_share_ge_0p8.iloc[0]} (V1) and {TT.minutes_share_ge_0p8.iloc[1]} (V2) minutes have a sale in at least 80% of cycles, against 33 fixed waves on D-1. D0 selling is not a fixed minute timetable.
  * **Buy-backs are not minute-clocked on D0:** {R['bb_sec0']:.0%} at second :00, against 48% on D-1.
* **Buy-backs mostly close lots sold during D0** ({R['bb_lots_other']:,} lots), not the carried book alone ({R['bb_lots_on_carried_only_contracts']:,} lots on contracts held only from D-1). D0 is an active intraday sell / buy-back cycle on top of the carried position.
* **15:14 clearance:** {R['lots_1514']:,} lots in the 15:14 minute (body buy-backs and body-stream long sales). Only {R['lots_after_1515']:,} lots trade after 15:15.

## 1. Lots by module and role
{table(RO)}

## 2. Lots by hour
{table(HR.reset_index())}

## 3. Timetable test (share of cycles with a sale in a given D0 minute)
{table(TT.round(3))}

## Next (plan phases 2–4)
Test whether the D-1 sell triggers drive D0 selling: the reactive two-candle breakout, the solo ladder at fresh extremes, and wider time windows (grid A in `d0_reconstruction`). Test whether the D-1 own-premium stop (about 1.6×) and the fast-move exits drive D0 buy-backs. Then build the D0 free-running reconstruction from the carried book and score it like D-1.
"""
open(f'{RP}/D0_INVENTORY.md', 'w').write(txt); print('ok')
