# Download the option-minute data

**Current status:** all 3,243 planned option contract-days were downloaded locally,
pushed in `9953c0d`, and received and reproduced in the cloud. There are 1,230,065
observed candles; 200 contract-days have explicitly recorded minute gaps. See
`research/OPTION_TRIGGER_FINDINGS.md` for the resulting replay. The commands below
remain available for reproducibility and additional requested contracts.

The direct cloud Breeze key/session pair was rejected at session exchange on
26 October 2026. The completed data arrived through the working local download
and repository push. That earlier rejection does not establish whether the session was
expired, mismatched to the app key or affected by another account/service issue.

Use the Windows checkout and native TLS setup that successfully downloaded the
index data. From `C:\Users\Administrator\Algo8-local` on branch
`data/local-breeze-fetch`:

```powershell
git pull --ff-only
py research/fetch_breeze_options.py --smoke --fetch --prompt-credentials --tls-backend native --continue-unavailable
```

Enter the API key and its **active API-login session** at the hidden prompts.
The process does not save them. No API-secret entry is needed for this documented
V2 historical flow. Do not put credentials into source files, commands or chat.

The four full-session smoke requests are actual contracts in the logs:

| Index | Trade date | Expiry | Strike | Rights |
| --- | --- | --- | ---: | --- |
| NIFTY | 6 July 2026 | 7 July 2026 | 24,350 | CE and PE |
| SENSEX | 7 October 2026 | 8 October 2026 | 72,600 | CE and PE |

Check the four `SMOKE CHECK PASS` messages. These require exact contract identity,
full minute-price coverage and at least 80% agreement between recorded fills and
their event-minute OHLC range, allowing one 0.05 price tick. This is a diagnostic
threshold, not a proven execution-price model or an optimized trading parameter.
A failure leaves the bars available for review and prevents bulk requests.

## Pull the exact traded contracts

Once the smoke samples pass:

```powershell
py research/fetch_breeze_options.py --scope all --fetch --prompt-credentials --tls-backend native --continue-unavailable
py research/push_validated_breeze_options.py --push
```

The plan contains **3,243 contract-days: 1,445 NIFTY and 1,798 SENSEX**. It requests
every traded contract throughout its observed cycle, including holding days
without executions. It covers the observed study interval only; omitted initial
inventory and unobserved pre-log holding days remain unresolved.

The existing 170 index sessions and their hashes remain unchanged. Options are
stored separately under `data/breeze/{raw,normalized,metadata}/options/`. Rate
limiting is inherited from the index client: at least 1.25 seconds between
historical requests, with bounded retries on retryable HTTP statuses. A complete
uncached plan takes at least about 68 minutes, plus network time/retries.

Completed requests resume from immutable raw caches. To rebuild cached outputs
without credentials or network requests, use `--revalidate-cached` instead of
`--fetch --prompt-credentials --tls-backend native`.

For a smaller first investigation, replace `--scope all` with `--scope sample`:
356 contract-days over the four contrasting cycles in the trigger study. The
four smoke requests remain the prerequisite. Choose either scope; shared caches
avoid downloading the same contract/day twice.

If SENSEX is unavailable while NIFTY works, add `--index NIFTY` to the smoke and
bulk commands to proceed independently. BFO historical support is documented in
an official historical example, but actual expired SENSEX coverage still requires
these live samples; BSE index success alone does not establish it.

## Interpreting gaps and progress

Option history is not validated using the index cash-session grid. Derivatives
continue during the CAS transition: expected minutes are **375 before 3 August**
and **385 from 3 August**, through the 15:39 minute, within this verified study.
Cash-transition gaps at 15:16–15:19 therefore remain missing option observations.

Illiquid contracts can have missing trade candles. The downloader preserves actual
observations, lists every missing minute, retains volume/open interest and records
zero-price/zero-volume bars. It never fills missing prices, assumes that a missing
bar means no market risk, or treats a zero-volume candle as an executable quote.

- `OBSERVED` means returned bars passed structural and identity checks. It does
  not mean a complete tradable grid or reliable portfolio marks.
- `UNAVAILABLE` means a contract/day could not be validated. With
  `--continue-unavailable`, it remains listed and the run exits with code 2.
- Authentication, HTTP, connection and explicit request-rejection failures stop
  further calls even when continuation was requested.
- Empty results are retained as raw-cache evidence, without normalized output or
  completion metadata. Re-running does not overwrite that response; review the
  reason before planning another broker request.
- The run summary is `data/breeze/diagnostics/options_download_review.json`.
  Missing minutes and fill comparisons are in each contract/day's metadata.

The options publisher stages only reproduced raw/CSV/metadata triples. It excludes
credentials, diagnostics, unrelated work and failed raw-only requests. It allows
explicitly sparse observations to be shared **with their missing-minute flags**;
it does not declare them complete for marked replay. Use the options publisher,
not the index publisher, for these new files.

## Strike-selection comparisons and limits

The default exact-traded plan supports initial stop/hedge replay once sufficient
marks are present. Testing why a strike was selected also requires unselected
neighbors. `--neighbors 2` adds two strike steps on each side of every selected
strike (50-point NIFTY, 100-point SENSEX); check its default plan before fetching.
Some neighbors may not have been listed or traded. Retain those failures rather
than substituting contracts. Neighbor coverage still does not guarantee a full
eligible option chain or identify the original selector.

Trade candles are not bid/ask quotes and do not directly supply IV, delta, theta,
transaction costs or an exact stop path inside a minute. Preserve these limits
when attributing returns or diagnosing intraminute triggers.

The official [SDK V2 options example](https://github.com/Idirect-Tech/Breeze-Python-SDK/blob/main/README.md#historical_data_v23)
documents the contract parameters and 1,000-interval request cap. Each request
here spans fewer than 1,000 minutes. The source snapshot hash, current acquisition
status and request manifests are under `research/outputs/`.

Offline checks:

```powershell
py research/test_breeze_options.py
```
