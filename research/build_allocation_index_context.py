"""Full-session prior-known index indicators, trend efficiency and realized vol."""
import math
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import logs
from allocation_rule_models import read_numeric
from strategy_rule_features import indicator_arrays
from rank_trigger_probabilities import save_records


def main():
    context = read_numeric('allocation_greek_context.csv.gz')
    index, _ = logs.load_index()
    lookup = {}
    for (u, day), bars in sorted(index.items()):
        previous = sorted(d for asset, d in index if asset == u and d < day)
        oldbars = index[(u, previous[-1])] if previous else []
        arrays = indicator_arrays(bars, oldbars[-1]['close'] if oldbars else None)
        prior_arrays = indicator_arrays(oldbars) if oldbars else {}
        prepared = []
        for i, bar in enumerate(bars):
            features = {'i_'+k: float(v[i]) if np.isfinite(v[i]) else None for k, v in arrays.items()}
            for window in (5, 15, 30):
                group = bars[max(0, i-window):i+1]
                returns = np.diff(np.log([b['close'] for b in group]))
                vol = float(np.std(returns)*math.sqrt(252*375)*100) if len(returns) == window else None
                travel = sum(abs(group[j]['close']-group[j-1]['close']) for j in range(1, len(group)))
                efficiency = abs(group[-1]['close']-group[0]['close'])/travel if len(returns) == window and travel else None
                features[f'i_realized_vol{window}_annual_pct'] = vol
                features[f'i_efficiency{window}'] = efficiency
            for name in ('rsi_14', 'adx_14', 'atr_pct_14', 'open_to_now_pct'):
                value = prior_arrays.get(name)
                features['i_prior_session_'+name] = float(value[-1]) if value is not None and np.isfinite(value[-1]) else None
            prepared.append((bar['t']+timedelta(minutes=1), features))
        lookup[(u, day)] = prepared
    rows = []
    for r in context:
        t = datetime.fromisoformat(r['cutoff_ist'])
        eligible = [row for row in lookup.get((r['underlying'], r['date']), []) if row[0] <= t]
        features = eligible[-1][1] if eligible else {}
        rows.append(dict(underlying=r['underlying'], expiry_date=r['expiry_date'], date=r['date'], clock=r['clock'],
                         cutoff_ist=r['cutoff_ist'], indicator_available_at_ist=eligible[-1][0].isoformat() if eligible else '', **features))
    save_records('allocation_index_context.csv.gz', rows)


if __name__ == '__main__':
    main()
