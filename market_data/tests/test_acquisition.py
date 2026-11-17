import csv, json, os, sys, glob, sqlite3
from datetime import date
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acquisition import config as C, planner as P, runner as RUN, normalize as N, qc as Q, legacy as L, calendar_rules as CR
from acquisition.client import BreezeClient, AuthError, RejectedError, ResponseError
from acquisition.store import Store, write_once
from fake_breeze import FakeBreeze, SECRET_KEY, SECRET_SESSION, SECRET_TOKEN

START, END = date(2024, 3, 4), date(2024, 3, 22)          # three weeks, two Thursday expiries (7th, 14th, 21st -> three)


@pytest.fixture(autouse=True)
def small_band(monkeypatch):
    monkeypatch.setattr(C, 'BAND_CORE_STEPS', 2); monkeypatch.setattr(C, 'BAND_WING_STEPS', 4); monkeypatch.setattr(P, 'strikes_for', lambda c, s, core=2, wing=4: [(c + k * s, 1 if abs(k) <= core else 2, abs(k)) for k in range(-wing, wing + 1)])


def client(fake): return BreezeClient(transport=fake, api_key=SECRET_KEY, session=SECRET_SESSION, sleep=lambda s: None, min_interval=0)


def build(tmp, fake, max_tier=2, **kw):
    st = Store(str(tmp / 'store')); c = client(fake)
    P.plan_index(st, 'NIFTY', START, END); RUN.run(st, c, ['index'], today='2024-03-30')
    for _ in range(4):
        if not P.plan_expiry_probes(st, 'NIFTY', START, END): break
        RUN.run(st, c, ['option'], max_tier=0, today='2024-03-30')
    P.plan_options(st, 'NIFTY', max_tier, START, END); stats = RUN.run(st, c, ['option'], max_tier=max_tier, today='2024-03-30', **kw)
    return st, c, stats


def test_end_to_end_index_expiries_options(tmp_path):
    fake = FakeBreeze(holidays=['2024-03-07'])                       # the Thursday expiry is a holiday: expiry moves to Wednesday the 6th
    st, c, stats = build(tmp_path, fake)
    td = P.trading_days(st, 'NIFTY'); assert date(2024, 3, 7) not in td and len(td) == 19
    assert st.day_status(dict(kind='index', und='NIFTY', expiry=None, strike=None, right=None, trade_day='2024-03-07')) == 'EMPTY'        # holiday recorded, not DONE
    exps = P.confirmed_expiries(st, 'NIFTY'); assert exps == [date(2024, 3, 6), date(2024, 3, 14), date(2024, 3, 21)]
    assert stats['failed'] == 0
    keys = [r[0] for r in st.db.execute("SELECT kind||und||expiry||strike||right||trade_day FROM contract_days WHERE kind='option'")]; assert len(keys) == len(set(keys))
    assert all(os.path.getsize(f) > 0 for f in glob.glob(str(tmp_path / 'store' / 'normalized' / 'option' / '**' / '*.csv'), recursive=True))
    assert not any(os.stat(f).st_mode & 0o222 for f in glob.glob(str(tmp_path / 'store' / 'raw' / '**' / '*.json'), recursive=True))          # raw files are read-only


def test_one_request_covers_both_sessions_and_stays_under_the_candle_cap(tmp_path):
    fake = FakeBreeze(); st, c, _ = build(tmp_path, fake)
    spans = {(q['from_date'][:10], q['to_date'][:10]) for q in fake.calls if q['product_type'] == 'options' and q.get('strike_price')}
    assert ('2024-03-13', '2024-03-14') in spans
    with pytest.raises(ValueError): N.check_span_size(3)


def test_resume_after_interruption_never_repeats_a_request(tmp_path):
    fake = FakeBreeze(); st = Store(str(tmp_path / 'store')); c = client(fake)
    P.plan_index(st, 'NIFTY', START, END); RUN.run(st, c, ['index'], today='2024-03-30'); P.plan_expiry_probes(st, 'NIFTY', START, END); RUN.run(st, c, ['option'], max_tier=0, today='2024-03-30')
    P.plan_options(st, 'NIFTY', 2, START, END); n_tasks = len(st.pending(['option']))
    s1 = RUN.run(st, c, ['option'], max_requests=17, today='2024-03-30'); assert s1['requests'] == 17
    before = len(fake.calls); st2 = Store(str(tmp_path / 'store'))                                         # a new process opens the same store
    s2 = RUN.run(st2, client(fake), ['option'], today='2024-03-30'); assert s2['requests'] == n_tasks - 17 and len(fake.calls) - before == n_tasks - 17
    assert len({json.dumps(q, sort_keys=True) for q in fake.calls}) == len(fake.calls)                      # no request was ever sent twice
    assert RUN.run(st2, client(fake), ['option'], today='2024-03-30')['requests'] == 0


def test_raw_present_but_manifest_lost_is_reused_without_a_request(tmp_path):
    fake = FakeBreeze(); st, c, _ = build(tmp_path, fake, 1); n = len(fake.calls)
    st.db.execute("UPDATE tasks SET status='PENDING' WHERE kind='option'"); st.db.execute("DELETE FROM contract_days WHERE kind='option'"); st.commit()
    s = RUN.run(st, c, ['option'], today='2024-03-30'); assert s['requests'] == 0 and s['reused_raw'] > 0 and len(fake.calls) == n
    assert st.db.execute("SELECT COUNT(*) FROM contract_days WHERE kind='option' AND status='DONE'").fetchone()[0] > 0


def test_daily_cap_stops_the_run_and_resumes_next_day(tmp_path):
    fake = FakeBreeze(); st = Store(str(tmp_path / 'store')); c = client(fake); P.plan_index(st, 'NIFTY', START, END)
    s = RUN.run(st, c, ['index'], daily_cap=5, today='2024-03-30'); assert s['requests'] == 5 and st.requests_today('2024-03-30') == 5
    assert RUN.run(st, c, ['index'], daily_cap=5, today='2024-03-30')['requests'] == 0
    assert RUN.run(st, c, ['index'], daily_cap=5, today='2024-03-31')['requests'] == 5


def test_auth_failure_stops_the_run_and_no_secret_reaches_disk(tmp_path):
    fake = FakeBreeze(); st = Store(str(tmp_path / 'store')); P.plan_index(st, 'NIFTY', START, END)
    with pytest.raises(RUN.StopRun): RUN.run(st, BreezeClient(transport=fake, api_key='WRONG', session=SECRET_SESSION, sleep=lambda s: None), ['index'], today='2024-03-30')
    assert st.counts().get('DONE', 0) == 0 and st.counts()['PENDING'] > 0
    c = client(fake); RUN.run(st, c, ['index'], today='2024-03-30')
    for dirpath, _, files in os.walk(tmp_path):
        for f in files:
            if f.endswith('.sqlite') or f.endswith('.json') or f.endswith('.csv'):
                b = open(os.path.join(dirpath, f), 'rb').read()
                assert SECRET_KEY.encode() not in b and SECRET_SESSION.encode() not in b and SECRET_TOKEN.encode() not in b
    assert 'SECRET' not in repr(c)


def test_http_401_and_html_rejection_stop_the_run():
    def t401(m, u, h, b): return (200, json.dumps({'Status': 200, 'Success': {'session_token': 't'}}).encode()) if 'customer' in u else (401, b'')
    with pytest.raises(AuthError): BreezeClient(transport=t401, api_key='k', session='s', sleep=lambda s: None).fetch({'a': 1})
    def thtml(m, u, h, b): return (200, json.dumps({'Status': 200, 'Success': {'session_token': 't'}}).encode()) if 'customer' in u else (200, b'<html>The requested URL was rejected. Request Rejected support id 123</html>')
    with pytest.raises(RejectedError): BreezeClient(transport=thtml, api_key='k', session='s', sleep=lambda s: None).fetch({'a': 1})


def test_transient_errors_are_retried_then_marked_retryable_and_five_in_a_row_stop(tmp_path):
    fake = FakeBreeze(fail_after=2); st = Store(str(tmp_path / 'store')); P.plan_index(st, 'NIFTY', START, END)
    with pytest.raises(RUN.StopRun): RUN.run(st, client(fake), ['index'], today='2024-03-30')
    assert st.counts().get('FAILED_RETRYABLE', 0) >= 1 and st.counts().get('DONE', 0) == 2


def test_wrong_instrument_in_the_response_is_rejected_and_raw_is_kept(tmp_path):
    fake = FakeBreeze(bad_identity=True); st = Store(str(tmp_path / 'store')); P.plan_index(st, 'NIFTY', START, START)
    RUN.run(st, client(fake), ['index'], today='2024-03-30'); assert st.counts() == {'FAILED': 6}
    assert glob.glob(str(tmp_path / 'store' / 'raw' / '**' / '*.json'), recursive=True) and not glob.glob(str(tmp_path / 'store' / 'normalized' / '**' / '*.csv'), recursive=True)


def test_unlisted_contract_is_empty_not_zero_and_blank_open_interest_stays_blank(tmp_path):
    fake = FakeBreeze(unlisted=lambda k, r: r == 'PE' and k % 100 == 0, no_oi=True); st, c, _ = build(tmp_path, fake, 1)
    assert st.db.execute("SELECT COUNT(*) FROM contract_days WHERE status='EMPTY' AND kind='option'").fetchone()[0] > 0
    f = glob.glob(str(tmp_path / 'store' / 'normalized' / 'option' / '**' / '*CE' / '*.csv'), recursive=True)[0]
    rows = list(csv.DictReader(open(f))); assert rows[0]['open_interest'] == '' and rows[0]['volume'] != ''


def test_write_once_refuses_to_overwrite(tmp_path):
    p = str(tmp_path / 'a' / 'x.json'); assert write_once(p, b'1') and not write_once(p, b'1')
    with pytest.raises(FileExistsError): write_once(p, b'2')


def test_rate_limiter_spaces_requests():
    t = [0.0]; sleeps = []
    def sl(s): sleeps.append(s); t[0] += s
    fake = FakeBreeze(); c = BreezeClient(transport=fake, api_key=SECRET_KEY, session=SECRET_SESSION, sleep=sl, clock=lambda: t[0], min_interval=1.25)
    for _ in range(3): c.fetch(N.request_params('index', 'NIFTY', date(2024, 3, 4), date(2024, 3, 4)))
    assert sleeps[0] == pytest.approx(1.25) and sleeps[1] == pytest.approx(1.25) and c.calls == 3


def test_no_unrequested_day_is_accepted(tmp_path):
    fake = FakeBreeze(); _, body = fake('GET', 'https://breezeapi.icicidirect.com/api/v2/historicalcharts?' + __import__('urllib.parse').parse.urlencode(N.request_params('index', 'NIFTY', date(2024, 3, 5), date(2024, 3, 6))), {'X-SessionToken': SECRET_TOKEN, 'apikey': SECRET_KEY}, None)
    rows = N.parse_rows('index', json.loads(body), 'NIFTY', date(2024, 3, 5), date(2024, 3, 6)); assert sorted(rows) == [date(2024, 3, 5), date(2024, 3, 6)]
    assert N.parse_rows('index', json.loads(body), 'NIFTY', date(2024, 3, 5), date(2024, 3, 5)).keys() == {date(2024, 3, 5)}      # bars outside the requested span are not retained


def test_legacy_import_registers_days_and_prevents_re_requests(tmp_path):
    br = tmp_path / 'br'; b = br / 'data' / 'breeze'
    for sub in ('raw/options/NIFTY/2024-03-14/22000CE', 'normalized/options/NIFTY/2024-03-14/22000CE', 'metadata/options/NIFTY/2024-03-14/22000CE'): (b / sub).mkdir(parents=True)
    raw = b'{"request":{},"response":{"Status":200,"Success":[]}}\n'; open(b / 'raw/options/NIFTY/2024-03-14/22000CE/2024-03-14.aaa.json', 'wb').write(raw)
    csvt = 'timestamp_ist,underlying,expiry_date,strike,option_type,open,high,low,close,volume,open_interest\n2024-03-14T09:15:00+05:30,NIFTY,2024-03-14,22000,CE,10,11,9,10.5,75,100\n'.encode(); open(b / 'normalized/options/NIFTY/2024-03-14/22000CE/2024-03-14.h.csv', 'wb').write(csvt)
    from acquisition.store import sha256_bytes
    json.dump(dict(contract=dict(expiry_date='2024-03-14', option_type='CE', strike=22000, trade_date='2024-03-14', underlying='NIFTY'), status='validated_observed_option_bars', raw_path='raw/options/NIFTY/2024-03-14/22000CE/2024-03-14.aaa.json',
                   normalized_path='normalized/options/NIFTY/2024-03-14/22000CE/2024-03-14.h.csv', normalized_sha256=sha256_bytes(csvt)), open(b / 'metadata/options/NIFTY/2024-03-14/22000CE/2024-03-14.h.json', 'w'))
    st = Store(str(tmp_path / 'store')); assert L.import_legacy(st, str(br)) == 1
    assert st.day_status(dict(kind='option', und='NIFTY', expiry='2024-03-14', strike=22000, right='CE', trade_day='2024-03-14')) == 'DONE'
    row = list(csv.DictReader(open(st.path('normalized', 'option', 'NIFTY', '2024-03-14', '22000CE', '2024-03-14.csv'))))[0]; assert row['source_id'].startswith('legacy:')


def test_qc_report_runs_and_labels_splits(tmp_path):
    fake = FakeBreeze(); st, c, _ = build(tmp_path, fake, 2); R = Q.report(st, 'NIFTY', str(tmp_path / 'qc'))
    assert R['options']['duplicate_keys'] == 0 and R['options']['ohlc_inconsistent'] == 0 and R['options']['contract_days_complete_grid'] == R['options']['contract_days']
    assert CR.split_of(date(2024, 3, 14)) == 'IN_SAMPLE' and CR.split_of(date(2026, 1, 5)) == 'OUT_OF_SAMPLE' and CR.split_of(date(2023, 1, 1)) == 'OUTSIDE_WINDOW'


def test_estimate_is_consistent_with_the_documented_cap():
    e = P.estimate(); assert e['option_tier1_requests'] == e['nominal_weekly_expiries'] * 82 and e['per_expiry_contracts'] == dict(tier1=82, tier2=100)
