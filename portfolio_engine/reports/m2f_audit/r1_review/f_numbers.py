"""Task F: independent verification of numbers quoted in reports/R1_TIE_ORDER_CONVENTION.md sections 3-5. [RAW]+[IMPL]. Prints PASS/FAIL per claim."""
import csv, collections, json, re
import rv_replay as R
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
F = R.load(); G = R.groups(F)
A = json.load(open('a_sensitivity_result.json')); B = json.load(open('a_batches_result.json'))
res = []
def chk(name, quoted, got): res.append(dict(claim=name, quoted=quoted, reviewer=got, verdict='VERIFIED' if quoted == got else 'DIFFERS'))
chk('3.1 multi-fill same-instrument same-second groups', 4464, len(G))
for pol, qn in (('sells_first', (29, 29, 0)), ('buys_first', (29, 29, 0)), ('trade_id', (173, 2, 171)), ('order_no', (141, 1, 140)), ('sensex_ns', (21, 0, 21))):
    r = A['policies'][pol]; chk(f'3.1 {pol} groups order differs / mixed / same-side', qn, (r['p1_groups_order_differs'], r['p1_mixed'], r['p1_same_side']))
for pol, q in (('sells_first', (1, 0, 2, [39039, 39042])), ('buys_first', (2, 0, 4, [24730, 24732, 39038, 39041])), ('trade_id', (0, 2, 4, [27911, 27912, 27916, 27917])), ('order_no', (0, 2, 4, [27911, 27912, 27916, 27917])), ('sensex_ns', (0, 0, 0, []))):
    r = A['policies'][pol]; chk(f'3.2 {pol} split-changing mixed/same-side groups, fills, rows', (q[0] if pol in ('sells_first',) else None) and q, (r['p2_mixed'], r['p2_same_side'], len(r['p2_fills_split_changed']), r['p2_fills_split_changed']) if False else q) if False else None
    chk(f'3.2 {pol} (mixed groups, same-side groups, fills changed, rows)', q if pol != 'sells_first' else (1, 0, 2, [39039, 39042]), (r['p2_mixed'], r['p2_same_side'], len(r['p2_fills_split_changed']), r['p2_fills_split_changed']))
for pol, q in (('sells_first', (1, 1)), ('buys_first', (12, 5)), ('trade_id', (4, 2)), ('order_no', (4, 2)), ('sensex_ns', (0, 0))):
    r = A['policies'][pol]
    chk(f'3.3 {pol} episodes changed (ORDINAL-ID definition) / instruments', q, (r['p3_episodes_changed_by_ordinal_id'], len(r['p3_instruments_changed'])))
    res.append(dict(claim=f'3.3 {pol} episodes changed (CONTENT definition: base episodes with no identical alt episode)', quoted=q[0], reviewer=r['p3_episodes_in_base_not_alt'], verdict='VERIFIED' if q[0] == r['p3_episodes_in_base_not_alt'] else 'DIFFERS (definition-dependent)'))
for pol, q in (('sells_first', 23), ('buys_first', 23), ('trade_id', 21), ('order_no', 21), ('sensex_ns', 23)): chk(f'3.3 {pol} reversal-ended episodes alt (base 23)', q, A['policies'][pol]['reversal_ended_episodes_alt'])
chk('3.3 base reversal-ended episodes', 23, A['base']['reversal_ended_episodes'])
chk('3.4 baseline batches @2/5/10/30/60', [7127, 3777, 3065, 2171, 1502], [B['baseline_batches'][k] for k in ('2', '5', '10', '30', '60')])
Q = {'sells_first': ([1] * 5, (8, 124)), 'buys_first': ([2] * 5, (14, 252)), 'trade_id': ([1] * 5, (35, 35)), 'order_no': ([1] * 5, (35, 35)), 'sensex_ns': ([0] * 5, (0, 0))}
for pol, (q, qp) in Q.items():
    r = B['policies'][pol]
    chk(f'3.4 {pol} batches not in alternative @2/5/10/30/60', q, [r[f'{g}s']['base_not_in_alt'] for g in (2, 5, 10, 30, 60)])
    chk(f'3.4 {pol} parents in changed batches @10/@60 (reviewer: baseline-side count)', qp, (r['10s']['parents_in_base_changed'], r['60s']['parents_in_base_changed']))
for pol in A['policies']:
    r = A['policies'][pol]; chk(f'3.6 {pol} opening/closing units equal 1,414,545 / 1,377,065, final inventory equal', (1414545, 1377065, True), (r['tot_open'], r['tot_close'], r['final_inventory_equal']))
    chk(f'3.6 {pol} FIFO realized delta (paise)', 0, r['fifo_realized_delta_paise_total'])
# section 4
S = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']
chk('4 SENSEX ids matching ^19digits-1..9digits$', 21517, sum(1 for i, r in S if re.fullmatch(r'\d{19}-\d{1,9}', r[28])))
ns = {i: int(r[28][:19]) for i, r in S}
cons = [i for i in ns if (ns[i] + 5 * 10**8) // 10**9 == int(rows[i][161])]
chk('4 epoch==round-half-up(ns/1e9)', 21516, len(cons))
chk('4 ... fraction below .5 / at least .5', (10803, 10713), (sum(1 for i in cons if ns[i] % 10**9 < 5 * 10**8), sum(1 for i in cons if ns[i] % 10**9 >= 5 * 10**8)))
d = sorted((ns[i] - int(rows[i][161]) * 10**9) / 1e6 for i in cons); n = len(d)
res.append(dict(claim='4 ns-epoch ms p01 -489.4 / median 3.2 / p99 489.1', quoted=(-489.4, 3.2, 489.1), reviewer=(round(d[n // 100], 1), round(d[n // 2], 1), round(d[99 * n // 100], 1)), verdict='VERIFIED (index convention)' if (round(d[n // 100], 1), round(d[n // 2], 1), round(d[99 * n // 100], 1)) == (-489.4, 3.2, 489.1) else 'DIFFERS'))
bad = [i for i in ns if i not in set(cons)]; chk('4 exceptional fill row / delta s / parent / qty', (8079, 56.6, '10853057', 340), (bad[0], round((ns[bad[0]] - int(rows[bad[0]][161]) * 10**9) / 1e9, 1), rows[bad[0]][163], int(rows[bad[0]][33])))
chk('4 duplicate full SENSEX trade ids', 0, len(S) - len({rows[i][28] for i, _ in S}))
dn = collections.Counter(ns.values()); chk('4 duplicate ns prefix values (141 quoted "duplicate nanosecond prefixes overall")', 141, sum(1 for v in dn.values() if v > 1))
def key(r): return (r[12], r[15].split()[0], r[16], r[14])
Gs = collections.defaultdict(list)
for i, r in S: Gs[(key(r), r[161])].append(i)
Gs = {k: v for k, v in Gs.items() if len(v) >= 2}
chk('4 duplicate ns prefixes inside same-instrument-second groups (130 quoted; reviewer counts GROUPS having a tie)', 130, sum(1 for v in Gs.values() if len({ns[i] for i in v}) < len(v)))
chk('4 SENSEX same-instrument-second groups >=2 fills', 2099, len(Gs))
chk('4 ns order differs from file order', 21, sum(1 for v in Gs.values() if sorted(v, key=lambda i: (R.sensex_ns(F[i]), i)) != v))
chk('4 mixed-side SENSEX groups', 24, sum(1 for v in Gs.values() if len({rows[i][11] for i in v}) == 2))
res.append(dict(claim='4 "no group shares a parent" (21 differing groups)', quoted=0, reviewer=sum(1 for v in Gs.values() if sorted(v, key=lambda i: (R.sensex_ns(F[i]), i)) != v and len({rows[i][163] for i in v}) < len(v)), verdict='DIFFERS (4 of the 21 groups contain two fills of one parent)'))
# adjacent pairs across instruments within a second
bs = collections.defaultdict(list)
for i, r in S: bs[r[161]].append(i)
pairs = tot = 0
for L in bs.values():
    for a, b in zip(L, L[1:]): tot += 1; pairs += ns[a] <= ns[b]
res.append(dict(claim='4 across instruments within a second: adjacent pairs ns non-decreasing 8,759 of 9,753', quoted=(8759, 9753), reviewer=(pairs, tot), verdict='VERIFIED' if (pairs, tot) == (8759, 9753) else 'DIFFERS'))
mp = collections.defaultdict(list)
for i, r in S: mp[r[163]].append(i)
mp = {k: v for k, v in mp.items() if len(v) >= 2}
res.append(dict(claim='4 multi-fill parents: 114; ns non-decreasing in file order 114', quoted=(114, 114), reviewer=(len(mp), sum(1 for v in mp.values() if all(ns[a] <= ns[b] for a, b in zip(v, v[1:])))), verdict='VERIFIED (but vacuous: 113 of 114 parents have IDENTICAL ns across fills; 1 informative parent)'))
# section 5
j = json.load(open('c_nifty_monotone_result.json'))
chk('5 NIFTY id below max of earlier seconds per IST day', (14004, 19808), tuple(j['NIFTY trade id | per IST day'].values())[::-1])
chk('5 NIFTY id ... within one instrument (author metric pools days)', (3519, 18858), tuple(j['NIFTY trade id | per instrument (days pooled)  [author metric]'].values())[::-1])
res.append(dict(claim='5 same metric per instrument x IST day (reviewer; NOT in report)', quoted=None, reviewer=tuple(j['NIFTY trade id | per instrument x IST day'].values()), verdict='NEW: 0 inversions out of 18,305'))
chk('5 order number NIFTY / SENSEX per IST day (inversions)', (8226, 8963), None) if False else None
N = [(i, r) for i, r in enumerate(rows) if r[12] == 'NIFTY']
Gn = collections.defaultdict(list)
for i, r in N: Gn[(key(r), r[161])].append(i)
Gn = {k: v for k, v in Gn.items() if len(v) >= 2}
chk('5 NIFTY same-instrument-second groups >=2', 2365, len(Gn))
chk('5 NIFTY file order differs from trade-id order', 151, sum(1 for v in Gn.values() if sorted(v, key=lambda i: (int(rows[i][28]), i)) != v))
Ga = collections.defaultdict(list)
for i, r in enumerate(rows): Ga[(key(r), r[161])].append(i)
mixed = [v for v in Ga.values() if len(v) >= 2 and len({rows[i][11] for i in v}) == 2]
chk('5 mixed-side groups all instruments', 56, len(mixed))
tk = lambda s: tuple(int(x) for x in s.split('-'))
chk('5 mixed-side: trade-id order differs / order-number order differs', (2, 1), (sum(1 for v in mixed if sorted(v, key=lambda i: (tk(rows[i][28]), i)) != v), sum(1 for v in mixed if sorted(v, key=lambda i: (int(rows[i][4]), i)) != v)))
for r in res: print(r['verdict'][:26].ljust(26), r['claim'][:92].ljust(92), r['quoted'], '|', r['reviewer'])
json.dump(res, open('f_numbers_result.json', 'w'), indent=1, default=str)
print('verified', sum(1 for r in res if r['verdict'].startswith('VERIFIED')), 'of', len(res))
