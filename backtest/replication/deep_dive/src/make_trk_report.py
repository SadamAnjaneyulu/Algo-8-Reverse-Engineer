"""Builds reports/BODY_REACTIVE_TRACKER.md from computed outputs (bl_trk_*, bl_summary_trk1-7.json)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from scipy.stats import chi2
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); R1, R2, R3, R4, R5, R6, R7 = J('trk1'), J('trk2'), J('trk3'), J('trk4'), J('trk5'), J('trk6'), J('trk7')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
SEC = pd.read_csv(f'{OUT}/bl_trk_seconds.csv'); CV = pd.read_csv(f'{OUT}/bl_trk_sim_cv.csv'); CV2 = pd.read_csv(f'{OUT}/bl_trk_sim2_cv.csv'); SP = pd.read_csv(f'{OUT}/bl_trk_sim2_splits.csv'); CR = pd.read_csv(f'{OUT}/bl_trk_sim2_cross.csv'); CP = pd.read_csv(f'{OUT}/bl_trk_cap.csv'); SD = pd.read_csv(f'{OUT}/bl_trk_side.csv'); MS = pd.read_csv(f'{OUT}/bl_trk_miss.csv'); FR = pd.read_csv(f'{OUT}/bl_trk_fires.csv'); EN = pd.read_csv(f'{OUT}/bl_trk_example_NIFTY.csv'); ES = pd.read_csv(f'{OUT}/bl_trk_example_SENSEX.csv'); CNT = pd.read_csv(f'{OUT}/bl_trk_counts.csv')
sec = SEC.copy(); sec['p (uniform)'] = sec.chi2_p_uniform.map(lambda v: f'{v:.4f}'); sec['share in first 10 s'] = sec.share_first_10s.map(lambda v: pct(v, 1)); sec = sec[['group', 'n', 'sec 0-9', 'sec 10-19', 'sec 20-29', 'sec 30-39', 'sec 40-49', 'sec 50-59', 'share in first 10 s', 'p (uniform)']]; sec.columns = ['group', 'n', ':00–09', ':10–19', ':20–29', ':30–39', ':40–49', ':50–59', 'share in first 10 s (uniform = 16.7%)', 'p vs uniform']
disp = R1['dispersion_var_over_mean']; p_under = chi2.cdf(31 * disp, 31)
fam_names = {'M0': 'M0 stateless range edge', 'M1': 'M1 range edge + refractory K', 'M1ss': 'M1 with refractory only for the same side', 'M2': 'M2 reference-move (grid) tracker', 'M2s': 'M2 + reset at scheduled pairs', 'M3': 'M3 swing (zig-zag) tracker', 'M4': 'M4 range edge + swing'}
cv = CV.copy(); cv['machine'] = cv.family.map(fam_names); cv['info'] = cv['info'].map({'bar': 'completed bars (causal)', 'intra': 'current-minute close (look-ahead proxy)'})
for c_ in ('precision_tol1', 'recall_tol1', 'F1_tol1', 'null_F1_p99', 'side_agreement_matched'): cv[c_] = cv[c_].round(3)
cv['F1 same minute'] = (2 * cv.precision_tol0 * cv.recall_tol0 / (cv.precision_tol0 + cv.recall_tol0)).round(3); cv['fires per cycle'] = cv.mean_fires_per_cycle.round(1); cv['count variance/mean'] = cv.count_var_over_mean.round(2)
cv = cv[['machine', 'info', 'configs', 'chosen_params', 'precision_tol1', 'recall_tol1', 'F1_tol1', 'null_F1_p99', 'F1 same minute', 'side_agreement_matched', 'fires per cycle', 'count variance/mean']]; cv.columns = ['machine', 'information', 'configs', 'parameters chosen (fold 1 / fold 2)', 'precision (±1 min)', 'recall (±1 min)', 'F1 (±1 min)', 'null F1 99th pct', 'F1 same minute', 'side agreement of matches', 'fires per cycle', 'fires: variance/mean']
c2 = CV2.copy(); c2['machine'] = c2.family.map({'M1': 'M1 level-triggered range edge + refractory', 'M7': 'M7 edge-triggered (re-arms when back inside) + refractory', 'M5': 'M5 band restarts at each fire'}); c2['information'] = c2['info'].map({'bar': 'completed bars', 'intra': 'current-minute close'})
for k in ('precision_tol1', 'recall_tol1', 'F1_tol1', 'F1_tol0', 'F1_tol2', 'insample_F1_tol1'): c2[k] = c2[k].round(3)
c2 = c2[['machine', 'information', 'configs', 'chosen_params', 'precision_tol1', 'recall_tol1', 'F1_tol1', 'F1_tol0', 'F1_tol2', 'insample_best', 'insample_F1_tol1']]; c2.columns = ['machine', 'information', 'configs', 'parameters chosen (N, K) fold 1 / fold 2', 'precision (±1 min)', 'recall (±1 min)', 'F1 (±1 min)', 'F1 same minute', 'F1 (±2 min)', 'in-sample best (N, K)', 'in-sample F1']
sp = R3['splits']; cr = CR.copy(); cr['precision'] = cr.precision.round(3); cr['recall'] = cr.recall.round(3); cr['F1'] = cr.F1.round(3); cr['same N, K = 1 (no spacing)'] = cr.same_N_K1_F1.round(3); cr = cr[['fit_on', 'scored_on', 'N', 'K', 'cycles_scored', 'precision', 'recall', 'F1', 'same N, K = 1 (no spacing)']]; cr.columns = ['parameters fitted on', 'scored on (frozen)', 'N', 'K', 'cycles', 'precision', 'recall', 'F1', 'F1 with no spacing (K = 1)']
cp = CP.copy()
for k in ('precision', 'recall', 'F1', 'fires_per_cycle', 'count_var_over_mean', 'count_sd'): cp[k] = cp[k].round(3)
cp.columns = ['model', 'configs', 'parameters chosen (N, K, cap, κ) fold 1 / fold 2', 'precision', 'recall', 'F1', 'fires per cycle', 'variance/mean of fires', 'SD of fires']
sd = SD.copy()
for k in ('precision', 'recall', 'F1', 'split_F1_mean', 'split_F1_lo', 'split_F1_hi'): sd[k] = sd[k].round(3)
sd.columns = ['model', 'configs', 'parameters chosen (N, K_same, K_opp)', 'precision', 'recall', 'F1', 'F1 random splits (mean)', '2.5%', '97.5%']
ms = MS.copy(); ms['machine fire within ±1 min'] = ms.machine_near.map({0: 'no (missed)', 1: 'yes'}); ms = ms[['machine fire within ±1 min', 'n', 'la_breakout', 'age_react_min', 'n_react_sofar']].round(2); ms.columns = ['actual pair minute', 'n', 'share with current-minute close beyond the prior 60 closes', 'median min since previous pair', 'mean pairs so far']
fh = pd.DataFrame(R4['precision_by_hour'].items(), columns=['hour', 'precision']); fh['hour'] = fh.hour.map(lambda h: f'{h}:00'); fh['precision'] = fh.precision.map(lambda v: pct(v, 0))
en = EN.copy(); es = ES.copy()
for d in (en, es): d.columns = ['time', 'seconds from 09:15', 'strike', 'live ATM', 'strike − ATM (steps)', 'live spot', 'position in 70-min range', 'min since previous reactive pair', 'tracker fire within ±1 min']
top = CV2.sort_values('F1_tol1', ascending=False).iloc[0]; m1 = CV[(CV.family == 'M1') & (CV['info'] == 'bar')].iloc[0]; m0 = CV[(CV.family == 'M0') & (CV['info'] == 'bar')].iloc[0]; m1i = CV[(CV.family == 'M1') & (CV['info'] == 'intra')].iloc[0]
cap_row = CP[CP.model == 'M1 + cap'].iloc[0]; gr_row = CP[CP.model == 'M1 + growing refractory'].iloc[0]; m1_row = CP[CP.model.str.startswith('M1 (cap')].iloc[0]
txt = f"""# Algo 8 — reactive pairs: is there a per-minute tracker?

*Investigation only. In-sample (D-1 of {R1['cycles_total']} live cycles, {R2['actual_pair_minutes']} reactive pair-minutes inside 10:30–15:15; not a holdout). Plan written before the tests: `BODY_REACTIVE_TRACKER_PLAN.md`. Steps after the first simulation (finer grids, edge-triggered/band-reset variants, capacity, side-specific spacing, residuals) are **post-hoc** and labelled. Figures: `figures/bl_trk_example_NIFTY.png`, `figures/bl_trk_example_SENSEX.png`, `figures/bl_trk_logic.png`. Everything describes a machine that reproduces the timing; **it does not show that Algo 8 contains this machine.***

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| Was "19 of 100 breakouts fire" the wrong yardstick? | **Yes.** It treated the condition as stateless. A tracker that keeps state and resets when it fires will ignore most condition-true minutes. The right test is to **simulate the tracker forward through each day and compare its fire times with the real pair times.** | Method |
| Is there a stateful per-minute tracker that reproduces the pairs? | **A simple one does, partially.** "Fire when the price is beyond its trailing ~70-minute range, then stay silent for ~4–14 minutes" matches the real pair minutes within ±1 minute with **precision {pct(m1.precision_tol1)}, recall {pct(m1.recall_tol1)}, F1 {m1.F1_tol1:.2f}** out-of-fold (random-timing null 99th percentile {m1.null_F1_p99:.2f}); the same range edge **without** state gives F1 {m0.F1_tol1:.2f}. Side of the strike agrees in {pct(m1.side_agreement_matched)} of matches. 100 random half-splits: F1 {sp['F1_mean']:.2f} (95% {sp['F1_q'][0]:.2f}–{sp['F1_q'][1]:.2f}). Fitted on NIFTY it scores F1 {CR.F1.iloc[0]:.2f} on SENSEX, fitted on SENSEX {CR.F1.iloc[1]:.2f} on NIFTY; across schedule versions {CR.F1.iloc[2]:.2f} / {CR.F1.iloc[3]:.2f}. | Observed (description); mechanism **Inferred** |
| Does it reproduce everything? | **No.** About half of the real pair-minutes have no tracker fire within ±1 minute and about half of the tracker's fires have no pair; to the same minute only F1 {2 * m1.precision_tol0 * m1.recall_tol0 / (m1.precision_tol0 + m1.recall_tol0):.2f} (completed bars) / {2 * m1i.precision_tol0 * m1i.recall_tol0 / (m1i.precision_tol0 + m1i.recall_tol0):.2f} (current-minute close). | Observed |
| Is it a per-minute clock? | **Not a fixed-second one.** Reactive pairs are spread almost uniformly over the seconds of the minute (only {pct(SEC.share_first_10s.iloc[0], 1)} in the first 10 s vs 16.7% uniform, p = {SEC.chi2_p_uniform.iloc[0]:.3f}), whereas scheduled timetable pairs are timer-driven ({pct(SEC.share_first_10s.iloc[1], 0)} in the first 10 s). So the check seems continuous or sub-minute, not once per minute at a fixed second. | Observed (seconds); frequency **Not testable** |
| Other tracker types? | **Do not fit as well.** Reference-move ("grid") trackers F1 {CV[(CV.family == 'M2') & (CV['info'] == 'bar')].F1_tol1.iloc[0]:.2f} and swing/zig-zag {CV[(CV.family == 'M3') & (CV['info'] == 'bar')].F1_tol1.iloc[0]:.2f} fail; range edge + swing {CV[(CV.family == 'M4') & (CV['info'] == 'bar')].F1_tol1.iloc[0]:.2f} (it also resets on each fire) is second best; restarting the band at each fire {CV2[(CV2.family == 'M5') & (CV2['info'] == 'bar')].F1_tol1.iloc[0]:.2f}. | Observed |
| How many pairs per day? | **{R1['mean']:.1f} ± {np.sqrt(R1['var']):.1f} per cycle (range {R1['min_max'][0]}–{R1['min_max'][1]}) — more regular than random arrivals** (variance/mean {disp:.2f} vs 1 for Poisson, p = {p_under:.4f}) and **unrelated to the day's number of breakouts** (Spearman {R1['spearman_pairs_vs_la_breakout_minutes'][0]:.2f}, p = {R1['spearman_pairs_vs_la_breakout_minutes'][1]:.2f}), to buy-back lots (Spearman {R1['spearman_pairs_vs_buyback_lots'][0]:+.2f}) or to the number of scheduled pairs ({R1['spearman_pairs_vs_scheduled_pairs'][0]:+.2f}). The market decides *when*, something else regularises *how many*. | Observed; cause **Unresolved** |

## 1. Time-aligned example cycles
Chosen by the rule fixed in the plan (≥ 8 reactive pairs, count closest to the median {R6['median_reactive_pairs_per_cycle']:.0f}, earliest expiry on ties): **NIFTY {R6['NIFTY']['expiry']}** and **SENSEX {R6['SENSEX']['expiry']}** (12 pairs each). Each figure shows, over 09:15–15:30: the spot with its trailing 70-minute high–low band and every reactive pair at its exact second; the live position inside the range; an event timeline (actual pairs, simulated tracker, scheduled pairs, buy-backs, hedge/stop/lump orders); and minutes since the previous reactive pair.

![NIFTY example](figures/bl_trk_example_NIFTY.png)

{table(en)}
![SENSEX example](figures/bl_trk_example_SENSEX.png)

{table(es)}
What the examples show (observed in these two cycles; not a proof):
* **Every pair is placed with the live spot at the edge of its trailing 70-minute range** (position −0.41 … −0.59 or +0.49 … +0.54 in all but the last SENSEX pair at 15:29), the strike one step beyond ATM on the side of that edge.
* The spot spends long stretches at the edge with **no** pair (NIFTY roughly 11:05–11:35 and 12:40–13:30: the price hugs the lower edge and nothing is sold), which is the spacing the state machine models.
* Several pairs are placed at the **same second** (NIFTY 12:30:08, 15:09:52; SENSEX 11:20:04, 13:46:10, 15:29:36): one fire can place 2–3 pair-lots ({int((FR.pairs > 1).sum())} of {len(FR)} fires have 2+ pairs; {int(FR.pairs.sum())} pairs in {len(FR)} fires clustered within 5 s).
* The simulated tracker (parameters chosen on the other half of the cycles) matches {R6['NIFTY']['matched']} of 12 (NIFTY) and {R6['SENSEX']['matched']} of 12 (SENSEX) pairs within ±1 minute: **better than the average** (recall {pct(m1.recall_tol1)}), so these two are not typical of the failures; it also fires more often than the real system ({R6['NIFTY']['machine_fires']} and {R6['SENSEX']['machine_fires']} fires).

## 2. Timing structure
{table(sec)}
* Reactive pairs: only a mild excess in the first 10 s of the minute; scheduled pairs are strongly concentrated at fixed seconds (:00, :10, :31, :59). A once-a-minute tracker with fixed latency would look like the second row; reactive pairs do not.
* Per cycle: {R1['mean']:.2f} reactive pairs, SD {np.sqrt(R1['var']):.2f}, counts {R1['min_max'][0]}–{R1['min_max'][1]} (cycles per count: {', '.join(f'{k}: {v}' for k, v in CNT.reactive_pairs.astype(int).value_counts().sort_index().items())}); variance/mean {disp:.2f}. Pair counts do not follow breakouts (Spearman with current-minute breakout minutes {R1['spearman_pairs_vs_la_breakout_minutes'][0]:+.2f}, with completed-bar breakout minutes {R1['spearman_pairs_vs_causal_breakout_minutes'][0]:+.2f}).

## 3. Forward-simulated trackers (pre-registered grid, out-of-fold)
Each machine runs through each day from 10:30, keeps its own state and resets on its own fires. Parameters are chosen on one half of the cycles (alternating) and scored on the other, both ways; "±1 min" = a fire within one minute of a real pair-minute, one-to-one matching. Null: the same fire times shifted by a random offset in each cycle (1,000 draws).

{table(cv)}
* **Range edge + refractory (M1) is the only family that matches**: F1 {m1.F1_tol1:.2f} vs null 99th percentile {m1.null_F1_p99:.2f}; precision and recall both ≥ 0.4 (the pre-registered success rule is met for the **±1-minute** definition).
* The stateless range edge **over-fires** (≈ {m0.mean_fires_per_cycle:.0f} fires per cycle vs ≈ 8 pair-minutes): recall {pct(m0.recall_tol1)} but precision {pct(m0.precision_tol1)} — the state (spacing) is what converts the edge condition into pair times. Variance/mean of fires per cycle: M1 {m1.count_var_over_mean:.2f} vs real pair-minutes {R5['actual_pair_minutes_per_cycle']['var_over_mean']:.2f}.
* Reference-move, swing and range-edge-plus-swing trackers are clearly worse (M2 resets at scheduled pairs do not help).

## 4. Extension (post-hoc): finer grid, variants, validation
Finer grid N ∈ 20…150 and K ∈ 1…40 ({R3['n_configs']} configurations):

{table(c2)}
* **Level-triggered and edge-triggered perform alike**; restarting the band at every fire is clearly worse. The cross-validated optimum moves to **N ≈ 70–80 with K ≈ 4–14** when state is included (N = 40–70 on the seconds-level activation study): window and spacing are **not separately identifiable** — a longer window with a spacing fits as well as a shorter one.
* **100 random half-splits**: out-of-fold F1 {sp['F1_mean']:.2f} (95% {sp['F1_q'][0]:.2f}–{sp['F1_q'][1]:.2f}), precision {sp['precision_mean']:.2f}, recall {sp['recall_mean']:.2f}; chosen N = 70 in {pct(sp['N_share'].get('70', sp['N_share'].get(70, 0)))} and 80 in {pct(sp['N_share'].get('80', sp['N_share'].get(80, 0)))} of splits.
* **Frozen cross-validation** (parameters fitted on one group, scored on the other):

{table(cr)}
  The spacing adds {np.mean(CR.F1 - CR.same_N_K1_F1):+.2f} F1 on average over the same range edge without it.

## 5. Extension (post-hoc): capacity, growing spacing, side-specific spacing
{table(cp)}
* A **cap of ≈ 12 fires** reproduces the regular daily counts (variance/mean {cap_row.count_var_over_mean:.2f}, real {R5['actual_pair_minutes_per_cycle']['var_over_mean']:.2f}) but does not improve timing (F1 {cap_row.F1:.3f} vs {m1_row.F1:.3f}); a **spacing that grows by 0.5 minute per fire** lifts F1 slightly to {gr_row.F1:.3f} (random-split mean {R5['random_split_F1_all_extensions'][0]:.2f}). Neither difference is decisive.
* Side-specific spacing does not help:

{table(sd)}

## 6. Residuals (post-hoc): where the machine fails
Machine M1 frozen at N = 70, K = 12 (completed bars): {R4['fires']} fires, {R4['fires_matching']} match a pair within ±1 minute (precision {pct(R4['precision'])}); {R4['pair_minutes_matched']} of {R4['pair_minutes']} pair-minutes have a fire within ±1 minute (recall {pct(R4['recall'])}).

{table(ms)}
* Missed pair-minutes are less often at a current-minute breakout (61% vs 92%): a part of the misses is intra-minute movement the minute-close data cannot show.
* Precision falls through the day and with the number of pairs already placed (fires by hour: {', '.join(f'{h} {p}' for h, p in zip(fh.hour, fh.precision))}): late in the day the machine fires where the real system does not, consistent with a daily capacity or decaying appetite that the machine lacks.
* One feature (relative volume at the target strike) looked informative among fires (AUC 0.71) but is probably contaminated by the system's own fills (a pair at the previous minute raises that strike's volume) and is not used.

## 7. Evidence register
| Claim | Label | Basis |
|---|---|---|
| "Breakouts that fire" is the wrong yardstick; a stateful forward simulation is the right test | **Method** | stateless vs stateful F1 {m0.F1_tol1:.2f} → {m1.F1_tol1:.2f} |
| A range-edge machine with a 4–14-minute spacing reproduces about half of the pair times (±1 min) out-of-fold, on both underlyings and both schedule versions | **Observed** | F1 {sp['F1_mean']:.2f} (random splits), cross-instrument {CR.F1.min():.2f}–{CR.F1.max():.2f}, null 99th pct {m1.null_F1_p99:.2f} |
| The pairs come from a per-minute tracker with state | **Inferred** | simulation fit; alternative stateful mechanisms (timer, rate limit, budget) fit as well |
| The tracker checks at a fixed second of each minute | **Not supported** | seconds roughly uniform (p = {SEC.chi2_p_uniform.iloc[0]:.3f}, +24% in the first 10 s) |
| Exact window and spacing | **Not identifiable** | N 70–80 with K 4–14; N and K trade off |
| Reference-move, swing, band-restart trackers | **Rejected** | F1 {CV[(CV.family == 'M2') & (CV['info'] == 'bar')].F1_tol1.iloc[0]:.2f} / {CV[(CV.family == 'M3') & (CV['info'] == 'bar')].F1_tol1.iloc[0]:.2f} / {CV2[(CV2.family == 'M5') & (CV2['info'] == 'bar')].F1_tol1.iloc[0]:.2f} |
| A daily capacity (≈ 12) | **Possible, not needed for timing** | regularises counts, no timing gain |
| What the remaining half of the pair times depend on | **Unresolved** | intra-minute movement, late-day behaviour, unknown state |
| Calculation frequency, tick-level crossing | **Not testable** | minute data only |

## 8. Limits and how this could be wrong
* **±1-minute tolerance** is generous at 266 pair-minutes in 286 minutes per cycle; the null (random shifts) controls for it (99th percentile {m1.null_F1_p99:.2f}), but the same-minute match is poor with completed bars ({2 * m1.precision_tol0 * m1.recall_tol0 / (m1.precision_tol0 + m1.recall_tol0):.2f}); I cannot claim to reproduce the exact trigger second.
* **Search size:** 288 + {R3['n_configs']} + {R5['n_configs']} + {R7['n_configs']} configurations were evaluated in total across steps (the plan's "≈ 100" was an underestimate for the first step: 288). Parameters were always chosen out-of-fold and validated on random splits and across instruments, but the families after M1 were designed after seeing M1 (post-hoc) and no multiplicity correction is applied.
* **Descriptive, not causal:** equivalent mechanisms (timer, rate limit, budget, hysteresis) can produce the same spacing; the machine is a compact description.
* **Current-minute information:** the "current-minute close" variant is look-ahead; the completed-bar variant is causal.
* **Close-based range;** no spot high/low or ticks; D-1 only; in-sample; no source code. The two example cycles were chosen by a rule fixed in advance, but their tracker match (11/12, 10/12) is above average.

## 9. Files
`src/bl_trk_timing.py` (T1) → `bl_trk_sim.py` (T2 grid) → `bl_trk_sim2.py` (post-hoc extension) → `bl_trk_resid.py` → `bl_trk_cap.py` → `bl_trk_side.py` → `bl_trk_example.py` (figures + tables) → `bl_trk_fig.py` → `make_trk_report.py`; `bl_trk_fires.csv` from the fire clustering step. Outputs `outputs/bl_trk_*`, `bl_summary_trk1…7.json`. Tests `tests/test_bl.py` (`test_trk_*`).
"""
open(f'{RP}/BODY_REACTIVE_TRACKER.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
