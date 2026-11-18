"""Track E: independent manifest verification (read-only). For m2c/m2d (sha256_of_text over the gunzipped payload) and m2e (sha256 over text/bytes), recompute from the files on disk, list output files NOT covered by any manifest, and classify fields as deterministic vs runtime metadata.
usage: manifest_check.py <portfolio_engine dir>   -> JSON on stdout. Class: [INV]/[REPRO] (hashes of outputs prove the files match the manifest, not that the contents are correct)."""
import gzip, hashlib, json, os, sys
PE = sys.argv[1]; R = os.path.join(PE, 'reports'); out = {}
def sha(b): return hashlib.sha256(b).hexdigest()
for d in ('m2c_data', 'm2d_data'):
    m = json.load(open(os.path.join(R, d, 'manifest.json'))); rec = dict(manifest_keys=sorted(m), bad=[], ok=0, hash_basis='sha256 of UNCOMPRESSED payload text (gz bytes are not hashed; gz written with mtime=0)')
    for n, v in m['files'].items():
        p = os.path.join(R, d, n); raw = gzip.open(p).read(); good = sha(raw) == v['sha256_of_text'] and raw.count(b'\n') - 1 == v['rows'] and os.path.getsize(p) == v['bytes_gz']
        rec['ok'] += good
        if not good: rec['bad'].append(n)
    present = sorted(os.listdir(os.path.join(R, d))); rec['files_on_disk'] = present; rec['not_covered_by_manifest'] = [x for x in present if x not in m['files']]
    rec['runtime_metadata_fields'] = [k for k in ('created_utc', 'generated_at_head', 'working_tree_dirty') if k in m]; out[d] = rec
rec = dict(per_cycle={}); 
for c in sorted(os.listdir(os.path.join(R, 'm2e_data'))):
    cd = os.path.join(R, 'm2e_data', c)
    if not os.path.isdir(cd): continue
    m = json.load(open(os.path.join(cd, 'manifest.json'))); bad = []; ok = 0
    for n, v in m['files'].items():
        b = open(os.path.join(cd, n), 'rb').read(); good = sha(b) == v['sha256'] and len(b) == v['bytes'] and b.count(b'\n') - 1 == v['rows']; ok += good
        if not good: bad.append(n)
    present = sorted(f for f in os.listdir(cd)); rec['per_cycle'][c] = dict(ok=ok, bad=bad, not_covered_by_manifest=[x for x in present if x not in m['files']], runtime_metadata_fields=[k for k in ('created_utc', 'generated_at_head') if k in m], has_created_utc='created_utc' in m)
out['m2e_data'] = rec
fm = {}
for c in sorted(os.listdir(os.path.join(R, 'm2e_figures'))):
    fd = os.path.join(R, 'm2e_figures', c)
    for mn in ('figure_manifest.json', 'case_figure_manifest.json'):
        M = json.load(open(os.path.join(fd, mn))); tot = 0; bad = []; keys = set()
        for f in M['figures']:
            keys |= set(f)
            for x in [f] + f.get('additional_data_csv', []):
                p = x.get('data_csv')
                if p:
                    fp = os.path.join(PE, p)
                    sh = x.get('data_csv_sha256') or x.get('sha256')
                    if not os.path.exists(fp): bad.append('MISSING ' + p); continue
                    if sh: tot += 1; bad += [] if sha(open(fp, 'rb').read()) == sh else [p]
        fm[f'{c}/{mn}'] = dict(csv_hash_checked=tot, bad=bad, figure_keys=sorted(keys), top_level_keys=sorted(M))
out['m2e_figures'] = fm; print(json.dumps(out, indent=1))
