"""Offline validation of the downloader; no live or fabricated market outcomes."""

import importlib.util
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import io

SPEC = importlib.util.spec_from_file_location("breeze_fetch", Path(__file__).with_name("fetch_breeze_indices.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
DAY = date(2026, 6, 23)


def response():
    return dict(Status=200, Success=[dict(datetime=(datetime(2026, 6, 23, 9, 15)+timedelta(minutes=i)).isoformat(" "),
                                         stock_code="NIFTY", exchange_code="NSE", open=100, high=102,
                                         low=99, close=101, volume=0) for i in range(375)])


class HistoryValidation(unittest.TestCase):
    def test_full_session(self):
        bars = module.normalize(response(), "NIFTY", DAY, "Asia/Kolkata", "start")
        self.assertEqual(len(bars), 375)
        self.assertTrue(bars[0]["timestamp_ist"].endswith("09:15:00+05:30"))

    def test_missing_and_duplicate_minutes_rejected(self):
        for payload in (dict(Status=200, Success=response()["Success"][:-1]),
                        dict(Status=200, Success=response()["Success"]+[response()["Success"][0]])):
            with self.assertRaises(module.FetchError):
                module.normalize(payload, "NIFTY", DAY, "Asia/Kolkata", "start")

    def test_missing_minutes_are_reported_exactly(self):
        payload = response()
        del payload["Success"][2:6]
        with self.assertRaises(module.MissingMinutesError) as caught:
            module.normalize(payload, "NIFTY", DAY, "Asia/Kolkata", "start")
        self.assertEqual([datetime.fromisoformat(t).strftime("%H:%M") for t in caught.exception.missing],
                         ["09:17", "09:18", "09:19", "09:20"])

    def test_bulk_continues_other_dates_but_reports_incomplete_exit_status(self):
        calls = []
        def fake_fetch(client, root, underlying, target, *args):
            calls.append((underlying, target))
            if target == date(2026, 6, 22):
                raise module.MissingMinutesError(["2026-06-22T09:17:00+05:30"])
            return {"regular_session_bars": 375, "interpretation": {"normalizer_version": 1}}
        with tempfile.TemporaryDirectory(prefix="algo8-continue-test-") as folder:
            argv = ["fetch", "--fetch", "--index", "NIFTY", "--start", "2026-06-22", "--end", "2026-06-23", "--continue-incomplete", "--output", folder]
            with patch.object(module.sys, "argv", argv), patch.object(module, "fetch_day", side_effect=fake_fetch), patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as caught:
                    module.main()
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(len(calls), 2)
            review = module.json.loads((Path(folder)/"diagnostics"/"download_review.json").read_text())
            self.assertEqual(review["status"], "incomplete")
            self.assertEqual(review["validated_index_days"], 1)
            self.assertEqual(len(review["incomplete_index_days"]), 1)

    def test_inspection_reads_incomplete_cache_without_network_or_writes(self):
        payload = response()
        del payload["Success"][2:6]
        class FakeClient:
            def fetch(self, params):
                return payload
        with tempfile.TemporaryDirectory(prefix="algo8-inspect-test-") as folder:
            root = Path(folder)
            with self.assertRaises(module.MissingMinutesError):
                module.fetch_day(FakeClient(), root, "NIFTY", DAY)
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            argv = ["fetch", "--inspect-cached", "--index", "NIFTY", "--start", "2026-06-23", "--end", "2026-06-23", "--output", folder]
            with patch.object(module.sys, "argv", argv), patch.object(module, "request_json", side_effect=AssertionError("unexpected network")), patch("sys.stdout", new_callable=io.StringIO) as out:
                module.main()
            report = module.json.loads(out.getvalue())
            self.assertEqual(report["status"], "incomplete")
            self.assertEqual(len(report["missing_minutes_ist"]), 4)
            self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_cas_optional_auction_holes_are_preserved_without_filling(self):
        day = date(2026, 10, 12)
        payload = response()
        payload["Success"] = [dict(r, datetime=r["datetime"].replace("2026-06-23", str(day))) for r in payload["Success"]
                              if r["datetime"][11:16] not in ("15:16", "15:17", "15:18", "15:19", "15:29")]
        bars = module.normalize(payload, "NIFTY", day, "Asia/Kolkata", "start")
        self.assertEqual(len(bars), 370)
        self.assertEqual(sum(r["session_phase"] == "continuous_cash" for r in bars), 360)
        self.assertNotIn("15:16", {r["timestamp_ist"][11:16] for r in bars})
        with self.assertRaises(module.MissingMinutesError):
            module.normalize(payload, "NIFTY", day, "Asia/Kolkata", "start", normalizer_version=1)

    def test_cas_continuous_gap_is_still_rejected(self):
        payload = response()
        day = date(2026, 10, 12)
        payload["Success"] = [dict(r, datetime=r["datetime"].replace("2026-06-23", str(day))) for r in payload["Success"] if r["datetime"][11:16] != "10:20"]
        with self.assertRaises(module.MissingMinutesError) as caught:
            module.normalize(payload, "NIFTY", day, "Asia/Kolkata", "start")
        self.assertEqual(caught.exception.missing, ["2026-10-12T10:20:00+05:30"])

    def test_cas_preserves_later_observations_and_labels_phase_boundaries(self):
        payload = response()
        day = date(2026, 10, 12)
        payload["Success"] = [dict(r, datetime=r["datetime"].replace("2026-06-23", str(day))) for r in payload["Success"]]
        last = payload["Success"][-1]
        payload["Success"].extend(dict(last, datetime=f"{day} 15:{minute}:00") for minute in range(30, 41))
        bars = module.normalize(payload, "NIFTY", day, "Asia/Kolkata", "start")
        self.assertEqual(len(bars), 385)
        phases = {r["timestamp_ist"][11:16]: r["session_phase"] for r in bars}
        self.assertEqual(phases["15:14"], "continuous_cash")
        self.assertEqual(phases["15:15"], "closing_transition")
        self.assertEqual(phases["15:20"], "auction_order_entry_or_random_close")
        self.assertEqual(phases["15:30"], "auction_matching")
        self.assertEqual(phases["15:35"], "post_auction_derivatives_still_open")
        self.assertNotIn("15:40", phases)

    def test_pre_cas_late_minutes_remain_required(self):
        payload = response()
        day = date(2026, 7, 31)
        payload["Success"] = [dict(r, datetime=r["datetime"].replace("2026-06-23", str(day))) for r in payload["Success"] if r["datetime"][11:16] != "15:17"]
        with self.assertRaises(module.MissingMinutesError):
            module.normalize(payload, "NIFTY", day, "Asia/Kolkata", "start")

    def test_legacy_complete_cas_profile_resumes_without_duplicate_outputs(self):
        day = date(2026, 8, 3)
        payload = response()
        payload["Success"] = [dict(r, datetime=r["datetime"].replace("2026-06-23", str(day))) for r in payload["Success"]]
        class Initial:
            def fetch(self, params):
                return payload
        class NoNetwork:
            def fetch(self, params):
                raise AssertionError("unexpected fetch")
        with tempfile.TemporaryDirectory(prefix="algo8-cas-legacy-") as folder:
            root = Path(folder)
            old = module.fetch_day(Initial(), root, "NIFTY", day, normalizer_version=1)
            result = module.fetch_day(NoNetwork(), root, "NIFTY", day)
            self.assertEqual(result, old)
            self.assertEqual(len(list((root/"metadata").rglob("*.json"))), 1)

    def test_cached_cas_revalidation_never_authenticates_or_downloads(self):
        day = date(2026, 10, 12)
        payload = response()
        payload["Success"] = [dict(r, datetime=r["datetime"].replace("2026-06-23", str(day))) for r in payload["Success"]
                              if r["datetime"][11:16] not in ("15:16", "15:17", "15:18", "15:19")]
        class Initial:
            def fetch(self, params):
                return payload
        with tempfile.TemporaryDirectory(prefix="algo8-cas-revalidate-") as folder:
            root = Path(folder)
            with self.assertRaises(module.MissingMinutesError):
                module.fetch_day(Initial(), root, "NIFTY", day, normalizer_version=1)
            raw = next((root/"raw").rglob("*.json"))
            original = raw.read_bytes()
            argv = ["fetch", "--revalidate-cached", "--index", "NIFTY", "--start", str(day), "--end", str(day), "--output", folder]
            with patch.object(module.sys, "argv", argv), patch.object(module, "request_json", side_effect=AssertionError("network forbidden")), patch("sys.stdout", new_callable=io.StringIO) as out:
                module.main()
            self.assertIn('"status": "complete"', out.getvalue())
            meta = module.json.loads(next((root/"metadata").rglob("*.json")).read_text())
            self.assertEqual(meta["interpretation"]["normalizer_version"], 2)
            self.assertEqual(meta["regular_session_bars"], 371)
            self.assertEqual(raw.read_bytes(), original)

    def test_wrong_index_bad_prices_and_empty_rejected(self):
        for field, value in (("stock_code", "RELIND"), ("exchange_code", "BSE"),
                             ("high", 98), ("close", float("nan"))):
            payload = response()
            payload["Success"][0][field] = value
            with self.assertRaises(module.FetchError):
                module.normalize(payload, "NIFTY", DAY, "Asia/Kolkata", "start")
        with self.assertRaises(module.FetchError):
            module.normalize(dict(Status=200, Success=[]), "NIFTY", DAY, "Asia/Kolkata", "start")

    def test_end_labels_require_explicit_interpretation(self):
        payload = response()
        for bar in payload["Success"]:
            bar["datetime"] = (datetime.fromisoformat(bar["datetime"])+timedelta(minutes=1)).isoformat(" ")
        with self.assertRaises(module.FetchError):
            module.normalize(payload, "NIFTY", DAY, "Asia/Kolkata", "start")
        self.assertEqual(len(module.normalize(payload, "NIFTY", DAY, "Asia/Kolkata", "end")), 375)

    def test_wrong_timezone_rejected(self):
        with self.assertRaises(module.FetchError):
            module.normalize(response(), "NIFTY", DAY, "UTC", "start")

    def test_resume_uses_raw_without_another_request(self):
        class FakeClient:
            calls = 0
            def fetch(self, params):
                self.calls += 1
                return response()
        client = FakeClient()
        with tempfile.TemporaryDirectory(prefix="algo8-breeze-test-") as folder:
            root = Path(folder)
            first = module.fetch_day(client, root, "NIFTY", DAY)
            second = module.fetch_day(client, root, "NIFTY", DAY)
            self.assertEqual(first, second)
            self.assertEqual(client.calls, 1)
            self.assertEqual(len(list(root.rglob("*.csv"))), 1)
            path = next(root.rglob("*.csv"))
            path.write_text("user data\n")
            with self.assertRaises(module.FetchError):
                module.fetch_day(client, root, "NIFTY", DAY)
            self.assertEqual(path.read_text(), "user data\n")

    def test_legacy_windows_metadata_resumes_without_overwrite(self):
        class FakeClient:
            def fetch(self, params):
                return response()
        with tempfile.TemporaryDirectory(prefix="algo8-windows-meta-") as folder:
            root = Path(folder)
            metadata = module.fetch_day(FakeClient(), root, "NIFTY", DAY)
            for key in ("raw_path", "normalized_path"):
                metadata[key] = metadata[key].replace("/", "\\")
            path = next((root/"metadata").rglob("*.json"))
            saved = module.canonical(metadata)
            path.write_bytes(saved)
            with patch.object(FakeClient, "fetch", side_effect=AssertionError("unexpected network call")):
                result = module.fetch_day(FakeClient(), root, "NIFTY", DAY)
            self.assertEqual(result, metadata)
            self.assertEqual(path.read_bytes(), saved)

    def test_request_under_candle_cap(self):
        p = module.parameters("NIFTY", DAY)
        span = (datetime.fromisoformat(p["to_date"])-datetime.fromisoformat(p["from_date"])).total_seconds()/60+1
        self.assertLessEqual(span, 1000)
        self.assertNotIn("AppKey", p)
        self.assertNotIn("SessionToken", p)

    def test_study_calendar_excludes_only_four_confirmed_weekday_holidays(self):
        targets, excluded = module.build_targets(date(2026, 6, 22), date(2026, 10, 22))
        self.assertEqual(len(targets), 170)
        self.assertEqual(len(excluded), 8)
        self.assertEqual({r["date"] for r in excluded}, {"2026-06-26", "2026-09-14", "2026-10-02", "2026-10-20"})
        self.assertTrue(all(day.weekday() < 5 for u, day in targets))
        self.assertEqual(sum(u == "NIFTY" for u, day in targets), 85)
        self.assertEqual(sum(u == "SENSEX" for u, day in targets), 85)

    def test_calendar_resumes_at_next_regular_session_and_filters_index(self):
        targets, excluded = module.build_targets(date(2026, 6, 26), date(2026, 6, 29), "NIFTY")
        self.assertEqual(targets, [("NIFTY", date(2026, 6, 29))])
        self.assertEqual(len(excluded), 1)
        smoke, excluded = module.build_targets(DAY, DAY, "SENSEX", smoke=True)
        self.assertEqual(smoke, [("SENSEX", date(2026, 6, 24))])
        self.assertEqual(excluded, [])

    def test_html_denial_is_reported_without_echoing_body(self):
        class Reply(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()
        class Opener:
            def open(self, request, timeout):
                return Reply(b'<html>Request Rejected. Your support ID is: <b>123456789012</b> private-marker</html>')
        with patch.object(module.urllib.request, "build_opener", return_value=Opener()):
            with self.assertRaises(module.FetchError) as caught:
                module.request_json(module.HISTORY_URL, {})
        self.assertIn("123456789012", str(caught.exception))
        self.assertIn("historical", str(caught.exception))
        self.assertNotIn("private-marker", str(caught.exception))

    def test_certificate_failure_has_safe_specific_reason(self):
        error = module.ssl.SSLCertVerificationError(1, "private-marker")
        error.verify_code = 20
        error.verify_message = "unable to get local issuer certificate"
        diagnostic = module.connection_diagnostic(module.urllib.error.URLError(error))
        self.assertEqual(diagnostic["category"], "tls_certificate_verification")
        self.assertEqual(diagnostic["verify_code"], 20)
        self.assertEqual(diagnostic["reason"], "unable to get local issuer certificate")
        self.assertNotIn("private-marker", str(diagnostic))

    def test_proxy_error_does_not_echo_credential_url(self):
        error = module.urllib.error.URLError("private-marker http://username:password@proxy.invalid/")
        diagnostic = module.connection_diagnostic(error)
        self.assertEqual(diagnostic["category"], "connection_or_proxy_error")
        self.assertNotIn("password", str(diagnostic))
        self.assertNotIn("proxy.invalid", str(diagnostic))

    def test_dns_and_reset_failures_are_distinguished(self):
        self.assertEqual(module.connection_diagnostic(module.socket.gaierror(11001, "private-marker"))["category"], "dns_resolution")
        self.assertEqual(module.connection_diagnostic(ConnectionResetError(10054, "private-marker"))["category"], "connection_reset")

    def test_network_diagnostics_never_send_credentials(self):
        sent = []
        class Reply(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()
        class Opener:
            def open(self, request, timeout):
                sent.append(request)
                return Reply(b"public-response")
        with patch.object(module.urllib.request, "build_opener", return_value=Opener()):
            diagnostic = module.network_diagnostics()
        self.assertEqual(len(sent), 3)
        self.assertFalse(diagnostic["credential_values_included"])
        for request in sent:
            self.assertIsNone(request.data)
            self.assertFalse(request.has_header("Apikey"))
            self.assertFalse(request.has_header("X-sessiontoken"))

    def test_default_tls_requires_certificate_and_hostname_validation(self):
        with patch.object(module, "TLS_BACKEND", "python"):
            context = module.tls_context()
        self.assertEqual(context.verify_mode, module.ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_native_trust_context_is_used_without_global_ssl_injection(self):
        context = module.ssl.create_default_context()
        class Native:
            SSLContext = staticmethod(lambda protocol: context)
        with patch.object(module, "TLS_BACKEND", "native"), patch.object(module.importlib, "import_module", return_value=Native), patch.dict(module.os.environ, {}, clear=True):
            self.assertIs(module.tls_context(), context)
        self.assertEqual(context.verify_mode, module.ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_unverified_native_context_is_rejected(self):
        context = module.ssl.SSLContext(module.ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        class Native:
            SSLContext = staticmethod(lambda protocol: context)
        with patch.object(module, "TLS_BACKEND", "native"), patch.object(module.importlib, "import_module", return_value=Native), patch.dict(module.os.environ, {}, clear=True):
            with self.assertRaises(module.FetchError):
                module.tls_context()


if __name__ == "__main__":
    unittest.main()
