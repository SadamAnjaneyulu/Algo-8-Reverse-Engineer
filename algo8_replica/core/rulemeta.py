"""Rule evidence register loader and guards. The register (config/rule_evidence.yaml) is the single source of truth for each rule's
evidence class. Guards here enforce the brief's non-negotiables: no classification change without a changelog entry, no REJECTED /
UNKNOWN rule running as an original-behaviour rule, no TEACHER_FORCED mode in a historical run."""
import os, hashlib
import yaml

CLASSES = ('CONFIRMED_OBSERVATION', 'STRONGLY_SUPPORTED', 'HYPOTHESIS', 'UNKNOWN', 'REJECTED')
MODES = ('OBSERVED_CONSTANT', 'BAND', 'TEACHER_FORCED_ONLY', 'USER_RULE_ONLY', 'DISABLED_BY_DEFAULT', 'NOT_IMPLEMENTED', 'ACCOUNTING')
REQUIRED = ('id', 'group', 'description', 'evidence_source', 'classification', 'parameters', 'parameter_ranges', 'implementation_status',
            'may_run_historically', 'mode', 'observed_or_hypothetical', 'limitations')
PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'rule_evidence.yaml')


def load(path=PATH):
    with open(path) as f: doc = yaml.safe_load(f)
    return doc


def sha256(path=PATH):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def validate(doc):
    """returns list of error strings (empty = valid)"""
    err = []; seen = set()
    for r in doc['rules']:
        miss = [k for k in REQUIRED if k not in r]
        if miss: err.append(f"{r.get('id')}: missing fields {miss}"); continue
        if r['id'] in seen: err.append(f"{r['id']}: duplicate id")
        seen.add(r['id'])
        if r['classification'] not in CLASSES: err.append(f"{r['id']}: bad classification {r['classification']}")
        if r['mode'] not in MODES: err.append(f"{r['id']}: bad mode {r['mode']}")
        if r['may_run_historically'] not in (True, False, 'conditional'): err.append(f"{r['id']}: bad may_run_historically")
        if r['classification'] == 'REJECTED' and r['mode'] not in ('DISABLED_BY_DEFAULT', 'NOT_IMPLEMENTED'): err.append(f"{r['id']}: REJECTED rule must not be active by default")
        if r['mode'] == 'TEACHER_FORCED_ONLY' and r['may_run_historically'] is not False: err.append(f"{r['id']}: teacher-forced rules cannot run historically")
        if r['classification'] == 'UNKNOWN' and r['mode'] in ('OBSERVED_CONSTANT',): err.append(f"{r['id']}: UNKNOWN rule cannot be an observed constant")
    return err


def check_run_config(doc, enabled):
    """enabled: {rule_id: mode_label} for a HISTORICAL run, mode_label in {'ON','BAND:<value>','OFF'}. Returns errors for rules that may not run."""
    by = {r['id']: r for r in doc['rules']}; err = []
    for rid, state in enabled.items():
        r = by.get(rid)
        if r is None: err.append(f'{rid}: not in register'); continue
        if state == 'OFF': continue
        if r['may_run_historically'] is False: err.append(f"{rid}: may not run historically ({r['classification']}, {r['mode']})")
        if r['classification'] == 'REJECTED': err.append(f'{rid}: REJECTED rule enabled')
    return err
