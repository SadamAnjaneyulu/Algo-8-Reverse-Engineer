"""python -m pe.cli replay --events E --instruments I --mode MODE --method FIFO --tie src [--snapshot-interval N] [--out-dir DIR] [--dump F] [--roles F]"""
import argparse, json, os, sys
from . import tsvio, replay as rp, provenance


def _run_cpp(a):
    import subprocess, tempfile
    from .schema import WARN_CODES
    binary = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'build', 'pe_replay'); tmp = tempfile.mkdtemp(); d = os.path.join(tmp, 'dump.tsv'); r = os.path.join(tmp, 'roles.tsv')
    p = subprocess.run([binary, '--events', a.events, '--instruments', a.instruments, '--mode', a.mode, '--method', a.method, '--tie', a.tie, '--snapshot-interval', str(a.snapshot_interval), '--dump', d, '--roles', r] + (['--strict'] if a.strict else []), capture_output=True, text=True)
    if p.returncode != 0: raise SystemExit(p.stderr.strip())
    res = rp.RunResult(); res.dump = open(d).read(); res.roles = []; res.checks = ['(checked inside the C++ core)']; res.meta = {}; res.warnings = {}
    for l in res.dump.splitlines():
        t = l.split('\t')
        if t[0] == 'META': res.meta[t[1]] = t[2]
        elif t[0] == 'WARN': res.warnings[t[1]] = int(t[2])
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True); r = sub.add_parser('replay')
    r.add_argument('--events', required=True); r.add_argument('--instruments', required=True); r.add_argument('--mode', required=True); r.add_argument('--method', default='FIFO'); r.add_argument('--tie', default='src')
    r.add_argument('--snapshot-interval', type=int, default=0); r.add_argument('--strict', action='store_true'); r.add_argument('--out-dir'); r.add_argument('--dump'); r.add_argument('--roles'); r.add_argument('--engine', choices=['python', 'cpp'], default='python')
    a = ap.parse_args(argv); ins = tsvio.read_instruments(a.instruments); fills = tsvio.read_events(a.events, ins)
    if a.engine == 'python': res = rp.replay(fills, ins, a.mode, a.method, a.tie, a.snapshot_interval, a.strict)
    else: res = _run_cpp(a)
    if a.dump: open(a.dump, 'w', newline='\n').write(res.dump)
    if a.roles and a.engine == 'python': open(a.roles, 'w', newline='\n').write(rp.roles_tsv(res.roles))
    if a.out_dir:
        cfg = dict(mode=a.mode, method=a.method, tie_order=a.tie, snapshot_interval=a.snapshot_interval)
        m = provenance.manifest(res, events_path=a.events, instruments_path=a.instruments, config=cfg, implementation=a.engine, reproduce=' '.join(['python3 -m pe.cli'] + (argv or sys.argv[1:])))
        d = provenance.run_dir(a.out_dir, a.mode, m['run_id']); open(os.path.join(d, 'state_dump.tsv'), 'w', newline='\n').write(res.dump); open(os.path.join(d, 'manifest.json'), 'w').write(json.dumps(m, indent=2, sort_keys=True))
        print(d)
    return 0


if __name__ == '__main__': sys.exit(main())
