"""Describe recurring additions; infer effects, not the author's intent.

Inventory roles are reconstructed retrospectively. Quotes and model state are
frozen before each execution window, so before/after risk changes isolate the
trades. This is descriptive, not an autonomous signal or profitability test.
"""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from audit_strike_hedge_rules import ROOT, OUT, logs, Market, write
from clarify_position_lifecycle import WINDOWS, inventory_at


def main():
    fills = logs.read_fills()
    index, _ = logs.load_index()
    cycles, metadata = defaultdict(list), defaultdict(list)
    for f in fills:
        cycles[(f['u'], str(f['expiry']))].append(f)
    for path in (ROOT / 'data/breeze/metadata/options').rglob('*.json'):
        m = json.loads(path.read_text())
        metadata[(m['contract']['underlying'], m['contract']['expiry_date'])].append(m)
    opening = {(r['underlying'], r['expiry_date']): r for r in
               csv.DictReader((OUT / 'trigger_initial_entries.csv').open())}
    rows = []
    for (u, e), records in sorted(cycles.items()):
        days = sorted({str(f['t'].date()) for f in records if str(f['t'].date()) < e})
        if not days:
            continue
        market = Market(u, e, metadata[(u, e)], index)
        for day in days:
            initial_k = int(opening[(u, e)]['strike'])
            for clock in WINDOWS:
                t = datetime.fromisoformat(day + 'T' + clock).replace(tzinfo=logs.IST)
                start, end = t - timedelta(seconds=2), t + timedelta(minutes=3)
                prior = [f for f in records if t - timedelta(minutes=15) <= f['t'] < start]
                during = [f for f in records if start <= f['t'] < end]
                before, after = inventory_at(records, start), inventory_at(records, end)
                shorts = Counter()
                new_inventory = Counter()
                for f in during:
                    key = (f['strike'], f['ot'])
                    if f['opening']:
                        new_inventory[key] += f['opening'] * (1 if f['side'] == 'Buy' else -1)
                        if f['side'] == 'Sell':
                            shorts[key] += f['opening']
                row = dict(underlying=u, expiry_date=e, date=day, clock=clock,
                           prior_15min_short_cover_quantity=sum(f['q'] - f['opening'] for f in prior if f['side'] == 'Buy'),
                           prior_15min_long_sale_quantity=sum(f['q'] - f['opening'] for f in prior if f['side'] == 'Sell'),
                           new_short_quantity=sum(shorts.values()),
                           new_long_quantity=sum(f['opening'] for f in during if f['side'] == 'Buy'),
                           short_quantity_before=sum(-q for q in before.values() if q < 0),
                           short_quantity_after=sum(-q for q in after.values() if q < 0),
                           initial_strike=initial_k,
                           quote_bar_start_ist=(t - timedelta(minutes=2)).isoformat(),
                           model_available=False, theta_change='', vega_change='', gamma_change='',
                           abs_delta_change='', new_inventory_delta='',
                           new_vs_initial_distance_change='', matched_pair_quantity=0,
                           pairs_different_from_initial_quantity=0,
                           new_vs_initial_timevalue_change='')
                # T-2 bar closes at T-1, before the earliest permitted T-2s fill.
                state = market.state(day, (t - timedelta(minutes=2)).strftime('%H:%M'))
                a, b = market.risk(before, state), market.risk(after, state)
                if a is not None and b is not None:
                    trade_inventory = Counter({k: after[k] - before[k] for k in before.keys() | after.keys()})
                    trade_risk = market.risk(trade_inventory, state)
                    assert trade_risk is not None
                    for name in ('theta_calendar_day', 'vega_one_point', 'gamma', 'delta'):
                        difference = b[name] - a[name]
                        assert abs(difference - trade_risk[name]) < 1e-7 * max(1, abs(a[name]), abs(b[name]))
                    row['model_available'] = True
                    row['theta_change'] = b['theta_calendar_day'] - a['theta_calendar_day']
                    row['vega_change'] = b['vega_one_point'] - a['vega_one_point']
                    row['gamma_change'] = b['gamma'] - a['gamma']
                    row['abs_delta_change'] = abs(b['delta']) - abs(a['delta'])
                new_risk = market.risk(new_inventory, state)
                if new_risk is not None:
                    row['new_inventory_delta'] = new_risk['delta']
                pairs = [(k, min(shorts[(k, 'CE')], shorts[(k, 'PE')]))
                         for k in {k for k, _ in shorts}]
                pairs = [(k, q) for k, q in pairs if q]
                row['matched_pair_quantity'] = sum(q for k, q in pairs)
                row['pairs_different_from_initial_quantity'] = sum(q for k, q in pairs if k != initial_k)
                if state and pairs:
                    forward = state['forward']
                    total = sum(q for k, q in pairs)
                    row['new_vs_initial_distance_change'] = sum(q * abs(k - forward) for k, q in pairs) / total - abs(initial_k - forward)
                    def timevalue(k):
                        bars = [market.bar(day, k, right, state['clock']) for right in ('CE', 'PE')]
                        if any(b is None or b['volume'] <= 0 for b in bars):
                            return None
                        return sum(b['close'] for b in bars) - abs(forward - k)
                    initial_tv = timevalue(initial_k)
                    values = [(q, timevalue(k)) for k, q in pairs]
                    if initial_tv is not None and all(v is not None for q, v in values):
                        row['new_vs_initial_timevalue_change'] = sum(q * v for q, v in values) / total - initial_tv
                rows.append(row)
        print('Checked', u, e, flush=True)
    write('building_rationale_windows.csv', rows)
    assert len(rows) == len({(r['underlying'], r['expiry_date'], r['date'], r['clock']) for r in rows})
    assert all(r['new_short_quantity'] > 0 for r in rows)
    summaries = []
    for u in ('NIFTY', 'SENSEX', 'pooled'):
        sample = [r for r in rows if u == 'pooled' or r['underlying'] == u]
        s = dict(underlying=u, windows=len(sample),
                 without_prior_short_covers=sum(r['prior_15min_short_cover_quantity'] == 0 for r in sample),
                 without_prior_reductions=sum(r['prior_15min_short_cover_quantity'] == r['prior_15min_long_sale_quantity'] == 0 for r in sample),
                 net_short_quantity_increased=sum(r['short_quantity_after'] > r['short_quantity_before'] for r in sample),
                 with_new_protection=sum(r['new_long_quantity'] > 0 for r in sample))
        for field, positive in [('theta_change', True), ('vega_change', False),
                                ('gamma_change', False), ('abs_delta_change', False),
                                ('new_vs_initial_distance_change', False),
                                ('new_vs_initial_timevalue_change', True)]:
            values = [r[field] for r in sample if r[field] != '']
            s[field + '_available'] = len(values)
            s[field + '_desired_sign'] = sum(v > 1e-8 if positive else v < -1e-8 for v in values)
        s['matched_pair_quantity'] = sum(r['matched_pair_quantity'] for r in sample)
        s['different_initial_pair_quantity'] = sum(r['pairs_different_from_initial_quantity'] for r in sample)
        summaries.append(s)
    write('building_rationale_summary.csv', summaries)
    contexts = list(csv.DictReader((OUT / 'addition_decision_opportunities.csv').open()))
    keys = {(r['underlying'], r['expiry_date'], r['date'], r['clock']) for r in rows}
    contexts = [r for r in contexts if (r['underlying'], r['expiry_date'], r['date'], r['clock']) in keys]
    assert len(contexts) == len(rows)
    conditions = []
    for field in ('spot_return5_pct', 'reference_premium_change5_pct', 'iv_change15_points', 'equity_pct_capital'):
        values = [float(r[field]) for r in contexts if r[field] != '']
        conditions.append(dict(feature=field, available=len(values), positive=sum(v > 0 for v in values),
                               negative=sum(v < 0 for v in values), zero=sum(v == 0 for v in values)))
    write('building_rationale_conditions.csv', conditions)
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
