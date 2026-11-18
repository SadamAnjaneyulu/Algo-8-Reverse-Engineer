"""Named premium, carry, trailing, Greek, range and OI exit candidates."""
import json

import numpy as np

from audit_strike_hedge_rules import OUT
from allocation_rule_models import cooldown_predictions, event_tolerance
from mass_match_strategy_rules import score
from rank_trigger_probabilities import save_records
from search_side_controllers import prepared_rows


def catalog():
    result = []
    groups = [
        ('premium_loss', 'a_loss_pct', (10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 100, 150), 'gt'),
        ('profit', 'a_loss_pct', (-10, -20, -25, -30, -40, -50, -60, -70, -80, -90, -95), 'le'),
        ('lot_loss', 'a_fifo_max_loss_pct', (10, 25, 40, 50, 60, 70, 75, 100), 'gt'),
        ('lot_loss_lifo', 'a_lifo_max_loss_pct', (10, 25, 40, 50, 60, 70, 75, 100), 'gt'),
        ('trailing', 'a_trailing_recovery_pct', (5, 10, 20, 25, 30, 50, 75, 100), 'gt'),
        ('carry_previous_close', 'a_from_previous_close_pct', (2, 3, 4, 5, 10, 20, 50), 'gt'),
        ('expiry_open', 'a_from_expiry_open_pct', (2, 3, 4, 5, 10, 20, 50), 'gt'),
        ('delta', 'a_contract_abs_delta', (.5, .55, .6, .65, .7, .75, .8, .85, .9, .95), 'gt'),
        ('iv', 'a_contract_iv_pct_change5', (.1, .25, .5, 1, 2, 3), 'gt'),
        ('gamma', 'a_contract_gamma_move1pct_over_premium', (.25, .5, 1, 2, 3, 5, 10), 'gt'),
        ('side_pnl', 'a_same_equity_pct_capital', (-1, -.75, -.5, -.4, -.25, -.1, 0), 'le'),
        ('movement', 'a_adverse_spot5_pct', (.025, .05, .1, .2, .3, .5, 1), 'gt'),
        ('entry_movement', 'a_adverse_spot_since_entry_pct', (.05, .1, .2, .3, .5, .75, 1), 'gt'),
        ('trend', 'a_i_adx_14', (15, 20, 25, 30, 40, 50), 'gt'),
        ('range', 'a_i_efficiency15', (.2, .3, .4, .5, .6, .8), 'gt'),
        ('oi_change', 'a_oi_change5_pct', (-10, -5, -2, 0, 2, 5, 10, 20), 'gt'),
        ('oi_ratio', 'a_same_strike_oi_ratio', (.5, .75, 1, 1.5, 2, 3), 'gt'),
    ]
    for family, field, levels, op in groups:
        for threshold in levels:
            for crossing in (False, True):
                result.append(dict(family=family, field=field, threshold=threshold, operator=op, crossing=crossing))
    return result


def rule_mask(rows, rule):
    values = np.array([np.nan if r.get(rule['field']) is None else r[rule['field']] for r in rows])
    valid = np.isfinite(values)
    state = valid & ((values <= rule['threshold']) if rule['operator'] == 'le' else (values > rule['threshold']))
    if not rule['crossing']:
        return state
    result = state.copy()
    previous = {}
    for i, r in enumerate(rows):
        key = (r['contract'], r['date'])
        if key in previous:
            result[i] &= not previous[key]
        previous[key] = bool(state[i])
    return result


def main():
    all_rows = prepared_rows(False)
    trials, evaluations, programs = [], [], {}
    for phase in ('preexpiry', 'expiry'):
        for u in ('NIFTY', 'SENSEX'):
            rows = [r for r in all_rows if r['phase'] == phase and r['underlying'] == u]
            train = np.array([i for i, r in enumerate(rows) if r['split'] == 'calibration' and r['onset_eligible']])
            test = np.array([i for i, r in enumerate(rows) if r['split'] == 'evaluation' and r['onset_eligible']])
            truth = np.array([bool(r['target_cover']) for r in rows])
            best = {}
            for rule in catalog():
                if 'oi' in rule['family'] and u == 'SENSEX':
                    continue
                mask = rule_mask(rows, rule)
                mask &= np.array([bool(r['onset_eligible']) for r in rows])
                for cooldown in (0, 5, 15):
                    predicted = cooldown_predictions(rows, mask, cooldown)
                    stat = score(truth[train], predicted[train])
                    spec = dict(phase=phase, underlying=u, cooldown=cooldown, **rule, **stat)
                    trials.append(spec)
                    key = (stat['f1'], -stat['false_positives'], -cooldown)
                    if rule['family'] not in best or key > best[rule['family']][0]:
                        best[rule['family']] = (key, spec, predicted)
            for family, (_, spec, predicted) in best.items():
                tolerance = event_tolerance([rows[i] for i in test], truth[test], predicted[test])
                evaluations.append(dict(phase=phase, underlying=u, family=family,
                                        **{k: spec[k] for k in ('field', 'threshold', 'operator', 'crossing', 'cooldown')},
                                        calibration_f1=spec['f1'], **score(truth[test], predicted[test]),
                                        tolerance2_precision=tolerance['precision'], tolerance2_recall=tolerance['recall']))
                programs[phase+'|'+u+'|'+family] = spec
    save_records('allocation_named_exit_calibration.csv.gz', trials)
    save_records('allocation_named_exit_evaluation.csv', evaluations)
    (OUT/'allocation_named_exit_programs.json').write_text(json.dumps(programs, indent=2)+'\n')


if __name__ == '__main__':
    main()
