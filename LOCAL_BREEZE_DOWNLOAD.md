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

`NIFTY`/NSE and `BSESEN`/BSE index mappings require live confirmation. Current
Breeze API docs say BSE securities are unavailable despite BFO SDK examples;
SENSEX coverage remains unverified. If NIFTY works but SENSEX does not, continue
NIFTY separately and retain the SENSEX limitation:

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
