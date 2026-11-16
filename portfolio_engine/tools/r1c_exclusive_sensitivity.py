"""Decision C: the EXCLUSIVE closing-batch interpretation (`gap < threshold`) as a SENSITIVITY artifact. The primary (inclusive, `gap <= threshold`) C1/C2 results are never touched.
python3 portfolio_engine/tools/r1c_exclusive_sensitivity.py -> reports/r1c_dual_scenario/m2c_exclusive_threshold/  (summary + gzip TSVs + manifest; every row states the link semantics)"""
import gzip, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.lineage_set import LineageSet
from pe import closing_batches as cb, provenance, tie_policy as tp
from pe.generators import historical as H
OUT = os.path.join(PE, 'reports', 'r1c_dual_scenario', 'm2c_exclusive_threshold'); os.makedirs(OUT, exist_ok=True)
ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); tp.require_primary(ls.tie, 'exclusive-threshold sensitivity (baseline ordering)')
parents, unattr, multi = cb.closing_parents(ls); prim = cb.all_views(parents); excl = cb.all_views_exclusive(parents)
for k, v in excl.items(): cb.check_view(v, parents, ls.cp, unattr)                      # same partition + reconciliation invariants, with the exclusive reference implementation
member = lambda v: {frozenset(p.key for p in b['members']) for b in v['batches']}
rows = []
for (m, g) in sorted(prim):
    a, b = member(prim[(m, g)]), member(excl[(m, g)])
    pairs = [(x.first_ts - y.first_ts) if m == 'C1' else (x.first_ts - y.last_ts) for st in sorted({p.stream for p in parents}) for y, x in zip(*(lambda ps: (ps, ps[1:]))(sorted([p for p in parents if p.stream == st], key=lambda p: (p.first_ts, p.first_src, p.parent_id))))]
    rows.append(dict(method=m, threshold_s=g, inclusive_batches=len(a), exclusive_batches=len(b), pairs_with_gap_exactly_threshold=sum(1 for x in pairs if x == g), inclusive_batches_not_in_exclusive=len(a - b), exclusive_batches_not_in_inclusive=len(b - a),
                     link_semantics_primary='inclusive: gap <= threshold', link_semantics_this_artifact='EXCLUSIVE: gap < threshold (sensitivity only)'))
    print(rows[-1], flush=True)
files = {}
for m in ('C1', 'C2'): files.update(cb.files_for_method({k: v for k, v in excl.items() if k[0] == m}, m, ls))
man = dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), generated_at_head=provenance.git_sha(REPO), execution_mode='HISTORICAL_OBSERVED_REPLAY', source_hashes=src, tie_order_convention=tp.CONVENTION_METADATA, link_semantics='EXCLUSIVE (gap < threshold): SENSITIVITY ONLY; the primary C1/C2 views in reports/m2c_data use gap <= threshold',
           primary_parameter_hashes={f'{m}@{g}': prim[(m, g)]['parameter_hash'] for (m, g) in prim}, exclusive_parameter_hashes={f'{m}@{g}': excl[(m, g)]['parameter_hash'] for (m, g) in excl}, files={}, reproduce='python3 portfolio_engine/tools/r1c_exclusive_sensitivity.py')
for name, text in files.items():
    path = os.path.join(OUT, name.replace('.tsv', '_EXCLUSIVE.tsv') + '.gz')
    with open(path, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as z: z.write(text.encode())
    man['files'][os.path.basename(path)] = dict(sha256_of_text=hashlib.sha256(text.encode()).hexdigest(), rows=text.count('\n') - 1, bytes_gz=os.path.getsize(path))
json.dump(man, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1); json.dump(dict(statement='Exclusive reading of the approved threshold, published as a sensitivity. The primary results use gap <= threshold.', rows=rows), open(os.path.join(OUT, 'exclusive_sensitivity_summary.json'), 'w'), indent=1)
