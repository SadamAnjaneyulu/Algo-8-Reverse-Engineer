"""Read-only Breeze V2 index history; standard library, no secret files.

Default is a plan. Use --smoke --fetch for two live sample requests after secure
configuration. Credentials are read from BREEZE_API_KEY and BREEZE_API_SESSION;
proxy placeholders may be used through their configured HTTPS destinations.
"""

import argparse
import csv
import getpass
import hashlib
import io
import importlib
import json
import math
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as clock, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
try:
    IST = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    raise SystemExit("IANA timezone data is missing. Install it locally with: python -m pip install tzdata") from None
SESSION_URL = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
HISTORY_URL = "https://breezeapi.icicidirect.com/api/v2/historicalcharts"
SYMBOLS = {"NIFTY": ("NSE", "NIFTY"), "SENSEX": ("BSE", "BSESEN")}
TLS_BACKEND = "python"


class FetchError(Exception):
    """Contains only sanitized, non-credential diagnostics."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FetchError("Redirect refused; verify the documented endpoint.")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2)+"\n").encode()


def save_immutable(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise FetchError("Existing artifact differs; preserved it without overwriting.")
        return
    with path.open("xb") as f:
        f.write(content)


def tls_context():
    """Use a supported trust source; always require chain and hostname checks."""
    if TLS_BACKEND == "native":
        try:
            truststore = importlib.import_module("truststore")
        except ImportError:
            raise FetchError("Native TLS trust requires truststore: py -m pip install truststore==0.10.5") from None
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Preserve explicit additional CA bindings. Otherwise native truststore
        # uses Windows CryptoAPI / macOS Security / OS OpenSSL trust settings.
        cafile, capath = os.environ.get("SSL_CERT_FILE"), os.environ.get("SSL_CERT_DIR")
        if cafile or capath:
            context.load_verify_locations(cafile=cafile, capath=capath)
    else:
        context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise FetchError("TLS context must verify both certificate chains and hostnames.")
    return context


def https_opener():
    return urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=tls_context()))


def connection_diagnostic(exc):
    """Categorize transport errors without arbitrary exception text or URLs."""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, ssl.SSLCertVerificationError):
        labels = (
            "unable to get local issuer certificate", "unable to verify the first certificate",
            "self-signed certificate", "certificate has expired", "certificate is not yet valid",
            "hostname mismatch", "IP address mismatch", "Missing Authority Key Identifier",
            "Missing Subject Key Identifier", "Basic Constraints of CA cert not marked critical",
            "CA cert does not include key usage extension", "path length constraint exceeded",
            "unsuitable certificate purpose", "certificate chain too long", "certificate signature failure",
        )
        message = str(getattr(reason, "verify_message", ""))
        label = next((label for label in labels if label.lower() in message.lower()), "certificate verification failed")
        code = getattr(reason, "verify_code", None)
        return dict(category="tls_certificate_verification", verify_code=code if isinstance(code, int) else None,
                    reason=label)
    if isinstance(reason, socket.gaierror):
        return dict(category="dns_resolution", os_error_code=reason.errno)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return dict(category="connection_timeout")
    if isinstance(reason, ssl.SSLError):
        return dict(category="tls_handshake")
    if isinstance(reason, ConnectionRefusedError):
        return dict(category="connection_refused", os_error_code=reason.errno)
    if isinstance(reason, ConnectionResetError):
        return dict(category="connection_reset", os_error_code=reason.errno)
    if isinstance(reason, OSError):
        return dict(category="connection_os_error", os_error_code=reason.errno,
                    windows_error_code=getattr(reason, "winerror", None))
    return dict(category="connection_or_proxy_error", reason_type=type(reason).__name__)


def network_diagnostics():
    """Credential-free checks through inherited proxy and verified TLS settings."""
    result = dict(python_version=sys.version.split()[0], openssl_version=ssl.OPENSSL_VERSION,
                  tls_backend=TLS_BACKEND,
                  credential_values_included=False, tls_verification="enabled",
                  configured_variable_presence={name: bool(os.environ.get(name)) for name in
                      ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")},
                  proxy_scheme_names=sorted(urllib.request.getproxies()), endpoints=[])
    try:
        context = tls_context()
        if TLS_BACKEND == "native":
            result["certificate_store_source"] = "native_operating_system"
        else:
            result["certificate_store_counts"] = context.cert_store_stats()
    except OSError as exc:
        result["certificate_store_error"] = connection_diagnostic(exc)
    for url in (SESSION_URL, HISTORY_URL, "https://pypi.org/"):
        parsed = urllib.parse.urlparse(url)
        entry = dict(host=parsed.hostname, path=parsed.path)
        try:
            request = urllib.request.Request(url, method="GET")
            with https_opener().open(request, timeout=15) as response:
                content = response.read(1024)
                entry.update(transport="connected_with_verified_tls", http_status=response.status,
                             broker_rejection_page=b"request rejected" in content.lower())
        except urllib.error.HTTPError as exc:
            # A normal HTTP rejection still proves verified TLS reached a server.
            entry.update(transport="connected_with_verified_tls", http_status=exc.code)
        except (urllib.error.URLError, OSError) as exc:
            entry.update(transport="failed", **connection_diagnostic(exc))
        except FetchError:
            entry.update(transport="redirect_refused")
        result["endpoints"].append(entry)
    return result


def request_json(url, headers, body=None):
    # HTTPS proxy and CA configuration are inherited. Never log headers, request
    # bodies, session responses, or arbitrary provider error messages.
    opener = https_opener()
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, data=body, headers=headers, method="GET")
            with opener.open(request, timeout=30) as response:
                content = response.read()
            try:
                result = json.loads(content)
            except (ValueError, UnicodeError):
                if b"request rejected" in content.lower():
                    # An HTML edge rejection can arrive with HTTP 200. Extract
                    # only the broker's numeric support ID, never arbitrary body
                    # text, which might echo request or account information.
                    match = re.search(rb"support\s+id.{0,100}?([0-9]{8,30})", content, re.I | re.S)
                    support = f" Support ID: {match.group(1).decode()}." if match else ""
                    stage = "historical" if urllib.parse.urlparse(url).path.endswith("historicalcharts") else "session"
                    raise FetchError(f"Breeze {stage} endpoint returned an HTML Request Rejected page.{support} Broker access/service review is required; no data accepted.") from None
                raise FetchError("Provider did not return valid JSON; body suppressed.") from None
            if not isinstance(result, dict):
                raise FetchError("Provider returned an unexpected response shape.")
            return result
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise FetchError(f"HTTP {exc.code}; response body suppressed.") from None
        except (urllib.error.URLError, OSError) as exc:
            diagnostic = connection_diagnostic(exc)
            stage = "history" if urllib.parse.urlparse(url).path.endswith("historicalcharts") else "session"
            raise FetchError(f"Breeze {stage} connection failed: {json.dumps(diagnostic, sort_keys=True)}. Run --diagnose-network; credential-bearing details suppressed.") from None
        except (ValueError, UnicodeError):
            raise FetchError("Provider did not return valid JSON; body suppressed.") from None


def status_ok(response):
    return response.get("Status") in (200, "200") and not response.get("Error")


class BreezeHistory:
    def __init__(self):
        self.api_key = os.environ.get("BREEZE_API_KEY")
        self.api_session = os.environ.get("BREEZE_API_SESSION")
        self.history_session = None
        self.previous_history_request = None

    def authenticate(self):
        if not self.api_key or not self.api_session:
            raise FetchError("Missing BREEZE_API_KEY or BREEZE_API_SESSION; configure securely in environment settings.")
        # Mirrors Breeze SDK 1.0.69 api_util(). Its V2 history method uses this
        # returned token directly and does not compute an API-secret checksum.
        body = json.dumps({"SessionToken": self.api_session, "AppKey": self.api_key}, separators=(",", ":")).encode()
        response = request_json(SESSION_URL, {"Content-Type": "application/json"}, body)
        success = response.get("Success")
        if not status_ok(response) or not isinstance(success, dict) or not success.get("session_token"):
            raise FetchError("Breeze session exchange failed; verify the active API login session and app key. Response suppressed.")
        self.history_session = success["session_token"]

    def fetch(self, params):
        if self.history_session is None:
            self.authenticate()
        if self.previous_history_request is not None:
            time.sleep(max(0, 1.25-(time.monotonic()-self.previous_history_request)))
        self.previous_history_request = time.monotonic()
        response = request_json(HISTORY_URL+"?"+urllib.parse.urlencode(params),
                                {"Content-Type": "application/json", "apikey": self.api_key,
                                 "X-SessionToken": self.history_session})
        if not status_ok(response) or not isinstance(response.get("Success"), list):
            raise FetchError("Breeze historical request failed; provider error body suppressed. Check session, entitlement and index stock-code mapping.")
        # Store historical bars only; never persist the session-exchange response.
        return {"Status": 200, "Success": response["Success"]}


def parameters(underlying, target_date):
    exchange, stock = SYMBOLS[underlying]
    # 736 one-minute slots, below the documented 1,000 cap. This broad range
    # covers the full Indian session under either local-wall or UTC treatment of
    # the SDK's Z-suffixed request strings. Returned bars still require validation.
    return dict(interval="1minute", from_date=f"{target_date}T03:30:00.000Z",
                to_date=f"{target_date}T15:45:00.000Z", stock_code=stock,
                exch_code=exchange, product_type="cash")


def normalize(response, underlying, target_date, response_timezone, bar_label):
    bars = response["Success"]
    if not bars:
        raise FetchError("Empty history: holiday, unsupported index, retention or entitlement requires review; not marked complete.")
    expected_exchange, expected_stock = SYMBOLS[underlying]
    normalized = {}
    source_zone = ZoneInfo(response_timezone)
    for bar in bars:
        if not isinstance(bar, dict):
            raise FetchError("Unexpected history bar shape.")
        if str(bar.get("stock_code", "")).upper() != expected_stock:
            raise FetchError("Returned stock_code does not match requested index mapping.")
        if str(bar.get("exchange_code", "")).upper() != expected_exchange:
            raise FetchError("Returned exchange does not match request.")
        try:
            t = datetime.fromisoformat(str(bar["datetime"]).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=source_zone)
            t = t.astimezone(IST)
            if bar_label == "end":
                t -= timedelta(minutes=1)
            prices = {key: float(bar[key]) for key in ("open", "high", "low", "close")}
        except (KeyError, ValueError, TypeError):
            raise FetchError("Cannot parse bar timestamps or OHLC fields.") from None
        if not all(math.isfinite(v) and v > 0 for v in prices.values()):
            raise FetchError("Nonpositive or nonfinite index OHLC.")
        if prices["high"] < max(prices.values()) or prices["low"] > min(prices.values()):
            raise FetchError("Invalid OHLC bounds.")
        if t.second or t.microsecond:
            raise FetchError("One-minute bar timestamp is off the minute grid.")
        if t.date() != target_date or not clock(9, 15) <= t.time() < clock(15, 30):
            continue
        stamp = t.isoformat()
        if stamp in normalized:
            raise FetchError("Duplicate regular-session bar timestamp.")
        normalized[stamp] = dict(timestamp_ist=stamp, underlying=underlying, **prices,
                                 provider_volume=bar.get("volume", ""))
    expected = {(datetime.combine(target_date, clock(9, 15), IST)+timedelta(minutes=i)).isoformat() for i in range(375)}
    if set(normalized) != expected:
        raise FetchError(f"Incomplete regular session: {len(expected-set(normalized))} expected minutes missing; check calendar, timezone, bar labels and index support.")
    return [normalized[key] for key in sorted(normalized)]


def fetch_day(client, root, underlying, target_date, response_timezone="Asia/Kolkata", bar_label="start"):
    params = parameters(underlying, target_date)
    request_id = digest(canonical(params))[:12]
    profile = dict(response_timezone=response_timezone, bar_label=bar_label, normalizer_version=1)
    profile_id = digest(canonical(profile))[:10]
    raw_path = root/"raw"/"indices"/underlying/f"{target_date}.{request_id}.json"
    normalized_path = root/"normalized"/"indices"/underlying/f"{target_date}.{profile_id}.csv"
    metadata_path = root/"metadata"/"indices"/underlying/f"{target_date}.{profile_id}.json"
    if raw_path.exists():
        payload = json.loads(raw_path.read_text())
        if not isinstance(payload, dict) or set(payload) != {"request", "response", "retrieved_at_utc"} or payload["request"] != params:
            raise FetchError("Cached raw artifact does not match its request.")
        response = payload["response"]
        if not status_ok(response) or not isinstance(response.get("Success"), list):
            raise FetchError("Cached raw artifact is not a successful history response.")
    else:
        response = client.fetch(params)
        payload = dict(request=params, response=response,
                       retrieved_at_utc=datetime.now(timezone.utc).isoformat())
        save_immutable(raw_path, canonical(payload))
    bars = normalize(response, underlying, target_date, response_timezone, bar_label)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(bars[0]))
    writer.writeheader()
    writer.writerows(bars)
    content = output.getvalue().encode()
    save_immutable(normalized_path, content)
    metadata = dict(underlying=underlying, date=target_date.isoformat(), request=params,
                    interpretation=profile, regular_session_bars=len(bars),
                    raw_sha256=digest(raw_path.read_bytes()), normalized_sha256=digest(content),
                    raw_path=str(raw_path.relative_to(root)), normalized_path=str(normalized_path.relative_to(root)),
                    retrieved_at_utc=payload["retrieved_at_utc"],
                    status="complete_under_documented_timestamp_convention",
                    note="Index provider_volume is retained for provenance, not treated as traded index volume.")
    save_immutable(metadata_path, canonical(metadata))
    return metadata


def main():
    global TLS_BACKEND
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Actually request data; default only prints plan.")
    parser.add_argument("--smoke", action="store_true", help="NIFTY 23 June and SENSEX 24 June sample sessions.")
    parser.add_argument("--index", choices=("both", "NIFTY", "SENSEX"), default="both")
    parser.add_argument("--prompt-credentials", action="store_true", help="Prompt for missing credentials with hidden input in a local terminal; never write them to disk.")
    parser.add_argument("--diagnose-network", action="store_true", help="Print credential-free TLS/DNS/proxy diagnostics; does not download bars or prompt for secrets.")
    parser.add_argument("--tls-backend", choices=("python", "native"), default="python",
                        help="Certificate trust source. native requires truststore and uses Windows CryptoAPI on Windows; verification stays enabled.")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 22))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 22))
    parser.add_argument("--output", type=Path, default=ROOT/"data"/"breeze")
    parser.add_argument("--response-timezone", default="Asia/Kolkata")
    parser.add_argument("--bar-label", choices=("start", "end"), default="start")
    args = parser.parse_args()
    TLS_BACKEND = args.tls_backend
    if args.fetch or args.diagnose_network:
        try:
            tls_context()
        except FetchError as exc:
            parser.error(str(exc))
        except OSError:
            parser.error("Cannot initialize the configured certificate trust source; check trusted CA configuration.")
    if args.diagnose_network:
        print(json.dumps(network_diagnostics(), indent=2))
        return
    if args.fetch and args.prompt_credentials:
        missing = [n for n in ("BREEZE_API_KEY", "BREEZE_API_SESSION") if not os.environ.get(n)]
        if missing and not sys.stdin.isatty():
            parser.error("Credential prompting requires an interactive local terminal.")
        for name in missing:
            value = getpass.getpass(f"{name} (hidden): ").strip()
            if not value:
                parser.error(f"{name} was empty")
            os.environ[name] = value
    ZoneInfo(args.response_timezone)
    if args.end < args.start:
        parser.error("--end must not precede --start")
    targets = []
    if args.smoke:
        targets = [("NIFTY", date(2026, 6, 23)), ("SENSEX", date(2026, 6, 24))]
    else:
        current = args.start
        while current <= args.end:
            if current.weekday() < 5:
                targets.extend((u, current) for u in SYMBOLS)
            current += timedelta(days=1)
    if args.index != "both":
        targets = [(u, d) for u, d in targets if u == args.index]
    print(json.dumps(dict(mode="fetch" if args.fetch else "plan", target_index_days=len(targets),
                          output=str(args.output), mappings=SYMBOLS,
                          first_targets=[(u, str(d)) for u, d in targets[:4]],
                          credentials_present={n: bool(os.environ.get(n)) for n in ("BREEZE_API_KEY", "BREEZE_API_SESSION")},
                          note="Weekdays are candidates; an empty response is not accepted as a verified exchange holiday.")))
    if not args.fetch:
        return
    client = BreezeHistory()
    for underlying, target in targets:
        try:
            result = fetch_day(client, args.output, underlying, target, args.response_timezone, args.bar_label)
        except FetchError as exc:
            print(f"BLOCKED {underlying} {target}: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"VALIDATED {underlying} {target}: {result['regular_session_bars']} regular-session bars")


if __name__ == "__main__":
    main()
