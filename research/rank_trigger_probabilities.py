"""Empirical hypothesis probabilities and cycle-separated probabilistic triggers.

Probabilities describe recorded events conditional on known context. They are
not posterior probabilities that a particular indicator is the original code.
"""
import json
import math
from datetime import datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text
from threadpoolctl import threadpool_limits

from audit_strike_hedge_rules import OUT, write
from combo_features import context_grid, datasets
from combo_option_flow import flow_grid
from search_exit_combinations import build_inputs, minute
from search_rule_combinations import decorate, tree_structure
from strategy_rule_features import predicate_grid


def save_records(name, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    write(name, [{key: row.get(key) for key in fields} for row in rows])


def wilson(successes, total):
    if not total:
        return None, None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    middle = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return middle - half, middle + half


def event_metrics(truth, predicted):
    truth, predicted = np.asarray(truth, bool), np.asarray(predicted, bool)
    tp = int(np.sum(truth & predicted))
    fp = int(np.sum(~truth & predicted))
    fn = int(np.sum(truth & ~predicted))
    lower, upper = wilson(tp, tp + fp)
    return dict(opportunities=len(truth), positives=int(truth.sum()), signals=tp + fp,
                correct_signals=tp, false_signals=fp, missed_events=fn,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                precision_wilson_lower=lower, precision_wilson_upper=upper)


def cycle_precision_interval(rows, truth, predicted):
    groups = sorted({r['cycle'] for r in rows})
    lookup = {key: i for i, key in enumerate(groups)}
    counts = np.zeros((len(groups), 2))
    for row, y, signal in zip(rows, truth, predicted):
        if signal:
            counts[lookup[row['cycle']]] += (int(y), 1)
    if not counts[:, 1].sum():
        return dict(precision_cycle_lower=None, precision_cycle_upper=None)
    rng = np.random.default_rng(20261027)
    samples = counts[rng.integers(0, len(groups), size=(2000, len(groups)))].sum(axis=1)
    samples = samples[samples[:, 1] > 0]
    low, high = np.quantile(samples[:, 0] / samples[:, 1], [.025, .975])
    return dict(precision_cycle_lower=float(low), precision_cycle_upper=float(high))


def select_threshold(rows, truth, probability, target):
    """Use earlier out-of-cycle predictions only; later labels are not arguments."""
    choices = []
    for threshold in np.r_[np.arange(.05, .951, .025), .98, .99]:
        predicted = probability >= threshold
        score = event_metrics(truth, predicted)
        cycles = len({r['cycle'] for r, signal in zip(rows, predicted) if signal})
        if score['signals'] >= 20 and cycles >= 3 and score['precision'] >= target:
            choices.append((score['recall'], score['precision'], threshold, score))
    if not choices:
        return None
    _, _, threshold, score = max(choices, key=lambda x: (x[0], x[1], -x[2]))
    return dict(threshold=float(threshold), calibration=score)


def first_alert(rows, probability, threshold, target_minutes):
    """One predicted alert per cycle; no hindsight replacement of an early alert."""
    predictions = {}
    if threshold is not None:
        for r, p in zip(rows, probability):
            if p >= threshold and r['cycle'] not in predictions:
                predictions[r['cycle']] = minute(datetime.fromisoformat(r['available_at_ist']))
    records = []
    for cycle, target in sorted(target_minutes.items()):
        guess = predictions.get(cycle)
        records.append(dict(cycle=cycle, observed_minute=target, predicted_minute=guess,
                            error_minutes=guess - target if guess is not None else None,
                            matched_2m=guess is not None and abs(guess - target) <= 2))
    return records


def numeric_features(rows, exit_task=False):
    result = []
    for name in rows[0]:
        allowed = predicate_grid([name]) or context_grid([name]) or flow_grid([name])
        if exit_task and not name.startswith('x_'):
            allowed = name.endswith('_pct_capital') or name == 'short_unrealized_pct_credit'
        if allowed and not name.endswith('_ist'):
            result.append(name)
    return sorted(set(result + ['clock_minute', 'clock_mod15', 'is_sensex', 'is_expiry']))


def build_tasks():
    slow, fast = datasets(include_flow=True)
    decorate(slow)
    decorate(fast)
    tasks = {}
    for phase in ('preexpiry', 'expiry'):
        quarter = [r for r in slow if r['phase'] == phase and r['quarter_target'] is not None]
        extra = [r for r in fast if r['phase'] == phase and r['off_quarter']]
        # Cover-onset opportunities deliberately exclude ongoing covering bursts.
        onset = [r for r in fast if r['phase'] == phase and r['x_short_units'] > 0
                 and (r['x_since_cover_minutes'] is None or r['x_since_cover_minutes'] > 5)]
        for kind, rows, target in [('quarter_entries', quarter, 'quarter_target'),
                                   ('extra_entries', extra, 'paired_sale'),
                                   ('cover_onsets', onset, 'short_cover')]:
            tasks[phase + '|' + kind] = dict(rows=rows, truth=np.array([bool(r[target]) for r in rows]))
    exit_rows, targets, labels = [], {}, []
    for cycle in build_inputs():
        target = cycle['targets']['first_short_flat']
        if target is None:
            continue
        key = cycle['underlying'] + '|' + cycle['expiry_date']
        targets[key] = target
        for point in cycle['path']:
            current = minute(point['t'])
            # Survival risk set: after the observed first closure this target has
            # already occurred. It is a conditional first-closure hazard study.
            if point['short_quantity'] <= 0 or current > target:
                continue
            row = {k: v for k, v in point.items() if k != 't'}
            row.update(underlying=cycle['underlying'], expiry_date=cycle['expiry_date'],
                       cycle=key, phase='expiry', date=cycle['expiry_date'],
                       clock=point['t'].strftime('%H:%M'), available_at_ist=point['t'].isoformat(),
                       split='calibration' if cycle['expiry_date'] <= '2026-08-31' else 'evaluation')
            exit_rows.append(row)
            labels.append(0 <= target - current < 3)
    decorate(exit_rows)
    tasks['expiry|first_closure_next_3m'] = dict(rows=exit_rows, truth=np.array(labels), target_minutes=targets)
    return tasks


def estimator(kind):
    if kind == 'logistic':
        model = make_pipeline(StandardScaler(), LogisticRegression(C=.1, max_iter=2000))
    elif kind == 'forest':
        model = RandomForestClassifier(n_estimators=120, max_depth=8, min_samples_leaf=10,
                                       n_jobs=2, random_state=20261027)
    elif kind == 'boosted':
        model = HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15,
                                              min_samples_leaf=20, l2_regularization=5,
                                              early_stopping=False, random_state=20261027)
    elif kind == 'readable_tree':
        model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=20, random_state=20261027)
    else:
        raise ValueError(kind)
    return make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), model)


def probability_logit(probability):
    p = np.clip(probability, 1e-5, 1 - 1e-5)
    return np.log(p / (1 - p)).reshape(-1, 1)


def predict_tree_probability(program, rows):
    tree = program['tree']
    results = []
    for row in rows:
        raw = [np.nan if row.get(key) is None else float(row[key]) for key in program['input_features']]
        values = [program['median_statistics'][i] if not np.isfinite(value) else value for i, value in enumerate(raw)]
        values.extend(float(not np.isfinite(raw[i])) for i in program['missing_indicator_features'])
        values = np.asarray(values, dtype=np.float32)
        node = 0
        while tree['children_left'][node] >= 0:
            node = tree['children_left'][node] if values[tree['feature'][node]] <= tree['threshold'][node] else tree['children_right'][node]
        weights = tree['values'][node][0]
        probability = weights[tree['classes'].index(True)] / sum(weights)
        logit = probability_logit(np.array([probability]))[0, 0]
        calibrated_logit = program['sigmoid_coefficient'] * logit + program['sigmoid_intercept']
        results.append(float(1 / (1 + np.exp(-np.clip(calibrated_logit, -700, 700)))))
    return np.array(results)


def conditional_hypotheses(tasks):
    records = []
    clocks = {'09:30', '09:45', '10:00', '10:15', '10:30', '10:45', '11:00', '11:15',
              '11:30', '11:45', '12:00', '12:30', '13:30', '13:45', '14:00', '14:15', '14:30'}
    for name, task in tasks.items():
        if 'closure' in name:
            continue
        rows, y = task['rows'], task['truth']
        rules = {
            'active_short_book': lambda r: r['x_short_units'] > 0,
            'recurring_preexpiry_clock_and_active': lambda r: r['clock'] in clocks and r['x_short_units'] > 0,
            'active_and_cycle_net_above_minus_0.4pct': lambda r: r['x_short_units'] > 0 and r.get('x_net_equity_pct_capital') is not None and r['x_net_equity_pct_capital'] > -.4,
            'short_premium_stress_above_4pct': lambda r: r.get('x_max_short_loss_pct') is not None and r['x_max_short_loss_pct'] > 4,
            'short_premium_stress_above_25pct': lambda r: r.get('x_max_short_loss_pct') is not None and r['x_max_short_loss_pct'] > 25,
            'cycle_net_loss_below_minus_0.5pct': lambda r: r.get('x_net_equity_pct_capital') is not None and r['x_net_equity_pct_capital'] <= -.5,
            'cycle_net_loss_below_minus_1pct': lambda r: r.get('x_net_equity_pct_capital') is not None and r['x_net_equity_pct_capital'] <= -1,
            'prior_pair_spot_distance_above_one_step': lambda r: r.get('x_prior_pair_spot_gap_steps') is not None and abs(r['x_prior_pair_spot_gap_steps']) > 1,
        }
        for rule_name, condition in rules.items():
            mask = np.array([condition(r) for r in rows])
            for split in ('calibration', 'evaluation'):
                selected = np.array([r['split'] == split for r in rows])
                score = event_metrics(y[selected], mask[selected])
                opposite = event_metrics(y[selected], ~mask[selected])
                records.append(dict(task=name, hypothesis=rule_name, split=split, **score,
                                    probability_without_condition=opposite['precision'],
                                    **cycle_precision_interval([r for r, s in zip(rows, selected) if s], y[selected], mask[selected]),
                                    covered_cycles=len({r['cycle'] for r, s in zip(rows, mask & selected) if s})))
    return records


def main():
    tasks = build_tasks()
    evaluations, reliability, trials, prediction_rows, closure_rows, rules = [], [], [], [], [], []
    selections, tree_programs = {}, {}
    for name, task in tasks.items():
        rows, y = task['rows'], task['truth']
        features = numeric_features(rows, 'closure' in name)
        x = np.array([[np.nan if r.get(k) is None else r[k] for k in features] for r in rows], dtype=float)
        train = np.array([i for i, r in enumerate(rows) if r['split'] == 'calibration'])
        test = np.array([i for i, r in enumerate(rows) if r['split'] == 'evaluation'])
        groups = np.array([rows[i]['cycle'] for i in train])
        split = GroupKFold(n_splits=3)
        train_rows = [rows[i] for i in train]
        model_results = []
        for kind in ('logistic', 'forest', 'boosted', 'readable_tree'):
            oof = np.empty(len(train))
            with threadpool_limits(limits=1):
                for a, b in split.split(train, groups=groups):
                    model = estimator(kind)
                    model.fit(x[train[a]], y[train[a]])
                    oof[b] = model.predict_proba(x[train[b]])[:, 1]
                calibrator = LogisticRegression(C=1, max_iter=1000)
                calibrator.fit(probability_logit(oof), y[train])
                calp = calibrator.predict_proba(probability_logit(oof))[:, 1]
                model = estimator(kind)
                model.fit(x[train], y[train])
                later = calibrator.predict_proba(probability_logit(model.predict_proba(x[test])[:, 1]))[:, 1]
            selections_here = {str(target): select_threshold(train_rows, y[train], calp, target) for target in (.8, .9)}
            model_results.append(dict(kind=kind, p=later, calibration_brier=brier_score_loss(y[train], calp), choices=selections_here))
            for threshold in (.5, .8, .9):
                score = event_metrics(y[test], later >= threshold)
                evaluations.append(dict(task=name, model=kind, policy='fixed_probability', threshold=threshold, **score))
            for target, selected in selections_here.items():
                trials.append(dict(task=name, model=kind, target_precision=float(target),
                                   eligible=selected is not None,
                                   threshold=selected['threshold'] if selected else None,
                                   **(selected['calibration'] if selected else {})))
            for low, high in zip((0, .1, .3, .5, .7, .8, .9), (.1, .3, .5, .7, .8, .9, 1.00001)):
                mask = (later >= low) & (later < high)
                n = int(mask.sum())
                correct = int(y[test][mask].sum())
                lower, upper = wilson(correct, n)
                reliability.append(dict(task=name, model=kind, lower_probability=low, upper_probability=min(high, 1),
                                        rows=n, actual_events=correct, estimated_probability=float(later[mask].mean()) if n else None,
                                        observed_probability=correct / n if n else None, wilson_lower=lower, wilson_upper=upper))
            for i, probability in zip(test, later):
                prediction_rows.append(dict(task=name, model=kind, underlying=rows[i]['underlying'],
                                            expiry_date=rows[i]['expiry_date'], date=rows[i]['date'], clock=rows[i]['clock'],
                                            target=int(y[i]), probability=float(probability)))
            if kind == 'readable_tree':
                imputer, tree = model.steps[0][1], model.steps[1][1]
                rules.append(name + '\n' + export_text(tree, feature_names=imputer.get_feature_names_out(features).tolist(),
                                                      show_weights=True, decimals=5))
                program = dict(input_features=features, median_statistics=imputer.statistics_.tolist(),
                               missing_indicator_features=imputer.indicator_.features_.tolist(),
                               tree=tree_structure(tree, imputer.get_feature_names_out(features).tolist()),
                               sigmoid_coefficient=float(calibrator.coef_[0, 0]),
                               sigmoid_intercept=float(calibrator.intercept_[0]), probability_clip=1e-5,
                               training_expiry_through='2026-08-31')
                np.testing.assert_allclose(predict_tree_probability(program, [rows[i] for i in test]), later, atol=1e-12)
                tree_programs[name] = program
            print('Probability model', name, kind, 'later Brier', round(brier_score_loss(y[test], later), 4), flush=True)
        selections[name] = {}
        for target in (.8, .9):
            eligible = [m for m in model_results if m['choices'][str(target)] is not None]
            chosen = max(eligible, key=lambda m: (m['choices'][str(target)]['calibration']['recall'],
                                                m['choices'][str(target)]['calibration']['precision'], -m['calibration_brier'])) if eligible else None
            selections[name][str(target)] = None if chosen is None else dict(model=chosen['kind'], **chosen['choices'][str(target)])
            probability = chosen['p'] if chosen is not None else np.zeros(len(test))
            threshold = chosen['choices'][str(target)]['threshold'] if chosen is not None else None
            predicted = probability >= threshold if threshold is not None else np.zeros(len(test), bool)
            evaluations.append(dict(task=name, model=chosen['kind'] if chosen else 'no_eligible_model',
                                    policy='calibration_selected_precision', requested_precision=target, threshold=threshold,
                                    **event_metrics(y[test], predicted),
                                    **cycle_precision_interval([rows[i] for i in test], y[test], predicted)))
            for underlying in ('NIFTY', 'SENSEX'):
                mask = np.array([rows[i]['underlying'] == underlying for i in test])
                evaluations.append(dict(task=name, underlying=underlying,
                                        model=chosen['kind'] if chosen else 'no_eligible_model',
                                        policy='selected_precision_by_index', requested_precision=target,
                                        threshold=threshold, **event_metrics(y[test][mask], predicted[mask])))
            if 'target_minutes' in task:
                target_times = {key: value for key, value in task['target_minutes'].items() if key.split('|')[1] > '2026-08-31'}
                for r in first_alert([rows[i] for i in test], probability, threshold, target_times):
                    closure_rows.append(dict(requested_precision=target, model=chosen['kind'] if chosen else None, **r))
        # Probability scoring is shown against the empirical event prior; high
        # raw accuracy from predicting no event is deliberately not reported.
        for m in model_results:
            evaluations.append(dict(task=name, model=m['kind'], policy='probability_quality',
                                    brier=brier_score_loss(y[test], m['p']),
                                    prior_brier=brier_score_loss(y[test], np.full(len(test), y[train].mean())),
                                    average_precision=average_precision_score(y[test], m['p']),
                                    later_event_rate=float(y[test].mean()), log_loss=log_loss(y[test], m['p'], labels=[False, True])))
    hypotheses = conditional_hypotheses(tasks)
    save_records('prob_hypothesis_evidence.csv', hypotheses)
    save_records('prob_model_evaluation.csv', evaluations)
    save_records('prob_calibration_selection.csv', trials)
    save_records('prob_reliability_bins.csv', reliability)
    save_records('prob_later_predictions.csv.gz', prediction_rows)
    save_records('prob_first_closure_alerts.csv', closure_rows)
    (OUT / 'prob_readable_trees.txt').write_text('\n\n'.join(rules).rstrip() + '\n')
    (OUT / 'prob_tree_programs.json').write_text(json.dumps(tree_programs, indent=2, allow_nan=False) + '\n')
    summary = dict(selections=selections,
                   later_selected=[r for r in evaluations if r['policy'] == 'calibration_selected_precision'],
                   closure_alerts=closure_rows,
                   hypothesis_evidence=[r for r in hypotheses if r['split'] == 'evaluation'],
                   limitations=[
                       'Predictive conditional event probabilities, not probabilities of original-code identity or causal effects.',
                       'All thresholds/model choices use earlier cycle-separated out-of-fold predictions; sigmoid calibration is fitted on those earlier predictions.',
                       'Those calibration/threshold scores are selection scores, not independent validation. Later cycles were inspected in earlier research.',
                       'State follows actual prior inventory; this is not an autonomous counterfactual replay.',
                       'Quarter targets are execution windows; extras/covers are exact physical minutes, 09:18-14:43 only.',
                       'Cover onset means no cover fills in the preceding five minutes, not a verified stop or portfolio-exit reason.',
                       'First-closure hazards use the observed at-risk path before the first full short closure and include opening-price proxies.',
                       'Wilson intervals treat opportunities as independent and are descriptive; repeated observations within cycles reduce effective sample size.',
                       'No 80-90 percent profitable-trade or economic-alpha claim follows from order matching.' ])
    (OUT / 'prob_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
