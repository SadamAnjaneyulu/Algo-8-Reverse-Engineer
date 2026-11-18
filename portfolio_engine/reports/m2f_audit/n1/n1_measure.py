"""N1 measurement (read-only): old GLOBAL keyed sort vs LOCAL (instrument, second) ordering vs atomic-second bucket states, on the full ledger."""
import sys, collections, json
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
from pe.generators import historical as H
from pe import replay as rp
REPO = '/home/user/Algo-8-Reverse-Engineer'
ins, fills, _ = H.generate(REPO)
def orders(policy):
    f2 = H.attach_tie_keys(REPO, fills, policy)
    eo = 'src' if policy == 'source_row' else policy
    local = rp.order_events(f2, eo)
    glob = sorted(f2, key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id)) if policy != 'source_row' else local
    return local, glob
def paths(order):
    inv = collections.defaultdict(int); g = []; inst_seq = collections.defaultdict(list); last = {}
    for f in order:
        inv[f.instrument_id] += f.side * f.quantity; g.append(sum(abs(v) for v in inv.values())); inst_seq[f.instrument_id].append(f.source_row_id)
    # bucket-end aggregate: state after the last fill of each second
    bend = {}; inv2 = collections.defaultdict(int)
    for f in order:
        inv2[f.instrument_id] += f.side * f.quantity; bend[f.timestamp_s] = sum(abs(v) for v in inv2.values())
    return g, inst_seq, bend
base_local, _ = orders('source_row'); gb, sb, bb = paths(base_local)
out = {}
for pol in ('per_contract_id_sequence', 'trade_id', 'order_no', 'sensex_trade_id_time'):
    local, glob = orders(pol)
    gl, sl, bl = paths(local); gg, sg, bg = paths(glob)
    out[pol] = dict(
        fills=len(local),
        per_instrument_sequences_local_equal_global=(sl == sg),
        stream_positions_differing_global_vs_local=sum(1 for a, b in zip(local, glob) if a.source_row_id != b.source_row_id),
        aggregate_gross_states_differing_global_vs_local=sum(1 for a, b in zip(gl, gg) if a != b), max_abs_aggregate_gross_diff_global_vs_local=max(abs(a - b) for a, b in zip(gl, gg)),
        stream_positions_differing_local_vs_baseline=sum(1 for a, b in zip(local, base_local) if a.source_row_id != b.source_row_id),
        aggregate_gross_states_differing_local_vs_baseline=sum(1 for a, b in zip(gl, gb) if a != b),
        bucket_end_aggregate_equal_local_vs_baseline=(bl == bb), bucket_end_aggregate_equal_global_vs_baseline=(bg == bb),
        local_cross_instrument_pattern_equals_baseline=([(f.timestamp_s, f.instrument_id) for f in local] == [(f.timestamp_s, f.instrument_id) for f in base_local]))
    print(pol, out[pol], flush=True)
json.dump(out, open('' + __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'n1_measure_result.json') + '', 'w'), indent=1)
