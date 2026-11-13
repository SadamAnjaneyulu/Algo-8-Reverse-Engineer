"""Cross-language parity: identical event files through the Python reference and the C++ core; dumps and per-fill roles must agree.
Exact for every integer token (FIFO/LIFO and all counts); AVG decimals compared with an absolute tolerance of 1e-6 paise-units (floating point pools); bit-identity of dumps is reported separately.
python3 portfolio_engine/tools/parity.py [--real-full]   -> prints a summary, writes portfolio_engine/reports/parity_report.json"""
import glob, json, os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tsvio, replay as rp
from pe.schema import *
BUILD = os.path.join(PE, 'build'); BIN = os.path.join(BUILD, 'pe_replay'); TOL = 1e-6


def build():
    subprocess.check_call(['cmake', '-S', os.path.join(PE, 'cpp'), '-B', BUILD, '-DCMAKE_BUILD_TYPE=Release'], stdout=subprocess.DEVNULL); subprocess.check_call(['cmake', '--build', BUILD], stdout=subprocess.DEVNULL)


def compare_dumps(a, b):
    """returns (ok, bit_identical, max_abs_decimal_diff, first_mismatch)"""
    la, lb = a.splitlines(), b.splitlines()
    if len(la) != len(lb): return False, False, None, f'line count {len(la)} vs {len(lb)}'
    worst = 0.0
    for i, (x, y) in enumerate(zip(la, lb)):
        if x == y: continue
        tx, ty = x.split('\t'), y.split('\t')
        if len(tx) != len(ty): return False, False, None, f'line {i}: {x} | {y}'
        for u, v in zip(tx, ty):
            if u == v: continue
            if '.' in u and '.' in v:
                try: d = abs(float(u) - float(v))
                except ValueError: return False, False, None, f'line {i}: {x} | {y}'
                worst = max(worst, d)
                if d > TOL: return False, False, worst, f'line {i}: {x} | {y}'
            else: return False, False, worst, f'line {i}: {x} | {y}'
    return True, a == b, worst, None


def run_cpp(events, instruments, mode, method, tie, interval, dump, roles):
    r = subprocess.run([BIN, '--events', events, '--instruments', instruments, '--mode', mode, '--method', method, '--tie', tie, '--snapshot-interval', str(interval), '--dump', dump, '--roles', roles], capture_output=True, text=True)
    return r.returncode, r.stderr.strip()


def parity_case(events, instruments, mode, method, tie, interval=0, tmp=None):
    ins = tsvio.read_instruments(instruments); fills = tsvio.read_events(events, ins); t0 = time.time(); res = rp.replay(fills, ins, mode, method, tie, interval, False); tpy = time.time() - t0
    d, rr = os.path.join(tmp, 'd.tsv'), os.path.join(tmp, 'r.tsv'); t0 = time.time(); rc, err = run_cpp(events, instruments, mode, method, tie, interval, d, rr); tcpp = time.time() - t0
    if rc != 0: return dict(ok=False, error=err)
    ok, bit, worst, why = compare_dumps(res.dump, open(d).read()); roles_ok = rp.roles_tsv(res.roles) == open(rr).read()
    return dict(ok=ok and roles_ok, dump_ok=ok, roles_identical=roles_ok, bit_identical_dump=bit, max_abs_decimal_diff=worst, mismatch=why, events=len(fills), python_s=round(tpy, 3), cpp_s=round(tcpp, 3))


def main():
    build(); out = []; tmp = tempfile.mkdtemp(); real_full = '--real-full' in sys.argv
    sets = [(f, 'SYNTHETIC_TEST') for f in sorted(glob.glob(os.path.join(PE, 'fixtures', 'synthetic', '*_events.tsv')))] + [(f, 'HISTORICAL_OBSERVED_REPLAY') for f in sorted(glob.glob(os.path.join(PE, 'fixtures', 'historical_sample', '*_events.tsv')))]
    if real_full: sets.append((os.path.join(PE, 'data_generated', 'historical_events.tsv'), 'HISTORICAL_OBSERVED_REPLAY'))
    for ev, mode in sets:
        ip = ev.replace('_events.tsv', '_instruments.tsv')
        for method in METHODS:
            for tie in TIE_ORDERS:
                r = parity_case(ev, ip, mode, method, tie, 5000 if 'historical_events' in ev else 0, tmp); r.update(fixture=os.path.relpath(ev, PE), mode=mode, method=method, tie=tie); out.append(r)
    # invalid fixtures: both implementations must reject
    bad = []
    for ev in sorted(glob.glob(os.path.join(PE, 'fixtures', 'invalid', '*_events.tsv'))):
        ip = os.path.join(PE, 'fixtures', 'invalid', 'base_instruments.tsv')
        try: tsvio.read_instruments(ip); fills = tsvio.read_events(ev, tsvio.read_instruments(ip)); rp.replay(fills, tsvio.read_instruments(ip), 'SYNTHETIC_TEST'); py = 'ACCEPTED'
        except EngineError as e: py = 'REJECTED'
        rc, _ = run_cpp(ev, ip, 'SYNTHETIC_TEST', 'FIFO', 'src', 0, os.path.join(tmp, 'x'), os.path.join(tmp, 'y')); bad.append(dict(fixture=os.path.basename(ev), python=py, cpp='REJECTED' if rc == 2 else 'ACCEPTED', ok=py == 'REJECTED' and rc == 2))
    ip = os.path.join(PE, 'fixtures', 'invalid', 'bad_option_type_instruments.tsv'); ev = os.path.join(PE, 'fixtures', 'invalid', 'base_instruments.tsv')
    try: tsvio.read_instruments(ip); py = 'ACCEPTED'
    except EngineError: py = 'REJECTED'
    rc, _ = run_cpp(os.path.join(PE, 'fixtures', 'synthetic', 'open_close_full_events.tsv'), ip, 'SYNTHETIC_TEST', 'FIFO', 'src', 0, os.path.join(tmp, 'x'), os.path.join(tmp, 'y')); bad.append(dict(fixture='bad_option_type_instruments.tsv', python=py, cpp='REJECTED' if rc == 2 else 'ACCEPTED', ok=py == 'REJECTED' and rc == 2))
    summ = dict(cases=len(out), cases_ok=sum(x['ok'] for x in out), bit_identical=sum(bool(x.get('bit_identical_dump')) for x in out), roles_identical=sum(bool(x.get('roles_identical')) for x in out), worst_decimal_diff=max([x.get('max_abs_decimal_diff') or 0 for x in out]),
                invalid_cases=len(bad), invalid_ok=sum(x['ok'] for x in bad), real_full_included=real_full)
    os.makedirs(os.path.join(PE, 'reports'), exist_ok=True); json.dump(dict(summary=summ, cases=out, invalid=bad), open(os.path.join(PE, 'reports', 'parity_report.json' if real_full else 'parity_report_fixtures_only.json'), 'w'), indent=1)
    print(json.dumps(summ)); [print('FAIL', x) for x in out + bad if not x['ok']]
    return 0 if summ['cases_ok'] == summ['cases'] and summ['invalid_ok'] == summ['invalid_cases'] else 1


if __name__ == '__main__': sys.exit(main())
