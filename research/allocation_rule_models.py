"""Cycle-separated candidate selection with false-signal and coverage accounting."""
import csv
import gzip
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier, export_text
from threadpoolctl import threadpool_limits

from audit_strike_hedge_rules import OUT
from mass_match_strategy_rules import score, cycle_weights
from search_rule_combinations import tree_structure


def read_numeric(name, prefixes=('g_', 'a_')):
    opener = gzip.open if name.endswith('.gz') else open
    with opener(OUT/name, 'rt') as stream:
        rows = list(csv.DictReader(stream))
    for r in rows:
        for key, value in r.items():
            if key.startswith(prefixes) or key in ('target_cover', 'target_cover_quantity', 'onset_eligible'):
                r[key] = float(value) if value else None
        r.setdefault('cycle', r['underlying']+'|'+r['expiry_date'])
    return rows


def cooldown_predictions(rows, raw, cooldown):
    result = np.zeros(len(rows), bool)
    last = {}
    for i in np.flatnonzero(raw):
        r = rows[i]
        key = (r.get('contract', r['cycle']), r['date'])
        current = int(r['clock'][:2])*60+int(r['clock'][3:5])
        if key not in last or current-last[key] >= cooldown:
            result[i] = True
            last[key] = current
    return result


def event_tolerance(rows, truth, predicted, tolerance=2):
    groups = defaultdict(lambda: [[], []])
    for r, y, p in zip(rows, truth, predicted):
        key = (r.get('contract', r['cycle']), r['date'])
        t = int(r['clock'][:2])*60+int(r['clock'][3:5])
        if y:
            groups[key][0].append(t)
        if p:
            groups[key][1].append(t)
    tp, signals, positives = 0, 0, 0
    for actual, guesses in groups.values():
        signals += len(guesses)
        positives += len(actual)
        if not actual or not guesses:
            continue
        distance = np.abs(np.array(guesses)[:, None]-np.array(actual)[None, :])
        cost = np.full((len(guesses), len(actual)+len(guesses)), 100.)
        cost[:, :len(actual)] = np.where(distance <= tolerance, distance, 1000)
        a, b = linear_sum_assignment(cost)
        tp += int(np.sum((b < len(actual)) & (cost[a, b] <= tolerance)))
    return dict(tolerance_minutes=tolerance, matched_events=tp, false_signals=signals-tp,
                missed_events=positives-tp, precision=tp/signals if signals else None,
                recall=tp/positives if positives else None)


def estimator(kind):
    if kind == 'tree4':
        model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, class_weight='balanced', random_state=20261026)
    elif kind == 'tree6':
        model = DecisionTreeClassifier(max_depth=6, min_samples_leaf=30, class_weight='balanced', random_state=20261026)
    elif kind == 'boosted':
        model = HistGradientBoostingClassifier(max_iter=70, max_leaf_nodes=7, min_samples_leaf=30,
                                              l2_regularization=10, early_stopping=False, random_state=20261026)
    else:
        raise ValueError(kind)
    return make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), model)


def event_probability(model, x):
    classes = list(model.classes_)
    if True not in classes:
        return np.zeros(len(x))
    return model.predict_proba(x)[:, classes.index(True)]


def candidate_selection(rows, y, features, task, kinds=('tree4', 'tree6', 'boosted'), cooldowns=(0, 5, 15)):
    x = np.array([[np.nan if r.get(k) is None else r[k] for k in features] for r in rows], float)
    train = np.array([i for i, r in enumerate(rows) if r['split'] == 'calibration'])
    test = np.array([i for i, r in enumerate(rows) if r['split'] == 'evaluation'])
    groups = np.array([rows[i]['cycle'] for i in train])
    calrows = [rows[i] for i in train]
    checks, bank = [], []
    for kind in kinds:
        oof = np.empty(len(train))
        with threadpool_limits(limits=1):
            for a, b in GroupKFold(n_splits=3).split(train, groups=groups):
                model = estimator(kind)
                model.fit(x[train[a]], y[train[a]])
                oof[b] = event_probability(model, x[train[b]])
        for threshold in np.arange(.05, .951, .05):
            for cooldown in cooldowns:
                predicted = cooldown_predictions(calrows, oof >= threshold, cooldown)
                stat = score(y[train], predicted, cycle_weights(rows, train))
                spec = dict(task=task, model=kind, threshold=float(threshold), cooldown=cooldown, **stat)
                checks.append(spec)
                bank.append((spec, predicted))
    def key(item):
        s = item[0]
        return (s['cycle_weighted_f1'], s['f1'], -(s['false_positives']), -s['cooldown'])
    selected = {'best_f1': max(bank, key=key)}
    for target in (.8, .9):
        eligible = [(s, p) for s, p in bank if s['signals'] >= 20 and s['precision'] >= target
                    and len({r['cycle'] for r, prediction in zip(calrows, p) if prediction}) >= 3]
        selected[f'precision_{target}'] = max(eligible, key=lambda item: (item[0]['recall'], *key(item))) if eligible else None
    fitted = {}
    results, predictions, programs, texts = [], [], {}, []
    for policy, chosen in selected.items():
        if chosen is None:
            predicted = np.zeros(len(test), bool)
            stat = dict(model='no_eligible_candidate', threshold=None, cooldown=None)
        else:
            spec = chosen[0]
            kind = spec['model']
            if kind not in fitted:
                model = estimator(kind)
                with threadpool_limits(limits=1):
                    model.fit(x[train], y[train])
                    probability = event_probability(model, x[test])
                fitted[kind] = (model, probability)
            model, probability = fitted[kind]
            predicted = cooldown_predictions([rows[i] for i in test], probability >= spec['threshold'], spec['cooldown'])
            stat = {k: spec[k] for k in ('model', 'threshold', 'cooldown')}
            if kind.startswith('tree'):
                imputer, tree = model.steps[0][1], model.steps[1][1]
                programs[policy] = dict(**stat, input_features=features, median_statistics=imputer.statistics_.tolist(),
                                       missing_indicator_features=imputer.indicator_.features_.tolist(),
                                       tree=tree_structure(tree, imputer.get_feature_names_out(features).tolist()))
                texts.append(task+' '+policy+'\n'+export_text(tree, feature_names=imputer.get_feature_names_out(features).tolist(), decimals=5))
        metric = score(y[test], predicted, cycle_weights(rows, test))
        tolerance = event_tolerance([rows[i] for i in test], y[test], predicted)
        results.append(dict(task=task, policy=policy, **stat, **metric,
                            tolerance2_precision=tolerance['precision'], tolerance2_recall=tolerance['recall']))
        for i, p in zip(test, predicted):
            predictions.append(dict(task=task, policy=policy, underlying=rows[i]['underlying'],
                                    expiry_date=rows[i]['expiry_date'], date=rows[i]['date'], clock=rows[i]['clock'],
                                    contract=rows[i].get('contract', ''), target=int(y[i]), predicted=int(p)))
    return checks, results, predictions, programs, texts
