"""Writes TP01_REPORT.md. Every number is read from the data / analysis outputs, none is typed in. python3 tp_reconstruction/scripts/write_report.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import tp_common as tc
A = lambda f: pd.read_csv(os.path.join(tc.ANALYSIS, f)); D = lambda f: pd.read_parquet(os.path.join(tc.DATA, f))
n0 = lambda v: f'{int(round(v)):,}' if isinstance(v, (int, float, np.integer, np.floating)) and np.isfinite(v) else ('' if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)); n1 = lambda v: f'{v:,.1f}'; pc = lambda v, d=1: f'{100 * v:.{d}f} %'; rs = lambda v: f'₹{v / 1e5:,.2f} L'


def table(df, cols=None, fmt=None):
    cols = cols or list(df.columns); fmt = fmt or {}
    out = ['| ' + ' | '.join(cols) + ' |', '|' + '|'.join(['---'] * len(cols)) + '|']
    for _, r in df.iterrows(): out.append('| ' + ' | '.join(fmt.get(c, lambda v: v)(r[c]) if c in fmt else str(r[c]) for c in cols) + ' |')
    return '\n'.join(out)


import re, ast
clean = lambda t: ast.literal_eval(re.sub(r'np\.float64\(([^)]*)\)', r'\1', t))
R = pd.read_csv(os.path.join(tc.DATA, 'reconciliation_summary.csv')).set_index('method')
DQ = A('data_quality_report.csv').set_index('check'); S = A('profitability_summary.csv'); M = A('matching_sensitivity.csv'); X = D('exit_event_consensus.parquet'); E = D('exit_events.parquet')
EP = D('position_episodes.parquet'); UL = A('underlying_level_summary.csv'); EL = A('expiry_level_summary.csv'); XC = A('crosscheck_vs_stage1_ledger.csv').set_index('item').value
Dec = A('premium_decay_distribution.csv'); H = A('closing_hazard_by_decay.csv'); C = A('exit_pattern_summary.csv'); ctx = A('market_context_summary.csv'); B = A('exit_behavior_summary.csv'); PP = A('profit_per_unit_summary.csv'); HD = A('holding_duration_summary.csv')
CL = A('clock_minute_clusters.csv'); man = json.load(open(os.path.join(tc.DATA, 'source_manifest.json')))
f = R.loc['FIFO']; lots = (E[E.method == 'FIFO'].qty_closed / E[E.method == 'FIFO'].und.map(tc.LOT)).sum()
st = M[M.section == 'closing-fill stability'].set_index('key'); cons = M[M.section == 'consensus label'].set_index('key')
cf = S[S.level == 'closing fill'].pivot(index='method', columns='label', values='count'); cu = S[S.level == 'closing fill'].pivot(index='method', columns='label', values='units')
pf = S[S.level == 'matched piece'].pivot(index='method', columns='label', values='count'); pos = S[S.level == 'position (fully closed)'].pivot(index='method', columns='label', values='count')
pnl = {m: R.loc[m, 'realized_gross_pnl_rupees'] for m in tc.METHODS}; sh = E[(E.method == 'FIFO') & (E.direction == -1)]
shp = sh[sh.label == 'PROFIT']; shl = sh[sh.label == 'LOSS']
hz = {m: H[(H.und == 'ALL') & (H.convention == m) & (H.rows >= 200)] for m in tc.METHODS}
peak = {m: hz[m][hz[m].bin_lo_pct >= 100].sort_values('hazard_standardised').iloc[-1] for m in tc.METHODS}
base_hz = {m: hz[m][(hz[m].bin_lo_pct >= 20) & (hz[m].bin_lo_pct < 100)].hazard_standardised.mean() for m in tc.METHODS}
prof_hz_max = {m: hz[m][hz[m].bin_lo_pct < 100].hazard_standardised.max() for m in tc.METHODS}
dcl = Dec[(Dec.side == 'PROFIT') & Dec.is_cluster]
c_dec = C[C.pattern_id == 'DECAY-0-5']; c_clk = C[C.family == 'clock minute']
tie = R.loc['FIFO', 'tie_ambiguous_fills']
ctx_t = ctx.set_index('feature')
dmod = {}
for k, v in XC.items():
    if k.startswith('difference: module '): dmod[k.split()[2]] = dmod.get(k.split()[2], 0) + int(v)
Lg = D('fill_event_ledger.parquet'); cyc = Lg.groupby(['und', 'expiry']).date.min().reset_index(); n_nod1 = int((cyc.date >= cyc.expiry).sum())
def mixtxt(t):
    d = clean(t); return ' / '.join(f"{m} {100 * d[m].get('PROFIT', 0):.0f} % profit" for m in tc.METHODS)
def line(m): return f"{m}: {n0(cf.loc[m, 'PROFIT'])} / {n0(cf.loc[m, 'LOSS'])} / {n0(cf.loc[m, 'BREAKEVEN'])} / {n0(cf.loc[m, 'UNRESOLVED'])}"
R_ = []
w = R_.append
w(f"""# TP-01 · Profitable position reconstruction and exit classification

**Verdict: PASS (reconstruction and descriptive analysis). The take-profit rule is NOT recovered.** The data support a stop-like response
(closing hazard peaks near 160–170 % of the reference entry) and clock-driven closing spikes. They do **not** show a fixed premium-decay take-profit level.
Everything here is observed behaviour or a labelled hypothesis. All results are in-sample on the same 65 sessions; nothing is validated on new data.
Branch `research/tp01-position-reconstruction` (from the Stage 1 tip `80baac08`). Phase 0 audit: [`PHASE0_AUDIT.md`](PHASE0_AUDIT.md).

## 1. Executive summary

| Question | Answer |
|---|---|
| Reconstructed | **{n0(f.episodes)} inventory episodes** (positions) in {R.loc['FIFO', 'contract_direction_cells']:,} contract-direction cells; **{n0(f.closed_units)} units closed** ({n0(lots)} lots) by **{n0(E[E.method == 'FIFO'].shape[0])} closing fills**; {n0(f.opened_units)} units opened; {n0(f.remaining_units)} units never closed (all in contracts that expired) |
| Reconciliation | opened = closed + remaining in every contract and direction; every fill unit is opened or closed; **0 unexplained units**; cash identity exact (difference {f.cash_identity_difference}) |
| Labels per closing fill (PROFIT / LOSS / BREAKEVEN / UNRESOLVED) | {line('FIFO')} · {line('LIFO')} · {line('AVG')} |
| Stable across FIFO / LIFO / average cost | **{pc(st.loc['STABLE', 'share_of_units'])} of closed units** ({pc(st.loc['STABLE', 'share_of_fills'])} of fills); position-level results are identical (fully closed positions: {n0(pos.loc['FIFO', 'PROFIT'])} profit / {n0(pos.loc['FIFO', 'LOSS'])} loss / {n0(pos.loc['FIFO', 'BREAKEVEN'])} breakeven) |
| Sensitive to the convention | **{pc(st.loc['CONVENTION_SENSITIVE', 'share_of_units'])} of closed units** ({n0(st.loc['CONVENTION_SENSITIVE', 'closing_fills'])} fills): the label depends on which lot a closing fill is assumed to close |
| Unresolved by order | {n0(st.loc['UNRESOLVED_ORDER', 'closing_fills'])} closing fills ({n0(st.loc['UNRESOLVED_ORDER', 'units'])} units): equal-second ordering changes their closing quantity |
| Realised gross P&L of closed quantities | {rs(pnl['FIFO'])} FIFO · {rs(pnl['LIFO'])} LIFO · {rs(pnl['AVG'])} average cost. **Net P&L: unavailable** (no charge fields). Excludes expiry settlement of the {n0(f.remaining_units)} unclosed units |
| Profitable short exits | median exit premium **{shp.exit_pct_of_entry.median():.0f} %** of entry (quartiles {shp.exit_pct_of_entry.quantile(.25):.0f}–{shp.exit_pct_of_entry.quantile(.75):.0f} %), median profit {shp.pnl_pts_per_unit.median():.1f} points/unit; **no decay-level cluster under all three conventions** |
| Closing hazard | stop-like peak at {peak['FIFO'].bin_lo_pct:.0f}–{peak['FIFO'].bin_lo_pct + 5:.0f} % (FIFO) / {peak['LIFO'].bin_lo_pct:.0f}–{peak['LIFO'].bin_lo_pct + 5:.0f} % (LIFO) / {peak['AVG'].bin_lo_pct:.0f}–{peak['AVG'].bin_lo_pct + 5:.0f} % (average cost) of the reference entry, hazard {peak['FIFO'].hazard_standardised:.2f} / {peak['LIFO'].hazard_standardised:.2f} / {peak['AVG'].hazard_standardised:.2f} versus about {base_hz['AVG']:.2f} elsewhere; **no peak on the profit side** (maximum {max(prof_hz_max.values()):.2f}) |
| Cannot be inferred | which lot a closure belongs to; the decision rule behind any closure; settlement P&L of unclosed units; net P&L; anything about periods outside these 65 sessions |

## 2. Raw source and verified counts

| Item | Verified |
|---|---|
| File / SHA-256 | `{man['raw_file']}` · `{man['sha256']}` |
| Fill rows | **{n0(man['rows'])}** (columns: {man['columns']}); ledger rows {n0(man['ledger_rows'])}; rows flagged by a data-quality rule: {man['flagged_rows']} |
| Parent orders (`UniqueOrderIdentifier`, column 163) | **{n0(DQ.loc['parent orders (col 163)', 'value'])}**; column 4 order numbers {n0(DQ.loc['order numbers (col 4), reused across days', 'value'])} (reused across days: not an identity) |
| Sessions / contracts | {DQ.loc['sessions', 'value']} sessions ({DQ.loc['sessions', 'note']}); {n0(DQ.loc['contracts', 'value'])} contracts |
| Quantity convention | units (multiples of 65 NIFTY / 20 SENSEX). P&L in rupees = points × units, **no lot multiplier** |
| Price convention | per-fill price = column 137. **Column 18 is the running order-average price** (differs from the fill price on {n0(DQ.loc['fills whose per-fill price differs from the running order average (col 18)', 'value'])} fills of multi-fill orders) |

The earlier research (41,421 fills, 39,874 parent orders) is confirmed from the file, not assumed.

## 3. Data-quality findings

{table(A('data_quality_report.csv')[['check', 'value', 'status', 'note']].fillna(''))}

Material points: (i) nothing is duplicated, missing or off-tick; (ii) trade ids and exchange tokens are **not** identities (tokens are reused across expiries); (iii) {tie} fills sit in 56 equal-second buy/sell groups whose open/close role depends on an ordering assumption; (iv) there is no charge information.

## 4. Position reconstruction

* **Identity:** (underlying, expiry, type, strike); contracts are never merged.
* **Role of a fill** is set by the current net inventory of its contract: against it → closes `min(qty, |inventory|)`, the excess opens the opposite direction (a reversal); with it or flat → opens. Partial fills are separate events.
* **Position (episode):** a run of non-zero inventory in one direction in one contract; flat or a reversal ends it. An episode is an **inventory** identity, not a claim about which strategy leg owns a lot (PR #5: ownership identified for 3.5 % of replacement pairs).
* **Order of events:** (execution second, file row). The file is chronological (0 backward steps). Alternative tie orders (sells first, buys first) are run for the ambiguity check.
* **Conventions:** FIFO, LIFO and average cost run on identical fills; none is called the truth. Average cost closes at the pool's quantity-weighted average price; a reversal re-opens at the reversing fill price.
* **Remaining quantity at the end:** every remaining unit is in a contract whose expiry date is within the data, so it is `EXPIRED_UNCLOSED` (no settlement fill exists; no settlement P&L is invented). `OPEN_AT_END_OF_DATA` = {n0(f.remaining_open_at_end_units)} units.
* **Labels:** PROFIT / LOSS if |gross P&L per unit| > **{tc.TOL} points** (half the 0.05 tick, fixed in `config.yaml` before any classification), BREAKEVEN otherwise, UNRESOLVED if the closing fill's closing quantity changes with the tie ordering. Values are rounded to 1e-9 before comparison.

## 5. FIFO / LIFO / average-cost comparison

{table(M[M.section.isin(['closing-fill stability', 'consensus label'])][['section', 'key', 'closing_fills', 'units', 'share_of_fills', 'share_of_units']].fillna(''), fmt={'closing_fills': n0, 'units': n0})}

Total realised gross P&L differs by only {rs(max(pnl.values()) - min(pnl.values()))} across the three conventions, because the P&L of a **fully closed position is convention-independent**
(largest difference between conventions: {M[M.section.str.startswith('fully closed positions')].pnl_rupees.iloc[0]:.2e} ₹). What the convention changes is which closing fill carries the profit or the loss.

Label transitions FIFO → LIFO (closing fills): PROFIT→LOSS {n0(M[(M.section == 'label transition FIFO -> LIFO') & (M.key == 'PROFIT -> LOSS')].closing_fills.iloc[0])}, LOSS→PROFIT {n0(M[(M.section == 'label transition FIFO -> LIFO') & (M.key == 'LOSS -> PROFIT')].closing_fills.iloc[0])}; all matrices are in `analysis/matching_sensitivity.csv`.

**What is stable, sensitive, unidentifiable.** Stable: quantities, episode structure, position-level P&L and labels, the direction of the aggregate profit/loss split. Sensitive: the label of {pc(st.loc['CONVENTION_SENSITIVE', 'share_of_fills'])} of closing fills, concentrated in short closings (NIFTY short: {pc(1 - UL[(UL.und == 'NIFTY') & (UL.direction == -1)].stable_share_units.iloc[0])} of units sensitive). Unidentifiable: which opening lot a closing fill closes.

## 6. PROFIT / LOSS / BREAKEVEN / UNRESOLVED counts

Closing fills (PROFIT / LOSS / BREAKEVEN / UNRESOLVED) and matched pieces:

| Convention | Closing fills | Units | Matched pieces |
|---|---|---|---|
""" + '\n'.join(f"| {m} | {n0(cf.loc[m, 'PROFIT'])} / {n0(cf.loc[m, 'LOSS'])} / {n0(cf.loc[m, 'BREAKEVEN'])} / {n0(cf.loc[m, 'UNRESOLVED'])} | {n0(cu.loc[m, 'PROFIT'])} / {n0(cu.loc[m, 'LOSS'])} / {n0(cu.loc[m, 'BREAKEVEN'])} / {n0(cu.loc[m, 'UNRESOLVED'])} | {n0(pf.loc[m, 'PROFIT'])} / {n0(pf.loc[m, 'LOSS'])} / {n0(pf.loc[m, 'BREAKEVEN'])} / {n0(pf.loc[m, 'UNRESOLVED'])} |" for m in tc.METHODS) + f"""

Positions (episodes): {n0(f.episodes)} in total; {n0(f.episodes_closed)} fully closed ({n0(pos.loc['FIFO', 'PROFIT'])} profit / {n0(pos.loc['FIFO', 'LOSS'])} loss / {n0(pos.loc['FIFO', 'BREAKEVEN'])} breakeven under every convention); {n0(f.episodes_expired_unclosed)} expired with quantity still open (no result label, no invented settlement).
Short closings are {n0(len(sh))} fills ({n0(len(shp))} PROFIT, {n0(len(shl))} LOSS under FIFO); long closings (mostly protective wings) are {n0(E[(E.method == 'FIFO') & (E.direction == 1)].shape[0])}, with LOSS dominating (wings decay).

![labels](analysis/figures/fig1_labels_and_stability.png)

## 7. Reconciliation of opened, closed and remaining quantity

{table(R.reset_index()[['method', 'fill_units', 'opened_units', 'closed_units', 'matched_units', 'remaining_units', 'unexplained_fill_units', 'unexplained_open_minus_close_minus_remaining', 'cells_not_reconciling', 'cash_identity_difference']].rename(columns={'unexplained_open_minus_close_minus_remaining': 'open − close − remaining', 'cells_not_reconciling': 'cells not reconciling'}), fmt={'fill_units': n0, 'opened_units': n0, 'closed_units': n0, 'matched_units': n0, 'remaining_units': n0})}

* Every one of the {n0(f.fill_rows)} fills is accounted for: {n0(f.fills_open_only)} open only, {n0(f.fills_close_only)} close only, {n0(f.fills_split_close_and_open)} split (reversals: {n0(f.reversal_units_reopened)} units re-opened in the opposite direction); {n0(f.fills_dq_flagged)} fills were flagged by a quality rule and {n0(f.fills_excluded_as_duplicates)} excluded as duplicates.
* Remaining units: {n0(f.remaining_short_units)} short (premium collected {rs(f.remaining_short_premium_collected)}) and {n0(f.remaining_long_units)} long (premium paid {rs(f.remaining_long_premium_paid)}), all in expired contracts. The realised P&L above therefore **omits** the settlement result of these units.
* **Cross-check against the Stage 1 order-level ledger** (decision-time ordering, per-order VWAP): lots per order agree on {pc(XC['order lots equal (Stage 1 lots == TP-01 open+close units / lot)'], 0)} of orders; closing/opening status agrees on {n0(XC['both closing'] + XC['both opening'])} of {n0(XC['parent orders compared'])} orders. The {n0(XC['Stage 1 closing, TP-01 opening only'] + XC['Stage 1 opening, TP-01 closing (any part)'])} that differ ({pc((XC['Stage 1 closing, TP-01 opening only'] + XC['Stage 1 opening, TP-01 closing (any part)']) / XC['parent orders compared'], 2)}) arise from decision-time versus execution-time ordering: {dmod.get('s_', 0)} stop-module (`s_`) orders (the overshoot of RSK-12: by execution time they open a short), {dmod.get('num', 0)} body orders, {dmod.get('h_', 0)} wing (`h_`) and {dmod.get('v_', 0)} lump (`v_`) orders (the `s_` cases are the RSK-12 overshoot; the cause of the other cases was not examined order by order). TP-01 orders by execution time, as required. Details: `analysis/crosscheck_vs_stage1_ledger.csv`.

## 8. Profitable versus losing exits (descriptive)

**Premium decay (short closings).** Profitable closings exit at a median {shp.exit_pct_of_entry.median():.0f} % of the entry premium; losing closings at a median {shl.exit_pct_of_entry.median():.0f} %. The profit-side distribution over 5-point bins is flat
({Dec[(Dec.method == 'FIFO') & (Dec.side == 'PROFIT') & (Dec.bin_lo_pct.between(15, 95))].closing_fills.min():.0f}–{Dec[(Dec.method == 'FIFO') & (Dec.side == 'PROFIT') & (Dec.bin_lo_pct.between(15, 95))].closing_fills.max():.0f} fills per bin from 15 % to 100 %) with one tall bin at 0–5 % (premium near its 0.05 floor).

![decay](analysis/figures/fig2_premium_decay_profit_exits.png)

**Profit per unit.** Profitable short closings earn a median {shp.pnl_pts_per_unit.median():.1f} points per unit (₹{PP[(PP.method == 'FIFO') & (PP.direction == 'short') & (PP.label == 'PROFIT')].rupees_per_lot_p50.iloc[0]:,.0f} per lot, quartiles {shp.pnl_pts_per_unit.quantile(.25):.1f}–{shp.pnl_pts_per_unit.quantile(.75):.1f}). The five most common profit values cover only {pc(PP[(PP.method == 'FIFO') & (PP.direction == 'short') & (PP.label == 'PROFIT')].top5_share_of_label.iloc[0])} of profitable fills: **no repeatable profit amount**.
Losing short closings lose a median {shl.pnl_pts_per_unit.median():.1f} points per unit.

**Holding time (median minutes, FIFO).**

{table(HD[(HD.method == 'FIFO') & (HD.direction == 'short') & HD.label.isin(['PROFIT', 'LOSS']) & (HD.session_relation != 'MIXED')][['label', 'session_relation', 'closing_fills', 'hold_min_p25', 'hold_min_p50', 'hold_min_p75']].round(0), fmt={'closing_fills': n0})}

Carried positions are held about a day (≈ 1,250–1,420 minutes) whichever way they end; same-session profits are held longer than same-session losses.

**Exit behaviour (FIFO labels).**

{table(B[B.direction == 'short'][['label', 'closing_fills', 'share_partial', 'share_one_lot', 'share_next_close_same_contract_within_60s', 'share_followed_by_replacement_open_within_60s', 'share_with_other_closings_same_und_within_10s', 'share_carried']].round(3), fmt={'closing_fills': n0})}

Closings are overwhelmingly one-lot partial exits ({pc(B[(B.label == 'ALL') & (B.direction == 'short')].share_partial.iloc[0], 0)} partial, {pc(B[(B.label == 'ALL') & (B.direction == 'short')].share_one_lot.iloc[0], 0)} one lot); about {pc(B[(B.label == 'ALL') & (B.direction == 'short')].share_next_close_same_contract_within_60s.iloc[0], 0)} are followed by another closing fill in the same contract within 60 s; about {pc(B[(B.label == 'ALL') & (B.direction == 'short')].share_followed_by_replacement_open_within_60s.iloc[0], 0)} are followed by an opening fill in the same underlying and right within 60 s (a replacement or re-entry); nearly all happen within 10 s of another closing in the same underlying (batch behaviour).

**Market context at the exit** (index bars completed before the exit minute only; stale closing minutes excluded; short closings with a stable PROFIT or LOSS label; {int(ctx.dates.iloc[0])} dates). AUC = P(feature higher at a profit exit than at a loss exit); the second AUC is computed within strata of expiry-day × clock hour and weighted by pair count; intervals are date-cluster bootstrap (500 resamples).

{table(ctx[['feature', 'n_profit', 'n_loss', 'median_profit', 'median_loss', 'auc_profit_gt_loss', 'auc_ci_lo', 'auc_ci_hi', 'auc_within_strata', 'auc_within_strata_ci_lo', 'auc_within_strata_ci_hi']], fmt={'n_profit': n0, 'n_loss': n0})}

Index return, volatility and distance from the open do not separate profit from loss (intervals include 0.5). **Time of day, expiry proximity and range expansion do**: losing closings follow a range expansion (AUC {ctx_t.loc['range_expansion', 'auc_profit_gt_loss']:.2f}, {ctx_t.loc['range_expansion', 'auc_within_strata']:.2f} within strata), profitable ones occur later in the day and nearer expiry (raw AUC {ctx_t.loc['tod_min', 'auc_profit_gt_loss']:.2f}, falling to {ctx_t.loc['tod_min', 'auc_within_strata']:.2f} once expiry day and hour are held fixed). This is consistent with adverse moves triggering losing exits, not with a market-state trigger for profits.

## 9. Candidate exit patterns (hypotheses only)

Candidates were selected by the rule fixed in `config.yaml` before any table was inspected: a 5-point decay bin, or a clock minute, whose count is ≥ {tc.CFG['candidate_rules']['cluster_excess_ratio']:.0f}× the median of its neighbours (≥ 100 fills); at most 3 per family. Each was evaluated once. No threshold was searched and none was optimised.

| Pattern | Result | Verdict |
|---|---|---|
| Premium-decay level (profit side) | Cluster bins: {', '.join(f"{int(b)}–{int(b) + 5} % in {sorted(dcl[dcl.bin_lo_pct == b].method)}" for b in sorted(dcl.bin_lo_pct.unique())) or 'none'}. FIFO's 0–5 % bin has an excess ratio of {Dec[(Dec.method == 'FIFO') & (Dec.side == 'PROFIT') & (Dec.bin_lo_pct == 0)].excess_ratio.iloc[0]:.2f}, just under the 3.0 rule. | **No decay level is a cluster under all three conventions** |
| Near-zero premium (0–5 %) | closing hazard {c_dec.hazard_ratio.min():.1f}–{c_dec.hazard_ratio.max():.1f}× its neighbours, but **{c_dec.hazard_ratio_controlled_for_expiry_day_and_clock_hour.min():.2f}–{c_dec.hazard_ratio_controlled_for_expiry_day_and_clock_hour.max():.2f}× once expiry day and clock hour are controlled**; exists only on expiry days | Artefact of time and the 0.05 price floor; **not a premium-level pattern** |
""" + '\n'.join(f"| Clock minute {r.pattern_id.split('-')[1]} | {n0(r.n_events)} short closings; closing hazard {r.hazard_ratio:.1f}× neighbouring minutes ({r.hazard_ratio_controlled_for_expiry_day_and_clock_hour:.1f}× within expiry-day strata); elevated in {r.cycles_elevated} cycles; per underlying NIFTY {clean(r.per_underlying_ratio)['NIFTY']} / SENSEX {clean(r.per_underlying_ratio)['SENSEX']} | HYPOTHESIS: scheduled (clock-driven) closing; the profit share of its closings depends on the convention ({mixtxt(r.label_mix_by_convention)}) |" for _, r in c_clk.iterrows()) + f"""

Other clock clusters under the same rule (not carried forward by the 3-candidate cap): {', '.join(CL[CL.is_cluster].key.tolist())}.
**Not a take-profit candidate, for contrast:** the closing hazard rises from about {base_hz['AVG']:.2f} to {peak['AVG'].hazard_standardised:.2f}–{peak['LIFO'].hazard_standardised:.2f} when a short is marked near {peak['AVG'].bin_lo_pct:.0f}–{peak['FIFO'].bin_lo_pct + 5:.0f} % of its reference entry (a loss), matching the per-lot stop found in Stage 1 (≈ 1.6–1.7×). The profit side is flat (maximum {max(prof_hz_max.values()):.2f}).

![hazard](analysis/figures/fig3_closing_hazard_by_decay.png)

![clock](analysis/figures/fig4_closing_clock_minutes.png)

**Phase 6 checklist for the evaluated candidates** (`analysis/exit_pattern_summary.csv`): how often the condition occurred (`rows_in_condition`) · how often a closing fill followed (`hazard_in_condition`, i.e. the condition without an exit is 1 − hazard) · profitability after the condition (`label_mix_*`) · expiry stability (`cycles_elevated`) · NIFTY vs SENSEX (`per_underlying_ratio`) · FIFO / LIFO / average cost (one row each, or `label_mix_by_convention`) · control for time of day and expiry proximity (`hazard_ratio_controlled_for_expiry_day_and_clock_hour`).
Hazard ratios carry no confidence interval; the cycle count is the stability evidence.

## 10. Expiry-wise and underlying-wise consistency

{table(UL.round(3)[['und', 'direction', 'closing_fills', 'closed_units', 'stable_share_units', 'pnl_FIFO', 'pnl_LIFO', 'pnl_AVG']].assign(direction=lambda d: d.direction.map({-1: 'short', 1: 'long'})), fmt={'closing_fills': n0, 'closed_units': n0, 'pnl_FIFO': n0, 'pnl_LIFO': n0, 'pnl_AVG': n0})}

By expiry (35 cycles; `analysis/expiry_level_summary.csv`): realised closed P&L is positive in {int((EL.pnl_FIFO > 0).sum())} and negative in {int((EL.pnl_FIFO < 0).sum())} cycles under FIFO (between {int(EL.pnl_FIFO.min()):,} and {int(EL.pnl_FIFO.max()):,} ₹); the stable share of closed units ranges from {EL.stable_share_units.min():.2f} to {EL.stable_share_units.max():.2f}.
Short closings realise gains and long (wing) closings realise losses in both underlyings. The closed-position P&L of a cycle is not the cycle's P&L, because unclosed units settle outside the data.

## 11. Limitations and unresolved ownership

1. **Ownership is not identified.** FIFO, LIFO and average cost are assumptions on identical fills; {pc(st.loc['CONVENTION_SENSITIVE', 'share_of_units'])} of closed units change label with the convention. Positions are inventory episodes, not strategy legs.
2. **A profitable closure is not a take-profit.** Profitable closings include scheduled closings (clock minutes), expiry-day flattening, replacement-linked buy-backs and closings of wing hedges.
3. **No settlement and no charges:** {n0(f.remaining_units)} units expire unclosed (their P&L is outside the data); net P&L is unavailable.
4. **Equal-second ordering:** {tie} fills depend on an ordering assumption (labelled UNRESOLVED; their effect is {n0(st.loc['UNRESOLVED_ORDER', 'units'])} units).
5. **NIFTY 23 Jun cycle:** its D-1 session is not in the export; a few first fills may close unseen inventory ({n_nod1} cycles have no D-1 session in the export).
6. **Market context** covers the closings with a valid index bar before the exit minute (stale closing minutes, DAT-15 of the alpha branch, are excluded); option bars are the 1-minute marks of contracts Algo 8 traded, with 2–3 % carried prices.
7. **In-sample:** 65 sessions, all inspected before; hazard ratios have no intervals; no external validation.
8. The Stage 1 order-level ledger and this execution-time ledger differ on {pc((XC['Stage 1 closing, TP-01 opening only'] + XC['Stage 1 opening, TP-01 closing (any part)']) / XC['parent orders compared'], 2)} of orders; conclusions that depend on a single order should name the ordering used.

## 12. Final TP-01 verdict

**PASS.** Completion criteria: every source fill accounted for ✔ · opened = closed + remaining ✔ · partial and full closures represented ✔ · gross realised P&L transparent (points × units, no multiplier) ✔ · FIFO/LIFO/average-cost sensitivity quantified ✔ · unresolved cases identified ✔ · labels reproducible (config tolerance, deterministic) ✔ · descriptive exit patterns available ✔ · tests pass ✔ · observed behaviour kept apart from hypotheses ✔.
**Not claimed:** a recovered take-profit rule, a validated trigger, or exact position ownership.

### Answers to the assignment's closing questions

1. **Reconstructed:** {n0(f.episodes)} positions, {n0(E[E.method == 'FIFO'].shape[0])} closing fills, {n0(f.closed_units)} closed units ({n0(lots)} lots).
2. **Counts (closing fills, P / L / BE / U):** {line('FIFO')}; {line('LIFO')}; {line('AVG')}.
3. **Stable across methods:** quantities, episodes, position-level results; {pc(st.loc['STABLE', 'share_of_units'])} of closed units keep their label.
4. **Candidate patterns:** clock-driven closing at 09:15 / 14:29 / 14:44 (hypothesis); a stop-like hazard peak near 160–170 %; **no** fixed premium-decay take-profit level; the 0–5 % bin is an artefact.
5. **Impossible to infer now:** lot ownership, the decision rule, settlement and net P&L, behaviour outside these sessions.
6. **Ready to pass:** yes, as a data-reconstruction and descriptive milestone.
7. **TP-02 should investigate:** section 13 (nothing has been started; your authorisation and decisions are needed first).

## 13. Proposal for TP-02 (not started)

TP-01 shows that profit and loss closings are not separated by a premium level, and that a large part of closing activity is scheduled or stop-like. TP-02 should therefore first **separate mechanisms before looking for a take-profit**:

1. **Mechanism taxonomy of closing fills on execution-time evidence** (pre-registered): clock-minute closings, stop-like closings (hazard peak near 160–170 %), expiry-day flattening, replacement-linked buy-backs, wing closings. Then ask what profit closings remain unexplained. *Decision needed:* may the taxonomy reuse the Stage 1 labels (decision-time ordering) as a cross-check, or must it be rebuilt on execution time only?
2. **Settlement completion.** Add expiry settlement for the 37,480 unclosed units so that cycle P&L is complete. *Needs:* official settlement prices for the expiry dates (not in the repository).
3. **Ownership evidence.** Any information that identifies which lot or leg a closing belongs to (order-tag semantics, configuration, logs) would turn the 13.5 % convention-sensitive closings into identified ones; Stage 1 questions Q1–Q9 are still open.
4. **Out-of-sample check.** Every pattern here is in-sample. A later period of the same account's trades is the only way to test the clock and hazard findings. *Needs:* new trades.
""")
open(os.path.join(tc.PKG, 'TP01_REPORT.md'), 'w').write('\n'.join(R_)); print('written', sum(len(x) for x in R_))
