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

    def test_request_under_candle_cap(self):
        p = module.parameters("NIFTY", DAY)
        span = (datetime.fromisoformat(p["to_date"])-datetime.fromisoformat(p["from_date"])).total_seconds()/60+1
        self.assertLessEqual(span, 1000)
        self.assertNotIn("AppKey", p)
        self.assertNotIn("SessionToken", p)

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
