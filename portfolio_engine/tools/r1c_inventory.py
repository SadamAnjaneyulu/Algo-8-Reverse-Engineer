"""R1-C file-level inventory: every path of the output universe appears exactly once with exactly one classification per comparison.
  python3 portfolio_engine/tools/r1c_inventory.py --control=<dir> --scenario=<dir> [--out=reports/r1c_dual_scenario/file_inventory]
control  = baseline scenario produced by tools/r1c_scenario_run.py into an EMPTY out root (reproduction of the delivered outputs);
scenario = the hybrid (or any) scenario produced the same way.
Universe = delivered files under the six historical report directories + the case-study Markdown  UNION  every file produced by either run under the same roots.
Classes: IDENTICAL, DIFFERENT, MISSING (delivered but not produced), NEW (produced but not delivered), EXCLUDED_WITH_REASON (explicit table below).
Identity check:  IDENTICAL + DIFFERENT + MISSING + NEW + EXCLUDED = TOTAL_UNIVERSE  for each comparison (asserted).
JSON files are compared after dropping provenance-only keys (created_utc, generated_at_head, working_tree_dirty, scenario, reproduce, tie_order_convention): everything else must be equal."""
import collections, gzip, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE)
ROOTS = ['reports/m2c_data', 'reports/m2c_figures', 'reports/m2d_data', 'reports/m2d_figures', 'reports/m2e_data', 'reports/m2e_figures']
SINGLE = ['reports/M2E_POSITION_CASE_STUDIES.md']
EXCLUDED = {'reports/m2e_data/review_dispositions.json': 'hand-written M2-E review record; produced by no generator in the chain'}
SIDECAR = 'inventory_series_intra_second_flags.tsv'        # scenario-only file (NEW by design); its manifest entry is ignored when comparing manifests
PROVENANCE = {'created_utc', 'generated_at_head', 'working_tree_dirty', 'scenario', 'reproduce', 'tie_order_convention'}
args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if a.startswith('--'))
CONTROL, SCEN = args['control'], args['scenario']; OUT = args.get('out', os.path.join(PE, 'reports', 'r1c_dual_scenario', 'file_inventory'))


def listing(base):
    out = set()
    for r in ROOTS:
        for d, _, fs in os.walk(os.path.join(base, r)):
            for f in fs: out.add(os.path.relpath(os.path.join(d, f), base))
    for s in SINGLE:
        if os.path.isfile(os.path.join(base, s)): out.add(s)
    return out


def raw(base, rel): return open(os.path.join(base, rel), 'rb').read()
def sha(b): return hashlib.sha256(b).hexdigest()


def strip(x):
    if isinstance(x, dict): return {k: strip(v) for k, v in x.items() if k not in PROVENANCE and k != SIDECAR}
    if isinstance(x, list): return [strip(v) for v in x]
    return x


def normalised(base, rel):
    b = raw(base, rel)
    if rel.endswith('.json'): return json.dumps(strip(json.loads(b)), sort_keys=True).encode()
    return b


def text_of(base, rel):
    b = raw(base, rel)
    if rel.endswith('.gz'): b = gzip.decompress(b)
    return b.decode(errors='replace')


def category(rel):
    n = os.path.basename(rel)
    if rel.endswith('.png'): return 'figure_png'
    if n == 'manifest.json' or n == 'figure_manifest.json' or n == 'case_figure_manifest.json': return 'manifest'
    if 'summary' in n or n in ('coverage.json', 'case_studies.json'): return 'summary_json'
    if n.endswith('.md'): return 'markdown_report'
    root = rel.split('/')[1]
    if root.startswith('m2c'): return 'm2c_' + ('figure_csv' if 'figures' in root else 'closing_batch_data')
    if root.startswith('m2d'): return 'm2d_' + ('figure_csv' if 'figures' in root else 'wing_body_data')
    if root == 'm2e_figures': return 'm2e_figure_csv'
    return 'm2e_cycle_table'


def detail(delivered_base, other_base, rel):
    """why a DIFFERENT file differs (machine-computed, no assumption)"""
    if rel.endswith('.png'): return dict(kind='png', delivered_bytes=len(raw(delivered_base, rel)), other_bytes=len(raw(other_base, rel)), note='rendered image bytes differ')
    if rel.endswith('.json'):
        a, b = strip(json.loads(raw(delivered_base, rel))), strip(json.loads(raw(other_base, rel))); diffs = []
        def walk(x, y, p=''):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in sorted(set(x) | set(y)): walk(x.get(k), y.get(k), p + '/' + str(k))
            elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y) and any(isinstance(i, (dict, list)) for i in x):
                for i, (u, v) in enumerate(zip(x, y)): walk(u, v, p + f'[{i}]')
            elif x != y: diffs.append(p)
        walk(a, b); return dict(kind='json', differing_leaf_fields=len(diffs), examples=diffs[:6])
    A, B = text_of(delivered_base, rel).split('\n'), text_of(other_base, rel).split('\n'); ha, hb = A[0], B[0]; A, B = [x for x in A[1:] if x], [x for x in B[1:] if x]
    ca, cb = collections.Counter(A), collections.Counter(B); only_a, only_b = sum((ca - cb).values()), sum((cb - ca).values())
    return dict(kind='table', header_equal=ha == hb, rows_delivered=len(A), rows_other=len(B), rows_only_in_delivered=only_a, rows_only_in_other=only_b, same_rows_reordered_only=(only_a == 0 and only_b == 0 and ha == hb),
                positions_changed=sum(1 for x, y in zip(A, B) if x != y))


def classify(rel, dbase, obase, other_set, delivered_set):
    if rel in EXCLUDED: return 'EXCLUDED_WITH_REASON', EXCLUDED[rel], None
    d, o = rel in delivered_set, rel in other_set
    if d and not o: return 'MISSING', 'delivered file not produced by the chain', None
    if o and not d: return 'NEW', 'produced by the chain, not a delivered file', None
    if normalised(dbase, rel) == normalised(obase, rel): return 'IDENTICAL', 'bytes equal' + (' after dropping provenance-only keys' if rel.endswith('.json') else ''), None
    det = detail(dbase, obase, rel)
    if det['kind'] == 'table': reason = 'same rows, different order' if det['same_rows_reordered_only'] else f"rows changed: {det['rows_only_in_delivered']} only in delivered, {det['rows_only_in_other']} only in the other scenario"
    elif det['kind'] == 'json': reason = f"{det['differing_leaf_fields']} content fields differ"
    else: reason = det['note']
    return 'DIFFERENT', reason, det


dset = listing(PE); cset = listing(CONTROL); sset = listing(SCEN); universe = sorted(dset | cset | sset | set(EXCLUDED))
rows = []
for rel in universe:
    rec = dict(path=rel, category=category(rel), delivered_sha256=sha(raw(PE, rel)) if rel in dset else None, control_sha256=sha(raw(CONTROL, rel)) if rel in cset else None, scenario_sha256=sha(raw(SCEN, rel)) if rel in sset else None)
    for name, obase, oset in (('control_vs_delivered', CONTROL, cset), ('scenario_vs_delivered', SCEN, sset)):
        c, reason, det = classify(rel, PE, obase, oset, dset); rec[name] = dict(classification=c, reason=reason, detail=det)
    if rel in cset and rel in sset:
        rec['scenario_vs_control'] = 'IDENTICAL' if normalised(CONTROL, rel) == normalised(SCEN, rel) else 'DIFFERENT'
    rows.append(rec)
summary = {}
for name in ('control_vs_delivered', 'scenario_vs_delivered'):
    cnt = collections.Counter(r[name]['classification'] for r in rows)
    for k in ('IDENTICAL', 'DIFFERENT', 'MISSING', 'NEW', 'EXCLUDED_WITH_REASON'): cnt.setdefault(k, 0)
    assert sum(cnt.values()) == len(universe) == len({r['path'] for r in rows}), (name, dict(cnt), len(universe))          # every path exactly once, exactly one class
    summary[name] = dict(cnt, TOTAL_UNIVERSE=len(universe))
cat = collections.defaultdict(lambda: collections.Counter())
for r in rows: cat[r['category']][r['scenario_vs_delivered']['classification']] += 1
summary['scenario_vs_delivered_by_category'] = {k: dict(v) for k, v in sorted(cat.items())}
summary['delivered_files'] = len(dset); summary['control_files_produced'] = len(cset); summary['scenario_files_produced'] = len(sset)
res = dict(statement='Every path appears once. IDENTICAL + DIFFERENT + MISSING + NEW + EXCLUDED_WITH_REASON = TOTAL_UNIVERSE for both comparisons (asserted by the tool).', control=CONTROL if False else 'baseline scenario reproduced from empty out root',
           scenario='alternative scenario produced from empty out root', summary=summary, files=rows)
json.dump(res, open(OUT + '.json', 'w'), indent=1, sort_keys=True)
print(json.dumps(summary, indent=1))
