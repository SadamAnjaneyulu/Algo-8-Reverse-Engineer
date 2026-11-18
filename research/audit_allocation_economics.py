"""Quote-quality sensitivities for the conditional frozen-allocation economics."""
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime

import numpy as np

from audit_strike_hedge_rules import ROOT, OUT, Market, logs
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def main():
    parents = {p['parent_id']: p for p in load_parents()}
    cases = {(r['attribution'], r['underlying'], r['expiry_date'], r['ids']): r for r in csv.DictReader((OUT/'allocation_frozen_stop_cases.csv').open())}
    with gzip.open(OUT/'allocation_frozen_stop_predictions.csv.gz', 'rt') as stream:
        predicted = {(r['task'], r['underlying'], r['expiry_date'], r['ids']): r for r in csv.DictReader(stream) if r['model'] == 'selected_stop_program'}
    with gzip.open(OUT/'allocation_frozen_stop_economics.csv.gz', 'rt') as stream:
        economic = list(csv.DictReader(stream))
    metadata = defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m = json.loads(path.read_text())
        metadata[(m['contract']['underlying'], m['contract']['expiry_date'])].append(m)
    index, _ = logs.load_index()
    markets, observations = {}, []
    for r in economic:
        u, e, ids, task = r['underlying'], r['expiry_date'], r['ids'], r['task']
        key = (u, e)
        if key not in markets:
            markets[key] = Market(u, e, metadata[key], index)
        c = cases[(task.split('|')[0], u, e, ids)]
        guess = float(predicted[(task, u, e, ids)]['predicted_minute'])
        short = [parents[i] for i in ids.split(';')]
        long = [parents[i] for i in c['hedge_ids'].split(';')]
        width = max(abs(a['strike']-b['strike']) for a, b in zip(short, long))
        row = dict(r)
        for name, signal in [('candidate', guess), ('clock', float(c['fallback_minute']))]:
            when = datetime.fromtimestamp((signal+1)*60, logs.IST)
            quotes = [markets[key].bar(str(when.date()), p['strike'], p['option_type'], when.strftime('%H:%M')) for p in short+long]
            assert all(quotes)
            debit = sum(q['open'] for q in quotes[:len(short)])-sum(q['open'] for q in quotes[len(short):])
            row[name+'_zero_volume_legs'] = sum(q['volume'] <= 0 for q in quotes)
            row[name+'_outside_payoff_price_bounds'] = int(debit < -.1 or debit > width+.1)
            row[name+'_net_per_10000_tail_loss'] = float(r[name+'_net'])/float(r['static_tail_loss'])*10000
        observations.append(row)
    save_records('allocation_frozen_economic_quote_quality.csv.gz', observations)
    summaries = []
    for task in sorted({r['task'] for r in observations}):
        for quality in ('all', 'nonzero_volume_endpoints', 'nonzero_volume_and_payoff_bounds'):
            rows = [r for r in observations if r['task'] == task and
                    (quality == 'all' or not(r['candidate_zero_volume_legs'] or r['clock_zero_volume_legs'])) and
                    (quality != 'nonzero_volume_and_payoff_bounds' or not(r['candidate_outside_payoff_price_bounds'] or r['clock_outside_payoff_price_bounds']))]
            if not rows:
                continue
            weeks = defaultdict(list)
            for r in rows:
                date = datetime.fromisoformat(r['expiry_date']).date().isocalendar()
                weeks[(date.year, date.week)].append(float(r['improvement_per_10000_tail_loss']))
            values = list(weeks.values())
            rng = np.random.default_rng(20261026)
            samples = [np.mean([value for j in rng.integers(0, len(values), len(values)) for value in values[j]]) for _ in range(2000)]
            low, high = np.quantile(samples, [.025, .975])
            summaries.append(dict(task=task, quality=quality, allocations=len(rows), weeks=len(weeks),
                                  mean_candidate_net_per_10000_tail_loss=float(np.mean([r['candidate_net_per_10000_tail_loss'] for r in rows])),
                                  mean_clock_net_per_10000_tail_loss=float(np.mean([r['clock_net_per_10000_tail_loss'] for r in rows])),
                                  mean_improvement_per_10000_tail_loss=float(np.mean([float(r['improvement_per_10000_tail_loss']) for r in rows])),
                                  lower=float(low), upper=float(high)))
    save_records('allocation_economic_quality_summary.csv', summaries)
    (OUT/'allocation_economic_quality_summary.json').write_text(json.dumps(dict(
        summaries=summaries,
        note='Endpoint-volume/payoff-bound filters are ex-post data-quality sensitivities, not tradable filters. Same recorded entries and inferred frozen hedges; static tail risk is not margin or equal dynamic market exposure. Previously inspected later weeks, multiple searched models and incomplete chain prevent a definitive alpha claim.'), indent=2)+'\n')


if __name__ == '__main__':
    main()
