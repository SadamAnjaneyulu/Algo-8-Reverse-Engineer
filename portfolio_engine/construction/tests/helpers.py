"""Tiny scenario builder for hand-written tests (same layout as the C++ tests)."""
import os, subprocess, shutil, tempfile
from pc.scenario import Scenario
from pc.engine import Simulation

T0 = 1767584760
SCE, SPE, WCE, WPE = 'NIFTY|2026-01-08|CE|24000', 'NIFTY|2026-01-08|PE|24000', 'NIFTY|2026-01-08|CE|24800', 'NIFTY|2026-01-08|PE|23200'
CUTID = f'basket_cut|{T0 + 600}|B1|SCE|CUT'


def L(*v): return '\t'.join(str(x) for x in v) + '\n'
def scn(body, evidence='SYNTHETIC_TEST_ONLY'):
    s = '#PC_SCENARIO v1\n' + L('META', 'name', 't') + L('META', 'evidence', evidence)
    for i in (SCE, SPE, WCE, WPE): s += L('INST', i, 65)
    s += L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 195, 10000, T0) + L('LEG', 'f2', 'B1', 'SPE', SPE, -1, 195, 9000, T0) + L('LEG', 'f3', 'B1', 'WCE', WCE, 1, 195, 200, T0) + L('LEG', 'f4', 'B1', 'WPE', WPE, 1, 195, 250, T0)
    return s + body
def plugins(cut=True, re=True, scr=True): return L('PLUGIN', 'basket_cut', '1.0.0', int(cut)) + L('PLUGIN', 'basket_reentry', '1.0.0', int(re)) + L('PLUGIN', 'scripted_actions', '1.0.0', int(scr))
def cfg(p, k, v): return L('CONFIG', p, k, v)
def risk(k, v): return L('RISK', k, v)
def mark(off, i, px): return L('MARK', T0 + off, i, px)
def tick(off): return L('TICK', T0 + off)
def action(off, aid, typ, leg, qty, parent='', info_off=0, plugin='', basket='B1'): return L('ACTION', T0 + off, aid, plugin, '1.0.0' if plugin else '', typ, basket, leg, qty, parent, T0 + off + info_off, '')


def example_body(re_cfg='', risk_lines=''):
    """the 195-unit example; `re_cfg` / `risk_lines` may re-state settings (they override the example's own; a setting appears once in the file)"""
    base = {('basket_cut', 'policy'): 'MARK_ADVERSE_MOVE', ('basket_cut', 'trigger_bp'): 2000, ('basket_cut', 'scope'): 'LEG', ('basket_cut', 'leg_side_filter'): 'SHORT', ('basket_cut', 'option_type_filter'): 'CE', ('basket_cut', 'units'): 65,
            ('basket_reentry', 'cooldown_s'): 600, ('basket_reentry', 'price_condition'): 'WITHIN_BAND', ('basket_reentry', 'band_bp'): 1500}
    for line in re_cfg.split('\n'):
        if line: _, p, k, v = line.split('\t'); base[(p, k)] = v
    return (plugins() + ''.join(cfg(p, k, v) for (p, k), v in base.items()) + risk_lines
            + mark(0, SCE, 10000) + mark(300, SCE, 11000) + mark(600, SCE, 12500) + mark(900, SCE, 12000) + mark(1200, SCE, 11000) + mark(1500, SCE, 10800)
            + mark(0, SPE, 9000) + mark(0, WCE, 200) + mark(0, WPE, 250) + ''.join(tick(o) for o in (0, 300, 600, 900, 1200, 1500)))


def run(text, extra=None, registry=None):
    from pc.engine import build_registry
    sc = Scenario.parse(text); sim = Simulation(sc, registry or build_registry(sc, extra)); return sim, sim.files()
def rows(tsv):
    r = [l.split('\t') for l in tsv.split('\n') if l and not l.startswith('#')]; return r[0], r[1:]
def table(tsv):
    h, r = rows(tsv); return [dict(zip(h, x)) for x in r]
def kv(files, key): return {r['key']: r['value'] for r in table(files['summary.tsv'])}.get(key)


def clean_refusal(stderr):
    """True when a command-line run was refused the intended way: the LAST stderr line is the program's own `ERROR: ...` message and no traceback frame points into
    this project's source. Output from the Python environment itself (site hooks, warnings) may precede it and is ignored."""
    lines = [l for l in stderr.strip().split('\n') if l.strip()]
    if not lines or not lines[-1].startswith('ERROR:'): return False
    return not any('File "' in l and ('/pc/' in l or '\\pc\\' in l or 'scenario.py' in l or 'engine.py' in l) for l in lines)


# ---------------------------------------------------------------- C++ build (shared by the parity tests)
_BUILD = {}
def cpp_build():
    if 'dir' in _BUILD: return _BUILD['dir']
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); d = tempfile.mkdtemp(prefix='pcbuild_')
    subprocess.check_call(['cmake', '-S', os.path.join(root, 'cpp'), '-B', d, '-DCMAKE_BUILD_TYPE=Release'], stdout=subprocess.DEVNULL); subprocess.check_call(['cmake', '--build', d], stdout=subprocess.DEVNULL)
    _BUILD['dir'] = d; return d
def cpp_run(scn_path, out_dir, make_dir=True):
    if make_dir: os.makedirs(out_dir, exist_ok=True)
    return subprocess.run([os.path.join(cpp_build(), 'pc_run'), scn_path, out_dir], capture_output=True, text=True)
