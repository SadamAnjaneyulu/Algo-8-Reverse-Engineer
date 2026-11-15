"""R1.2: separate validation of the SENSEX trade-id timestamp hypothesis. Classification of everything here: [RAW] (raw csv, csv module only) + [IMPL] (independent M2-F references, no pe imports).
python3 sensex_tid_investigation.py <out.json>"""
import sys, csv, json, re, collections
sys.dont_write_bytecode = True
M = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/'
for t in ('track_a', 'track_b', 'track_c'): sys.path.insert(0, M + t)
import ref_model as RM, ref_closing as RB, ref_wing_body as RC, load_raw as LR

OUT = sys.argv[1]
rows = RM.load_raw(); raw = list(csv.reader(open(RM.RAW, newline='')))
for r, rr in zip(rows, raw): r['tid_s'] = rr[28]; r['ono'] = int(rr[4]); r['entry'] = rr[23]
S = [r for r in rows if r['und'] == 'SENSEX']; N = [r for r in rows if r['und'] == 'NIFTY']
R = {}
# 1. extraction rule -------------------------------------------------------------------------------------------------------------------------------
pat = re.compile(r'^(\d{19})-(\d{1,9})$')
m = [pat.match(r['tid_s']) for r in S]
R['1_format'] = dict(sensex_fills=len(S), match_19digit_dash_suffix=sum(1 for x in m if x), nonmatching_examples=[r['tid_s'] for r, x in zip(S, m) if not x][:5],
                     prefix_lengths=dict(collections.Counter(len(r['tid_s'].split('-')[0]) for r in S)), suffix_lengths=dict(collections.Counter(len(r['tid_s'].split('-')[1]) for r in S if '-' in r['tid_s'])),
                     nifty_ids_all_numeric_no_dash=all(r['tid_s'].isdigit() for r in N), nifty_numeric_lengths=dict(collections.Counter(len(r['tid_s']) for r in N)))
for r in S: r['ns'] = int(r['tid_s'].split('-')[0]); r['sfx'] = int(r['tid_s'].split('-')[1])
# 2. relation to the epoch column ------------------------------------------------------------------------------------------------------------------
d = collections.Counter(r['ns'] // 10**9 - r['ts'] for r in S)
fl = sum(1 for r in S if r['ns'] // 10**9 == r['ts']); rd = sum(1 for r in S if (r['ns'] + 500_000_000) // 10**9 == r['ts']); ce = sum(1 for r in S if -(-r['ns'] // 10**9) == r['ts'])
frac = collections.defaultdict(collections.Counter)
for r in S: frac[r['ns'] // 10**9 - r['ts']][('frac>=.5' if r['ns'] % 10**9 >= 5 * 10**8 else 'frac<.5')] += 1
R['2_relation_to_epoch'] = dict(floor_ns_s_minus_epoch_distribution={str(k): v for k, v in sorted(d.items())}, epoch_equals_floor=fl, epoch_equals_round_half_up=rd, epoch_equals_ceil=ce, fraction_split={str(k): dict(v) for k, v in frac.items()},
                                  max_abs_diff_s=max(abs(k) for k in d))
exc = [r for r in S if abs(r['ns'] // 10**9 - r['ts']) > 1 or not (r['ns'] // 10**9 == r['ts'] or (r['ns'] + 500_000_000) // 10**9 == r['ts'])]
R['3_exceptional_fills'] = [dict(row=r['row'], tid=r['tid_s'], epoch=r['ts'], ns_s=r['ns'] / 1e9, diff_s=r['ns'] / 1e9 - r['ts'], inst=r['inst'], parent=r['parent'], side=r['side'], qty=r['qty']) for r in exc]
# 4. duplicates and collisions ---------------------------------------------------------------------------------------------------------------------
cnt_full = collections.Counter(r['tid_s'] for r in S); cnt_ns = collections.Counter(r['ns'] for r in S)
G = collections.defaultdict(list)
for r in S: G[(r['inst'], r['ts'])].append(r)
multi = [g for g in G.values() if len(g) > 1]
tie_ns_in_group = [g for g in multi if len({x['ns'] for x in g}) < len(g)]
R['4_duplicates_collisions'] = dict(duplicate_full_trade_ids=sum(1 for v in cnt_full.values() if v > 1), duplicate_ns_prefixes_global=sum(1 for v in cnt_ns.values() if v > 1), same_ns_prefix_in_same_instrument_second_group=len(tie_ns_in_group),
                                    examples_same_ns_in_group=[[(x['row'], x['tid_s'], x['side'], x['qty']) for x in g] for g in tie_ns_in_group[:4]],
                                    nifty_duplicate_trade_ids=sum(1 for v in collections.Counter(r['tid_s'] for r in N).values() if v > 1), nifty_distinct_over_rows=len({r['tid_s'] for r in N}))
# 5. ordering consistency in same-instrument same-second groups ------------------------------------------------------------------------------------
dis = [g for g in multi if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (f['ns'], f['row']))]]
mixed = [g for g in multi if len({x['side'] for x in g}) > 1]
def kind(g):
    return dict(rows=[x['row'] for x in g], sides=''.join('B' if x['side'] > 0 else 'S' for x in g), qty=[x['qty'] for x in g], same_parent=len({x['parent'] for x in g}) == 1, ns_gap_ms=[round((x['ns'] - g[0]['ns']) / 1e6, 3) for x in g], tids=[x['tid_s'] for x in g])
R['5_ordering'] = dict(multi_fill_groups=len(multi), mixed_side_groups=len(mixed), file_order_differs_from_ns_order=len(dis), mixed_side_that_differ=sum(1 for g in dis if len({x['side'] for x in g}) > 1),
                       differing_groups=[kind(g) for g in dis], file_order_differs_from_ns_order_then_suffix=sum(1 for g in multi if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (f['ns'], f['sfx'], f['row']))]))
# global within-second behaviour (all SENSEX fills): is file order the ns order across instruments? ----------------------------------------------------
adj = tot = 0
byts = collections.defaultdict(list)
for r in S: byts[r['ts']].append(r)
for v in byts.values():
    v.sort(key=lambda f: f['row'])
    for a, b in zip(v, v[1:]): tot += 1; adj += b['ns'] >= a['ns']
R['5b_global_within_second'] = dict(adjacent_same_second_pairs=tot, file_order_ns_nondecreasing=adj)
# 6. semantics: per-fill time or per-order time? ---------------------------------------------------------------------------------------------------
P = collections.defaultdict(list)
for r in S: P[r['parent']].append(r)
mp = [v for v in P.values() if len(v) > 1]
R['6_semantics'] = dict(parents_with_multiple_fills=len(mp), parents_all_distinct_ns=sum(1 for v in mp if len({x['ns'] for x in v}) == len(v)), parents_ns_increasing_in_file_order=sum(1 for v in mp if all(b['ns'] >= a['ns'] for a, b in zip(sorted(v, key=lambda f: f['row']), sorted(v, key=lambda f: f['row'])[1:]))),
                        ns_minus_epoch_ms_quantiles=None)
dd = sorted((r['ns'] / 1e6 - r['ts'] * 1e3) for r in S); q = lambda p: round(dd[int(p * (len(dd) - 1))], 1)
R['6_semantics']['ns_minus_epoch_ms_quantiles'] = {k: q(v) for k, v in dict(min=0, p01=.01, p50=.5, p99=.99, max=1).items()}
# 7. accounting / lineage effect of the SENSEX-only ns policy (NIFTY stays file order) ---------------------------------------------------------------
ordered_src = RM.order_fills(rows, 'src'); ordered_ns = sorted(rows, key=lambda f: (f['ts'], f['ns'] if f['und'] == 'SENSEX' else 0, f['row']))
for r in N: r['ns'] = 0
base = {c: RM.replay_ref(ordered_src, c) for c in ('FIFO', 'LIFO')}; alt = {c: RM.replay_ref(ordered_ns, c) for c in ('FIFO', 'LIFO')}
def sig(X):
    by = collections.defaultdict(list)
    for r, o in X.oa.items(): by[o['ep']].append(r)
    return {eid: ((e['dir'], e['opened'], e['closed'], e['ended_by'], e['rev'], e['n_open'], e['n_close']), frozenset(by.get(eid, []))) for eid, e in X.episodes.items()}
acc = {}
for c in ('FIFO', 'LIFO'):
    a, b = sig(alt[c]), sig(base[c]); chg = [e for e in set(a) | set(b) if a.get(e) != b.get(e)]
    acc[c] = dict(episodes_identity_changed=len(chg), fills_open_close_split_changed=sum(1 for r in base[c].fills if (base[c].fills[r]['close'], base[c].fills[r]['open']) != (alt[c].fills[r]['close'], alt[c].fills[r]['open'])),
                  OA_membership_diff=len(set(base[c].oa) ^ set(alt[c].oa)), CP_membership_diff=len(set(base[c].cp) ^ set(alt[c].cp)), realized_delta_paise=float(alt[c].realized_total - base[c].realized_total),
                  OA_units=sum(o['qty'] for o in alt[c].oa.values()), CP_units=sum(x['qty'] for x in alt[c].cp.values()), final_inv_equal=alt[c].final_inv == base[c].final_inv, cash_equal=alt[c].cash == base[c].cash, reversal_fills=sum(1 for f in alt[c].fills.values() if f['rev']))
FB = RB.load_raw()
def batches(X):
    rep = []
    for f in FB: g = dict(f); fr = X.fills[f['row'] - 1]; g['close_qty'] = fr['close']; g['open_qty'] = fr['open']; rep.append(g)
    P_ = RB.parents_from(rep); return {(m_, g_): RB.partition(RB.build(P_, m_, g_)) for m_ in ('C1', 'C2') for g_ in (2, 5, 10, 30, 60)}
b0 = batches(base['FIFO']); b1 = batches(alt['FIFO']); R['7_effect'] = dict(accounting=acc, batches_changed={f'{k[0]}@{k[1]}s': len(b0[k] - b1[k]) for k in b0})
FC = LR.load(); rank = {f['row']: i for i, f in enumerate(ordered_ns)}; rank0 = {f['row']: i for i, f in enumerate(ordered_src)}
A0 = RC.analyse(FC, 'TAGGED', order=lambda f: rank0[f['row']]); A1 = RC.analyse(FC, 'TAGGED', order=lambda f: rank[f['row']])
lk = lambda A_: {m_: {(l['level'], l['wing'], l['body']) for l in L} for m_, L in A_['links'].items()}
l0, l1 = lk(A0), lk(A1); R['7_effect']['wing_body'] = dict(items_only_in_one=len(set(A0['items']) ^ set(A1['items'])), links_changed={m_: len(l0[m_] ^ l1[m_]) for m_ in l0})
# which instruments/groups the policy changes ordering for (accounting relevant or not) ---------------------------------------------------------------
R['7_effect']['groups_differing_in_order'] = len(dis); R['7_effect']['groups_changing_open_close_split'] = None
json.dump(R, open(OUT, 'w'), indent=1, default=str)
for k, v in R.items(): print(k, json.dumps(v, default=str)[:900])
