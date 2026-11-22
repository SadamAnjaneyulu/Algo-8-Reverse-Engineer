"""Builds reports/D1_FREE_RUN.md and figures/bl_fr_summary.png from bl_fr_*.csv and bl_summary_fr1/fr2.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); CL = pd.read_csv(f'{OUT}/bl_fr_classes.csv'); OV = pd.read_csv(f'{OUT}/bl_fr_overall.csv'); BK = pd.read_csv(f'{OUT}/bl_fr_book.csv'); CA = pd.read_csv(f'{OUT}/bl_fr_carry.csv'); PC = pd.read_csv(f'{OUT}/bl_fr_cycles.csv'); CE = pd.read_csv(f'{OUT}/bl_fr_cell.csv'); PA = pd.read_csv(f'{OUT}/bl_fr_params.csv'); J1 = json.load(open(f'{OUT}/bl_summary_fr1.json'))
pct = lambda x: '–' if x != x else f'{100 * x:.0f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
PRI, LATE, TF = 'FR free-running (primary)', 'FR + late R3 (post-hoc)', 'TF-hedge (hedge on real body)'
P = CL[CL.variant == PRI].set_index('cls'); T = CL[CL.variant == TF].set_index('cls'); ov = OV.set_index('variant'); o = ov.loc[PRI]
names = {'body_sell': 'Body sells', 'body_buyback': 'Body buy-backs', 'wing_buy': 'Wing buys (`h_`)', 'wing_sell': 'Wing sells (`h_`)', 'opening_wings': 'Opening wings (body stream)', 'lump': 'Overnight lump (`v_`)', 'not_modelled': 'Not modelled'}
order = list(names)
# ---------------- figure
fig, ax = plt.subplots(2, 2, figsize=(14, 9)); x = np.arange(6); w = .27; cls6 = order[:6]
for k, (col, nm, cl) in enumerate((('F1', 'timing (±1 min)', '#2b6cb0'), ('F1_within1', 'timing + strike within one', '#38a169'), ('F1_strict', 'timing + exact strike', '#dd6b20'))): ax[0, 0].bar(x + (k - 1) * w, [P.loc[c, col] for c in cls6], w, color=cl, label=nm)
for c_i, c in enumerate(cls6):
    if c in T.index and T.loc[c, 'sim_lots'] > 0: ax[0, 0].scatter(c_i - w, T.loc[c, 'F1'], marker='D', color='k', zorder=5, label='hedge on the real body (timing)' if c == 'wing_buy' else None)
ax[0, 0].set_xticks(x); ax[0, 0].set_xticklabels([names[c].replace(' (', '\n(') for c in cls6], fontsize=7); ax[0, 0].set_ylim(0, 1.25); ax[0, 0].legend(fontsize=7, loc='upper left', ncol=2); ax[0, 0].set_title(f"(a) Free-running reconstruction vs the real D-1 ledger: overall F1 {o.F1:.2f}")
b = BK[(BK.variant == PRI) & (BK.j != 'all hours')].assign(j=lambda d: d.j.astype(int)); tt = lambda q, c: b[b.quantity == q].sort_values('j')[c]
for q, cl in (('short lots S', '#2b6cb0'), ('long lots L', '#dd6b20')):
    ax[0, 1].plot((b[b.quantity == q].sort_values('j').j + 15) / 60 + 9, tt(q, 'mean_real'), color=cl, lw=2, label=f'{q} — real'); ax[0, 1].plot((b[b.quantity == q].sort_values('j').j + 15) / 60 + 9, tt(q, 'mean_sim'), color=cl, ls='--', label=f'{q} — simulated')
ax[0, 1].set_xlabel('hour (D-1)'); ax[0, 1].set_ylabel('lots per right (mean over cycles)'); ax[0, 1].legend(fontsize=8); ax[0, 1].set_title('(b) Book through the day: real vs simulated (mean over cycles)')
q = PC.sort_values('F1'); ax[1, 0].bar(range(len(q)), q.F1, color=np.where(q.und == 'NIFTY', '#2b6cb0', '#dd6b20')); ax[1, 0].axhline(o.F1, ls='--', color='k', lw=.8); ax[1, 0].set_xticks([]); ax[1, 0].set_ylabel('lot-level F1 per cycle'); ax[1, 0].set_title('(c) Per cycle (blue NIFTY, orange SENSEX; dashed: overall)')
for k, c in enumerate(order): ax[1, 1].bar(k - .2, P.loc[c, 'real_lots'], .4, color='#2b6cb0', label='real' if k == 0 else None); ax[1, 1].bar(k + .2, P.loc[c, 'sim_lots'], .4, color='#dd6b20', label='simulated' if k == 0 else None)
ax[1, 1].set_xticks(range(len(order))); ax[1, 1].set_xticklabels([names[c].replace(' (', '\n(').replace('Not modelled', 'Not\nmodelled') for c in order], fontsize=7); ax[1, 1].legend(); ax[1, 1].set_title('(d) Lots by class: real vs simulated'); ax[1, 1].set_ylabel('lots')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_fr_summary.png'), dpi=130)
# ---------------- tables
tab = pd.DataFrame([[names[c], int(P.loc[c, 'real_lots']), int(P.loc[c, 'sim_lots']), pct(P.loc[c, 'precision']), pct(P.loc[c, 'recall']), f"{P.loc[c, 'F1']:.2f}" if c != 'not_modelled' else '0', f"{P.loc[c, 'F1_within1']:.2f}" if c != 'not_modelled' else '0', f"{P.loc[c, 'F1_strict']:.2f}" if c != 'not_modelled' else '0', pct(P.loc[c, 'strike_exact_of_matched'])] for c in order], columns=['class', 'real lots', 'simulated lots', 'precision', 'recall', 'F1 timing', 'F1 + strike within one', 'F1 + exact strike', 'exact strike among matched'])
tab.loc[len(tab)] = ['**All D-1 lots**', int(o.real_lots), int(o.sim_lots), pct(o.precision), pct(o.recall), f'**{o.F1:.2f}**', f'{o.F1_within1:.2f}', f'{o.F1_strict:.2f}', '–']
tf = pd.DataFrame([[names[c], f"{T.loc[c, 'F1']:.2f}", f"{T.loc[c, 'F1_within1']:.2f}", f"{T.loc[c, 'F1_strict']:.2f}", f"{P.loc[c, 'F1']:.2f}"] for c in ('wing_buy', 'wing_sell')], columns=['class', 'F1 timing, hedge on the real body', 'F1 + strike within one', 'F1 + exact strike', 'F1 timing, free-running'])
hb = BK[(BK.j == 'all hours')]; bk = pd.DataFrame([[v.replace('FR free-running (primary)', 'free-running').replace('TF-hedge (hedge on real body)', 'hedge on the real body'), r.quantity, f'{r.mean_real:.1f}', f'{r.MAE_lots:.1f}', f'{r.median_abs_err_pct:.0f}%', f'{r.corr:.2f}'] for v, r in ((r.variant, r) for r in hb.itertuples())], columns=['variant', 'quantity (per right, hours 1–6.5)', 'mean real lots', 'mean abs error (lots)', 'median abs error', 'correlation'])
cr = pd.DataFrame([[v.replace('FR free-running (primary)', 'free-running').replace('TF-hedge (hedge on real body)', 'hedge on the real body'), pct(J1[f'carry_{v}']['short_overlap']), pct(J1[f'carry_{v}']['long_overlap']), f"{J1[f'carry_{v}']['real_S_mean']:.0f} / {J1[f'carry_{v}']['sim_S_mean']:.0f}", f"{J1[f'carry_{v}']['real_L_mean']:.0f} / {J1[f'carry_{v}']['sim_L_mean']:.0f}", f"{J1[f'carry_{v}']['S_corr']:.2f} / {J1[f'carry_{v}']['L_corr']:.2f}"] for v in (PRI, TF)], columns=['variant', 'carried shorts matched (same contract)', 'carried longs matched', 'short lots at the close: real / simulated (both rights)', 'long lots: real / simulated', 'correlation across cycles (S / L)'])
ce = CE.copy(); ce['cls'] = ce.cls.map(lambda c: names.get(c, '**Any activity**')); ce = ce[['cls', 'real_cells', 'sim_cells', 'P_exact', 'R_exact', 'F1_exact', 'F1_pm1']].round(2); ce.columns = ['class', 'real cells', 'simulated cells', 'precision (same minute)', 'recall (same minute)', 'F1 same minute', 'F1 ±1 minute']
worst = PC.sort_values('F1').head(2)
txt = f"""# Algo 8 — complete D-1 reconstruction vs the original, free-running

*Plan `D1_FREE_RUN_PLAN.md`, written before running. In-sample (D-1 of 32 live cycles; parameters fitted on one cycle half and scored on the other). The simulator uses the market data only (spot and option one-minute OHLC); no real order is ever an input in the primary variant. Figure: `figures/bl_fr_summary.png`.*

## 0. How accurate is it?
| Measure | Result |
|---|---|
| **Lot-level, timing (±1 min, same right and class)** | **F1 {o.F1:.2f}** (precision {pct(o.precision)}, recall {pct(o.recall)}). {int(o.matched):,} of {int(o.real_lots):,} real lots matched. |
| …and the strike within one step | F1 {o.F1_within1:.2f} |
| …and the exact strike | F1 {o.F1_strict:.2f} |
| Minute cells with any activity (same minute / ±1) | F1 {CE[CE.cls == 'any'].F1_exact.iloc[0]:.2f} / {CE[CE.cls == 'any'].F1_pm1.iloc[0]:.2f} |
| Per cycle | median F1 {PC.F1.median():.2f}, {pct((PC.F1 >= 0.65).mean())} of cycles at or above 0.65, range {PC.F1.min():.2f}–{PC.F1.max():.2f} |
| Book through the day (short and long lots per right) | correlation {BK[(BK.variant == PRI) & (BK.j == 'all hours') & (BK.quantity == 'short lots S')].iloc[0]['corr']:.2f} / {BK[(BK.variant == PRI) & (BK.j == 'all hours') & (BK.quantity == 'long lots L')].iloc[0]['corr']:.2f}, median error about {BK[(BK.variant == PRI) & (BK.j == 'all hours') & (BK.quantity == 'short lots S')].iloc[0].median_abs_err_pct:.0f}% |
| **Book carried into D0** | {pct(J1[f'carry_{PRI}']['short_overlap'])} of the real carried shorts and {pct(J1[f'carry_{PRI}']['long_overlap'])} of the real carried longs are reproduced as the same contracts |

**Reading:**
* Timing of what the system does is reproduced to about 0.7 F1, and in terms of *which minute and which side* to about 0.89 F1 (±1 minute cells).
* The exact strike is right in {pct(P.loc['lump', 'strike_exact_of_matched'])}–{pct(P.loc['body_sell', 'strike_exact_of_matched'])} of matched lots depending on the class (lump lowest, body sells highest).
* The carried book agrees in total size to {pct(J1[f'carry_{PRI}']['sim_S_mean'] / J1[f'carry_{PRI}']['real_S_mean'])} (shorts) and {pct(J1[f'carry_{PRI}']['sim_L_mean'] / J1[f'carry_{PRI}']['real_L_mean'])} (longs), averaged over cycles, but the same contracts only {pct(J1[f'carry_{PRI}']['short_overlap'])} and {pct(J1[f'carry_{PRI}']['long_overlap'])} of the time.
* These are **free-running** numbers: errors compound (a missed sell changes the wings that follow, and a different buy-back changes the carried book). They are lower than the AUCs (0.96) because AUC scored each minute given the real book and ignored strikes and lot counts.

## 1. By class (free-running)
{table(tab)}

* **Body sells** are the most accurate (0.76), then the **opening wings** (0.97, a fixed form).
* **Wing buys** follow the body sells: F1 0.73 free-running, **{T.loc['wing_buy', 'F1']:.2f} when the real body trades are given**. So the hedge module itself is reproduced at about 0.92–0.95, and its free-running score is mostly the body's error passed on.
* **Buy-backs are the weakest** (0.55). Only a graded stop on the lot's own premium is decoded (θ = 1.5 chosen on both folds), not the neighbouring-lot clusters or the 15–21% of buy-backs with no identified rule. The wing sells inherit this: 0.54.
* **Lump** (0.64): the clock and side are right; size is the unresolved part, so about 40% of its lots do not match.
* **Not modelled** ({int(P.loc['not_modelled', 'real_lots'])} lots, 3% of D-1): the stop module's liquidation (one cycle), the body-stream wing closes and rebuys at 15:15, and one hedge cover. They stay in the recall denominator.

## 2. The hedge module on its own (given the real body orders)
{table(tf)}

## 3. Book
{table(bk)}

{table(cr)}

* **Carried-book overlap** is the share of real carried lots that appear as the same contract on the same side in the simulation. It is lower than the size agreement because strikes differ by one step and the lump sits at a slightly different strike.
* In the hedge-on-real-body variant the carried **short** overlap is 100% by construction (the real body orders are the input).
* The correlation of the end-of-day totals across cycles is weak (0.37 / 0.38) because of two outliers. In cycle 14 (NIFTY, F1 {PC[PC.cid == 14].F1.iloc[0]:.2f}) there is a 240-lot deep-out-of-the-money batch sell (not modelled) and 128 body-stream long lots, and 328 shorts are carried. In cycle 8 (NIFTY, F1 {PC[PC.cid == 8].F1.iloc[0]:.2f}) the real stop module liquidated the book at 14:46 (not modelled). These are the two worst cycles by F1.

## 4. Cell level (cycle × minute × right)
{table(ce)}

## 5. What drives the gap to 100%
| Missing piece | Lots affected | Effect |
|---|---|---|
| Solo sell timing (the open piece of the body) | about a third of body sells | recall of body sells 69% |
| Deep-OTM batch sells (287 lots) and after-15:00 solo sells (336 lots) | about 13% of body sells | the late rule R3 adds recall but costs precision: overall F1 {ov.loc[LATE].F1:.3f} vs {o.F1:.3f} |
| Buy-back rule (graded stop only) | 1,324 lots | F1 0.55; passes to wing sells |
| Lump size | 1,489 lots | F1 0.64 |
| Stop module, 15:15 flatten, hedge cover | 457 lots (3%) | recall ceiling about 97% |
| Exact strike (minute data lag the live price) | all classes | F1 0.45 strict vs 0.69 timing |

## Parameters (out-of-fold)
{table(PA[PA.variant == PRI][['fold', 'tp', 'theta', 'a', 'b', 'lump_ratio', 'lump_t', 'open_off']])}
Fixed from earlier studies, not re-fitted here: solo ladder (0.2 step, 60-minute gate), wing premium target k = 2.5%, lump strike 2.2 σ√T. **The wing strike rule runs here on previous-minute closes. Its exact-strike share among matched wing buys is {pct(P.loc['wing_buy', 'strike_exact_of_matched'])}.** `D1_LONG_SIDE.md` reported 65% using a "calibrated" analysis price that uses the true wing's own price, so the free-running figure is the honest one.

## Evidence labels
Observed: all numbers above (executed). Post-hoc: the late R3 variant. Not testable: exact fills and seconds, margin inputs, event order within a minute. In-sample: the rules were found on the same 32 cycles.
"""
open(f'{RP}/D1_FREE_RUN.md', 'w').write(txt); print('ok')
