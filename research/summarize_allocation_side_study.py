"""Audit and consolidate allocation, cross-index and side-controller evidence."""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from audit_strike_hedge_rules import OUT, logs
from rank_trigger_probabilities import save_records


def read(name):
    opener = gzip.open if name.endswith('.gz') else open
    with opener(OUT/name, 'rt') as stream:
        yield from csv.DictReader(stream)


def main():
    sizes = list(read('allocation_size_schedule.csv'))
    normalized, agree = [], 0
    clocks = sorted({r['clock'] for r in sizes if r['phase'] == 'preexpiry'})
    for clock in clocks:
        group = [r for r in sizes if r['phase'] == 'preexpiry' and r['clock'] == clock]
        values = {r['underlying']: [float(r['modal_'+side+'_'+right])/logs.UNIT[r['underlying']]
                                   for side, right in [('short', 'CE'), ('short', 'PE'), ('long', 'CE'), ('long', 'PE')]] for r in group}
        same = values['NIFTY'] == values['SENSEX']
        agree += same
        normalized.append(dict(clock=clock, nifty_mode_units='|'.join(map(str, values['NIFTY'])),
                               sensex_mode_units='|'.join(map(str, values['SENSEX'])), normalized_modes_equal=same))
    save_records('allocation_cross_index_modal_schedule.csv', normalized)
    feature_count, full_greek = 0, 0
    keys = set()
    for r in read('allocation_contract_features.csv.gz'):
        t = datetime.fromisoformat(r['cutoff_ist'])
        assert datetime.fromisoformat(r['bar_start_ist']) == t-timedelta(minutes=1)
        assert float(r['g_short_units']) > 0
        if r['g_book_delta_per_short_unit']:
            assert float(r['g_model_coverage']) == 1
            full_greek += 1
        keys.add((r['underlying'], r['expiry_date'], int(r['strike']), r['option_type'], r['date'], r['clock']))
        feature_count += 1
    for r in read('allocation_index_context.csv.gz'):
        if r['indicator_available_at_ist']:
            assert datetime.fromisoformat(r['indicator_available_at_ist']) <= datetime.fromisoformat(r['cutoff_ist'])
    parent_rows = list(read('allocation_parent_inventory.csv'))
    parent_map = {r['parent_id']: r for r in parent_rows}
    byminute = defaultdict(list)
    for r in parent_rows:
        if r['role'] == 'new_short':
            byminute[(r['underlying'], r['expiry_date'], r['first'][:10], r['first'][11:16])].append(r)
    old_extra = [r for r in read('combo_action_predictions.csv.gz') if r['task'] == 'extra_pairs'
                 and r['kind'] == 'boolean_temporal' and r['target'] == '1']
    boundary_rows = []
    for r in old_extra:
        group = byminute[(r['underlying'], r['expiry_date'], r['date'], r['clock'])]
        early_timer = bool(group) and all(datetime.fromisoformat(p['first']).minute % 15 == 14
                                         and datetime.fromisoformat(p['first']).second >= 58 for p in group)
        boundary_rows.append(dict(underlying=r['underlying'], expiry_date=r['expiry_date'], date=r['date'],
                                  phase=r['phase'], clock=r['clock'], old_extra_label=1,
                                  all_new_short_parents_within2s_of_upcoming_quarter=early_timer))
    save_records('allocation_extra_boundary_label_audit.csv', boundary_rows)
    cover_keys = {(p['underlying'], p['expiry_date'], int(p['strike']), p['option_type'], p['first'][:10], p['first'][11:16])
                  for p in parent_rows if p['role'] == 'short_cover'}
    short_sums = defaultdict(float)
    for r in read('allocation_lot_closures.csv.gz'):
        if r['attribution'] == 'fifo':
            short_sums[(r['underlying'], r['expiry_date'])] += float(r['short_realized_pnl'])
    maximum_error = max(abs(short_sums[(r['underlying'], r['expiry_date'])]-float(r['short_position_realized_pnl_fifo']))
                        for r in read('option_profit_source_cycles.csv'))
    assert maximum_error < 1e-6
    for name in ('allocation_side_rule_predictions.csv.gz', 'allocation_entry_filter_predictions.csv.gz'):
        assert all(r['expiry_date'] > '2026-08-31' for r in read(name))
    for r in read('allocation_budget_inputs.csv'):
        assert datetime.fromisoformat(r['reference_bar_start_ist'])+timedelta(minutes=1) <= datetime.fromisoformat(r['reference_known_at_ist'])
    for r in read('allocation_frozen_stop_cases.csv'):
        entered = max(datetime.fromisoformat(parent_map[p]['last']) for p in (r['ids']+';'+r['hedge_ids']).split(';'))
        assert entered.timestamp()/60 < float(r['fallback_minute'])
        assert entered < datetime.fromisoformat(r['observed_first_reduction'])
    direction = []
    for r in read('allocation_side_direction_summary.csv'):
        denominator = int(r['losing_short_with_spot'])
        direction.append(dict(attribution=r['attribution'], underlying=r['underlying'], option_type=r['option_type'], phase=r['phase'],
                              losing_shorts=denominator, adverse_spot=int(r['losing_short_and_adverse_spot']),
                              adverse_fraction=int(r['losing_short_and_adverse_spot'])/denominator if denominator else None))
    labels = json.loads((OUT/'allocation_entry_label_summary.json').read_text())
    summary = dict(
        modal_schedules=dict(compared_clocks=len(clocks), matching_normalized_modes=agree, rows=normalized),
        audits=dict(contract_minutes=feature_count, contract_minutes_with_full_book_greek_fit=full_greek,
                    pure_cover_contract_minutes=len(cover_keys), cover_contract_minutes_with_prior_short_state=len(cover_keys & keys),
                    fifo_short_realized_pnl_max_error=maximum_error, all_market_cutoffs_checked=True,
                    later_prediction_dates_checked=True, frozen_exits_after_entry_checked=True),
        entry_label_correction=labels,
        extra_label_boundary=dict(old_later_paired_extra_minutes=len(boundary_rows),
                                  timer_only_within2s_of_next_quarter=sum(r['all_new_short_parents_within2s_of_upcoming_quarter'] for r in boundary_rows)),
        losing_short_direction=direction,
        limitations=['Modal schedule agreement is descriptive across all observed data, not independent code-identity proof.',
                     'Capital/margin per leg is unavailable. Quantities and premium cashflow do not identify it.',
                     'Exact allocation IDs are not recovered; inferred links and FIFO/LIFO remain sensitivity assumptions.',
                     'No 80-90 percent exit-controller recovery or original-backtest replication is established.'])
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('allocation_*')) if p.name != 'allocation_study_overview.json'}
    summary['sha256'] = manifest
    (OUT/'allocation_study_overview.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ('audits',)}, indent=2))


if __name__ == '__main__':
    main()
