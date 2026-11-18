"""Separate-side exit hypotheses, Greeks/OI and cross-index rule comparisons."""
import json
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import OUT
from allocation_rule_models import read_numeric, candidate_selection
from rank_trigger_probabilities import save_records


def normalize_side(row):
    right = row['option_type']
    other = 'PE' if right == 'CE' else 'CE'
    sign = 1 if right == 'CE' else -1
    banned = {'g_price', 'g_cost', 'g_fifo_cost', 'g_lifo_cost', 'g_spot', 'g_oi', 'g_volume',
              'g_contract_delta', 'g_contract_gamma', 'g_contract_vega_one_point', 'g_contract_theta_calendar_day',
              'g_fifo_spot_since_entry_pct', 'g_lifo_spot_since_entry_pct'}
    for name, value in list(row.items()):
        if not name.startswith('g_') or name in banned or name.startswith(('g_CE_', 'g_PE_', 'g_spot_return')):
            continue
        row['a_'+name[2:]] = value
    for side, prefix in ((right, 'same'), (other, 'opposite')):
        for name, value in list(row.items()):
            if name.startswith('g_'+side+'_'):
                suffix = name[len('g_'+side+'_'):]
                row['a_'+prefix+'_'+suffix] = value*sign if value is not None and 'delta_' in suffix else value
    row['a_book_delta_per_short_unit'] = abs(row['g_book_delta_per_short_unit']) if row['g_book_delta_per_short_unit'] is not None else None
    for field in ('vega_one_point', 'theta_calendar_day'):
        value = row['g_contract_'+field]
        row['a_contract_'+field+'_over_premium'] = value/row['g_price'] if value is not None and row['g_price'] else None
    row['a_contract_iv_minus_atm'] = row['g_contract_iv_pct']-row['g_atm_iv_pct'] if row['g_contract_iv_pct'] is not None and row['g_atm_iv_pct'] is not None else None
    row['a_clock_minute'] = int(row['clock'][:2])*60+int(row['clock'][3:5])-555
    row['a_clock_mod15'] = int(row['clock'][3:5]) % 15
    for name, value in list(row.items()):
        if not name.startswith('i_'):
            continue
        direction = name.startswith(('i_ema_gap_', 'i_bollinger_z_', 'i_spot_return_', 'i_supertrend_direction_', 'i_donchian_direction_')) or name in ('i_open_to_now_pct', 'i_twap_gap_pct', 'i_opening_gap_pct')
        row['a_'+name] = (value*sign if value is not None else None) if direction else (100-value if value is not None else None) if name.startswith('i_rsi_') and right == 'PE' and 'neutral' not in name else value
    return row


def prepared_rows(onsets_only=True):
    rows = read_numeric('allocation_contract_features.csv.gz')
    index_rows = read_numeric('allocation_index_context.csv.gz', prefixes=('i_',))
    indexed = {(r['underlying'], r['expiry_date'], r['date'], r['clock']): r for r in index_rows}
    contract_lookup = {(r['contract'], r['date'], r['clock']): r for r in rows}
    for r in rows:
        r.update({k: v for k, v in indexed[(r['underlying'], r['expiry_date'], r['date'], r['clock'])].items() if k.startswith('i_')})
        past = (datetime.fromisoformat(r['cutoff_ist'])-timedelta(minutes=5)).strftime('%H:%M')
        old = contract_lookup.get((r['contract'], r['date'], past))
        for field in ('iv_pct', 'abs_delta'):
            a = r['g_contract_'+field]
            b = old['g_contract_'+field] if old else None
            r['g_contract_'+field+'_change5'] = a-b if a is not None and b is not None else None
        normalize_side(r)
    # Compare first decisions after five quiet minutes, not continuation fills.
    return [r for r in rows if r['onset_eligible']] if onsets_only else rows


def common_side_features(row):
    return sorted(k for k in row if k.startswith('a_') and not (k.startswith('a_oi') or '_oi_' in k))


def main():
    rows = prepared_rows()
    fields = common_side_features(rows[0])
    all_scores, evaluations, predictions, programs, texts = [], [], [], {}, []
    for phase in ('preexpiry', 'expiry'):
        for scope in ('pooled_normalized', 'per_index', 'per_index_side'):
            group = defaultdict(list)
            for r in rows:
                if r['phase'] != phase:
                    continue
                key = 'all' if scope == 'pooled_normalized' else r['underlying'] if scope == 'per_index' else r['underlying']+'|'+r['option_type']
                group[key].append(r)
            for key, selected in sorted(group.items()):
                task = phase+'|'+scope+'|'+key
                y = np.array([bool(r['target_cover']) for r in selected])
                # Per-index/right fits use the same grammar and normalized inputs.
                kinds = ('tree4', 'tree6', 'boosted') if scope != 'per_index_side' else ('tree4', 'boosted')
                checks, result, pr, program, readable = candidate_selection(selected, y, fields, task, kinds)
                all_scores.extend(checks)
                evaluations.extend(result)
                predictions.extend(pr)
                programs[task] = program
                texts.extend(readable)
                print(task, [(r['policy'], r['precision'], r['recall']) for r in result], flush=True)
        # Test OI within NIFTY; all SENSEX supplied OI is missing.
        selected = [r for r in rows if r['phase'] == phase and r['underlying'] == 'NIFTY']
        task = phase+'|nifty_with_oi|NIFTY'
        oi_fields = sorted(k for k in selected[0] if k.startswith('a_'))
        checks, result, pr, program, readable = candidate_selection(selected, np.array([bool(r['target_cover']) for r in selected]), oi_fields, task)
        all_scores.extend(checks)
        evaluations.extend(result)
        predictions.extend(pr)
        programs[task] = program
        texts.extend(readable)
    save_records('allocation_side_rule_calibration.csv.gz', all_scores)
    save_records('allocation_side_rule_evaluation.csv', evaluations)
    save_records('allocation_side_rule_predictions.csv.gz', predictions)
    (OUT/'allocation_side_rule_programs.json').write_text(json.dumps(programs, indent=2, allow_nan=False)+'\n')
    (OUT/'allocation_side_rule_text.txt').write_text('\n\n'.join(texts).rstrip()+'\n')
    (OUT/'allocation_side_rule_summary.json').write_text(json.dumps(dict(
        onset_opportunities=len(rows), calibration_parameter_context_comparisons=len(all_scores), evaluation=evaluations,
        note='First contract-side cover decisions after five quiet minutes, conditioning on actual prior inventory. Exact-minute and one-to-one ±2-minute event scores are separate. Common inputs are side-normalized and omit OI; NIFTY OI is tested separately. Selected thresholds are scores, not calibrated causal probabilities.'), indent=2)+'\n')


if __name__ == '__main__':
    main()
