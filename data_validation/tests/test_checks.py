"""Every check must stay silent on a clean synthetic session and fire on the matching deliberate corruption."""
import os, sys
from datetime import date, datetime, timedelta
import numpy as np, pandas as pd, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from validation import checks as K
from validation import calendar_evidence as CE

DAY = date(2024, 2, 8); EXP = date(2024, 2, 8); STEP = 50; CENTER = 22000
PLAN = {(CENTER + k * STEP, r) for k in range(-4, 5) for r in ('CE', 'PE')}


def clean():
    rows = []; t0 = datetime(2024, 2, 8, 9, 15)
    for s, r in sorted(PLAN):
        for m in range(375):
            p = round(100 + (m % 7) * 0.05 + abs(s - CENTER) / 100, 2)
            rows.append(dict(datetime=(t0 + timedelta(minutes=m)).strftime('%Y-%m-%d %H:%M:%S'), expiry_date='08-FEB-2024', strike=s, right=r, open=p, high=p + 0.05, low=p - 0.05, close=p, volume=75 * (m % 5), open_interest=1000 + m, stock_code='NIFTY', exchange_code='NFO'))
    return pd.DataFrame(rows)


def report(x, **kw): return K.session_report(x, kw.get('day', DAY), kw.get('expiry', EXP), kw.get('step', STEP), kw.get('plan', PLAN))


def test_clean_session_has_no_problems():
    assert K.problems(report(clean())) == []


def test_duplicate_timestamps_detected():
    x = clean(); x = pd.concat([x, x.iloc[[10, 20]]], ignore_index=True)
    assert 'duplicate_keys' in K.problems(report(x)) and report(x)['duplicate_full_rows'] == 2


def test_invalid_ohlc_detected():
    x = clean(); x.loc[5, 'high'] = x.loc[5, 'low'] - 1; x.loc[6, 'low'] = x.loc[6, 'high'] + 1; x.loc[7, 'open'] = 0; x.loc[8, 'close'] = -3
    p = K.problems(report(x)); assert {'high_lt_open_or_close', 'low_gt_open_or_close', 'nonpositive'} <= set(p)


def test_wrong_expiry_identifier_detected():
    x = clean(); x.loc[x.index[:100], 'expiry_date'] = '15-FEB-2024'; assert 'expiry_mismatch' in K.problems(report(x)) and report(x)['expiry_mismatch'] == 100
    y = clean(); y.loc[0, 'expiry_date'] = 'garbage'; assert report(y)['expiry_unparseable'] == 1


def test_missing_ce_or_pe_detected():
    x = clean(); assert 'missing_option_type' in K.problems(report(x[x.right == 'CE'])); assert 'missing_option_type' in K.problems(report(x[x.right == 'PE']))
    y = clean(); y = y[~((y.right == 'PE') & (y.strike == CENTER))]; r = report(y); assert r['planned_without_rows'] == 1


def test_incorrect_d1_date_detected():
    td = [date(2024, 2, 5), date(2024, 2, 6), date(2024, 2, 7), date(2024, 2, 8)]
    assert K.d1_mapping(EXP, date(2024, 2, 7), td) and not K.d1_mapping(EXP, date(2024, 2, 6), td) and not K.d1_mapping(EXP, date(2024, 2, 4), td)
    td2 = [date(2026, 11, 6), date(2026, 11, 9)]; assert not K.d1_mapping(date(2026, 11, 9), date(2026, 11, 8), td2)          # a Sunday special session is not the previous trading day


def test_incorrect_timezone_and_clock_detected():
    x = clean(); x['datetime'] = x['datetime'].str.replace(' ', 'T') + '+05:30'; assert 'has_timezone_suffix' in K.problems(report(x))
    y = clean(); ts = pd.to_datetime(y.datetime) - pd.Timedelta(hours=5, minutes=30); y['datetime'] = ts.dt.strftime('%Y-%m-%d %H:%M:%S'); p = K.problems(report(y)); assert 'before_0915' in p                 # UTC clock written as if IST
    z = clean(); z['datetime'] = (pd.to_datetime(z.datetime) + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d %H:%M:%S'); assert 'other_date' in K.problems(report(z))


def test_weekend_and_off_session_timestamps_detected():
    x = clean(); sat = x.copy(); sat['datetime'] = (pd.to_datetime(sat.datetime) + pd.Timedelta(days=2)).dt.strftime('%Y-%m-%d %H:%M:%S'); assert 'weekend' in K.problems(report(sat, day=date(2024, 2, 10)))
    late = clean(); late.loc[0, 'datetime'] = '2024-02-08 16:45:00'; assert 'after_expected_last' in K.problems(report(late))
    sec = clean(); sec.loc[0, 'datetime'] = '2024-02-08 09:15:30'; assert 'nonzero_seconds' in K.problems(report(sec))


def test_out_of_order_detected():
    x = clean(); a, b = x.index[3], x.index[4]; x.loc[[a, b], 'datetime'] = x.loc[[b, a], 'datetime'].values; assert 'out_of_order_or_repeated_within_contract' in K.problems(report(x))


def test_incorrect_strike_interval_detected():
    x = clean(); x.loc[x.strike == CENTER + 50, 'strike'] = CENTER + 55; assert 'off_grid_rows' in K.problems(report(x))
    bad_plan = {(CENTER + k * 100, 'CE') for k in range(-3, 4)} | {(CENTER + k * 50, 'PE') for k in range(-3, 4)}; assert K.plan_step_flags({(s, r) for s, r in PLAN}, 100)['plan_steps_ok'] is False
    uneven = sorted({s for s, _ in PLAN}); uneven = {(s, 'CE') for s in uneven if s != CENTER}; assert K.plan_step_flags(uneven, 50)['plan_steps_ok'] is False


def test_strike_outside_plan_detected():
    x = clean(); extra = x[x.strike == CENTER].copy(); extra['strike'] = CENTER + 1000; assert 'rows_outside_plan' in K.problems(report(pd.concat([x, extra])))


def test_negative_and_missing_volume_open_interest_detected():
    x = clean(); x.loc[0, 'volume'] = -5; x.loc[1, 'open_interest'] = -1; x.loc[2, 'volume'] = np.nan; r = report(x); assert r['volume_negative'] == 1 and r['open_interest_negative'] == 1 and r['volume_nan'] == 1


def test_missing_candles_and_coverage():
    x = clean(); x = x[~((x.strike == CENTER) & (x.right == 'CE') & x.datetime.str.contains(' 11:'))]; c = K.candle_coverage(x[(x.strike == CENTER) & (x.right == 'CE')], DAY); assert c['missing'] == 60 and c['coverage'] == pytest.approx(315 / 375)
    assert K.candle_coverage(clean()[lambda d: (d.strike == CENTER) & (d.right == 'PE')], DAY)['missing'] == 0
    assert K.candle_coverage(clean().iloc[:10], date(2026, 8, 4))['grid'] == 385                                                       # closing-auction era grid


def test_underlying_alignment_and_missing_underlying_session():
    opt = {'09:15', '09:16', '09:17'}; assert K.underlying_alignment(opt, {'09:15', '09:16'})['option_minutes_without_spot'] == 1
    assert K.underlying_alignment(opt, set())['option_minutes_without_spot'] == 3


def test_raw_vs_normalized_detects_changed_dropped_and_added_rows():
    x = clean(); raw = x.to_dict('records'); assert K.raw_vs_norm(raw, x) == dict(raw_only=0, norm_only=0, value_mismatch=0)
    y = x.copy(); y.loc[3, 'close'] += 0.05; assert K.raw_vs_norm(raw, y)['value_mismatch'] == 1
    z = x.iloc[1:]; assert K.raw_vs_norm(raw, z)['raw_only'] == 1
    w = pd.concat([x, x.iloc[[0]].assign(datetime='2024-02-08 15:35:00')]); assert K.raw_vs_norm(raw, w)['norm_only'] == 1


def test_manifest_consistency():
    planned = [('2024-02-08', '2024-02-07'), ('2024-02-08', '2024-02-08')]; assert K.manifest_flags(planned, planned) == dict(planned_without_file=[], file_not_planned=[])
    r = K.manifest_flags(planned, [planned[0], ('2024-02-15', '2024-02-14')]); assert r['planned_without_file'] == [planned[1]] and r['file_not_planned'] == [('2024-02-15', '2024-02-14')]


def test_atm_centre_uses_d2_close_not_d1():
    assert K.atm_centre(21976.3, 50) == 22000 and K.atm_centre(21974.9, 50) == 21950 and K.atm_centre(73451, 100) == 73500


def test_independent_calendar_rules():
    for und, d, wd in (('NIFTY', date(2024, 2, 5), 3), ('NIFTY', date(2025, 9, 1), 1), ('SENSEX', date(2024, 6, 3), 4), ('SENSEX', date(2025, 9, 1), 3)): assert CE.rule_weekday(und, d)[0] == wd
    e = {r['week_monday']: r for r in CE.expected_expiries('NIFTY')}
    assert e['2026-11-09']['expected_expiry'] == '2026-11-09' and e['2026-11-09']['holiday_shifted'] and e['2026-11-09']['d1'] == '2026-11-06'        # Tuesday 10 Nov is not a trading day; D-1 is Friday, not the Sunday special session
    assert e['2026-08-31']['expected_expiry'] == '2026-09-01'
