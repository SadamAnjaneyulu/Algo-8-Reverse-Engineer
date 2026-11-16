"""Track E system-level mutation runner. Mutates a hard-linked COPY of a scratch mirror, runs the existing suite (stop at first failure), records killed/survived.
usage: mut_run.py --mirror <scratch tree> --work <dir> --id E01 [--env K=V ...] [--tests <pytest args>]   (never touches the repository)"""
import argparse, json, os, shutil, subprocess, sys, time
MUT = {
 'E01': ('python/pe/closing_batches.py', ":{stream[2]}:{n:03d}'", ":{stream[2]}:001'", 'batch-id collision: sequence number dropped from CLOSING_BATCH ids'),
 'E02': ('python/pe/lineage.py', "self.events.append((f'LE:{episode_id}:{n}'", "self.events.append((f'LE:{episode_id}:1'", 'lifecycle event-id collision: LE id ignores the sequence number'),
 'E03': ('python/pe/replay.py', "key=lambda f: (f.timestamp_s, tk(f.side), f.source_row_id, f.fill_id)", "key=lambda f: (f.timestamp_s, tk(f.side), -f.source_row_id, f.fill_id)", 'sort-order change: source_row tie-break reversed'),
 'E04': ('python/pe/replay.py', "def _fmt(x, avg): return f'{x:.6f}' if avg else str(int(x))", "def _fmt(x, avg): return f'{x:.4f}' if avg else str(int(x))", 'float formatting: AVG decimals 6 -> 4 places (Python only)'),
 'E05': ('tools/m2c_closing_batches.py', "dict(sha256_of_text=hashlib.sha256(text.encode()).hexdigest()", "dict(sha256_of_text=hashlib.sha256(text.rstrip().encode()).hexdigest()", 'manifest hash computed over the wrong bytes (trailing newline stripped)'),
 'E06': ('python/pe/closing_batches.py', "'n_parents', 'n_closing_portions', 'total_closing_qty'", "'n_closing_portions', 'n_parents', 'total_closing_qty'", 'TSV column reorder in closing_batches_*.tsv'),
 'E07': ('python/pe/provenance.py', "try: return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd, stderr=subprocess.DEVNULL).decode().strip()", "try: return '0' * 40", 'provenance sha wrong: git_sha() returns a constant'),
 'E08': ('python/pe/tsvio.py', "if r['schema_version'] != SCHEMA_FILL: raise EventValidationError(f'{path}:{n}: schema_version {r[\"schema_version\"]!r}')", "pass", 'schema_version not checked by the Python event reader (version bump undetected)'),
 'E09': ('python/pe/schema.py', "def ist_day(ts): return (ts + IST_OFFSET_S) // 86400", "def ist_day(ts):\n    import time\n    t = time.localtime(ts); return days_from_civil(t.tm_year, t.tm_mon, t.tm_mday)", 'timezone via machine local time instead of the fixed +05:30 offset (Python ist_day)'),
 'E11': ('python/pe/closing_batches.py', "    for stream in sorted(streams):\n        ps = sorted", "    for stream in set(streams):\n        ps = sorted", 'nondeterministic ordering: set iteration over streams in build_view'),
 'E12': ('python/pe/lineage.py', "n = self._ca_n.get(f.fill_id, 0) + 1; self._ca_n[f.fill_id] = n;", "n = 1; self._ca_n[f.fill_id] = n;", 'CA id collision: second allocation of one closing fill reuses id :1'),
 'E13': ('python/pe/forensics.py', "def ist_str(ts): return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts + IST))", "def ist_str(ts): return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))", 'IST display strings lose the +05:30 offset (UTC shown as IST)'),
 'E14': ('tools/m2e_build.py', "man['files'][n] = dict(sha256=F.sha(t)", "man['files'][n] = dict(sha256=F.sha(t[:-1])", 'm2e manifest hash over the wrong bytes (last byte dropped)'),
 'E15': ('python/pe/generators/historical.py', "Fill(f'F{int(r.src_row):06d}'", "Fill(f'F{int(r.src_row):d}'", 'fill-id format change (zero padding removed)'),
 'E16': ('python/pe/schema.py', "IST_OFFSET_S = 19800", "IST_OFFSET_S = 0", 'IST offset constant wrong (0) in Python schema'),
 'E17': ('cpp/include/pe/types.hpp', "constexpr i64 kIstOffsetS = 19800;", "constexpr i64 kIstOffsetS = 0;", 'IST offset constant wrong (0) in the C++ core (rebuild required)'),
 'E18': ('cpp/include/pe/types.hpp', 'std::snprintf(b, sizeof b, "%.6f", x)', 'std::snprintf(b, sizeof b, "%.5f", x)', 'C++ AVG decimal formatting 6 -> 5 places (rebuild required)'),
 'E19': ('python/pe/lineage.py', "return '\\n'.join(L) + '\\n'\n\n\ndef lifecycle_tsv", "return '\\n'.join(L)\n\n\ndef lifecycle_tsv", 'dropped trailing newline in observed_allocations.tsv (Python)'),
}
ap = argparse.ArgumentParser(); ap.add_argument('--mirror', required=True); ap.add_argument('--work', required=True); ap.add_argument('--id', required=True); ap.add_argument('--env', action='append', default=[]); ap.add_argument('--tests', default='portfolio_engine/tests'); ap.add_argument('--tag', default='')
a = ap.parse_args(); f, old, new, desc = MUT[a.id]; name = a.id + a.tag; d = os.path.join(a.work, name); shutil.rmtree(d, ignore_errors=True); subprocess.check_call(['cp', '-al', a.mirror, d])
tgt = os.path.join(d, 'portfolio_engine', f); src = open(tgt).read(); assert src.count(old) == 1, f'{a.id}: pattern occurs {src.count(old)} times'
os.unlink(tgt); open(tgt, 'w').write(src.replace(old, new))
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1'); [env.__setitem__(*e.split('=', 1)) for e in a.env]
if f.startswith('cpp/'):
    bd = os.path.join(d, 'portfolio_engine', 'build'); shutil.rmtree(bd); subprocess.check_call(['cmake', '-S', os.path.join(d, 'portfolio_engine', 'cpp'), '-B', bd], stdout=subprocess.DEVNULL); subprocess.check_call(['cmake', '--build', bd, '-j2'], stdout=subprocess.DEVNULL)
t0 = time.time(); r = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', '-x', '-q', '-rf', '--tb=line'] + a.tests.split(), cwd=d, env=env, capture_output=True, text=True); dt = time.time() - t0
tail = r.stdout.strip().splitlines()[-14:]; failed = [l for l in r.stdout.splitlines() if l.startswith('FAILED') or l.startswith('ERROR')]
res = dict(id=name, change=desc, file=f, rc=r.returncode, killed=r.returncode != 0, seconds=round(dt), failed=failed[:6], tail=tail, env=a.env); os.makedirs(os.path.join(a.work, '_results'), exist_ok=True)
json.dump(res, open(os.path.join(a.work, '_results', name + '.json'), 'w'), indent=1); print(json.dumps({k: res[k] for k in ('id', 'killed', 'seconds', 'failed')}, indent=0)[:900])
