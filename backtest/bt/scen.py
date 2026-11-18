"""Turns one cycle's real data into an engine scenario (.scn), runs the UNMODIFIED Python engine and the C++ runner on the same text, and returns outputs + a parity flag."""
import os, random, subprocess, sys, tempfile
from datetime import datetime, timedelta
PC = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/construction'
if PC + '/python' not in sys.path: sys.path.insert(0, PC + '/python')
from pc.scenario import Scenario          # noqa: E402
from pc.engine import Simulation          # noqa: E402
PC_RUN = PC + '/build/pc_run'; EPOCH0 = datetime(1970, 1, 1)
PLUGINS = [('capital_stop', '1.0.0'), ('basket_cut', '1.0.0'), ('basket_reentry', '1.0.0'), ('scripted_actions', '1.0.0')]


def epoch(day, hm, sec=0): return int((datetime.fromisoformat(f'{day} {hm}:{sec:02d}') - timedelta(hours=5, minutes=30) - EPOCH0).total_seconds())
def paise(x): return int(round(x * 100 / 5)) * 5
def lot_of(c): return c['lot_d1'] if c['lot_d1'] > 1 else c['lot_d0']
def iid(c, lid): L = c['legs'][lid]; return f"{c['und']}|{c['expiry']}|{L['cp']}|{L['strike']}"


def end_hm(variant): return '15:25' if variant == 'FLATTEN_1525' else '15:30'


def make_text(c, cfg, variant, lots=3, drop_frac=0.0, drop_seed=0, name=None):
    """cfg = {'cut': dict|None, 'reentry': dict|None, 'stop': dict|None}; plugin config values are written as given (strings/ints)."""
    lot = lot_of(c); rng = random.Random(drop_seed); L = ['#PC_SCENARIO v1', f'META\tname\t{name or c["und"] + "_" + c["expiry"]}', 'META\tevidence\tSYNTHETIC_TEST_ONLY',
                                                       'META\tdescription\tHISTORICAL_BREEZE_REPLAY (the engine evidence stamp is a fixed string)', 'META\tmethod\tFIFO']
    for lid in sorted(c['legs']): L.append(f'INST\t{iid(c, lid)}\t{lot}')
    for n, v in PLUGINS:
        if n == 'capital_stop' and not cfg.get('stop'): continue          # the baseline engine never sees the extra plugin
        L.append(f'PLUGIN\t{n}\t{v}\t{1 if (n == "scripted_actions" or cfg.get({"capital_stop": "stop", "basket_cut": "cut", "basket_reentry": "reentry"}[n])) else 0}')
    for key, pl in (('stop', 'capital_stop'), ('cut', 'basket_cut'), ('reentry', 'basket_reentry')):
        for k, v in sorted((cfg.get(key) or {}).items()): L.append(f'CONFIG\t{pl}\t{k}\t{v}')
    first_seed = None
    for i, lid in enumerate(sorted(c['legs'])):
        e = c['legs'][lid]; ts = epoch(c['d1'], e['hm']); first_seed = ts if first_seed is None else min(first_seed, ts)
        L.append(f'LEG\tS{i + 1}-{lid}\tB1\t{lid}\t{iid(c, lid)}\t{e["side"]}\t{lots * lot}\t{paise(e["open"])}\t{ts}')
    end_ts = epoch(c['d0'], end_hm(variant)); marks = []; ticks = set()
    for lid in sorted(c['legs']):
        for day, fr in ((c['d1'], c['frames'][lid][0]), (c['d0'], c['frames'][lid][1])):
            for r in fr.itertuples():
                if not ('09:15' <= r.hm <= '15:29'): continue
                ts = epoch(day, r.hm) + 60
                if ts > end_ts or (drop_frac and rng.random() < drop_frac): continue
                marks.append(f'MARK\t{ts}\t{iid(c, lid)}\t{paise(r.close)}')
    for day in (c['d1'], c['d0']):
        for m in range(555, 930):
            ts = epoch(day, '%02d:%02d' % (m // 60, m % 60)) + 60
            if first_seed + 60 <= ts <= end_ts and ts >= epoch(c['d1'], '09:17'): ticks.add(ts)
    L += marks + [f'TICK\t{t}' for t in sorted(ticks)]
    return '\n'.join(L) + '\n'


def run_python(text):
    sim = Simulation(Scenario.parse(text)).run(); return sim, sim.files()


def run_cpp(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'c.scn'); open(p, 'w', newline='\n').write(text); o = os.path.join(d, 'out'); r = subprocess.run([PC_RUN, p, o], capture_output=True, text=True)
        if r.returncode != 0: return None, r.stderr.strip()[-300:]
        return {f: open(os.path.join(o, f), encoding='utf-8', newline='').read() for f in os.listdir(o)}, ''


def run(c, cfg, variant, lots=3, check_cpp=True, **kw):
    text = make_text(c, cfg, variant, lots, **kw); sim, files = run_python(text); res = dict(text_len=len(text), files=files, fills=[(f.fill_id, f.instrument_id, f.timestamp_s if hasattr(f, 'timestamp_s') else f.ts, f.side, f.quantity, f.price_paise) for f in sim.fills], parity=None)
    if check_cpp:
        cf, err = run_cpp(text); res['parity'] = (cf is not None and cf == files); res['parity_detail'] = err if cf is None else ('' if res['parity'] else ','.join(k for k in files if files[k] != cf.get(k)))
    return res
