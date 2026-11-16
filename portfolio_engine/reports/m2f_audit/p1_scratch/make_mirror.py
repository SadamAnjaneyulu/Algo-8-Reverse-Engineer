"""Scratch mirror for the R1-C completeness check. Copies tracked portfolio_engine files to <dest>, symlinks the raw csv and tp_reconstruction, and patches ONLY the mirror so that the engine order of the
delivered generators is taken from env PE_TIE ('src' control or 'per_contract_id_sequence'). The repository itself is never modified."""
import os, shutil, subprocess, sys
REPO = '/home/user/Algo-8-Reverse-Engineer'; dest = sys.argv[1]
shutil.rmtree(dest, ignore_errors=True); P = dest + '/portfolio_engine'; os.makedirs(P)
files = subprocess.run(['git', 'ls-files', 'portfolio_engine'], cwd=REPO, capture_output=True, text=True).stdout.split('\n')
for f in files:
    if not f or not os.path.isfile(REPO + '/' + f): continue
    os.makedirs(os.path.dirname(dest + '/' + f), exist_ok=True); shutil.copy(REPO + '/' + f, dest + '/' + f)
os.symlink(REPO + '/tp_reconstruction', dest + '/tp_reconstruction'); os.symlink(REPO + '/Trades_GKOHNP140.csv', dest + '/Trades_GKOHNP140.csv')
def sub(rel, old, new, count=1):
    s = open(P + '/' + rel).read(); assert s.count(old) >= 1, (rel, old[:50]); open(P + '/' + rel, 'w').write(s.replace(old, new) if count == 0 else s.replace(old, new, count))
TIE = "os.environ.get('PE_TIE', 'src')"
KEYED = lambda fills_var, repo_var='REPO': f"H.attach_tie_keys({repo_var}, {fills_var}, {TIE})"
# forensics.Cycle
sub('python/pe/forensics.py', "self.ls = LineageSet(self.fills, self.ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')", f"import os; self.fills = H.attach_tie_keys(repo, self.fills, {TIE}); self.ls = LineageSet(self.fills, self.ins, 'HISTORICAL_OBSERVED_REPLAY', {TIE})")
# builders: engine order from env; primary guard removed ONLY in the mirror
for rel in ('tools/m2c_closing_batches.py', 'tools/m2d_wing_body.py', 'tools/m2e_build.py'):
    s = open(P + '/' + rel).read()
    s = s.replace("'HISTORICAL_OBSERVED_REPLAY', 'src')", "'HISTORICAL_OBSERVED_REPLAY', os.environ.get('PE_TIE', 'src'))")
    s = s.replace("ls = LineageSet(fills, ins,", "fills = H.attach_tie_keys(REPO, fills, os.environ.get('PE_TIE', 'src')); ls = LineageSet(fills, ins,")
    s = s.replace("full = LineageSet(fills_all, ins_all,", "fills_all = H.attach_tie_keys(REPO, fills_all, os.environ.get('PE_TIE', 'src')); full = LineageSet(fills_all, ins_all,")
    import re
    s = re.sub(r"tp\.require_primary\([^;]*?\)(;|\n)", lambda m: 'None' + m.group(1), s)
    open(P + '/' + rel, 'w').write(s)

# ---- mirror-only: keyed policies permute fills WITHIN each (instrument, second) group inside the slots the baseline order gives that group (cross-instrument interleaving stays as in the baseline)
sub('python/pe/replay.py', "        return sorted(fills, key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))",
"""        base = sorted(fills, key=lambda f: (f.timestamp_s, f.source_row_id, f.fill_id)); slots = {}
        for i, f in enumerate(base): slots.setdefault((f.timestamp_s, f.instrument_id), []).append(i)
        out = list(base)
        for k, idx in slots.items():
            grp = sorted((base[i] for i in idx), key=lambda f: (f.tie_key, f.source_row_id, f.fill_id))
            for i, f in zip(idx, grp): out[i] = f
        return out""")
_fp = P + '/python/pe/forensics.py'; _s = open(_fp).read(); import re as _re
_s, _n = _re.subn(r"sorted\(c\.fills, key=lambda f: \(f\.timestamp_s, f\.source_row_id\)\)", "__import__('pe.replay', fromlist=['x']).order_events(c.fills, __import__('os').environ.get('PE_TIE', 'src'))", _s); assert _n >= 3, _n; open(_fp, 'w').write(_s)
print('mirror ready', dest)
