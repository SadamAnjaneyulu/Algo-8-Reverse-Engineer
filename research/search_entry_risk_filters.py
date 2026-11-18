"""Range/Greek/OI entry filters and the 27 active-book expiry suppressions."""
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import OUT, logs
from allocation_rule_models import candidate_selection, read_numeric
from combo_features import datasets
from rank_trigger_probabilities import save_records, event_metrics


def build_rows():
    slow, fast = datasets(include_flow=True)
    greek = read_numeric('allocation_greek_context.csv.gz')
    index = read_numeric('allocation_index_context.csv.gz', prefixes=('i_',))
    gmap = {(r['underlying'], r['expiry_date'], r['date'], r['clock']): r for r in greek}
    imap = {(r['underlying'], r['expiry_date'], r['date'], r['clock']): r for r in index}
    sizes = {(r['underlying'], r['expiry_date'], r['date'], r['clock']): r for r in csv.DictReader((OUT/'allocation_window_sizes.csv').open())}
    offschedule = set()
    for p in csv.DictReader((OUT/'allocation_parent_inventory.csv').open()):
        if p['role'] != 'new_short':
            continue
        when = datetime.fromisoformat(p['first'])
        timer = when.replace(hour=9, minute=30, second=0)
        planned = False
        while timer.hour*60+timer.minute <= 870:
            if -2 <= (when-timer).total_seconds() < 180:
                planned = True
                break
            timer += timedelta(minutes=15)
        if not planned:
            offschedule.add((p['underlying'], p['expiry_date'], str(when.date()), when.strftime('%H:%M')))
    for rows, embargo in ((slow, 1), (fast, 0)):
        for r in rows:
            t = datetime.fromisoformat(r['date']+'T'+r['clock']).replace(tzinfo=logs.IST)-timedelta(minutes=embargo)
            key = (r['underlying'], r['expiry_date'], r['date'], t.strftime('%H:%M'))
            r.update({k: v for k, v in gmap[key].items() if k.startswith('g_')})
            r.update({k: v for k, v in imap[key].items() if k.startswith('i_')})
            r['a_clock_minute'] = int(r['clock'][:2])*60+int(r['clock'][3:5])-555
            r['a_clock_mod15'] = int(r['clock'][3:5]) % 15
            r['target_offschedule_any_short'] = (r['underlying'], r['expiry_date'], r['date'], r['clock']) in offschedule
            for window in (5, 15, 30):
                vol = r.get(f'i_realized_vol{window}_annual_pct')
                r[f'a_iv_over_intraday_rv{window}'] = r['g_atm_iv_pct']/vol if vol and r['g_atm_iv_pct'] is not None else None
            size = sizes.get((r['underlying'], r['expiry_date'], r['date'], r['clock']))
            if size:
                ce, pe = float(size['new_short_CE_quantity']), float(size['new_short_PE_quantity'])
                r['target_any_short'] = ce+pe > 0
                r['target_both_rights'] = ce > 0 and pe > 0
    active = [r for r in slow if r['phase'] == 'expiry' and r['quarter_target'] is not None and r['x_short_units'] > 0]
    return {
        'expiry_same_strike_suppression': active,
        'expiry_any_short_suppression': active,
        'expiry_both_rights_suppression': active,
        'preexpiry_extra': [r for r in fast if r['phase'] == 'preexpiry' and r['off_quarter']],
        'expiry_extra': [r for r in fast if r['phase'] == 'expiry' and r['off_quarter']],
        'preexpiry_offschedule_any': [r for r in fast if r['phase'] == 'preexpiry' and r['off_quarter']],
        'expiry_offschedule_any': [r for r in fast if r['phase'] == 'expiry' and r['off_quarter']],
    }


def range_catalog():
    return [(family, field, threshold, op)
            for family, field, levels, op in [
                ('trend_ADX', 'i_adx_14', (10, 15, 20, 25, 30, 35, 40), 'le'),
                ('neutral_RSI', 'i_rsi_neutral_distance_14', (5, 10, 15, 20, 25, 30), 'le'),
                ('trend_efficiency', 'i_efficiency15', (.1, .2, .3, .4, .5, .6, .7, .8), 'le'),
                ('recent_range', 'g_range15_pct', (.1, .15, .2, .25, .3, .4, .5, .75, 1), 'le'),
                ('implied_realized', 'a_iv_over_intraday_rv15', (.5, .75, 1, 1.25, 1.5, 2, 3, 4), 'gt'),
                ('net_delta', 'g_book_delta_per_short_unit', (-.3, -.2, -.1, 0, .1, .2, .3), 'le'),
                ('vega_budget', 'g_book_vega_pct_capital', (-.2, -.1, -.05, -.025, -.01), 'gt'),
                ('gamma_budget', 'g_book_gamma_move1pct_pct_capital', (-2, -1, -.75, -.5, -.25, -.1), 'gt'),
                ('OI_PCR', 'o_oi_pcr', (.5, .75, 1, 1.25, 1.5, 2, 3), 'le')]
            for threshold in levels]


def main():
    tasks = build_rows()
    trials, evaluations, predictions, texts, programs = [], [], [], [], {}
    for task, dataset in tasks.items():
        for scope in ('pooled_common', 'per_index', 'nifty_with_oi'):
            groups = defaultdict(list)
            for r in dataset:
                if scope == 'nifty_with_oi' and r['underlying'] != 'NIFTY':
                    continue
                groups['all' if scope == 'pooled_common' else r['underlying']].append(r)
            for group, rows in groups.items():
                fields = sorted(k for k in rows[0] if k.startswith(('g_', 'i_', 'x_', 'a_')) and not k.endswith('_ist') and k != 'g_spot')
                if scope == 'nifty_with_oi':
                    fields += sorted(k for k in rows[0] if k.startswith('o_'))
                if 'suppression' in task:
                    field = 'target_any_short' if 'any_short' in task else 'target_both_rights' if 'both_rights' in task else 'quarter_target'
                    truth = np.array([not bool(r[field]) for r in rows])
                else:
                    field = 'target_offschedule_any_short' if 'offschedule_any' in task else 'paired_sale'
                    truth = np.array([bool(r[field]) for r in rows])
                name = task+'|'+scope+'|'+group
                checks, result, pr, program, readable = candidate_selection(rows, truth, fields, name, cooldowns=(0,) if 'suppression' in task else (0, 5, 15))
                trials.extend(checks)
                programs[name] = program
                texts.extend(readable)
                for r in result:
                    if 'suppression' in task:
                        selected = [p for p in pr if p['policy'] == r['policy']]
                        metric = event_metrics([not bool(p['target']) for p in selected], [not bool(p['predicted']) for p in selected])
                        r.update(entry_precision=metric['precision'], entry_recall=metric['recall'],
                                 entry_false_signals=metric['false_signals'], entry_missed=metric['missed_events'])
                evaluations.extend(result)
                predictions.extend(pr)
                print(name, [(r['policy'], r['precision'], r['recall']) for r in result], flush=True)
    named, named_trials = [], []
    rows = tasks['expiry_any_short_suppression']
    for u in ('NIFTY', 'SENSEX'):
        selected = [r for r in rows if r['underlying'] == u]
        train = np.array([i for i, r in enumerate(selected) if r['split'] == 'calibration'])
        test = np.array([i for i, r in enumerate(selected) if r['split'] == 'evaluation'])
        y = np.array([not bool(r['target_any_short']) for r in selected])
        best = {}
        for family, field, threshold, operator in range_catalog():
            if family == 'OI_PCR' and u == 'SENSEX':
                continue
            values = np.array([np.nan if r.get(field) is None else r[field] for r in selected])
            known = np.isfinite(values)
            allow = known & ((values <= threshold) if operator == 'le' else (values > threshold))
            # Missing inputs abstain from filtering: no synthetic rejection.
            reject = known & ~allow
            stat = event_metrics(y[train], reject[train])
            f1 = 2*stat['correct_signals']/(2*stat['correct_signals']+stat['false_signals']+stat['missed_events']) if stat['correct_signals'] else 0
            spec = dict(underlying=u, family=family, field=field, threshold=threshold, allow_operator=operator,
                        calibration_f1=f1, **stat)
            named_trials.append(spec)
            if family not in best or (f1, -stat['false_signals']) > best[family][0]:
                best[family] = ((f1, -stat['false_signals']), spec, reject)
        for family, (_, spec, reject) in best.items():
            entry = event_metrics(~y[test], ~reject[test])
            named.append(dict(**{k: spec[k] for k in ('underlying', 'family', 'field', 'threshold', 'allow_operator', 'calibration_f1')},
                              **event_metrics(y[test], reject[test]), entry_precision=entry['precision'], entry_recall=entry['recall']))
    save_records('allocation_entry_filter_calibration.csv.gz', trials)
    save_records('allocation_entry_filter_evaluation.csv', evaluations)
    save_records('allocation_entry_filter_predictions.csv.gz', predictions)
    save_records('allocation_named_entry_filter_calibration.csv', named_trials)
    save_records('allocation_named_entry_filter_evaluation.csv', named)
    (OUT/'allocation_entry_filter_programs.json').write_text(json.dumps(programs, indent=2, allow_nan=False)+'\n')
    (OUT/'allocation_entry_filter_text.txt').write_text('\n\n'.join(texts).rstrip()+'\n')
    (OUT/'allocation_entry_filter_summary.json').write_text(json.dumps(dict(evaluation=evaluations, named_filters=named,
        note='Targets separately measure no same-strike pair, no both-right entry and genuinely no new shorts while prior exposure remains active. Named range filters use genuinely no new short. Suppression precision/recall measure missing entries; entry metrics invert decisions. Initial no-trade eligibility remains unidentified. Greeks/IV-to-intraday-RV are model proxies.'), indent=2)+'\n')


if __name__ == '__main__':
    main()
