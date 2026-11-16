"""Item 1f: reproduce the N1 measurement (old global keyed sort vs local ordering) for per_contract_id_sequence with my own code."""
import json
import rawload as R
rows = R.load(); local = R.order_hybrid(rows); old = sorted(rows, key=lambda r: (r['ts'], R.hybrid_key(r), r['row']))
pos = sum(1 for a, b in zip(local, old) if a['row'] != b['row'])


def gross_path(order):
    inv = {}; g = 0; out = []
    for f in order:
        i = inv.get(f['inst'], 0); j = i + f['side'] * f['qty']; inv[f['inst']] = j; g += abs(j) - abs(i); out.append(g)
    return out


a, b = gross_path(local), gross_path(old); d = [abs(x - y) for x, y in zip(a, b)]
base = gross_path(R.order_baseline(rows)); dl = [abs(x - y) for x, y in zip(a, base)]
sec_end_equal = all(x == y for x, y, f, nxt in zip(a, b, local, local[1:] + [None]) if nxt is None or nxt['ts'] != f['ts'])
res = dict(positions_differ_old_vs_local=pos, intermediate_gross_states_differ=sum(1 for x in d if x), max_diff_units=max(d), second_end_gross_equal=sec_end_equal,
           local_vs_baseline_positions=sum(1 for x, y in zip(local, R.order_baseline(rows)) if x['row'] != y['row']), local_vs_baseline_gross_states_differ=sum(1 for x in dl if x))
print(res); json.dump(res, open('item1f_n1_measure_result.json', 'w'), indent=1)
