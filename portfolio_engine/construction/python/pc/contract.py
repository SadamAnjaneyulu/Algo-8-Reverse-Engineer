"""The plugin contract. A plugin is a deterministic function from a read-only context to proposed actions plus decision records.
It never touches the ledger, the basket book or any source data."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from . import API_VERSION


class ConfigError(Exception): pass
class LookAheadError(Exception): pass

OK, NO_ACTION, ERROR = 'OK', 'NO_ACTION', 'ERROR'          # PluginResult.status ; INVALID_CONFIG is raised as ConfigError at configure time


def fnv1a64(text):
    h = 14695981039346656037
    for b in text.encode('utf-8'): h = ((h ^ b) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f'{h:016x}'


@dataclass(frozen=True)
class Spec:
    kind: str                     # 'int', 'enum' or 'str'
    default: object
    allowed: tuple = ()           # enum values
    minimum: int = None           # int lower bound
    maximum: int = None           # int upper bound
    doc: str = ''


@dataclass(frozen=True)
class ProposedAction:
    action_id: str; plugin: str; version: str; type: str      # type: CUT | REENTRY
    group_id: str; basket_id: str; leg_id: str; qty: int
    parent_cut_id: str; ts: int; info_ts: int; reason: str     # info_ts = newest data timestamp the plugin used (must not exceed ts)


@dataclass(frozen=True)
class Decision:
    ts: int; plugin: str; version: str; basket_id: str; leg_id: str
    outcome: str                   # PROPOSED | NOT_PROPOSED
    reason: str; detail: str; info_ts: int


@dataclass
class PluginResult:
    status: str = NO_ACTION
    actions: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    error: str = ''


class Plugin(ABC):
    name = ''
    version = '0.0.0'
    api_version = API_VERSION
    CONFIG_SPEC = {}

    def __init__(self, config=None):
        self.config = self.validate_config(config or {})

    @classmethod
    def validate_config(cls, config):
        errs, out = [], {}
        for k in config:
            if k not in cls.CONFIG_SPEC: errs.append(f'unknown key {k}')
        for k, s in cls.CONFIG_SPEC.items():
            v = config.get(k, s.default)
            if s.kind == 'int':
                try: v = int(v)
                except (TypeError, ValueError): errs.append(f'{k}: not an integer ({v!r})'); continue
                if s.minimum is not None and v < s.minimum: errs.append(f'{k}: below minimum {s.minimum}')
                if s.maximum is not None and v > s.maximum: errs.append(f'{k}: above maximum {s.maximum}')
            elif s.kind == 'str': v = str(v)
            else:
                if v not in s.allowed: errs.append(f'{k}: {v!r} not in {list(s.allowed)}')
            out[k] = v
        if errs: raise ConfigError(f'{cls.name}: ' + '; '.join(errs))
        return out

    @property
    def config_hash(self):
        return fnv1a64(f'{self.name}@{self.version}|' + ';'.join(f'{k}={self.config[k]}' for k in sorted(self.config)))

    @abstractmethod
    def evaluate(self, ctx):
        """-> PluginResult. Must be deterministic and may only use `ctx` (data with timestamp <= ctx.ts)."""
