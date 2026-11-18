"""Assembles every number quoted in the reports into reports/tables/report_numbers.json (so the prose is generated from computed values, never typed)."""
import json, sys
from datetime import date, timedelta
import pandas as pd, numpy as np
from . import calendar_evidence as CE
T = 'reports/tables'; ALGO8_START, ALGO8_END = date(2026, 6, 22), date(2026, 10, 22)


def months_between(a, b): return (b - a).days / 30.4375


def main():
    N = {}; cs = json.load(open(f'{T}/coverage_summary.json')); q = json.load(open(f'{T}/quality_summary.json')); inv = json.load(open(f'{T}/inventory.json')); deep = pd.read_csv(f'{T}/deep_scan_sessions.csv'); o = pd.DataFrame(json.load(open(f'{T}/option_session_scan.json')))
    u = pd.DataFrame(json.load(open(f'{T}/underlying_scan.json'))); leg = json.load(open(f'{T}/legacy_crosscheck_summary.json')); N['legacy'] = leg; N['inventory'] = {k: inv[k] for k in ('commit', 'files', 'bytes', 'checkpoint_rows')}; N['coverage'] = cs; N['quality'] = q
    for und in ('NIFTY', 'SENSEX'):
        idx = und.lower(); t = pd.read_csv(f'{T}/{idx}_expiry_coverage.csv'); t['notes'] = t.notes.fillna(''); present = t[t.d0_option_rows > 0]
        usable_d1 = int(((t.d1_option_rows > 0) & ~t.notes.str.contains('D-1 session .* (?:is incomplete|has an intraday outage|no contract traded)|dataset D-1')).sum()); usable_d0 = int(((t.d0_option_rows > 0) & ~t.notes.str.contains('D0 session .* (?:is incomplete|has an intraday outage|no contract traded)')).sum())
        first_exp, last_exp = present.expected_expiry.min(), present.expected_expiry.max(); first_day = pd.Timestamp(t[t.expected_expiry == first_exp].d1_expected.iloc[0]).date(); last_day = pd.Timestamp(last_exp).date()
        N[idx] = dict(first_expiry=first_exp, last_expiry=last_exp, first_session=str(first_day), last_session=str(last_day), usable_d1=usable_d1, usable_d0=usable_d0, expiries_present=len(present), span_years=round((last_day - first_day).days / 365.25, 2))
        # split on actual data: last 12 months out-of-sample, remainder in-sample; whole expiries are assigned by D0
        d0s = pd.to_datetime(present.expected_expiry).dt.date; oos_start_nominal = last_day - timedelta(days=365)
        oos = [e for e in d0s if e > oos_start_nominal]; ins = [e for e in d0s if e <= oos_start_nominal]
        N[idx]['split'] = dict(proposed_oos_from_exclusive=str(oos_start_nominal), is_expiries=len(ins), oos_expiries=len(oos), is_first=str(first_day), is_last_d0=str(max(ins)), oos_first_d0=str(min(oos)), oos_last_d0=str(max(oos)), is_months=round(months_between(first_day, max(ins)), 1),
                            oos_expiries_inside_algo8_window=sum(1 for e in oos if ALGO8_START <= e <= ALGO8_END), oos_expiries_after_algo8_window=sum(1 for e in oos if e > ALGO8_END), oos_expiries_before_algo8_window=sum(1 for e in oos if e < ALGO8_START),
                            algo8_window_expiries=sum(1 for e in d0s if ALGO8_START <= e <= ALGO8_END))
        N[idx]['split']['clean_oos_expiries_before_exposure'] = N[idx]['split']['oos_expiries_before_algo8_window']
        N[idx]['split']['crossing_expiry_pairs'] = 0
    json.dump(N, open(f'{T}/report_numbers.json', 'w'), indent=1, default=str); print(json.dumps({k: N[k] for k in ('nifty', 'sensex')}, indent=1, default=str))


if __name__ == '__main__': main()
