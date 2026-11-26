"""Builds reports/D0_SELLS.md and figures/bl_d0s_summary.png from the chunk-1 outputs (bl_d0s_*.csv, bl_summary_d0s0..4.json)."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda k: json.load(open(f'{OUT}/bl_summary_{k}.json'))
R0, R1, R2, R3, R4 = J('d0s0'), J('d0s1'), J('d0s2'), J('d0s3'), J('d0s4')
T1 = pd.read_csv(f'{OUT}/bl_d0s_tests.csv'); TT = pd.read_csv(f'{OUT}/bl_d0s_tt.csv'); SO = pd.read_csv(f'{OUT}/bl_d0s_solo.csv'); SO['chosen'] = SO.chosen.str.replace(' | ', ' / ', regex=False); AU = pd.read_csv(f'{OUT}/bl_d0s_auc.csv'); AT = pd.read_csv(f'{OUT}/bl_d0s_auc_type.csv'); CC = pd.read_csv(f'{OUT}/bl_d0s_auc_cc.csv')
W = pd.read_csv(f'{OUT}/bl_d0s_waves.csv'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz')
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
v = lambda df, col, key, name='test': float(df[df[name].str.startswith(key)][col].iloc[0])
lab = R0['by_label']; tot = R0['lots']; tt_all = TT.iloc[0]; tt_g = TT.iloc[1]; t2b = TT[TT.test.str.startswith('T2b breakout')].iloc[0]
m1 = SO[SO.machine == 'M1 spot ladder'].iloc[0]; m4 = SO[SO.machine.str.startswith('M4')].iloc[0]; m3 = SO[SO.machine.str.startswith('M3 counter')].iloc[0]; d1l = SO[SO.machine.str.startswith('D-1 ladder')].iloc[0]
pm1 = SO[SO.machine.str.startswith('placebo M1 (0.05')].iloc[0]; pm3 = SO[SO.machine.str.startswith('placebo M3')]; m3ref = SO[SO.machine.str.startswith('M3 r 0.5 real')].iloc[0]
A = AU.set_index('variant'); a = lambda k: A[A.index.str.startswith(k)].iloc[0]; bc = R3['burst_coupling']
wg = W.groupby(['und', 'version']).agg(waves=('t', 'size'), lots_per_right=('lots', 'sum')).reset_index(); wg['cycles'] = [R2['cycles_per_group'].get(str((u, vv)), R2['cycles_per_group'].get(f"('{u}', '{vv}')", '')) for u, vv in zip(wg.und, wg.version)]
# ---------------- figure
fig, ax = plt.subplots(2, 2, figsize=(15, 10))
P0 = S[S.pid >= 0].drop_duplicates(['cid', 'pid']); SL = [33360 + 900 * k for k in range(24)]; cids = sorted(S.cid.unique()); M_ = np.full((len(cids), 24), np.nan)
for r, i in enumerate(cids):
    for k, st in enumerate(SL):
        g = P0[(P0.cid == i) & (P0.t0 >= st) & (P0.t0 < st + 180)]
        if len(g): M_[r, k] = g.t0.min() - st
im = ax[0, 0].imshow(M_, aspect='auto', cmap='viridis', vmin=0, vmax=70); ax[0, 0].set_xticks(range(0, 24, 2)); ax[0, 0].set_xticklabels([f'{s // 3600:02d}:{s // 60 % 60:02d}' for s in SL[::2]], rotation=45, fontsize=8)
from bl_common import pd as _pd
CY = _pd.read_csv(f'{OUT}/bl_size_cycles.csv'); ax[0, 0].set_yticks(range(len(cids))); ax[0, 0].set_yticklabels([f'{CY.iloc[i].und[:2]} {CY.iloc[i].version} {CY.iloc[i].expiry[5:]}' for i in cids], fontsize=6)
ax[0, 0].set_title('First pair in each 15-min slot: seconds after the slot start\n(blank = no pair; rows grouped by underlying and version)', fontsize=10); plt.colorbar(im, ax=ax[0, 0], fraction=.03)
b1 = [('slot rule (1 pair per slot)', v(T1, 'value', 'T1 rule S0 (1')), ('timetable per\nunderlying x version', tt_all.F1), ('breakout on\nunexplained pairs', t2b.F1), ('placebo:\npermuted spot', v(TT, 'F1', 'T2b placebo: cycle')), ('placebo:\n+15 min', v(TT, 'F1', 'T2b placebo: fires'))]
ax[0, 1].bar(range(len(b1)), [x[1] for x in b1], color=['#a0aec0', '#2b6cb0', '#2b6cb0', '#cbd5e0', '#cbd5e0']); ax[0, 1].set_xticks(range(len(b1))); ax[0, 1].set_xticklabels([x[0] for x in b1], fontsize=8)
for k, x in enumerate(b1): ax[0, 1].text(k, x[1] + .015, f'{x[1]:.2f}', ha='center')
ax[0, 1].set_ylim(0, 1); ax[0, 1].set_title('Pair sells: out-of-fold lot F1 (minute ±1)', fontsize=10)
b2 = [('D-1 ladder\nunchanged', d1l.F1), ('M1 spot ladder\n(D0 fit)', m1.F1), ('M3 counter-sell\non buy-backs', m3.F1), ('M4 union', m4.F1), ('placebo M1\npermuted spot', pm1.F1), ('placebo M3\nshifted ±10 min', pm3.F1.mean())]
ax[1, 0].bar(range(len(b2)), [x[1] for x in b2], color=['#a0aec0', '#2b6cb0', '#2b6cb0', '#2b6cb0', '#cbd5e0', '#cbd5e0']); ax[1, 0].set_xticks(range(len(b2))); ax[1, 0].set_xticklabels([x[0] for x in b2], fontsize=8)
for k, x in enumerate(b2): ax[1, 0].text(k, x[1] + .01, f'{x[1]:.2f}', ha='center')
ax[1, 0].set_ylim(0, .6); ax[1, 0].set_title('Solo sells: out-of-fold lot F1 (minute ±1)', fontsize=10)
vv = ['timetable + clock only', 'B causal (market lagged 1 min)', 'A same-minute market + rules', 'C A + real buy-back history (earlier minutes) + book', 'C0 C + same-minute buy-backs (teacher-forced)']; lb = ['timetable\n+ clock', 'B causal', 'A same-minute', 'C + buy-back\nhistory', 'C0 + same-min\nbuy-backs']
xx = np.arange(len(vv)); ax[1, 1].bar(xx - .2, [A.loc[k, 'AUC'] for k in vv], .4, label='all sells', color='#2b6cb0'); ax[1, 1].bar(xx + .2, [float(AT[AT.sell_label == 'solo'][k].iloc[0]) for k in vv], .4, label='solo sells', color='#90cdf4')
for k, kk in enumerate(vv): ax[1, 1].text(k - .2, A.loc[kk, 'AUC'] + .005, f'{A.loc[kk, "AUC"]:.3f}', ha='center', fontsize=8)
ax[1, 1].set_xticks(xx); ax[1, 1].set_xticklabels(lb, fontsize=8); ax[1, 1].set_ylim(.7, 1); ax[1, 1].legend(fontsize=8); ax[1, 1].set_title('D0 selling AUC (leave-one-cycle-out)', fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0s_summary.png'), dpi=130)
# ---------------- report
dec = pd.DataFrame([
    ('D0 pair timetable per underlying x version (fixed seconds)', f"OOF lot F1 {tt_all.F1:.3f} (precision {tt_all.precision:.0%}, recall {tt_all.recall:.0%}); strike exact {R2['t1b_strike_exact']:.0%}", 'pooled slot rule 0.446', 'kept', 'Observed'),
    ('D-1 breakout machine on pairs the timetable leaves', f"F1 {t2b.F1:.3f} (CI {t2b.ci_lo:.2f}–{t2b.ci_hi:.2f})", f"placebos {v(TT, 'F1', 'T2b placebo: cycle'):.3f} / {v(TT, 'F1', 'T2b placebo: fires'):.3f}", 'kept (weak recall)', 'Observed'),
    ('D-1 solo ladder unchanged', f"F1 {d1l.F1:.3f} (precision {d1l.precision:.0%}, recall {d1l.recall:.0%})", f"placebo {v(T1, 'value', 'T3b placebo'):.3f}", 'carries over, but covers 9% of D0 solo lots', 'Observed'),
    ('M1 spot ladder refit for D0 (0.05 step, fresh 60-min extreme, lots = steps crossed)', f"F1 {m1.F1:.3f} (CI {m1.ci_lo:.2f}–{m1.ci_hi:.2f})", f"placebo {pm1.F1:.3f}", 'kept', 'Observed'),
    ('M2 premium ladder', f"F1 {SO[SO.machine.str.startswith('M2')].F1.iloc[0]:.3f}", 'below M1', 'rejected (M1 better)', 'Observed'),
    ('M3 counter-sell r × real other-right buy-back lots', f"F1 {m3.F1:.3f}; all-cycle r 0.5 {m3ref.F1:.3f}", f"shifted buy-backs {pm3.F1.min():.3f}–{pm3.F1.max():.3f}", 'kept as coupling (teacher-forced)', 'Observed'),
    ('M4 union ladder + counter-sell', f"F1 {m4.F1:.3f}", f"M1 alone {m1.F1:.3f}", 'kept (+0.02)', 'Observed'),
    ('Solo direction after a favourable 5-min move', f"{v(T1, 'value', 'T3a solo lots after a favourable 5'):.0%}", f"null {v(T1, 'null', 'T3a solo lots after a favourable 5'):.0%}", 'descriptive only (< 1.5× null)', 'Observed'),
    ('Replacement: same-right buy-back ≤ 60 s before', f"{v(T1, 'value', 'T3c'):.0%} of solo lots", f"null {v(T1, 'null', 'T3c'):.0%}", 'kept (1.5×, CI clears null)', 'Observed'),
    ('Counter-sell: other-right buy-back within ±60 s', f"{v(T1, 'value', 'T3d'):.0%} of solo lots", f"null {v(T1, 'null', 'T3d'):.0%}", 'kept', 'Observed'),
], columns=['rule', 'result', 'null / comparison', 'decision', 'evidence'])
txt = f"""# Algo 8 — D0 chunk 1: body sells

*Plan `D0_SELLS_PLAN.md` (written before the tests; addenda 1b and 1c were written after T1 and T3 and before their own tests). In-sample: D0 of the {R1['cycles']} cycles with both D-1 and D0 logs ({R1['cycles_with_sells']} have D0 sells). Out-of-fold = cycle halves by parity. Figure: `figures/bl_d0s_summary.png`.*

## 0. Result
* **D0 selling ranks at AUC {a('A same').AUC:.3f}** (CI {a('A same').ci_lo:.3f}–{a('A same').ci_hi:.3f}) from market data and the decoded rules, with leave-one-cycle-out fits.
  * With completed bars only (causal) the AUC is **{a('B causal').AUC:.3f}**.
  * Adding the real buy-back history from earlier minutes gives **{a('C A').AUC:.3f}**. *Observed.*
* **D0 has a fixed pair timetable, like D-1, but per underlying and version.**
  * Pair start seconds repeat across cycles to within 1–2 s: {', '.join(f'{u} {vv} {n} waves' for u, vv, n in zip(wg.und, wg.version, wg.waves))}.
  * Learned on one half and scored on the other, it gives pair-lot **F1 {tt_all.F1:.3f}** (precision {tt_all.precision:.0%}, recall {tt_all.recall:.0%}), with the strike nearest the previous close {R2['t1b_strike_exact']:.0%} exact. *Observed.*
  * **This corrects `D0_INVENTORY.md`.** Its "no D0 timetable" came from pooling NIFTY and SENSEX.
* **All body selling stops at the first stop-module order** (11 cycles). In 4 of them the stop fires before 09:16. Here the stop time is taken from the real orders; chunk 4 decodes it.
* **Solo sells (70% of D0 sale lots) are the weak part, as on D-1.**
  * The D-1 ladder carries over and is precise ({d1l.precision:.0%}) but finds only {d1l.recall:.0%} of the lots.
  * Refit for D0 (finer 0.05-step ladder, lots = steps crossed, fresh 60-minute extreme), it reaches **F1 {m1.F1:.3f}**, against a placebo of {pm1.F1:.3f}.
  * Adding a counter-sell on the real other-right buy-backs gives {m4.F1:.3f}.
* **Solo sells are tied to buy-backs on the other right.**
  * {v(T1, 'value', 'T3d'):.0%} of solo lots are sold within ±60 s of one, against a {v(T1, 'null', 'T3d'):.0%} null.
  * The tie is partly a common cause, the same spot move. Inside each spot-move quintile the buy-back still ranks solo minutes at AUC {CC.AUC_bb_other_now.min():.2f}–{CC.AUC_bb_other_now.max():.2f}.
  * There is no fixed lot ratio (median {bc['lots_ratio_q'][2]:.2f}, IQR {bc['lots_ratio_q'][1]:.2f}–{bc['lots_ratio_q'][3]:.2f}).

## 1. What D0 selling is made of
| label | definition | lots | share |
|---|---|---|---|
| grid pair | CE + PE at the same strike within 3 s, starting in minute-of-hour 1–3 / 16–18 / 31–33 / 46–48 | {lab['grid_pair']:,} | {R0['share']['grid_pair']:.1%} |
| off-grid pair | the same pairing, any other minute | {lab['offgrid_pair']:,} | {R0['share']['offgrid_pair']:.1%} |
| solo | unpaired sale | {lab['solo']:,} | {R0['share']['solo']:.1%} |

These are {tot:,} lots in the {R1['cycles']} decodable cycles. The inventory's 10,190 also counts 3 cycles with no D-1 log, which are left out here.

## 2. The pair timetable
**The pooled slot view (T1)** shows the windows exist but mixes groups:
* grid windows hold {R1['t1_window_pairlots_shift0']:,} pair lots, against {R1['t1_window_pairlots_shift5']} / {R1['t1_window_pairlots_shift10']} in windows shifted by 5 / 10 minutes;
* a pooled rule of one pair per slot scores only {v(T1, 'value', 'T1 rule S0 (1'):.3f}.

**Per underlying and version (T1b),** learned out-of-fold:

{table(TT[TT.test.str.startswith('T1b')][['test', 'F1', 'ci_lo', 'ci_hi', 'precision', 'recall', 'real_lots', 'sim_lots']])}

Waves found on all cycles (descriptive):

{table(wg[['und', 'version', 'cycles', 'waves', 'lots_per_right']], 0)}

* The NIFTY timetables have several pairs per slot. SENSEX V1 has one pair per slot, about 60 s after the slot start, and sells in fewer slots.
* {R2['t1b_pairs_explained_share']:.0%} of real pairs fall within 3 s of a wave of their own group (out-of-fold).

## 3. Pairs the timetable does not explain ({R2['t2b_residual_pairs']})
* **{R2['t2b_residual_before_1000']} are in the 09:xx hour,** {R2['t2b_residual_0915_0918']} of them between 09:15 and 09:18: an opening burst whose size varies by cycle.
* **{R2['t2b_residual_with_bb_60s_before']:.0%} follow a body buy-back within 60 s,** against {R2['t1b_explained_with_bb_60s_before']:.0%} for timetable pairs. They look like re-centring pairs after a stop (*Inferred*).
* **The D-1 breakout machine, run unchanged, explains part of the rest (10:30–15:15):**

{table(TT[TT.test.str.startswith('T2b')][['test', 'F1', 'ci_lo', 'ci_hi', 'precision', 'recall', 'real_lots', 'sim_lots']])}

## 4. Solo sells
**Descriptive tests (T3)**

{table(T1[T1.test.str.startswith('T3')][['test', 'value', 'ci_lo', 'ci_hi', 'null', 'n']])}

* **Bursts.** {R1['t3e_bursts']:,} bursts (gap ≤ 30 s). The median burst is 1 lot, the 90th percentile {R1['t3e_lots_per_burst_q'][2]:.0f}. Bursts of 5+ lots carry {R1['t3e_share_lots_in_bursts_ge5']:.0%} of solo lots, and {R1['t3e_spot_move_favourable_bursts_ge5']:.0%} of them come with a favourable spot move.
* **Coupling with other-right buy-backs (±90 s).**
  * {bc['lots_share']:.0%} of solo lots are in such bursts.
  * The buy-back comes {bc['dt_q'][1]:.0f} s to {bc['dt_q'][3]:.0f} s around the burst start (IQR).
  * Sold lots / bought lots: median {bc['lots_ratio_q'][2]:.2f}. There is no fixed ratio.

**Machines, fitted on one half and scored on the other (addendum 1c)**

{table(SO[['machine', 'F1', 'ci_lo', 'ci_hi', 'precision', 'recall', 'sim_lots', 'real_lots', 'chosen']])}

* The finer ladder is the best single rule. The grid boundary (0.05 step) does not bind: the extended grid gives the same F1.
* Counter-sell is a real coupling (2× its shifted placebo), but adds little on top of the ladder.

**Common-cause check (T5).** The same-minute other-right buy-back as a score for solo minutes, inside quintiles of the favourable spot move:

{table(CC)}

## 5. Strikes (T4)
* **Pairs:** at the strike nearest the previous minute's close {R1['t4_pair_atm_exact']:.0%} exact, {R1['t4_pair_atm_pm1']:.0%} within one step.
* **Solo:** nearest ATM {R1['t4_solo_atm_exact']:.0%} exact, {R1['t4_solo_atm_pm1']:.0%} within one step. The D-1 rule (the premium nearest the last sale's premium on that right) scores {R1['t4_solo_premium_nearest_prev_sale']:.0%}.
  * Solo sells sit around ATM, often at 2 strikes in one burst. Neither rule is exact.

## 6. One ranking number for D0 selling (T5)
{table(AU[['variant', 'AUC', 'ci_lo', 'ci_hi', 'AUC_no_wave_minutes', 'cells', 'positives']])}

`AUC_no_wave_minutes` leaves out the cells within one minute of a timetable wave (out-of-fold waves).

**By sell label (that label's cells against all no-sale cells):**

{table(AT)}

## 7. Kept and rejected
{table(dec)}

## 8. Caveats
* **In-sample.** All 30 cycles were used to find the structure. Scores are out-of-fold over cycle halves only. The timetable groups are small (NIFTY V2: 4 cycles).
* **Teacher-forced parts:** the stop time, the ladder resets at real pair sales, and M3 (real buy-backs). Chunk 5 replaces them with simulated ones.
* **Two matchers.** T3b (descriptive) uses the one-to-one matcher without the stop gate; the machine table uses a minute histogram matcher with the stop gate. The D-1 ladder scores F1 0.154 under both.
* **Solo machines are scored on the minute only.** Strike is not used in their F1 (Section 5 covers strikes). The minute matcher takes exact minutes first, then ±1.
* **Same-minute alignment (AUC A)** uses the bar the sale falls in. B is the causal number.
* **Post-hoc steps:**
  * addenda 1b and 1c were written after seeing T1 and T3;
  * the extended ladder grid and the all-cycle wave table are labelled where they appear.

## Run order
`src/bl_d0_data.py` → `bl_d0s_label.py` → `bl_d0s_tests.py` → `bl_d0s_tt.py` → `bl_d0s_solo.py` → `bl_d0s_auc.py` → `make_d0s_report.py`. Outputs `outputs/bl_d0s_*`, `bl_summary_d0s0…4.json`.
"""
open(os.path.join(RP, 'D0_SELLS.md'), 'w').write(txt); print('written', len(txt))
