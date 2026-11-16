"""C-01 sample check: W1..W3 link sets baseline vs hybrid from my two regenerated out roots (link_id column), plus tagged opening body units from the items files."""
import gzip, csv, io, json, sys, os
base, hyb = sys.argv[1:3]; res = {}


def rd(root, name):
    with gzip.open(os.path.join(root, 'reports', 'm2d_data', name), 'rt') as fh: return list(csv.DictReader(fh, delimiter='\t'))


for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'):
    a = {r['link_id'] for r in rd(base, f'wing_body_links_{m}.tsv.gz')}; b = {r['link_id'] for r in rd(hyb, f'wing_body_links_{m}.tsv.gz')}
    res[m] = dict(baseline=len(a), hybrid=len(b), only_baseline=len(a - b), only_hybrid=len(b - a))
ia, ib = rd(base, 'wing_body_items.tsv.gz'), rd(hyb, 'wing_body_items.tsv.gz')
ub = lambda it: sum(int(r['qty']) for r in it if r['level'] == 'OPENING' and r['role'] == 'BODY')
res['opening_body_units'] = dict(baseline=ub(ia), hybrid=ub(ib)); res['items_only_in_one'] = len({r['item_id'] for r in ia} ^ {r['item_id'] for r in ib})
print(json.dumps(res, indent=1)); json.dump(res, open('item5d_links_result.json', 'w'), indent=1)
