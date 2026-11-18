"""Frozen side/paired allocations: stop programs, attribution and cost diagnostics.

The matched entries are observed; their parent/hedge associations are inferred.
These are conditional allocation tests, not an autonomous portfolio backtest.
"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import ROOT, OUT, Market, logs
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def atom_bank():
    atoms = [dict(family='none', threshold=0, activation=0)]
    for family in ('short_loss', 'hedged_loss'):
        atoms += [dict(family=family, threshold=v, activation=0) for v in (10, 20, 25, 30, 40, 50, 60, 70, 75, 100, 150)]
    for family in ('short_profit', 'hedged_profit'):
        atoms += [dict(family=family, threshold=v, activation=0) for v in (20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95)]
    for family in ('carry_short_loss', 'carry_hedged_loss'):
        atoms += [dict(family=family, threshold=v, activation=0) for v in (2, 3, 4, 5, 10, 20)]
    for activation in (20, 40, 60):
        atoms += [dict(family='activated_hedged_trail', threshold=v, activation=activation) for v in (10, 20, 30, 50)]
    return atoms


def first_hits(short, hedged, times, days, entry_short, entry_hedged, expiry, prior_short, prior_hedged, atoms):
    hits = np.full(len(atoms), np.inf)
    low = np.minimum.accumulate(hedged)
    with np.errstate(divide='ignore', invalid='ignore'):
        short_change = 100*(short/entry_short-1)
        net_change = 100*(hedged/entry_hedged-1) if entry_hedged > 0 else np.full(len(short), np.nan)
        carry_short = 100*(short/prior_short-1) if prior_short and prior_short > 0 else np.full(len(short), np.nan)
        carry_net = 100*(hedged/prior_hedged-1) if prior_hedged and prior_hedged > 0 else np.full(len(short), np.nan)
        rebound = np.where(low > 0, 100*(hedged/low-1), np.nan)
    for i, atom in enumerate(atoms):
        family, threshold = atom['family'], atom['threshold']
        mask = np.zeros(len(short), bool)
        if family == 'short_loss': mask = short_change >= threshold
        elif family == 'hedged_loss': mask = net_change >= threshold
        elif family == 'short_profit': mask = short_change <= -threshold
        elif family == 'hedged_profit': mask = net_change <= -threshold
        elif family == 'carry_short_loss': mask = (days == expiry) & (carry_short >= threshold)
        elif family == 'carry_hedged_loss': mask = (days == expiry) & (carry_net >= threshold)
        elif family == 'activated_hedged_trail': mask = (low <= entry_hedged*(1-atom['activation']/100)) & (rebound >= threshold)
        indices = np.flatnonzero(mask)
        if len(indices): hits[i] = times[indices[0]]
    return hits


def main():
    parents = {r['parent_id']: r for r in load_parents()}
    links = {r['short_parent']: r for r in csv.DictReader((OUT/'allocation_inferred_hedge_links.csv').open())}
    paired = list(csv.DictReader((OUT/'allocation_inferred_short_pairs.csv').open()))
    exits = {(r['attribution'], r['parent_id']): r for r in csv.DictReader((OUT/'allocation_short_first_exit_evidence.csv').open())}
    metadata = defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m = json.loads(path.read_text())
        metadata[(m['contract']['underlying'], m['contract']['expiry_date'])].append(m)
    index, _ = logs.load_index()
    specs = []
    for identifier, link in links.items():
        p = parents[identifier]
        specs.append(dict(kind=p['option_type'], ids=[identifier], hedge_ids=[link['long_parent']],
                          ambiguous=link['association_ambiguous'] == 'True'))
    for pair in paired:
        ids = [pair['ce_parent'], pair['pe_parent']]
        if all(identifier in links for identifier in ids):
            specs.append(dict(kind='combined', ids=ids, hedge_ids=[links[i]['long_parent'] for i in ids],
                              ambiguous=pair['association_ambiguous'] == 'True' or any(links[i]['association_ambiguous'] == 'True' for i in ids)))
    bycycle = defaultdict(list)
    for spec in specs:
        p = parents[spec['ids'][0]]
        bycycle[(p['underlying'], p['expiry_date'])].append(spec)
    atoms = atom_bank()
    cases, matrices, paths, exclusions = [], [], [], []
    for (u, e), batch in sorted(bycycle.items()):
        market = Market(u, e, metadata[(u, e)], index)
        for spec in batch:
            shorts = [parents[i] for i in spec['ids']]
            longs = [parents[i] for i in spec['hedge_ids']]
            entered = max(p['last'] for p in shorts+longs)
            deadline = datetime.fromisoformat(e+('T15:14' if e >= '2026-08-03' else 'T15:25')).replace(tzinfo=logs.IST)
            if entered >= deadline:
                exclusions.append(dict(underlying=u, expiry_date=e, kind=spec['kind'], attribution='both', reason='entry_at_or_after_clock_exit_deadline'))
                continue
            initial_short = sum(p['price'] for p in shorts)
            initial_long = sum(p['price'] for p in longs)
            initial_credit = initial_short-initial_long
            if initial_credit <= 0:
                continue
            moments, short_values, net_values, days, missing = [], [], [], [], 0
            for day in sorted(d for d in market.days if str(entered.date()) <= d <= e):
                start = datetime.fromisoformat(day+'T09:15').replace(tzinfo=logs.IST)
                count = 385 if day >= '2026-08-03' else 375
                for j in range(count):
                    previous = start+timedelta(minutes=j)
                    t = previous+timedelta(minutes=1)
                    if entered >= t:
                        continue
                    prices = [market.bar(day, p['strike'], p['option_type'], previous.strftime('%H:%M')) for p in shorts+longs]
                    if not all(prices):
                        missing += 1
                        continue
                    s = sum(p['close'] for p in prices[:len(shorts)])
                    net = s-sum(p['close'] for p in prices[len(shorts):])
                    moments.append(t.timestamp()/60)
                    short_values.append(s)
                    net_values.append(net)
                    days.append(day)
            if not moments:
                continue
            prior_days = sorted(d for d in market.days if d < e)
            prior_short, prior_net = None, None
            if prior_days and str(entered.date()) < e:
                day = prior_days[-1]
                clock = '15:39' if day >= '2026-08-03' else '15:29'
                prices = [market.bar(day, p['strike'], p['option_type'], clock) for p in shorts+longs]
                if all(prices):
                    prior_short = sum(p['close'] for p in prices[:len(shorts)])
                    prior_net = prior_short-sum(p['close'] for p in prices[len(shorts):])
            hits = first_hits(np.array(short_values), np.array(net_values), np.array(moments), np.array(days),
                              initial_short, initial_credit, e, prior_short, prior_net, atoms)
            fallback = deadline.timestamp()/60
            for mode in ('fifo', 'lifo'):
                targets = [exits.get((mode, identifier)) for identifier in spec['ids']]
                if not all(targets):
                    continue
                target = min(datetime.fromisoformat(r['first_cover_ist']) for r in targets)
                if entered >= target:
                    exclusions.append(dict(underlying=u, expiry_date=e, kind=spec['kind'], attribution=mode, reason='entries_not_complete_before_first_reduction'))
                    continue
                cases.append(dict(underlying=u, expiry_date=e, kind=spec['kind'], attribution=mode,
                                  ids=';'.join(spec['ids']), hedge_ids=';'.join(spec['hedge_ids']), ambiguous=spec['ambiguous'],
                                  observed_first_reduction=target.isoformat(), target_minute=target.timestamp()/60,
                                  fallback_minute=fallback, missing_path_minutes=missing, initial_credit=initial_credit,
                                  quantity=shorts[0]['quantity'], entry_phase='preexpiry' if str(entered.date()) < e else 'expiry',
                                  split='calibration' if e <= '2026-08-31' else 'evaluation'))
                matrices.append(hits)
                paths.append((shorts, longs, market))
        print('Frozen allocation paths', u, e, len(cases), flush=True)
    matrix = np.array(matrices).T
    left, right = np.triu_indices(len(atoms))
    evaluation, prediction, selected_programs, economic = [], [], {}, []
    for attribution in ('fifo', 'lifo'):
        for kind in ('CE', 'PE', 'combined'):
            for asset in ('pooled', 'NIFTY', 'SENSEX'):
                eligible = [i for i, c in enumerate(cases) if c['attribution'] == attribution and c['kind'] == kind and (asset == 'pooled' or c['underlying'] == asset)]
                train = np.array([i for i in eligible if cases[i]['split'] == 'calibration'], int)
                test = np.array([i for i in eligible if cases[i]['split'] == 'evaluation'], int)
                if not len(train) or not len(test):
                    continue
                targets = np.array([cases[i]['target_minute'] for i in train])
                fallback = np.array([cases[i]['fallback_minute'] for i in train])
                pr = np.minimum(np.minimum(matrix[left][:, train], matrix[right][:, train]), fallback)
                errors = abs(pr-targets)
                hits = np.sum(errors <= 2, axis=1)
                complexity = (left != 0).astype(int)+(right != 0).astype(int)
                best = int(np.lexsort((complexity, errors.mean(axis=1), -hits))[0])
                name = attribution+'|'+kind+'|'+asset
                selected_programs[name] = dict(atom1=atoms[left[best]], atom2=atoms[right[best]], calibration_cases=len(train),
                                               calibration_match_rate=float(hits[best]/len(train)))
                for model in ('clock_only', 'selected_stop_program'):
                    out = []
                    for i in test:
                        c = cases[i]
                        guess = c['fallback_minute'] if model == 'clock_only' else min(matrix[left[best], i], matrix[right[best], i], c['fallback_minute'])
                        error = guess-c['target_minute']
                        row = dict(task=name, model=model, underlying=c['underlying'], expiry_date=c['expiry_date'],
                                   ids=c['ids'], observed_minute=c['target_minute'], predicted_minute=guess, error_minutes=error,
                                   ambiguous=c['ambiguous'], missing_path_minutes=c['missing_path_minutes'])
                        out.append(row)
                        prediction.append(row)
                        if asset != 'pooled' or model != 'selected_stop_program' or c['ambiguous']:
                            continue
                        shorts, longs, market = paths[i]
                        def outcome(signal):
                            when = datetime.fromtimestamp((signal+1)*60, logs.IST)
                            quotes = [market.bar(str(when.date()), p['strike'], p['option_type'], when.strftime('%H:%M')) for p in shorts+longs]
                            if not all(quotes): return None
                            debit = sum(q['open'] for q in quotes[:len(shorts)])-sum(q['open'] for q in quotes[len(shorts):])
                            quantity = c['quantity']
                            turnover = quantity*(sum(p['price'] for p in shorts+longs)+sum(q['open'] for q in quotes))
                            orders = 2*len(quotes)
                            cost = .0025*turnover+orders*20+orders*quantity*.05
                            return quantity*(c['initial_credit']-debit)-cost
                        a, b = outcome(guess), outcome(c['fallback_minute'])
                        width = max(abs(p['strike']-h['strike']) for p, h in zip(shorts, longs))
                        risk = c['quantity']*(width-c['initial_credit'])
                        if a is not None and b is not None and risk > 0:
                            economic.append(dict(task=name, underlying=c['underlying'], expiry_date=c['expiry_date'], ids=c['ids'],
                                                 candidate_net=a, clock_net=b, static_tail_loss=risk,
                                                 improvement_per_10000_tail_loss=(a-b)/risk*10000))
                    evaluation.append(dict(task=name, model=model, later_cases=len(out), matches_2m=int(sum(abs(r['error_minutes']) <= 2 for r in out)),
                                           match_rate=float(sum(abs(r['error_minutes']) <= 2 for r in out)/len(out)),
                                           mean_abs_error_minutes=float(np.mean([abs(r['error_minutes']) for r in out])),
                                           unambiguous_cases=sum(not r['ambiguous'] for r in out)))
    economic_summary = []
    for task in sorted({r['task'] for r in economic}):
        rows = [r for r in economic if r['task'] == task]
        weeks = defaultdict(list)
        for r in rows:
            date = datetime.fromisoformat(r['expiry_date']).date().isocalendar()
            weeks[(date.year, date.week)].append(r['improvement_per_10000_tail_loss'])
        values = list(weeks.values())
        rng = np.random.default_rng(20261026)
        samples = [np.mean([value for j in rng.integers(0, len(values), len(values)) for value in values[j]]) for _ in range(2000)]
        low, high = np.quantile(samples, [.025, .975])
        economic_summary.append(dict(task=task, allocations=len(rows), weeks=len(weeks), mean_improvement_per_10000_tail_loss=float(np.mean([r['improvement_per_10000_tail_loss'] for r in rows])),
                                     lower=float(low), upper=float(high)))
    save_records('allocation_frozen_stop_cases.csv', cases)
    save_records('allocation_frozen_stop_exclusions.csv', exclusions)
    save_records('allocation_frozen_stop_evaluation.csv', evaluation)
    save_records('allocation_frozen_stop_predictions.csv.gz', prediction)
    save_records('allocation_frozen_stop_economics.csv.gz', economic)
    save_records('allocation_frozen_stop_economic_summary.csv', economic_summary)
    (OUT/'allocation_frozen_stop_programs.json').write_text(json.dumps(selected_programs, indent=2)+'\n')
    (OUT/'allocation_frozen_stop_summary.json').write_text(json.dumps(dict(cases=len(cases), atoms=len(atoms), or_pairs=len(left), evaluation=evaluation,
        economic_summary=economic_summary,
        limitations=['Frozen inferred side/paired allocations, not original basket IDs; FIFO/LIFO targets differ.',
                     'Missing path minutes can hide earlier crossings. No missing quote is invented.',
                     'Targets are first partial short reductions, not necessarily full liquidation.',
                     'Economic comparison shares recorded entries and inferred frozen protection, uses next-minute open exits, stress costs and static expiry tail risk, not broker margin or independent entry alpha.',
                     'Later periods were already inspected. No full original strategy or capital controller is reproduced.']), indent=2)+'\n')


if __name__ == '__main__':
    main()
