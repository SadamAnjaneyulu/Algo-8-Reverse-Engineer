"""M2-B reconciliation on the REAL ledger: lineage counts and identities vs TP-01 / TP-02 reference outputs. Reports every difference; nothing is adjusted to force a match.
python3 portfolio_engine/tools/m2b_reconcile.py -> reports/M2B_RECONCILIATION_REPORT.md, reports/m2b_reconciliation.json"""
import json, os, sys, hashlib
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
import pandas as pd
from pe import tsvio, replay as rp, parents as pa
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators import historical as H
M = 'HISTORICAL_OBSERVED_REPLAY'; TP = os.path.join(REPO, 'tp_reconstruction')
ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, M, 'src'); passed = ls.check(fills)
R = {}; R['source_hashes'] = src; R['events'] = len(fills); R['invariants_passed'] = passed
R['opening_allocations'] = len(ls.oa); R['closing_portions'] = len(ls.cp); R['episodes'] = len(ls.episodes)
tp1 = pd.read_parquet(os.path.join(TP, 'data', 'position_episodes.parquet'))
for m in METHODS:
    e = tp1[tp1.method == m].set_index('episode_id'); mine = ls.runs[m].state.episodes
    R[f'episodes_{m}_ids_equal_tp01'] = set(e.index) == set(mine)
    R[f'episodes_{m}_fields_equal_tp01'] = all(int(mine[k]['opened']) == e.loc[k].opened_units and int(mine[k]['closed']) == e.loc[k].closed_units and mine[k]['direction'] == e.loc[k].direction and mine[k]['ended_by'] == e.loc[k].ended_by for k in mine)
st = ls.runs['FIFO'].state; R['opened_units'] = st.opened; R['closed_units'] = st.closed; R['remaining_units'] = st.opened - st.closed
R['oa_units'] = sum(r[8] for r in ls.oa.values()); R['cp_units'] = sum(r[8] for r in ls.cp.values())
summ = pd.read_csv(os.path.join(TP, 'data', 'reconciliation_summary.csv')).set_index('method')
R['realized_rupees_from_allocations'] = {m: (sum(float(r[7]) for r in ls.ca[m]) if m == 'AVG' else sum(int(r[7]) for r in ls.ca[m])) / 100 for m in METHODS}
R['realized_rupees_tp01'] = {m: float(summ.loc[m].realized_gross_pnl_rupees) for m in METHODS}
tl = pd.read_parquet(os.path.join(TP, 'tp02', 'data', 'exit_event_timelines.parquet'), columns=['close_row', 'qty_closed'])
cp_rows = {int(r[11]): r[8] for r in ls.cp.values()}; tl_rows = dict(zip(tl.close_row.astype(int), tl.qty_closed.astype(int)))
R['tp02_timeline_rows'] = len(tl); R['cp_source_rows_equal_tp02_close_rows'] = set(cp_rows) == set(tl_rows); R['cp_quantities_equal_tp02_qty_closed'] = sum(cp_rows[k] != tl_rows.get(k) for k in cp_rows)
# parents
mixed = ls.mixed_parents(); R['parents_total'] = len(ls.roles); R['parent_roles'] = {k: sum(1 for v in ls.roles.values() if v == k) for k in pa.ROLES}; R['mixed_parents'] = len(mixed)
rev_fill_parents = {r[3] for r in ls.cp.values() if f'OA:{r[2]}' in ls.oa}; R['mixed_parents_with_a_reversal_fill'] = len(set(mixed) & rev_fill_parents); R['mixed_parents_without_reversal'] = len(set(mixed) - rev_fill_parents)
byp = defaultdict(int)
for f in fills: byp[f.parent_order_id] += f.quantity
R['mixed_parent_double_count_check'] = all(sum(r[8] for r in list(ls.oa.values()) + list(ls.cp.values()) if r[3] == p) == byp[p] for p in mixed)
R['mixed_parent_list'] = mixed
# convention sensitivity (descriptive only)
sens = [c for c, v in ls.sensitivity.items() if v == 'CONVENTION_SENSITIVE']; R['closing_portions_convention_sensitive_fifo_vs_lifo'] = len(sens); R['closing_portion_units_convention_sensitive'] = sum(ls.cp[c][8] for c in sens)
R['remaining_slices'] = {m: sum(int(t.split('\t')[5]) for t in ln_lines) for m in ('FIFO', 'LIFO', 'AVG') for ln_lines in [__import__('pe.lineage', fromlist=['x']).slices_tsv(ls.runs[m].state, ls.runs[m].lineage).splitlines()[1:]]}
R['terminal_status_counts'] = pd.Series([l.split('\t')[8] for l in ls.files['FIFO']['episodes.tsv'].splitlines()[1:]]).value_counts().to_dict()
R['observed_layer_hash'] = {m: hashlib.sha256((ls.files[m]['observed_allocations.tsv'] + ls.files[m]['lifecycle.tsv'] + ls.files[m]['episodes.tsv']).encode()).hexdigest()[:16] for m in METHODS}
# tie orders: observed-layer differences confined to ambiguous instruments
amb = set(); base = {}
for tie in TIE_ORDERS:
    r = rp.replay(fills, ins, M, 'FIFO', tie, lineage=True); base[tie] = {(x[0], x[1], x[5], x[8]) for x in r.lineage.observed}
diff = (base['src'] | base['sells_first'] | base['buys_first']) - (base['src'] & base['sells_first'] & base['buys_first']); diff_fills = {x[1].split(':', 1)[1] for x in diff}; R['tie_order_observed_rows_differing'] = len(diff); R['tie_order_fills_differing'] = len(diff_fills)
amb_ref = {f'F{int(v):06d}' for v in pd.read_csv(os.path.join(TP, 'data', 'role_ambiguity_fills.csv')).src_row}; amb_inst = {ins[f.instrument_id].instrument_id for f in fills if f.fill_id in amb_ref}
inst_of = {f.fill_id: f.instrument_id for f in fills}; grp = defaultdict(set)
for f in fills: grp[(f.instrument_id, f.timestamp_s)].add(f.side)
mixed_inst = {k[0] for k, v in grp.items() if len(v) == 2}; diff_inst = {inst_of[x] for x in diff_fills}
R['tie_order_instruments_differing'] = len(diff_inst); R['instruments_with_mixed_side_same_second_fills'] = len(mixed_inst); R['ambiguous_instruments_tp01_close_qty_definition'] = len(amb_inst)
R['tie_order_differences_confined_to_mixed_side_instruments'] = diff_inst <= mixed_inst; R['tie_order_differences_confined_to_tp01_ambiguous_instruments'] = diff_inst <= amb_inst
# parents.tsv
rows = H.generate_parents(REPO, ls.roles); os.makedirs(os.path.join(PE, 'data_generated'), exist_ok=True); pp = os.path.join(PE, 'data_generated', 'parents.tsv'); pa.write_parents(pp, rows); back = pa.read_parents(pp)
R['parents_tsv_rows'] = len(back); R['parents_tsv_missing'] = {c: sum(1 for r in back.values() if r[c] is None) for c in pa.PARENT_COLUMNS if any(r[c] is None for r in back.values())}
R['parents_tsv_conflicts'] = {c: sum(1 for r in rows if r.get(c) == 'CONFLICT') for c in pa.PARENT_COLUMNS if any(r.get(c) == 'CONFLICT' for r in rows)}
R['parent_units_equal_fill_units'] = sum(r['filled_units'] for r in rows) == sum(f.quantity for f in fills)
R['targets'] = dict(opening_allocations=23684, closing_portions=17760, episodes=2667, mixed_parents=26)
R['targets_met'] = dict(opening_allocations=R['opening_allocations'] == 23684, closing_portions=R['closing_portions'] == 17760, episodes=R['episodes'] == 2667, mixed_parents=R['mixed_parents'] == 26, tp02_rows=R['tp02_timeline_rows'] == 17760)
os.makedirs(os.path.join(PE, 'reports'), exist_ok=True); json.dump(R, open(os.path.join(PE, 'reports', 'm2b_reconciliation.json'), 'w'), indent=1, default=str)
print(json.dumps({k: v for k, v in R.items() if k not in ('mixed_parent_list', 'invariants_passed')}, indent=1, default=str)); print('invariants', R['invariants_passed'])
