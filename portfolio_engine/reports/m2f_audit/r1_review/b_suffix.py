"""Task B: suffix behaviour of SENSEX trade ids '<ns>-<suffix>'; duplicates/collisions; ordering consistency in same-instrument-same-second groups. [RAW]"""
import csv, datetime, collections, json, statistics
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
S = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']
def key(r): return (r[12], r[15][:r[15].index(' ')], r[16], r[14])
out = {}
import re
pat = re.compile(r'^(\d{19})-(\d{1,9})$')
out['sensex_rows'] = len(S); out['id_pattern_ok'] = sum(1 for i, r in S if pat.match(r[28]))
out['nifty_ids_with_dash'] = sum(1 for r in rows if r[12] == 'NIFTY' and '-' in r[28]); out['nifty_ids_all_digits'] = sum(1 for r in rows if r[12] == 'NIFTY' and r[28].isdigit())
ns = {i: int(r[28][:19]) for i, r in S}; suf = {i: int(r[28].split('-')[1]) for i, r in S}; ep = {i: int(r[161]) for i, r in S}
# relation to epoch: floor vs round
fl = sum(1 for i in ns if ns[i] // 10**9 == ep[i]); rd = sum(1 for i in ns if (ns[i] + 500_000_000) // 10**9 == ep[i]); ce = sum(1 for i in ns if -(-ns[i] // 10**9) == ep[i])
out['epoch==floor(ns/1e9)'] = fl; out['epoch==round_half_up(ns/1e9)'] = rd; out['epoch==ceil(ns/1e9)'] = ce
d = [(ns[i] - ep[i] * 10**9) / 1e6 for i in ns if (ns[i] + 500_000_000) // 10**9 == ep[i]]  # ms
d.sort(); n = len(d)
out['ns_minus_epoch_ms_consistent_rows'] = dict(n=n, min=d[0], p01=d[n // 100], median=d[n // 2], p99=d[99 * n // 100], max=d[-1], frac_negative=sum(1 for x in d if x < 0) / n)
bad = [i for i in ns if (ns[i] + 500_000_000) // 10**9 != ep[i]]; out['inconsistent_rows'] = bad; out['inconsistent_diff_s'] = [(ns[i] - ep[i] * 10**9) / 1e9 for i in bad]
# uniformity check of the fractional part (rounding => epoch-ns uniform on [-500,500) ms; floor => [0,1000))
frac = [(ns[i] % 10**9) / 1e9 for i in ns]; out['fractional_second_deciles'] = [sum(1 for f in frac if k / 10 <= f < (k + 1) / 10) for k in range(10)]
# duplicates
dup_full = collections.Counter(r[28] for i, r in S); out['duplicate_full_ids'] = sum(1 for v in dup_full.values() if v > 1)
dup_ns = collections.defaultdict(list)
for i in ns: dup_ns[ns[i]].append(i)
dn = {k: v for k, v in dup_ns.items() if len(v) > 1}; out['duplicate_ns_prefix_values'] = len(dn); out['rows_in_duplicate_ns_prefix'] = sum(len(v) for v in dn.values())
out['dup_ns_same_parent'] = sum(1 for v in dn.values() if len({rows[i][163] for i in v}) == 1)
out['dup_ns_same_instrument'] = sum(1 for v in dn.values() if len({key(rows[i]) for i in v}) == 1)
out['dup_ns_same_instrument_and_parent'] = sum(1 for v in dn.values() if len({(key(rows[i]), rows[i][163]) for i in v}) == 1)
out['dup_ns_different_parent_same_instrument'] = sum(1 for v in dn.values() if len({key(rows[i]) for i in v}) == 1 and len({rows[i][163] for i in v}) > 1)
out['dup_ns_different_instrument'] = sum(1 for v in dn.values() if len({key(rows[i]) for i in v}) > 1)
# suffix monotonic with ns? per-day, per-instrument, global
def inv(groupfn, label):
    G = collections.defaultdict(list)
    for i in ns: G[groupfn(i)].append(i)
    tot = bad = ties = 0
    for g, L in G.items():
        L = sorted(L, key=lambda i: (ns[i], i))
        for a, b in zip(L, L[1:]):
            if ns[a] == ns[b]: ties += 1; continue
            tot += 1; bad += suf[b] < suf[a]
    out[f'suffix_decreases_when_ns_increases[{label}]'] = dict(adjacent_pairs=tot, decreases=bad, equal_ns_pairs_skipped=ties, groups=len(G))
def day(i): return (ep[i] + 19800) // 86400
inv(lambda i: 0, 'global'); inv(day, 'per IST day'); inv(lambda i: (day(i), key(rows[i])), 'per IST day x instrument'); inv(lambda i: key(rows[i]), 'per instrument (all days)')
# suffix granularity
out['suffix_mod10_eq0'] = sum(1 for i in suf if suf[i] % 10 == 0); out['suffix_mod2_eq0'] = sum(1 for i in suf if suf[i] % 2 == 0)
# within same instrument-second groups with >=2 fills: ns vs suffix vs file order
G = collections.defaultdict(list)
for i in ns: G[(key(rows[i]), ep[i])].append(i)
G = {k: v for k, v in G.items() if len(v) >= 2}
out['same_instrument_second_groups_ge2'] = len(G)
cnt = collections.Counter(); det = []
for k, v in G.items():
    ords_ns = sorted(v, key=lambda i: (ns[i], i)); ords_suf = sorted(v, key=lambda i: (suf[i], i))
    distinct_ns = len({ns[i] for i in v}) == len(v)
    cnt['groups_all_ns_distinct'] += distinct_ns
    ns_differs_file = ords_ns != v
    if ns_differs_file:
        cnt['ns_order_differs_from_file'] += 1
        cnt['  ...of which suffix order == ns order'] += (ords_suf == ords_ns)
        cnt['  ...of which suffix order == file order'] += (ords_suf == v)
        det.append(dict(key=k[0], ep=k[1], rows=v, sides=''.join(rows[i][11][0] for i in v), ns_order=ords_ns, suffix_order=ords_suf, ns=[ns[i] % 10**9 for i in v], suf=[suf[i] for i in v], ids=[rows[i][28] for i in v]))
    else:
        cnt['ns_order_equals_file'] += 1
        cnt['  ...suffix order == file order'] += (ords_suf == v)
    cnt['groups_with_tied_ns'] += (len({ns[i] for i in v}) < len(v))
    cnt['mixed_side'] += (len({rows[i][11] for i in v}) == 2)
    cnt['mixed_side_ns_differs'] += (ns_differs_file and len({rows[i][11] for i in v}) == 2)
out['group_counts'] = dict(cnt); out['ns_vs_file_differing_groups'] = det
# groups whose suffix order disagrees with ns order when both are strictly informative
dis = 0; disl = []
for k, v in G.items():
    if len({ns[i] for i in v}) == len(v) and len({suf[i] for i in v}) == len(v):
        a = sorted(v, key=lambda i: ns[i]); b = sorted(v, key=lambda i: suf[i])
        if a != b: dis += 1; disl.append((k, v))
out['groups_distinct_ns_and_suffix_where_ns_order_ne_suffix_order'] = dis
json.dump(out, open('b_suffix_result.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'ns_vs_file_differing_groups'}, indent=1))
