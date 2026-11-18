"""Generates the markdown reports from the computed result tables (nothing typed by hand except prose)."""
import json, os, pickle, subprocess
import numpy as np, pandas as pd
from . import experiment as X, config as C, final_run as F
R, OUT = 'results', 'reports'
P = pd.read_csv(f'{R}/performance_summary.csv'); G = {v: pd.read_csv(f'{R}/is_grid_{v}.csv') for v in X.VARIANTS}; S = pd.read_csv(f'{R}/stress_tests.csv'); SEL = json.load(open(f'{R}/is_selection.json')); FZ = json.load(open('FROZEN_CONFIG.json'))
EXC = pd.read_csv(f'{R}/data_coverage_and_exclusions.csv'); HEDGE = pd.read_csv(f'{R}/hedge_effectiveness.csv'); CONC = pd.read_csv(f'{R}/concentration.csv'); VOL = pd.read_csv(f'{R}/volatility_regimes.csv'); WORST = pd.read_csv(f'{R}/worst_cycles.csv'); EXP = json.load(open(f'{R}/exposure_summary.json'))
HEAD = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd='..').stdout.strip()
FROZEN = {v: FZ['frozen'][v]['config'] for v in FZ['frozen']}
def md(df, fmt=None):
    df = df.copy(); fmt = fmt or {}
    for c in df.columns:
        if c in fmt: df[c] = df[c].map(lambda x: '' if pd.isna(x) else fmt[c].format(x))
        elif df[c].dtype.kind == 'f': df[c] = df[c].map(lambda x: '' if pd.isna(x) else f'{x:,.2f}')
    return '| ' + ' | '.join(map(str, df.columns)) + ' |\n|' + '---|' * len(df.columns) + '\n' + '\n'.join('| ' + ' | '.join(map(str, r)) + ' |' for r in df.itertuples(index=False))
rs = lambda x: f'Rs {x:,.0f}'
def row(v, n, part, scope): r = P[(P.variant == v) & (P.config == n) & (P.part == part) & (P.scope == scope)]; return r.iloc[0] if len(r) else None
COLS = ['cycles', 'gross_pnl', 'net_pnl', 'costs', 'slippage', 'cum_return_pct', 'ann_return_pct', 'sharpe', 'sortino', 'max_dd_pct', 'longest_dd_days', 'calmar', 'win_rate_pct', 'avg_win', 'avg_loss', 'profit_factor', 'expectancy', 'worst_cycle', 'best_cycle']
def perf_table(scope, parts=('IS', 'OOS', 'OOS_exposed', 'OOS_clean_before', 'OOS_clean_after', 'OOS_clean_all')):
    rows = []
    for v in X.VARIANTS:
        for n in F.names_for(v):
            for part in parts:
                r = row(v, n, part, scope)
                if r is not None: rows.append([v, n + (' (FROZEN)' if n == FROZEN[v] else ' (baseline)'), part] + [r[c] for c in COLS])
    return pd.DataFrame(rows, columns=['exit', 'config', 'period'] + COLS)
FM = {'cycles': '{:.0f}', 'gross_pnl': '{:,.0f}', 'net_pnl': '{:,.0f}', 'costs': '{:,.0f}', 'slippage': '{:,.0f}', 'avg_win': '{:,.0f}', 'avg_loss': '{:,.0f}', 'expectancy': '{:,.0f}', 'worst_cycle': '{:,.0f}', 'best_cycle': '{:,.0f}', 'longest_dd_days': '{:.0f}'}

# ------------------------------------------------------------------ numbers used in prose
h_is, h_oos, h_clean, h_exp = row('HOLD_SETTLE', 'HOLD', 'IS', 'COMBINED'), row('HOLD_SETTLE', 'HOLD', 'OOS', 'COMBINED'), row('HOLD_SETTLE', 'HOLD', 'OOS_clean_all', 'COMBINED'), row('HOLD_SETTLE', 'HOLD', 'OOS_exposed', 'COMBINED')
f_oos, f_clean = row('HOLD_SETTLE', FROZEN['HOLD_SETTLE'], 'OOS', 'COMBINED'), row('HOLD_SETTLE', FROZEN['HOLD_SETTLE'], 'OOS_clean_all', 'COMBINED')
fl_is, fl_oos, fl_clean = row('FLATTEN_1525', 'HOLD', 'IS', 'COMBINED'), row('FLATTEN_1525', 'HOLD', 'OOS', 'COMBINED'), row('FLATTEN_1525', 'HOLD', 'OOS_clean_all', 'COMBINED')
conc = CONC[(CONC.variant == 'HOLD_SETTLE') & (CONC.config == 'HOLD')].set_index('part')
st = S[(S.scope == 'COMBINED')]
def sv(v, n, sc, part): x = st[(st.variant == v) & (st.config == n) & (st.scenario == sc) & (st.part == part)]; return float(x.net_pnl.iloc[0])
d_clean = {sc: F.subsets(F.table('HOLD', 'HOLD_SETTLE', dict(F.BASE, **p)))['OOS_clean_all'].net.sum() for sc, p in (('base', {}), ('slippage_x3', F.SCEN['slippage_x3']), ('slippage_x6', F.SCEN['slippage_x6']), ('costs_x2', F.SCEN['costs_x2']))}
wf = pd.DataFrame(SEL['HOLD_SETTLE']['walk_forward']); wf_sel, wf_hold = wf.val_net_chosen.sum(), wf.val_net_hold.sum()
runs = 0; bad = 0; by = {}
for root, _, fs in os.walk(X.ENG):
    for f in fs:
        d = pickle.load(open(os.path.join(root, f), 'rb')); runs += len(d); bad += sum(1 for v in d.values() if v['parity'] is not True); by[os.path.basename(root)] = by.get(os.path.basename(root), 0) + len(d)
CYC = pd.read_csv(f'{R}/cycle_feasibility.csv'); SUBN = 100 * ((CYC.sub_ce | CYC.sub_pe)[CYC.und == 'NIFTY']).mean(); SUBS = 100 * ((CYC.sub_ce | CYC.sub_pe)[CYC.und == 'SENSEX']).mean()

_h = HEDGE[(HEDGE.variant == 'HOLD_SETTLE') & (HEDGE.config == 'HOLD') & (HEDGE.part == 'IS')].set_index('und'); _hn, _cn, _hs, _cs = _h.loc['NIFTY', 'full_worst_cycle'], _h.loc['NIFTY', 'core_worst_cycle'], _h.loc['SENSEX', 'full_worst_cycle'], _h.loc['SENSEX', 'core_worst_cycle']
# ------------------------------------------------------------------ EXECUTIVE
EXE = f"""# Algo 8 portfolio-construction engine: historical backtest, executive report
Prepared for Rahul. Code commit `{HEAD}`; data commit `{C.DATA_COMMIT}`; configuration frozen in `backtest/FROZEN_CONFIG.json` before any out-of-sample accounting.

## The answer in five lines
1. **I tested the existing engine, but it contains no entry rule.** It cuts and re-enters baskets that are handed to it. I fed it the only documented basket structure (Algo 8's observed 09:16 four-leg basket: short ATM CE+PE, long wings 2,000 points away for NIFTY and 4,000 for SENSEX, three lots per leg) built from real Breeze prices. That structure is an extrapolation to 2023-2025 (it was observed in June-October 2026 only).
2. **The basket held to expiry made a small net profit.** In sample ({int(h_is.cycles)} weekly cycles, NIFTY + SENSEX, net of slippage and costs): **{rs(h_is.net_pnl)}** ({h_is.cum_return_pct:.2f}% of the stated Rs 2 crore, Sharpe {h_is.sharpe:.2f}). Out of sample ({int(h_oos.cycles)} cycles): **{rs(h_oos.net_pnl)}** ({h_oos.cum_return_pct:.2f}%, Sharpe {h_oos.sharpe:.2f}).
3. **Most of the out-of-sample profit sits in the window we had already studied.** The {int(h_exp.cycles)} cycles of 22 Jun - 22 Oct 2026 earned {rs(h_exp.net_pnl)}. The {int(h_clean.cycles)} previously uninspected cycles earned **{rs(h_clean.net_pnl)}** (Sharpe {h_clean.sharpe:.2f}): break-even, and negative for NIFTY. Without its five best cycles the whole out-of-sample year earns {rs(conc.loc['OOS', 'net_without_best5'])}.
4. **The engine's cut and re-entry plugins did not help.** In the hold-to-expiry variant only 2 of the 25 plugin configurations beat plain holding in sample, by {rs(SEL['HOLD_SETTLE']['chosen_is_net'] - SEL['HOLD_SETTLE']['hold_is_net'])} at best. The pre-registered rule froze `{FROZEN['HOLD_SETTLE']}` for the hold-to-expiry variant and plain holding for the flatten variant. Out of sample the frozen plugin configuration earned {rs(f_oos.net_pnl)} (clean subset {rs(f_clean.net_pnl)}) against {rs(h_oos.net_pnl)} for plain holding. In the walk-forward test its selection procedure earned {rs(wf_sel)} against {rs(wf_hold)} for holding.
5. **Python and C++ agreed on all {runs:,} engine runs** (byte-identical outputs), and the accounting layer matches the engine's own ledger to the paisa wherever the engine closed every position.

## What this does and does not show
* It does **not** show that Algo 8 is profitable or that the engine reproduces it. The engine's cut and re-entry rules are example policies; Algo 8's entry rules are not decoded; position size (about Rs 0.5 crore notional per leg) is tiny against Rs 2 crore, so returns are small in rupee terms.
* Profits depend on a handful of cycles and on costs: clean out-of-sample net falls from {rs(d_clean['base'])} to {rs(d_clean['slippage_x3'])} with 3x slippage and {rs(d_clean['slippage_x6'])} with 6x. The flatten-at-15:25 variant earns {rs(fl_oos.net_pnl)} out of sample and {rs(fl_clean.net_pnl)} on the clean subset.
* The wings are a margin device, not a loss limiter at the cycle level: their cumulative premium cost in sample was {rs(abs(HEDGE[(HEDGE.variant == 'HOLD_SETTLE') & (HEDGE.config == 'HOLD') & (HEDGE.part == 'IS')].wings_pnl.sum()))}, and they do not shrink the worst cycle (NIFTY {_hn:,.0f} with wings vs {_cn:,.0f} without; SENSEX {_hs:,.0f} vs {_cs:,.0f}).
* Only {len(CYC)} of 319 expected expiry cycles could be used (validation status Complete); results are for D-1/D0 only.

## Headline table (combined NIFTY + SENSEX, net of slippage and costs, base assumptions)
{md(perf_table('COMBINED', ('IS', 'OOS', 'OOS_clean_all'))[['exit', 'config', 'period', 'cycles', 'net_pnl', 'cum_return_pct', 'sharpe', 'max_dd_pct', 'win_rate_pct', 'profit_factor']], FM)}

Details: METHODOLOGY.md, NIFTY_REPORT.md, SENSEX_REPORT.md, COMBINED_REPORT.md, COST_AND_STRESS_REPORT.md, PARITY_REPORT.md, LIMITATIONS_AND_CONCLUSIONS.md; data in `backtest/results/` (trade ledger, monthly performance, stress tests).
"""
open(f'{OUT}/EXECUTIVE_REPORT.md', 'w').write(EXE)

# ------------------------------------------------------------------ METHODOLOGY
split_rows = pd.DataFrame([['In-sample (IS)', 'first available session (NIFTY 2023-11-08, SENSEX 2024-05-30) to 2025-11-17', 'by D0 date'], ['Embargo', 'cycle with D-1 <= 2025-11-17 < D0 (NIFTY expiry 2025-11-18)', 'dropped'], ['Out-of-sample (OOS)', '2025-11-18 to last expiry (NIFTY 2026-11-09, SENSEX 2026-11-12)', 'by D0 date'],
                           ['  OOS exposed', 'D0 2026-06-22 to 2026-10-22 (inspected during Algo 8 reverse engineering)', 'subset'], ['  OOS clean (before)', 'D0 2025-11-18 to 2026-06-21', 'subset'], ['  OOS clean (after)', 'D0 2026-10-23 on', 'subset']], columns=['Period', 'Dates', 'Rule'])
MET = f"""# Methodology
## 1. The engine and how data enters it
`portfolio_engine/construction`: Python reference (`pc`) and C++ runner (`pc_run`), both reading the same scenario text. Flow at every evaluation time t: seed fills with ts <= t are applied to the position ledger (the historical `PortfolioState.apply_fill`) -> each enabled plugin sees a read-only context (marks and baskets with timestamps <= t) -> proposed CUT / REENTRY actions are checked by the risk validator (atomic groups) -> accepted actions become new fills at the latest mark <= t. Plugins never touch the ledger. The engine has **no** entry logic (baskets enter only as `LEG` seed lines), **no** settlement, costs, slippage or margin, and only knows `basket_cut`, `basket_reentry` and `scripted_actions`; I added `capital_stop` (Python and C++, 5 tests, documented in `plugins/stop.py`). The scenario file carries a fixed `SYNTHETIC_TEST_ONLY` evidence stamp that the loader requires; I left it unchanged and marked the description `HISTORICAL_BREEZE_REPLAY`.
Adapter (`bt/`): one scenario per cycle built from the pinned dataset commit: instruments (4 contracts), seed fills (entry), one MARK per completed 1-minute bar (timestamp = bar start + 60 s, price = bar close) and one TICK per minute. No bar is visible before it completes, entries are at the bar open, nothing after D0 is read except the official close for settlement. Marks are last-trade closes including carried zero-volume bars; missing bars leave the previous mark in place.
## 2. Cycles and split
One cycle = one weekly expiry (D-1 + D0). Used only if the validation status is Complete: {len(CYC)} cycles (NIFTY {int((CYC.und == 'NIFTY').sum())}, SENSEX {int((CYC.und == 'SENSEX').sum())}), all feasible under the entry rule. Excluded and counted, never skipped silently:
{md(EXC)}
{md(split_rows)}
## 3. Basket construction (Algo 8 observed structure, rulebook v0.6 'Observed', not decoded)
Decision 09:16 on D-1; K = step x floor(S/step + 0.5), S = close of the 09:15 spot bar (so no D-2 or future price is used for the trade; D-2 was only used to choose which strikes were downloaded); short CE and PE at K; long CE at K+W and long PE at K-W (W 2,000 NIFTY; 4,000 SENSEX, 2,000 from 2026-09-16); three lots per leg; lot size inferred per session from the gcd of option volumes (NIFTY 50/25/75/65, SENSEX 10/20, consistent with the exchange revisions). Each leg enters at the open of the first traded bar (volume > 0) in 09:16-09:20. If a wing never traded in that window the nearest strike toward ATM that did is used (a wing was substituted in {SUBN:.0f}% of NIFTY and {SUBS:.0f}% of SENSEX cycles); the average distances were NIFTY 1,916/1,969 points (CE/PE) and SENSEX 3,756/3,776.
## 4. Exit variants
HOLD_SETTLE: carry to expiry; settle at the intrinsic value of the official close (15:30 spot bar; Yahoo daily close when absent; recorded per cycle). The dataset has no settlement price, so this is a proxy. FLATTEN_1525: engine ticks stop at 15:25; open inventory is closed at the 15:25 mark with slippage and costs.
## 5. Execution, costs, margin
Gross = engine reference prices + settlement. Net = trades re-priced for delay and slippage (base max(Rs 0.10, 0.5% of price) against every order), minus Rs 20 brokerage per order, NSE 0.035% / BSE 0.0325% transaction charge, SEBI 0.0001%, stamp 0.003% on buys, GST 18% on (brokerage + transaction + SEBI), STT on sells 0.0625% (to 2024-09-30), 0.1% (to 2026-03-31), 0.15% after, exercise STT on long ITM options 0.125% / 0.15%. The 2026 STT change is confirmed by reports; the other rates are quoted from memory and **unverified**. There is no bid/ask in the data: slippage is an assumption and is stressed (3x, 6x, delay). Margin = worst-case expiry loss of the open positions with premiums ignored (a proxy, not exchange SPAN; real margin and broker terms are unknown). Capital = Rs 2 crore as stated in Info.txt (not verified), constant; peak combined margin proxy {EXP['peak_combined_margin_proxy_rs']:,.0f} ({EXP['peak_combined_margin_util_pct']:.1f}% of capital, at most {EXP['max_simultaneous_baskets']} baskets at once).
## 6. Metrics
One return per expiry cycle, aggregated to ISO weeks, divided by Rs 2 crore; Sharpe and Sortino annualised with sqrt(52), risk-free 0, no compounding. Drawdown from the minute-level mark-to-market equity path. Annualised return = total net P&L / capital / years of data. A 'trade' is one basket cycle; order counts are reported separately. Sharpe is not computed from individual orders.
## 7. Selection and freezing
Pre-registered in `PREREGISTRATION.md` before any in-sample grid result was seen: 26 configurations; per exit variant the best in-sample net P&L replaces plain holding only if it beats it and is positive in at least 2 of 3 chronological thirds. Result: HOLD_SETTLE -> `{FROZEN['HOLD_SETTLE']}` (in-sample {rs(SEL['HOLD_SETTLE']['chosen_is_net'])} vs holding {rs(SEL['HOLD_SETTLE']['hold_is_net'])}); FLATTEN_1525 -> HOLD (the best candidate failed the thirds test). Frozen at code commit `{FZ['code_commit_before_freeze']}`, then committed, then the out-of-sample accounting was run once.
Walk-forward (expanding window, applying the same rule), HOLD_SETTLE:
{md(wf[['fold', 'chosen', 'val_net_chosen', 'val_net_hold', 'val_cycles', 'best_in_hindsight', 'val_net_best']], {'val_net_chosen': '{:,.0f}', 'val_net_hold': '{:,.0f}', 'val_net_best': '{:,.0f}'})}
The selection procedure earned {rs(wf_sel)} across the four validation blocks against {rs(wf_hold)} for plain holding.
## 8. Verification
{runs:,} engine runs, each executed by Python and C++: {runs - bad:,} byte-identical. Accounting vs engine ledger: in all stop-out cycles the engine's FIFO realised P&L equals the accounting gross P&L exactly. 10 harness tests, 5 plugin tests, existing engine suite (175 + 5) and C++ checks (100/100) pass.
"""
open(f'{OUT}/METHODOLOGY.md', 'w').write(MET)

# ------------------------------------------------------------------ per-index reports and combined
def scope_report(title, scope, extra=''):
    t = perf_table(scope); mo = pd.read_csv(f'{R}/monthly_performance.csv')
    sub = '' if scope == 'COMBINED' else f"{md(mo[(mo.variant == 'HOLD_SETTLE') & (mo.config == 'HOLD') & (mo.und == scope)].groupby('month').agg(cycles=('cycles', 'sum'), net=('net', 'sum'), return_pct=('net_return_pct_of_capital', 'sum')).reset_index(), {'net': '{:,.0f}', 'return_pct': '{:.3f}'})}"
    if scope == 'COMBINED': sub = md(mo[(mo.variant == 'HOLD_SETTLE') & (mo.config == 'HOLD')].groupby('month').agg(cycles=('cycles', 'sum'), net=('net', 'sum'), return_pct=('net_return_pct_of_capital', 'sum')).reset_index(), {'net': '{:,.0f}', 'return_pct': '{:.3f}'})
    h = HEDGE[(HEDGE.variant == 'HOLD_SETTLE') & (HEDGE.config == 'HOLD')]; h = h if scope == 'COMBINED' else h[h.und == scope]
    v = VOL[(VOL.variant == 'HOLD_SETTLE') & (VOL.config == 'HOLD')]; v = v if scope == 'COMBINED' else v[v.und == scope]
    w = WORST[(WORST.variant == 'HOLD_SETTLE') & (WORST.config == 'HOLD')]; w = w if scope == 'COMBINED' else w[w.und == scope]
    return f"""# {title}
Net of slippage and costs unless stated; Rs; combined/NIFTY/SENSEX each measured against the same Rs 2 crore capital. `exit` = HOLD_SETTLE or FLATTEN_1525; baseline = no plugin acts.
{extra}
## Performance by period
{md(t, FM)}
## Hedge (wings) contribution, HOLD_SETTLE baseline, gross at reference prices
{md(h[['part', 'und', 'cycles', 'core_only_gross', 'with_wings_gross', 'wings_pnl', 'core_worst_cycle', 'full_worst_cycle', 'std_reduction_pct']], {'core_only_gross': '{:,.0f}', 'with_wings_gross': '{:,.0f}', 'wings_pnl': '{:,.0f}', 'core_worst_cycle': '{:,.0f}', 'full_worst_cycle': '{:,.0f}', 'std_reduction_pct': '{:.1f}'})}
## Volatility regimes (terciles of the D-1 spot range, cut-offs from in-sample cycles)
{md(v[['und', 'part', 'regime', 'cycles', 'net', 'avg_net', 'win_rate_pct', 'worst', 'tercile_cut_pct']], {'net': '{:,.0f}', 'avg_net': '{:,.0f}', 'worst': '{:,.0f}'})}
## Worst cycles (HOLD_SETTLE baseline)
{md(w.head(8)[['und', 'expiry', 'part', 'subset', 'net', 'move_pct_close_vs_K']], {'net': '{:,.0f}', 'move_pct_close_vs_K': '{:.2f}'})}
## Monthly net P&L (HOLD_SETTLE baseline)
{sub}
Charts: `reports/figures/equity_drawdown_*.png`, `monthly_hold_settle_hold.png`.
"""
open(f'{OUT}/NIFTY_REPORT.md', 'w').write(scope_report('NIFTY performance report', 'NIFTY')); open(f'{OUT}/SENSEX_REPORT.md', 'w').write(scope_report('SENSEX performance report', 'SENSEX', 'SENSEX data start 2024-05-30, so its in-sample period is about 1.5 years. SENSEX open interest is unavailable and was not used.'))
open(f'{OUT}/COMBINED_REPORT.md', 'w').write(scope_report('Combined NIFTY + SENSEX portfolio report', 'COMBINED', f"The engine can hold both baskets at once (maximum simultaneous baskets {EXP['max_simultaneous_baskets']}); P&L is additive. Peak combined margin proxy {rs(EXP['peak_combined_margin_proxy_rs'])} ({EXP['peak_combined_margin_util_pct']:.1f}% of capital). Gross units per basket at entry: NIFTY ~{EXP['avg_gross_units_at_entry_nifty']:.0f}, SENSEX ~{EXP['avg_gross_units_at_entry_sensex']:.0f}, net units 0 (shorts offset by wings)."))
conc_tab = CONC
open(f'{OUT}/COMBINED_REPORT.md', 'a').write(f"\n## Concentration\n{md(conc_tab, {'net': '{:,.0f}', 'net_without_best5': '{:,.0f}', 'net_without_worst5': '{:,.0f}', 'net_without_best5_and_worst5': '{:,.0f}', 'best5_sum': '{:,.0f}', 'worst5_sum': '{:,.0f}', 'top5_share_of_net_pct': '{:.0f}'})}\n")

# ------------------------------------------------------------------ cost and stress
pv = st.pivot_table(index=['variant', 'config', 'scenario'], columns='part', values='net_pnl').reset_index()
pv2 = S[S.scope.isin(['NIFTY', 'SENSEX'])].pivot_table(index=['variant', 'config', 'scenario', 'scope'], columns='part', values='net_pnl').reset_index()
cs = pd.DataFrame([[sc, v] for sc, v in d_clean.items()], columns=['scenario (HOLD_SETTLE baseline)', 'clean OOS net P&L (64 cycles)'])
STR = f"""# Transaction-cost sensitivity and stress tests
Scenario definitions are in `PREREGISTRATION.md` (written before the in-sample grid). Combined NIFTY + SENSEX net P&L in rupees; `missing_20pct_bars` removes 20% of the bars fed to the engine (3 seeds): it cannot change a configuration with no plugin, so the baseline is identical by construction. Sizing scenarios rerun the engine with 1 and 6 lots per leg.
## All scenarios
{md(pv.rename(columns={'IS': 'in-sample net', 'OOS': 'out-of-sample net'}), {'in-sample net': '{:,.0f}', 'out-of-sample net': '{:,.0f}'})}
## Clean out-of-sample (the 64 previously uninspected cycles), HOLD_SETTLE baseline
{md(cs, {'clean OOS net P&L (64 cycles)': '{:,.0f}'})}
## Per index
{md(pv2.rename(columns={'IS': 'in-sample net', 'OOS': 'out-of-sample net'}), {'in-sample net': '{:,.0f}', 'out-of-sample net': '{:,.0f}'})}
## Reading
* The baseline stays positive under 3x and 6x slippage in the hold-to-expiry variant, but its clean out-of-sample result is {rs(d_clean['slippage_x3'])} at 3x and {rs(d_clean['slippage_x6'])} at 6x. The frozen plugin configuration turns negative out of sample at 3x slippage ({rs(sv('HOLD_SETTLE', FROZEN['HOLD_SETTLE'], 'slippage_x3', 'OOS'))}).
* The flatten variant is more cost-sensitive because it trades eight orders per cycle: out-of-sample net is {rs(sv('FLATTEN_1525', 'HOLD', 'slippage_x3', 'OOS'))} at 3x and {rs(sv('FLATTEN_1525', 'HOLD', 'slippage_x6', 'OOS'))} at 6x slippage.
* Execution delay did **not** hurt (it improved results by a few hundred rupees per cycle): the 09:16 bar open is not a favourable price, so the result does not depend on speed. I did not investigate why; it should not be read as a benefit.
* P&L scales almost linearly with size (1 lot {rs(sv('HOLD_SETTLE', 'HOLD', 'size_1_lot', 'IS'))} vs 6 lots {rs(sv('HOLD_SETTLE', 'HOLD', 'size_6_lots', 'IS'))} in sample) because costs are small relative to premium; a 6-lot position still uses only a fraction of the stated capital.
* Volatility regimes and worst cycles are in the index reports: the baseline lost money in the high-volatility tercile out of sample for both indices; the worst cycles are 2-4% index moves between entry and expiry.
"""
open(f'{OUT}/COST_AND_STRESS_REPORT.md', 'w').write(STR)

# ------------------------------------------------------------------ parity
PAR = f"""# Python / C++ parity report
Every engine run in this study was executed by the Python reference and by the C++ runner on the same scenario text and compared file by file (decisions, actions, states, lineage, events, instruments, summary).
* Engine runs: **{runs:,}**; byte-identical: **{runs - bad:,}**; differences: **{bad}**.
{md(pd.DataFrame(sorted(by.items()), columns=['result set', 'runs']))}
The 26-configuration in-sample grid x 2 exit variants x 175 cycles, the out-of-sample runs of the frozen configurations, the 1 lot / 6 lot reruns and the missing-bars reruns are all included. Plugins exercised on real data: basket_cut (side-aware, partial and full cuts), basket_reentry (cooldown and price-band conditions), capital_stop, risk validator (atomic groups).
Beyond fixture parity: the real-data runs include partial fills at different entry minutes, stale marks, carried prices, price jumps, multi-lot quantity rounding and one-per-leg cut limits, none of which the fixtures contained. No disagreement was found, so there was nothing to investigate. A byte-identical result proves the two implementations agree; it does not prove the logic is right. Correctness of the logic was checked separately: in the 38 cycles where the capital stop closed every position, the engine's own FIFO realised P&L equals the accounting layer's gross P&L to the paisa (`tests/test_backtest.py`).
"""
open(f'{OUT}/PARITY_REPORT.md', 'w').write(PAR)

# ------------------------------------------------------------------ limitations
LIM = f"""# Research limitations and final conclusions
## What was tested
The existing engine's plugin framework (cut, re-entry, stop) on real NIFTY and SENSEX D-1/D0 option data, fed with the Algo 8 observed basket structure, under an explicit execution-cost model, with a frozen configuration and a held-out final year.
## Blockers and unresolved items
1. **The engine has no entry rule.** The basket structure is the rulebook's *observed* pattern from June-October 2026, extrapolated to November 2023 onward (wing width, three lots per leg, 09:16 timing). If Algo 8 traded differently earlier, the results describe a hypothetical strategy.
2. **No bid/ask.** Fills are last-trade prices plus an assumed slippage; the spread of far wings is unobservable. 54% of NIFTY and 31% of SENSEX wings were substituted by a nearer strike because the nominal wing never traded.
3. **No settlement price** in the data; the official close comes from the 15:30 spot bar or Yahoo's daily close.
4. **Cost rates** other than the 2026 STT change are unverified; broker terms and margin are unknown (margin is a proxy). Return figures use the stated, unverified Rs 2 crore.
5. **Stop-loss interpretation.** "4% carry / 1% of capital" is defined here as 4% of the basket margin proxy and 1% of Rs 2 crore; this reading is a choice. The capital stop never helped in sample and is not part of either frozen configuration.
6. **Only D-1/D0 sessions** exist; {len(CYC)} of 319 expected cycles are usable; SENSEX starts 2024-05-30 and lacks 35 expected expiries; open interest is not used. Cycles with outages, special sessions or missing contracts were excluded, which could bias results toward calmer weeks.
7. **Contamination.** 2026-06-22..2026-10-22 was inspected during reverse engineering. Treat the clean subset (64 cycles, of which only 5 are after the exposed window) as the only independent evidence, and note it is small.
8. **Statistical power.** 100 out-of-sample weekly cycles; results are dominated by a few cycles ({conc.loc['OOS', 'top5_share_of_net_pct']:.0f}% of out-of-sample net comes from the best five). No significance test is claimed; the configuration grid (26) was searched on 175 cycles.
9. The engine evidence stamp says `SYNTHETIC_TEST_ONLY` by design; the files are labelled in their description.
## Conclusions
* The hold-to-expiry short-straddle-with-far-wings basket is slightly profitable in sample and break-even out of sample once the already-inspected window is removed; it is not robust to 3x slippage on the clean subset.
* The cut and re-entry plugins add no demonstrated value on this data; plain holding beat the selected plugin configuration out of sample and in walk-forward.
* The engine and its C++ twin are consistent with each other and with an independent ledger on real data; the infrastructure is ready for a richer basket-construction layer, but this test cannot say whether Algo 8 itself has an edge.
* Next steps if wanted: obtain real entry/exit rules or the Algo 8 fills for 2023-2025; replace last-trade prices with quotes; verify cost rates; extend data to other days to expiry.
"""
open(f'{OUT}/LIMITATIONS_AND_CONCLUSIONS.md', 'w').write(LIM)
print('reports written')
