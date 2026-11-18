"""Prototype risk validation. These are simple synthetic-model controls (unit counts, lineage, cooldown, look-ahead). They are NOT exchange margin
and NOT calibrated or production risk controls."""
from .contract import Spec

# reason codes (shared with the C++ implementation)
DUPLICATE_ACTION_ID = 'DUPLICATE_ACTION_ID'; INVALID_ACTION_TYPE = 'INVALID_ACTION_TYPE'; PLUGIN_MISMATCH = 'PLUGIN_MISMATCH'; STALE_ACTION_TIMESTAMP = 'STALE_ACTION_TIMESTAMP'
LOOKAHEAD_VIOLATION = 'LOOKAHEAD_VIOLATION'; INVALID_BASKET_STATE = 'INVALID_BASKET_STATE'; MISSING_OR_INVALID_LEG = 'MISSING_OR_INVALID_LEG'; INVALID_QUANTITY = 'INVALID_QUANTITY'
INSUFFICIENT_INVENTORY = 'INSUFFICIENT_INVENTORY'; QUANTITY_LIMIT_EXCEEDED = 'QUANTITY_LIMIT_EXCEEDED'; INVALID_CUT_LINEAGE = 'INVALID_CUT_LINEAGE'; REENTRY_LIMIT_EXCEEDED = 'REENTRY_LIMIT_EXCEEDED'
COOLDOWN_NOT_ELAPSED = 'COOLDOWN_NOT_ELAPSED'; EXPOSURE_LIMIT_EXCEEDED = 'EXPOSURE_LIMIT_EXCEEDED'; GROUP_REJECTED = 'GROUP_REJECTED'

BIG = 1_000_000_000
RISK_SPEC = {
    'max_gross_units': Spec('int', BIG, minimum=0, doc='sum of |net inventory| over all instruments after the action'),
    'max_short_units': Spec('int', BIG, minimum=0, doc='sum of net short inventory over all instruments after the action'),
    'max_cut_qty_per_action': Spec('int', BIG, minimum=0),
    'max_reentry_qty_per_action': Spec('int', BIG, minimum=0),
    'reentry_min_cooldown_s': Spec('int', 0, minimum=0, doc='validator-side minimum time between a cut and its re-entry (independent of the plugin cooldown)'),
}


def parse_risk(cfg):
    out = {}
    for k in cfg:
        if k not in RISK_SPEC: raise ValueError(f'unknown risk key {k}')
    for k, s in RISK_SPEC.items():
        v = int(cfg.get(k, s.default))
        if v < s.minimum or v > 10 ** 12: raise ValueError(f'risk {k} outside 0..10^12')
        out[k] = v
    return out


class Projection:
    """a scratch copy of the basket book plus per-instrument inventory deltas; validation of a group runs on it so a rejected group changes nothing"""
    def __init__(self, book): self.book = book.clone(); self.delta = {}


def exposure(ledger_inv, delta):
    """(gross_units, short_units) of the ledger inventory shifted by `delta`; ledger_inv: {instrument: signed inventory}"""
    gross = short = 0
    for iid in set(ledger_inv) | set(delta):
        v = ledger_inv.get(iid, 0) + delta.get(iid, 0); gross += abs(v); short += -v if v < 0 else 0
    return gross, short


def check(action, now, proj, ledger_inv, lots, limits, producer):
    """first failing rule -> (reason, detail); passing -> None. `ledger_inv` is the unchanged ledger's signed inventory per instrument."""
    b = proj.book
    if action.action_id in b.seen_ids: return DUPLICATE_ACTION_ID, action.action_id
    if action.type not in ('CUT', 'REENTRY'): return INVALID_ACTION_TYPE, action.type
    if action.plugin != producer.name or action.version != producer.version: return PLUGIN_MISMATCH, f'{action.plugin}@{action.version} returned by {producer.name}@{producer.version}'
    if action.ts != now: return STALE_ACTION_TIMESTAMP, f'action_ts={action.ts} now={now}'
    if action.info_ts > action.ts: return LOOKAHEAD_VIOLATION, f'info_ts={action.info_ts} ts={action.ts}'
    if action.basket_id not in b.baskets: return INVALID_BASKET_STATE, 'unknown basket'
    leg = b.leg(action.basket_id, action.leg_id)
    if leg is None: return MISSING_OR_INVALID_LEG, action.leg_id
    lot = lots[leg.instrument_id]
    if action.qty <= 0 or action.qty % lot != 0: return INVALID_QUANTITY, f'qty={action.qty} lot={lot}'
    if action.type == 'CUT':
        if b.status(action.basket_id) == 'FULLY_CUT': return INVALID_BASKET_STATE, 'basket already fully cut'
        if action.qty > leg.current: return INSUFFICIENT_INVENTORY, f'qty={action.qty} available={leg.current}'
        if action.qty > limits['max_cut_qty_per_action']: return QUANTITY_LIMIT_EXCEEDED, f'qty={action.qty} limit={limits["max_cut_qty_per_action"]}'
        sign = -leg.side
    else:
        cut = b.cuts.get(action.parent_cut_id)
        if cut is None or cut.basket_id != action.basket_id or cut.leg_id != action.leg_id: return INVALID_CUT_LINEAGE, f'parent_cut={action.parent_cut_id!r}'
        if action.qty > limits['max_reentry_qty_per_action']: return QUANTITY_LIMIT_EXCEEDED, f'qty={action.qty} limit={limits["max_reentry_qty_per_action"]}'
        if action.ts < cut.ts + limits['reentry_min_cooldown_s']: return COOLDOWN_NOT_ELAPSED, f'ts={action.ts} earliest={cut.ts + limits["reentry_min_cooldown_s"]}'
        if cut.reentered + action.qty > cut.qty or leg.current + action.qty > leg.initial: return REENTRY_LIMIT_EXCEEDED, f'reentered={cut.reentered} qty={action.qty} cut_qty={cut.qty}'
        sign = leg.side
    g0, s0 = exposure(ledger_inv, proj.delta)
    d = dict(proj.delta); d[leg.instrument_id] = d.get(leg.instrument_id, 0) + sign * action.qty
    g1, s1 = exposure(ledger_inv, d)
    if g1 > limits['max_gross_units'] and g1 > g0: return EXPOSURE_LIMIT_EXCEEDED, f'gross={g1} limit={limits["max_gross_units"]}'
    if s1 > limits['max_short_units'] and s1 > s0: return EXPOSURE_LIMIT_EXCEEDED, f'short={s1} limit={limits["max_short_units"]}'
    return None
