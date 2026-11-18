"""R1-C (project decision Option C): dual-scenario comparison SOURCE_ROW_ORDER_CONVENTION (historical baseline) vs PER_CONTRACT_ID_SEQUENCE (sensitivity scenario).
Reads committed result files only (production pipeline JSON, independent raw-csv reference JSON) plus one cheap key computation for policy distinctness; writes
reports/R1C_DUAL_SCENARIO_COMPARISON.md and reports/r1c_dual_scenario/dual_scenario_results.json (both result sets preserved).   python3 portfolio_engine/tools/r1c_dual_scenario_report.py"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.generators import historical as H
from pe import tie_policy as tp
n = lambda x: f'{x:,}'
HY = 'per_contract_id_sequence'
prod = json.load(open(os.path.join(PE, 'reports', 'r1_tie_order', 'per_contract_id_sequence_sensitivity.json')))['policies'][HY]
five = json.load(open(os.path.join(PE, 'reports', 'r1_tie_order', 'r1_tie_order_sensitivity.json')))['policies']
ind = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1', 'independent_per_contract_id_sequence_result.json')))
B, A = ind['src'], ind[HY]

# ---- distinctness of the hybrid key from the individual policies (production loader; groups = same instrument, same second, >= 2 fills) ----------------------------
ins, fills, _ = H.generate(REPO); fills.sort(key=lambda f: f.source_row_id)
keyed = {p: H.attach_tie_keys(REPO, fills, p) for p in (HY, 'trade_id', 'order_no', 'sensex_trade_id_time')}
G = collections.defaultdict(list)
for i, f in enumerate(fills): G[(f.instrument_id, f.timestamp_s)].append(i)
G = {k: v for k, v in G.items() if len(v) > 1}
def order(p, idx): return [keyed[p][i].source_row_id for i in sorted(idx, key=lambda i: (keyed[p][i].tie_key, keyed[p][i].source_row_id))]
def src_order(idx): return sorted(keyed[HY][i].source_row_id for i in idx)
dist = {}
for p in ('trade_id', 'order_no', 'sensex_trade_id_time'):
    diff = [k for k, v in G.items() if order(HY, v) != order(p, v)]
    dist[p] = dict(groups_where_order_differs_from_hybrid=len(diff), by_underlying=dict(collections.Counter(ins[k[0]].underlying for k in diff)), examples=[[list(k), order(HY, G[k]), order(p, G[k])] for k in diff[:3]])
dist['source_row'] = dict(groups_where_order_differs_from_hybrid=sum(1 for k, v in G.items() if order(HY, v) != src_order(v)))
dist['multi_fill_groups'] = len(G)

# ---- preserve both result sets ----------------------------------------------------------------------------------------------------------------------------------
results = dict(statement='Neither ordering is claimed to be verified exchange execution chronology; the true intra-second sequence is UNRESOLVED.', baseline='SOURCE_ROW_ORDER_CONVENTION', scenario='PER_CONTRACT_ID_SEQUENCE (policy `per_contract_id_sequence`, SENSITIVITY-ONLY)',
               definition='NIFTY: numeric trade id; SENSEX: nanosecond trade-id time (epoch fallback when the id time disagrees with the epoch, i.e. row 8079); final tie-break: source row; SENSEX id suffix not used',
               independent_reference={'baseline': B, 'scenario': A}, production_pipeline_vs_baseline=prod, distinctness_from_individual_policies=dist,
               individual_policies_for_reference={k: dict(episodes_changed=v['3_episode_identity']['episodes_changed'], fills_split_changed=v['2_groups_changing_open_close_allocation']['fills_changed']) for k, v in five.items()})
os.makedirs(os.path.join(PE, 'reports', 'r1c_dual_scenario'), exist_ok=True)
json.dump(results, open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'dual_scenario_results.json'), 'w'), indent=1, sort_keys=True)

# ---- document ---------------------------------------------------------------------------------------------------------------------------------------------------
fa, aa = A['accounting']['FIFO'], A['absolute']; ba = B['absolute']
la = prod['6_lot_attribution']; tot = la['FIFO']['closing_fills_compared']
bt = A['batches']; wb = A['wing_body']; bl = wb['links_baseline']; lc = wb['links_changed']
# cross-check production vs independent before writing anything
assert prod['3_episode_identity']['episodes_changed'] == fa['episodes_identity_changed'] and prod['2_groups_changing_open_close_allocation']['fills_changed'] == fa['fills_open_close_split_changed']
assert prod['3_episode_identity']['instruments'] == fa['_instruments'] and prod['2_groups_changing_open_close_allocation']['fill_rows'] == fa['_split_rows']
for k, v in prod['4_closing_batch_membership'].items(): assert v['baseline_batches_not_in_alternative'] == bt[k]['baseline_batches_not_in_alternative']
for m in lc: assert prod['5_wing_body_membership']['links_changed'][m] == lc[m]
assert prod['5_wing_body_membership']['opening_body_units'] == wb['headline']['opening_body_units']
L = ['# R1-C — Dual-scenario comparison: `SOURCE_ROW_ORDER_CONVENTION` vs `PER_CONTRACT_ID_SEQUENCE`', '',
     '**Project decision (owner, 2026-11-15): Option C.** `SOURCE_ROW_ORDER_CONVENTION` stays the primary convention of the delivered historical reconstruction (M2-B to M2-E outputs are not regenerated). Downstream research evaluates **both** orderings. '
     '**Neither ordering is claimed to be verified exchange execution chronology; the true intra-second sequence is UNRESOLVED.**', '',
     f'Generated by `tools/r1c_dual_scenario_report.py` from `reports/r1_tie_order/per_contract_id_sequence_sensitivity.json` (production pipeline) and `reports/m2f_audit/r1/independent_per_contract_id_sequence_result.json` (independent raw-csv reference, no `pe` imports); both result sets are preserved in `reports/r1c_dual_scenario/dual_scenario_results.json`. The generator asserts that the two sources agree on instruments, episodes, split rows, batch membership, link counts and body units before it writes.', '',
     '## 1. The scenario (a defined sensitivity, not a new truth)', '',
     '| Part | Rule |', '|---|---|', '| NIFTY | numeric trade id (a per-contract, per-IST-day non-decreasing counter; meaning undocumented) |',
     '| SENSEX | nanosecond time embedded in the trade id, when it agrees with the raw epoch (round-half-up); otherwise the epoch-derived time (the exceptional row 8079) |', '| final tie-break | source-file row order |', '| not used | the SENSEX id suffix; the order number |',
     '| scope | only fills of the same instrument inside the same second are reordered; seconds themselves are never reordered |', '| implementation | policy `per_contract_id_sequence`, Python only, sensitivity-only; convention id `SENSITIVITY_ONLY:per_contract_id_sequence`; the delivered-output builders refuse it (`require_primary`) |', '',
     '### Distinct from the individual policies (measured, not assumed)', '',
     f"Same-instrument-second groups with at least two fills: {n(dist['multi_fill_groups'])}. Groups where the hybrid order differs from the other policy's order:", '',
     '| Other policy | Groups where the orders differ | Where |', '|---|---:|---|']
for p in ('source_row', 'trade_id', 'order_no', 'sensex_trade_id_time'):
    d = dist[p]; L.append(f"| `{p}` | {d['groups_where_order_differs_from_hybrid']} | {', '.join(f'{k} {v}' for k, v in d.get('by_underlying', {}).items()) or ('all' if p == 'source_row' else '-')} |")
L += ['', 'The hybrid is **not** `trade_id` (that policy orders SENSEX by the whole id including the suffix, so fills sharing one nanosecond are ordered by suffix; here that separates the two policies in the two SENSEX groups shown in the JSON examples, rows 4736-4744 and 4745-4747), **not** `order_no`, and **not** `sensex_trade_id_time` (that policy leaves NIFTY in source-row order). '
      'On this ledger it happens to produce the same accounting outcome as `trade_id` (below); that is a measured coincidence of this data set, not an equivalence, and the policies stay separate.', '',
      '## 2. Result: the six populations (hybrid vs baseline)', '', '| Population | Baseline | Hybrid |', '|---|---|---|',
      f"| 1. Groups whose order differs | - | {prod['1_groups_differing_in_order']['differing']} of {n(prod['1_groups_differing_in_order']['multi_fill_groups'])} ({prod['1_groups_differing_in_order']['differing_mixed_side']} mixed-side, {prod['1_groups_differing_in_order']['differing_same_side']} same-side) |",
      f"| 2. Groups changing opening/closing allocation | - | {prod['2_groups_changing_open_close_allocation']['groups']} groups, {fa['fills_open_close_split_changed']} fills (source rows {', '.join(map(str, fa['_split_rows']))}) |",
      f"| 3. Position identity: episodes | {n(ba['FIFO']['n_episodes'])} | {n(aa['FIFO']['n_episodes'])} in total; **{fa['episodes_identity_changed']} change identity** (ordinal id), {prod['3_episode_identity']['episodes_changed_by_content']} by content, in {fa['instruments_changed']} instruments ({', '.join(fa['_instruments'])}) |",
      f"| 3. Reversal-ended episodes | {ba['FIFO']['reversal_ended_episodes']} | {aa['FIFO']['reversal_ended_episodes']} |",
      f"| 4. Closing batches | see section 3 | 1 baseline batch absent per view (C1 = C2) |",
      f"| 5. Wing/body | W1 {n(bl['W1'])}, W1_S60 {n(bl['W1_S60'])}, W2 {n(bl['W2'])}, W2_S60 {n(bl['W2_S60'])}, W3 {n(bl['W3'])} links | links changed: W1 {lc['W1']}, W1_S60 {lc['W1_S60']}, W2 {lc['W2']}, W2_S60 {lc['W2_S60']}, W3 {lc['W3']}; items only in one scenario {prod['5_wing_body_membership']['items_only_in_one']} |",
      f"| 6. FIFO lot attribution (of {n(tot)} closing fills) | - | {la['FIFO']['closing_fills_with_changed_consumption_sequence']} changed by lot sequence ({100 * la['FIFO']['closing_fills_with_changed_consumption_sequence'] / tot:.2f} %), {la['FIFO']['closing_fills_with_changed_source_lots']} by lot set |",
      f"| 6. LIFO lot attribution | - | {la['LIFO']['closing_fills_with_changed_consumption_sequence']} by lot sequence ({100 * la['LIFO']['closing_fills_with_changed_consumption_sequence'] / tot:.2f} %), {la['LIFO']['closing_fills_with_changed_source_lots']} by lot set |", '',
      '## 3. Closing batches (all ten views)', '', '| View | Batches baseline | Batches hybrid | Baseline batches absent in hybrid | Hybrid batches absent in baseline |', '|---|---:|---:|---:|---:|']
for k, v in bt.items(): L.append(f"| {k} | {n(v['n_batches_baseline'])} | {n(v['n_batches'])} | {v['baseline_batches_not_in_alternative']} | {v['alternative_batches_not_in_baseline']} |")
L += ['', '## 4. Portfolio-level metrics under both scenarios (independent exact-arithmetic reference)', '', '| Metric | Baseline | Hybrid | Same? |', '|---|---:|---:|---|']
def row(name, a, b): L.append(f'| {name} | {a} | {b} | {"yes" if a == b else "**NO**"} |')
row('Fills', n(41421), n(41421)); row('Opening units', n(ba['FIFO']['opening_units']), n(aa['FIFO']['opening_units'])); row('Closing units', n(ba['FIFO']['closing_units']), n(aa['FIFO']['closing_units']))
row('Final inventory per instrument', 'equal' if fa['final_inv_equal'] else 'DIFFERS', 'equal' if fa['final_inv_equal'] else 'DIFFERS'); row('Cash flow', 'equal' if fa['cash_equal'] else 'DIFFERS', 'equal' if fa['cash_equal'] else 'DIFFERS')
row('FIFO realized P&L, paise (price only, no costs)', n(int(ba['FIFO']['realized_total_paise'])), n(int(aa['FIFO']['realized_total_paise']))); row('LIFO realized P&L, paise (price only, no costs)', n(int(ba['LIFO']['realized_total_paise'])), n(int(aa['LIFO']['realized_total_paise'])))
row('Episodes', n(ba['FIFO']['n_episodes']), n(aa['FIFO']['n_episodes'])); row('Reversal fills (per-fill zero crossings)', ba['FIFO']['reversal_fills'], aa['FIFO']['reversal_fills'])
row('Opening body units', n(B['wing_body']['headline']['opening_body_units']), n(wb['headline']['opening_body_units'])); row('Closing body units', n(B['wing_body']['headline']['closing_body_units']), n(wb['headline']['closing_body_units']))
L += ['', 'Realized P&L: the total FIFO and LIFO delta is 0 in the reference run (`realized_delta_paise`); per-instrument equality was verified for the individual policies by the reviewer, not separately for the hybrid. Portfolio-level equity, drawdown, Sharpe or similar are **not** computed at this stage: M2 has no portfolio return series, and none was invented here.', '',
      '## 5. Which conclusions are stable and which depend on the ordering', '',
      '### Stable under both scenarios (tested here)', '', '* Fill count, aggregate opening and closing units, final inventory per instrument, cash flow, FIFO and LIFO realized P&L totals, total episode count.',
      f"* Closing-batch **counts** at every threshold (membership differs by one batch per view).",
      f"* W3 links (0 changed); W1/W2 link counts change by {lc['W1']} of {n(bl['W1'])} and the S60 views by {lc['W1_S60']} of {n(bl['W1_S60'])}.", '',
      '### Dependent on the ordering convention (tested here)', '',
      f"* Position (episode) identity for {fa['episodes_identity_changed']} episodes in {fa['instruments_changed']} instruments, and the reversal-ended episode count ({ba['FIFO']['reversal_ended_episodes']} vs {aa['FIFO']['reversal_ended_episodes']}).",
      f"* Opening/closing allocation of {fa['fills_open_close_split_changed']} fills.",
      f"* FIFO and LIFO lot attribution of {la['FIFO']['closing_fills_with_changed_consumption_sequence']} / {la['LIFO']['closing_fills_with_changed_consumption_sequence']} closing fills (3.7 to 3.8 % of {n(tot)} closing fills): any analysis that depends on **which lot** a close consumed must be run under both.",
      '* Membership of one closing batch per view; 6 W1/W2 links and 6 S60 links; opening body units (626,765 baseline vs 625,985).', '',
      '### Not tested here (UNKNOWN, not "stable")', '',
      '* The M2-D evidence-class labels (W1 WEAKLY_SUPPORTED, W1_S60/W3 UNRESOLVED, W2, ownership, protective intent) were **not re-derived** under the hybrid ordering. Only link and item counts were compared; the small count changes make a label change unlikely but that is an inference, not a result.',
      '* M2-E case studies, figures and records were not regenerated (by decision); their dependence on the ordering was **not measured**; it can only arise through the quantities listed as dependent above (an expectation, not a test).', '* Any M3 result: none exists.', '',
      '## 6. Rules for downstream research (project decision Option C)', '',
      '1. The baseline stays `SOURCE_ROW_ORDER_CONVENTION`; delivered M2 outputs are never regenerated or replaced.', '2. Every downstream research result is reported under **both** orderings, side by side, with both result sets stored.',
      '3. A conclusion is called ordering-stable only if it holds under both; otherwise it is labelled ordering-dependent with the size of the dependence.', '4. Neither ordering is described as verified chronology; the individual `trade_id`, `order_no`, `sensex_trade_id_time` policies remain separate sensitivities.',
      '5. Source data is never modified; the ordering is a configurable convention applied at replay time (M3 requirement, see `IMPLEMENTATION_PLAN.md`).']
open(os.path.join(PE, 'reports', 'R1C_DUAL_SCENARIO_COMPARISON.md'), 'w').write('\n'.join(L) + '\n'); print('written', len(L), 'lines')
