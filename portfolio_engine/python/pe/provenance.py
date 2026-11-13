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


def manifest(result, *, events_path, instruments_path, extra_sources=None, config, implementation, reproduce):
    src = {'events_sha256': sha256_file(events_path), 'instruments_sha256': sha256_file(instruments_path)}; src.update(extra_sources or {})
    cfg_hash = sha256_text(json.dumps(config, sort_keys=True)); sha = git_sha(os.path.dirname(os.path.abspath(events_path)))
    run_id = sha256_text(json.dumps([cfg_hash, src, sha, implementation], sort_keys=True))[:16]
    m = result.meta
    return dict(run_id=run_id, execution_mode=config['mode'], implementation=implementation, config=config, config_hash=cfg_hash, source_hashes=src, git_sha=sha, matching_convention=config['method'], tie_order=config['tie_order'],
                timestamp_range=[int(m['first_ts']), int(m['last_ts'])], warnings={k: v for k, v in result.warnings.items() if v}, invariants_checked=sorted(set(result.checks)), dump_sha256=sha256_text(result.dump),
                reproduce_command=reproduce, created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))


def run_dir(root, mode, run_id):
    d = os.path.join(root, mode, run_id); os.makedirs(d, exist_ok=True); return d
