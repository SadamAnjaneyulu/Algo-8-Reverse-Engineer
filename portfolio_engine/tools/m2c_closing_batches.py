"""M2-C: build the C1 / C2 closing-batch views on the REAL ledger, check every partition invariant, write gzip'd outputs + manifest + summary.
python3 portfolio_engine/tools/m2c_closing_batches.py   -> reports/m2c_data/*.tsv.gz, manifest.json, m2c_summary.json (deterministic; rerun gives identical bytes in the gz payloads)"""
import gzip, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import closing_batches as cb, provenance
from pe.generators import historical as H
OUT = os.path.join(PE, 'reports', 'm2c_data'); os.makedirs(OUT, exist_ok=True)
ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); ls.check(fills)
before = {n: hashlib.sha256(ls.files['FIFO'][n].encode()).hexdigest() for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv')}
parents, unattr, multi = cb.closing_parents(ls); views = cb.all_views(parents)
for k, v in views.items(): cb.check_view(v, parents, ls.cp, unattr)                      # partition + reconciliation, every view
rec2 = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); assert all(hashlib.sha256(rec2.files['FIFO'][n].encode()).hexdigest() == before[n] for n in before)      # observed ledger unchanged by grouping
S = dict(source_hashes=src, closing_parents=len(parents), closing_portions=len(ls.cp), closing_units=sum(r[8] for r in ls.cp.values()), unattributable_closing_portions=len(unattr), parents_in_multiple_streams=len(multi),
         mixed_parents_in_scope=sum(1 for p in parents if ls.roles[p.parent_id] == 'MIXED'), summary=cb.summarize(views, parents, ls), stability=cb.stability(views))
mp = [p for p in parents if ls.roles[p.parent_id] == 'MIXED']; S['mixed_parents_closing_qty_vs_all_fill_qty'] = dict(closing_qty=sum(p.qty for p in mp), fill_qty=sum(f.quantity for f in fills if f.parent_order_id in {p.parent_id for p in mp}))
ties = {}
for p in parents: ties.setdefault((p.stream, p.first_ts), 0); ties[(p.stream, p.first_ts)] += 1
S['c2_rule_sensitivity'] = cb.c2_rule_sensitivity(parents); S['parents_with_last_after_first'] = sum(1 for p in parents if p.last_ts > p.first_ts)
S['equal_first_ts_groups'] = sum(1 for v in ties.values() if v > 1); S['parents_in_equal_first_ts_groups'] = sum(v for v in ties.values() if v > 1)
files = {}
for m in ('C1', 'C2'): files.update(cb.files_for_method(views, m, ls))
man = dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), generated_at_head=provenance.git_sha(REPO), working_tree_dirty=bool(__import__('subprocess').run(['git', 'status', '--porcelain', '--', 'portfolio_engine/python', 'portfolio_engine/tools'], cwd=REPO, capture_output=True, text=True).stdout.strip()), execution_mode='HISTORICAL_OBSERVED_REPLAY', grouping_version=cb.GROUPING_VERSION, source_hashes=src, files={}, views={f'{m}_{g}s': v['parameter_hash'] for (m, g), v in views.items()},
           reproduce='python3 portfolio_engine/tools/m2c_closing_batches.py')
for name, text in files.items():
    path = os.path.join(OUT, name + '.gz')
    with open(path, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as z: z.write(text.encode())
    man['files'][name + '.gz'] = dict(sha256_of_text=hashlib.sha256(text.encode()).hexdigest(), rows=text.count('\n') - 1, bytes_gz=os.path.getsize(path))
json.dump(man, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1); json.dump(S, open(os.path.join(OUT, 'm2c_summary.json'), 'w'), indent=1, default=str)
for r in S['summary']: print(r['method'], r['threshold_s'], 'batches', r['batches'], 'parents', r['parents'], 'cps', r['closing_portions'], 'singletons', r['singleton_batches'], 'size', r['size']['median'], r['size']['p99'], r['size']['max'], 'dur max', r['duration_s']['max'], 'x', round(r['max_duration_over_threshold'], 1))
print(json.dumps(S['stability'], indent=0)[:1500]); print({k: v for k, v in S.items() if k not in ('summary', 'stability')})
