# R1-C dual-scenario independent reference (derived from independent_tie_sensitivity.py, which is unchanged). Orderings: src and the hybrid PER_CONTRACT_ID_SEQUENCE. Imports no pe.*; the hybrid key is re-derived here from the raw csv. Usage: python3 independent_per_contract_id_sequence.py <out.json>
# Copied from the R1 decision-brief experiment (run 2026-11-15); content below this header line is unchanged. Usage: python3 independent_tie_sensitivity.py <out.json>. Independent of pe.* (Track A/B/C references).
"""R1 decision-brief experiment (SCRATCH ONLY; writes nothing in the repository).
Replays the RAW csv under several intra-second orderings with the M2-F independent references (Track A accounting, Track B closing batches, Track C wing/body; none imports pe.*),
and measures what changes relative to SOURCE-ROW order.  Classification of every number: [RAW] + [IMPL]."""
import sys, json, time, collections
sys.dont_write_bytecode = True
M = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/'
for t in ('track_a', 'track_b', 'track_c'): sys.path.insert(0, M + t)
import ref_model as RM, ref_closing as RB, ref_wing_body as RC, load_raw as LR
import csv

OUT = sys.argv[1]
rows = RM.load_raw(); raw = list(csv.reader(open(RM.RAW, newline='')))
tkey = lambda s: tuple(int(x) for x in s.split('-'))
def hybrid_key(r, rr):
    if rr[12] == 'SENSEX':
        tid = rr[28]; ns = int(tid.split('-')[0]); return ns if (ns + 500_000_000) // 10**9 == r['ts'] else r['ts'] * 10**9      # embedded ns time if consistent with the epoch, else epoch fallback; suffix ignored
    return int(rr[28])                                                                                                                  # NIFTY numeric trade id
for r, rr in zip(rows, raw): r['hk'] = hybrid_key(r, rr)
ORD = {'src': lambda: RM.order_fills(rows, 'src'), 'per_contract_id_sequence': lambda: sorted(rows, key=lambda f: (f['ts'], f['hk'], f['row']))}
THR = (2, 5, 10, 30, 60)
FB = RB.load_raw(); FC = LR.load()


def sig(R):
    by = collections.defaultdict(list)
    for r, o in R.oa.items(): by[o['ep']].append(r)
    return {eid: ((e['dir'], e['opened'], e['closed'], e['ended_by'], e['rev'], e['n_open'], e['n_close']), frozenset(by.get(eid, []))) for eid, e in R.episodes.items()}


def acc_metrics(base, R):
    s, b = sig(R), sig(base); ids = set(s) | set(b); chg = [e for e in ids if s.get(e) != b.get(e)]
    split = [r for r in base.fills if (base.fills[r]['close'], base.fills[r]['open']) != (R.fills[r]['close'], R.fills[r]['open'])]
    ca = lambda X: collections.Counter({(x[0], x[1]): x[2] for x in X.ca})
    return dict(instruments_changed=len({e.split('#')[0] for e in chg}), episodes_identity_changed=len(chg), n_episodes=len(R.episodes), fills_open_close_split_changed=len(split),
                reversal_fills=sum(1 for f in R.fills.values() if f['rev']), OA_membership_diff=len(set(base.oa) ^ set(R.oa)), CP_membership_diff=len(set(base.cp) ^ set(R.cp)),
                CA_pairs_diff=len(set(ca(base).items()) ^ set(ca(R).items())), realized_delta_paise=float(R.realized_total - base.realized_total),
                OA_units=sum(o['qty'] for o in R.oa.values()), CP_units=sum(c['qty'] for c in R.cp.values()), final_inv_equal=R.final_inv == base.final_inv, cash_equal=R.cash == base.cash,
                _instruments=sorted({e.split('#')[0] for e in chg}), _split_rows=split)


def batches_for(R):
    rep = []
    for f in FB:
        g = dict(f); fr = R.fills[f['row'] - 1]; g['close_qty'] = fr['close']; g['open_qty'] = fr['open']; rep.append(g)
    P = RB.parents_from(rep); res = {}
    for m in ('C1', 'C2'):
        for g in THR:
            B = RB.build(P, m, g); res[(m, g)] = (RB.partition(B), len(B), B)
    return res


def wb_for(order_rank):
    A = RC.analyse(FC, 'TAGGED', order=lambda f: order_rank[f['row']])
    items = {k: (v.qty, v.first_ts) for k, v in A['items'].items()}
    links = {m: {(l['level'], l['wing'], l['body']) for l in L} for m, L in A['links'].items()}
    head = dict(opening_wing_items=sum(1 for k in items if k[0] == 'OPENING' and k[1] == 'WING'), opening_body_items=sum(1 for k in items if k[0] == 'OPENING' and k[1] == 'BODY'),
                opening_wing_units=sum(v[0] for k, v in items.items() if k[0] == 'OPENING' and k[1] == 'WING'), opening_body_units=sum(v[0] for k, v in items.items() if k[0] == 'OPENING' and k[1] == 'BODY'),
                closing_wing_units=sum(v[0] for k, v in items.items() if k[0] == 'CLOSING' and k[1] == 'WING'), closing_body_units=sum(v[0] for k, v in items.items() if k[0] == 'CLOSING' and k[1] == 'BODY'),
                links={m: len(s) for m, s in links.items()})
    return items, links, head


res = {}; base = None; t0 = time.time()
for name, mk in ORD.items():
    ordered = mk(); rank = {f['row']: i for i, f in enumerate(ordered)}
    acc = {}
    Rs = {}
    for conv in ('FIFO', 'LIFO'): Rs[conv] = RM.replay_ref(ordered, conv)
    bt = batches_for(Rs['FIFO']); items, links, head = wb_for(rank)
    if name == 'src': base = dict(R=Rs, bt=bt, items=items, links=links, head=head)
    r = dict(accounting={}, batches={}, wing_body={})
    for conv in ('FIFO', 'LIFO'): r['accounting'][conv] = acc_metrics(base['R'][conv], Rs[conv])
    for k, (part, n, B) in bt.items():
        bp = base['bt'][k][0]; gone = bp - part; new = part - bp
        r['batches'][f'{k[0]}@{k[1]}s'] = dict(n_batches=n, n_batches_baseline=base['bt'][k][1], baseline_batches_not_in_alternative=len(gone), alternative_batches_not_in_baseline=len(new), parents_in_changed_baseline_batches=sum(len(p) for _, p in gone))
    ik = set(items) | set(base['items'])
    r['wing_body'] = dict(headline=head, items_only_in_one=len(set(items) ^ set(base['items'])), items_qty_or_first_ts_changed=sum(1 for k in set(items) & set(base['items']) if items[k] != base['items'][k]),
                          links_changed={m: len(links[m] ^ base['links'][m]) for m in links}, links_baseline={m: len(base['links'][m]) for m in links})
    r['absolute'] = {conv: dict(realized_total_paise=str(Rs[conv].realized_total), n_episodes=len(Rs[conv].episodes), reversal_fills=sum(1 for f in Rs[conv].fills.values() if f['rev']), opening_units=sum(o['qty'] for o in Rs[conv].oa.values()),
                                closing_units=sum(c['qty'] for c in Rs[conv].cp.values()), reversal_ended_episodes=sum(1 for e in Rs[conv].episodes.values() if e['ended_by'] == 'REVERSAL' or e.get('ended_by') == 'reversal')) for conv in ('FIFO', 'LIFO')}
    res[name] = r
    print(f'{name:16s} done {time.time() - t0:6.0f}s  fifo: inst {r["accounting"]["FIFO"]["instruments_changed"]} ep {r["accounting"]["FIFO"]["episodes_identity_changed"]} split {r["accounting"]["FIFO"]["fills_open_close_split_changed"]} | C1@10 gone {r["batches"]["C1@10s"]["baseline_batches_not_in_alternative"]} | W1 links chg {r["wing_body"]["links_changed"]["W1"]}', flush=True)
    json.dump(res, open(OUT, 'w'), indent=1, default=str)
