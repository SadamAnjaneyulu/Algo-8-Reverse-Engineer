"""Retrospective event/control examples for the remaining controller gaps."""
import csv

from audit_strike_hedge_rules import OUT
from rank_trigger_probabilities import build_tasks, save_records


def minute_of_day(row):
    return int(row['clock'][:2]) * 60 + int(row['clock'][3:5])


def main():
    tasks = build_tasks()
    features = ['feature_cutoff_ist', 'last_completed_bar_start_ist', 'x_cutoff_ist',
                'x_short_units', 'x_long_units', 'x_hedge_coverage', 'x_side_imbalance_units',
                'x_net_equity_pct_capital', 'x_short_book_equity_pct_capital', 'x_long_book_equity_pct_capital',
                'x_realized_equity_pct_capital', 'x_unrealized_equity_pct_capital', 'x_max_short_loss_pct',
                'x_max_trailing_rise_pct', 'x_short_over4_fraction', 'x_short_over25_fraction',
                'x_since_short_minutes', 'x_since_cover_minutes', 'x_since_long_minutes',
                'x_short_orders_5m', 'x_cover_orders_5m', 'x_long_orders_5m',
                'x_prior_pair_spot_gap_steps', 'x_spot_change_since_pair_pct', 'reference_iv_pct',
                'spot_abs_return5_pct', 'time_since_last_pair_min', 'o_volume_pcr', 'o_oi_pcr',
                'o_ce_oi_change_5', 'o_pe_oi_change_5', 'o_ce_relative_volume_15', 'o_pe_relative_volume_15']
    result = []

    def add(task, row, label, case_kind, reference=''):
        identifier = row['cycle'] + '|' + row['date'] + '|' + row['clock']
        result.append(dict(case_id=identifier, task=task, case_kind=case_kind,
                           matched_event_case_id=reference, underlying=row['underlying'], expiry_date=row['expiry_date'],
                           date=row['date'], clock=row['clock'], observed_action=int(label),
                           **{key: row.get(key) for key in features}))
        return identifier

    for task_name, task in tasks.items():
        if 'closure' in task_name or task_name == 'preexpiry|quarter_entries':
            continue
        rows, y = task['rows'], task['truth']
        if task_name == 'expiry|quarter_entries':
            for row, label in zip(rows, y):
                if row['split'] == 'evaluation' and row['x_short_units'] > 0:
                    add(task_name, row, label, 'executed_quarter' if label else 'suppressed_quarter')
            continue
        controls = [(row, label) for row, label in zip(rows, y) if row['split'] == 'evaluation'
                    and not label and row['x_short_units'] > 0]
        for row, label in zip(rows, y):
            if row['split'] != 'evaluation' or not label:
                continue
            identifier = add(task_name, row, label, 'observed_event')
            choices = [(control, value) for control, value in controls
                       if control['underlying'] == row['underlying'] and control['cycle'] != row['cycle']
                       and abs(minute_of_day(control) - minute_of_day(row)) <= 15]
            choices.sort(key=lambda item: (abs(minute_of_day(item[0]) - minute_of_day(row)),
                                           abs(item[0]['x_short_units'] - row['x_short_units']),
                                           item[0]['expiry_date'], item[0]['clock']))
            used = set()
            for control, value in choices:
                if control['cycle'] in used:
                    continue
                add(task_name, control, value, 'matched_no_action_control', identifier)
                used.add(control['cycle'])
                if len(used) == 3:
                    break
    save_records('prob_trigger_casebook.csv', result)
    failures = [r for r in csv.DictReader((OUT / 'prob_exit_hypothesis_predictions.csv').open())
                if r['split'] == 'evaluation' and r['hypothesis'] == 'net_cycle_loss_0.5pct_OR_time'
                and r['after_aug3_cutoff'] == '915' and r['target_kind'] == 'first_short_flat'
                and r['matched_2m'] == 'False']
    save_records('prob_exit_priority_cases.csv', failures)
    print('Casebook rows:', len(result), 'Exit counterexamples:', len(failures))


if __name__ == '__main__':
    main()
