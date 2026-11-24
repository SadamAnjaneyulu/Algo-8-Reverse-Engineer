"""Builds reports/PREPAPER_RESULT.md and figures/bl_prepaper.png (plan reports/PREPAPER_PLAN.md)."""
import sys, os, json, glob, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); PP = f'{OUT}/prepaper'; RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures')
def _md(d):
    f = lambda v: ('' if pd.isna(v) else (f'{v:,.0f}' if isinstance(v, (float, np.floating)) and abs(v) >= 100 else (f'{v:.2f}' if isinstance(v, (float, np.floating)) else str(v))))
    return '| ' + ' | '.join(map(str, d.columns)) + ' |\n|' + '---|' * len(d.columns) + '\n' + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pc = lambda x, d=0: f'{100 * x:.{d}f}%'; k = lambda x: f'₹{x / 1e3:,.1f}k'; lk = lambda x: f'₹{x / 1e5:,.1f} lakh'
E = pd.read_csv(f'{PP}/exec_cycles.csv'); GT = pd.read_csv(f'{PP}/gates.csv'); H = pd.read_csv(f'{PP}/headline.csv'); PT = pd.read_csv(f'{PP}/param_table.csv'); ER = pd.read_csv(f'{PP}/eras.csv'); WC = pd.read_csv(f'{PP}/worst_cycles.csv'); CAPT = pd.read_csv(f'{PP}/capacity.csv')
S = json.load(open(f'{PP}/pp_summary.json')); TR = json.load(open(f'{PP}/trend.json')); PATH = pd.read_csv(f'{PP}/path.csv', index_col=0); SVR = pd.read_csv(f'{PP}/sim_vs_real_by_era.csv'); REAL = pd.read_csv(f'{PP}/real/cycle_economic_results.csv'); lam = np.loadtxt(f'{PP}/pbo_logits.txt')
V = pd.concat([pd.read_csv(f) for f in glob.glob(f'{PP}/var_null*.csv')]); nulls = V[V.ok].groupby('variant').net.mean(); base = S['base']
# ---------------- tables
B1 = pd.DataFrame([dict(test=lab, **{'mean net per cycle (₹)': E[c].mean(), 'OOS (₹)': E[E.split == 'OOS'][c].mean(), 'live window (₹)': E[E.split == 'LIVE_FITTED'][c].mean(), 'cycles > 0': pc((E[c] > 0).mean())}) for lab, c in (
    ('gross (no costs, no slippage)', 'net_m0'), ('**baseline: verified costs + slippage**', 'net'), ('NSE fee 0.03553% instead of 0.03503%', 'net_nse_03553'), ('costs × 1.5', 'net_cost1.5'), ('costs × 2', 'net_cost2'), ('slippage × 2', 'net_slip2'), ('slippage × 3', 'net_slip3'), ('slippage × 6', 'net_slip6'),
    ('costs × 1.5 + slippage × 2', 'net_cost1.5_slip2'), ('costs × 2 + slippage × 3', 'net_cost2_slip3'), ('costs × 2 + slippage × 2', 'net_m2'), ('fills delayed 1 minute', 'net_delay1'), ('fills delayed 2 minutes', 'net_delay2'), ('fills at realistic in-bar position', 'net_barpos'),
    ('size × 0.5 (slippage scaled)', 'net_size0.5'), ('size × 2 (slippage scaled)', 'net_size2'), ('margin-capped (S2)', 'net_capped'))])
HH = H.copy(); HH['win_rate'] = HH.win_rate.map(pc); HH['return_on_2cr_per_year'] = HH.return_on_2cr_per_year.map(lambda x: pc(x, 1)); HH['profit_factor'] = HH.profit_factor.round(2)
PTt = PT.pivot_table(index='parameter', columns='level', values='change_pct').reindex(columns=['-40%', '-20%', '+20%', '+40%', '-15min', '-5min', '+5min', '+15min']).dropna(axis=1, how='all')
PTo = PT.pivot_table(index='parameter', columns='level', values='oos_mean_net')
PT2 = pd.DataFrame({'parameter': PTt.index, **{c: [pc(v) if pd.notna(v) else '' for v in PTt[c]] for c in PTt.columns}, 'OOS mean at −40% / +40% (₹)': [f"{PTo.loc[p, '-40%']:,.0f} / {PTo.loc[p, '+40%']:,.0f}" if '-40%' in PTo.columns and pd.notna(PTo.loc[p].get('-40%')) else f"{PTo.loc[p].get('-15min', np.nan):,.0f} / {PTo.loc[p].get('+15min', np.nan):,.0f} (±15 min)" for p in PTt.index]})
PA = PATH[['mean_week', 'sharpe_annual', 'max_drawdown', 'longest_underwater_weeks', 'one_year_pnl_median', 'one_year_pnl_p5', 'one_year_mdd_p95', 'p_loss_10', 'p_negative_year']].T.reset_index().rename(columns={'index': 'measure'})
ERt = ER.copy(); ERt['win_rate'] = ERt.win_rate.map(pc); ERt['costs_share_of_gross'] = ERt.costs_share_of_gross.map(lambda x: pc(x) if pd.notna(x) else 'gross ≤ 0')
REAL['era'] = np.where(REAL.expiry_date >= '2026-08-03', 'from 3 Aug 2026', 'before 3 Aug 2026'); RE = REAL.groupby('era').agg(cycles=('cycle_id', 'size'), real_gross=('marked_economic_pnl', 'mean'), real_conservative_net=('conservative_marked_net', 'mean')).reset_index()
sv = SVR.assign(era=np.where(SVR.expiry >= '2026-08-03', 'from 3 Aug 2026', 'before 3 Aug 2026')).groupby('era').agg(sim_gross=('gross', 'mean'), rank_corr=('gross', lambda x: np.nan)).reset_index()
for i, r in sv.iterrows(): g = SVR[(SVR.expiry >= '2026-08-03') == (r.era == 'from 3 Aug 2026')]; sv.loc[i, 'rank_corr'] = g[['gross', 'marked_economic_pnl']].corr('spearman').iloc[0, 1]
RE = RE.merge(sv, on='era'); late = E[E.d0 > REAL.expiry_date.max()]
WCt = WC.copy(); WCt['gap at 09:16'] = (100 * pd.read_csv(f'{OUT}/unres/cycle_night_gaps.csv').set_index(['und', 'expiry']).loc[list(zip(WC.und, WC.expiry))].gap_min_0916.values).round(2); WCt['cycle stop'] = np.where(WCt.stop_j.notna(), 'hit', 'no'); WCt = WCt[['und', 'expiry', 'split', 'net', 'gap at 09:16', 'cycle stop']]
sd_cycle = E.net.std(); n_need = (2.8 * sd_cycle / max(base, 1)) ** 2
# ---------------- figure
fig, ax = plt.subplots(2, 3, figsize=(20, 11))
b = B1.iloc[1:15]; ax[0, 0].barh(range(len(b))[::-1], b['mean net per cycle (₹)'] / 1e3, color=['#2b6cb0' if v > 0 else '#c53030' for v in b['mean net per cycle (₹)']]); ax[0, 0].set_yticks(range(len(b))[::-1]); ax[0, 0].set_yticklabels([t.replace('**', '') for t in b.test], fontsize=8); ax[0, 0].axvline(0, color='k', lw=.6); ax[0, 0].set_xlabel('mean net per cycle, ₹ thousand'); ax[0, 0].set_title(f'B1: costs and execution — break-even at {S["breakeven_mult"]:.1f}× costs and slippage')
pt = PTt.loc[PTt.index != 'timing', ['-40%', '-20%', '+20%', '+40%']]; y = np.arange(len(pt))
for j, (c, col) in enumerate((('-40%', '#c53030'), ('-20%', '#ed8936'), ('+20%', '#68d391'), ('+40%', '#2f855a'))): ax[0, 1].barh(y + (j - 1.5) * .2, 100 * pt[c], .2, color=col, label=c)
ax[0, 1].set_yticks(y); ax[0, 1].set_yticklabels(pt.index, fontsize=8); ax[0, 1].axvline(0, color='k', lw=.6); ax[0, 1].axvline(-50, color='k', ls='--', lw=.6); ax[0, 1].legend(fontsize=8); ax[0, 1].set_xlabel('change in mean net vs frozen strategy, %'); ax[0, 1].set_title('B2: parameter sensitivity — no cliff at ±20% (dashed = −50% gate)')
ax[0, 2].hist(nulls / 1e3, bins=10, color='#999999', label='random timetables (20 runs)'); ax[0, 2].axvline(base / 1e3, color='#2b6cb0', lw=2, label='real timetable'); ax[0, 2].axvline(S['null_p95'] / 1e3, color='k', ls='--', label='95th percentile of null'); ax[0, 2].legend(fontsize=8); ax[0, 2].set_xlabel('mean net per cycle, ₹ thousand'); ax[0, 2].set_title('B3: the timetable adds ≈ ₹6k over random times (G5 fails by ₹0.1k)')
ax[1, 0].hist(lam, bins=40, color='#2b6cb0'); ax[1, 0].axvline(0, color='#c53030'); ax[1, 0].set_xlabel('logit of the OOS rank of the in-sample best variant'); ax[1, 0].set_title(f'B3: PBO = {S["PBO"]:.2f} (share left of the red line) — tuning among variants does not carry over')
wk = E.assign(wk=pd.to_datetime(E.d0).dt.strftime('%G-%V'), d=pd.to_datetime(E.d0)).groupby('wk').agg(net=('net', 'sum'), cap=('net_capped', 'sum'), d=('d', 'max')).sort_values('d')
for col_, c_, lab_ in (('net', '#2b6cb0', 'constant lot'), ('cap', '#c05621', 'margin-capped')): ax[1, 1].plot(wk.d, wk[col_].cumsum() / 1e5, color=c_, label=lab_)
for dte, lab_ in (('2024-10-01', 'STT 0.1%'), ('2026-04-01', 'STT 0.15%'), ('2026-08-03', 'closing auction')): ax[1, 1].axvline(pd.Timestamp(dte), color='#999999', ls=':', lw=1); ax[1, 1].text(pd.Timestamp(dte), ax[1, 1].get_ylim()[1] * 0.02 if False else 5, lab_, rotation=90, fontsize=7, color='#555555')
ax[1, 1].tick_params(axis='x', rotation=30, labelsize=8); ax[1, 1].set_ylabel('cumulative net, ₹ lakh'); ax[1, 1].legend(fontsize=8); ax[1, 1].set_title('B4: equity curve (weekly, simulator, verified costs)')
x_ = np.arange(len(ER)); ax[1, 2].bar(x_, ER.mean_net / 1e3, color=['#2b6cb0' if v > 0 else '#c53030' for v in ER.mean_net]); ax[1, 2].set_xticks(x_); ax[1, 2].set_xticklabels(['Nov 23–Sep 24', 'Oct 24–Mar 26', 'Apr–Jul 26', 'from 3 Aug 26'], fontsize=8); ax[1, 2].axhline(0, color='k', lw=.6)
ax[1, 2].set_ylabel('simulator mean net per cycle, ₹ thousand'); ax[1, 2].set_title('Eras: the simulator loses money after 3 Aug 2026\n(real log: still positive, see text)')
plt.tight_layout(); os.makedirs(FIG, exist_ok=True); plt.savefig(f'{FIG}/bl_prepaper.png', dpi=110); plt.close()
fail = GT[~GT.passed].gate.tolist()
md = f"""# Pre-paper-trading validation — result

*Plan and gates: `PREPAPER_PLAN.md` (committed before any run; gates approved by you before the runs). 275 cycles, Nov 2023 – Nov 2026, simulator of the reconstructed strategy, verified cost schedule, constant lot (NIFTY 65 / SENSEX 20) unless stated. Every cycle was used before: this measures **robustness of the reconstruction**, not new evidence. Figure: `figures/bl_prepaper.png`.*

## Verdict: **{S['verdict']}** — {S['gates_passed']} of 8 gates pass
{_md(GT.assign(passed=GT.passed.map({True: 'PASS', False: '**FAIL**'})))}

**Failing:** {', '.join(fail)}. By the rule you approved, Algo 8's reconstruction does **not** go to paper trading as it stands. The single most important finding is outside the gates: **the simulator loses money after 3 Aug 2026** (closing auction + STT 0.15%), and the {len(late)} most recent cycles (after the real log ends) are its worst run — while the real system's log over the same weeks is still positive. Paper trading **this** simulator would test a strategy that is not behaving like Algo 8 in the current market regime.

## 1. Headline (simulator, verified costs)
{_md(HH.rename(columns={'set': 'sample', 'mean_net': 'mean net (₹)', 'total': 'total (₹)', 'return_on_2cr_per_year': 'return on ₹2 crore per year'}))}

* Costs + slippage take **{pc(1 - base / E.net_m0.mean())}** of gross. Constant-lot net here (₹{base:,.0f}) is higher than the ₹61k of `ALPHA_SOURCE.md` because brokerage is now charged per order instead of being scaled with the lot restatement; the verified schedule raises the NSE fee before Oct 2024 (0.0495%).
* Funding the ₹2 crore at 6.5% a year costs ≈ {k(S['funding_per_cycle'])} per cycle ({S['cycles_per_year']:.0f} cycles a year).
* Performance falls by sample: IS {k(H.loc[1, 'mean_net'])} → OOS {k(H.loc[2, 'mean_net'])} → live window {k(H.loc[3, 'mean_net'])} per cycle. Linear trend of the weekly series: {TR['slope_per_week']:,.0f} ₹ per week per week (t = {TR['slope_t']:.2f}, not significant on its own).

## 2. B1 — costs and execution
{_md(B1)}

* **Break-even:** costs and slippage together can rise to **{S['breakeven_mult']:.2f}×** before the mean net reaches zero. Slippage alone fails between ×3 and ×6.
* Delayed and in-bar fills cut the mean by ≈ 35–38% but keep it positive (the path is not re-simulated: stops would also trigger differently).
* Sizing: doubling size with proportionally worse slippage gives {k(E['net_size2'].mean())} per cycle (not 2 × {k(base)}): returns per rupee fall with size.

## 3. B2 — parameter sensitivity (change in mean net vs the frozen strategy)
{_md(PT2)}

* No ±20% change (or ±5-minute timing shift) flips the sign or halves the mean: **G3 passes**. The surface is mostly a plateau.
* Two weak spots: a **looser D-1 per-lot stop** (+20% / +40%) cuts the **out-of-sample** mean from ₹{S['oos']:,.0f} to ₹{PTo.loc['d1_stop_ratio', '+20%']:,.0f} / ₹{PTo.loc['d1_stop_ratio', '+40%']:,.0f}; shifting the timetable **15 minutes later** costs {pc(-PT[(PT.parameter == 'timing') & (PT.level == '+15min')].change_pct.iloc[0])}.

## 4. B3 — overfitting and noise floor
* **Deflated Sharpe:** weekly Sharpe {S['SR_week']:.3f} (≈ {S['SR_week'] * np.sqrt(52):.2f} annualised) against a selection threshold of {S['sr0_counted']:.3f} → DSR {S['DSR_counted']:.3f} at N = {S['N_counted']} configurations ({S['DSR_1000']:.3f} at N = 1,000). **Passes** — but the variants are near-copies of one strategy and much of the sample is in-sample for the rules, so this is generous.
* **Probability of backtest overfitting (CSCV, 41 variants, 16 blocks, 12,870 splits): {S['PBO']:.2f}** → **fails** (< 0.5 required). Picking the best-looking variant in-sample gives a below-median variant out-of-sample 60% of the time: the parameter tuning has no out-of-sample value. It does not say the premium is fake; it says fine-tuning is curve-fitting.
* **Random-timetable null (20 runs, same structure, random times):** mean {k(S['null_mean'])} (range {k(S['null_min'])} – {k(S['null_max'])}); the real timetable's {k(base)} beats {pc(S['null_pct'])} of them but sits ₹{S['null_p95'] - base:,.0f} below the 95th percentile → **fails G5 by a hair**. Consistent with earlier findings: **the premium is harvested at almost any time of day; the exact clock is not the edge.**

## 5. B4 — path and tail risk (weekly, ₹2 crore capital)
{_md(PA.rename(columns={'constant lot': 'constant lot (₹)', 'margin-capped': 'margin-capped (₹)'}))}

* Historical maximum drawdown {lk(PATH.loc['constant lot', 'max_drawdown'])} ({pc(PATH.loc['constant lot', 'max_drawdown'] / 2e7, 1)} of capital), longest time under water {int(PATH.loc['constant lot', 'longest_underwater_weeks'])} weeks. One-year block bootstrap: 95th-percentile drawdown {lk(PATH.loc['constant lot', 'one_year_mdd_p95'])}; a one-year loss of more than 10% essentially never appears (**G6 passes**) — **because the bootstrap resamples the 3-year history, which has no crash**; it cannot produce the tail it never saw.
* Overnight implied-volatility shock on the carried book (no gap): ×1.5 → mean loss {k(S['iv_shock']['iv_shock_1.5']['mean'])}, worst {lk(S['iv_shock']['iv_shock_1.5']['worst'])}; ×2 → mean {k(S['iv_shock']['iv_shock_2.0']['mean'])}, worst {lk(S['iv_shock']['iv_shock_2.0']['worst'])} (the wings are long volatility, which is why ×2 is not worse on average). Gap shocks: `UNRESOLVED_THREE.md` §3.
* Ten worst cycles:

{_md(WCt)}

## 6. B5 — liquidity and capacity
{_md(CAPT.assign(share_of_fill_units_at_or_below=CAPT.share_of_fill_units_at_or_below.map(lambda x: pc(x, 1)), share_of_fills_at_or_below=CAPT.share_of_fills_at_or_below.map(lambda x: pc(x, 1))))}

**G7 passes:** {pc(S['capacity_10'], 1)} of the simulated fill volume is at most 10% of that contract's traded volume in the same minute; doubling size barely changes it. Capacity is not the constraint at this size.

## 7. Margin-capped sizing (S2)
Causal cap (90th percentile of the previous 8 cycles' modelled peak margin): mean multiplier {E.s_cap.mean():.2f}, mean net {k(E.net_capped.mean())} per cycle, but **{pc((E.peak_margin_capped > 2e7).mean(), 1)} of cycles still exceed ₹2 crore** → **G8 fails**. A cap set from past cycles cannot anticipate a large cycle; the real system must control margin **inside** the cycle (stop adding), which the simulator does not model. (Margin rests on the unverified 9.3% scan range.)

## 8. The regime problem (most important)
{_md(ERt.rename(columns={'mean_net': 'mean net (₹)', 'mean_gross': 'mean gross (₹)', 'after_funding': 'after funding (₹)'}))}

Real log vs simulator around the closing auction (same cycles):
{_md(RE.rename(columns={'real_gross': 'real gross (₹)', 'real_conservative_net': 'real net, conservative costs (₹)', 'sim_gross': 'simulator gross (₹)', 'rank_corr': 'rank correlation sim vs real'}))}

* After 3 Aug 2026 the simulator still ranks cycles like the real system (rank correlation {RE.loc[RE.era == 'from 3 Aug 2026', 'rank_corr'].iloc[0]:.2f}) but earns about half of the real gross per cycle.
* The **{len(late)} cycles after the real log ends** ({late.d0.min()} – {late.d0.max()}) average {k(late.net.mean())} net in the simulator — the worst stretch of the 3 years, with no real data to compare.
* Reading: the reconstruction is **least reliable exactly in the regime paper trading would run in** (STT 0.15%, closing auction, 15:14 exit). Whether the real Algo 8 still has an edge now is supported only by 23 real post-auction cycles (₹69k gross, ₹29k net at conservative costs per cycle).

## 9. What it would take to reach GO
1. **Rebuild the post-3-Aug-2026 behaviour** (D0 timetable, 15:14 exit, transition minutes 15:15–15:20) against the 23 real post-auction cycles until the simulator earns what the real system earns there — then rerun this battery.
2. **Freeze one configuration and stop tuning** (PBO says tuning adds nothing); keep the frozen parameters.
3. **Intra-cycle margin control** in the simulator (stop adding when modelled margin reaches the cap) → retest G8; obtain NSE SPAN files to verify the scan range.
4. G5 is a near-miss and says the clock is not the edge; it does not need a fix, but it should not be marketed as one.

## 10. If you paper-trade anyway — the forward-test design (pre-registered)
* Run the frozen strategy on paper for every NIFTY and SENSEX cycle; log per cycle: net P&L under the verified costs, modelled peak margin, overnight tradeable gap, realised ÷ implied variance by segment, and the simulator's prediction for the same cycle.
* **Power:** per-cycle standard deviation is {k(sd_cycle)}; to distinguish a mean of {k(base)} from zero at 95% confidence with 80% power needs ≈ **{n_need:,.0f} cycles** (≈ {n_need / S['cycles_per_year']:.1f} years). Paper trading will not prove the edge quickly; it can only catch a broken implementation or a clearly negative regime.
* **Stop rules (pre-registered):** stop the paper test if cumulative net falls below −₹20 lakh, or if the mean over any 26 consecutive cycles is below −₹30k, or if the simulator–paper gap per cycle exceeds ₹1 lakh on average over 10 cycles (implementation broken).

## Limits
Simulator ≈ 36% of the real P&L overall (≈ 0.5× after 3 Aug 2026); B1 re-prices fills without re-simulating paths; margin uses an unverified scan range; bootstrap and stress use 3 calm years; all cycles were used before. 135+ passing tests show the code reproduces its outputs, not that the conclusions are right.
"""
open(f'{RP}/PREPAPER_RESULT.md', 'w').write(md); print('written', S['verdict'], fail, 'n_need', round(n_need))
