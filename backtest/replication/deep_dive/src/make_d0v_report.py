"""Builds reports/D0_SIZING.md and figures/bl_d0v_summary.png from bl_d0v_* outputs. Verdicts are computed from the tables (hypotheses of reports/D0_SIZING_PLAN.md)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures')
def _md(self, index=True, **kw):
    d = self.reset_index() if index else self
    h = '| ' + ' | '.join(str(c) for c in d.columns) + ' |\n|' + '---|' * len(d.columns) + '\n'
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return h + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pd.DataFrame.to_markdown = _md
F1 = pd.read_csv(f'{OUT}/bl_d0v_f1.csv'); CL = pd.read_csv(f'{OUT}/bl_d0v_f1_class.csv'); PN = pd.read_csv(f'{OUT}/bl_d0v_pnl.csv'); BK = pd.read_csv(f'{OUT}/bl_d0v_book.csv'); SC = pd.read_csv(f'{OUT}/bl_d0v_scale.csv'); ST = pd.read_csv(f'{OUT}/bl_d0v_stop.csv'); R = json.load(open(f'{OUT}/bl_summary_d0v.json')); CYC = pd.read_csv(f'{OUT}/bl_d0v_cycles.csv')
pc = lambda x, d=1: f'{100 * x:.{d}f}%'; OOF = 'OOF (cycle halves)'; FA = 'forward A (same version, later cycles)'; FB = 'forward B (train V1, test V2)'
f1 = lambda sp, t, c='F1': float(F1[(F1.split == sp) & (F1.treatment == t)][c].iloc[0]); pn = lambda sp, t, s, c: float(PN[(PN.split == sp) & (PN.treatment == t) & (PN.s == s)][c].iloc[0]); bk = lambda sp, t, s, c: float(BK[(BK.split == sp) & (BK.treatment == t) & (BK.s == s)][c].iloc[0])
sc = lambda t, s, c: float(SC[(SC.treatment == t) & (SC.s == s)][c].iloc[0]); M0, A, B = 'M0 reference', 'A draw', 'B fixed median'
# hypotheses
h1 = {sp: (f1(sp, A, 'dF1_vs_M0'), f1(sp, A, 'dF1_lo'), f1(sp, A, 'dF1_hi')) for sp in (OOF, FA, FB)}; H1 = all(v[1] > 0 for v in h1.values())
h2 = {(t, sp): R[f'pnl_spearman_diff_{t}_{sp}'] for t in (A, B) for sp in (OOF, FA, FB)}; H2 = any(v['lo'] > 0 for v in h2.values())
h3 = {sp: (f1(sp, A, 'dF1_vs_B'), f1(sp, A, 'dF1_vs_B_lo'), f1(sp, A, 'dF1_vs_B_hi')) for sp in (OOF, FA, FB)}; H3_notbetter = all(v[1] <= 0 for v in h3.values())
h4 = {t: sc(t, 0.1, 'median_ratio_to_s_x_P1') for t in (M0, A, B)}; H4 = all(0.8 <= v <= 1.2 for v in h4.values())
nl = R['null_hold_carried_book']; rs = R['real_pnl_spread_lakh']; mean_real = R['real_pnl_lakh_oof']['sum'] / R['real_pnl_lakh_oof']['cycles']; tstat = mean_real / (rs['std'] / np.sqrt(R['real_pnl_lakh_oof']['cycles']))
yn = lambda b: 'holds' if b else 'fails'
# figure
fig, ax = plt.subplots(2, 2, figsize=(14, 9)); col = {M0: '#555555', A: '#2b6cb0', B: '#c05621'}; T3 = [M0, A, B]
x = np.arange(3); w = 0.26
for k, t in enumerate(T3):
    v = [f1(sp, t) for sp in (OOF, FA, FB)]; e = [f1(sp, t, 'F1_rep_sd') for sp in (OOF, FA, FB)]; ax[0, 0].bar(x + (k - 1) * w, v, w, yerr=e, color=col[t], label=t, capsize=3)
ax[0, 0].set_xticks(x); ax[0, 0].set_xticklabels(['OOF halves\n(30 cycles)', 'forward A\n(9)', 'forward B\n(10)']); ax[0, 0].set_ylabel('lot F1 (overall)'); ax[0, 0].set_title('Lot match by sizing treatment (bars: repetition sd)'); ax[0, 0].legend(fontsize=8); ax[0, 0].set_ylim(0.3, 0.55)
cl = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'stop']
for k, t in enumerate(T3):
    z = CL[CL.treatment == t].set_index('cls').loc[cl]; ax[0, 1].bar(np.arange(len(cl)) + (k - 1) * w, z.sim / z.real, w, color=col[t], label=t)
ax[0, 1].axhline(1, color='k', ls=':'); ax[0, 1].set_xticks(np.arange(len(cl))); ax[0, 1].set_xticklabels([c.replace('_', '\n') for c in cl], fontsize=8); ax[0, 1].set_title('Simulated lots ÷ real lots (OOF, s = 1)'); ax[0, 1].legend(fontsize=8)
for t in T3:
    z = PN[(PN.split == OOF) & (PN.treatment == t)].sort_values('s'); ax[1, 0].plot(z.s, z.spearman, 'o-', color=col[t], label=t)
ax[1, 0].axhline(nl['spearman'], color='k', ls='--', label=f'null: carried book held ({nl["spearman"]:.2f})'); ax[1, 0].set_xscale('log'); ax[1, 0].set_xticks([0.1, 0.25, 0.5, 1]); ax[1, 0].set_xticklabels(['0.1', '0.25', '0.5', '1']); ax[1, 0].set_xlabel('scale s (your capital ÷ the real system\'s)'); ax[1, 0].set_ylabel('Spearman, simulated vs s × real cycle P&L'); ax[1, 0].set_title('Does the P&L ranking survive a smaller account?'); ax[1, 0].legend(fontsize=8)
for t in T3:
    z = SC[(SC.treatment == t) & (SC.s < 1)].sort_values('s'); ax[1, 1].plot(z.s, z.noise_per_real_size_lakh, 'o-', color=col[t], label=t)
ax[1, 1].axhline(rs['std'], color='k', ls='--', label=f'real cycle P&L spread, sd ({rs["std"]:.1f} lakh)'); ax[1, 1].set_xscale('log'); ax[1, 1].set_xticks([0.1, 0.25, 0.5]); ax[1, 1].set_xticklabels(['0.1', '0.25', '0.5']); ax[1, 1].set_xlabel('scale s'); ax[1, 1].set_ylabel('lot-rounding noise per cycle, in real-size ₹ lakh'); ax[1, 1].set_title('Noise added by small lots vs the P&L being measured'); ax[1, 1].minorticks_off(); ax[1, 0].minorticks_off(); ax[1, 1].legend(fontsize=8)
plt.tight_layout(); plt.savefig(os.path.join(FIG, 'bl_d0v_summary.png'), dpi=120); plt.close()
L = []; w_ = L.append
w_('# Algo 8 — D0 sizing in the free-run simulator: A (drawn), B (fixed median), C (scaled)\n')
w_('*Plan `D0_SIZING_PLAN.md` (pre-registered; the addendum lists the post-hoc changes, including a scale bug I fixed after the first run). In-sample discovery on D0 of 30 cycles; every fitted part is refit on each split\'s training cycles, as in `D0_FREE_RUN`. Figure: `figures/bl_d0v_summary.png`. Scripts `bl_d0v_sizing.py` → `bl_d0v_analysis.py` → `make_d0v_report.py`.*\n')
w_('## 0. Result\n')
w_(f'**None of the three sizing treatments reconstructs D0 better than the simulator as it was (M0).** Timing and triggers are identical in all of them; only lot counts change.\n')
w_('| | M0 reference | A draw | B fixed median |\n|---|---|---|---|')
w_(f'| overall lot F1, OOF halves (30 cycles) | **{f1(OOF,M0):.3f}** | {f1(OOF,A):.3f} (CI of change {h1[OOF][1]:+.3f} to {h1[OOF][2]:+.3f}) | {f1(OOF,B):.3f} (CI {f1(OOF,B,"dF1_lo"):+.3f} to {f1(OOF,B,"dF1_hi"):+.3f}) |')
w_(f'| forward A (9) / forward B (10) | {f1(FA,M0):.3f} / {f1(FB,M0):.3f} | {f1(FA,A):.3f} / {f1(FB,A):.3f} | {f1(FA,B):.3f} / {f1(FB,B):.3f} |')
w_(f'| simulated ÷ real lots, body sells / buy-backs (OOF) | {CL[(CL.treatment==M0)&(CL.cls=="body_sell")].eval("sim/real").iloc[0]:.2f} / {CL[(CL.treatment==M0)&(CL.cls=="body_buyback")].eval("sim/real").iloc[0]:.2f} | {CL[(CL.treatment==A)&(CL.cls=="body_sell")].eval("sim/real").iloc[0]:.2f} / {CL[(CL.treatment==A)&(CL.cls=="body_buyback")].eval("sim/real").iloc[0]:.2f} | {CL[(CL.treatment==B)&(CL.cls=="body_sell")].eval("sim/real").iloc[0]:.2f} / {CL[(CL.treatment==B)&(CL.cls=="body_buyback")].eval("sim/real").iloc[0]:.2f} |')
w_(f'| peak shorts per right, simulated ÷ real (median cycle) | {bk(OOF,M0,0.5,"peak_ratio_median")/bk(OOF,M0,0.5,"peak_ratio_median")*pd.Series(BK[(BK.split==OOF)&(BK.treatment==M0)&(BK.s==1)].sim_peak_median).iloc[0]/pd.Series(BK[(BK.split==OOF)&(BK.treatment==M0)&(BK.s==1)].real_peak_x_s_median).iloc[0]:.2f} | {BK[(BK.split==OOF)&(BK.treatment==A)&(BK.s==1)].eval("sim_peak_median/real_peak_x_s_median").iloc[0]:.2f} | {BK[(BK.split==OOF)&(BK.treatment==B)&(BK.s==1)].eval("sim_peak_median/real_peak_x_s_median").iloc[0]:.2f} |')
w_(f'| cycle P&L, Spearman vs real (OOF, s = 1; null {nl["spearman"]:.2f}) | {pn(OOF,M0,1,"spearman"):.2f} | {pn(OOF,A,1,"spearman"):.2f} | {pn(OOF,B,1,"spearman"):.2f} |')
w_(f'| cycle P&L, sum simulated ÷ real (OOF) | {pn(OOF,M0,1,"sum_ratio"):.2f} | {pn(OOF,A,1,"sum_ratio"):.2f} | {pn(OOF,B,1,"sum_ratio"):.2f} |')
w_(f'| stops found (real 11): both / real only / sim only (OOF) | ' + ' | '.join(f'{int(ST[(ST.split==OOF)&(ST.treatment==t)&(ST.s==1)].both.iloc[0])} / {int(ST[(ST.split==OOF)&(ST.treatment==t)&(ST.s==1)].real_only.iloc[0])} / {int(ST[(ST.split==OOF)&(ST.treatment==t)&(ST.s==1)].sim_only.iloc[0])}' for t in T3) + ' |\n')
w_('**Verdicts on the pre-registered hypotheses**\n')
w_(f'| hypothesis | verdict | evidence |\n|---|---|---|')
w_(f'| H1 A raises overall lot F1 over M0 | **{yn(H1)}** | change in F1: OOF {h1[OOF][0]:+.3f} (CI {h1[OOF][1]:+.3f}, {h1[OOF][2]:+.3f}), forward A {h1[FA][0]:+.3f}, forward B {h1[FB][0]:+.3f}; A is lower on all three |')
w_(f'| H2 A or B raises P&L fidelity (Spearman) over M0 | **{yn(H2)}** | all six CIs include 0 (e.g. OOF A {h2[(A,OOF)]["diff"]:+.3f} [{h2[(A,OOF)]["lo"]:+.2f}, {h2[(A,OOF)]["hi"]:+.2f}], B {h2[(B,OOF)]["diff"]:+.3f} [{h2[(B,OOF)]["lo"]:+.2f}, {h2[(B,OOF)]["hi"]:+.2f}]) |')
w_(f'| H3 A is not better than B | **{yn(H3_notbetter)}** | A − B in F1: OOF {h3[OOF][0]:+.3f} [{h3[OOF][1]:+.3f}, {h3[OOF][2]:+.3f}], forward A {h3[FA][0]:+.3f} [{h3[FA][1]:+.3f}, {h3[FA][2]:+.3f}], forward B {h3[FB][0]:+.3f} [{h3[FB][1]:+.3f}, {h3[FB][2]:+.3f}]; drawing the count adds noise, not information |')
w_(f'| H4 P&L scales with s (median P&L(s) ÷ (s × P&L(1)) within 0.8–1.2 at s = 0.1) | **{yn(H4)}** | M0 {h4[M0]:.2f}, A {h4[A]:.2f}, B {h4[B]:.2f}. Lots and peak scale linearly (below); the P&L of a 0.1 account is dominated by rounding noise |\n')
w_('## 1. What each treatment does to the book (OOF, s = 1)\n'); w_(CL.round(3).to_markdown(index=False) + '\n')
w_(f'* **B undersizes**: with 1 lot per solo event and 2 per buy-back it trades about {pc(CL[(CL.treatment==B)&(CL.cls=="body_sell")].eval("sim/real").iloc[0],0)} of the real sell lots and holds a peak of about {pc(BK[(BK.split==OOF)&(BK.treatment==B)&(BK.s==1)].eval("sim_peak_median/real_peak_x_s_median").iloc[0],0)} of the real book. Its precision is higher (fewer wrong lots) and its recall lower; the hedge follows the smaller book.')
w_(f'* **A calibrates the totals** (sell lots {CL[(CL.treatment==A)&(CL.cls=="body_sell")].eval("sim/real").iloc[0]:.2f}×, buy-back lots {CL[(CL.treatment==A)&(CL.cls=="body_buyback")].eval("sim/real").iloc[0]:.2f}× the real) but puts the lots in the wrong cells more often than M0, so F1 falls. Repetition spread of F1 is {f1(OOF,A,"F1_rep_sd"):.3f} (OOF) to {f1(FB,A,"F1_rep_sd"):.3f} (forward B).')
w_(f'* **M0** over-sells slightly (1.06×) and over-buys-back (1.09×): every lot that crosses the stop level is bought back, where the real system takes fewer (`D0_QTY.md` B3).\n')
w_('## 2. Lot F1 by treatment and split\n'); w_(F1[['split', 'treatment', 'reps', 'F1', 'F1_rep_sd', 'sim_lots', 'real_lots', 'F1_body_sell', 'F1_body_buyback', 'F1_wing_buy', 'F1_wing_sell', 'F1_stop', 'dF1_vs_M0', 'dF1_lo', 'dF1_hi']].round(3).to_markdown(index=False) + '\n')
w_('*Oldest-first lot selection (the plan\'s sensitivity) changes F1 by +0.012 (A, OOF), +0.009 (B, OOF) and by more in the 9–10-cycle forward splits (B, forward B: +0.087). The choice of which lots a buy-back takes matters and is not recovered.*\n')
w_('## 3. Cycle profit and loss (before costs)\n'); w_(PN[PN.s == 1][['split', 'treatment', 'cycles', 'spearman', 'median_err_lakh', 'sum_ratio', 'same_sign', 'sim_sum_lakh', 'real_sum_lakh', 'sim_median_lakh', 'real_median_lakh']].round(3).to_markdown(index=False) + '\n')
w_(f'* **Null comparator (post-hoc):** holding the carried book to 15:14 and trading nothing gives Spearman **{nl["spearman"]:.2f}** with the real P&L and sums to {nl["sum_lakh"]:.1f} lakh against the real {nl["real_sum_lakh"]:.1f}. The simulator\'s 0.81–0.84 is therefore real information beyond the market and the carried book, but about half of the ranking is not.')
w_(f'* **The real P&L is small against its own noise.** Over the 30 cycles: sum ₹{R["real_pnl_lakh_oof"]["sum"]:.1f} lakh, mean ₹{mean_real:.2f} lakh per cycle, spread (sd) ₹{rs["std"]:.1f} lakh, t ≈ {tstat:.1f}; median cycle ₹{R["real_pnl_lakh_oof"]["median"]:.2f} lakh. **Before brokerage, taxes and the fill position inside the bar** (sells fill in the lower part of the bar, buys in the upper). Against ~₹20 crore of notional per right this is a thin edge, not a measured one.')
w_(f'* **A sum ratio near 1 is not accuracy.** The sums are small differences of large flows, so M0\'s 1.02 in OOF is within the noise of the per-cycle spread; forward A (sums 2.1 vs 4.1 lakh) and forward B (8.4 vs 0.4 lakh) show the level error. Spearman and the per-cycle median error are the fair readings.')
w_('* Simulated P&L uses the simulator\'s own prices (previous-minute close for sells, minute prices otherwise), which are better than the real fills by construction.\n')
w_('## 4. C: scale s (OOF cycles, lot-identity thinning)\n'); w_(SC.round(3).to_markdown(index=False) + '\n'); w_(PN[(PN.split == OOF)][['treatment', 's', 'spearman', 'median_err_lakh', 'sum_ratio', 'same_sign']].round(3).to_markdown(index=False) + '\n')
w_(BK[BK.split == OOF][['treatment', 's', 'peak_ratio_median', 'peak_spearman', 'lots_ratio_body_sell', 'lots_ratio_body_buyback', 'lots_ratio_wing_buy', 'lots_ratio_wing_sell', 'lots_ratio_stop']].round(3).to_markdown(index=False) + '\n')
w_(f'* **Linear in lots, noisy in P&L.** Lots per class and the peak book stay within about 0.9–1.1 of s × real for M0 at every s. P&L ranking falls from {pn(OOF,M0,1,"spearman"):.2f} (s = 1) to {pn(OOF,M0,0.25,"spearman"):.2f} (0.25) and {pn(OOF,M0,0.1,"spearman"):.2f} (0.1) for M0, and to {pn(OOF,A,0.1,"spearman"):.2f} / {pn(OOF,B,0.1,"spearman"):.2f} for A / B, against the null {nl["spearman"]:.2f}.')
w_(f'* **Lot-rounding noise per cycle, in real-size ₹ lakh:** M0 {sc(M0,0.5,"noise_per_real_size_lakh"):.1f} (s = 0.5) → {sc(M0,0.25,"noise_per_real_size_lakh"):.1f} (0.25) → {sc(M0,0.1,"noise_per_real_size_lakh"):.1f} (0.1), against a real cycle P&L spread of {rs["std"]:.1f}. At s = 0.1 an account\'s result for one cycle is nearly as much rounding as strategy. The ranking stays above the null at every s ({pn(OOF,M0,0.1,"spearman"):.2f}–{pn(OOF,M0,0.5,"spearman"):.2f} for M0), but with 30 cycles the margin over the null at s = 0.1 is inside the noise of a Spearman.')
w_('* The stop level was scaled with s (the stop stays the same share of the book); stops found at s = 0.1: ' + ', '.join(f'{t} {int(ST[(ST.split==OOF)&(ST.treatment==t)&(ST.s==0.1)].both.iloc[0])}/11' for t in T3) + ' (s = 1: ' + ', '.join(f'{int(ST[(ST.split==OOF)&(ST.treatment==t)&(ST.s==1)].both.iloc[0])}/11' for t in T3) + ').\n')
w_('## 5. What to use for the backtest\n')
w_('| use | choice | why |\n|---|---|---|')
w_(f'| **point backtest** | **M0 at the real scale**, i.e. the simulator\'s own rules | highest lot F1 (OOF {f1(OOF,M0):.3f}, forward {f1(FA,M0):.3f} / {f1(FB,M0):.3f}); no treatment beat it; lot totals within 1.06× / 1.09× |')
w_(f'| **sizing-uncertainty band** | **A**, 10+ draws per cycle | right total lots ({CL[(CL.treatment==A)&(CL.cls=="body_sell")].eval("sim/real").iloc[0]:.2f}× / {CL[(CL.treatment==A)&(CL.cls=="body_buyback")].eval("sim/real").iloc[0]:.2f}×); between-draw P&L sd ≈ {sc(A,1,"between_rep_sd_lakh"):.2f} lakh per cycle shows how much unknown sizing moves a cycle |')
w_(f'| **low-size bound** | **B** | about {pc(CL[(CL.treatment==B)&(CL.cls=="body_sell")].eval("sim/real").iloc[0],0)} of real sell lots; useful only as "what if it trades less", not as a reconstruction |')
w_(f'| **your capital** | s from your capital; **s ≥ 0.25 is usable, s = 0.1 is within noise of the null** | P&L ranking {pn(OOF,M0,0.25,"spearman"):.2f} / {pn(OOF,A,0.25,"spearman"):.2f} / {pn(OOF,B,0.25,"spearman"):.2f} at s = 0.25 and {pn(OOF,M0,0.1,"spearman"):.2f} / {pn(OOF,A,0.1,"spearman"):.2f} / {pn(OOF,B,0.1,"spearman"):.2f} at 0.1 (M0 / A / B) against a null of {nl["spearman"]:.2f}; with 30 cycles a Spearman has a standard error of about 0.15–0.18, so 0.1 cannot be told from the null. The real system\'s ~₹20 crore per right makes s = 0.1 about ₹2 crore per right |')
w_('\nA better lot match would need the tick path (what sets the count inside a minute); until then M0 is the simulator to use, and A is the honest error bar on it.\n')
w_('## 6. Adversarial read\n')
w_('* **These are sizing assumptions inside a simulator.** A result better than M0 would not have shown that the real system sizes that way; the result being worse is a weaker statement than it sounds, because M0\'s timing is shared by all three and a wrong count in a right minute is penalised the same as a wrong minute.')
w_('* **Which lots a buy-back takes is my assumption** (most-adverse first); oldest-first moves F1 by up to +0.09 in a 10-cycle split. Not recovered from the data.')
w_('* **Forward splits are 9 and 10 cycles.** Their P&L and F1 differences have wide CIs; only the OOF (30 cycles) comparisons carry weight, and even there H2 is not rejected in either direction.')
w_('* **The P&L is cash before costs on 30 cycles with a sd about four times its mean.** It cannot say whether the real system makes money, only whether the simulator tracks the sign and rank of what it did.')
w_('* **Everything is in-sample discovery on these 32 cycles.** None of it has been run on cycles outside them, and no result here is a statement about a 3-year history.')
w_('* **Not testable:** the real system\'s capital or margin, fills inside the bar, costs, the tick path.\n')
w_('## Addendum (post-hoc, also in `D0_SIZING_PLAN.md`)\n* First scale run discarded: counts were scaled twice (about s²). Replaced by lot-identity thinning; integrity check (M0, s = 1 identical to the stored free-run, 49/49 cycles, lots by class/right/minute/strike) passes with both versions of the code.\n* Null comparator and real-P&L context added after seeing a Spearman of 0.81.\n')
open(f'{RP}/D0_SIZING.md', 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
