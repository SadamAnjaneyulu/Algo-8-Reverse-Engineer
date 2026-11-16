"""Two reversal measures (Decision B, owner-approved 2026-11-16). They are DIFFERENT things and are never merged into one count.

PER_FILL_ZERO_CROSSING_REVERSAL (primary technical event): one executed fill changes the instrument inventory from one non-zero sign to the opposite non-zero sign
  (before * after < 0). A fill that only reaches zero, or that starts from zero, is not one.
PARENT_LEVEL_SAME_SECOND_NET_SIGN_FLIP (additional diagnostic): for one (instrument, parent order, second) the inventory immediately before the parent's FIRST fill of that second and
  immediately after its LAST fill of that second have opposite non-zero signs. Fills of other parents that interleave inside the second are part of the inventory path.
A parent-level sign flip is NOT automatically a broker-designated reversal and NOT proof of a strategy event; it is a grouping diagnostic. Neither measure is a subset of the other
(a parent can cross zero twice inside the second and end on its starting sign: two per-fill events, no parent-level flip).
Both depend on the order of same-instrument fills inside a second (a convention, see docs/ORDERING_SEMANTICS.md); they are reported under the baseline and the hybrid scenario.
"""
from collections import OrderedDict

PER_FILL = 'PER_FILL_ZERO_CROSSING_REVERSAL'
PARENT_LEVEL = 'PARENT_LEVEL_SAME_SECOND_NET_SIGN_FLIP'
sgn = lambda x: (x > 0) - (x < 0)


def measures(rows):
    """rows: iterable of (fill_id, source_row_id, instrument_id, parent_order_id, timestamp_s, signed_quantity) in the PROCESSING order (inventory starts at zero per instrument).
    Returns per_fill events and parent_level events with the inventory before / after, so every count traces to source rows."""
    inv = {}; per_fill = []; groups = OrderedDict()
    for fid, row, inst, parent, ts, q in rows:
        before = inv.get(inst, 0); after = before + q; inv[inst] = after
        if sgn(before) * sgn(after) < 0: per_fill.append(dict(fill_id=fid, source_row_id=row, instrument_id=inst, parent_order_id=parent, timestamp_s=ts, inventory_before=before, inventory_after=after))
        g = groups.setdefault((inst, parent, ts), dict(instrument_id=inst, parent_order_id=parent, timestamp_s=ts, inventory_before=before, inventory_after=after, fills=[]))
        g['inventory_after'] = after; g['fills'].append(row)
    parent_level = [dict(g, n_fills=len(g['fills'])) for g in groups.values() if sgn(g['inventory_before']) * sgn(g['inventory_after']) < 0]
    return dict(per_fill=per_fill, parent_level=parent_level, counts={PER_FILL: len(per_fill), PARENT_LEVEL: len(parent_level)})


def from_fills(ordered_fills):
    """ordered_fills: pe.schema.Fill objects in processing order (e.g. replay.order_events(fills, tie_order))"""
    return measures((f.fill_id, f.source_row_id, f.instrument_id, f.parent_order_id, f.timestamp_s, f.side * f.quantity) for f in ordered_fills)
