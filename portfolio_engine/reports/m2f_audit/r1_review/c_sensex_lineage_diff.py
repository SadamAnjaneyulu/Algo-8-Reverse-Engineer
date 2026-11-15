"""Task C: how do the lineage TSVs under sensex_trade_id_time differ from the primary, given 0 split changes? (pe used as object under test)"""
import sys, json, collections
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
from pe.generators import historical as H
from pe import replay as rp
repo = '/home/user/Algo-8-Reverse-Engineer'
ins, fills = H.generate(repo)[:2]
base = rp.lineage_files(rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'src', lineage=True))
sx = rp.lineage_files(rp.replay(H.attach_tie_keys(repo, fills, 'sensex_trade_id_time'), ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'sensex_trade_id_time', lineage=True))
out = {}
for k in base:
    a = base[k].splitlines(); b = sx[k].splitlines()
    out[k] = dict(lines=len(a), identical=a == b, same_multiset=collections.Counter(a) == collections.Counter(b), differing_positions=sum(1 for x, y in zip(a, b) if x != y), only_in_base=len(collections.Counter(a) - collections.Counter(b)), only_in_sx=len(collections.Counter(b) - collections.Counter(a)))
    if a != b:
        d = [(x, y) for x, y in zip(a, b) if x != y][:2]; out[k]['example'] = d
json.dump(out, open('c_sensex_lineage_diff_result.json', 'w'), indent=1); print(json.dumps(out, indent=1)[:3500])

# --- content-level comparison of CA rows (CP, OA, qty) and of lifecycle rows
def ca_rows(txt): return {tuple(l.split('\t')[2:5]) for l in txt.splitlines()[1:] if l.startswith('CA')}
cb, cs = ca_rows(base['ca_FIFO.tsv']), ca_rows(sx['ca_FIFO.tsv'])
out2 = dict(ca_pairs_base=len(cb), ca_pairs_only_base=len(cb - cs), ca_pairs_only_sx=len(cs - cb), example_only_base=sorted(cb - cs)[:3], example_only_sx=sorted(cs - cb)[:3])
cps_changed = sorted({x[0] for x in cb ^ cs}); out2['closing_portions_with_different_FIFO_source_lots'] = len(cps_changed); out2['closing_portion_fill_ids_sample'] = cps_changed[:6]
fl = lambda t: collections.Counter(t.splitlines()); lb, ls_ = fl(base['lifecycle.tsv']), fl(sx['lifecycle.tsv']); out2['lifecycle_example_only_base'] = list((lb - ls_).keys())[:2]; out2['lifecycle_example_only_sx'] = list((ls_ - lb).keys())[:2]
json.dump(out2, open('c_sensex_lineage_diff2_result.json', 'w'), indent=1); print(json.dumps(out2, indent=1))
