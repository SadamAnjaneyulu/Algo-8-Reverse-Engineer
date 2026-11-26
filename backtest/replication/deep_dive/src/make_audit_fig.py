"""Power curves and baseline-noise false-positive figure for reports/POWER_ANALYSIS.md -> outputs/audit/power_curves.png (palette validated: blue ramp for the ordered effect sizes; blue/orange/aqua for the three baselines)."""
import os, numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
AU = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs', 'audit'); P = pd.read_csv(f'{AU}/power_sim.csv'); L = pd.read_csv(f'{AU}/power_large_n.csv'); L['effect'] = L.effect.map(lambda x: f'+{float(x):.3f}'); CF = pd.read_csv(f'{AU}/power_crossfit.csv')
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'; BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'; ramp = {'+0.098': '#08306b', '+0.075': '#2171b5', '+0.050': '#4292c6', '+0.025': '#9ecae1', '0.000': '#9a9993'}
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK, 'font.size': 10, 'axes.titlesize': 11, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'axes.spines.top': False, 'axes.spines.right': False, 'grid.color': GRID, 'axes.grid': True, 'axes.axisbelow': True, 'axes.grid.axis': 'y'})
fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.9)); a = ax[0]
for eff, col in ramp.items():
    d = P[(P.scenario == 'exact') & (P.method == 'lin') & (P.design == 'fixed') & (P.effect == eff)].sort_values('N_or_maxN'); u = pd.Series(list(d.rejection_rate), index=list(d.N_or_maxN))
    if eff in ('+0.050', '+0.025'): e = L[L.effect == eff]; u = pd.concat([u, pd.Series(list(e.power), index=list(e.N))]); u = u[~u.index.duplicated(keep='last')].sort_index()
    a.plot(u.index, u.values, color=col, lw=2.2, marker='o', ms=4, label=f'true Δ = {eff}')
a.axhline(0.8, color=INK2, ls=':', lw=1); a.text(9.5, 0.82, '80% power', fontsize=8.5, color=INK2); a.axvline(30, color=INK2, ls='--', lw=1); a.text(30.8, 0.46, '30 cycles', fontsize=8.5, color=INK2, rotation=90, va='bottom')
a.set_xscale('log'); a.set_xlim(9, 700); a.set_ylim(0, 1.03); a.set_xticks([10, 20, 30, 60, 100, 200, 400]); a.set_xticklabels(['10', '20', '30', '60', '100', '200', '400']); a.minorticks_off()
a.set_xlabel('confirmatory cycles (single analysis, 5% two-sided, exact clock)'); a.set_ylabel('probability that the lower bound is above 0'); a.set_title('Power by true effect size'); a.legend(frameon=False, loc='lower right', fontsize=9)
b = ax[1]; xs = [30, 60, 90]
def rate(scen, n): return float(P[(P.scenario == scen) & (P.method == 'lin') & (P.design == 'fixed') & (P.effect == '0.000') & (P.N_or_maxN == n)].rejection_rate.iloc[0])
ex = {n: rate('exact', n) for n in (30, 60, 80, 100)}; ex[90] = (ex[80] + ex[100]) / 2; bn = {n: rate('burnin', n) for n in (30, 60, 80, 100)}; bn[90] = (bn[80] + bn[100]) / 2
cf = {n: float(CF[(CF.method == 'lin') & (CF.design == f'fixed{n}') & (CF.effect == '0.000')].rejection_rate.iloc[0]) for n in xs}
for dct, lab, col, mk, dy in ((bn, 'burn-in-only clock', ORANGE, '^', 0.0), (cf, 'cross-fitted clock', AQUA, 's', 0.016), (ex, 'exact clock', BLUE, 'o', -0.016)):
    b.plot(xs, [dct[n] for n in xs], color=col, lw=2.2, marker=mk, label=lab); b.text(92, dct[90] + dy, lab, color=INK, fontsize=9, va='center')
b.axhline(0.025, color=INK2, ls=':', lw=1); b.text(28.5, 0.13, 'dotted line = 2.5% one-sided\n(the nominal level)', fontsize=8.5, color=INK2, va='top'); b.set_xlim(27, 135); b.set_ylim(0, 0.55); b.set_xticks(xs)
b.set_xlabel('confirmatory cycles (single analysis)'); b.set_ylabel('false-positive rate'); b.set_title('False positives when features only offset a noisy clock')
fig.tight_layout(); fig.savefig(f'{AU}/power_curves.png', dpi=160); print('ok')
