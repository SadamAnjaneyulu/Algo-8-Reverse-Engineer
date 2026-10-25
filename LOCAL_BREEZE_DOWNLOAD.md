# Run the Breeze index download on your computer

The cloud login succeeds, but the history endpoint returns an HTML rejection.
The exact cause is unconfirmed. Running the same supported requests from your own
computer can distinguish a cloud-route issue from a broader account/service issue;
it is not guaranteed to resolve it. This chat cannot execute commands on your
computer or export cloud-managed credential values.

Use your existing checkout of `SadamAnjaneyulu/Algo-8-Reverse-Engineer` and the
`data/local-breeze-fetch` branch. No separate worktree is required.

```sh
git fetch origin data/local-breeze-fetch
git switch data/local-breeze-fetch
```

Python 3.9+ is required. On Windows, if IANA timezone data is unavailable:

```sh
python -m pip install tzdata
```

## First try two small requests

Run in an interactive terminal on your computer:

```sh
python research/fetch_breeze_indices.py --smoke --fetch --prompt-credentials
```

Enter your Breeze API key and active API-login session when prompted. Input is
hidden and stays in that process. It is never saved to a file or shell command.
Use the values you know locally; do not paste them into chat. Cloud proxy
placeholders are not portable credentials for your computer.

The requests are read-only. The downloader preserves your normal networking/TLS
settings. If the rejection repeats locally, stop and provide the sanitized support
ID to ICICI. Do not try to bypass broker controls or disable TLS verification.

For a connection/TLS/proxy error on your computer, first update and run the
credential-free diagnostic. On Windows PowerShell, from the repository folder:

```powershell
git pull --ff-only
py research/fetch_breeze_indices.py --diagnose-network
```

This does not ask for keys. It reports DNS/connection error categories, certificate
verification codes, proxy presence (never proxy values), and public endpoint HTTP
status. It preserves TLS verification and your inherited proxy configuration.
Share this diagnostic output to distinguish a local certificate/trust problem,
DNS failure, timeout, connection reset or broker HTTP rejection. It does not
establish data access just because HTTPS connects.

### Windows: self-signed certificate in the login endpoint's chain

If Python's diagnostic reports certificate verification code 19 for
`api.icicidirect.com`, while other sites pass TLS, do not assume the API key is
invalid. The chain is not trusted by that Python/OpenSSL context. The issuer and
reason (broker chain, security software, organizational inspection, or other
network behavior) remain unconfirmed.

Try the supported native Windows trust source. It uses Windows CryptoAPI chain
validation through `truststore`; it does not accept arbitrary self-signed
certificates, disable hostname checks, or install a new root certificate.

```powershell
git pull --ff-only
py -m pip install truststore==0.10.5
py research/fetch_breeze_indices.py --diagnose-network --tls-backend native
```

If the login endpoint now shows `connected_with_verified_tls` (an unauthenticated
HTTP 400/401/415 is acceptable for this connectivity check), retry:

```powershell
py research/fetch_breeze_indices.py --smoke --fetch --prompt-credentials --tls-backend native
```

Keep `--tls-backend native` on subsequent full downloads if this is the working
trust source. The normal proxy configuration and any explicitly configured CA
locations are retained. Official truststore source/docs:
https://pypi.org/project/truststore/0.10.5/ and https://truststore.readthedocs.io/.

If native verification also fails, stop before sending credentials and check the
certificate issuer in the browser/with IT or ICICI. Do not trust a certificate
downloaded from the failed connection, turn off antivirus, or set verification
to false to force the request through.

`NIFTY`/NSE and `BSESEN`/BSE have now returned full 375-bar sessions for 22–25 June
2026. Both mappings are verified for those downloaded dates. The earlier BSE
availability concern from conflicting documentation did not prevent these real
downloads. If a later date fails for one index, it can be investigated separately:

```sh
python research/fetch_breeze_indices.py --index NIFTY --smoke --fetch --prompt-credentials
```

## Fetch the study period after the sample validates

For both indices:

```sh
python research/fetch_breeze_indices.py --start 2026-06-22 --end 2026-10-22 --fetch --prompt-credentials
```

Or add `--index NIFTY` to fetch only the working series. Completed sessions resume
from their raw cache. The first unexpected empty/partial session stops the run;
an exchange holiday must be verified rather than silently filled or marked complete.

The verified calendar snapshot now excludes four full-day weekday holidays for
both indices in this study: **26 June (Muharram), 14 September (Ganesh Chaturthi),
2 October (Mahatma Gandhi Jayanti), and 20 October (Dussehra)**. Sources and retrieval
hashes are in `research/market_calendar_2026.json`: NSE's cash-market holiday API
and ICICI Direct's published BSE holiday list. The default plan now contains
**170 index-days: 85 for each index**. Unknown missing/partial sessions still stop.

If the previous run stopped at 26 June, update and rerun the original range:

```powershell
git pull --ff-only
py research/fetch_breeze_indices.py --start 2026-06-22 --end 2026-10-22 --fetch --prompt-credentials --tls-backend native
```

Existing validated sessions are reused. New metadata uses portable forward-slash
paths, while existing Windows-path metadata is preserved and supported. The
repository's `.gitattributes` keeps provider artifact bytes unchanged across
Windows/Linux so Git cannot invalidate the saved file hashes through EOL conversion.

## Push only validated data back to this repository

Review the exact file list, then publish it on the work branch:

```sh
python research/push_validated_breeze_data.py
python research/push_validated_breeze_data.py --push
```

The helper checks full 375-bar sessions, raw/normalized hashes, reproducible
normalization and artifact schemas before staging. It stages only validated data
triples under `data/breeze/{raw,normalized,metadata}/indices/`; it excludes scripts,
diagnostics, credential files and unrelated work. It refuses main/master,
unexpected remotes and an index with pre-existing staged changes. It makes a
data-only commit and pushes the current branch without force. Your local GitHub
authentication and Git commit identity must already work.

If no data validated, nothing is committed. The cloud agent can fetch the pushed
branch and continue the market-condition analysis after you report the result.
