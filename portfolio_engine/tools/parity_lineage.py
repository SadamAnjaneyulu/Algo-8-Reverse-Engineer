"""Python vs C++ parity for the M2-B lineage files (observed layer, lifecycle, episodes, closing allocations, slices). Exact for integers/text; AVG decimals within 1e-6; bit-identity reported.
python3 portfolio_engine/tools/parity_lineage.py [--real-full]  -> reports/parity_lineage_report.json"""
import glob, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python')); sys.path.insert(0, HERE)
from pe import tsvio, replay as rp
from pe.schema import *
import parity
BIN = parity.BIN


def files_for(method): return ['observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv', f'ca_{method}.tsv', f'slices_{method}.tsv']


def case(events, instruments, mode, method, tie, tmp):
    ins = tsvio.read_instruments(instruments); fills = tsvio.read_events(events, ins); res = rp.replay(fills, ins, mode, method, tie, lineage=True); py = rp.lineage_files(res)
    d = os.path.join(tmp, 'lin'); os.makedirs(d, exist_ok=True)
    r = subprocess.run([BIN, '--events', events, '--instruments', instruments, '--mode', mode, '--method', method, '--tie', tie, '--lineage-dir', d], capture_output=True, text=True)
    if r.returncode != 0: return dict(ok=False, error=r.stderr.strip())
    ok = True; bit = True; worst = 0.0; bad = None
    for name in files_for(method):
        cpp = open(os.path.join(d, name)).read(); o, b, w, why = parity.compare_dumps(py[name], cpp)
        ok &= o; bit &= b; worst = max(worst, w or 0.0)
        if not o and bad is None: bad = f'{name}: {why}'
    return dict(ok=ok, bit_identical=bit, max_abs_decimal_diff=worst, mismatch=bad, events=len(fills))


def main():
    parity.build(); tmp = tempfile.mkdtemp(); real = '--real-full' in sys.argv; out = []
    sets = [(f, 'SYNTHETIC_TEST') for f in sorted(glob.glob(os.path.join(PE, 'fixtures', 'synthetic_m2', '*_events.tsv')))] + [(f, 'SYNTHETIC_TEST') for f in sorted(glob.glob(os.path.join(PE, 'fixtures', 'synthetic', '*_events.tsv')))] \
           + [(f, 'HISTORICAL_OBSERVED_REPLAY') for f in sorted(glob.glob(os.path.join(PE, 'fixtures', 'historical_sample', '*_events.tsv')))]
    if real: sets.append((os.path.join(PE, 'data_generated', 'historical_events.tsv'), 'HISTORICAL_OBSERVED_REPLAY'))
    for ev, mode in sets:
        ip = ev.replace('_events.tsv', '_instruments.tsv')
        for m in METHODS:
            for t in TIE_ORDERS: r = case(ev, ip, mode, m, t, tmp); r.update(fixture=os.path.relpath(ev, PE), method=m, tie=t); out.append(r)
    summ = dict(cases=len(out), ok=sum(x['ok'] for x in out), bit_identical=sum(bool(x.get('bit_identical')) for x in out), worst_decimal_diff=max(x.get('max_abs_decimal_diff') or 0 for x in out), real_full_included=real)
    os.makedirs(os.path.join(PE, 'reports'), exist_ok=True); json.dump(dict(summary=summ, cases=out), open(os.path.join(PE, 'reports', 'parity_lineage_report.json' if real else 'parity_lineage_report_fixtures_only.json'), 'w'), indent=1)
    print(json.dumps(summ)); [print('FAIL', x) for x in out if not x['ok']]; return 0 if summ['ok'] == summ['cases'] else 1


if __name__ == '__main__': sys.exit(main())
