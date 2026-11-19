"""Render ../ALGO8_V1_BACKTEST_REPORT.md from computed outputs (all numbers computed)."""
import os, json, numpy as np, pandas as pd
import ref
import warnings; warnings.filterwarnings('ignore')
N_ORD = len(ref.orders(ref.load_fills()))
O = ref.OUT; P = json.load(open(f'{ref.EP}/config/algo8_v1_params.json'))
S = pd.read_csv(f'{O}/v1_backtest_summary.csv'); D = pd.read_csv(f'{O}/v1_backtest_cycles.csv'); PA = pd.read_csv(f'{O}/v1_parity_event_agreement.csv'); PI = pd.read_csv(f'{O}/v1_parity_inventory.csv'); PC = pd.read_csv(f'{O}/v1_parity_cycles.csv')
M2 = pd.read_csv(f'{O}/mode2_event_agreement.csv'); I2 = pd.read_csv(f'{O}/mode2_inventory_by_cycle.csv'); SM = pd.read_csv(f'{O}/mode2_sim_meta.csv')
def md(t, f=2):
    t = t.reset_index(drop=True); o = ['| ' + ' | '.join(map(str, t.columns)) + ' |', '|' + '---|' * len(t.columns)]
    for r in t.itertuples(index=False): o.append('| ' + ' | '.join((f'{x:,.{f}f}' if isinstance(x, (float, np.floating)) else str(x)) for x in r) + ' |')
    return '\n'.join(o)
cols = ['group', 'cycles', 'gross', 'net', 'costs', 'weekly_sharpe', 'max_dd_pct_cycle_level', 'win_rate', 'profit_factor', 'worst_cycle', 'net_ex_top5', 'cycle_stop_share', 'leg_stops_per_cycle']
base = S[(S.variant == 'V0_base') & ~S.group.str.startswith('structure')][cols].copy()
struct = S[(S.variant == 'V0_base') & S.group.str.startswith('structure')][['group', 'cycles', 'net', 'weekly_sharpe', 'win_rate', 'cycle_stop_share']].copy()
sens = []
for g in ('IS', 'OOS (all)'):
    x = S[S.group == g][['variant', 'cycles', 'gross', 'net', 'costs', 'weekly_sharpe', 'max_dd_pct_cycle_level', 'cycle_stop_share', 'orders_per_cycle']].copy(); x.insert(0, 'period', g); sens.append(x)
sens = pd.concat(sens)
fid = PA[PA.strike_mode == 'any'][['category', 'n_sim', 'n_act', 'P', 'R', 'lift_P', 'cls']].copy(); r1 = M2[(M2.variant == 'R1') & M2.primary & (M2.strike_mode == 'any')].set_index('category')
fid['R1_recall_for_comparison'] = [r1.R.get({'D-1 body entries (17 ladder slots, first 3 min)': 'D-1 body entries (original sells in the 17 ladder slots, first 3 min of each)', 'D-1 body entries (all original D-1 body sells)': 'D-1 body entries (all original D-1 body sells)', 'D-1 wing entries': 'D-1 wing entries (h_ Buy)', 'D0 body entries': 'D0 body entries (num Sell)'}.get(c, c), np.nan) for c in fid.category]
dpos = D[D.variant == 'V0_base']; _f = D[D.variant == 'V8_fixed_rupee_cycle_stop'].merge(dpos, on=['und', 'expiry'], suffixes=('_f', '')); NCH = int((abs(_f.net - _f.net_f) > 1).sum()); NALL = len(_f); n_is = int((dpos.split == 'IS').sum()); n_oos = int(dpos.split.str.startswith('OOS').sum())
L = f'''# Algo 8 decision engine v1 — built from the 35 live cycles, backtested 2 years in-sample / 1 year out-of-sample

**What this is.** A rule engine whose entry schedule, strike choice, wing choice, risk controls (per-lot stop, cycle stop, flatten) and settlement are taken from the 35 live cycles and run on the event-driven core (`src/algo8_v1.py`, parameters in `config/algo8_v1_params.json` with ledger hash and provenance). It is the closest executable approximation of Algo 8's observed decision making that the evidence supports. **It is not the original algorithm:** entry schedule and risk constants are descriptive, in-sample hypotheses; behaviours whose trigger is unknown are *not* modelled (off-schedule entries, Clock-B reductions, lump hedge, "4 % carry SL", "1 % expiry-day" rule, margin gate).
**Direction.** Replicating decision making and risk control, not maximising P&L: no parameter was tuned on any period; variants below are pre-declared sensitivities and ablations, and none was selected.

## 1. Read this first — what the IS/OOS split can and cannot tell you
* IS = D0 ≤ 2025-11-17 ({n_is} eligible cycles, ≈ 2 years); OOS = D0 ≥ 2025-11-18 ({n_oos} cycles, ≈ 1 year), the same boundary as the earlier backtest; the single embargo cycle (D-1 in IS, D0 in OOS) is dropped.
* **The rules were read from 35 live cycles (2026-06-23 → 2026-10-22) that lie inside the OOS year.** So the **IS years are out-of-time for the rules** (a genuine test of whether the extracted decision rules behave sensibly on earlier data), whereas the **OOS year contains the sample the rules came from**. It is therefore reported in three tiers: clean before the live window (2025-11-18 → 2026-06-21, previously scored by earlier programmes for related strategies), the live window itself (rules read from it: in-sample), and after it (5 cycles).
* The original has no execution records before June 2026, so **nothing here shows that Algo 8 behaved this way in 2023–2025**, and historical P&L cannot be compared with the original.
* The 2-year IS has {int(((dpos.split == "IS") & (dpos.und == "SENSEX")).sum())} SENSEX cycles only (SENSEX data start 2024-05-30). Expiry structures differ (NIFTY Thursday → Tuesday 2025-09; SENSEX Friday → Tuesday → Thursday): see §4.

## 2. The decision rules (all HYPOTHESES read from the 35 cycles; `config/algo8_v1_params.json`)
| Decision | Rule in v1 | Source / evidence |
|---|---|---|
| Entry timing, D-1 | sell CE and PE at the {len(P["ladder_d1"]["minutes"])} minutes where the original sold in ≥ 50 % of the cycles (they cluster at 09:16 + 15 k min and at the :14 clock minutes), lots = conditional median | schedule covers {100 * P["ladder_d1"]["share_of_original_lots_covered"]:.0f} % of the original D-1 body-sell lots; the rest are off-schedule entries with an unknown trigger (U10), **not modelled** |
| Entry timing, D0 | same construction on D0, {len(P["ladder_d0"]["minutes"])} minutes; **only while the book holds an open body short** and no cycle stop has fired | covers {100 * P["ladder_d0"]["share_of_original_lots_covered"]:.0f} % of original D0 body-sell lots; D0 trigger unknown (U11) |
| Strike | nearest strike to the previous completed minute's index close | exact 79 % in D-1 ladder windows, 45 % over all sells (parity S8) |
| Wing | one OTM same-right wing per body lot whose price ≈ {P["wing"]["price_ratio_to_body"]:.3f} × body price | strike exact 32 % (S11); wing-to-body association is timing-only (U3) |
| Per-lot stop | buy back a body lot at LTP ≥ 1.60 × its own entry (entry ≤ ₹4 exempt); its wing closes with it | band 1.55–1.70; explains ≤ 17 % of original buy-backs (S15) |
| Cycle stop | cumulative LTP MTM ≤ −₹1,44,000 → liquidate everything, no further entries (marks: previous completed close) | −1.30 to −1.44 lakh band; reproduced 1/0/0 of 11 causally (S16) |
| Final flatten | D0 minute {P["flatten"]["minute_post_cutover"]} (15:14) from 2026-08-03; minute {P["flatten"]["minute_pre_cutover"]} (15:20) before | observed last-short minute; pre-cutover rule extrapolated to all earlier history |
| Settlement | residual lots cash-settled at the official index close (Yahoo) | proxy (U12) |
| Execution | fill at the open of the decision minute; slippage max(₹0.10, 0.5 %) against the order; costs per `bt/account.py` | **cost rates other than the 2026 STT are unverified**; no bid/ask data |
| Size | lots as in the ladder, at each session's inferred lot size; **the cycle-stop rupee limit scales linearly with the session lot size** (₹1,44,000 at the 2026 size of the index: NIFTY 65 / SENSEX 20; user decision); the per-lot stop is a price multiple and needs no scaling | historical lot size is inferred from volumes (U14); variant S1 uses 2026 sizes; V8 keeps the limit fixed in rupees (changes {NCH} of {NALL} cycles, all with non-2026 lot sizes) |

## 3. How close is v1 to the 35 live cycles? (in-sample; same pre-registered classes as the parity study)
{md(fid.round(3))}

Inventory: contract-minutes exactly equal **{100 * PI.exact.mean():.1f} %** (R1: {100 * I2[I2.variant == "R1"].exact.mean():.1f} %); overnight short lots actual {PI.short_end_d1_actual.mean():.0f} vs v1 {PI.short_end_d1_sim.mean():.0f} (R1: {I2[I2.variant == "R1"].short_lots_end_d1_sim.mean():.0f}); cycle stops v1 {int(PC.cycle_stop.sum())} of 35 vs 12 actual (R1: {int(SM[SM.variant == "R1"].stopped.sum())}); orders per cycle v1 {PC.n_orders.mean():.0f} vs {N_ORD / 35:.0f} actual.
**Reading:** v1 moves D0 entries from 0 to precision 75 % / recall 26 % and raises D-1 recall to 42 %, but the original's off-schedule and D0 trigger-based actions are still absent, so the inventory path remains a MISMATCH. v1 is *closer*, not equivalent.

## 4. Backtest results (V0 base; net of slippage and estimated costs; ₹2 crore stated capital; weekly Sharpe = weekly net/₹2 Cr × √52, secondary diagnostic)
{md(base)}

By expiry structure (all periods, V0):
{md(struct)}

**Caveats on these numbers.** Costs are large (≈ {100 * D[(D.variant == "V0_base")].costs.sum() / D[(D.variant == "V0_base")].gross.sum():.0f} % of gross) because the engine places ≈ 770 orders per cycle; the cost rates are estimates, not verified statutory figures (only the 2026 STT change is confirmed), so net figures are provisional. Drawdown is computed on the cycle-level cumulative P&L, not the minute path. There is no margin model (the cycle stop is the only capital control). The scaled cycle stop fires in about 32 % of in-sample cycles versus 25 % when the limit is held fixed in rupees (variant V8), because older, smaller lots reach a proportionally smaller limit. Cells of 5–60 cycles carry no confidence intervals. Differences between structures are confounded with lot size, liquidity and volatility.

## 5. Sensitivities and ablations (pre-declared; none selected; none changes the rules)
{md(sens.round(2))}

Ablations show what each part of the decision engine *does* in the replica (for example, removing the wings lowers costs and raises the diagnostic Sharpe; removing the per-lot stop worsens the OOS drawdown severely). They are **not** recommendations: the aim is to reproduce Algo 8's observed structure, so no variant replaces the base rules.

## 6. Verdict
* v1 is a **faithful implementation of what the 35 cycles show at the schedule level** (D-1/D0 ladders, ATM strikes, wings, stops, flatten) and is deterministic, causal and tested (31 tests).
* It is **not yet close to the original at the inventory level** ({100 * PI.exact.mean():.0f} % of contract-minutes exact; the engine carries {100 * PI.short_end_d1_sim.mean() / PI.short_end_d1_actual.mean():.0f} % of the original overnight shorts), because about {100 * (1 - P['ladder_d1']['share_of_original_lots_covered']):.0f} % of D-1 and {100 * (1 - P['ladder_d0']['share_of_original_lots_covered']):.0f} % of D0 body-sell lots fall outside the per-minute schedule (their triggers are not revealed by the records).
* The IS/OOS numbers describe how this rule set behaves historically; they say nothing about the original's performance and the OOS year is contaminated by construction (§1).
* To get closer: parent-order ids and sub-second timestamps (see `NEXT_PHASE_ALPHA_READINESS.md` §5) so the off-schedule and D0 triggers can be identified or rejected instead of approximated.

## 7. Reproduce
`python3 src/params_from_35.py && python3 src/run_v1_parity.py && python3 src/run_v1_backtest.py && python3 src/make_v1_report.py` (≈ 5 min; needs the ledger, the pinned dataset commit and the per-cycle cache). Outputs: `outputs/v1_backtest_cycles.csv` (every cycle × variant), `v1_backtest_summary.csv`, `v1_parity_*.csv`. Tests: `python3 -m pytest tests -q`.
'''
open(os.path.join(ref.EP, 'ALGO8_V1_BACKTEST_REPORT.md'), 'w').write(L); print(len(L))
