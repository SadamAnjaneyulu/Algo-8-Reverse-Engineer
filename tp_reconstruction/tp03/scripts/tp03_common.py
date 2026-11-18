"""TP-03 shared helpers: frozen configuration, testability gates, E2 evidence ceiling. Read-only reuse of TP-01 / TP-02 code."""
import os, sys, hashlib
import yaml
HERE = os.path.dirname(os.path.abspath(__file__)); TP03 = os.path.dirname(HERE); PKG = os.path.dirname(TP03); REPO = os.path.dirname(PKG)
sys.path.insert(0, os.path.join(PKG, 'scripts')); sys.path.insert(0, os.path.join(PKG, 'tp02', 'scripts'))
CONFIG_PATH = os.path.join(TP03, 'config.yaml'); FREEZE_PATH = os.path.join(TP03, 'config.sha256')
DATA = os.path.join(TP03, 'data'); ANALYSIS = os.path.join(TP03, 'analysis')
for _d in (DATA, ANALYSIS): os.makedirs(_d, exist_ok=True)


def config_sha256():
    return hashlib.sha256(open(CONFIG_PATH, 'rb').read()).hexdigest()


def assert_frozen():
    """Phase 1 / 2 scripts call this first: a changed configuration is a deviation that must be recorded, not a silent edit"""
    frozen = open(FREEZE_PATH).read().split()[0]
    if frozen != config_sha256(): raise RuntimeError('tp03/config.yaml differs from the frozen hash in tp03/config.sha256: record the deviation or restore the file')


assert_frozen_checked = False
CFG = yaml.safe_load(open(CONFIG_PATH))


def testability(kind, n_obs, cycles_per_und, minority_pooled=None, minority_per_und=None, cfg=None):
    """Which threshold applies (clarification 1).
    kind == 'E2_action'  (binary action / no-action): BOTH the general rule N >= min_events AND the minority gates (pooled, per underlying) AND cycles per underlying.
    any other kind (quantity, strike, wing, ... no minority class): N >= min_events AND cycles per underlying; the minority gates are not applied.
    The general min_events is never applied to the minority class itself."""
    cfg = cfg or CFG; g = cfg['entry']['testability_gates']; me = cfg['inference']['min_events']; reasons = []
    if n_obs < me: reasons.append(f'N={n_obs} < min_events={me}')
    if any(c < g['min_cycles_per_underlying'] for c in cycles_per_und): reasons.append(f'cycles per underlying {list(cycles_per_und)} < {g["min_cycles_per_underlying"]}')
    if kind == 'E2_action':
        if minority_pooled is None or minority_per_und is None: raise ValueError('E2_action needs the minority-class counts')
        if minority_pooled < g['min_minority_class_events_pooled']: reasons.append(f'minority pooled {minority_pooled} < {g["min_minority_class_events_pooled"]}')
        if any(m < g['min_minority_class_events_per_underlying'] for m in minority_per_und): reasons.append(f'minority per underlying {list(minority_per_und)} < {g["min_minority_class_events_per_underlying"]}')
    return dict(testable=not reasons, reasons=reasons, rule='E2 minority gates + N>=min_events' if kind == 'E2_action' else 'N>=min_events and cycles')


def e2_evidence_ceiling(passes_holm_pre_expiry, passes_holm_expiry_day, same_sign):
    """E2 is capped at WEAKLY_SUPPORTED unless the same feature passes Holm with the same sign in BOTH designs; the pre-expiry design is exploratory (control windows selected from earlier behaviour)"""
    if passes_holm_pre_expiry and passes_holm_expiry_day and same_sign: return 'STRONGLY_SUPPORTED_POSSIBLE'          # other STRONGLY_SUPPORTED criteria (both underlyings, >= 60 % of cycles, S0 / S1) still apply
    if passes_holm_pre_expiry or passes_holm_expiry_day: return 'WEAKLY_SUPPORTED_CAP'
    return 'NO_EFFECT_OR_UNRESOLVED'
