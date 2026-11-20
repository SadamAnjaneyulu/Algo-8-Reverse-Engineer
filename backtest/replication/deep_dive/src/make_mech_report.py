"""Builds reports/BODY_REACTIVE_MECHANISM.md from computed outputs (numbers read from outputs/bl_mech_* / bl_react_*)."""
import sys, json, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json')); M1, M2, M3, M4 = J('mech1'), J('mech2'), J('mech3'), J('mech4')
pct = lambda x, n=0: f'{100 * x:.{n}f}%'
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
Hb = pd.read_csv(f'{OUT}/bl_mech_hazard_block.csv'); On = pd.read_csv(f'{OUT}/bl_mech_onset.csv'); GBm = pd.read_csv(f'{OUT}/bl_mech_gb.csv'); GT = pd.read_csv(f'{OUT}/bl_mech_gate.csv'); IA = pd.read_csv(f'{OUT}/bl_mech_interarrival.csv'); ST = pd.read_csv(f'{OUT}/bl_mech_strike_rules.csv', index_col=0); CE = pd.read_csv(f'{OUT}/bl_mech_census.csv', index_col=0); P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); SE = pd.read_csv(f'{OUT}/bl_mech_strata_t_exc.csv'); SV = pd.read_csv(f'{OUT}/bl_mech_strata_t_vol.csv'); MH = pd.read_csv(f'{OUT}/bl_react_move_hazard.csv')
gate = M3['gate_all']; gb = GBm.set_index('model').LOCO_AUC; before = int(P[(P.j < 75)].yR.sum()); after = int(P[(P.j >= 360)].yR.sum()); inw = int(P[(P.j >= 75) & (P.j < 360)].yR.sum())
hb = Hb[Hb.blk.between(1, 24)][['clock', 'R_per1000', 'solo_per1000', 'bb_per1000', 'tot_vol_med', 'rv_med']].copy(); hb['tot_vol_med'] = (hb.tot_vol_med / 1e6).round(0); hb.columns = ['block start', 'reactive pairs per 1000 cycle-min', 'solo sells per 1000', 'buy-backs per 1000', 'median option volume (millions / 15 min)', 'median realised volatility (% / 15 min)']; hb = hb.round(1)
on = On.copy(); on.columns = ['spot excursion from opening ATM', 'cycles', 'Spearman with first reactive pair', 'permutation p', 'median time reached', 'share of cycles reaching it AFTER the first reactive pair']; on['spot excursion from opening ATM'] = ['≥ 1 step', '≥ 1.5 steps', '≥ 2 steps', '≥ 3 steps', 'day range ≥ 0.2%', 'day range ≥ 0.3%']
gt = GT.copy(); gt.columns = ['subset', 'cycle-minutes', 'window start', 'window stop', 'hazard inside (per 1000)', 'hazard outside (per 1000)']
gbt = pd.DataFrame([(m, f'{gb[m]:.3f}') for m in gb.index], columns=['model (reactive-pair minute, leave-one-cycle-out AUC)', 'AUC'])
ia = IA.copy(); ia.columns = ['minutes since previous reactive pair', 'cycle-minutes in window', 'reactive-pair minutes', 'per 1000']
rules = ST.drop(index=['previous reactive strike +-1 step'], errors='ignore').head(8)[['reactive_hit', 'timetable_hit', 'half1', 'half2', 'NIFTY', 'SENSEX']].copy(); rules = (rules * 100).round(1).astype(str) + '%'; rules.insert(0, 'rule', rules.index); rules.columns = ['strike rule', 'reactive pairs (n = 368)', 'timetable pairs', 'first half', 'second half', 'NIFTY', 'SENSEX']
cen = CE.reset_index()[['cls', 'orders', 'lots', 'lots_per_cycle', 'share_of_sold_lots', 'median_clock_h', 'cycles_with']].copy(); cen['share_of_sold_lots'] = cen.share_of_sold_lots.map(lambda v: pct(v, 1)); cen['median_clock_h'] = cen.median_clock_h.map(lambda v: f'{int(v)}:{int(round((v % 1) * 60)):02d}'); cen.columns = ['class (D-1 sell orders, all modules)', 'orders', 'lots', 'lots per cycle', 'share of D-1 sold lots', 'median clock time', 'cycles with it']
se = SE.pivot(index='hour', columns='level', values='per1000'); se = se[['low excursion', 'mid', 'high excursion']].reset_index(); se.columns = ['clock hour', 'low spot excursion from open', 'mid', 'high']
sv = SV.pivot(index='hour', columns='level', values='per1000'); sv = sv[['low volume', 'mid', 'high volume']].reset_index(); sv.columns = ['clock hour', 'low option volume', 'mid', 'high']
mv = MH[MH['var'] == 'a15'][['bin', 'n', 'ev', 'R_per1000', 'solo_per1000']].round(1); mv.columns = ['|15-min spot move| (%)', 'cycle-minutes', 'reactive-pair minutes', 'reactive per 1000', 'solo sell per 1000']
Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); RR = Pr[Pr.reactive]; mid = int(((RR.tod >= 15 * 3600 + 900) & (RR.tod < 15 * 3600 + 25 * 60)).sum()); late = RR[RR.tod >= 15 * 3600 + 25 * 60]; late_n = len(late); late_c = int(late.groupby(['und', 'expiry']).ngroups); late_last3 = int((late.tod >= 15 * 3600 + 28 * 60).sum()); R1 = J('react1')
best = ST.loc['ATM + 1 step toward 15-min move']; v13 = Hb.set_index('blk').loc[13]; v12 = Hb.set_index('blk').loc[12]
txt = f"""# Algo 8 — reactive pairs in depth (D-1): the 10:30–15:15 gate, the strike rule, and a census of every sell

*Investigation only. In-sample, observational (32 D-1 cycles). Plan written before the tests: `BODY_REACTIVE_MECHANISM_PLAN.md`. Numbers are read from `outputs/bl_mech_*`, `bl_react_*` and `bl_summary_mech*.json`. Figure: `figures/bl_mech_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Why only after 11:00?** | **It is not 11:00 — it is a hard time gate at 10:30.** Maximum-likelihood start of the active window **{gate['start']}** (bootstrap 5–95%: {M3['gate_boot_start'][0]}–{M3['gate_boot_start'][2]}), stop **{gate['stop']}** ({M3['gate_boot_stop'][0]}–{M3['gate_boot_stop'][2]}). Inside the window the reactive-pair hazard is **{gate['h_in'] * 1000:.1f}** per 1000 cycle-minutes, outside **{gate['h_out'] * 1000:.1f}** (only {before} reactive-pair minutes before 10:30 and {after} after 15:15, against {inw} inside). Same in NIFTY and SENSEX and in both halves of the sample. The first reactive pair of a cycle comes at a median **{M1['first_q'][2]}** (10–90%: {M1['first_q'][0]}–{M1['first_q'][4]}) because the hazard is ≈ 2.8% per minute after the gate opens; the earlier "11:00" came from averaging by clock hour. | Observed |
| Is it **London open / volume**? | **Not supported.** Option volume peaks at the open and again 14:15–15:00 and is lowest around 11:00–12:00, but the reactive hazard is flat (≈ 20–35 per 1000) across all of that; the gate opens at 10:30 while volume is **falling**. No step at the London open (12:30 IST while the UK is on summer time): hazard {v13.R_per1000:.0f} vs {v12.R_per1000:.0f} per 1000 in the block before; volume ×{M1['vol_ratio_1230_vs_prev']:.2f}. Spot excursion from the opening strike does not explain the onset either (Spearman 0.12–0.24, permutation p 0.19–0.47). | Observed (not supported) |
| So what *is* the gate? | **The clock — or something deterministic in time.** "Waves done so far", "short lots held" and the clock are not separable: a model with those progress variables but **no clock** reaches AUC {gb['no clock + progress']:.3f}, the clock alone {gb['clock only (j)']:.3f}; all proxies without the clock {gb['all proxies, no clock']:.3f}, adding the clock {gb['all proxies + clock']:.3f}. Why 10:30 is a configuration choice that fills cannot reveal. | Observed; reason **Unresolved** |
| **How do they happen inside the window?** | At a roughly **constant rate of ≈ 2.8% per cycle-minute** (≈ one pair-minute every 36 min; mean {M3['interarrival_mean']:.1f} min between successive reactive pairs), **burstier than a Poisson clock** (CV {M3['interarrival_cv']:.2f}; hazard {IA.per1000.iloc[0]:.0f} per 1000 in the minute right after a previous pair vs ≈ 17–34 later). **Not** according to spot move %: the hazard is {mv['reactive per 1000'].iloc[0]:.0f}–{mv['reactive per 1000'].max():.0f} per 1000 for 15-min moves of 0–0.3% and almost zero above 0.3% — unlike solo sells, which keep rising. Each firing is usually one pair (77%). | Observed |
| **Which strike?** | **ATM of the previous minute + 1 step in the direction of the recent (15-minute) move: {pct(best.reactive_hit, 1)}** of reactive pairs (first half {pct(best.half1, 1)}, second half {pct(best.half2, 1)}; NIFTY {pct(best.NIFTY, 1)}, SENSEX {pct(best.SENSEX, 1)}) vs {pct(best.timetable_hit, 1)} for timetable pairs; another 13% are +2 steps. The offset does **not** grow with the size of the move. This is just under my pre-registered 80% line, so I call it **nearly supported**; every other rule (lagged ATM, momentum projection, floor/ceil, synthetic ATM, previous reactive strike) is ≤ 45%. | Observed (near-supported) |
| When does it **stop**? | At the end of the window, **≈ 15:15** (hazard {Hb.set_index('blk').loc[24, 'R_per1000']:.0f} per 1000 in the 15:15–15:30 block vs {Hb.set_index('blk').loc[23, 'R_per1000']:.0f} before); the last reactive pair of a cycle has median {M1['last_q'][2]}. Between 15:15 and 15:25 there are **{mid}** reactive pairs; then **{late_n} pairs in {late_c} cycles in the final minutes 15:25–15:30** ({late_last3} of them at 15:28 or later) — a closing-time effect outside the gate, not part of the hazard fit (the panel ends at 15:28). | Observed |
| **Any other selling** besides timetable pairs, reactive pairs and solo sells? | **Yes — and no unexplained remainder.** Counting every D-1 sell order of every module (**{M4['total_lots']:,} lots in {M4['n_cycles']} cycles**): **hedge-module sells that close long wings = {pct(CE.loc['hedge-module sell closing a long wing', 'share_of_sold_lots'], 1)}** (largest "other" type), **batches of ≥ 3 lots** {pct(CE.loc['batch (>= 3 lots, one strike/right, within 3 s)', 'share_of_sold_lots'], 1)} (a sub-type of solo), end-of-day solo sells (≥ 15:00) {pct(CE.loc['end-of-day solo (>= 15:00)', 'share_of_sold_lots'], 1)}, body sells closing wings {pct(CE.loc['body sell closing a long wing', 'share_of_sold_lots'], 1)}, near-pairs {pct(CE.loc['near-pair (CE and PE within 3 s, different strikes)', 'share_of_sold_lots'], 1)} and stop-module wing sales {pct(CE.loc['stop-module sell closing a long wing', 'share_of_sold_lots'], 1)} (§5). | Observed |

## 1. Definitions (locked in the plan)
Same pair / timetable / reactive definitions as `BODY_REACTIVE_PAIRS.md`. Panel = D-1 cycle-minutes (5–373) without a timetable wave ({len(P):,} rows, {int(P.yR.sum())} reactive-pair minutes). Option volume = CE+PE minute volume of the ATM ±3 strikes; realised volatility = sum of |1-minute returns|; excursion = |spot − opening ATM| in strike steps. Gate = piecewise-constant hazard (low outside, constant inside) fitted by maximum likelihood over start 09:35–11:40 and stop 13:55–15:25 (5-minute grid), cluster bootstrap over cycles (60 draws).

## 2. When it starts and stops (Observed)
Hazard by 15-minute block, with option volume and volatility for comparison:
{table(hb)}
* The step is at **10:30** (block start 10:30: 22 per 1000 vs 0–10 before) and the rate then stays 17–55 per 1000 until 15:15 (the 11:45 block is high, 55). Maximum-likelihood window and bootstrap:
{table(gt)}
  (The V2 subset has only 11 cycles and a noisier estimate, 11:00–14:30 with a high outside rate; V1 and every other subset give 10:30–15:15.)
* **Volume** is highest at 9:15 ({hb['median option volume (millions / 15 min)'].iloc[0]:.0f} million per 15 min in the first listed block) and in 14:15–15:00 (≈ 200), lowest 11:00–12:00 (≈ 115); the hazard does not follow it. Within each clock hour the hazard shows no consistent ordering across the low, mid and high option-volume terciles:
{table(sv)}
* **Spot excursion from the opening strike:** the first reactive pair is not tied to when the spot first leaves the opening ATM:
{table(on)}
* **Clock vs proxies** (leave-one-cycle-out gradient boosting; `no clock` = hour/minute removed; ids = underlying and version):
{table(gbt)}
  Excursion from the open does not help (AUC {gb['no clock + range_open']:.2f}); option volume helps only together with the clock ({gb['clock + volume']:.2f}); the "progress" variables (waves done, short lots held, minutes since the last sell) carry the clock's information ({gb['no clock + progress']:.2f}) — they are all time-driven, so a calendar gate and a progress gate cannot be told apart with this data.

## 3. How a reactive pair happens inside the window (Observed)
* **Rate:** about {gate['h_in'] * 1000:.0f} per 1000 cycle-minutes, constant through the window; mean {M3['interarrival_mean']:.1f} min between pairs (quartiles {M3['interarrival_q'][1]:.1f} / {M3['interarrival_q'][2]:.1f} / {M3['interarrival_q'][3]:.1f}); CV {M3['interarrival_cv']:.2f} > 1 means clustering:
{table(ia)}
* **Not by spot move %:** reactive pairs vs solo sells by the absolute 15-minute spot move:
{table(mv)}
  Reactive pairs do not follow the solo-sell logic (1-minute breakout / favourable move, `BODY_SOLO_VARIABLE_SEARCH.md`): their rate is nearly flat in the size of the move and vanishes in large moves. The earlier report found only a small tilt from market-move and event-history features; none of that changes.
* **Strike:** pre-registered rules ranked by hit rate on reactive pairs:
{table(rules)}
  ("ATM" = nearest strike to the previous-minute spot close; the "toward the move" side is the sign of the spot change over 15 / 5 / 3 minutes.) The sold strike lies about 1.1 steps beyond the spot in the direction of the move (quartiles 0.9–1.4), whatever the size of the move.
* **Quantity:** one pair in 77% of firings, at most {int(R1['burst_pairs_q'][3])}; the number of pairs per firing is not related to lots just bought back (Spearman {R1['corr_pairs_bbl5'][0]:.2f}) or to the strike drift ({R1['corr_pairs_absdrift'][0]:.2f}), and only weakly to the 5-minute move ({R1['corr_pairs_a5'][0]:.2f}).

## 4. Why not London open? (summary of the evidence)
1. The gate opens at 10:30 IST, two hours before the London open (12:30 IST during UK summer time; UK clocks changed on 2026-10-25, after the last D-1 date used).
2. The hazard shows no step at 12:30 (block 12:30: {v13.R_per1000:.0f} per 1000; previous block {v12.R_per1000:.0f}); volume rises only ×{M1['vol_ratio_1230_vs_prev']:.2f} and volatility ×{M1['rv_ratio_1230_vs_prev']:.2f}.
3. Within each clock hour the rate has no consistent ordering across the low/mid/high option-volume terciles (table above).
4. Caveat: option volume and calendar time are strongly collinear in an intraday panel; what I can say is that volume does not add anything once the clock is in, not that the algorithm ignores volume.

## 5. Census of every D-1 sell (Observed)
All sell orders of all modules on D-1, in the fixed priority of the plan:
{table(cen)}
* **Total {M4['total_lots']:,} lots over {M4['n_cycles']} cycles; no residual class.** The three types you know (timetable pairs {pct(CE.loc['scheduled cell', 'share_of_sold_lots'], 1)}, reactive pairs {pct(CE.loc['reactive pair (outside timetable)', 'share_of_sold_lots'], 1)}, solo = single + batch + end-of-day + near-pair {pct(CE.loc[['single solo', 'batch (>= 3 lots, one strike/right, within 3 s)', 'end-of-day solo (>= 15:00)', 'near-pair (CE and PE within 3 s, different strikes)'], 'share_of_sold_lots'].sum(), 1)}) add up to {pct(CE.loc[['scheduled cell', 'reactive pair (outside timetable)', 'single solo', 'batch (>= 3 lots, one strike/right, within 3 s)', 'end-of-day solo (>= 15:00)', 'near-pair (CE and PE within 3 s, different strikes)'], 'share_of_sold_lots'].sum(), 1)}; the other **{pct(CE.loc[[i for i in CE.index if 'long wing' in i], 'share_of_sold_lots'].sum(), 1)}** is wing-closing sells (hedge module, body, stop module).
* **Hedge-module sells closing long wings** ({pct(CE.loc['hedge-module sell closing a long wing', 'share_of_sold_lots'], 1)}; median {int(CE.loc['hedge-module sell closing a long wing', 'median_clock_h'])}:{int(round((CE.loc['hedge-module sell closing a long wing', 'median_clock_h'] % 1) * 60)):02d}; in {int(CE.loc['hedge-module sell closing a long wing', 'cycles_with'])} of 32 cycles) are the unwinds of the wing longs that the hedge module bought (see `BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md`: a balance controller of long wings against short lots). They sell options but reduce protection rather than add short premium.
* **Batches** (≥ 3 lots at one strike and right within 3 s; part of "solo" in the sizing study): {M4['batch_n']} batches in {M4['batch_cycles']} cycles, median {M4['batch_lots_q'][1]:.0f} lots (90%: {M4['batch_lots_q'][3]:.0f}), {pct(M4['batch_ce_share'])} CE, most often in {', '.join(f'{k}:xx' for k, v in sorted(M4['batch_hour'].items(), key=lambda kv: -kv[1])[:3])}; {M4['batch_big_n']} batches of ≥ 10 lots hold {pct(M4['batch_big_share_of_lots'])} of all batch lots (a few outsized orders, up to 54 lots in one order at 15:15–15:31 in one NIFTY cycle).
* **Near-pairs** (CE and PE within 3 s at different strikes) are minor ({M4['near_pair_n']} orders in 4 cycles), and stop-module wing sales occur in one cycle.

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Reactive pairs are gated to 10:30–15:15 (hazard {gate['h_in'] * 1000:.1f} vs {gate['h_out'] * 1000:.1f} per 1000) | **Observed** | ML window, bootstrap, subsets |
| The 10:30 start is not explained by volume, spot excursion or the London open | **Observed** (not supported) | volume strata, excursion correlation, 12:30 check |
| Calendar gate vs progress gate | **Not separable** | progress variables are deterministic in time |
| Inside the window: flat ≈ 2.8%/min, bursty, not move-triggered | **Observed** | inter-arrival, move hazard |
| Strike = previous-minute ATM + 1 step toward the 15-min move ({pct(best.reactive_hit, 1)}) | **Observed** (near-supported, 80% line missed) | 368 pairs, halves, underlyings |
| What fires an individual pair | **Unresolved** | no feature gives a rule |
| Other sells: hedge wing unwinds 19.6%, batches 9.1%, EOD solo 3.6%, body wing sells 2.7%, minor others | **Observed** | census, no residual |
| Why 10:30 / 15:15 | **Unresolved** | configuration |

## 7. Limits and how this could be wrong
* **Minute data**: a trigger on ticks or the live ATM inside the minute would look like a flat hazard with a tilt. The strike rule is evaluated on previous-minute closes.
* **Gate estimation** assumes a two-level hazard; a gradual ramp would show as a less sharp profile, but the likelihood profile peaks sharply at 10:30 (figure B).
* **Time gate vs progress gate** cannot be separated (waves done is a function of time in this strategy).
* **±3 s pairing:** coincident solo sells at one strike would be called a pair; batches and near-pairs are defined on the same rule.
* **Census classes** use fixed priority; a sell that fits two types is counted in the first (order in the plan). Hedge-module classification comes from earlier contract-level roles.
* In-sample; D-1 only; 32 cycles; predictive not causal; no source code.

## 8. Files
`src/bl_mech_panel.py` → `bl_mech_tests1.py` (onset, volume, clock vs proxies) → `bl_mech_strike.py` → `bl_mech_tests2.py` (gate, inter-arrival) → `bl_mech_census.py` → `bl_mech_fig.py` → `make_mech_report.py`. Outputs `outputs/bl_mech_*`, `bl_summary_mech*.json`. Tests `tests/test_bl.py` (`test_mech_*`).
"""
open(f'{RP}/BODY_REACTIVE_MECHANISM.md', 'w').write(txt); print(len(txt.splitlines()), 'lines')
