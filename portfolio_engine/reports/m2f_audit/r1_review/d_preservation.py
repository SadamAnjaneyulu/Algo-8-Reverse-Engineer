"""Task D: independent preservation check. Hash every file in the author's baseline at working tree (HEAD) and
also compare baseline against git blobs at 562d7eb6 (is the baseline itself genuine?)."""
import json, hashlib, subprocess, os, sys, collections
R = '/home/user/Algo-8-Reverse-Engineer'
base = json.load(open(f'{R}/portfolio_engine/reports/m2f_audit/r1/baseline_sha256_before_R1.json'))
B = base['sha256']
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
out = {'baseline_files': len(B), 'missing_at_worktree': [], 'differs_worktree': [], 'baseline_vs_git_blob_562d7eb6_mismatch': [], 'ls_tree_not_in_baseline': []}
for p, h in B.items():
    fp = f'{R}/{p}'
    if not os.path.exists(fp): out['missing_at_worktree'].append(p); continue
    if sha(fp) != h: out['differs_worktree'].append(p)
# genuineness of baseline: git blob at 562d7eb6
tree = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '562d7eb6'], cwd=R).decode().split('\n')
tree = [t for t in tree if t.startswith(('portfolio_engine/', 'tp_reconstruction/')) or t == 'Trades_GKOHNP140.csv']
out['ls_tree_files_562d7eb6'] = len(tree)
for t in tree:
    if t not in B: out['ls_tree_not_in_baseline'].append(t); continue
    data = subprocess.run(['git', 'show', f'562d7eb6:{t}'], cwd=R, capture_output=True).stdout
    if hashlib.sha256(data).hexdigest() != B[t]: out['baseline_vs_git_blob_562d7eb6_mismatch'].append(t)
# classify differing
def cls(p):
    if p.endswith('manifest.json') and ('m2c_data' in p or 'm2d_data' in p or 'm2e_data' in p): return 'delivered manifest'
    if p.startswith('portfolio_engine/python/') : return 'code'
    if p.startswith('portfolio_engine/tests/'): return 'test'
    if p.startswith('portfolio_engine/tools/'): return 'tool'
    if p.endswith('.md'): return 'doc(md)'
    return 'OTHER'
out['differs_classified'] = {p: cls(p) for p in out['differs_worktree']}
out['differs_OTHER'] = [p for p, c in out['differs_classified'].items() if c == 'OTHER']
out['delivered_output_exts_changed'] = [p for p in out['differs_worktree'] if p.endswith(('.tsv.gz', '.tsv', '.csv', '.png', '.parquet'))]
out['summary_json_changed'] = [p for p in out['differs_worktree'] if p.endswith('summary.json') or p.endswith(('coverage.json','case_studies.json','figure_manifest.json','case_figure_manifest.json'))]
out['raw_csv_identical'] = sha(f'{R}/Trades_GKOHNP140.csv') == B['Trades_GKOHNP140.csv']
out['tp_reconstruction_files'] = sum(1 for k in B if k.startswith('tp_reconstruction/'))
out['tp_reconstruction_differing'] = [p for p in out['differs_worktree'] if p.startswith('tp_reconstruction/')]
# the files in the baseline for tp_reconstruction exist and match (above); also check untracked/new files under tp_reconstruction
newtp = []
for root, d, fs in os.walk(f'{R}/tp_reconstruction'):
    if '__pycache__' in root: continue
    for f in fs:
        rel = os.path.relpath(os.path.join(root, f), R)
        if rel not in B: newtp.append(rel)
out['tp_reconstruction_files_not_in_baseline'] = newtp
# files added since baseline (git)
out['git_added_since_baseline'] = subprocess.check_output(['git','diff','--name-status','--diff-filter=AD','562d7eb6','HEAD'],cwd=R).decode().strip().split('\n')
out['git_status_porcelain'] = subprocess.check_output(['git','status','--porcelain'],cwd=R).decode().strip().split('\n')
json.dump(out, open('/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/r1_review/d_preservation_result.json', 'w'), indent=1)
print(json.dumps({k: (v if not isinstance(v, (list, dict)) or len(v) < 40 else f'{type(v).__name__}[{len(v)}]') for k, v in out.items()}, indent=1))
