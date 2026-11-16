"""Run manifest: ids, hashes, git sha, mode, warnings, reproduction command. Runs are written to runs/<mode>/<run_id>/ so modes never share a directory."""
import hashlib, json, os, subprocess, time


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def sha256_text(s): return hashlib.sha256(s.encode()).hexdigest()


def git_sha(cwd=None):
    try: return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd, stderr=subprocess.DEVNULL).decode().strip()
    except Exception: return 'UNAVAILABLE'


def code_fingerprint(pe_root):
    """sha256 identifying the GENERATING CODE of a portfolio_engine tree (M2-F E-D02; stamping it into manifests is a proposal, not done here).
    Covers python/pe/**/*.py (recursive) and tools/*.py (not recursive); __pycache__, tests, cpp, docs, fixtures and reports are NOT covered.
    Files are taken in sorted order of their POSIX relative path; for each the hash is fed `<relpath>\\0<byte length>\\0<raw bytes>`, so renaming, adding or removing a file changes the result,
    and concatenation cannot make two different trees collide. Raw bytes: no newline normalisation (a CRLF checkout fingerprints differently from an LF one)."""
    from .schema import EngineError
    root = os.path.abspath(pe_root); files = []
    for base, recursive in (('python/pe', True), ('tools', False)):
        top = os.path.join(root, *base.split('/'))
        if not os.path.isdir(top): raise EngineError(f'code_fingerprint: {top} is not a directory (pe_root must be the portfolio_engine directory)')
        for d, dirs, names in os.walk(top):
            dirs[:] = sorted(x for x in dirs if x != '__pycache__') if recursive else []
            files += [os.path.relpath(os.path.join(d, n), root).replace(os.sep, '/') for n in names if n.endswith('.py')]
    h = hashlib.sha256()
    for rel in sorted(files):
        with open(os.path.join(root, *rel.split('/')), 'rb') as f: b = f.read()
        h.update(rel.encode() + b'\0' + str(len(b)).encode() + b'\0' + b)
    return h.hexdigest()


def manifest(result, *, events_path, instruments_path, extra_sources=None, config, implementation, reproduce):
    src = {'events_sha256': sha256_file(events_path), 'instruments_sha256': sha256_file(instruments_path)}; src.update(extra_sources or {})
    cfg_hash = sha256_text(json.dumps(config, sort_keys=True)); sha = git_sha(os.path.dirname(os.path.abspath(events_path)))
    run_id = sha256_text(json.dumps([cfg_hash, src, sha, implementation], sort_keys=True))[:16]
    m = result.meta
    from . import tie_policy
    return dict(run_id=run_id, execution_mode=config['mode'], tie_order_convention=tie_policy.convention_id(config['tie_order']), implementation=implementation, config=config, config_hash=cfg_hash, source_hashes=src, git_sha=sha, matching_convention=config['method'], tie_order=config['tie_order'],
                timestamp_range=[int(m['first_ts']), int(m['last_ts'])], warnings={k: v for k, v in result.warnings.items() if v}, invariants_checked=sorted(set(result.checks)), dump_sha256=sha256_text(result.dump),
                reproduce_command=reproduce, created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))


def run_dir(root, mode, run_id):
    d = os.path.join(root, mode, run_id); os.makedirs(d, exist_ok=True); return d
