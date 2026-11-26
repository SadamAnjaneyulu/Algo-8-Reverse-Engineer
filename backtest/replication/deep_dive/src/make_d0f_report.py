"""Builds reports/D0_FULL_AUC.md and figures/bl_d0f_summary.png."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); C = lambda n: pd.read_csv(f'{OUT}/{n}.csv'); R = json.load(open(f'{OUT}/bl_summary_d0f1.json'))
A, S4, PCY, TY, AB = C('bl_d0f_auc'), C('bl_d0f_s4'), C('bl_d0f_cycles'), C('bl_d0f_types'), C('bl_d0f_abl')
CAU = 'causal'; PLUS = [v for v in A.variant.unique() if v != CAU][0]
S, T = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'), pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); PR = C('bl_d0e_str_pairs'); STR = PR[PR.dk == 2]; leg = set(STR.ce_idx) | set(STR.pe_idx)
S['t0'] = T.type.values; S['off'] = T.off_steps.values; S['type3'] = [('strangle pair' if ix in leg else ('far-OTM solo' if (pid < 0 and t0 != 'opening solo' and off >= 3) else t0)) for ix, pid, t0, off in zip(S.index, S.pid, S.t0, S.off)]; LOTS = S.groupby('type3').lots.sum(); TOT = LOTS.sum()
TYPES = ['scheduled pair', 'strangle pair', 'counter-sell solo', 'replacement solo', 'other solo', 'far-OTM solo', 'extreme solo', 'opening solo', 'opening pair', 're-centre pair', 'breakout pair', 'other pair', 'late solo']
def g(var, sch, out, col='auc'):
    d = A[(A.variant == var) & A.scheme.str.startswith(sch) & (A.outcome == out)]; return d[col].iloc[0] if len(d) else np.nan
def s4(var, out, col='mean_auc'):
    d = S4[(S4.variant == var) & (S4.outcome == out)]; return d[col].iloc[0] if len(d) else np.nan
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
ANY = 'any D0 sell'
# ------------- type table
rows = []
for t in TYPES:
    cells = int(g(CAU, 'S1', t, 'cells')); a1, a2, a4 = g(CAU, 'S1', t), g(CAU, 'S2b', t), s4(CAU, t); b1, b2, b4 = g(PLUS, 'S1', t), g(PLUS, 'S2b', t), s4(PLUS, t)
    ok = lambda x: x >= 0.85
    if cells < 150: v = 'indicative (<150 cells)'
    elif ok(a1) and ok(a4) and (a2 != a2 or ok(a2)): v = 'met (causal)'
    elif ok(b1) and ok(b4) and (b2 != b2 or ok(b2)): v = 'met with same-minute information only'
    else: v = 'not met'
    rows.append(dict(type=t, lots_share=LOTS.get(t, 0) / TOT, cells=cells, S1_causal=a1, S2b_causal=a2, S4_mean_causal=a4, S1_plus_minute=b1, S2b_plus_minute=b2, S4_mean_plus_minute=b4, verdict=v))
TT = pd.DataFrame(rows); TT.round(4).to_csv(f'{OUT}/bl_d0f_typetable.csv', index=False)
# ------------- figure
fig, ax = plt.subplots(2, 2, figsize=(17, 11)); a = ax[0, 0]
labs = ['S1 leave-one-\ncycle-out', 'S2b forward,\nwithin version', 'S4 random halves\n(mean of 30)', 'S3b new version\n+3 cycles', 'S3 new version,\nno adaptation']
vc = [g(CAU, 'S1', ANY), g(CAU, 'S2b', ANY), s4(CAU, ANY), g(CAU, 'S3b', ANY), g(CAU, 'S3', ANY)]; vp = [g(PLUS, 'S1', ANY), g(PLUS, 'S2b', ANY), s4(PLUS, ANY), np.nan, np.nan]; x = np.arange(5)
a.bar(x - .2, vc, .4, color='#2b6cb0', label='causal'); a.bar(x + .2, vp, .4, color='#d69e2e', label='+ minute bar and same-minute buy-backs'); a.axhline(.85, color='r', ls='--'); a.set_xticks(x); a.set_xticklabels(labs, fontsize=8); a.set_ylim(.5, 1); a.legend(fontsize=8, loc='lower left'); a.set_ylabel('AUC, any D0 sell'); a.set_title('A. Whole D0 selling on cycles the model never saw', fontsize=10)
a = ax[0, 1]; t = TT.iloc[::-1]; y = np.arange(len(t)); a.barh(y - .2, t.S1_causal, .4, color='#2b6cb0', label='causal (leave-one-cycle-out)'); a.barh(y + .2, t.S1_plus_minute, .4, color='#d69e2e', label='+ same-minute information'); a.axvline(.85, color='r', ls='--'); a.set_yticks(y); a.set_yticklabels([f"{r.type} ({r.lots_share:.0%})" for r in t.itertuples()], fontsize=8); a.set_xlim(.6, 1.0); a.legend(fontsize=8, loc='lower left'); a.set_title('B. Each selling type (share of D0 sell lots)', fontsize=10)
a = ax[1, 0]; p = PCY.sort_values('auc'); a.bar(range(len(p)), p.auc, color=np.where(p.version == 'V1', '#2b6cb0', '#e53e3e')); a.axhline(.85, color='r', ls='--'); a.set_ylim(.5, 1); a.set_xlabel('cycles, sorted (blue: before 16 Sep, red: from 16 Sep)'); a.set_ylabel('AUC of that cycle'); a.set_title(f"C. Cycle by cycle (median {PCY.auc.median():.2f}, {int((PCY.auc >= .85).sum())} of {len(PCY)} cycles at or above 0.85)", fontsize=10)
a = ax[1, 1]; mm = AB.pivot(index='outcome', columns='model', values='auc'); show = [ANY, 'scheduled pair', 'strangle pair', 'counter-sell solo', 'replacement solo', 'extreme solo', 'other solo']; cm = [c for c in mm.columns if c.startswith('market')][0]; cc = [c for c in mm.columns if c.startswith('learned')][0]; x = np.arange(len(show))
a.bar(x - .27, [mm.loc[s, cm] for s in show], .27, color='#2b6cb0', label='market, book, buy-backs'); a.bar(x, [mm.loc[s, cc] for s in show], .27, color='#805ad5', label='learned clock + time'); a.bar(x + .27, [g(CAU, 'S1', s) for s in show], .27, color='#38a169', label='both'); a.axhline(.85, color='r', ls='--'); a.set_xticks(x); a.set_xticklabels([s.replace(' ', '\n', 1) for s in show], fontsize=8); a.set_ylim(.5, 1.02); a.legend(fontsize=8, loc='lower left'); a.set_title('D. What carries each AUC (leave-one-cycle-out)', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0f_summary.png'), dpi=115); plt.close()
# ------------- report
n_ok = int((TT.verdict == 'met (causal)').sum()); n_plus = int((TT.verdict == 'met with same-minute information only').sum()); n_ind = int(TT.verdict.str.startswith('indicative').sum()); n_no = int((TT.verdict == 'not met').sum())
big = TT[TT.verdict == 'met (causal)'].lots_share.sum(); wk = TT[~TT.verdict.isin(['met (causal)'])].type.tolist(); wk_share = TT[~TT.verdict.isin(['met (causal)'])].lots_share.sum()
a1 = A[(A.variant == CAU) & A.scheme.str.startswith('S1') & (A.outcome == ANY)].iloc[0]; pc = R['per_cycle_any']; pl = R['placebo_any']
txt = f"""# Algo 8 — D0 selling, every selling type, on cycles the model has not seen

*Plan `D0_FULL_AUC_PLAN.md` (addendum lists what changed after the first results). In-sample discovery on D0: {R['cycles']} cycles with minutes before their stop, 14,962 minute cells (cycle × minute × right, 09:15 to the minute before the stop or 15:10), {R['lots_in_panel']:,} of the {R['lots_total']:,} D0 sell lots fall in these cells. **Everything below is scored on cycles that were not used to fit that score:** the model and the clock timetables are learned on training cycles only. Figure: `figures/bl_d0f_summary.png`. Scripts `bl_d0f_*.py`.*

## 0. Result
**Whole D0 selling is reproduced at AUC 0.89–0.93 on unseen cycles as long as the timetable version has been seen** (worst of 30 random splits {s4(CAU,ANY,'min_auc'):.3f}, worst single cycle {R['per_cycle_any']['min']:.3f}). Per selling type, {n_ok} of 13 pass the strict causal rule ({', '.join(TT[TT.verdict=='met (causal)'].type)}; {big:.0%} of all D0 sell lots) and {n_plus} more pass once the same-minute information is allowed; {n_ind} small types are indicative only and {n_no} is not met.

| Whole D0 selling ("any sell" in the minute, on the right) | Causal | With the minute's own bar and same-minute buy-backs |
|---|---|---|
| **S1 leave-one-cycle-out** (every cycle predicted by a model that never saw it) | **{g(CAU,'S1',ANY):.3f}** (CI {a1.lo:.3f}–{a1.hi:.3f}), within-cycle {g(CAU,'S1',ANY,'within_cycle_auc'):.3f} | {g(PLUS,'S1',ANY):.3f} |
| **S2b forward in time**, inside each timetable version (first two thirds → last third) | **{g(CAU,'S2b',ANY):.3f}** | {g(PLUS,'S2b',ANY):.3f} |
| **S4 thirty random halves** of the cycles, mean ± sd (worst split) | **{s4(CAU,ANY):.3f} ± {s4(CAU,ANY,'sd'):.3f}** ({s4(CAU,ANY,'min_auc'):.3f}) | {s4(PLUS,ANY):.3f} ± {s4(PLUS,ANY,'sd'):.3f} ({s4(PLUS,ANY,'min_auc'):.3f}) |
| **S3b new timetable version, three new-version cycles added** | **{g(CAU,'S3b',ANY):.3f}** | — |
| **S3 new timetable version, no adaptation** (train before 16 Sep, test from 16 Sep) | **{g(CAU,'S3',ANY):.3f}** | — |
| Placebo (features shuffled within each cycle), S1 | {pl['auc']:.3f} (within {pl['within']:.3f}) | — |

* **Cycle by cycle (S1):** median AUC {pc['median']:.3f}, worst {pc['min']:.3f}, {pc['share_ge_085']:.0%} of the {pc['n']} scored cycles at or above 0.85 (Figure C).
* **The one case that fails is a new timetable.** The system's clocks changed on 16 Sep. A model trained only on the old clocks scores {g(CAU,'S3',ANY):.2f} on the new cycles; after seeing **three** cycles of the new version it is back to {g(CAU,'S3b',ANY):.2f}. This is the real risk for "new data": a changed timetable has to be re-learned, and about three cycles are enough. *Observed.*
* **Type assignment:** among the {R['sale_cells']:,} cells with a sale, the predicted type (the highest one-vs-rest probability) is the true type in **{R['type_top1_accuracy']:.0%}** of cells (always guessing the commonest type: {R['majority_type_share']:.0%}). Scheduled pairs and strangles are recognised in 96–97% of their cells; counter-sell 63%, replacement 55%, other solo 47%; re-centre, breakout, extreme and far-OTM are rarely picked (7–33%). *Observed.*

## 1. Every type
{table(TT[['type','lots_share','cells','S1_causal','S2b_causal','S4_mean_causal','S1_plus_minute','S4_mean_plus_minute','verdict']])}
*S1 leave-one-cycle-out, S2b forward inside each version, S4 mean of 30 random cycle halves. "—" = no test cycle has that type. "Plus minute" adds the minute's own spot and premium bar and the buy-backs of the same minute; for the types whose label is itself a buy-back within 60 s (re-centre, counter, replacement) that is partly definitional.*

* **Passing causally ({n_ok} types, {big:.0%} of lots):** {', '.join(TT[TT.verdict=='met (causal)'].type)}. Replacement solo is at {g(CAU,'S1','replacement solo'):.3f} (S1) and {s4(CAU,'replacement solo'):.3f} (S4) but {g(CAU,'S2b','replacement solo'):.3f} in the forward test, which has only 33 positive cells; under the strict rule that puts it in the next group.
* **Passing only with same-minute information ({n_plus}):** {', '.join(TT[TT.verdict=='met with same-minute information only'].type)}.
* **Indicative only (<150 cells, {n_ind}):** {', '.join(TT[TT.verdict.str.startswith('indicative')].type)}; their AUCs are high where the clock decides them (opening) and noisy otherwise.
* **Not met ({n_no}):** {', '.join(TT[TT.verdict=='not met'].type) or 'none'}.
* **The types that fall short are small and noisy:** {', '.join(wk)} together are {wk_share:.0%} of D0 sell lots. The three small pair types (re-centre, breakout, other pair) have 90–176 cells and swing by ±0.1 between random halves; as one group ("event pairs") they reach {g(CAU,'S1','event pairs (re-centre + breakout + other pair; post-hoc group)'):.3f} (S1), {g(CAU,'S2b','event pairs (re-centre + breakout + other pair; post-hoc group)'):.3f} (S2b), {s4(CAU,'event pairs (re-centre + breakout + other pair; post-hoc group)'):.3f} (S4 mean).

## 2. What carries the AUC
{table(AB.pivot(index='outcome', columns='model', values='auc').reset_index().round(3))}
*(leave-one-cycle-out, causal; all causal features together are in §1.)*
* **Whole selling:** the learned clock + time position alone gives 0.84 and market, book and past buy-backs alone 0.85; together 0.91. They are complementary.
* **Timetable types** (scheduled pair, strangle, opening, late) are carried by the **learned clock** (0.98–1.00 alone).
* **Market-driven types** (counter-sell, replacement, extreme) are carried by **market, book and past buy-backs** (0.89–0.93 alone); the clock alone is at 0.54–0.71.
* **Other solo** is the weakest type either way (0.81 with everything, 0.65 clock only).

## 3. What this does and does not show
* **Observed:** a single causal model with learned timetables ranks the minutes of D0 selling at AUC {g(CAU,'S1',ANY):.2f} on unseen cycles, {g(CAU,'S2b',ANY):.2f} forward in time inside a version and {s4(CAU,ANY):.2f} on average over random halves, and the types that carry {big:.0%} of D0 sell lots are individually at or above 0.85.
* **Not shown:** lots, strikes and seconds. This is a ranking of minutes and a type label for them; the order-level reconstruction is `D0_FREE_RUN.md` (lot F1 about 0.4).
* **Not met:** the four small/noisy types ({wk_share:.0%} of lots) under the strict causal rule; a **new timetable version** without a few cycles to re-learn it.
* **Optimism:** the types (including the strangle), the far-OTM cut and several features were found after looking at all {R['cycles']} cycles. The unseen-cycle numbers protect against fitting a model to a cycle, not against the structure having been chosen with all cycles in view. A real test needs new cycles scored with everything frozen now.

## Caveats
* Cells with a sale are 24% of all cells, so PR-AUC is far lower than AUC; the ranking is strong, a hard threshold would not be precise.
* Per-cycle AUCs use the 24 cycles with at least 5 positives. Three cycles that stop out before 09:16 have no cells.
* The "plus minute" variant is a convention of the D-1 work; it is not knowable ahead.

## Run order
`bl_d0f_panel.py` → `bl_d0f_auc.py` (~6 min, one thread per worker: `OMP_NUM_THREADS=1`) → `bl_d0f_abl.py` (~2 min) → `make_d0f_report.py`.
"""
open(os.path.join(RP, 'D0_FULL_AUC.md'), 'w').write(txt); print(TT.round(3).to_string(index=False)); print(n_ok, n_plus, n_ind, n_no, round(big, 3), round(wk_share, 3))
