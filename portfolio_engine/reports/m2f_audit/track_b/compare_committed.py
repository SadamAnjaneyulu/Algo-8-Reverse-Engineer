"""Task 1: compare own reference to committed m2c_data for all 10 views. [RAW]/[IMPL] vs committed outputs."""
import sys, gzip, csv, json, collections
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
from ref_closing import *
D = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2c_data/'
def rd(name):
    with gzip.open(D + name + '.tsv.gz', 'rt') as f: return list(csv.DictReader(f, delimiter='\t'))
fills = load_raw(); rep = replay(fills); P = parents_from(rep)
print('closing parents', len(P), 'portions', sum(len(p['cps']) for p in P), 'units', sum(p['qty'] for p in P))
res = {}
for m in ('C1', 'C2'):
    B = rd('closing_batches_' + m); M = rd('closing_batch_members_' + m); PO = rd('closing_batch_portions_' + m)
    for g in (2, 5, 10, 30, 60):
        bb = [r for r in B if int(r['threshold_s']) == g]; mm = [r for r in M if int(r['threshold_s']) == g]
        pp = [r for r in PO if int(r['threshold_s']) == g]
        mine = build(P, m, g)
        # committed partition
        mem = collections.defaultdict(list)
        for r in mm: mem[r['batch_id']].append(r['parent_order_id'])
        bmap = {r['batch_id']: r for r in bb}
        com = set()
        for bid, pids in mem.items():
            r = bmap[bid]; com.add(((r['underlying'], r['expiry'], r['session']), frozenset(pids)))
        mymap = {(b['stream'], frozenset(b['pids'])): b for b in mine}
        mine_set = set(mymap)
        diffs = {'only_mine': len(mine_set - com), 'only_committed': len(com - mine_set)}
        # per-batch attributes
        bad = collections.Counter()
        for bid, r in bmap.items():
            k = ((r['underlying'], r['expiry'], r['session']), frozenset(mem[bid]))
            b = mymap.get(k)
            if not b: continue
            if int(r['n_parents']) != len(b['pids']): bad['n_parents'] += 1
            if int(r['n_closing_portions']) != b['ncp']: bad['ncp'] += 1
            if int(r['total_closing_qty']) != b['qty']: bad['qty'] += 1
            if int(r['start_ts']) != b['first']: bad['start'] += 1
            if int(r['end_ts']) != b['last']: bad['end'] += 1
            if int(r['duration_s']) != b['last'] - b['first']: bad['dur'] += 1
            if int(r['n_links']) != len(b['links']): bad['n_links'] += 1
            if len(b['links']) and int(r['max_link_gap_s']) != max(b['links']): bad['max_gap'] += 1
        # id numbering: sequential in order of start within stream?
        # portions
        pcom = collections.defaultdict(set)
        for r in pp: pcom[r['batch_id']].add((int(r['source_row_id']), int(r['quantity'])))
        pbad = 0
        rowq = {f['row']: f['close_qty'] for f in rep}
        for bid, r in bmap.items():
            k = ((r['underlying'], r['expiry'], r['session']), frozenset(mem[bid]))
            b = mymap.get(k)
            if not b: continue
            mp = {(row - 1, rowq[row]) for row in b['cps']}
            if mp != pcom[bid]: pbad += 1
        allrows = [x for b in mine for x in b['cps']]
        cons = dict(portions=len(allrows), uniq=len(set(allrows)), units=sum(b['qty'] for b in mine),
                    parents=sum(len(b['pids']) for b in mine))
        # committed portions rows sum
        cqty = sum(int(r['quantity']) for r in pp)
        st = stats(mine)
        res[(m, g)] = dict(committed_batches=len(bb), my_batches=len(mine), diffs=diffs, attr_bad=dict(bad),
                           portion_set_mismatch=pbad, cons=cons, committed_portion_units=cqty, **st)
        print(m, g, res[(m, g)])
json.dump({f'{k[0]}_{k[1]}': v for k, v in res.items()}, open('compare_committed_result.json', 'w'), indent=1)
