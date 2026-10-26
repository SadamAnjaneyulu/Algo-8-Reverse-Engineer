"""Clock quantities versus fixed premium/notional/Greek sizing hypotheses."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import ROOT, OUT, Market, logs
from build_allocation_side_features import vector_greeks
from rank_trigger_probabilities import save_records


def round_units(value, method):
    if method == 'floor':
        return max(0, int(np.floor(value)))
    if method == 'ceil':
        return max(0, int(np.ceil(value)))
    return max(0, int(np.floor(value+.5)))


def size_metrics(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    exact = np.all(actual == predicted, axis=1)
    return dict(allocations=len(actual), exact_joint=int(exact.sum()), exact_rate=float(exact.mean()),
                mean_absolute_units_per_right=float(np.abs(actual-predicted).mean()))


def main():
    observed = list(csv.DictReader((OUT/'allocation_window_sizes.csv').open()))
    metadata = defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m = json.loads(path.read_text())
        metadata[(m['contract']['underlying'], m['contract']['expiry_date'])].append(m)
    index, _ = logs.load_index()
    markets = {}
    inputs, missing = [], []
    for r in observed:
        if r['clock'] == '09:16' or float(r['new_short_CE_quantity'])+float(r['new_short_PE_quantity']) == 0:
            continue
        u, e, day = r['underlying'], r['expiry_date'], r['date']
        key = (u, e)
        if key not in markets:
            markets[key] = Market(u, e, metadata[key], index)
        market = markets[key]
        # Windows can start two seconds early: retain a full-minute embargo.
        t = datetime.fromisoformat(day+'T'+r['clock']).replace(tzinfo=logs.IST)-timedelta(minutes=1)
        guide, _ = logs.reference(index, u, t)
        if not guide:
            missing.append(dict(underlying=u, expiry_date=e, date=day, clock=r['clock'], reason='missing_prior_index'))
            continue
        k = logs.round_strike(guide['close'], u)
        clock = guide['t'].strftime('%H:%M')
        state = market.state(day, clock)
        quotes = [market.bar(day, k, ot, clock) for ot in ('CE', 'PE')]
        if state is None or not all(q and q['close'] > 0 and q['volume'] > 0 for q in quotes):
            missing.append(dict(underlying=u, expiry_date=e, date=day, clock=r['clock'], reason='missing_fresh_atm_reference'))
            continue
        greeks = vector_greeks([q['close'] for q in quotes], [state['forward']]*2, [k]*2, [state['tau']]*2, [True, False])
        if not np.all(np.isfinite(greeks['delta'])):
            missing.append(dict(underlying=u, expiry_date=e, date=day, clock=r['clock'], reason='unfitted_greeks'))
            continue
        row = dict(underlying=u, expiry_date=e, date=day, phase=r['phase'], clock=r['clock'], split=r['split'],
                   cycle=u+'|'+e, reference_bar_start_ist=guide['t'].isoformat(), reference_known_at_ist=t.isoformat())
        for j, ot in enumerate(('CE', 'PE')):
            row['actual_'+ot] = float(r['new_short_'+ot+'_units'])
            row['premium_'+ot] = logs.UNIT[u]*quotes[j]['close']
            row['notional_'+ot] = logs.UNIT[u]*guide['close']
            row['vega_'+ot] = logs.UNIT[u]*greeks['vega_one_point'][j]
            row['gamma_'+ot] = logs.UNIT[u]*.5*greeks['gamma'][j]*(state['forward']*.01)**2
            row['theta_'+ot] = logs.UNIT[u]*abs(greeks['theta_calendar_day'][j])
        inputs.append(row)
    save_records('allocation_budget_inputs.csv', inputs)
    save_records('allocation_budget_exclusions.csv', missing)
    comparisons, predictions, calibration = [], [], []
    for phase in ('preexpiry', 'expiry'):
        for target_asset in ('NIFTY', 'SENSEX'):
            target = [r for r in inputs if r['phase'] == phase and r['underlying'] == target_asset and r['split'] == 'evaluation']
            if not target:
                continue
            truth = [[r['actual_CE'], r['actual_PE']] for r in target]
            for scope in ('own_index', 'pooled_budget', 'other_index_transfer'):
                cal = [r for r in inputs if r['phase'] == phase and r['split'] == 'calibration' and
                       (r['underlying'] == target_asset if scope == 'own_index' else r['underlying'] != target_asset if scope == 'other_index_transfer' else True)]
                clock_map = defaultdict(list)
                for r in cal:
                    clock_map[r['clock']].append(r)
                counts = {clock: Counter((r['actual_CE'], r['actual_PE']) for r in rs).most_common(1)[0][0] for clock, rs in clock_map.items()}
                clock_pred = [counts.get(r['clock'], (0, 0)) for r in target]
                comparisons.append(dict(phase=phase, underlying=target_asset, scope=scope, family='clock_quantity', rounding='',
                                        **size_metrics(truth, clock_pred)))
                for family in ('premium', 'notional', 'vega', 'gamma', 'theta'):
                    def predict(rows, train_rows, method, exclude_cycle=False):
                        result = []
                        for r in rows:
                            peers = [a for a in train_rows if a['clock'] == r['clock'] and (not exclude_cycle or a['cycle'] != r['cycle'])]
                            current = []
                            for ot in ('CE', 'PE'):
                                budgets = [a['actual_'+ot]*a[family+'_'+ot] for a in peers if a['actual_'+ot] > 0]
                                budget = float(np.median(budgets)) if budgets else 0
                                current.append(round_units(budget/r[family+'_'+ot], method) if r[family+'_'+ot] > 0 else 0)
                            result.append(current)
                        return result
                    best = None
                    for method in ('floor', 'nearest', 'ceil'):
                        pr = predict(cal, cal, method, True)
                        stat = size_metrics([[r['actual_CE'], r['actual_PE']] for r in cal], pr)
                        calibration.append(dict(phase=phase, underlying=target_asset, scope=scope, family=family, rounding=method, **stat))
                        key = (stat['exact_rate'], -stat['mean_absolute_units_per_right'])
                        if best is None or key > best[0]:
                            best = (key, method)
                    chosen = predict(target, cal, best[1])
                    comparisons.append(dict(phase=phase, underlying=target_asset, scope=scope, family=family, rounding=best[1], **size_metrics(truth, chosen)))
                    for r, values in zip(target, chosen):
                        predictions.append(dict(underlying=target_asset, expiry_date=r['expiry_date'], date=r['date'], phase=phase,
                                                clock=r['clock'], scope=scope, family=family, actual_ce=r['actual_CE'], actual_pe=r['actual_PE'],
                                                predicted_ce=values[0], predicted_pe=values[1]))
    save_records('allocation_budget_calibration.csv', calibration)
    save_records('allocation_budget_evaluation.csv', comparisons)
    save_records('allocation_budget_predictions.csv', predictions)
    (OUT/'allocation_budget_summary.json').write_text(json.dumps(dict(
        quoted_positive_windows=len(inputs), exclusions=len(missing), evaluation=comparisons,
        note='Sizing conditional on an observed new-short allocation; entry eligibility is not predicted. Greek budgets refer to the short core, not net hedged portfolio or broker margin. Earlier-only budgets/rounding use leave-cycle-out calibration; later reference prices precede the execution window.'), indent=2)+'\n')


if __name__ == '__main__':
    main()
