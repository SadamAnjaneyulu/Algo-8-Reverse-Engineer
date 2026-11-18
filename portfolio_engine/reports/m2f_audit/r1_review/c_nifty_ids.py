"""Task C: strength of NIFTY trade-id / order-number inversions vs file order; same-parent constraints; same-side flip groups. [RAW]"""
import csv, collections, json, datetime
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
def inst(r): return (r[12], r[15].split()[0], r[16], r[14])
def day(r): return (int(r[161]) + 19800) // 86400
out = {}
N = [(i, r) for i, r in enumerate(rows) if r[12] == 'NIFTY']
# per (day, instrument) sequences in file order; adjacent pairs: cross-second vs same-second; id and order number
for name, col in (('trade_id', 28), ('order_no', 4)):
    S = collections.defaultdict(list)
    for i, r in N: S[(day(r), inst(r))].append(i)
    cs = cs_inv = ss = ss_inv = ss_eq = cs_eq = 0
    for L in S.values():
        for a, b in zip(L, L[1:]):
            va, vb = int(rows[a][col]), int(rows[b][col])
            if rows[a][161] == rows[b][161]:
                ss += 1; ss_inv += vb < va; ss_eq += vb == va
            else:
                cs += 1; cs_inv += vb < va; cs_eq += vb == va
    out[f'NIFTY_{name}_adjacent_pairs_same_instrument_same_day'] = dict(cross_second_pairs=cs, cross_second_decreases=cs_inv, cross_second_rate=cs_inv / cs, same_second_pairs=ss, same_second_decreases=ss_inv, same_second_rate=ss_inv / ss, same_second_equal=ss_eq, cross_second_equal=cs_eq)
# SENSEX order number the same
S = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']; G = collections.defaultdict(list)
for i, r in S: G[(day(r), inst(r))].append(i)
cs = ci = ss = si = 0
for L in G.values():
    for a, b in zip(L, L[1:]):
        va, vb = int(rows[a][4]), int(rows[b][4])
        if rows[a][161] == rows[b][161]: ss += 1; si += vb < va
        else: cs += 1; ci += vb < va
out['SENSEX_order_no_adjacent_pairs'] = dict(cross_second_pairs=cs, cross_second_decreases=ci, same_second_pairs=ss, same_second_decreases=si)
# NIFTY trade id vs parent partial fills: is the NIFTY trade id increasing within a parent (consistent with sequence)?
P = collections.defaultdict(list)
for i, r in N: P[r[163]].append(i)
mp = {k: v for k, v in P.items() if len(v) >= 2}
out['NIFTY_multi_fill_parents'] = len(mp)
out['NIFTY_parents_trade_id_not_increasing_in_remaining_qty_sequence'] = sum(1 for v in mp.values() if any(int(rows[b][28]) < int(rows[a][28]) for a, b in zip(sorted(v, key=lambda i: -int(rows[i][20])), sorted(v, key=lambda i: -int(rows[i][20]))[1:])))
out['NIFTY_parents_trade_id_not_increasing_in_file_order'] = sum(1 for v in mp.values() if any(int(rows[b][28]) < int(rows[a][28]) for a, b in zip(v, v[1:])))
# NIFTY: same-parent same-second pairs: id order vs file order
same_par = [(v) for v in mp.values()]
c = collections.Counter()
for v in same_par:
    for a, b in zip(v, v[1:]):
        if rows[a][161] == rows[b][161]:
            c['same_parent_same_second_pairs'] += 1
            c['  trade_id decreases'] += int(rows[b][28]) < int(rows[a][28])
            c['  remaining_qty NOT decreasing (file order contradicts partial-fill sequence)'] += int(rows[b][20]) >= int(rows[a][20])
out['NIFTY_same_parent_same_second_pairs'] = dict(c)
# the two same-side flip groups: dump raw details
def dump(rs):
    return [dict(row=i, side=rows[i][11], qty=int(rows[i][33]), px=rows[i][137], tid=rows[i][28], ono=rows[i][4], pid=rows[i][163], status=rows[i][27], rem=rows[i][20], ep=rows[i][161], c23=rows[i][23], modtype=rows[i][22], tag=rows[i][163][:2]) for i in rs]
out['flip_groups'] = {'CE24600': dump([27908, 27911, 27917]), 'PE23200': dump([27906, 27912, 27916])}
# context: preceding fills of those instruments that day
for nm, rr in (('CE24600', [27908]), ('PE23200', [27906])):
    k = inst(rows[rr[0]]); ctx = [i for i, r in enumerate(rows) if inst(r) == k and abs(int(r[161]) - int(rows[rr[0]][161])) < 600]
    out['context_' + nm] = dump(ctx)
json.dump(out, open('c_nifty_ids_result.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if not k.startswith(('flip', 'context'))}, indent=1))
for k in ('flip_groups', 'context_CE24600', 'context_PE23200'):
    print(k)
    v = out[k]
    for x in (v if isinstance(v, list) else [y for z in v.values() for y in z]): print('  ', x)
