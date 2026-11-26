"""Builds reports/PREMIUM_AND_ARCHITECTURE.md and figures/bl_premium_arch.png (plan reports/PREMIUM_AND_ARCHITECTURE_PLAN.md)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); PR = f'{OUT}/premium'; AR = f'{OUT}/arch'; RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures'); RES = f'{OUT}/bt3_results'
def _md(d):
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return '| ' + ' | '.join(map(str, d.columns)) + ' |\n|' + '---|' * len(d.columns) + '\n' + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
P = pd.read_csv(f'{PR}/premium_stats.csv'); C = pd.read_csv(f'{PR}/premium_cycles.csv'); A = pd.read_csv(f'{AR}/arch_stats.csv'); G = pd.read_csv(f'{AR}/arch_gap.csv'); NG = json.load(open(f'{OUT}/unres/nightgap_summary.json')); FC = json.load(open(f'{OUT}/final/final_checks.json')); _g = pd.read_csv(f'{OUT}/unres/cycle_night_gaps.csv').gap_min_0916.abs(); obs = dict(max_abs_gap_pct=100 * float(_g.max()), n_over_2pct=int((_g > .02).sum()), n_over_1pct=int((_g > .01).sum()))
AD = pd.read_csv(f'{RES}/ablate_diffs.csv').set_index('variant'); AS = pd.read_csv(f'{RES}/ablate_summary.csv').set_index('variant')
p = lambda q, s, st: P[(P.q == q) & (P.segment == s) & (P.stat == st)].iloc[0]; pc = lambda x, d=0: f'{100 * x:.{d}f}%'; ci = lambda r, f=lambda x: f'{x:.2f}': f'{f(r.value)} [{f(r.lo)}, {f(r.hi)}]'
seg = ['D-1 day', 'overnight', 'D0 day']
# ---- A tables
A1 = pd.DataFrame([dict(segment=s, **{'realised ÷ implied': ci(p('A1', s, 'realised / implied (all variance)')),
     'continuous ÷ implied': ci(p('A1', s, 'continuous (bipower) / implied')) if s != 'overnight' else '— (all jump)',
     'jump share of realised': ci(p('A1', s, 'jump share of realised variance'), lambda x: pc(x)) if s != 'overnight' else '100% (gap)',
     'median cycle ratio': f"{p('A1', s, 'median per-cycle ratio').value:.2f}", 'cycles with ratio > 1': pc(p('A1', s, 'share of cycles with ratio > 1').value),
     'top 10% of cycles carry': pc(p('A1', s, 'share of realised variance from the top 10% of cycles').value) + ' of realised', 'P&L skewness': f"{p('A1', s, 'skewness of short-straddle P&L (% of premium)').value:.1f}",
     'NIFTY / SENSEX ratio': f"{p('A1', s, 'realised / implied, NIFTY').value:.2f} / {p('A1', s, 'realised / implied, SENSEX').value:.2f}"}) for s in seg])
a2 = lambda st: p('A2', 'overnight', st); A2 = pd.DataFrame([dict(group=g, cycles=int(a2(f'{g}: cycles').value), **{'implied overnight variance (bp²)': f"{a2(f'{g}: implied variance consumed (bp^2)').value:,.0f}", 'realised gap variance (bp²)': f"{a2(f'{g}: realised gap variance (bp^2)').value:,.0f}", 'realised ÷ implied': ci(a2(f'{g}: realised / implied'))}) for g in ('1 calendar day', '2-4 calendar days')])
A3 = pd.DataFrame([dict(segment=s, **{'before 20 Nov 2024': f"{P[(P.q == 'A3') & (P.segment == s) & P.stat.str.contains('before 20 Nov')].iloc[0].value:.2f}", 'after': f"{P[(P.q == 'A3') & (P.segment == s) & P.stat.str.contains('after 20 Nov')].iloc[0].value:.2f}",
     'after − before [95%]': ci(p('A3', s, 'ratio after minus before (+ = premium shrank)')), 'NIFTY / SENSEX change': f"{p('A3', s, 'ratio after minus before, NIFTY').value:+.2f} / {p('A3', s, 'ratio after minus before, SENSEX').value:+.2f}"}) for s in seg])
vol = {u: p('A3', 'D-1 first hour', f'{u} volume (units), atm: after / before median').value for u in ('NIFTY', 'SENSEX')}; rho = {s: P[(P.q == 'A3') & (P.segment == s) & P.stat.str.startswith('Spearman')].iloc[0] for s in ('overnight', 'D0 day')}
A4 = pd.DataFrame([dict(segment=s, **{t: f"{P[(P.q == 'A4') & (P.segment == s) & P.stat.str.contains(f'tercile {t} ')].iloc[0].value:.2f}" for t in ('low', 'mid', 'high')}) for s in seg])
# ---- B tables
lab = {'d1_no_wings': 'no D-1 longs (wings + lump)', 'd1_no_lump': 'no overnight lump', 'd0_no_hedge': 'no D0 hedge controller', 'd1_no_stops': 'no D-1 per-lot stops', 'd0_no_stop_tp': 'no D0 stop / take-profit', 'no_cycle_stop': 'no cycle stop', 'full': 'full strategy'}
B1 = []
for v in ['full', 'd1_no_wings', 'd1_no_lump', 'd0_no_hedge', 'd1_no_stops', 'd0_no_stop_tp', 'no_cycle_stop']:
    r = {ps: A[(A.variant == v) & (A.psr == ps) & (A.vsr == 0.04)].iloc[0] for ps in (0.04, 0.06, 0.093)}
    B1.append({'variant': lab[v], 'net ₹/cycle': f"{r[0.06].net_per_cycle:,.0f}", 'median peak margin, ₹ cr (PSR 4 / 6 / 9.3%)': ' / '.join(f'{r[x].median_peak_margin / 1e7:.2f}' for x in (0.04, 0.06, 0.093)),
               'cycles with peak margin > ₹2 cr': ' / '.join(pc(r[x].share_peak_over_2cr) for x in (0.04, 0.06, 0.093)), 'overnight margin vs full': ('—' if v == 'full' else ' / '.join(f'{r[x].d1_close_margin_ratio:.2f}×' for x in (0.04, 0.06, 0.093))),
               'return on peak margin, Δ vs full [95%] (PSR 6%)': ('—' if v == 'full' else f"{100 * r[0.06].rom_diff_vs_full:+.2f} pp [{100 * r[0.06].rom_diff_lo:+.2f}, {100 * r[0.06].rom_diff_hi:+.2f}]"),
               'p5 / worst cycle (₹k)': f"{AS.loc[v].net_p5 / 1e3:,.0f} / {AS.loc[v].net_worst / 1e3:,.0f}"})
B1 = pd.DataFrame(B1)
gm = G.groupby(['variant', 'gap', 'vol_mult']).loss.mean().unstack('variant'); g125 = gm.xs(1.25, level='vol_mult'); g1 = gm.xs(1.0, level='vol_mult')
GT = pd.DataFrame({'overnight gap': [f'{100 * x:+.0f}%' for x in g125.index], 'full (mean loss, ₹ lakh)': (g125['full'] / 1e5).round(1).values, 'no D-1 longs': (g125['d1_no_wings'] / 1e5).round(1).values, 'no lump': (g125['d1_no_lump'] / 1e5).round(1).values, 'no D-1 stops': (g125['d1_no_stops'] / 1e5).round(1).values})
cost_w = AD.loc['d1_no_wings'].net_k_diff; cost_l = AD.loc['d1_no_lump'].net_k_diff
save5 = ((g125['d1_no_wings'] - g125['full']).loc[[-0.05, 0.05]].mean()); save3 = ((g125['d1_no_wings'] - g125['full']).loc[[-0.03, 0.03]].mean())
be5 = cost_w / save5; be3 = cost_w / save3
r6 = lambda v: A[(A.variant == v) & (A.psr == 0.06) & (A.vsr == 0.04)].iloc[0]; r93 = lambda v: A[(A.variant == v) & (A.psr == 0.093) & (A.vsr == 0.04)].iloc[0]
# ---- figure
fig, ax = plt.subplots(2, 2, figsize=(15, 10)); x = np.arange(3)
ax[0, 0].bar(x - .2, [p('A1', s, 'realised / implied (all variance)').value for s in seg], .2, label='all realised ÷ implied', color='k')
ax[0, 0].bar(x, [p('A1', 'D-1 day', 'continuous (bipower) / implied').value, 0, p('A1', 'D0 day', 'continuous (bipower) / implied').value], .2, label='continuous (no jumps) ÷ implied', color='#2b6cb0')
ax[0, 0].bar(x + .2, [p('A1', s, 'median per-cycle ratio').value for s in seg], .2, label='median cycle', color='#c05621'); ax[0, 0].axhline(1, color='#c53030', ls='--'); ax[0, 0].set_xticks(x); ax[0, 0].set_xticklabels(seg); ax[0, 0].legend(fontsize=8)
ax[0, 0].set_title('A1: overnight = rare-gap insurance (median night realises 27%)\nD0 = steady over-pricing even without jumps')
for s, col in zip(seg, ('#2b6cb0', 'k', '#c05621')):
    rv = {'D-1 day': 'rv_d1', 'overnight': 'gap2', 'D0 day': 'rv_d0'}[s]; v = np.sort(C[rv].dropna().values)[::-1]; ax[0, 1].plot(np.arange(1, len(v) + 1) / len(v) * 100, np.cumsum(v) / v.sum() * 100, color=col, label=s)
ax[0, 1].plot([0, 100], [0, 100], color='#999999', ls=':'); ax[0, 1].set_xlabel('% of cycles (largest realised variance first)'); ax[0, 1].set_ylabel('% of total realised variance'); ax[0, 1].legend(); ax[0, 1].set_title('Concentration: 10% of nights carry 68% of the overnight variance')
vv = ['full', 'd1_no_wings', 'd1_no_lump', 'd0_no_hedge', 'd1_no_stops', 'd0_no_stop_tp', 'no_cycle_stop']; ac = pd.read_csv(f'{AR}/arch_cycles.csv'); ac = ac[(ac.psr == 0.06) & (ac.vsr == 0.04)]
ax[1, 0].boxplot([ac[ac.variant == v].peak_margin / 1e7 for v in vv], showfliers=False); ax[1, 0].set_xticks(range(1, len(vv) + 1)); ax[1, 0].set_xticklabels([lab[v].replace("no ", "no\n") for v in vv]); ax[1, 0].axhline(2, color='#c53030', ls='--', label='₹2 crore capital'); ax[1, 0].legend(); ax[1, 0].tick_params(axis='x', labelsize=7)
ax[1, 0].set_ylabel('peak approximate margin, ₹ crore (PSR 6%)'); ax[1, 0].set_title('B: D0 hedge and D0 stops keep the expiry-day book inside ₹2 crore')
for v, col in (('full', 'k'), ('d1_no_wings', '#c53030'), ('d1_no_lump', '#c05621'), ('d1_no_stops', '#2b6cb0')):
    ax[1, 1].plot(100 * g125.index, g125[v] / 1e5, marker='o', color=col, label=lab[v])
ax[1, 1].axvspan(-obs['max_abs_gap_pct'], obs['max_abs_gap_pct'], color='#2f855a', alpha=.1, label=f'gaps seen in 3 years (max {obs["max_abs_gap_pct"]:.1f}%)'); ax[1, 1].set_xlabel('overnight index gap, %'); ax[1, 1].set_ylabel('mean loss of the carried book, ₹ lakh (IV × 1.25)'); ax[1, 1].legend(fontsize=8)
ax[1, 1].set_title('B: with wings the gap loss stops growing beyond ~3%;\nlargest tradeable gap in the sample 2.8%')
plt.tight_layout(); os.makedirs(FIG, exist_ok=True); plt.savefig(f'{FIG}/bl_premium_arch.png', dpi=110); plt.close()
json.dump(dict(overnight_median_ratio=float(p('A1', 'overnight', 'median per-cycle ratio').value), overnight_top10=float(p('A1', 'overnight', 'share of realised variance from the top 10% of cycles').value), d0_jump_share=float(p('A1', 'D0 day', 'jump share of realised variance').value),
               d0_continuous_ratio_hi=float(p('A1', 'D0 day', 'continuous (bipower) / implied').hi), sebi_diff_lo={s: float(p('A3', s, 'ratio after minus before (+ = premium shrank)').lo) for s in seg}, sebi_diff_hi={s: float(p('A3', s, 'ratio after minus before (+ = premium shrank)').hi) for s in seg},
               over2cr={v: float(r93(v).share_peak_over_2cr) for v in vv}, overnight_margin_ratio_wings={str(ps): float(A[(A.variant == 'd1_no_wings') & (A.psr == ps) & (A.vsr == 0.04)].iloc[0].d1_close_margin_ratio) for ps in (0.04, 0.06, 0.093)},
               max_gap=obs['max_abs_gap_pct'], breakeven_5pct=float(be5), breakeven_3pct=float(be3)), open(f'{AR}/premium_arch_summary.json', 'w'), indent=1)
md = f"""# Why the premium exists, and why Algo 8 is built the way it is

> **Corrections, 24 Nov 2026 (two rounds).** (1) The overnight gaps here are measured to the **09:16** open, the first minute a book can trade; the largest on a cycle night is **{obs['max_abs_gap_pct']:.2f}%**. A first round of corrections replaced this with the 09:15 first print (4.62% on 3 Feb 2026); the raw bars show that print existed only at the opening tick — NIFTY was back to +{100 * FC['feb3']['gap_after_first_minute']:.2f}% by the end of that minute and several 09:15 option prints were stale — so the 09:16 basis is the right one for P&L and is restored. (2) On 3 Feb 2026 the long legs' **overnight** protection was worth **₹{FC['feb3_overnight_difference'] / 1e5:.2f} lakh** (mark-to-market of the carried book at the first tradeable minute, with vs without them); the ₹{FC['feb3_net_difference'] / 1e5:.2f} lakh difference in the two cycles' net results mostly comes from different D0 management, not the gap. Earlier text that said '≈ ₹7 lakh to the long legs' was a wrong attribution. (3) The first-print overnight ratios quoted in the first correction (0.63 / 0.39 / 63%) used partly stale 09:15 option prints and are withdrawn; the 09:16-basis figures below stand. See `UNRESOLVED_THREE.md` §0.

*Plan: `PREMIUM_AND_ARCHITECTURE_PLAN.md` (written before the tests). 275 cycles, Nov 2023 – Nov 2026. Every cycle was used before: **exploratory**. Figure: `figures/bl_premium_arch.png`. Builds on `DESIGN_THESIS.md`.*

## The refined idea (version 2)
The first version ("options near expiry are over-priced; sell them, carry overnight, re-balance, survive the tails") holds. The tests below split it into **two different premia with two different causes**, and show that the inventory architecture is shaped by **margin and the gap tail**, not by return:

> **1. The overnight premium is gap insurance.** On a typical night the opening gap realises about a quarter of the variance that was priced (median {p('A1', 'overnight', 'median per-cycle ratio').value:.2f}); the premium is paid back on rare large gaps (the top 10% of nights carry {pc(p('A1', 'overnight', 'share of realised variance from the top 10% of cycles').value)} of all realised gap variance; P&L skewness {p('A1', 'overnight', 'skewness of short-straddle P&L (% of premium)').value:.1f}). Selling the overnight is **selling insurance against a gap**.
>
> **2. The expiry-day premium is a steady over-pricing, not jump insurance.** Jumps are only {pc(p('A1', 'D0 day', 'jump share of realised variance').value)} of D0 realised variance; even the smooth (continuous) part is only {p('A1', 'D0 day', 'continuous (bipower) / implied').value:.2f} of what is priced, and the typical day realises {p('A1', 'D0 day', 'median per-cycle ratio').value:.2f}. Something other than tail risk keeps expiry-day options rich. The leading remaining candidate (**Inferred, untested**) is structural demand for short-dated options and the inventory cost of the sellers who supply it; it cannot be identified here without signed order flow.
>
> **3. Algo 8 sells the middle of the gap distribution and buys back the far tail.** Its overnight book is covered by cheap far wings and the lump; with them the carried book's mean gap loss **stops growing beyond about 3%** (≈ ₹{g125.loc[[-0.03, 0.03], 'full'].mean() / 1e5:.0f}–{g125.loc[[-0.05, 0.05], 'full'].max() if False else g125.loc[[-0.05, -0.03, 0.03, 0.05], 'full'].max() / 1e5:.0f} lakh) while without them it keeps growing (≈ ₹{g125.loc[[-0.05, 0.05], 'd1_no_wings'].mean() / 1e5:.0f} lakh at ±5%), and they cut the overnight margin to {1 / r6('d1_no_wings').d1_close_margin_ratio:.2f}× (PSR 6%) of an unhedged book, but cost ≈ ₹{cost_w / 1e3:.1f}k per cycle. The largest tradeable overnight gap on a cycle night in 3 years was **{obs['max_abs_gap_pct']:.1f}%** (NIFTY, 3 Feb 2026, whose opening tick printed 4.6%); that night the long legs saved ≈ ₹{FC['feb3_overnight_difference'] / 1e5:.1f} lakh of overnight mark-to-market (≈ {FC['feb3_overnight_difference'] / cost_w:.0f} average cycles of their cost). Nothing near 5–13% occurred, so the sample cannot show their value there.
>
> **4. The expiry-day rules are capital rules.** Without the D0 hedge controller or the D0 stop/take-profit, the expiry-day book outgrows ₹2 crore of approximate margin in {pc(r93('d0_no_hedge').share_peak_over_2cr)} and {pc(r93('d0_no_stop_tp').share_peak_over_2cr)} of cycles (PSR 9.3%; {pc(r93('full').share_peak_over_2cr)} with them). They exist to keep the size the capital allows, and they also cut the expiry-day scenario loss.

## Question 1 — why does the premium exist?
| Mechanism | Verdict | Key evidence |
|---|---|---|
| **Jump / gap insurance** | **Supported for the overnight**; **not the main reason on D-1 and D0** | Overnight: median night 0.27 of priced, 15% of nights above priced, top 10% carry 68%; D-1/D0: jumps 7–10% of realised variance and the continuous part alone is well below implied |
| **Closed-market / calendar-time pricing** (weekends priced, not realised) | **Not supported** (18 cycles; descriptive) | Multi-day gaps price {a2('2-4 calendar days: implied variance consumed (bp^2)').value / a2('1 calendar day: implied variance consumed (bp^2)').value:.1f}× the variance of a one-night gap and realise {a2('2-4 calendar days: realised gap variance (bp^2)').value / a2('1 calendar day: realised gap variance (bp^2)').value:.1f}×: weekends are **not** over-priced relative to single nights |
| **Demand pressure for options** | **Not testable with this data** (neither supported nor refuted) | Volume rose, not fell, after SEBI's 20 Nov 2024 measures (NIFTY ×{vol['NIFTY']:.1f}, SENSEX ×{vol['SENSEX']:.1f} in units; lot sizes changed and SENSEX weeklies grew); the premium did not shrink reliably; pre-determined volume does not predict the premium (Spearman {rho['overnight'].value:+.2f} overnight, {rho['D0 day'].value:+.2f} D0). Volume is not **net buying**; the mechanism needs signed flow |
| **Time-varying risk premium** | **Descriptive** | On D-1 and D0 the premium is largest when implied volatility is high (D0 ratio 1.06 in the low-IV third: no premium); overnight the opposite (richest in calm cycles) |

### A1 — jumps vs continuous variance
{_md(A1)}

* **Overnight** is the textbook insurance profile: most nights cheap, a few nights expensive, strongly negative skew.
* **D-1 and D0** are not: the premium survives with jumps removed, and the typical day realises less than priced. NIFTY is richer than SENSEX in every segment (D0 SENSEX ratio {p('A1', 'D0 day', 'realised / implied, SENSEX').value:.2f}, close to fair).

### A2 — weekends and holidays (overnight)
{_md(A2)}

### A3 — demand: SEBI natural experiment (effective 20 Nov 2024)
{_md(A3)}

The before/after shifts are mixed in sign and their intervals include zero. Confounds: volatility regime, NIFTY's expiry weekday change, lot-size changes, SENSEX's growth as BSE's only weekly. **Not a clean test of demand.**

### A4 — by implied-volatility level (D-1 opening ATM IV terciles, realised ÷ implied)
{_md(A4)}

## Question 2 — why this inventory architecture?
Approximate exchange margin (SPAN-like scenario margin + 2% exposure margin on short notional, + 2% on expiry day from 20 Nov 2024). **The NSE price scan range could not be verified**, so every result is shown for 4%, 6% and 9.3% (volatility scan 4 points; 0 and 8 give the same conclusions, `outputs/arch/arch_stats.csv`). Constant lot size. Peak margin is evaluated every 15 minutes of both days.

{_md(B1)}

**Overnight gap stress** of the book carried at the D-1 close (mean over cycles; implied volatility × 1.25; time value kept, i.e. conservative; D0 actions after the gap not included):

{_md(GT)}

Largest overnight gap actually seen in 3 years: **{obs['max_abs_gap_pct']:.2f}%** (only {obs['n_over_2pct']} cycles above 2%, {obs['n_over_1pct']} above 1%).

### Component by component
| Component | Tail it protects against | Cost | Margin effect | What happens without it |
|---|---|---|---|---|
| **Wings (all D-1 longs)** | Overnight gap beyond ~2% | ≈ ₹{cost_w / 1e3:.1f}k per cycle (net) | Overnight margin {r6('d1_no_wings').d1_close_margin_ratio:.2f}× higher without them at PSR 6% ({A[(A.variant == 'd1_no_wings') & (A.psr == 0.04) & (A.vsr == 0.04)].iloc[0].d1_close_margin_ratio:.2f}× at 4%, {r93('d1_no_wings').d1_close_margin_ratio:.2f}× at 9.3%); **peak** margin almost unchanged (the peak is on D0) | Higher mean P&L and return on peak margin in this sample; mean loss in a ±5% gap ≈ {g125.loc[[-0.05, 0.05], 'd1_no_wings'].mean() / 1e5:.0f} lakh instead of {g125.loc[[-0.05, 0.05], 'full'].mean() / 1e5:.0f} lakh. **Break-even:** they pay for themselves if a ±5% gap happens more than once every {1 / be5:.0f} cycles (≈ {1 / be5 / 104:.1f} years at two expiries a week; ±3%: once every {1 / be3:.0f} cycles) |
| **Overnight lump** | Gap on the heavier side | ≈ ₹{cost_l / 1e3:.1f}k per cycle | Overnight margin {r6('d1_no_lump').d1_close_margin_ratio:.2f}× without it | Gap loss about {g125.loc[[-0.05, 0.05], 'd1_no_lump'].mean() / g125.loc[[-0.05, 0.05], 'full'].mean():.1f}× larger at ±5% |
| **D0 hedge controller** | Expiry-day intraday move | ≈ ₹{AD.loc['d0_no_hedge'].net_k_diff / 1e3:.1f}k per cycle | Median peak margin {r6('full').median_peak_margin / 1e7:.2f} → {r6('d0_no_hedge').median_peak_margin / 1e7:.2f} cr (PSR 6%); cycles above ₹2 cr {pc(r6('full').share_peak_over_2cr)} → {pc(r6('d0_no_hedge').share_peak_over_2cr)} | **Does not fit the capital**; return on peak margin lower at PSR 9.3% (interval excludes zero) |
| **D0 stop / take-profit** | Expiry-day book growth (path) | mean +₹{AD.loc['d0_no_stop_tp'].net_k_diff / 1e3:.0f}k without it (interval includes 0) | Median peak margin {r6('d0_no_stop_tp').median_peak_margin / 1e7:.2f} cr — **above ₹2 crore** in {pc(r6('d0_no_stop_tp').share_peak_over_2cr)} of cycles | Peak margin ≈ {r6('d0_no_stop_tp').median_peak_margin / r6('full').median_peak_margin:.1f}× higher; the strategy as sized cannot run on ₹2 crore |
| **D-1 per-lot stops** | Trending D-1 (path) | removing them lowers net by ₹{-AD.loc['d1_no_stops'].net_k_diff / 1e3:.0f}k (interval includes 0) | Overnight margin {r6('d1_no_stops').d1_close_margin_ratio:.2f}× without them | Worse return on margin ({100 * r6('d1_no_stops').rom_diff_vs_full:+.2f} pp, interval includes 0), larger gap loss |
| **Cycle stop (≈ ₹1.2–1.4 lakh)** | A bad day turning into a disaster | ≈ ₹{AD.loc['no_cycle_stop'].net_k_diff / 1e3:.0f}k per cycle | Cycles above ₹2 cr {pc(r6('full').share_peak_over_2cr)} → {pc(r6('no_cycle_stop').share_peak_over_2cr)} | 5th-percentile cycle ₹{abs(AD.loc['no_cycle_stop'].d_p5) / 1e3:,.0f}k worse, worst ₹{abs(AD.loc['no_cycle_stop'].d_worst) / 1e3:,.0f}k worse |

**Reading against the plan's rule:** no protective component raises the **return on peak margin** in this sample (wings and lump lower it slightly, intervals excluding zero; the others are within noise, except the D0 hedge at PSR 9.3% which helps). So none "pays for itself after margin" **in this 3-year sample, whose largest gap was {obs['max_abs_gap_pct']:.1f}%**. Their measurable jobs are: (a) **capital feasibility** — the D0 hedge and D0 stops keep the expiry-day book within ₹2 crore; (b) **gap insurance** — the wings and lump halve losses in gaps the sample did not contain; (c) **path protection** — the stops cut the 5th-percentile and worst cycles.

## How the two questions connect
The overnight premium exists **because** of rare large gaps (Q1). A seller who keeps the whole overnight premium also keeps the whole gap tail. Algo 8 keeps the part of the premium paid for gaps of roughly 1–3% and **buys back the far tail** with wings that cost ≈ ₹{cost_w / 1e3:.0f}k a cycle. In this 3-year sample the largest gap was {obs['max_abs_gap_pct']:.1f}% and the long legs cost ≈ ₹{cost_w / 1e3:.0f}k a cycle net (that figure already includes their payoff on the 3 Feb 2026 night). Whether they pay in expectation depends on gaps larger than any in the sample (see `UNRESOLVED_THREE.md`).

## Evidence levels
| Claim | Level |
|---|---|
| Overnight premium = gap insurance (rare, concentrated, negative skew) | **Observed** (3 years, market data) |
| D0 premium is not jump compensation | **Observed** |
| Weekends are over-priced relative to single nights | **Not supported** (descriptive, 15 cycles) |
| Demand pressure causes the premium | **Not testable** with OHLCV + volume (no signed flow) |
| D0 hedge and D0 stops keep the book within ₹2 crore | **Observed under the approximate margin model**, across the scan-range grid |
| Wings and lump cap the overnight gap loss (flat beyond ~3%) and halve the overnight margin | **Observed** under the model (stress, not history) |
| Wings pay for themselves | **Unresolved**: break-even needs a ±5% gap about once every {1 / be5:.0f} cycles; the 3 years' largest tradeable gap was {obs['max_abs_gap_pct']:.1f}% (overnight value of the legs that night ≈ ₹{FC['feb3_overnight_difference'] / 1e5:.1f} lakh) |
| The real broker margin equals this model | **Unknown** (PSR not verified; real margin calls, peak-margin snapshots, broker add-ons not modelled) |

## Next tests
1. The real NSE SPAN risk-parameter files (price scan range per day) to replace the grid.
2. 2020–2022 chains: the March 2020 gaps are exactly the tail the wings insure.
3. Signed flow (open-interest change by strike, buyer/seller-initiated volume) to test demand.
"""
open(f'{RP}/PREMIUM_AND_ARCHITECTURE.md', 'w').write(md); print(json.load(open(f'{AR}/premium_arch_summary.json')))
