"""Builds reports/ALPHA_SOURCE.md and figures/bl_bt3_alpha.png from outputs/bt3_results/{ablate_*,greeks_*,alpha_*}.csv (plan reports/ALPHA_SOURCE_PLAN.md)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RES = f'{OUT}/bt3_results'; RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures')
def _md(self, index=True, **kw):
    d = self.reset_index() if index else self
    h = '| ' + ' | '.join(str(c) for c in d.columns) + ' |\n|' + '---|' * len(d.columns) + '\n'
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return h + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pd.DataFrame.to_markdown = _md
k = lambda x: f'{x / 1e3:+,.0f}k'; kk = lambda x: f'{x / 1e3:,.0f}k'; pc = lambda x, d=1: f'{100 * x:.{d}f}%'
CT = pd.read_csv(f'{RES}/greeks_components_trading.csv'); CC = pd.read_csv(f'{RES}/greeks_components_calendar.csv'); RT = pd.read_csv(f'{RES}/greeks_reconciliation_trading.csv'); RC = pd.read_csv(f'{RES}/greeks_reconciliation_calendar.csv')
AS = pd.read_csv(f'{RES}/ablate_summary.csv').set_index('variant'); AD = pd.read_csv(f'{RES}/ablate_diffs.csv').set_index('variant'); AI = pd.read_csv(f'{RES}/alpha_iv_cycles.csv'); NC = pd.read_csv(f'{RES}/alpha_naive_compare_cycles.csv')
comp = ['delta', 'gamma', 'theta', 'vega', 'resid']
def table(C, R, by='split'):
    n = R.groupby(by).size() if by == 'split' else None
    t = C.groupby(by)[comp + ['holding']].sum().div(n, axis=0) if by == 'split' else C[comp + ['holding']].sum().to_frame().T.div(len(R))
    ex = R.groupby('split').execution.mean() if by == 'split' else pd.Series({0: R.execution.mean()}); gr = R.groupby('split').gross.mean() if by == 'split' else pd.Series({0: R.gross.mean()})
    t['execution'] = ex.values; t['gross'] = gr.values; return t
T_t = table(CT, RT); T_t.loc['ALL'] = table(CT, RT, by='all').iloc[0].values; T_c = table(CC, RC); T_c.loc['ALL'] = table(CC, RC, by='all').iloc[0].values
fmt = lambda T: T.assign(**{c: T[c].map(kk) for c in T.columns}).reset_index().rename(columns={'index': 'split', 'holding': 'holding total'})
rec_sum = RT.recon_diff.sum(); rec_worst = RT.loc[RT.recon_diff.abs().idxmax()]
# session and side
n = len(RT); S = CT.groupby(['side', 'session'])[comp + ['holding']].sum().div(n); Sc = CC.groupby(['side', 'session'])[comp + ['holding']].sum().div(n)
S_f = S.assign(**{c: S[c].map(kk) for c in S.columns}).reset_index(); sh = S.holding.copy(); d0_share = S.loc[('short', 'D0 day'), 'holding'] / S.holding.sum()
# clock-independent totals
tot_t = CT[comp].sum().div(n); tot_c = CC[comp].sum().div(n); decay_t = tot_t[['theta', 'vega', 'resid']].sum(); decay_c = tot_c[['theta', 'vega', 'resid']].sum()
# IV / RV
iv = AI.groupby('und')[['iv_D1_open', 'iv_D1_mid', 'iv_D1_close', 'iv_D0_open', 'iv_D0_mid', 'iv_D0_late', 'rv_D1', 'rv_D0']].mean().mul(100).round(1).reset_index(); iv['overnight gap, mean |%|'] = AI.assign(a=AI.overnight_move_pct.abs()).groupby('und').a.mean().round(2).values
# naive vs strategy
rng = np.random.default_rng(20260101); NC['wk'] = pd.to_datetime(NC.expiry).dt.strftime('%G-%V'); wks = NC.wk.unique(); grp = {w: NC[NC.wk == w] for w in wks}
def st(s): return dict(naive=s.naive_pnl.sum() / s.naive_premium.sum(), strat=s.gross.sum() / s.premium_sold.sum(), naive_mean=s.naive_pnl.mean(), strat_per_straddle=s.strat_per_straddle.mean(), naive_sd=s.naive_pnl.std(), strat_sd=s.strat_per_straddle.std())
base = st(NC); B = pd.DataFrame([st(pd.concat([grp[w] for w in rng.choice(wks, len(wks))])) for _ in range(2000)]); lo, hi = B.quantile(.025), B.quantile(.975); dif = B.strat - B.naive
NV = pd.DataFrame([dict(split='ALL', cycles=len(NC), **{'naive straddle, gross % of premium': pc(base['naive']) + f' [{pc(lo["naive"])}, {pc(hi["naive"])}]', 'strategy, gross % of premium sold': pc(base['strat']) + f' [{pc(lo["strat"])}, {pc(hi["strat"])}]'})] + [dict(split=s, cycles=len(g), **{'naive straddle, gross % of premium': pc(g.naive_pnl.sum() / g.naive_premium.sum()), 'strategy, gross % of premium sold': pc(g.gross.sum() / g.premium_sold.sum())}) for s, g in NC.groupby('split')])
equiv = NC.n_straddle_equiv.mean(); worst_n = NC.naive_pnl.min(); worst_s = NC.strat_per_straddle.min()
ab = AD.copy(); ab['variant'] = ab.index; labels = {'d1_no_timetable': 'no D-1 timetable', 'd1_no_breakout': 'no D-1 breakout pairs', 'd1_no_ladder': 'no D-1 solo ladder', 'd1_no_stops': 'no D-1 per-lot stops', 'd1_no_wings': 'no D-1 wings', 'd1_no_lump': 'no overnight lump', 'd0_no_new_sells': 'no D0 new sells', 'd0_no_waves': 'no D0 timetable waves', 'd0_no_breakout': 'no D0 breakout pairs', 'd0_no_ladder': 'no D0 solo ladder', 'd0_no_counter': 'no D0 counter-sells', 'd0_no_stop_tp': 'no D0 stop / take-profit', 'd0_no_hedge': 'no D0 hedge', 'no_cycle_stop': 'no cycle stop', 'd0_only': 'D0 module only', 'P1_flip_ladder_direction': 'PLACEBO: ladder sells the opposite right', 'P2_shift_waves_37min': 'PLACEBO: waves shifted 37 min'}
AB = pd.DataFrame([dict(variant=labels[v], **{'net Δ/cycle': k(r.net_k_diff) + f' [{r.net_k_lo / 1e3:,.0f}k, {r.net_k_hi / 1e3:,.0f}k]'.replace('-', '−'), 'gross Δ/cycle': k(r.gross_k_diff), 'net Δ IS / OOS / live': ' / '.join(k(x) for x in (r.net_diff_IS, r.net_diff_OOS, r.net_diff_LIVE_FITTED)), 'same sign in all 3': 'yes' if r.sign_consistent_across_splits else 'no', 'p5 Δ': k(r.d_p5), 'worst Δ': k(r.d_worst), 'verdict': r.verdict}) for v, r in AD.iterrows()])
full = AS.loc['full']; cost_share = 1 - full.net_mean / full.gross_mean
# ---- figure
fig, ax = plt.subplots(1, 3, figsize=(19, 6.2)); cols = ['delta', 'gamma', 'theta', 'vega', 'resid', 'execution']; x = np.arange(len(cols)); w = .38
tt = T_t.loc['ALL']; tc = T_c.loc['ALL']; ax[0].bar(x - w / 2, [tt[c] / 1e3 for c in cols], w, label='trading-minute clock', color='#2b6cb0'); ax[0].bar(x + w / 2, [tc[c] / 1e3 for c in cols], w, label='calendar clock', color='#c05621'); ax[0].axhline(0, color='k', lw=.6); ax[0].set_xticks(x); ax[0].set_xticklabels(cols); ax[0].set_ylabel('₹ thousand per cycle (actual lots)'); ax[0].set_title('Where the holding P&L comes from\n(theta/vega split depends on the clock; gamma does not)'); ax[0].legend()
ax[1].bar([0, 1], [100 * base['naive'], 100 * base['strat']], yerr=[[100 * (base['naive'] - lo['naive']), 100 * (base['strat'] - lo['strat'])], [100 * (hi['naive'] - base['naive']), 100 * (hi['strat'] - base['strat'])]], color=['#999999', '#2b6cb0'], capsize=6); ax[1].set_xticks([0, 1]); ax[1].set_xticklabels(['naive ATM straddle\nheld D-1 09:16 → D0 close', 'strategy']); ax[1].axhline(0, color='k', lw=.6); ax[1].set_ylabel('gross P&L, % of premium sold (95% week-bootstrap)'); ax[1].set_title('Per ₹ of premium sold the mean is the same;\nthe naive hold is far more dispersed')
o = AD.loc[list(labels)]; y = np.arange(len(o))[::-1]; colr = ['#2f855a' if 'LOWERS' in v else ('#c53030' if 'RAISES' in v else '#999999') for v in o.verdict]
ax[2].barh(y, o.net_k_diff / 1e3, xerr=[(o.net_k_diff - o.net_k_lo) / 1e3, (o.net_k_hi - o.net_k_diff) / 1e3], color=colr, capsize=3); ax[2].set_yticks(y); ax[2].set_yticklabels([labels[v] for v in o.index], fontsize=8); ax[2].axvline(0, color='k', lw=.6); ax[2].set_xlabel('Δ net P&L per cycle vs full strategy (₹ thousand), 95% week-cluster CI'); ax[2].set_title('Ablations and placebos\ngreen: removing lowers net · red: raises · grey: unclear', fontsize=11)
plt.tight_layout(); os.makedirs(FIG, exist_ok=True); plt.savefig(f'{FIG}/bl_bt3_alpha.png', dpi=110); plt.close()
json.dump(dict(cycles=int(n), holding_per_cycle=float(RT.holding.mean()), gross_per_cycle=float(RT.gross.mean()), execution_share=float(RT.execution.sum() / RT.gross.sum()), recon_sum=float(rec_sum), decay_trading=float(decay_t), decay_calendar=float(decay_c), gamma=float(tot_t.gamma), d0_short_share=float(d0_share), naive_ratio=float(base['naive']), strat_ratio=float(base['strat']), diff_lo=float(dif.quantile(.025)), diff_hi=float(dif.quantile(.975)), cost_share=float(cost_share)), open(f'{RES}/alpha_headline.json', 'w'), indent=1)
exec_sh = RT.execution.sum() / RT.gross.sum()
md = f"""# Where does the edge come from? — result

*Plan: `ALPHA_SOURCE_PLAN.md` (written before the tests). Data: the 275 cycles of the combined backtest (IS 175, OOS 64, rule-fitted live window 36; the 276 complete cycles less one embargo cycle; the naive benchmark has 274 because one cycle lacks a matching strike). **Exploratory** — every cycle was already used, so nothing here is out-of-sample evidence. Figure: `figures/bl_bt3_alpha.png`.*

## The answer in five lines
1. **RESULT — the profit is mainly a short-premium (short-volatility) carry; net direction is small and the fill model is not the source.** Premium decay (theta + vega + residual: **{kk(decay_t)} per cycle on the trading-minute clock, {kk(decay_c)} on the calendar clock — the same total either way**) exceeds the gamma loss (**{kk(tot_t.gamma)}**) by ≈ {kk(decay_t + tot_t.gamma)}; delta adds {kk(tot_t.delta)} and execution {kk(RT.execution.mean())} ({pc(exec_sh, 0)} of gross, below the {pc(.25, 0)} reading threshold of the plan).
2. **The edge is thin relative to the carry:** the net of decay and gamma is ≈ {pc((decay_t + tot_t.gamma) / decay_t, 0)} of the decay collected. A small change in realised versus implied volatility flips it.
3. **Per ₹ of premium sold the strategy earns the same mean as a naive straddle** ({pc(base['strat'])} vs {pc(base['naive'])}; difference {pc(base['strat'] - base['naive'])}, 95% interval [{pc(dif.quantile(.025))}, {pc(dif.quantile(.975))}]). **What the rules change is the dispersion**, not the mean return per ₹ sold (see below). The naive straddle's own mean is not distinguishable from zero in 3 years ([{pc(lo['naive'])}, {pc(hi['naive'])}]); the strategy's is ([{pc(lo['strat'])}, {pc(hi['strat'])}]).
4. **Where in time:** {pc(d0_share, 0)} of the holding P&L comes from short lots held **during the expiry day (D0)**; D-1 daytime is small, the overnight step is small.
5. **What the rules do:** the reactive *selling* rules (solo ladders, D0 waves, counter-sells) are what carries the *size* of the edge (removing them lowers gross by ₹16k–78k per cycle); **the direction of the ladder matters** (flipped-direction placebo −₹35k/cycle net, same sign in IS, OOS and live window) **and the loss sits in delta** (−₹31k of the −₹36k gross): the reactive ladder has a **trend-aligned element** (it sells calls after new lows and puts after new highs, i.e. the right moving away from the money) worth ≈ ₹31k delta P&L per cycle relative to the flipped version, although net delta over the whole book is only +₹13k. The *protective* rules (wings, lump, hedge, cycle stop) **cost mean P&L** in this simulator.

## 1. Physical decomposition (Method 1)
Holding P&L per cycle in ₹ (actual lots), split with Black–Scholes sensitivities from each contract's own implied volatility (r = 6.5%). **Reconciliation:** holding + execution equals gross P&L to within ₹{rec_sum:,.0f} in total over {n} cycles ({pc(abs(rec_sum) / RT.gross.sum(), 2)} of gross); the largest single-cycle gap is ₹{rec_worst.recon_diff:,.0f} on {rec_worst.und} {rec_worst.expiry} (cause not found; it is {pc(abs(rec_worst.recon_diff) / abs(rec_worst.gross), 1)} of that cycle).

**Trading-minute clock (primary: 375 minutes a day, 250 days; overnight is one minute):**

{fmt(T_t).to_markdown(index=False)}

**Calendar clock (sensitivity: overnight and weekends count as elapsed time):**

{fmt(T_c).to_markdown(index=False)}

* **The theta / vega split is not identified.** It depends on the clock: the overnight step shows vega {k(S.loc[('short', 'overnight step'), 'vega'])} (trading clock) versus {k(Sc.loc[('short', 'overnight step'), 'vega'])} (calendar clock). What is clock-independent: gamma ({kk(tot_t.gamma)} vs {kk(tot_c.gamma)}), delta, execution, and **theta + vega + residual** ({kk(decay_t)} vs {kk(decay_c)}). I therefore state the finding as **"premium decay minus gamma"** and do not claim "vega" or "theta" individually.
* Residual (unexplained by the model) is {kk(tot_t.resid)} on the primary clock and {kk(tot_c.resid)} on the calendar clock — the trading clock fits the data better (₹40k vs ₹175k residual per cycle), but the residual is not small enough to ignore.
* Reading rule of the plan: theta + vega is the largest positive component and delta + gamma net to a loss ⇒ **volatility-premium type**. Delta is not the main positive component; execution is {pc(exec_sh, 0)} of gross (< 25%).

**By position type and session (trading clock, ₹ per cycle):**

{S_f.to_markdown(index=False)}

Short lots held on D0 produce {pc(d0_share, 0)} of the holding P&L; long lots (wings, lump, hedge) lose {kk(-S.loc['long'].holding.sum())} per cycle on net — they are paid for with decay.

## 2. Implied versus realised volatility (observed, model-based)
ATM implied volatility (average of call and put, trading-minute clock) and realised volatility of the index minute returns (annualised on the same 93,750-minute year), averages over {len(AI)} cycles, % per year:

{iv.to_markdown(index=False)}

* On D-1, implied volatility (≈ 12–14%) is **above** realised (≈ 9%): the premium sold is rich on average.
* On D0, implied (≈ 11% at the open) is about equal to realised for NIFTY and **below** realised for SENSEX (≈ 9.8% vs 12.2% mid-day); late on D0 the ATM implied volatility is not reliable (price of a few rupees, minutes to expiry). This is consistent with the D0 gamma loss being large ({kk(S.loc[('short', 'D0 day'), 'gamma'])}) and offset by decay ({kk(S.loc[('short', 'D0 day'), 'theta'])}).
* **Not tested:** why implied exceeds realised (risk premium, demand for protection, expiry-day convexity) or whether it persists.

## 3. Naive benchmark (Method 4)
One ATM straddle sold at the D-1 09:16 open and bought back at the D0 15:14 close, no management, one lot per leg at the constant lot size. Gross, no costs. The strategy sells the equivalent of ≈ {equiv:.0f} such straddles of premium per cycle (premium sold ÷ one straddle's premium; re-sales count again).

{NV.to_markdown(index=False)}

* Per straddle, the naive hold has mean ₹{NC.naive_pnl.mean():,.0f}, worst ₹{worst_n:,.0f}, standard deviation ₹{NC.naive_pnl.std():,.0f}; the strategy per straddle-equivalent of premium has mean ₹{NC.strat_per_straddle.mean():,.0f}, worst ₹{worst_s:,.0f}, standard deviation ₹{NC.strat_per_straddle.std():,.0f}. **Dispersion per ₹ sold is about {NC.naive_pnl.std() / NC.strat_per_straddle.std():.1f}× lower in the strategy.**
* The naive result is not stable across splits (9.4% IS, 2.4% OOS, 8.7% live window); the strategy's ({pc(NC[NC.split == 'IS'].gross.sum() / NC[NC.split == 'IS'].premium_sold.sum())}, {pc(NC[NC.split == 'OOS'].gross.sum() / NC[NC.split == 'OOS'].premium_sold.sum())}, {pc(NC[NC.split == 'LIVE_FITTED'].gross.sum() / NC[NC.split == 'LIVE_FITTED'].premium_sold.sum())}) is positive in all three but varies too.
* **Caveat:** "premium sold" counts every re-sale, so the strategy's denominator is inflated by turnover; the comparison per ₹ is not per ₹ of risk. The ratio test does not show that the rules add mean return per unit of premium; it shows they do not obviously subtract it, while taking it with much smaller dispersion.

## 4. Ablations and placebos (Methods 2 and 3)
Re-running the whole chain with one rule removed (or broken). Δ vs the full strategy, per cycle, net of costs, with a week-cluster bootstrap interval; p5 Δ and worst Δ are the changes in the 5th-percentile and worst cycle (negative = the variant has a worse tail).

{AB.to_markdown(index=False)}

* **Selling rules carry the size of the edge** (D-1 ladder, D0 new sells, waves, ladder, counter-sells). Caution: removing a selling rule also removes premium sold, so this is *scale* as well as *timing*. The two tests that keep the amount of selling and break something else:
  * **P1 direction:** selling the opposite right on the reactive ladder lowers net by {k(AD.loc['P1_flip_ladder_direction'].net_k_diff)} per cycle (interval [{AD.loc['P1_flip_ladder_direction'].net_k_lo / 1e3:,.0f}k, {AD.loc['P1_flip_ladder_direction'].net_k_hi / 1e3:,.0f}k]), same sign in IS, OOS and the live window ⇒ **the direction of the reactive sale is part of the edge** (it sells the right that is moving away from the money). In the flipped variant the change is almost entirely in **delta** (−₹31k of −₹36k gross; gamma +₹5k, theta −₹6k, vega −₹10k): the real ladder's direction earns directional P&L, the flipped one gives it back. So **the reactive ladder is partly a short-horizon trend-aligned (momentum) rule**, not only premium collection (Observed in the simulator; the mechanism beyond that is Inferred).
  * **P2 timing:** shifting scheduled waves by 37 minutes lowers net by {k(AD.loc['P2_shift_waves_37min'].net_k_diff)} [{AD.loc['P2_shift_waves_37min'].net_k_lo / 1e3:,.0f}k, {AD.loc['P2_shift_waves_37min'].net_k_hi / 1e3:,.0f}k] but the sign is **not** the same in all three splits (live window +₹6k): the exact minute of the waves is **at most weakly** supported.
* **Protective rules cost mean:** no wings {k(AD.loc['d1_no_wings'].net_k_diff)}, no lump {k(AD.loc['d1_no_lump'].net_k_diff)}, no hedge {k(AD.loc['d0_no_hedge'].net_k_diff)}, no cycle stop {k(AD.loc['no_cycle_stop'].net_k_diff)} per cycle (all with intervals above zero and the same sign in all splits). The tail benefit in the simulation is small or absent for wings (p5 improves without them; worst cycle worsens by ₹90k) and clear for the cycle stop (p5 −₹61k, worst −₹74k without it). **Margin and capital are not modelled here** — if the real system holds wings and a hedge for margin relief, the simulator cannot see that benefit (Unresolved).
* **Costs are half the gross edge:** the full strategy earns ₹{full.gross_mean:,.0f} gross and ₹{full.net_mean:,.0f} net per cycle at constant lot size ({pc(cost_share, 0)} lost to slippage, statutory costs and ₹20/order over ≈ {full.orders:,.0f} orders per cycle). Gross-only effects in the table (for example the D-1 timetable: gross {k(AD.loc['d1_no_timetable'].gross_k_diff)} with an interval excluding zero, net {k(AD.loc['d1_no_timetable'].net_k_diff)} with an interval including zero) are **not established net of costs**. Real broker costs are unknown.

## 5. What is and is not supported
| claim | evidence level |
|---|---|
| The profit is carry from selling premium (decay exceeds gamma loss) | **Observed** (clock-independent total), model-based decomposition |
| Directional beta is not the main source | **Observed**: net delta {kk(tot_t.delta)} of {kk(RT.holding.mean())} holding; but the ladder's direction is worth ≈ ₹31k delta per cycle against the flipped placebo (trend-aligned element) |
| It is not produced by the fill model | **Observed**: execution term {pc(exec_sh, 0)} of gross (but a 10% dependence on the assumed fill position remains) |
| Direction of the reactive sale matters | **Observed** in the simulator (placebo, same sign in IS / OOS / live), exploratory |
| The exact minute of the waves matters | **Weak** (sign not consistent across splits) |
| The management rules raise the mean return per ₹ sold | **Not supported** (difference {pc(base['strat'] - base['naive'])}, interval [{pc(dif.quantile(.025))}, {pc(dif.quantile(.975))}]) |
| The rules reduce dispersion per ₹ sold ≈ 3× | **Observed** (per straddle-equivalent, naive hold vs strategy) |
| Wings, lump, hedge protect the tail | **Not supported in this simulator**; margin benefit not modelled (**Unresolved**) |
| Implied volatility exceeds realised on D-1 | **Observed** (model-based ATM IV, trading clock) |
| The premium is a persistent, tradable risk premium | **Not testable here** (3 years, naive straddle's mean not distinguishable from zero) |
| Edge survives real costs | **Unknown** (cost model inherited, half the gross) |

## 6. Adversarial notes — why this could be fake
* **Same data used many times.** The exploratory ablations reuse every cycle; nothing here is untouched evidence.
* **Greek attribution is a model** (Black–Scholes, r = 6.5%, no dividends, per-contract implied volatility, minute marks); the residual is {kk(tot_t.resid)}–{kk(tot_c.resid)} per cycle; the vega/theta split flips sign with the clock; overnight and expiry-minute implied volatilities are unreliable.
* **Ablation = my simulator with the assumed D-1 and D0 timetable**, causal fill pricing, and the 0.30 / 0.62 fill positions; a different (real) rule detail could change the ranking.
* **The strategy is a short-volatility book with a fat left tail** (worst cycle ≈ −₹1.3 million on a ₹2 crore base; p5 ≈ −₹377k); an apparently stable carry in 3 years that includes only a few stress events can end with a loss that wipes many cycles.
* **Per-₹-premium comparison is not per-unit-of-risk.**
* The naive straddle's mean is statistically indistinguishable from zero, so "the strategy beats the naive hold" is **not** claimed; the claim is "similar mean per ₹ sold, much lower dispersion".

## 7. Next tests (not run)
1. More years (2020–2022) for the naive-carry and per-₹-premium comparison — the cheapest way to reduce the uncertainty in item 3.
2. A margin model (SPAN-style) to price the wings/hedge benefit the simulator cannot see.
3. Day-shifted placebo (shift all selling rules by one day) as a second timing test.
4. Real broker costs, then repeat the net-of-cost ablations.
5. Forward / paper trading against this pre-registered reading.
"""
open(f'{RP}/ALPHA_SOURCE.md', 'w').write(md); print(md[:2500]); print(json.load(open(f'{RES}/alpha_headline.json')))
