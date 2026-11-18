"""Controlled economic test: fresh ATM ladder versus fixed-strike averaging."""
import csv
import json
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np

from audit_strike_hedge_rules import OUT, logs
from analyze_allocation_sizes import frozen_expiry_bound
from audit_alpha_candidate import interval
from benchmark_hedged_straddle import Quotes, cost
from rank_economic_alpha import select_plan, simulate, stamp
from rank_trigger_probabilities import save_records


def main():
    observed = list(csv.DictReader((OUT/'allocation_window_sizes.csv').open()))
    groups = defaultdict(list)
    for r in observed:
        if r['phase'] == 'preexpiry' and r['split'] == 'calibration':
            groups[r['clock']].append(r)
    weights = {}
    for clock, rows in groups.items():
        values = Counter(tuple(float(r['new_'+side+'_'+right+'_quantity'])/logs.UNIT[r['underlying']]
                               for side, right in [('short', 'CE'), ('short', 'PE'), ('long', 'CE'), ('long', 'PE')]) for r in rows)
        modal = values.most_common(1)[0][0]
        if len(set(modal)) != 1:
            raise ValueError('Calibration modal vector is not a balanced four-role basket.')
        if modal[0] > 0: weights[clock] = int(modal[0])
    index, _ = logs.load_index()
    quotes = Quotes()
    starts = list(csv.DictReader((OUT/'trigger_initial_entries.csv').open()))
    observations, exclusions = [], []
    for initial in starts:
        u, expiry, pre = initial['underlying'], initial['expiry_date'], initial['event_minute_ist'][:10]
        for endclock in ('09:16', '15:14'):
            prepared = {}
            for clock in set(weights) | {'15:13'}:
                plan, failure = select_plan(index, quotes, u, expiry, pre, 'staggered', 'budget_2p5',
                                             timing=('pre', clock, 'expiry', endclock))
                if failure:
                    exclusions.append(dict(underlying=u, expiry_date=expiry, endclock=endclock, clock=clock, reason=failure))
                else:
                    prepared[clock] = plan
            if '09:16' not in prepared:
                continue
            total = sum(weights.values())
            opening = prepared['09:16']
            results = {}
            for scheme in ('opening_lump', 'fixed_strike_ladder', 'fresh_atm_ladder', 'late_lump'):
                plans, invalid = [], False
                if scheme == 'opening_lump':
                    plans = [(opening, total)]
                elif scheme == 'late_lump':
                    plans = [(prepared['15:13'], total)] if '15:13' in prepared else []
                    invalid = not plans
                else:
                    for clock, weight in sorted(weights.items()):
                        if scheme == 'fresh_atm_ladder':
                            if clock not in prepared:
                                invalid = True
                                break
                            plan = prepared[clock]
                        else:
                            signal = stamp(pre, clock)
                            entry = signal+timedelta(minutes=1)
                            plan = {**opening, 'signal': signal, 'entry': entry}
                            prices = [quotes.bar(u, expiry, (k, ot), pre, entry.strftime('%H:%M')) for k, ot, sign in plan['legs']]
                            if not all(prices):
                                invalid = True
                                break
                            plan['entry_prices'] = [p['open'] for p in prices]
                            plan['entry_zero_volume'] = sum(p['volume'] <= 0 for p in prices)
                            plan['credit'] = sum(-sign*p['open'] for (k, ot, sign), p in zip(plan['legs'], prices))
                        plans.append((plan, weight))
                if invalid:
                    continue
                net, gross, entry_cash, inventory, zero = 0., 0., 0., Counter(), 0
                for raw, weight in plans:
                    plan = {**raw, 'quantity': weight*logs.UNIT[u]}
                    outcome, failure = simulate(plan, quotes, 'time_only')
                    if failure:
                        invalid = True
                        exclusions.append(dict(underlying=u, expiry_date=expiry, endclock=endclock, clock=scheme, reason=failure))
                        break
                    # Charge the same base-unit child-order count in every arm.
                    expense = cost(outcome['turnover'], outcome['transacted_units'], 8*weight, 'primary')
                    net += outcome['gross']-expense
                    gross += outcome['gross']
                    zero += outcome['zero_volume_endpoints']
                    entry_cash += plan['credit']*plan['quantity']
                    for k, ot, sign in plan['legs']:
                        inventory[(k, ot)] += sign*plan['quantity']
                if invalid: continue
                bound = frozen_expiry_bound(inventory, entry_cash)
                if bound is None or bound <= 0: continue
                results[scheme] = dict(underlying=u, expiry_date=expiry,
                                       split='calibration' if expiry <= '2026-08-31' else 'evaluation',
                                       exit_clock=endclock, scheme=scheme, base_units_per_right=total,
                                       net_primary=net, gross=gross, zero_volume_endpoints=int(zero),
                                       frozen_expiry_loss_bound=bound, normalized_net=net/bound*10000)
            # Compare exactly the same quoted cycles across all four arms.
            if len(results) == 4:
                observations.extend(results.values())
        print('Staggered controls', u, expiry, len(observations), flush=True)
    save_records('alpha_staggered_cycles.csv', observations)
    save_records('alpha_staggered_exclusions.csv', exclusions)
    summaries, comparisons = [], []
    for asset in ('NIFTY', 'SENSEX', 'pooled'):
        for endclock in ('09:16', '15:14'):
            for split in ('calibration', 'evaluation'):
                for scheme in ('opening_lump', 'fixed_strike_ladder', 'fresh_atm_ladder', 'late_lump'):
                    rows = [r for r in observations if r['exit_clock'] == endclock and r['split'] == split and r['scheme'] == scheme
                            and (asset == 'pooled' or r['underlying'] == asset)]
                    if rows:
                        summaries.append(dict(asset=asset, exit_clock=endclock, split=split, scheme=scheme,
                                              cycles=len(rows), net_primary=sum(r['net_primary'] for r in rows),
                                              winning=sum(r['net_primary'] > 0 for r in rows), **interval(rows, 'normalized_net')))
                if split != 'evaluation': continue
                baseline = {(r['underlying'], r['expiry_date']): r for r in observations if r['exit_clock'] == endclock and r['split'] == split and r['scheme'] == 'fixed_strike_ladder'}
                fresh = [r for r in observations if r['exit_clock'] == endclock and r['split'] == split and r['scheme'] == 'fresh_atm_ladder'
                         and (asset == 'pooled' or r['underlying'] == asset)]
                difference = [dict(expiry_date=r['expiry_date'], difference=r['net_primary']-baseline[(r['underlying'], r['expiry_date'])]['net_primary']) for r in fresh]
                if difference:
                    comparisons.append(dict(asset=asset, exit_clock=endclock, common_cycles=len(difference),
                                            total_difference=sum(r['difference'] for r in difference), **interval(difference, 'difference')))
    save_records('alpha_staggered_summary.csv', summaries)
    save_records('alpha_staggered_recentering_comparison.csv', comparisons)
    (OUT/'alpha_staggered_summary.json').write_text(json.dumps(dict(weights=weights, total_units=sum(weights.values()),
        results=summaries, comparisons=comparisons,
        limitations=['Earlier-only pooled modal clock weights; one basket per weighted slot, no adaptive sizing or recorded exit borrowing.',
                     'Identical intended total quantity and base-unit child-order costs, not identical margin or dynamic risk.',
                     'All arms share a quote-complete cohort; missing contracts from the traded-only universe can strongly select that cohort.',
                     'No stops, extra entries or re-entry controller in this mechanism isolation. Later dates were already inspected.']), indent=2)+'\n')


if __name__ == '__main__': main()
