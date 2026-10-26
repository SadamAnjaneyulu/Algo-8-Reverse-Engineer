"""Weekly uncertainty, quote quality and frozen execution sensitivities."""
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import OUT, logs
from benchmark_hedged_straddle import Quotes, cost
from rank_economic_alpha import select_plan, week
from rank_trigger_probabilities import save_records, wilson


def interval(rows, field):
    groups = defaultdict(list)
    for r in rows: groups[week(r['expiry_date'])].append(float(r[field]))
    blocks = list(groups.values())
    if not blocks: return dict(weeks=0, mean=None, lower=None, upper=None)
    rng = np.random.default_rng(20261026)
    samples = [np.mean([v for j in rng.integers(0, len(blocks), len(blocks)) for v in blocks[j]]) for _ in range(10000)]
    low, high = np.quantile(samples, [.025, .975])
    return dict(weeks=len(blocks), mean=float(np.mean([float(r[field]) for r in rows])), lower=float(low), upper=float(high))


def main():
    summary = json.loads((OUT/'alpha_candidate_summary.json').read_text())
    with gzip.open(OUT/'alpha_candidate_cycles.csv.gz', 'rt') as stream:
        rows = list(csv.DictReader(stream))
    paired = list(csv.DictReader((OUT/'alpha_selected_vs_baseline.csv').open()))
    evidence = []
    for selected in summary['selected']:
        if not selected['model']: continue
        for quality in ('all', 'fresh_and_price_bounds'):
            chosen = [r for r in rows if r['model'] == selected['model'] and r['split'] == 'evaluation'
                      and (selected['asset'] == 'pooled' or r['underlying'] == selected['asset'])
                      and (quality == 'all' or (int(r['zero_volume_endpoints']) == 0 and int(r['payoff_price_bound_violations']) == 0))]
            for r in chosen: r['normalized_net'] = float(r['net_primary'])/float(r['risk_budget'])*10000
            traded = [r for r in chosen if r['trade_allowed'] == 'True']
            winners = sum(float(r['net_primary']) > 0 for r in traded)
            low, high = wilson(winners, len(traded))
            evidence.append(dict(asset=selected['asset'], model=selected['model'], quality=quality,
                                 cycles=len(chosen), traded=len(traded), winning=winners,
                                 win_rate_lower=low, win_rate_upper=high,
                                 **interval(chosen, 'normalized_net')))
    comparisons = []
    for asset in ('pooled', 'NIFTY', 'SENSEX'):
        chosen = [r for r in paired if r['asset'] == asset]
        if chosen:
            for r in chosen:
                r['normalized_difference'] = float(r['candidate_per_10000'])-float(r['baseline_per_10000'])
            comparisons.append(dict(asset=asset, common_cycles=len(chosen),
                                    total_difference_net=sum(float(r['difference_net']) for r in chosen),
                                    **interval(chosen, 'difference_net'),
                                    **{'risk_normalized_'+k: v for k, v in interval(chosen, 'normalized_difference').items()}))
    index, _ = logs.load_index()
    quotes = Quotes()
    sensitivity, attribution = [], []
    for selected in summary['selected']:
        if not selected['model']: continue
        geometry, horizon, policy, filter_name = selected['model'].split('|')
        if policy != 'time_only' or filter_name != 'none': continue
        chosen = [r for r in rows if r['model'] == selected['model'] and r['split'] == 'evaluation'
                  and (selected['asset'] == 'pooled' or r['underlying'] == selected['asset'])]
        for r in chosen:
            plan, error = select_plan(index, quotes, r['underlying'], r['expiry_date'], r['preexpiry_date'], horizon, geometry)
            assert error is None
            for label, entry_delay, exit_delay, extra_orders in [('primary', 0, 0, 0), ('entry_plus_1m', 1, 0, 0),
                                                               ('exit_plus_1m', 0, 1, 0), ('both_plus_1m', 1, 1, 0),
                                                               ('three_parallel_parents', 0, 0, 16)]:
                entry, end = plan['entry']+timedelta(minutes=entry_delay), plan['end']+timedelta(minutes=exit_delay)
                a = [quotes.bar(r['underlying'], r['expiry_date'], (k, ot), str(entry.date()), entry.strftime('%H:%M')) for k, ot, sign in plan['legs']]
                b = [quotes.bar(r['underlying'], r['expiry_date'], (k, ot), str(end.date()), end.strftime('%H:%M')) for k, ot, sign in plan['legs']]
                if not all(a) or not all(b):
                    sensitivity.append(dict(asset=selected['asset'], expiry_date=r['expiry_date'], variant=label, available=False, net=None))
                    continue
                quantity = plan['quantity']
                gross = quantity*sum(sign*(y['open']-x['open']) for (k, ot, sign), x, y in zip(plan['legs'], a, b))
                turnover = quantity*sum(x['open']+y['open'] for x, y in zip(a, b))
                net = gross-cost(turnover, 8*quantity, 8+extra_orders, 'primary')
                sensitivity.append(dict(asset=selected['asset'], expiry_date=r['expiry_date'], variant=label, available=True, net=net))
                if label == 'primary':
                    short_pnl = quantity*sum(x['open']-y['open'] for (k, ot, sign), x, y in zip(plan['legs'], a, b) if sign < 0)
                    hedge_pnl = quantity*sum(y['open']-x['open'] for (k, ot, sign), x, y in zip(plan['legs'], a, b) if sign > 0)
                    assert abs(short_pnl+hedge_pnl-gross) < 1e-6
                    attribution.append(dict(asset=selected['asset'], expiry_date=r['expiry_date'], short_premium_pnl=short_pnl,
                                            long_hedge_pnl=hedge_pnl, cost_stress=gross-net, net=net,
                                            entry_net_credit=quantity*sum(-sign*x['open'] for (k, ot, sign), x in zip(plan['legs'], a)),
                                            exit_net_debit=quantity*sum(-sign*y['open'] for (k, ot, sign), y in zip(plan['legs'], b))))
    save_records('alpha_candidate_weekly_evidence.csv', evidence)
    save_records('alpha_candidate_baseline_evidence.csv', comparisons)
    save_records('alpha_candidate_execution_sensitivity.csv', sensitivity)
    save_records('alpha_candidate_profit_components.csv', attribution)
    sensitivity_summary = []
    for asset in ('pooled', 'NIFTY', 'SENSEX'):
        for label in sorted({r['variant'] for r in sensitivity}):
            rs = [r for r in sensitivity if r['asset'] == asset and r['variant'] == label and r['available']]
            if rs: sensitivity_summary.append(dict(asset=asset, variant=label, cycles=len(rs), net=sum(r['net'] for r in rs),
                                                  winning=sum(r['net'] > 0 for r in rs)))
    save_records('alpha_candidate_sensitivity_summary.csv', sensitivity_summary)
    chosen_nifty = next((r for r in summary['selected'] if r['asset'] == 'NIFTY'), None)
    if chosen_nifty and chosen_nifty['model']:
        rulebook = dict(status='Highest-ranked NIFTY economic candidate; not recovered original code or certified independent alpha',
                        selected_model=chosen_nifty['model'], selection_period='Expiries through 2026-08-31',
                        entry=dict(signal='09:16 IST on the observed pre-expiry session', modeled_fill='09:17 candle open',
                                   short_strike='Nearest 50-point strike to the completed 09:15 index close',
                                   quantity_per_leg=195,
                                   wings='Each right separately: highest prior fresh outward premium <= 2.5% of the corresponding ATM premium'),
                        exit=dict(clock='15:14 expiry-day candle open', note='Time-only won the earlier ranking; tested side stops did not improve the selected economic score'),
                        exposure='Defined-risk short volatility; short CE/PE plus outward long CE/PE',
                        scope='One basket per cycle. Observed later ladder entries, pending orders and original margin/controller are not replicated',
                        capital='No inference of broker margin from premium cashflows or theoretical payoff loss',
                        calibration=chosen_nifty['calibration'], later=chosen_nifty['later'])
        (OUT/'alpha_highest_ranked_rulebook.json').write_text(json.dumps(rulebook, indent=2)+'\n')
    original_entries = {(r['underlying'], r['expiry_date']): r['first_leg_time_ist'][11:16]
                        for r in csv.DictReader((OUT/'trigger_initial_entries.csv').open())}
    ordinary_sensitivity = []
    for selected in summary['selected']:
        if not selected['model']: continue
        chosen = [r for r in rows if r['model'] == selected['model'] and r['split'] == 'evaluation'
                  and (selected['asset'] == 'pooled' or r['underlying'] == selected['asset'])
                  and original_entries[(r['underlying'], r['expiry_date'])] == '09:16']
        ordinary_sensitivity.append(dict(asset=selected['asset'], cycles=len(chosen),
                                         net_primary=sum(float(r['net_primary']) for r in chosen),
                                         note='Excludes recorded delayed-opening cycles, without selecting on their profit.'))
    save_records('alpha_candidate_ordinary_opening_sensitivity.csv', ordinary_sensitivity)
    audits = dict(weekly_evidence=evidence, common_baseline=comparisons, execution_sensitivities=sensitivity_summary,
                  ordinary_opening_sensitivity=ordinary_sensitivity,
                  caveat='Small previously inspected samples, many searched alternatives, historical traded-chain selection and unequal dynamic risk prevent a validated alpha or original-code probability claim.')
    audits['sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('alpha_*')) if p.name != 'alpha_economic_audit.json'}
    (OUT/'alpha_economic_audit.json').write_text(json.dumps(audits, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(weekly=evidence, common_baseline=comparisons, sensitivities=sensitivity_summary), indent=2))


if __name__ == '__main__': main()
