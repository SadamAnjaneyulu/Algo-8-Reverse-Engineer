"""Aggregate the combined inverse search and audit its saved artifacts."""
import csv
import gzip
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'outputs'


def read_json(name):
    return json.loads((OUT / name).read_text())


def read_csv(name):
    opener = gzip.open if name.endswith('.gz') else open
    with opener(OUT / name, 'rt', newline='') as stream:
        yield from csv.DictReader(stream)


def main():
    names = ['action', 'flow_action', 'exit', 'hedge', 'sizing', 'joint', 'liquidity']
    studies = {name: read_json(f'combo_{name}_summary.json') for name in names}
    counts = {name: value.get('calibration_comparisons', value.get('calibration_model_settings'))
              for name, value in studies.items()}
    counts['active_book_baselines'] = studies['joint']['stronger_baselines']['calibration_comparisons']
    audits = {}
    for name in ('action', 'flow_action'):
        count = sum(1 for _ in read_csv(f'combo_{name}_search_scores.csv.gz'))
        assert count == counts[name], (name, count, counts[name])
        audits[name + '_score_rows'] = count
    histograms = list(read_csv('combo_exit_search_histograms.csv'))
    assert sum(int(r['programs']) for r in histograms) == counts['exit']
    assert all(sum(json.loads(r['calibration_match_histogram'])) == int(r['programs']) for r in histograms)
    audits['exit_histogram_contexts'] = len(histograms)
    for name in ('action', 'flow_action', 'joint'):
        suffix = '.csv.gz' if name != 'joint' else '.csv'
        count = 0
        for row in read_csv(f'combo_{name}_predictions' + suffix):
            assert row['expiry_date'] > '2026-08-31', (name, row)
            count += 1
        audits[name + '_later_prediction_rows'] = count
    count = 0
    for row in read_csv('combo_option_flow_features.csv.gz'):
        cutoff = datetime.fromisoformat(row['date'] + 'T' + row['clock'] + ':00+05:30')
        assert datetime.fromisoformat(row['flow_bar_start_ist']) == cutoff - timedelta(minutes=1)
        if row['flow_reference_pair_minute_ist']:
            assert datetime.fromisoformat(row['flow_reference_pair_minute_ist']) + timedelta(minutes=1) <= cutoff
        count += 1
    audits['causal_flow_context_rows'] = count
    for name in ('full_history', 'full_history_flow'):
        models = read_json(f'combo_{name}_programs.json')['models']
        assert all(m['historical_exact_rate'] == 1 for m in models.values())
        assert all(m['fit_kind'] == 'all_observed_resubstitution' for m in models.values())
        audits[name] = {key: {field: m[field] for field in ('rows', 'leaves', 'historical_exact_rate')}
                        for key, m in models.items()}
    economic = read_json('combo_economic_summary.json')
    audits['economic_intervals_include_zero'] = all(r['lower'] <= 0 <= r['upper'] for r in economic['comparisons'])
    assert audits['economic_intervals_include_zero']
    artifacts = sorted(OUT.glob('combo_*'))
    manifest = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in artifacts if p.name != 'combo_overview.json'}
    summary = dict(
        calibration_parameter_context_comparisons=counts,
        total_new_comparisons=sum(counts.values()),
        previous_separate_study_comparisons=71720,
        counts_note='Repeated rule/parameter/context evaluations, not distinct independent hypotheses. Sizing counts 48 settings; its 192 cycle-fold fits are not added again. Full-history fits and descriptive change points are excluded.',
        split=dict(calibration_expiry_through='2026-08-31', later_expiry_after='2026-08-31',
                   limitation='Later dates were already inspected in previous research; this is not an untouched holdout.'),
        audits=audits,
        conclusions=dict(extra_entry_trigger='Not recovered', exact_exit_controller='Not recovered',
                         exact_hedge_selector='Partial matches only', sizing='Partial later quantity matches',
                         eligibility='No-trade eligibility unidentified; schedule changes descriptive',
                         economic_alpha='Not established by the conditional fixed-basket diagnostic'),
        artifact_manifest=manifest)
    (OUT / 'combo_overview.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(total_new_comparisons=summary['total_new_comparisons'], counts=counts,
                          audited_artifacts=len(manifest), causal_flow_rows=count), indent=2))


if __name__ == '__main__':
    main()
