"""Consistency tests over the produced validation tables (skipped when the tables have not been generated)."""
import json, os
import pandas as pd, pytest
T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports', 'tables')
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(T, 'report_numbers.json')), reason='run the pipeline first')


def J(n): return json.load(open(os.path.join(T, n)))


def test_manifest_matches_files():
    inv = J('inventory.json')
    for i in ('nifty', 'sensex'):
        m = inv['manifest_vs_files'][i]; assert not m['sessions_in_checkpoint_without_file'] and not m['files_not_in_checkpoint'] and not m['spot_missing_files'] and not m['futures_missing_files']
        assert m['spot_files'] == m['option_session_files'] == m['futures_files']
    assert inv['checkpoint_rows'] == 103776 and inv['checkpoint_duplicate_rows'] == 0 and inv['commit'] == 'eb4097308d47ccc75078ab73ba76d33bb1c7030b'


def test_every_expected_expiry_is_classified_exactly_once():
    for i in ('nifty', 'sensex'):
        t = pd.read_csv(os.path.join(T, f'{i}_expiry_coverage.csv')); assert t.expected_expiry.is_unique and set(t.status) <= {'Complete', 'Partial', 'Missing', 'Unverified'}
        s = J('coverage_summary.json')[i.upper()]; assert s['complete'] + s['partial'] + s['missing'] + s['unverified'] == s['expected'] == len(t)


def test_raw_equals_normalized_everywhere():
    q = J('quality_summary.json')
    for i in ('nifty', 'sensex'):
        r = q[i]['raw_vs_norm']; assert r['raw_only'] == r['norm_only'] == r['value_mismatch'] == 0 and r['raw_rows'] == r['norm_rows']
        u = q[i]['underlying']; assert u['raw_only'] == u['norm_only'] == u['raw_mismatch_rows'] == 0


def test_no_duplicates_no_invalid_ohlc_and_symmetric_plan():
    o = pd.DataFrame(json.load(open(os.path.join(T, 'option_session_scan.json'))))
    for c in ('dup_keys', 'dup_rows_full', 'ohlc_nan', 'ohlc_nonpositive', 'ohlc_high_lt_open_or_close', 'ohlc_low_gt_open_or_close', 'ohlc_high_lt_low', 'ohlc_off_tick', 'expiry_mismatch_rows', 'strike_off_grid_rows', 'rows_outside_plan', 'ts_unparseable', 'date_mismatch_rows'): assert o[c].sum() == 0, c
    assert (o.plan_strikes == 91).all() and set(o.right_values) == {'CE,PE'}
    assert ((o['index'] == 'nifty') == (o.plan_step_values == '50')).all() and ((o['index'] == 'sensex') == (o.plan_step_values == '100')).all()


def test_known_defects_are_still_detected():
    o = pd.DataFrame(json.load(open(os.path.join(T, 'option_session_scan.json')))); assert int(o.volume_neg.sum()) == 13
    assert int(((o['index'] == 'nifty') & (o.weekend_rows > 0)).sum()) == 1                                       # Muhurat Sunday session
    q = J('quality_summary.json'); assert q['sensex']['oi']['share_rows_oi_zero'] == 1.0
    t = pd.read_csv(os.path.join(T, 'nifty_expiry_coverage.csv')); assert set(t[t.status == 'Partial'].expected_expiry) == {'2024-06-27', '2026-11-09'}
    s = pd.read_csv(os.path.join(T, 'sensex_expiry_coverage.csv')); assert {'2024-11-22', '2025-02-25', '2025-04-01', '2025-08-26', '2026-03-12'} <= set(s[s.status == 'Missing'].expected_expiry)


def test_legacy_crosscheck_has_no_mismatch():
    s = J('legacy_crosscheck_summary.json'); assert s['contract_days_with_any_mismatch'] == 0 and s['index_days_with_mismatch'] == 0 and s['minutes_both'] > 1_000_000


def test_split_never_crosses_an_expiry():
    n = J('report_numbers.json')
    for i in ('nifty', 'sensex'): assert n[i]['split']['crossing_expiry_pairs'] == 0 and n[i]['split']['is_last_d0'] < n[i]['split']['oos_first_d0']
