"""Task 4: longest chains, frozen-cycle counts, C1==C2 claim, unit conservation from RAW quantities. [RAW]/[IMPL]"""
import sys, json, collections
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
from ref_closing import *
import datetime
TH = (2, 5, 10, 30, 60)
fills = load_raw(); rep = replay(fills); P = parents_from(rep)
def hhmmss(t): return (datetime.datetime(1970,1,1)+datetime.timedelta(seconds=t+IST)).strftime('%H:%M:%S')
out = {'longest': {}, 'cycles': {}, 'conservation': {}}
# raw-only conservation: closing units computed straight from raw by an independent minimal loop (no shared code with replay())
pos = collections.defaultdict(int); closing_units = 0; n_cp = 0
for f in fills:   # raw file order == time order (verified monotone)
    s = 1 if f['side'] == 'Buy' else -1; inv = pos[f['instr']]
    if inv != 0 and (inv > 0) != (s > 0): c = min(f['qty'], abs(inv)); closing_units += c; n_cp += 1
    pos[f['instr']] += s * f['qty']
out['conservation']['raw_minimal_loop_closing_units'] = closing_units; out['conservation']['raw_minimal_loop_closing_portions'] = n_cp
out['conservation']['total_fill_units'] = sum(f['qty'] for f in fills)
out['conservation']['opening_units'] = sum(f['open_qty'] for f in rep)
out['conservation']['open_plus_close_equals_fill_units'] = out['conservation']['opening_units'] + sum(f['close_qty'] for f in rep) == out['conservation']['total_fill_units']
for m in ('C1', 'C2'):
    for g in TH:
        B = build(P, m, g)
        U = sum(b['qty'] for b in B); allcp = [r for b in B for r in b['cps']]
        out['conservation'][f'{m}_{g}'] = dict(batch_units=U, equals_raw=(U == closing_units), parents_once=(sum(len(b['pids']) for b in B) == len({p['pid'] for p in P})),
                                              portions_once=(len(allcp) == len(set(allcp)) == n_cp))
        if m == 'C1':
            ranked = sorted(B, key=lambda b: -(b['last'] - b['first']))[:3]
            out['longest'][g] = [dict(stream=b['stream'], seq=None, parents=len(b['pids']), portions=b['ncp'], units=b['qty'],
                                      contracts=len({f['instr'] for p in P if p['pid'] in set(b['pids']) for f in p['cps']}),
                                      start=hhmmss(b['first']), end=hhmmss(b['last']), dur=b['last'] - b['first'], maxgap=max(b['links']) if b['links'] else 0) for b in ranked]
        # frozen cycles
        for und, exp in (('NIFTY', '2026-06-30'), ('SENSEX', '2026-07-16')):
            sub = [b for b in B if b['stream'][0] == und and b['stream'][1] == exp]
            sizes = [len(b['pids']) for b in sub]
            out['cycles'][f'{m}|{und}|{exp}|{g}'] = dict(batches=len(sub), parents=sum(sizes), singletons=sum(1 for s in sizes if s == 1), max_parents=max(sizes), max_dur=max(b['last'] - b['first'] for b in sub),
                                                         units=sum(b['qty'] for b in sub), sessions=sorted({b['stream'][2] for b in sub}))
# C1 vs C2 under base
for g in TH:
    a, b = pset_ = None, None
    c1 = build(P, 'C1', g); c2 = build(P, 'C2', g)
    out['conservation'][f'C1_eq_C2_partition_{g}'] = partition(c1) == partition(c2)
json.dump(out, open('chains_cycles_result.json', 'w'), indent=1, default=str)
print(json.dumps(out['conservation'], indent=0)[:1500])
for g in TH:
    print(g, [(x['stream'][2], x['parents'], x['portions'], x['units'], x['contracts'], x['start'], x['end'], x['dur'], x['maxgap']) for x in out['longest'][g]])
for k, v in out['cycles'].items():
    if k.startswith('C1'): print(k, v)
