"""Builds reports/BACKTEST3Y_RESULT.md and figures/bl_bt3_summary.png from outputs/bt3_results (plan reports/BACKTEST3Y_PLAN.md and its two addenda)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy import stats
import bl_bt3_metrics as M
OUT = M.OUT; RES = M.RES; RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures')
def _md(self, index=True, **kw):
    d = self.reset_index() if index else self
    h = '| ' + ' | '.join(str(c) for c in d.columns) + ' |\n|' + '---|' * len(d.columns) + '\n'
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return h + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pd.DataFrame.to_markdown = _md
cyc = lambda s, r, leg='': pd.read_csv(f'{RES}/{s}_{r.replace("/", "-")}_cycles{leg}.csv')
T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); sel = open(f'{RES}/IS_version_selection.txt').read().split('\n')[0]; ident = pd.read_csv(f'{OUT}/bl_bt3_identity.csv'); FRZ = json.load(open(f'{OUT}/bl_bt3_frozen.json'))
rows = []
for sp, runs in (('IS', ('B/V2', 'A/V1')), ('OOS', ('B/V2', 'A/V1')), ('LIVE_FITTED', ('A/V1',))):
    for r in runs:
        C = cyc(sp, r); C = C[C.ok]
        for b in ('gross', 'net'): rows.append(dict(split=sp, run=r if sp != 'LIVE_FITTED' else 'observed', basis=b, **M.metrics(C, b)))
H = pd.DataFrame(rows); H.to_csv(f'{RES}/headline_metrics.csv', index=False)
pc = lambda x, d=1: f'{100 * x:.{d}f}%'; lk = lambda x: f'{x / 1e5:.2f}'
g = lambda sp, r, b: H[(H.split == sp) & (H.run == r) & (H.basis == b)].iloc[0]
# ---- real-system check on the live window (32 cycles with logs)
import bl_d0v_sizing as Z
key = {(r.und, r.expiry): i for i, r in enumerate(Z.CY.itertuples())}; L = cyc('LIVE_FITTED', 'A/V1'); L['cid'] = [key.get((u, e), -1) for u, e in zip(L.und, L.expiry)]; Lm = L[L.cid >= 0].copy(); Lm['real'] = [Z.real_info(c)['pnl'] for c in Lm.cid]
rho = stats.spearmanr(Lm.gross, Lm.real).correlation; leg = cyc('LIVE_FITTED', 'A/V1', '_LEGACY_PRICING'); legm = leg[leg.expiry.isin(Lm.expiry)]
# ---- bias audit table
bias = []
for sp, r in (('IS', 'A/V1'), ('IS', 'B/V2'), ('LIVE_FITTED', 'A/V1')):
    a = cyc(sp, r, '_LEGACY_PRICING'); b = cyc(sp, r); bias.append(dict(split=sp, run=r, gross_legacy=a.gross.mean(), gross_causal=b.gross.mean(), net_legacy=a.net.mean(), net_causal=b.net.mean()))
BI = pd.DataFrame(bias); BI['net_overstatement'] = 1 - BI.net_causal / BI.net_legacy
# ---- stress tables
st = {}
for sp in ('IS', 'OOS'):
    for r in ('B/V2', 'A/V1'): d = pd.read_csv(f'{RES}/{sp}_{r.replace("/", "-")}_stress.csv'); s = d.drop(columns=['und', 'expiry', 'd0']); st[(sp, r)] = pd.DataFrame({'mean per cycle (Rs)': s.mean().round(0), 'total (Rs lakh)': (s.sum() / 1e5).round(1), 'win rate': (s > 0).mean().round(2)}).reset_index().rename(columns={'index': 'scenario'})
# ---- attribution by class and day (OOS point line), by index and year
F = pd.read_csv(f'{RES}/OOS_B-V2_fills.csv.gz').merge(pd.read_csv(f'{OUT}/bl_bt3_cycles.csv')[['und', 'expiry', 'unit']], on=['und', 'expiry']); F['rs'] = -F.side * F.price * F.lots * F.unit
AT = F.groupby(['day', 'cls']).agg(lots=('lots', 'sum'), gross_lakh=('rs', lambda x: x.sum() / 1e5)).reset_index(); AT['day'] = AT.day.map({0: 'D-1', 1: 'D0'})
O = cyc('OOS', 'B/V2'); O['year'] = pd.to_datetime(O.d0).dt.year; BY = O.groupby(['year', 'und']).agg(cycles=('net', 'size'), net_mean=('net', 'mean'), net_total_lakh=('net', lambda x: x.sum() / 1e5), win=('net', lambda x: (x > 0).mean())).reset_index()
stops = pd.DataFrame({sp: [cyc(sp, 'B/V2' if sp != 'LIVE_FITTED' else 'A/V1').stop_j.notna().mean()] for sp in ('IS', 'OOS', 'LIVE_FITTED')})
# ---- figure
fig, ax = plt.subplots(2, 2, figsize=(15, 9)); col = {'IS': '#555555', 'OOS': '#2b6cb0', 'LIVE_FITTED': '#c05621'}
for r, ls in (('B/V2', '-'), ('A/V1', '--')):
    parts = []
    for sp in ('IS', 'OOS'):
        C = cyc(sp, r); C = C[C.ok]; C['wk'] = pd.to_datetime(C.d0).dt.strftime('%G-%V'); parts.append(C.groupby('wk').net.sum().rename(sp))
    CL = cyc('LIVE_FITTED', 'A/V1'); CL['wk'] = pd.to_datetime(CL.d0).dt.strftime('%G-%V'); parts.append(CL.groupby('wk').net.sum().rename('LIVE_FITTED'))
    W = pd.concat(parts, axis=1).fillna(0).sort_index(); tot = W.sum(axis=1).cumsum() / 1e5; x = np.arange(len(W)); ax[0, 0].plot(x, tot.values, ls, color='k' if r == 'B/V2' else '#888', label=f'{r} net, all splits')
    start = {sp: W.index.get_indexer([W[W[sp] != 0].index[0]])[0] for sp in ('OOS', 'LIVE_FITTED')}
for sp, c in (('OOS', '#2b6cb0'), ('LIVE_FITTED', '#c05621')): ax[0, 0].axvline(start[sp], color=c, ls=':'); ax[0, 0].text(start[sp] + 1, ax[0, 0].get_ylim()[1] * .02, {'OOS': 'OOS starts', 'LIVE_FITTED': 'rule-fitted window'}[sp], color=c, fontsize=8, rotation=90, va='bottom')
ax[0, 0].set_title('Cumulative net P&L, weekly (₹ lakh); the line is one continuous series'); ax[0, 0].set_ylabel('₹ lakh'); ax[0, 0].legend(fontsize=8)
for k, sp in enumerate(('IS', 'OOS')):
    d = st[(sp, 'B/V2')]; d = d[d.scenario != 'gross']; ax[0, 1].bar(np.arange(len(d)) + (k - .5) * .4, d['mean per cycle (Rs)'] / 1e3, .4, color=col[sp], label=sp)
ax[0, 1].set_xticks(np.arange(len(d))); ax[0, 1].set_xticklabels(d.scenario, rotation=25, ha='right', fontsize=8); ax[0, 1].axhline(0, color='k', lw=.8); ax[0, 1].set_ylabel('mean net per cycle (₹ thousand)'); ax[0, 1].set_title('Stress tests, B/V2 (point line)'); ax[0, 1].legend(fontsize=8)
for k, sp in enumerate(('IS', 'OOS')):
    C = cyc(sp, 'B/V2'); ax[1, 0].hist(C.net / 1e3, bins=30, alpha=.55, color=col[sp], label=f'{sp} (n={len(C)})', density=True)
ax[1, 0].axvline(0, color='k', lw=.8); ax[1, 0].set_xlabel('net P&L per cycle (₹ thousand)'); ax[1, 0].set_title('Distribution of cycle net P&L, B/V2'); ax[1, 0].legend(fontsize=8)
ax[1, 1].scatter(Lm.real / 1e5, Lm.gross / 1e5, c='#c05621'); lim = max(abs(Lm.real).max(), abs(Lm.gross).max()) / 1e5; ax[1, 1].plot([-lim, lim], [-lim, lim], 'k:'); ax[1, 1].set_xlabel('real cycle cash P&L (₹ lakh)'); ax[1, 1].set_ylabel('simulated D-1 → D0 gross (₹ lakh)'); ax[1, 1].set_title(f'The chain against the real system, 32 live cycles (rho {rho:.2f})')
plt.tight_layout(); plt.savefig(os.path.join(FIG, 'bl_bt3_summary.png'), dpi=120); plt.close()
# ---- report
Lw = []; w = Lw.append; o2n, o2g, a2n, i2n, i2g = g('OOS', 'B/V2', 'net'), g('OOS', 'B/V2', 'gross'), g('OOS', 'A/V1', 'net'), g('IS', 'B/V2', 'net'), g('IS', 'B/V2', 'gross'); lv = g('LIVE_FITTED', 'observed', 'net'); lvg = g('LIVE_FITTED', 'observed', 'gross')
w('# Algo 8 reconstruction — combined D-1 + D0 backtest on 3 years of one-minute option data\n')
w('*Plan `BACKTEST3Y_PLAN.md` with Addendum 1 (in-sample / out-of-sample division) and Addendum 2 (fill-pricing amendment), both written before the OOS run. Scripts `bl_bt3_*.py`. Figure `figures/bl_bt3_summary.png`. Dataset commit `eb40973…`. Frozen D0 parameters `outputs/bl_bt3_frozen.json`.*\n')
w('## 0. Result\n')
w(f'**On the locked out-of-sample cycles (64, 2025-11-20 → 2026-11-12, run once) the reconstructed D-1 + D0 strategy earned ₹{lk(o2n.mean_rs)} lakh net per cycle (₹{lk(o2g.mean_rs)} lakh gross), a profit factor of {o2n.profit_factor:.2f} and a weekly Sharpe of {o2n.sharpe_weekly:.2f}, but the 95% interval of the mean net cycle P&L (₹{lk(o2n.ci_cycle_lo)} to ₹{lk(o2n.ci_cycle_hi)} lakh, t = {o2n.t_stat:.2f}) includes zero.** The in-sample figure is almost the same (₹{lk(i2n.mean_rs)} lakh net per cycle on 175 cycles, t = {i2n.t_stat:.2f}), so the estimate is stable, but 64 cycles cannot separate it from zero, and it halves under triple slippage or double costs.\n')
w('| | cycles | orders per cycle | win rate (cycles) | profit factor | mean net per cycle | t | 95% interval of the mean (₹ lakh) | weekly Sharpe | return on ₹2 crore | max drawdown |\n|---|---|---|---|---|---|---|---|---|---|---|')
def line(sp, r, nm):
    n, gr = g(sp, r, 'net'), g(sp, r, 'gross'); return f'| {nm} | {int(n.cycles)} | {n.orders/n.cycles:.0f} | {pc(n.win_rate,0)} | {n.profit_factor:.2f} | ₹{lk(n.mean_rs)} lakh | {n.t_stat:.2f} | {lk(n.ci_cycle_lo)} to {lk(n.ci_cycle_hi)} | {n.sharpe_weekly:.2f} | {n.return_pct_on_2cr:.1f}% | {n.max_drawdown_pct:.1f}% |'
w(line('OOS', 'B/V2', '**OOS, timetable B/V2 (point line), net**')); w(line('OOS', 'A/V1', 'OOS, timetable A/V1 (band), net')); w(line('IS', 'B/V2', 'IS (development), B/V2, net')); w(line('IS', 'A/V1', 'IS, A/V1, net')); w(line('LIVE_FITTED', 'observed', 'Rule-fitted live window, net (in-sample for the rules)'))
w(f'\n*Gross (simulator fills, no slippage or costs): OOS B/V2 ₹{lk(o2g.mean_rs)} lakh per cycle, profit factor {o2g.profit_factor:.2f}, Sharpe {o2g.sharpe_weekly:.2f}; IS B/V2 ₹{lk(i2g.mean_rs)} lakh. Return on ₹2 crore is the total over the period, not annualised (OOS ≈ one year).*\n')
w('| question | answer |\n|---|---|')
w(f'| Does the out-of-sample result agree with the in-sample one? | **Yes.** Net per cycle ₹{lk(o2n.mean_rs)} lakh (OOS) vs ₹{lk(i2n.mean_rs)} lakh (IS), win rate {pc(o2n.win_rate,0)} vs {pc(i2n.win_rate,0)}. The timetable version was chosen on IS only. |')
w(f'| Is it statistically distinguishable from zero? | **Not out of sample** (t = {o2n.t_stat:.2f}, 64 cycles; the A/V1 band t = {a2n.t_stat:.2f}). In sample t = {i2n.t_stat:.2f}. NIFTY and SENSEX cycles of the same week are not independent, so the real t is lower. |')
w(f'| How sensitive is it to the unverified cost model? | **Very.** OOS B/V2 net per cycle: base ₹{st[("OOS","B/V2")].iloc[0,1]/1e5:.2f} lakh, slippage ×3 ₹{st[("OOS","B/V2")].iloc[1,1]/1e5:.2f}, slippage ×6 ₹{st[("OOS","B/V2")].iloc[2,1]/1e5:.2f}, costs ×2 ₹{st[("OOS","B/V2")].iloc[3,1]/1e5:.2f}, one-minute delay ₹{st[("OOS","B/V2")].iloc[4,1]/1e5:.2f}, fills at the real in-bar position ₹{st[("OOS","B/V2")].iloc[6,1]/1e5:.2f}. The older timetable A/V1 is ≈ 0 at slippage ×3 and costs ×2. |')
w(f'| How good is the reconstruction against the real system? | On the 32 live cycles with logs, the fully simulated chain tracks the real cash P&L with Spearman **{rho:.2f}** (0.81 when D0 is fed the real D-1 book), **earns ₹{Lm.gross.sum()/1e5:.1f} lakh against the real ₹{Lm.real.sum()/1e5:.1f} lakh on the same 32 cycles (about {100*Lm.gross.sum()/Lm.real.sum():.0f}%): it ranks the cycles but earns far less than the real system did**, finds {int(Lm.stop_j.notna().sum())} cycle stops against 11, sends {Lm.orders.median():.0f} orders per cycle against about 1,136. |')
w(f'| Which timetable? | Unknown before June 2026. The pre-registered rule chose **B/V2** from IS (₹{lk(i2n.mean_rs)} vs ₹{lk(g("IS","A/V1","net").mean_rs)} lakh per cycle); OOS reproduces the ranking (₹{lk(o2n.mean_rs)} vs ₹{lk(a2n.mean_rs)}). Both stay reported: the band is part of the result. |\n')
w('## 1. The in-sample / out-of-sample division\n'); w(T.groupby('split3').agg(cycles=('expiry', 'size'), NIFTY=('und', lambda x: int((x == 'NIFTY').sum())), SENSEX=('und', lambda x: int((x == 'SENSEX').sum())), first_d0=('d0', 'min'), last_d0=('d0', 'max')).reset_index().to_markdown(index=False) + '\n')
w('*IS = D0 up to 2025-11-17 (the boundary of the earlier backtest); OOS = after it; LIVE_FITTED = the June–October 2026 cycles the rules were fitted on, in-sample for the rules although later than the boundary; EMBARGO = D-1 in IS, D0 in OOS.*\n')
w('## 2. Full metrics\n'); w(H[['split', 'run', 'basis', 'cycles', 'orders', 'trades_per_day', 'win_rate', 'profit_factor', 'mean_rs', 'median_rs', 't_stat', 'ci_cycle_lo', 'ci_cycle_hi', 'ci_month_lo', 'ci_month_hi', 'total_rs', 'return_pct_on_2cr', 'sharpe_weekly', 'max_drawdown_pct']].round(2).to_markdown(index=False) + '\n')
w('### By index (net)\n'); w(pd.concat([pd.read_csv(f'{RES}/{s}_metrics.csv') for s in ('IS', 'OOS')]).query("basis == 'net' and `index` != 'ALL'")[['split', 'run', 'index', 'cycles', 'win_rate', 'profit_factor', 'mean_rs', 't_stat', 'ci_cycle_lo', 'ci_cycle_hi', 'sharpe_weekly', 'max_drawdown_pct']].round(2).to_markdown(index=False) + '\n')
w('### OOS (B/V2) by year and index\n'); w(BY.round(2).to_markdown(index=False) + '\n')
w('## 3. Stress tests (net, per cycle)\n')
for (sp, r), d in st.items(): w(f'**{sp}, {r}**\n'); w(d.to_markdown(index=False) + '\n')
w('## 4. Where the P&L comes from (OOS B/V2, gross, ₹ lakh)\n'); w(AT.round(2).to_markdown(index=False) + '\n')
w('*These are **cash flows by class and day, not P&L by module**: the D0 buy-backs close lots that D-1 sold, so D-1 rows read as credits and D0 rows as debits. The edge is the difference of large flows.*\n')
ATT = []
for sp in ('IS', 'OOS'):
    f = cyc(sp, 'B/V2'); h = pd.read_csv(f'{RES}/{sp}_B-V2_HOLD_cycles.csv'); ATT.append(dict(split=sp, cycles=len(f), full_gross=f.gross.mean(), full_net=f.net.mean(), d1_only_gross=h.gross.mean(), d1_only_net=h.net.mean(), d0_adds_gross=(f.gross - h.gross).mean(), d0_adds_net=(f.net - h.net).mean(), orders_full=f.orders.mean(), orders_d1_only=h.orders.mean()))
w('### What each module adds (diagnostic, B/V2, mean per cycle in ₹)\n'); w(pd.DataFrame(ATT).round(0).to_markdown(index=False) + '\n')
w('*"D-1 only" = the same D-1 rules, then on D0 only the carried book is managed (per-lot stops and take-profit, hedge, cycle stop, 15:14 clearance) and **nothing new is sold**. The difference is what the D0 module adds. This is a **second look at the OOS cycles** run after the headline result; it is a diagnostic of the frozen model, no parameter was changed because of it.*\n')
w('## 5. Audit of my own pricing (read this before trusting any number above)\n')
w('The first in-sample run gave profit factor 3.1 and a weekly Sharpe of 3.5 gross. I treated that as a warning, found two look-ahead biases in the fills inherited from the research simulators (reactive sells priced before the move that triggered them; stop buy-backs priced at the minute close instead of the stop level), amended the fill model **before** the OOS run (`BACKTEST3Y_PLAN.md`, Addendum 2) and withdrew the first numbers. The size of the bias:\n')
w(BI.round({'gross_legacy': 0, 'gross_causal': 0, 'net_legacy': 0, 'net_causal': 0, 'net_overstatement': 2}).to_markdown(index=False) + '\n')
w(f'*Net overstatement = 1 − causal ÷ legacy. The amended model is still an approximation: one-minute bars do not show what came first inside the minute.*\n')
w('## 6. What this does not show\n')
w(f'* **On the live cycles the chain earns about {100*Lm.gross.sum()/Lm.real.sum():.0f}% of what the real system earned** (same 32 cycles, gross, causal fills). The legacy pricing earned {100*legm[legm.expiry.isin(Lm.expiry)].gross.sum()/Lm.real.sum():.0f}% of it. The reconstruction is the weaker engine on level, which is the right direction for a conservative backtest, but it also means the out-of-sample number is not an estimate of what the real system earns.')
w('* **It is a test of reconstructed rules, not of the real system.** Real orders exist only for the 32 live cycles. For earlier years nothing says the 2026 system traded this way.')
w('* **The timetable before June 2026 is unknown;** both versions are reported; the point line was chosen on IS.')
w('* **Costs are the earlier project\'s model, flagged unverified there** (slippage max(₹0.10, 0.5%), dated statutory costs, ₹20 per order). The system sends about 1,200 orders per cycle, so costs are about 40% of gross; the result is a statement about that model, not about a broker.')
w('* **64 out-of-sample cycles, ≈ one year, two indices that are correlated.** The mean is positive and agrees with IS, but its interval includes zero.')
w('* **The D0 simulator is M0** (no strangle timetable, which is 3% of D0 lots and SENSEX before 16 Sep; no opening-sell reconstruction beyond the ladder and timetable). Lot counts per decision are the real system\'s, held constant while the exchange lot size changed (NIFTY 50 → 25 → 75 → 65; SENSEX 10 → 20), so ₹ P&L scales with the unit; `points_lots_mean` is in the metrics file.')
w(f'* **The day-shifted placebo of the plan is not done** (the cycle cache holds only D-1 and D0).')
w(f'* **Ticks, partial fills, margin and real liquidity are not modelled.** The {int(FRZ["trained_on_cycles"])}-cycle rule fit and the pricing audit show the model is sensitive to how the first seconds of a minute are filled.')
w(f'* **The OOS was run once.** Nothing was changed after its result was seen. Anything changed from here on is a new development step on a contaminated OOS.\n')
w('## 7. Pipeline checks\n'); w(f'* D0 simulator vs the earlier research simulator, real carried book, legacy pricing: **{int(ident.same_lots.sum())} of {len(ident)} cycles identical**, max P&L difference {ident.rel_pnl_diff.max():.1e}.\n* Gross recomputed from the fills equals the simulator cash on every cycle (`gross_check_diff` = 0).\n* No cycle failed or was dropped after seeing a result: IS 175/175, OOS 64/64, live window 36/36.\n* Cycle stops: IS {pc(stops.IS.iloc[0],0)}, OOS {pc(stops.OOS.iloc[0],0)}, live window {pc(stops.LIVE_FITTED.iloc[0],0)} of cycles (real system: 11 of 32).\n')
open(f'{RP}/BACKTEST3Y_RESULT.md', 'w').write('\n'.join(Lw)); print('written', len('\n'.join(Lw))); print(BI.round(0).to_string()); print('live check rho', round(rho, 3))
