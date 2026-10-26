"""Ambiguity-aware parent associations and CE/PE exit-direction evidence."""
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
from scipy.optimize import linear_sum_assignment

from audit_strike_hedge_rules import OUT, logs
from build_allocation_side_features import ShortLots
from rank_trigger_probabilities import save_records


def match_parents(left, right, allowed, seconds=5):
    if not left or not right:
        return []
    costs = np.full((len(left), len(right)+len(left)), 100.)
    counts = []
    for i, a in enumerate(left):
        n = 0
        for j, b in enumerate(right):
            distance = abs((a['first']-b['first']).total_seconds())
            if distance <= seconds and allowed(a, b):
                costs[i, j] = distance
                n += 1
        counts.append(n)
    rows, cols = linear_sum_assignment(costs)
    return [(left[i], right[j], costs[i, j], counts[i]) for i, j in zip(rows, cols)
            if j < len(right) and costs[i, j] <= seconds]


def load_parents():
    rows = list(csv.DictReader((OUT/'allocation_parent_inventory.csv').open()))
    for r in rows:
        for name in ('first', 'last', 'label'):
            r[name] = datetime.fromisoformat(r[name])
        for name in ('strike', 'quantity', 'requested_quantity'):
            r[name] = int(r[name])
        r['price'] = float(r['price'])
    return rows


def main():
    parents = load_parents()
    parent_map = {p['parent_id']: p for p in parents}
    source_map = {int(s): p['parent_id'] for p in parents for s in p['sources'].split(';')}
    sessions = defaultdict(list)
    for p in parents:
        sessions[(p['underlying'], p['expiry_date'], str(p['first'].date()))].append(p)
    hedge_links, paired_links = [], []
    for (u, e, day), ps in sessions.items():
        for right in ('CE', 'PE'):
            shorts = [p for p in ps if p['role'] == 'new_short' and p['option_type'] == right]
            longs = [p for p in ps if p['role'] == 'new_long' and p['option_type'] == right]
            matched = match_parents(shorts, longs, lambda a, b: a['quantity'] == b['quantity'] and (b['strike'] > a['strike'] if right == 'CE' else b['strike'] < a['strike']))
            for short, long, distance, candidates in matched:
                hedge_links.append(dict(underlying=u, expiry_date=e, date=day, option_type=right,
                                        short_parent=short['parent_id'], long_parent=long['parent_id'],
                                        short_strike=short['strike'], long_strike=long['strike'], quantity=short['quantity'],
                                        entry_time_distance_seconds=float(distance), candidate_longs=candidates,
                                        association_ambiguous=candidates > 1,
                                        entry_short_premium=short['price'], entry_long_premium=long['price']))
        calls = [p for p in ps if p['role'] == 'new_short' and p['option_type'] == 'CE']
        puts = [p for p in ps if p['role'] == 'new_short' and p['option_type'] == 'PE']
        for ce, pe, distance, candidates in match_parents(calls, puts, lambda a, b: a['quantity'] == b['quantity'] and a['strike'] == b['strike']):
            paired_links.append(dict(underlying=u, expiry_date=e, date=day, ce_parent=ce['parent_id'],
                                     pe_parent=pe['parent_id'], strike=ce['strike'], quantity=ce['quantity'],
                                     time_distance_seconds=float(distance), candidate_puts=candidates,
                                     association_ambiguous=candidates > 1))
    save_records('allocation_inferred_hedge_links.csv', hedge_links)
    save_records('allocation_inferred_short_pairs.csv', paired_links)
    linked = {r['short_parent']: r for r in hedge_links}
    fills = logs.read_fills()
    long_closed = []
    grouped = defaultdict(list)
    for r in fills:
        grouped[(r['u'], str(r['expiry']))].append(r)
    for (u, e), records in grouped.items():
        for mode in ('fifo', 'lifo'):
            lots = ShortLots(mode == 'lifo')
            for r in records:
                flipped = {**r, 'side': 'Sell' if r['side'] == 'Buy' else 'Buy'}
                lots.apply(flipped, source_map[r['source']], None)
            long_closed.extend(dict(underlying=u, expiry_date=e, attribution=mode, position_role='long',
                                    **{k: (-v if k == 'short_realized_pnl' else v) for k, v in r.items()}) for r in lots.closes)
    with gzip.open(OUT/'allocation_lot_closures.csv.gz', 'rt') as stream:
        short_closed = [dict(r, position_role='short') for r in csv.DictReader(stream)]
    first = {}
    for r in short_closed+long_closed:
        key = (r['attribution'], r['position_role'], r['parent_id'])
        when = datetime.fromisoformat(r['exit_ist'])
        if key not in first or when < first[key][0]:
            first[key] = (when, float(r['exit_price']))
    index, _ = logs.load_index()
    exit_rows = []
    for (mode, role, identifier), (when, price) in sorted(first.items()):
        if role != 'short':
            continue
        p = parent_map[identifier]
        if p['role'] != 'new_short':
            continue
        before, _ = logs.reference(index, p['underlying'], when)
        entry, _ = logs.reference(index, p['underlying'], p['first'])
        movement = 100*(before['close']/entry['close']-1) if before and entry else None
        hedge = linked.get(identifier)
        hedge_exit = first.get((mode, 'long', hedge['long_parent'])) if hedge else None
        later = [a for a in sessions.get((p['underlying'], p['expiry_date'], str(when.date())), [])
                 if a['role'] == 'new_short' and a['option_type'] == p['option_type']
                 and when+timedelta(seconds=5) < a['first'] <= when+timedelta(minutes=10)]
        next_parent = min(later, key=lambda a: a['first']) if later else None
        exit_rows.append(dict(underlying=p['underlying'], expiry_date=p['expiry_date'], parent_id=identifier,
                              attribution=mode, option_type=p['option_type'], strike=p['strike'], quantity=p['quantity'],
                              entry_ist=p['first'].isoformat(), first_cover_ist=when.isoformat(),
                              phase='preexpiry' if str(when.date()) < p['expiry_date'] else 'expiry',
                              entry_complete_before_cover=p['last'] < when, entry_premium=p['price'], first_cover_price=price,
                              first_cover_premium_change_pct=100*(price/p['price']-1),
                              prior_spot_change_since_entry_pct=movement,
                              adverse_spot_since_entry=movement*(1 if p['option_type'] == 'CE' else -1) > 0 if movement is not None else None,
                              inferred_hedge_parent=hedge['long_parent'] if hedge else '',
                              hedge_association_ambiguous=hedge['association_ambiguous'] if hedge else None,
                              inferred_hedge_first_close_ist=hedge_exit[0].isoformat() if hedge_exit else '',
                              hedge_first_close_within5s=abs((hedge_exit[0]-when).total_seconds()) <= 5 if hedge_exit else None,
                              next_same_side_entry_10m=next_parent['first'].isoformat() if next_parent else '',
                              next_same_side_strike=next_parent['strike'] if next_parent else None))
    save_records('allocation_short_first_exit_evidence.csv', exit_rows)
    summaries = []
    for mode in ('fifo', 'lifo'):
        for u in ('NIFTY', 'SENSEX'):
            for right in ('CE', 'PE'):
                for phase in ('preexpiry', 'expiry'):
                    rs = [r for r in exit_rows if r['attribution'] == mode and r['underlying'] == u and r['option_type'] == right and r['phase'] == phase and r['entry_complete_before_cover']]
                    known = [r for r in rs if r['adverse_spot_since_entry'] is not None]
                    losing = [r for r in known if r['first_cover_premium_change_pct'] > 0]
                    summaries.append(dict(attribution=mode, underlying=u, option_type=right, phase=phase, parents=len(rs),
                                          with_entry_and_exit_spot=len(known), adverse_spot=sum(r['adverse_spot_since_entry'] for r in known),
                                          losing_short_with_spot=len(losing), losing_short_and_adverse_spot=sum(r['adverse_spot_since_entry'] for r in losing),
                                          higher_buyback_premium=sum(r['first_cover_premium_change_pct'] > 0 for r in rs),
                                          lower_buyback_premium=sum(r['first_cover_premium_change_pct'] < 0 for r in rs),
                                          next_same_side_entry_within10m=sum(bool(r['next_same_side_entry_10m']) for r in rs)))
    save_records('allocation_side_direction_summary.csv', summaries)
    (OUT/'allocation_association_summary.json').write_text(json.dumps(dict(
        pure_short_parents=sum(p['role'] == 'new_short' for p in parents), inferred_fresh_hedge_links=len(hedge_links),
        ambiguous_hedge_links=sum(r['association_ambiguous'] for r in hedge_links), inferred_ce_pe_pairs=len(paired_links),
        direction=summaries,
        limitations=['Parent links minimize entry-time distances, not original basket IDs. Alternative eligible links are flagged.',
                     'FIFO/LIFO change lot attribution; market direction and fill prices remain observed.',
                     'No fresh hedge association does not imply absence of previously purchased protection.',
                     'A later same-side sale is an observed event, not proof the cover triggered re-entry.']), indent=2)+'\n')


if __name__ == '__main__':
    main()
