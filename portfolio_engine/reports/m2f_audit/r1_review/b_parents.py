"""Task B: multi-fill parents. (1) is ns constant within a parent (order-time) or per-fill? (2) do minute columns follow the row's own fill time or the parent's last update? (3) mechanical constraint: remaining quantity (col 20) must strictly decrease along true fill sequence; compare to ns order and file order. [RAW]"""
import csv, datetime, collections, json
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
IST = datetime.timedelta(hours=5, minutes=30)
def parse(s): return int((datetime.datetime.strptime(s, '%m/%d/%Y %H:%M') - IST).replace(tzinfo=datetime.timezone.utc).timestamp())
def nsof(r): return int(r[28][:19]) if '-' in r[28] else None
P = collections.defaultdict(list)
for i, r in enumerate(rows): P[(r[12], r[163])].append(i)
out = {}
for und in ('SENSEX', 'NIFTY'):
    multi = {k: v for k, v in P.items() if k[0] == und and len(v) >= 2}
    o = dict(multi_fill_parents=len(multi), fills_in_multi=sum(len(v) for v in multi.values()))
    if und == 'SENSEX':
        same_ns = sum(1 for v in multi.values() if len({nsof(rows[i]) for i in v}) == 1)
        o['parents_with_identical_ns_across_fills'] = same_ns
        o['parents_with_ns_nondecreasing_in_file_order'] = sum(1 for v in multi.values() if all(nsof(rows[a]) <= nsof(rows[b]) for a, b in zip(v, v[1:])))
        o['parents_with_ns_strictly_increasing_in_file_order'] = sum(1 for v in multi.values() if all(nsof(rows[a]) < nsof(rows[b]) for a, b in zip(v, v[1:])))
        spans = [(nsof(rows[v[-1]]) - nsof(rows[v[0]])) / 1e9 for v in multi.values()]
        o['ns_span_seconds_max'] = max(spans); o['ns_span_gt60s'] = sum(1 for s in spans if s > 60)
    # (3) remaining-qty constraint (col 20)
    rem_ok = rem_viol = 0; ns_vs_rem_viol = []; file_vs_rem_viol = []; ep_vs_rem_viol = []; tied_rem = 0; sameparent_samesec_groups = 0; sameparent_samesec_file_vs_rem = []
    consistency = []
    for k, v in multi.items():
        rem = [int(rows[i][20]) for i in v]; ordq = int(rows[v[0]][19])
        if len(set(rem)) < len(rem): tied_rem += 1; continue
        by_rem = sorted(v, key=lambda i: -int(rows[i][20]))      # true fill sequence: remaining after fill falls
        if by_rem != v: file_vs_rem_viol.append(k + (v,))
        eps = [int(rows[i][161]) for i in v]
        if any(eps[b] < eps[a] for a in range(len(v)) for b in range(a + 1, len(v)) if rem[b] < rem[a]) : pass
        # epoch contradiction: a fill with smaller remaining (later in true sequence) has an earlier epoch
        if any(int(rows[b][161]) < int(rows[a][161]) for a, b in zip(by_rem, by_rem[1:])): ep_vs_rem_viol.append(k + (by_rem,))
        if und == 'SENSEX' and any(nsof(rows[b]) < nsof(rows[a]) for a, b in zip(by_rem, by_rem[1:])): ns_vs_rem_viol.append(k + (by_rem,))
        # also check: remaining == order_qty - cumulative fill in remaining order
        cum = 0; ok = True
        for i in by_rem:
            cum += int(rows[i][33])
            if ordq - cum != int(rows[i][20]): ok = False
        consistency.append(ok)
    o['parents_tied_remaining(not testable)'] = tied_rem
    o['parents_testable'] = len(consistency); o['remaining_equals_orderqty_minus_cum_fill(all fills in parent, sorted by remaining)'] = sum(consistency)
    o['file_order_contradicts_remaining_sequence'] = len(file_vs_rem_viol)
    o['epoch_contradicts_remaining_sequence(earlier epoch for later-in-sequence fill)'] = len(ep_vs_rem_viol)
    if und == 'SENSEX': o['ns_contradicts_remaining_sequence'] = len(ns_vs_rem_viol)
    o['file_vs_rem_examples'] = [(a, b, [int(x) for x in c]) for a, b, c in file_vs_rem_viol[:5]]
    o['ep_vs_rem_examples'] = [(a, b, [int(x) for x in c]) for a, b, c in ep_vs_rem_viol[:5]]
    out[und] = o
# (2) minute columns follow own fill time or parent last update?  SENSEX multi-fill parents with >= 2 distinct ns-minutes
tr = collections.Counter()
for k, v in P.items():
    if k[0] != 'SENSEX' or len(v) < 2: continue
    mins = [(nsof(rows[i]) // 10**9) // 60 for i in v]
    if len(set(mins)) < 2: continue
    last_min = max(mins)
    for i, m in zip(v, mins):
        if m == last_min: continue
        for j in (23, 69, 79, 119, 130):
            t = parse(rows[i][j]) // 60
            tr[(j, 'own_fill_minute' if t == m else ('parent_last_fill_minute' if t == last_min else 'other'))] += 1
out['minute_cols_on_non_last_fills_of_multi_minute_parents'] = {f'col{j}:{w}': n for (j, w), n in sorted(tr.items())}
json.dump(out, open('b_parents_result.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
