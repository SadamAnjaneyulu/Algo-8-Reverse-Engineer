#!/usr/bin/env bash
# Re-creates every table and report from the pinned commit (read-only; about 40 minutes on 4 cores). Needs pandas, numpy, pyarrow and the committed reference/ files.
set -euo pipefail
cd "$(dirname "$0")"
C=${1:-eb4097308d47ccc75078ab73ba76d33bb1c7030b}
python3 -m validation.inventory "$C" reports/tables
python3 -m validation.session_scan "$C" reports/tables
python3 -m validation.deep_scan "$C" reports/tables
python3 -m validation.legacy_crosscheck "$C" reports/tables
python3 -m validation.extra_findings "$C" reports/tables
python3 -m validation.coverage "$C" reports/tables reports/tables
python3 -m validation.yahoo_compare reports/tables
python3 -m validation.quality_summary reports/tables
python3 -m validation.report_numbers
python3 -m validation.make_reports
python3 -m pytest tests -q -p no:cacheprovider
