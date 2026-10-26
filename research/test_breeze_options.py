"""Offline checks for expired-option identity, sparse coverage and safe publication."""
import copy
import csv
import io
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import fetch_breeze_options as opts

TARGET=opts.Target('NIFTY','2026-07-07',24350,'CE','2026-07-06')


def response(target=TARGET, count=None):
    n=count if count is not None else (385 if date.fromisoformat(target.trade_date)>=opts.base.CAS_START else 375)
    start=datetime.fromisoformat(target.trade_date+'T09:15:00')
    exchange,stock=opts.MAPPINGS[target.underlying]
    return dict(Status=200,Success=[dict(datetime=(start+timedelta(minutes=i)).isoformat(' '),
        stock_code=stock,exchange_code=exchange,expiry_date=datetime.fromisoformat(target.expiry_date).strftime('%d-%b-%Y').upper(),
        right='Call' if target.option_type=='CE' else 'Put',strike_price=float(target.strike),
        product_type='Options',open=100,high=102,low=99,close=101,volume=1000,open_interest=5000) for i in range(n)])


class FakeClient:
    def __init__(self,payload=None):
        self.payload=payload if payload is not None else response()
        self.calls=0

    def fetch(self,params):
        self.calls+=1
        return self.payload


class OptionChecks(unittest.TestCase):
    def test_parameters_name_exact_expired_contract_and_fit_1000_interval_cap(self):
        p=opts.parameters(TARGET)
        self.assertEqual((p['exch_code'],p['product_type'],p['right'],p['strike_price']),('NFO','options','call','24350'))
        self.assertEqual(p['expiry_date'],'2026-07-07T07:00:00.000Z')
        self.assertLess((datetime.fromisoformat(p['to_date'])-datetime.fromisoformat(p['from_date'])).total_seconds()/60,1000)

    def test_both_exchange_smoke_contracts_are_actual_traded_contracts(self):
        fills=opts.load_fills()
        targets=opts.targets_for('sample','both',True)
        self.assertEqual(len(targets),4)
        self.assertTrue(all(t in fills for t in targets))

    def test_pre_cas_derivative_grid(self):
        bars=opts.normalize(response(),TARGET,opts.PROFILE)
        c=opts.coverage(bars,TARGET)
        self.assertEqual(c['observed_bars'],375)
        self.assertTrue(c['full_minute_grid'])

    def test_post_cas_options_keep_trading_during_cash_transition(self):
        t=opts.Target('SENSEX','2026-10-08',72600,'PE','2026-10-07')
        bars=opts.normalize(response(t),t,opts.PROFILE)
        self.assertEqual(len(bars),385)
        self.assertTrue(any(b['timestamp_ist'][11:16]=='15:17' for b in bars))
        self.assertEqual(bars[-1]['timestamp_ist'][11:16],'15:39')
        self.assertTrue(opts.coverage(bars,t)['full_minute_grid'])

    def test_missing_option_minutes_are_recorded_without_filling(self):
        r=response()
        del r['Success'][1:4]
        bars=opts.normalize(r,TARGET,opts.PROFILE)
        c=opts.coverage(bars,TARGET)
        self.assertEqual(len(bars),372)
        self.assertFalse(c['full_minute_grid'])
        self.assertEqual(len(c['missing_minutes_ist']),3)
        self.assertEqual(c['missing_minutes_ist'][0][11:16],'09:16')

    def test_all_contract_identity_fields_are_required(self):
        for key,value in [('exchange_code','NSE'),('stock_code','BSESEN'),('right','Put'),('strike_price',24400),('expiry_date','14-JUL-2026'),('product_type','Futures')]:
            with self.subTest(key=key):
                r=response()
                r['Success'][0][key]=value
                with self.assertRaises(opts.base.FetchError):
                    opts.normalize(r,TARGET,opts.PROFILE)

    def test_duplicate_and_malformed_prices_rejected(self):
        for field,value in [('high',98),('volume',-1),('open_interest',float('nan')),('close',float('inf')),('low',-1)]:
            with self.subTest(field=field):
                r=response()
                r['Success'][0][field]=value
                with self.assertRaises(opts.base.FetchError):
                    opts.normalize(r,TARGET,opts.PROFILE)
        r=response()
        r['Success'].append(copy.deepcopy(r['Success'][0]))
        with self.assertRaises(opts.base.FetchError):
            opts.normalize(r,TARGET,opts.PROFILE)

    def test_zero_price_is_preserved_but_flagged(self):
        r=response()
        r['Success'][0].update(open=0,low=0)
        bars=opts.normalize(r,TARGET,opts.PROFILE)
        self.assertEqual(opts.coverage(bars,TARGET)['zero_price_bars'],1)

    def test_explicit_end_label_and_utc_profile(self):
        r=response()
        for row in r['Success']:
            wall=datetime.fromisoformat(row['datetime'])
            row['datetime']=(wall-timedelta(hours=5,minutes=29)).isoformat(' ')
        profile=dict(opts.PROFILE,response_timezone='UTC',bar_label='end')
        bars=opts.normalize(r,TARGET,profile)
        self.assertEqual(len(bars),375)
        self.assertTrue(bars[0]['timestamp_ist'].endswith('09:15:00+05:30'))

    def test_fill_alignment_reports_matches_mismatches_and_gaps(self):
        bars=opts.normalize(response(count=2),TARGET,opts.PROFILE)
        start=datetime(2026,7,6,9,15,1,tzinfo=opts.base.IST)
        a=opts.fill_alignment(bars,TARGET,{TARGET:[(start,100),(start,110),(start+timedelta(minutes=5),100)]})
        self.assertEqual((a['fills_inside_ohlc_plus_one_tick'],a['fills_outside_ohlc_plus_one_tick'],a['fills_without_bar']),(1,1,1))

    def test_cache_resume_never_downloads_or_rewrites(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f)
            client=FakeClient()
            m=opts.fetch_day(client,root,TARGET,opts.PROFILE,{})
            before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(opts.fetch_day(opts.CacheOnly(),root,TARGET,opts.PROFILE,{}),m)
            self.assertEqual(before,{p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertEqual(client.calls,1)

    def test_empty_cache_has_no_validated_metadata(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f)
            with self.assertRaises(opts.base.FetchError):
                opts.fetch_day(FakeClient(dict(Status=200,Success=[])),root,TARGET,opts.PROFILE,{})
            self.assertEqual(len(list(root.rglob('*.json'))),1)
            self.assertFalse((root/'metadata').exists())

    def test_unknown_response_fields_never_persist(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f)
            r=response()
            r['Success'][0]['session_token']='test-only-placeholder'
            with self.assertRaises(opts.base.FetchError):
                opts.fetch_day(FakeClient(r),root,TARGET,opts.PROFILE,{})
            self.assertFalse(list(root.rglob('*')))

    def test_publisher_accepts_only_reproducible_data_and_preserves_sparse_flag(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f)
            data=root/'data/breeze'
            with patch.object(opts,'load_fills',return_value={}):
                m=opts.fetch_day(FakeClient(response(count=2)),data,TARGET,opts.PROFILE,{})
                self.assertFalse(m['minute_grid_price_coverage_complete'])
                self.assertEqual(len(opts.validated_files(root)),3)
                raw,normalized,meta=opts.paths(data,TARGET,opts.PROFILE)
                original=normalized.read_bytes()
                normalized.write_bytes(original+b'changed')
                with self.assertRaises(opts.base.FetchError):
                    opts.validated_files(root)
                normalized.write_bytes(original)
                m['coverage']['full_minute_grid']=True
                meta.write_bytes(opts.base.canonical(m))
                with self.assertRaises(opts.base.FetchError):
                    opts.validated_files(root)

    def test_publisher_rejects_extra_metadata_and_path_changes(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f)
            data=root/'data/breeze'
            with patch.object(opts,'load_fills',return_value={}):
                m=opts.fetch_day(FakeClient(),data,TARGET,opts.PROFILE,{})
                _,_,meta=opts.paths(data,TARGET,opts.PROFILE)
                for extra in [('api_key','test-only-placeholder'),('raw_path','../../outside')]:
                    changed=dict(m)
                    changed[extra[0]]=extra[1]
                    meta.write_bytes(opts.base.canonical(changed))
                    with self.assertRaises(opts.base.FetchError):
                        opts.validated_files(root)

    def test_default_plan_cannot_authenticate_or_request(self):
        with patch.object(opts.sys,'argv',['options','--smoke']), patch.object(opts.base,'BreezeHistory',side_effect=AssertionError('network forbidden')),patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(opts.main(),0)

    def test_bulk_cannot_authenticate_before_smoke_cache_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            argv=['options','--fetch','--scope','all','--output',folder]
            with patch.object(opts.sys,'argv',argv),patch.object(opts,'targets_for',return_value=[TARGET]),patch.object(opts,'load_fills',return_value={}),patch.object(opts.base,'BreezeHistory',side_effect=AssertionError('must not authenticate')),patch('sys.stdout',new_callable=io.StringIO):
                with self.assertRaises(opts.base.FetchError):
                    opts.main()

    def test_smoke_quality_gate_distinguishes_sparse_and_misaligned_samples(self):
        m=dict(minute_grid_price_coverage_complete=True,fill_alignment=dict(logged_fills=10,fills_inside_ohlc_plus_one_tick=8))
        self.assertTrue(opts.smoke_ready(m))
        m['fill_alignment']['fills_inside_ohlc_plus_one_tick']=7
        self.assertFalse(opts.smoke_ready(m))
        m['fill_alignment']['fills_inside_ohlc_plus_one_tick']=10
        m['minute_grid_price_coverage_complete']=False
        self.assertFalse(opts.smoke_ready(m))

    def test_failed_smoke_quality_is_reported_and_exits_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            class AuthenticatedFake(FakeClient):
                def authenticate(self):
                    pass
            argv=['options','--fetch','--smoke','--output',folder]
            with patch.object(opts.sys,'argv',argv),patch.object(opts,'targets_for',return_value=[TARGET]),patch.object(opts,'load_fills',return_value={}),patch.object(opts.base,'tls_context'),patch.object(opts.base,'BreezeHistory',return_value=AuthenticatedFake(response(count=2))),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(opts.main(),2)
            review=json.loads((Path(folder)/'diagnostics/options_download_review.json').read_text())
            self.assertFalse(review['smoke_checks_passed'])
            self.assertEqual(len(review['smoke_review_required']),1)

    def test_all_scope_covers_every_observed_contract_day_and_excludes_weekend(self):
        fills=opts.load_fills()
        plan=set(opts.targets_for('all','both',False))
        self.assertTrue(set(fills)<=plan)
        self.assertEqual(len(plan),3243)
        self.assertTrue(all(date.fromisoformat(t.trade_date).weekday()<5 for t in plan))


if __name__=='__main__':
    unittest.main()
