"""Track E: Python vs C++ byte-for-byte parity on raw-derived fills (full ledger + the two frozen cycles) from the TP-01 ledger via the repo generator, with a fresh C++ build.
[XLANG] only (both engines implement one written spec); the INPUT is raw-derived (TP-01 parquet whose source hash is checked against Trades_GKOHNP140.csv). usage: parity_real.py --root <scratch tree> --work <dir>"""
import argparse, json, os, subprocess, sys, itertools, time
ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--work', required=True); a = ap.parse_args()
PE = os.path.join(a.root, 'portfolio_engine'); sys.path.insert(0, os.path.join(PE, 'python')); os.makedirs(a.work, exist_ok=True)
from pe import tsvio, replay as rp
from pe.schema import *
from pe.generators import historical as H
BIN = os.path.join(PE, 'build', 'pe_replay'); MODE = 'HISTORICAL_OBSERVED_REPLAY'; out = []
for tag, cyc in (('full', None), ('NIFTY_2026-06-30', ('NIFTY', '2026-06-30')), ('SENSEX_2026-07-16', ('SENSEX', '2026-07-16'))):
    ins, fills, src = H.generate(a.root, cyc); ev = os.path.join(a.work, tag + '_events.tsv'); ip = os.path.join(a.work, tag + '_instruments.tsv'); tsvio.write_events(ev, fills); tsvio.write_instruments(ip, ins)
    ev_back = tsvio.read_events(ev, tsvio.read_instruments(ip)); roundtrip = ev_back == fills or [f.__dict__ if hasattr(f, '__dict__') else f for f in ev_back] == [f for f in fills]
    for method, tie in itertools.product(METHODS, TIE_ORDERS if tag == 'full' else ('src',)):
        interval = 5000 if tag == 'full' else 0; t0 = time.time(); R = rp.replay(fills, ins, MODE, method, tie, interval, False, True); tp = time.time() - t0
        py = {'dump.tsv': R.dump.encode(), 'roles.tsv': rp.roles_tsv(R.roles).encode(), **{k: v.encode() for k, v in rp.lineage_files(R).items()}}
        d = os.path.join(a.work, f'{tag}_{method}_{tie}'); os.makedirs(d, exist_ok=True); t0 = time.time()
        r = subprocess.run([BIN, '--events', ev, '--instruments', ip, '--mode', MODE, '--method', method, '--tie', tie, '--snapshot-interval', str(interval), '--dump', d + '/dump.tsv', '--roles', d + '/roles.tsv', '--lineage-dir', d, '--strict'], capture_output=True, text=True); tc = time.time() - t0
        if r.returncode: out.append(dict(tag=tag, method=method, tie=tie, ok=False, err=r.stderr[:200])); continue
        bad = [n for n in py if open(os.path.join(d, n), 'rb').read() != py[n]]
        out.append(dict(tag=tag, method=method, tie=tie, fills=len(fills), byte_identical=not bad, differing=bad, files=len(py), py_s=round(tp, 2), cpp_s=round(tc, 2), roundtrip_events_equal=roundtrip, tsv_event_roundtrip_ok=len(ev_back) == len(fills),
                        dump_sha_py=__import__('hashlib').sha256(py['dump.tsv']).hexdigest()[:16]))
        print(out[-1], flush=True)
json.dump(out, open(os.path.join(a.work, 'parity_real_result.json'), 'w'), indent=1); print('ALL IDENTICAL' if all(x.get('byte_identical') for x in out) else 'DIFFERENCES')
