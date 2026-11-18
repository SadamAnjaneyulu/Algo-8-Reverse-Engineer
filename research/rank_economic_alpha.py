"""Autonomous protected-volatility candidate family and economic mechanism tests."""
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import ROOT, OUT, logs
from benchmark_hedged_straddle import Quotes, cost
from option_pricing_model import implied_vol
from rank_trigger_probabilities import save_records

HORIZONS = {
    'pre_intraday': ('pre', '09:16', 'pre', '15:14'),
    'pre_to_next_open': ('pre', '09:16', 'expiry', '09:16'),
    'pre_to_expiry': ('pre', '09:16', 'expiry', '15:14'),
    'late_to_next_open': ('pre', '15:13', 'expiry', '09:16'),
    'late_to_expiry': ('pre', '15:13', 'expiry', '15:14'),
    'expiry_intraday': ('expiry', '09:16', 'expiry', '15:14'),
}
EXITS = ('time_only', 'symmetric_50', 'separate_50_60', 'separate_50_60_profit90',
         'capital_1pct', 'separate_with_capital')
FILTERS = ('none', 'opening_range_le_0.3', 'gap_le_0.5', 'iv_prior_rv_ge_1.25',
           'iv_rv15_ge_1.25', 'efficiency15_le_0.4', 'iv_rich_and_low_efficiency')


def stamp(day, clock):
    return datetime.fromisoformat(day+'T'+clock).replace(tzinfo=logs.IST)


def known_features(index, quotes, u, expiry, signal, strike):
    prior = signal-timedelta(minutes=1)
    bars = [b for b in index.get((u, str(signal.date())), []) if b['t'] <= prior]
    previous_days = sorted(d for asset, d in index if asset == u and d < str(signal.date()))
    old = index[(u, previous_days[-1])] if previous_days else []
    history = (old[-30:]+bars)[-16:]
    changes = np.diff(np.log([b['close'] for b in history]))
    rv15 = float(np.std(changes)*math.sqrt(252*375)*100) if len(changes) == 15 else None
    past_changes = np.diff(np.log([b['close'] for b in old]))
    prior_rv = float(np.std(past_changes)*math.sqrt(252*375)*100) if len(past_changes) > 100 else None
    travel = sum(abs(history[i]['close']-history[i-1]['close']) for i in range(1, len(history)))
    efficiency = abs(history[-1]['close']-history[0]['close'])/travel if len(history) == 16 and travel else None
    initial = bars[0] if bars else None
    day = str(signal.date())
    ce = quotes.bar(u, expiry, (strike, 'CE'), day, prior.strftime('%H:%M'))
    pe = quotes.bar(u, expiry, (strike, 'PE'), day, prior.strftime('%H:%M'))
    expiry_time = stamp(expiry, '15:35' if expiry >= '2026-08-03' else '15:30')
    tau = (expiry_time-signal).total_seconds()/(365*86400)
    forward = strike+ce['close']-pe['close'] if ce and pe else None
    iv = implied_vol(ce['close'], forward, strike, tau, 'CE') if ce and pe and forward > 0 else None
    return dict(reference_bar_start_ist=prior.isoformat(),
                opening_range_pct=100*(initial['high']-initial['low'])/initial['open'] if initial else None,
                gap_pct=100*(initial['open']/old[-1]['close']-1) if initial and old else None,
                iv_pct=iv*100 if iv is not None else None, prior_session_rv_pct=prior_rv,
                rv15_pct=rv15, efficiency15=efficiency,
                iv_over_prior_rv=iv*100/prior_rv if iv is not None and prior_rv else None,
                iv_over_rv15=iv*100/rv15 if iv is not None and rv15 else None)


def allowed(features, name):
    if name == 'none': return True
    if name == 'opening_range_le_0.3':
        v = features['opening_range_pct']; return v <= .3 if v is not None else None
    if name == 'gap_le_0.5':
        v = features['gap_pct']; return abs(v) <= .5 if v is not None else None
    if name == 'iv_prior_rv_ge_1.25':
        v = features['iv_over_prior_rv']; return v >= 1.25 if v is not None else None
    if name == 'iv_rv15_ge_1.25':
        v = features['iv_over_rv15']; return v >= 1.25 if v is not None else None
    if name == 'efficiency15_le_0.4':
        v = features['efficiency15']; return v <= .4 if v is not None else None
    a, b = features['iv_over_prior_rv'], features['efficiency15']
    return a >= 1.25 and b <= .4 if a is not None and b is not None else None


def select_plan(index, quotes, u, expiry, pre, horizon, geometry, timing=None):
    entry_day, signal_clock, exit_day, exit_clock = HORIZONS[horizon] if timing is None else timing
    signal = stamp(pre if entry_day == 'pre' else expiry, signal_clock)
    entry = signal+timedelta(minutes=1)
    end = stamp(pre if exit_day == 'pre' else expiry, exit_clock)
    guide, _ = logs.reference(index, u, signal)
    if not guide: return None, 'missing_prior_index'
    strike = logs.round_strike(guide['close'], u)
    prior_clock = (signal-timedelta(minutes=1)).strftime('%H:%M')
    day = str(signal.date())
    wings = {}
    for right in ('CE', 'PE'):
        if geometry == 'seed_config':
            gap = 2000 if u == 'NIFTY' or pre >= '2026-09-16' else 4000
            wings[right] = strike+(gap if right == 'CE' else -gap)
        else:
            reference = quotes.bar(u, expiry, (strike, right), day, prior_clock)
            if reference is None or reference['volume'] <= 0: return None, 'missing_fresh_atm_budget_quote'
            budget = .025*reference['close']
            if u == 'SENSEX': budget = math.floor(budget/.1+.5+1e-10)*.1
            candidates = []
            for asset, exp, k, ot, d in quotes.metadata:
                if (asset, exp, ot, d) != (u, expiry, right, day) or not(k > strike if right == 'CE' else k < strike): continue
                b = quotes.bar(u, expiry, (k, right), day, prior_clock)
                if b and b['volume'] > 0 and 0 < b['close'] <= budget:
                    candidates.append((budget-b['close'], abs(k-guide['close']), k))
            if not candidates: return None, 'missing_outward_budget_wing'
            wings[right] = min(candidates)[2]
    legs = [(strike, 'CE', -1), (wings['CE'], 'CE', 1),
            (strike, 'PE', -1), (wings['PE'], 'PE', 1)]
    prices = [quotes.bar(u, expiry, (k, ot), str(entry.date()), entry.strftime('%H:%M')) for k, ot, sign in legs]
    if not all(prices): return None, 'missing_entry_open'
    credit = sum(-sign*p['open'] for (k, ot, sign), p in zip(legs, prices))
    width = max(wings['CE']-strike, strike-wings['PE'])
    if not 0 < credit < width: return None, 'invalid_entry_spread_price_bounds'
    quantity = 3*logs.UNIT[u]
    features = known_features(index, quotes, u, expiry, signal, strike)
    return dict(underlying=u, expiry_date=expiry, preexpiry_date=pre, horizon=horizon, geometry=geometry,
                signal=signal, entry=entry, end=end, legs=legs, entry_prices=[p['open'] for p in prices],
                entry_zero_volume=sum(p['volume'] <= 0 for p in prices), quantity=quantity,
                credit=credit, static_tail_loss=quantity*(width-credit),
                sidewise_loss_budget=quantity*(wings['CE']-strike+strike-wings['PE']-credit), features=features), None


def simulate(plan, quotes, policy):
    u, expiry, legs, q = plan['underlying'], plan['expiry_date'], plan['legs'], plan['quantity']
    entry, end = plan['entry'], plan['end']
    prices = plan['entry_prices']
    active = {'CE': True, 'PE': True}
    pending = {}
    cash = plan['credit']*q
    turnover = q*sum(prices)
    units, orders = 4*q, 4
    zeros = plan['entry_zero_volume']
    bounds = sum(not(-.1 <= prices[i]-prices[i+1] <= abs(legs[i+1][0]-legs[i][0])+.1) for i in (0, 2))
    exit_times, reasons = {}, {}
    stopped = policy in ('symmetric_50', 'separate_50_60', 'separate_50_60_profit90', 'separate_with_capital')
    capital = policy in ('capital_1pct', 'separate_with_capital')
    t = entry+timedelta(minutes=1)
    while t <= end:
        due = [right for right in ('CE', 'PE') if active[right] and (t >= end or pending.get(right) == t)]
        for right in due:
            side_quotes = []
            for i, (k, ot, sign) in enumerate(legs):
                if ot != right: continue
                b = quotes.bar(u, expiry, (k, ot), str(t.date()), t.strftime('%H:%M'))
                if b is None: return None, 'missing_exit_open'
                side_quotes.append((k, sign, b['open']))
                cash += sign*q*b['open']; turnover += q*b['open']; units += q; orders += 1
                zeros += b['volume'] <= 0
            debit = sum(-sign*price for k, sign, price in side_quotes)
            width = abs(side_quotes[0][0]-side_quotes[1][0])
            bounds += not(-.1 <= debit <= width+.1)
            active[right] = False
            exit_times[right] = t.isoformat()
            reasons[right] = pending.get(right+'_reason', 'time') if t < end else 'time'
        if not any(active.values()): break
        if not stopped and not capital:
            t = end
            continue
        previous = t-timedelta(minutes=1)
        day, clock = str(previous.date()), previous.strftime('%H:%M')
        # Overnight has no fabricated candles. Every available session minute is
        # monitored; a missing required quote in a session invalidates the run.
        session_end = '15:39' if day >= '2026-08-03' else '15:29'
        if '09:15' <= clock <= session_end and previous >= entry:
            current = []
            for i, (k, ot, sign) in enumerate(legs):
                b = quotes.bar(u, expiry, (k, ot), day, clock)
                if (sign < 0 and stopped) or (active[ot] and capital):
                    if b is None: return None, 'missing_stop_monitor'
                current.append(b)
            execute = t+timedelta(minutes=1)
            if execute < end:
                if capital and day == expiry:
                    mark = cash+sum(sign*q*current[i]['close'] for i, (k, ot, sign) in enumerate(legs) if active[ot])
                    if mark <= -200000:
                        for right in ('CE', 'PE'):
                            if active[right] and right not in pending:
                                pending[right], pending[right+'_reason'] = execute, 'capital_loss'
                if stopped:
                    for i in (0, 2):
                        right = legs[i][1]
                        if not active[right] or right in pending: continue
                        change = current[i]['close']/prices[i]-1
                        loss = .5 if policy == 'symmetric_50' or right == 'CE' else .6
                        reason = 'leg_loss' if change >= loss else 'leg_profit' if policy == 'separate_50_60_profit90' and change <= -.9 else None
                        if reason:
                            pending[right], pending[right+'_reason'] = execute, reason
        # Advance across the overnight break directly; do not sleep or fill it.
        if t.strftime('%H:%M') > ('15:40' if str(t.date()) >= '2026-08-03' else '15:30') and str(t.date()) < expiry:
            t = stamp(expiry, '09:16')
        else:
            t += timedelta(minutes=1)
    if any(active.values()): return None, 'unclosed_position'
    result = dict(gross=cash, turnover=turnover, transacted_units=units, orders=orders,
                  zero_volume_endpoints=int(zeros), payoff_price_bound_violations=int(bounds), ce_exit_ist=exit_times['CE'], pe_exit_ist=exit_times['PE'],
                  ce_exit_reason=reasons['CE'], pe_exit_reason=reasons['PE'])
    for scenario in ('gross', 'low', 'primary', 'high'):
        result['net_'+scenario] = cash-cost(turnover, units, orders, scenario)
    return result, None


def week(expiry):
    value = datetime.fromisoformat(expiry).date().isocalendar()
    return value.year, value.week


def drawdown(values):
    equity = np.cumsum(values)
    peaks = np.maximum.accumulate(np.r_[0, equity])[1:]
    return float(np.max(peaks-equity)) if len(equity) else 0.


def stats(rows):
    rows = sorted(rows, key=lambda r: (r['expiry_date'], r['underlying']))
    values = [r['net_primary']/r['risk_budget']*10000 for r in rows]
    groups = defaultdict(list)
    for r, value in zip(rows, values): groups[week(r['expiry_date'])].append(value)
    leave = [float(np.mean([v for key, values in groups.items() if key != omitted for v in values])) for omitted in groups] if len(groups) > 1 else []
    active = [r for r in rows if r['trade_allowed']]
    return dict(cycles=len(rows), active_cycles=len(active), weeks=len(groups), net_primary=sum(r['net_primary'] for r in rows),
                net_high=sum(r['net_high'] for r in rows), mean_net_per_10000_tail_loss=float(np.mean(values)) if values else None,
                median_net_per_10000_tail_loss=float(np.median(values)) if values else None,
                worst_leave_week_out_mean=min(leave) if leave else None,
                winning_traded_cycles=sum(r['net_primary'] > 0 for r in active),
                traded_win_rate=sum(r['net_primary'] > 0 for r in active)/len(active) if active else None,
                closed_cycle_drawdown_rupees=drawdown([r['net_primary'] for r in rows]),
                worst_cycle_net=min((r['net_primary'] for r in rows), default=None))


def main():
    starts = list(csv.DictReader((OUT/'trigger_initial_entries.csv').open()))
    index, _ = logs.load_index()
    quotes = Quotes()
    observations, exclusions, references = [], [], []
    for initial in starts:
        u, expiry, pre = initial['underlying'], initial['expiry_date'], initial['event_minute_ist'][:10]
        for horizon in HORIZONS:
            for geometry in ('seed_config', 'budget_2p5'):
                plan, failure = select_plan(index, quotes, u, expiry, pre, horizon, geometry)
                if failure:
                    exclusions.append(dict(underlying=u, expiry_date=expiry, horizon=horizon, geometry=geometry, policy='plan', reason=failure))
                    continue
                simulations = {}
                for policy in EXITS:
                    result, failure = simulate(plan, quotes, policy)
                    if failure:
                        exclusions.append(dict(underlying=u, expiry_date=expiry, horizon=horizon, geometry=geometry, policy=policy, reason=failure))
                    else:
                        simulations[policy] = result
                if horizon == 'pre_to_expiry' and geometry == 'seed_config' and 'time_only' in simulations:
                    references.append(dict(underlying=u, expiry_date=expiry, preexpiry_date=pre,
                                           split='calibration' if expiry <= '2026-08-31' else 'evaluation',
                                           model='seed_config|pre_to_expiry|time_only|none',
                                           static_tail_loss=plan['static_tail_loss'], risk_budget=plan['static_tail_loss'],
                                           **simulations['time_only']))
                # Exit variants use the same quote-valid cycle cohort; a policy
                # cannot look better merely by failing a different monitor quote.
                if len(simulations) != len(EXITS):
                    continue
                if any(allowed(plan['features'], name) is None for name in FILTERS):
                    exclusions.append(dict(underlying=u, expiry_date=expiry, horizon=horizon, geometry=geometry, policy='all', reason='missing_common_filter_input'))
                    continue
                for policy, result in simulations.items():
                    for filter_name in FILTERS:
                        permission = allowed(plan['features'], filter_name)
                        if permission is None:
                            exclusions.append(dict(underlying=u, expiry_date=expiry, horizon=horizon, geometry=geometry, policy=policy+'|'+filter_name, reason='missing_filter_input'))
                            continue
                        outcome = dict(result)
                        if not permission:
                            outcome.update({key: 0 for key in result if key in ('gross', 'turnover', 'transacted_units', 'orders', 'zero_volume_endpoints', 'payoff_price_bound_violations') or key.startswith('net_')})
                            outcome.update(ce_exit_ist='', pe_exit_ist='', ce_exit_reason='filter_skip', pe_exit_reason='filter_skip')
                        observations.append(dict(underlying=u, expiry_date=expiry, preexpiry_date=pre,
                                                 split='calibration' if expiry <= '2026-08-31' else 'evaluation',
                                                 model=geometry+'|'+horizon+'|'+policy+'|'+filter_name,
                                                 geometry=geometry, horizon=horizon, exit_policy=policy, filter=filter_name,
                                                 trade_allowed=bool(permission), quantity=plan['quantity'],
                                                 entry_ist=plan['entry'].isoformat(), cutoff_ist=plan['end'].isoformat(),
                                                 static_tail_loss=plan['static_tail_loss'], entry_credit_unit=plan['credit'],
                                                 risk_budget=plan['static_tail_loss'] if policy in ('time_only', 'capital_1pct') else plan['sidewise_loss_budget'],
                                                 **plan['features'], **outcome))
        print('Economic candidates', u, expiry, len(observations), flush=True)
    save_records('alpha_candidate_cycles.csv.gz', observations)
    save_records('alpha_reference_cycles.csv', references)
    save_records('alpha_candidate_exclusions.csv', exclusions)
    summaries, selected, paired = [], [], []
    eligible_counts = {asset: sum(r['expiry_date'] <= '2026-08-31' and (asset == 'pooled' or r['underlying'] == asset) for r in starts) for asset in ('pooled', 'NIFTY', 'SENSEX')}
    models = sorted({r['model'] for r in observations})
    for asset in ('pooled', 'NIFTY', 'SENSEX'):
        candidates = []
        for model in models:
            cal = [r for r in observations if r['model'] == model and r['split'] == 'calibration' and (asset == 'pooled' or r['underlying'] == asset)]
            later = [r for r in observations if r['model'] == model and r['split'] == 'evaluation' and (asset == 'pooled' or r['underlying'] == asset)]
            if not cal or not later: continue
            calstat, teststat = stats(cal), stats(later)
            qualifies = (len(cal) >= math.ceil(.7*eligible_counts[asset]) and calstat['active_cycles'] >= max(4, math.ceil(.5*len(cal))) and calstat['weeks'] >= 4)
            summaries.append(dict(asset=asset, model=model, selection_eligible=qualifies,
                                  **{'cal_'+k: v for k, v in calstat.items()}, **{'later_'+k: v for k, v in teststat.items()}))
            if qualifies:
                geometry, horizon, policy, filter_name = model.split('|')
                complexity = (policy != 'time_only')+(filter_name != 'none')
                candidates.append((calstat['worst_leave_week_out_mean'], calstat['median_net_per_10000_tail_loss'], calstat['mean_net_per_10000_tail_loss'], -complexity, model, calstat, teststat))
        if not candidates:
            selected.append(dict(asset=asset, model=None, reason='No candidate meets calibration coverage/support'))
            continue
        best = max(candidates, key=lambda row: row[:4])
        selected.append(dict(asset=asset, model=best[4], calibration=best[5], later=best[6]))
        baseline = {(r['underlying'], r['expiry_date']): r for r in references
                    if r['model'] == 'seed_config|pre_to_expiry|time_only|none' and r['split'] == 'evaluation'}
        for r in observations:
            if r['model'] != best[4] or r['split'] != 'evaluation' or not(asset == 'pooled' or r['underlying'] == asset): continue
            b = baseline.get((r['underlying'], r['expiry_date']))
            if b:
                paired.append(dict(asset=asset, model=best[4], underlying=r['underlying'], expiry_date=r['expiry_date'],
                                   candidate_net=r['net_primary'], baseline_net=b['net_primary'],
                                   candidate_per_10000=r['net_primary']/r['risk_budget']*10000,
                                   baseline_per_10000=b['net_primary']/b['risk_budget']*10000,
                                   difference_net=r['net_primary']-b['net_primary'],
                                   candidate_zero_volume=r['zero_volume_endpoints'], baseline_zero_volume=b['zero_volume_endpoints']))
    save_records('alpha_candidate_ranking.csv', summaries)
    save_records('alpha_selected_vs_baseline.csv', paired)
    (OUT/'alpha_candidate_summary.json').write_text(json.dumps(dict(selected=selected, observed_cycles=len(starts),
        model_count=len(models), observations=len(observations), exclusions=len(exclusions),
        selection='Earlier-only worst leave-one-week-out mean normalized net outcome, then median and mean, then simpler policy on exact ties; minimum data coverage and active-trade support. Exit/filter variants share quote-valid cycles within each horizon/geometry.',
        limitations=['Autonomous single protected basket per cycle; no actual later trade decisions are replayed. This does not replicate the observed allocation ladder or original capital/margin controller.',
                     'Three observed quantity units per leg. Joint exits use the frozen expiry loss bound; separate-side exits use the more conservative sum-of-side-widths loss budget, since separate exits can exceed the frozen-basket bound. Neither is broker margin or equal dynamic risk.',
                     'Seed-wing date configuration and candidate thresholds draw on previously inspected research. Later data are chronological checks, not untouched validation.',
                     'Trade-candle zero-volume flags, missing-quote exclusions and traded-contract-only universe limit execution and generalization.',
                     'Filters skip with zero outcome only after the unfiltered policy is quote-valid; missing input/quotes are excluded, not profitable zero trades.',
                     'Closed-cycle drawdown excludes intracycle losses and is not the screenshot drawdown. No original-code posterior probability or verified independent alpha is claimed.']), indent=2, allow_nan=False)+'\n')
    print(json.dumps(selected, indent=2))


if __name__ == '__main__':
    main()
