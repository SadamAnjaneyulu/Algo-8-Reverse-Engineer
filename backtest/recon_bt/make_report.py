import json, pandas as pd, numpy as np
RES='results'; T=pd.read_csv(f'{RES}/summary_table.csv'); S=pd.read_csv(f'{RES}/stress_concentration.csv'); P=pd.read_csv(f'{RES}/stop_paired.csv'); J=json.load(open(f'{RES}/summary.json')); CAL=json.load(open(f'{RES}/calibration_vs_real.json')); V=json.load(open(f'{RES}/pipeline_validation.json')); Y=pd.read_csv(f'{RES}/by_year_S200.csv'); L=pd.read_csv(f'{RES}/cycle_ledger.csv')
L_=lambda x:f'{x/1e5:,.1f}'; f2=lambda x:f'{x:.2f}'
def row(lv,sc,sp):
    r=T[(T.level==lv)&(T.scope==sc)&(T.split==sp)]
    if not len(r): return None
    r=r.iloc[0]; ci='' if pd.isna(r.sharpe_ci_lo) else f' [{r.sharpe_ci_lo:.1f}, {r.sharpe_ci_hi:.1f}]'
    return f"| {sc} | {sp} | {int(r.cycles)} | {L_(r.net_pnl)} | {r.win_rate_pct:.0f}% | {r.sharpe:.2f}{ci} | {L_(r.max_dd_rs)} ({r.max_dd_pct:.1f}%) | {r.profit_factor:.2f} | {L_(r.worst_cycle)} | {r.stop_rate_pct:.0f}% |\n"
hdr="| Scope | Period | Cycles | Net P&L (Rs lakh) | Win rate | Sharpe [95% CI] | Max DD Rs lakh (% of 2 cr) | Profit factor | Worst cycle (lakh) | Stop rate |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
def block(lv,splits=('ALL_PERIODS','PRE','DEV','POST','USER_IS','USER_OOS')):
    s=hdr
    for sc in ('ALL','NIFTY','SENSEX'):
        for sp in splits:
            x=row(lv,sc,sp)
            if x: s+=x
    return s
cmp="| Level | Scope | Net (lakh) | Win | Sharpe | Max DD (lakh) | PF | Stop rate | Net w/o top-5 cycles | Net at 3x costs+slippage |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
for lv in ('S200','S125','NONE'):
    for sc in ('ALL','NIFTY','SENSEX'):
        r=T[(T.level==lv)&(T.scope==sc)&(T.split=='ALL_PERIODS')].iloc[0]; q=S[(S.level==lv)&(S.scope==sc)&(S.split=='ALL_PERIODS')].iloc[0]
        cmp+=f"| {lv} | {sc} | {L_(r.net_pnl)} | {r.win_rate_pct:.0f}% | {r.sharpe:.2f} | {L_(r.max_dd_rs)} | {r.profit_factor:.2f} | {r.stop_rate_pct:.0f}% | {L_(q.net_without_top5)} | {L_(q.net_slip3x_cost3x)} |\n"
g='| Check (PRE = 234 cycles unseen by rule development) | S200 | S125 | NONE |\n|---|---|---|---|\n'
for k in J['grades']['S200']:
    g+=f"| {k} | "+' | '.join(('n/a' if J['grades'][lv][k][2] is None else ('PASS' if J['grades'][lv][k][2] else 'FAIL'))+(f" ({J['grades'][lv][k][0]:.2f})" if isinstance(J['grades'][lv][k][0],(int,float)) and J['grades'][lv][k][0]==J['grades'][lv][k][0] and k.startswith('R7') else '') for lv in ('S200','S125','NONE'))+' |\n'
pp=P[(P.a=='S200')&(P.b=='S125')]; pr=''.join(f"| {r.split} | {r.cycles} | {r.cycles_changed} | {r.cycles_better} / {r.cycles_worse} | {L_(r.total_diff)} | {'n/a' if pd.isna(r.ci_lo_per_week) else f'[{r.ci_lo_per_week/1e3:,.0f}k, {r.ci_hi_per_week/1e3:,.0f}k]'} | {L_(r.diff_without_top5)} |\n" for r in pp.itertuples())
sv=J['stop_verdict']
cal=''.join(f"| {lv} | {L_(CAL[lv]['sim_gross'])} | {CAL[lv]['ratio_to_real_gross']:.2f}x | {CAL[lv]['corr_cycle_gross']:.2f} | {CAL[lv]['stopped']} |\n" for lv in ('NONE','S125','S200'))
yr=''.join(f"| {r.und} | {r.year} | {r.cycles} | {L_(r.net)} | {r.win:.0f}% |\n" for r in Y.itertuples())
txt=f"""# Reconstructed Algo 8: performance backtest on the 3-year dataset (S200 = Rs 2.0 lakh hard stop)

*2026-11-26. Preregistered before any P&L (`PREREGISTRATION.md`). 275 weekly cycles (NIFTY 154, SENSEX 121), D0 2023-11-09 to 2026-11-12, free-running D-1 + D0 engines, costs and slippage included, capital stated as Rs 2 crore (not verified). Nothing is committed. **This tests our reconstruction of Algo 8, not the original system.***

## Result first
* **With the Rs 2 lakh stop (S200): net Rs {L_(T[(T.level=='S200')&(T.scope=='ALL')&(T.split=='ALL_PERIODS')].net_pnl.iloc[0])} lakh over 275 cycles, win rate {T[(T.level=='S200')&(T.scope=='ALL')&(T.split=='ALL_PERIODS')].win_rate_pct.iloc[0]:.0f}%, Sharpe {T[(T.level=='S200')&(T.scope=='ALL')&(T.split=='ALL_PERIODS')].sharpe.iloc[0]:.2f}, max drawdown Rs {L_(T[(T.level=='S200')&(T.scope=='ALL')&(T.split=='ALL_PERIODS')].max_dd_rs.iloc[0])} lakh.** NIFTY and SENSEX are shown separately below.
* **Is 2L better than 1.2L? Not demonstrated.** Aggregate P&L is higher at 2L (+Rs {L_(pp[pp.split=='ALL'].total_diff.iloc[0])} lakh) and the drawdown smaller, but the gain is **concentrated in a handful of cycles** (without the 5 biggest it turns {L_(pp[pp.split=='ALL'].diff_without_top5.iloc[0])} lakh), its week-bootstrap interval includes 0, and it is **negative in the 5 post-freeze cycles**. Rule fixed in advance: not supported.
* **No stop at all earns the most in this simulation (Sharpe {T[(T.level=='NONE')&(T.scope=='ALL')&(T.split=='ALL_PERIODS')].sharpe.iloc[0]:.2f}) and has the smallest drawdown in rupees**: the stops realise losses that later recover, and they cannot stop gap losses (the worst cycle with a stop, Rs {L_(sv['worst_cycle']['S200'])} lakh, is identical at 1.25L and 2L and is worse than the worst cycle without any stop, Rs {L_(L.net_NONE.min())} lakh: a stop that triggers after a gap or on a dip that later recovers can lose more than holding). The real system's stop exists for tail protection that this 3-year sample only partly contains.
* **Calibration against the real trade export (32 development cycles): at 2L the simulated gross P&L is {CAL['S200']['ratio_to_real_gross']:.2f}x the real one with a per-cycle correlation of {CAL['S200']['corr_cycle_gross']:.2f}; at 1.25L it is {CAL['S125']['ratio_to_real_gross']:.2f}x; with no stop {CAL['NONE']['ratio_to_real_gross']:.2f}x.** This is in-sample, 3 preregistered levels only, and it is evidence about the simulator, not proof that the real stop is 2L.
* **Overfitting verdict:** the rules were reconstructed on Jun-Oct 2026 (36 cycles = DEV). The other 234 older cycles (PRE) were never used: the strategy stays profitable there for NIFTY and SENSEX separately, at 3x costs and without its 5 best cycles (all of R1-R5 pass at every level), so this is **not** an artefact of the development window. The 5 post-freeze cycles (POST) are too few to judge and are negative at S125/S200. **But "profitable in simulation" is not "the real algo earned this"**: sizes, fills and rules before June 2026 are extrapolations (section 7).

## 1. Headline: S200, by instrument and period
{hdr}{''.join(row('S200',sc,sp) or '' for sc in ('ALL','NIFTY','SENSEX') for sp in ('ALL_PERIODS','PRE','DEV','POST','USER_IS','USER_OOS'))}
*PRE = D0 before 2026-06-22 (out-of-sample backwards); DEV = 2026-06-22..2026-10-22 (rules reconstructed here, in-sample); POST = from 2026-10-23 (after the freeze); USER_IS / USER_OOS = your earlier split (D0 <= 2025-11-17 / >= 2025-11-18). Sharpe: weekly cycle returns on Rs 2 crore, sqrt(52); CI = 4-week block bootstrap (blank when < 12 weeks). Drawdown from the minute-level net equity path.*

## 2. The three stop levels side by side (all periods)
{cmp}
## 3. Other metrics, S125 and no-stop blocks
**S125 (1.25 lakh):**

{block('S125',('ALL_PERIODS','PRE','DEV','POST'))}
**NONE (reference):**

{block('NONE',('ALL_PERIODS','PRE','DEV','POST'))}
## 4. Overfitting and robustness checks (preregistered)
{g}
R7 (DEV Sharpe to PRE Sharpe, S200): {J['grades']['S200']['R7 DEV->PRE Sharpe ratio (reported)'][0]:.2f} (DEV is lower than PRE: no sign that the development window flatters the result).

**S200 vs S125, paired per cycle** (week-clustered bootstrap, per week):

| Period | Cycles | Cycles where the stop level matters | Better / worse | Total difference (lakh) | 95% interval | Difference without the 5 largest (lakh) |
|---|---:|---:|---:|---:|---|---:|
{pr}
Preregistered requirement for "S200 better supported": (a) PRE interval above 0: **{sv['a_paired_ci_lower_gt0_in_PRE']}**; (b) positive mean in DEV, PRE and POST: **{sv['b_positive_mean_in_DEV_PRE_POST']}**; (c) positive without the 5 largest in PRE: **{sv['c_positive_after_removing_top5_in_PRE']}**; (d) worst cycle/DD not >25% worse: {sv['d_worst_cycle_and_maxdd_not_more_than_25pct_worse']}. **Verdict: not separable on this evidence.**

**By year, S200 (net Rs lakh, win rate):**

| Index | Year | Cycles | Net | Win |
|---|---|---:|---:|---:|
{yr}
## 5. Calibration against the real trade export (32 development cycles, Jun-Oct 2026)
Real = cash flows of the real order log (fill prices, before brokerage and taxes) plus settlement of leftovers: **Rs {L_(CAL['real_gross_cash_32cycles'])} lakh**; the real system had 11 cycle stops in the D0 stage of 30 cycles.

| Simulated stop level | Sim gross (lakh) | Ratio to real | Per-cycle correlation with real | Cycles stopped in sim (of 32) |
|---|---:|---:|---:|---:|
{cal}
## 6. Pipeline validation (before interpretation)
The data builder reproduces the 2026 research caches exactly on the 32 development cycles ({V['d1_arrays_equal']}/{V['cycles']} D-1 and {V['d0_arrays_equal']}/{V['d0_cycles_with_cache']} D0 array sets identical) and the D-1 replay reproduces B1's {V['total_orders']:,} orders order-for-order ({V['d1_orders_identical']}/{V['cycles']} cycles identical). All 275 cycles hand off D-1 to D0 without error, and every cycle ends flat (no residual position, no settlement needed).

## 7. What this is not (read before using any number)
1. **The rules are our reconstruction** (keys F1 0.74 D-1, 0.42 D0 against the real 2026 orders), applied **unchanged to 2023-2025**, before the period in which Algo 8 was observed. Whether the real system traded this way then is unknown.
2. **Sizes:** the engines' lot counts at each session's actual lot size (NIFTY 50/25/75/65, SENSEX 10/20); hundreds of lots per cycle. Margin and the real capital are unknown: the Rs 2 crore denominator is a stated figure, so **drawdown %, annual return % and Calmar are not reliable**; rupee figures, win rate and Sharpe are (Sharpe does not depend on the denominator). Re-scaled to the 2026 lot sizes, S200 net is Rs {L_(S[(S.level=='S200')&(S.scope=='ALL')&(S.split=='ALL_PERIODS')].net_scaled_2026_lots.iloc[0])} lakh.
3. **Fills** are one-minute-bar conventions (documented in the preregistration) with 0.5% adverse slippage and the earlier backtest's cost model (partly unverified). The D0 engine's aggregated events understate the real number of orders, so brokerage is understated.
4. **Short-premium strategies have negative skew**: a high win rate and a high Sharpe over a calm 3 years can coexist with rare large losses (worst cycle Rs {L_(sv['worst_cycle']['S200'])} lakh here). The Sharpe confidence intervals above do not cover regime change.
5. POST has 5 cycles: no inference. Every number is a simulation of a reconstruction.

## 8. Next steps (not started)
1. Decide the stop level from evidence that is not in-sample (the sample cannot separate 1.25L from 2L; new expiries are the only cure).
2. Complete Python algo as a clean package (the D-1/D0 engines already exist; needs a single event-driven runner with the stop, accounting and a live-feed interface).
3. C++ port with Python/C++ parity tests (the earlier portfolio engine did this: 13,525 byte-identical runs).

Files: `results/summary_table.csv`, `cycle_ledger.csv`, `stress_concentration.csv`, `stop_paired.csv`, `by_year_S200.csv`, `calibration_vs_real.json`, `pipeline_validation.json`, `figures/equity_curves.png`, `figures/drawdown.png`; code `engine_run.py`, `run_all.py`, `analyze.py`, `make_report.py`, `validate_pipeline.py`.
"""
open('REPORT.md','w').write(txt); print(len(txt))
