"""Audit overlapping positions, opening conditions and exit P&L context."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from audit_strike_hedge_rules import OUT, logs, write

WINDOWS = ('09:30', '09:45', '10:00', '10:15', '10:30', '10:45', '11:00', '11:15',
           '11:30', '11:45', '12:00', '12:30', '13:30', '13:45', '14:00', '14:15', '14:30')


def inventory_at(fills, cutoff):
    inventory = Counter()
    for fill in fills:
        if fill['t'] < cutoff:
            inventory[(fill['strike'], fill['ot'])] += fill['signed']
    return inventory


def retained_lower_bound(before, window_fills, short=True):
    """Conservative retained old exposure, without attributing anonymous baskets.

    Treat every opposite-side fill on a previously held contract as consuming
    its old inventory first. New opening fills cannot reduce this lower bound.
    """
    sign = -1 if short else 1
    keys = {key for key, quantity in before.items() if quantity * sign > 0}
    opposite = 'Buy' if short else 'Sell'
    possible_closes = Counter()
    for r in window_fills:
        if r['side'] == opposite:
            possible_closes[(r['strike'], r['ot'])] += r['q']
    return sum(max(0, abs(before[key]) - possible_closes[key]) for key in keys)


def main():
    fills = logs.read_fills()
    cycles = defaultdict(list)
    for r in fills:
        cycles[(r['u'], str(r['expiry']))].append(r)
    windows = []
    for (u, e), records in sorted(cycles.items()):
        for day in sorted({str(r['t'].date()) for r in records if str(r['t'].date()) < e}):
            for clock in WINDOWS:
                t = datetime.fromisoformat(day + 'T' + clock).replace(tzinfo=logs.IST)
                start, end = t - timedelta(seconds=2), t + timedelta(minutes=3)
                before = inventory_at(records, start)
                after = inventory_at(records, end)
                during = [r for r in records if start <= r['t'] < end]
                windows.append(dict(underlying=u, expiry_date=e, date=day, clock=clock,
                                    short_quantity_before=sum(-q for q in before.values() if q < 0),
                                    short_quantity_after=sum(-q for q in after.values() if q < 0),
                                    retained_old_short_lower_bound=retained_lower_bound(before, during),
                                    retained_old_long_lower_bound=retained_lower_bound(before, during, False)))
    write('lifecycle_scheduled_window_retention.csv', windows)
    sample = []
    for clock in ('09:17:00', '09:29:58', '09:33:00', '09:48:00', '10:03:00', '14:33:00'):
        t = datetime.fromisoformat('2026-07-13T' + clock).replace(tzinfo=logs.IST)
        inventory = inventory_at(cycles[('NIFTY', '2026-07-14')], t)
        sample.append(dict(timestamp_ist=t.isoformat(), short_ce_24000=inventory[(24000, 'CE')],
                           short_pe_24000=inventory[(24000, 'PE')], long_ce_26000=inventory[(26000, 'CE')],
                           long_pe_22000=inventory[(22000, 'PE')],
                           all_short_quantity=sum(-q for q in inventory.values() if q < 0),
                           all_long_quantity=sum(q for q in inventory.values() if q > 0)))
    write('lifecycle_13_july_inventory.csv', sample)
    openings = list(csv.DictReader((OUT / 'trigger_initial_entries.csv').open()))
    ordinary = [r for r in openings if r['first_leg_time_ist'][11:16] == '09:16']
    ordinary.sort(key=lambda r: float(r['completed_range_pct']), reverse=True)
    write('lifecycle_opening_market_conditions.csv', ordinary)
    first_covers = []
    for opening in ordinary:
        start = datetime.fromisoformat(opening['event_minute_ist'])
        snapshot = start + timedelta(minutes=1)
        for right in ('CE', 'PE'):
            records = [r for r in cycles[(opening['underlying'], opening['expiry_date'])]
                       if r['strike'] == int(opening['strike']) and r['ot'] == right]
            entries = [r for r in records if start <= r['t'] < snapshot and r['side'] == 'Sell' and r['opening'] > 0]
            if not entries:
                continue
            first = next((r for r in records if r['t'] >= snapshot and r['side'] == 'Buy' and r['q'] > r['opening']), None)
            additions = [r for r in records if first and snapshot <= r['t'] < first['t']
                         and r['side'] == 'Sell' and r['opening'] > 0]
            cost = sum(float(r['price']) * r['opening'] for r in entries) / sum(r['opening'] for r in entries)
            first_covers.append(dict(underlying=opening['underlying'], expiry_date=opening['expiry_date'],
                                     entry_date=str(start.date()), strike=opening['strike'], option_type=right,
                                     initial_short_quantity=sum(r['opening'] for r in entries), initial_vwap=cost,
                                     first_cover_ist=first['t'].isoformat() if first else '',
                                     first_cover_price=float(first['price']) if first else None,
                                     first_cover_phase=('preexpiry' if str(first['t'].date()) < opening['expiry_date'] else 'expiry') if first else '',
                                     intervening_same_contract_short_additions=len(additions),
                                     initial_cost_reference_uncontaminated=first is not None and not additions,
                                     premium_change_pct=100 * (float(first['price']) / cost - 1) if first else None))
    write('lifecycle_initial_short_first_covers.csv', first_covers)
    exits = [r for r in csv.DictReader((OUT / 'option_marked_cycle_summary.csv').open())
             if r['terminal_95pct_short_reduction_ist'] and r['material_exit_prior_minute_equity']]
    exit_context = [dict(underlying=r['underlying'], expiry_date=r['expiry_date'],
                         material_exit_ist=r['terminal_95pct_short_reduction_ist'],
                         prior_net_equity_before_costs=float(r['material_exit_prior_minute_equity']),
                         prior_net_equity_sign='profit' if float(r['material_exit_prior_minute_equity']) > 0 else 'loss',
                         residual_contracts=int(r['residual_contracts'])) for r in exits]
    write('lifecycle_material_exit_pnl_context.csv', exit_context)
    summary = dict(scheduled_windows=len(windows),
                   guaranteed_prior_short_retention=sum(r['retained_old_short_lower_bound'] > 0 for r in windows),
                   guaranteed_prior_long_retention=sum(r['retained_old_long_lower_bound'] > 0 for r in windows),
                   net_short_quantity_increased=sum(r['short_quantity_after'] > r['short_quantity_before'] for r in windows),
                   first_0930_windows=[r for r in windows if r['clock'] == '09:30'],
                   example_inventory=sample,
                   material_exit_prior_pnl_counts=dict(Counter(r['prior_net_equity_sign'] for r in exit_context)),
                   initial_leg_first_cover_rows=len(first_covers),
                   initial_leg_uncontaminated_first_covers=sum(r['initial_cost_reference_uncontaminated'] for r in first_covers),
                   limitations=['Retention bounds require no basket IDs and do not prove all old lots survive.',
                                'Initial rows include only observed entry dates; no-trade eligibility is not labeled.',
                                'Opening-candle magnitude is descriptive, not an inferred spike threshold.',
                                'Exit P&L is the preceding completed-minute whole-book mark before costs, not the exact exit fill outcome or trigger reason.',
                                'Initial short first-cover cost references are pooled within the opening minute; cleanliness is a retrospective exclusion, not an entry condition or proof of allocation identity.',
                                'No economic alpha or independent 80-90 percent controller recovery is established.'])
    (OUT / 'lifecycle_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('first_0930_windows', 'limitations')}, indent=2))


if __name__ == '__main__':
    main()
