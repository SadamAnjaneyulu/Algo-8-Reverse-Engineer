"""Validate data-only artifacts, then optionally commit and push on a work branch.

Default prints the candidate file list. --push stages ONLY verified raw/index,
normalized/index and metadata triples. It rejects pre-existing staged work,
main/master branches, unexpected GitHub remotes, and unexpected response fields.
"""

import argparse
import csv
import importlib.util
import io
import json
import subprocess
import sys
import urllib.parse
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("breeze_fetch", Path(__file__).with_name("fetch_breeze_indices.py"))
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)
BAR_FIELDS = {"datetime", "stock_code", "exchange_code", "product_type", "open", "high", "low", "close", "volume", "open_interest", "count"}
META_FIELDS = {"underlying", "date", "request", "interpretation", "regular_session_bars", "raw_sha256", "normalized_sha256", "raw_path", "normalized_path", "retrieved_at_utc", "status", "note"}
EXPECTED_NOTE = "Index provider_volume is retained for provenance, not treated as traded index volume."


def contained(root, relative, prefix):
    # Metadata written on Windows must resolve identically after a Linux clone.
    relative = relative.replace("\\", "/")
    path = root / relative
    if Path(relative).is_absolute() or path.is_symlink() or not path.resolve().is_relative_to((root/prefix).resolve()):
        raise fetch.FetchError("Artifact path is outside the expected data subtree.")
    if not path.is_file():
        raise fetch.FetchError("A referenced data artifact is missing.")
    return path


def validated_files(root):
    data = root/"data"/"breeze"
    selected = set()
    for path in sorted((data/"metadata"/"indices").glob("*/*.json")):
        if path.is_symlink() or not path.resolve().is_relative_to((data/"metadata"/"indices").resolve()):
            raise fetch.FetchError("Unexpected metadata path.")
        metadata = json.loads(path.read_text())
        if set(metadata) != META_FIELDS or metadata["status"] != "complete_under_documented_timestamp_convention" or metadata["note"] != EXPECTED_NOTE:
            raise fetch.FetchError("Unexpected metadata fields or incomplete data; not staged.")
        u, day = metadata["underlying"], date.fromisoformat(metadata["date"])
        if u not in fetch.SYMBOLS or path.parent.name != u or metadata["request"] != fetch.parameters(u, day):
            raise fetch.FetchError("Metadata does not match a supported index/day request.")
        profile = metadata["interpretation"]
        if set(profile) != {"response_timezone", "bar_label", "normalizer_version"} or profile["normalizer_version"] != 1 or profile["bar_label"] not in ("start", "end"):
            raise fetch.FetchError("Unexpected normalization profile.")
        datetime.fromisoformat(metadata["retrieved_at_utc"])
        raw = contained(data, metadata["raw_path"], f"raw/indices/{u}")
        normalized = contained(data, metadata["normalized_path"], f"normalized/indices/{u}")
        if fetch.digest(raw.read_bytes()) != metadata["raw_sha256"] or fetch.digest(normalized.read_bytes()) != metadata["normalized_sha256"]:
            raise fetch.FetchError("Data hash mismatch; nothing staged.")
        payload = json.loads(raw.read_text())
        if set(payload) != {"request", "response", "retrieved_at_utc"} or payload["request"] != metadata["request"] or payload["retrieved_at_utc"] != metadata["retrieved_at_utc"]:
            raise fetch.FetchError("Raw payload does not match metadata.")
        response = payload["response"]
        if set(response) != {"Status", "Success"} or response["Status"] != 200 or not isinstance(response["Success"], list):
            raise fetch.FetchError("Unexpected raw response shape.")
        if any(not isinstance(bar, dict) or set(bar)-BAR_FIELDS for bar in response["Success"]):
            raise fetch.FetchError("Unexpected raw-bar fields; review before sharing. Nothing staged.")
        bars = fetch.normalize(response, u, day, profile["response_timezone"], profile["bar_label"])
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=list(bars[0]))
        writer.writeheader()
        writer.writerows(bars)
        if metadata["regular_session_bars"] != len(bars) or output.getvalue().encode() != normalized.read_bytes():
            raise fetch.FetchError("Normalized data does not reproduce from the saved raw response.")
        selected.update((path.relative_to(root).as_posix(), raw.relative_to(root).as_posix(), normalized.relative_to(root).as_posix()))
    if not selected:
        raise fetch.FetchError("No completed, validated index sessions exist; nothing to push.")
    return sorted(selected)


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise fetch.FetchError(f"Git {args[0]} failed; original files preserved. Inspect your terminal/Git configuration; remote error text suppressed.")
    return r.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--push", action="store_true", help="Commit verified data only, then push the current work branch.")
    args = parser.parse_args()
    files = validated_files(ROOT)
    profiles = sum(path.startswith("data/breeze/metadata/indices/") for path in files)
    print(f"Validated {profiles} index day/profile records ({len(files)} artifact paths).")
    if not args.push:
        for path in files:
            print(path)
        return
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch in ("main", "master"):
        raise fetch.FetchError("Switch to a work branch before publishing data.")
    if git("diff", "--cached", "--name-only"):
        raise fetch.FetchError("Other staged changes exist; preserved them without mixing commits.")
    remote = git("remote", "get-url", "origin")
    parsed = urllib.parse.urlparse(remote)
    identity = parsed.path.strip("/").removesuffix(".git")
    valid = parsed.hostname == "github.com" and identity.lower() == "sadamanjaneyulu/algo-8-reverse-engineer"
    valid = valid or remote.lower().removesuffix(".git") == "git@github.com:sadamanjaneyulu/algo-8-reverse-engineer"
    if not valid:
        raise fetch.FetchError("Origin is not the requested GitHub repository; not staging or pushing.")
    # Paths come from verified data triples, never a broad git add of the checkout.
    for offset in range(0, len(files), 100):
        git("add", "--", *files[offset:offset+100])
    if git("diff", "--cached", "--name-only"):
        git("commit", "-m", "Add validated Breeze minute index data")
    git("push", "-u", "origin", "HEAD")
    print(f"Pushed validated data on branch {branch}.")


if __name__ == "__main__":
    try:
        main()
    except (fetch.FetchError, ValueError, KeyError, TypeError, OSError) as exc:
        # FetchError text is deliberately sanitized. Other exceptions may include
        # user-authored file contents; report their class without values.
        print(str(exc) if isinstance(exc, fetch.FetchError) else f"Validation stopped: {type(exc).__name__}; no automatic overwrite.", file=sys.stderr)
        sys.exit(1)
