"""Intra-second fill-order policies (R1).

Source timestamps have ONE-SECOND resolution, so the true order of same-instrument fills inside a second is not observable. The delivered reconstruction uses
SOURCE_ROW_ORDER_CONVENTION: such fills are processed in source-file row order. That is a deterministic CONVENTION, not verified execution chronology.
Every other policy here is SENSITIVITY-ONLY: it exists to measure how much a result depends on the convention, never to replace it.

policy              engine order   primary  keyed  what it does
source_row          'src'          yes      no     source-file row order (alias: legacy name 'src')            -> SOURCE_ROW_ORDER_CONVENTION
sells_first         'sells_first'  no       no     inside a second, sells before buys, then source row       [Python and C++]
buys_first          'buys_first'   no       no     inside a second, buys before sells, then source row       [Python and C++]
trade_id            'trade_id'     no       yes    raw trade-id column (numeric for NIFTY; '<ns>-<suffix>' for SENSEX), then source row   [Python only]
order_no            'order_no'     no       yes    raw order-number column, then source row                   [Python only]
sensex_trade_id_time 'sensex_trade_id_time' no yes SENSEX only: the nanosecond timestamp embedded in the trade id (validated in reports/m2f_audit/r1), then source row; NIFTY stays source row   [Python only]
NIFTY trade ids are NOT assumed to share SENSEX semantics (they are not time-monotone).
"""
import re
from dataclasses import dataclass
from .schema import EngineError

SOURCE_ROW_ORDER_CONVENTION = 'SOURCE_ROW_ORDER_CONVENTION'
PRIMARY_POLICY = 'source_row'
CONVENTION_METADATA = {'id': SOURCE_ROW_ORDER_CONVENTION, 'engine_policy': 'src', 'verified_intra_second_chronology': False,
                       'statement': 'same-instrument fills inside one second are processed in source-file row order; a deterministic convention, not verified execution chronology',
                       'sensitivity': 'reports/R1_TIE_ORDER_CONVENTION.md'}    # stamped identically into every delivered manifest (tools/r1_stamp_convention.py and the builders)
SENSITIVITY_PREFIX = 'SENSITIVITY_ONLY:'


@dataclass(frozen=True)
class TiePolicy:
    name: str; engine_order: str; primary: bool; keyed: bool; cpp_supported: bool; description: str

    @property
    def sensitivity_only(self): return not self.primary


POLICIES = {p.name: p for p in (
    TiePolicy('source_row', 'src', True, False, True, 'source-file row order within a second (SOURCE_ROW_ORDER_CONVENTION)'),
    TiePolicy('sells_first', 'sells_first', False, False, True, 'sells before buys within a second, then source row'),
    TiePolicy('buys_first', 'buys_first', False, False, True, 'buys before sells within a second, then source row'),
    TiePolicy('trade_id', 'trade_id', False, True, False, 'raw trade id, then source row'),
    TiePolicy('order_no', 'order_no', False, True, False, 'raw order number, then source row'),
    TiePolicy('sensex_trade_id_time', 'sensex_trade_id_time', False, True, False, 'SENSEX nanosecond trade-id time (epoch-derived fallback for an inconsistent id), NIFTY source row'))}
ALIASES = {'src': 'source_row'}
KEYED = tuple(p.name for p in POLICIES.values() if p.keyed)


def resolve(name):
    n = ALIASES.get(name, name)
    if n not in POLICIES: raise EngineError(f'unknown tie-order policy {name!r}; known: {sorted(POLICIES)}')
    return POLICIES[n]


def engine_order(name): return resolve(name).engine_order
def is_primary(name): return resolve(name).primary


def convention_id(name):
    """identifier stamped into manifests / provenance: the primary convention, or an explicit sensitivity label (never the primary's name)"""
    p = resolve(name); return SOURCE_ROW_ORDER_CONVENTION if p.primary else SENSITIVITY_PREFIX + p.name


def require_primary(name, what='this output'):
    """guard for builders of DELIVERED outputs: a sensitivity policy must never silently replace the primary convention"""
    if not is_primary(name): raise EngineError(f'{what} must use {SOURCE_ROW_ORDER_CONVENTION}; got sensitivity-only policy {resolve(name).name!r}')
    return SOURCE_ROW_ORDER_CONVENTION


# ---- per-fill sensitivity keys (pure functions of raw column values) --------------------------------------------------------------------------------
_SENSEX_TID = re.compile(r'^(\d{19})-(\d{1,9})$')


def trade_id_key(trade_id):
    if '-' in trade_id: a, b = trade_id.split('-', 1); return (int(a), int(b))
    return (int(trade_id), 0)


def order_no_key(order_no): return (int(order_no),)


def sensex_time_key(underlying, trade_id, epoch_s):
    """SENSEX: nanosecond timestamp embedded in the trade id when it is consistent with the raw epoch (epoch == round-half-up(ns/1e9)); otherwise the epoch-derived time (an exceptional id is never trusted).
    Other underlyings: (0,), i.e. the policy leaves them in source-row order."""
    if underlying != 'SENSEX': return (0,)
    m = _SENSEX_TID.match(trade_id)
    if m:
        ns = int(m.group(1))
        if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)
    return (epoch_s * 10**9,)


def tie_key(policy, underlying, trade_id, order_no, epoch_s):
    n = resolve(policy).name
    if n == 'trade_id': return trade_id_key(trade_id)
    if n == 'order_no': return order_no_key(order_no)
    if n == 'sensex_trade_id_time': return sensex_time_key(underlying, trade_id, epoch_s)
    return None
