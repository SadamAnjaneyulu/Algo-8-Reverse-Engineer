"""Item 1g: does the SENSEX embedded ns time agree with file order for adjacent same-second pairs of different instruments (a venue-wide clock would give ~100 percent)?"""
import json, collections
import rawload as R
rows = R.load(); sx = [r for r in rows if r['und'] == 'SENSEX']; c = collections.Counter()
for a, b in zip(sx, sx[1:]):
    if a['ts'] != b['ts']: continue
    ka, kb = R.hybrid_key(a), R.hybrid_key(b); kind = 'cross_instrument' if a['inst'] != b['inst'] else 'same_instrument'
    c[(kind, 'increasing' if kb > ka else ('decreasing' if kb < ka else 'equal'))] += 1
d = collections.defaultdict(list)
for r in sx: d[R.ist_day(r['ts'])].append(R.hybrid_key(r))
res = {f'{k[0]}|{k[1]}': v for k, v in c.items()}; res['day_level_adjacent_decreases'] = sum(sum(1 for a, b in zip(L, L[1:]) if b < a) for L in d.values()); res['day_level_adjacent_pairs'] = sum(len(L) - 1 for L in d.values())
print(json.dumps(res, indent=1)); json.dump(res, open('item1g_sensex_cross_result.json', 'w'), indent=1)
