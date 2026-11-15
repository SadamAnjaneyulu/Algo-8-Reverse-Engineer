"""R1: stamp the tie-order convention metadata into the four DELIVERED manifests (metadata only; no data value changes).
Safety: (1) each manifest must round-trip through json.loads/json.dumps(indent=1) byte-identically BEFORE the key is added, so nothing but the new key can change;
(2) every other tracked file must equal its sha256 in reports/m2f_audit/r1/baseline_sha256_before_R1.json before and after; (3) the tool is idempotent.
python3 portfolio_engine/tools/r1_stamp_convention.py [--dry-run]"""
import hashlib, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tie_policy as tp
MANIFESTS = ['portfolio_engine/reports/m2c_data/manifest.json', 'portfolio_engine/reports/m2d_data/manifest.json', 'portfolio_engine/reports/m2e_data/NIFTY_2026-06-30/manifest.json', 'portfolio_engine/reports/m2e_data/SENSEX_2026-07-16/manifest.json']
BASE = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1', 'baseline_sha256_before_R1.json')))['sha256']
sha = lambda p: hashlib.sha256(open(os.path.join(REPO, p), 'rb').read()).hexdigest()
dry = '--dry-run' in sys.argv


def others_unchanged(exclude):
    bad = []
    for p, h in BASE.items():
        if p in exclude or p.startswith('portfolio_engine/python/') or p.startswith('portfolio_engine/tests/') or p.startswith('portfolio_engine/tools/') or p.endswith(('.md',)) or p.startswith('portfolio_engine/reports/m2f_audit/'): continue
        if not os.path.exists(os.path.join(REPO, p)) or sha(p) != h: bad.append(p)
    return bad


assert not others_unchanged(set(MANIFESTS)), 'a non-manifest delivered output differs from the R1 baseline BEFORE stamping'
report = []
for p in MANIFESTS:
    path = os.path.join(REPO, p); text = open(path).read(); obj = json.loads(text)
    assert json.dumps(obj, indent=1) == text, f'{p}: JSON round trip is not byte-identical; refusing to rewrite'
    before = sha(p); assert before == BASE[p], f'{p} differs from the R1 baseline'
    new = dict(obj); new['tie_order_convention'] = tp.CONVENTION_METADATA
    if obj.get('tie_order_convention') == tp.CONVENTION_METADATA: report.append((p, before, before, 'already stamped')); continue
    out = json.dumps(new, indent=1)
    if not dry: open(path, 'w').write(out)
    report.append((p, before, hashlib.sha256(out.encode()).hexdigest(), 'stamped' if not dry else 'dry-run'))
if not dry: assert not others_unchanged(set(MANIFESTS)), 'a non-manifest delivered output changed during stamping'
for p, b, a, s in report: print(f'{s:15s} {p}\n   before {b}\n   after  {a}')
print('all other delivered data/figure/summary files verified byte-identical to the R1 baseline' + (' (dry run: nothing written)' if dry else ''))
