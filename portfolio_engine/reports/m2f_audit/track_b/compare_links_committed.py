"""Compare member-level join gaps and overlap flags in committed members files to own reference (all 10 views). [IMPL]"""
import sys, gzip, csv, collections, json
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
from ref_closing import *
D = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2c_data/'
fills = load_raw(); P = parents_from(replay(fills)); res = {}
for m in ('C1', 'C2'):
    M = list(csv.DictReader(gzip.open(D + f'closing_batch_members_{m}.tsv.gz', 'rt'), delimiter='\t'))
    B = {r['batch_id']: r for r in csv.DictReader(gzip.open(D + f'closing_batches_{m}.tsv.gz', 'rt'), delimiter='\t')}
    for g in (2, 5, 10, 30, 60):
        mem = collections.defaultdict(list)
        for r in M:
            if int(r['threshold_s']) == g: mem[r['batch_id']].append(r)
        mine = {(b['stream'], tuple(b['pids'])): b for b in build(P, m, g)}
        bad = 0; n = 0; badb = 0
        for bid, rows in mem.items():
            st = bid.split(':')[-4:-1]; key = (tuple(st), tuple(r['parent_order_id'] for r in rows))
            b = mine.get(key)
            if b is None: bad += 1; continue                       # includes order-within-batch mismatch
            for i, r in enumerate(rows[1:]):
                n += 1
                if int(r['join_gap_s']) != b['links'][i] or bool(int(r['interval_overlap'])) != b['ov'][i] or bool(int(r['strict_overlap'])) != b['sov'][i]: bad += 1
            br = B[bid]
            if int(br['n_overlap_links']) != sum(b['ov']) or int(br['n_strict_overlap_links']) != sum(b['sov']) or int(br['has_interval_overlap']) != int(any(b['ov'])): badb += 1
        res[f'{m}_{g}'] = dict(links_checked=n, member_link_mismatch=bad, batch_overlap_count_mismatch=badb)
        print(m, g, res[f'{m}_{g}'])
json.dump(res, open('compare_links_committed_result.json', 'w'), indent=1)
