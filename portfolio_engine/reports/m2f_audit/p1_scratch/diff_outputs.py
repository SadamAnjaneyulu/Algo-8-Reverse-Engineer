"""Compare scratch-mirror outputs with the DELIVERED outputs (repo), file by file. usage: diff_outputs.py <mirror_dir> <out.json>
Ignored: manifest.json / *summary*.json fields that carry timestamps or git heads are compared after dropping created_utc/generated_at_head; PNGs compared by sha256."""
import hashlib, json, os, sys, gzip
REPO = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine'; M = sys.argv[1] + '/portfolio_engine'
roots = ['reports/m2c_data', 'reports/m2d_data', 'reports/m2e_data', 'reports/m2e_figures', 'reports/m2d_figures', 'reports/m2c_figures', 'reports/M2E_POSITION_CASE_STUDIES.md']
def files(base):
    p = os.path.join(base, ''); out = []
    for r in roots:
        full = os.path.join(base, r)
        if os.path.isfile(full): out.append(r)
        for d, _, fs in os.walk(full):
            for f in fs: out.append(os.path.relpath(os.path.join(d, f), base))
    return sorted(set(out))
def norm(path):
    b = open(path, 'rb').read()
    if path.endswith('.json'):
        try:
            o = json.loads(b)
            def strip(x):
                if isinstance(x, dict): return {k: strip(v) for k, v in x.items() if k not in ('created_utc', 'generated_at_head', 'tie_order_convention')}
                if isinstance(x, list): return [strip(v) for v in x]
                return x
            return json.dumps(strip(o), sort_keys=True).encode()
        except Exception: return b
    return b
res = dict(same=[], different=[], only_in_delivered=[], only_in_scratch=[])
D, S = set(files(REPO)), set(files(M))
for f in sorted(D | S):
    if f not in S: res['only_in_delivered'].append(f); continue
    if f not in D: res['only_in_scratch'].append(f); continue
    (res['same'] if norm(os.path.join(REPO, f)) == norm(os.path.join(M, f)) else res['different']).append(f)
print({k: len(v) for k, v in res.items()})
for f in res['different'][:60]: print('DIFF', f)
for f in res['only_in_delivered'][:20]: print('MISSING', f)
json.dump(res, open(sys.argv[2], 'w'), indent=1)
