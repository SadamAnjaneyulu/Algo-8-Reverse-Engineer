#!/usr/bin/env bash
# Reproduces every lot-lifecycle output. Needs the live ledger (Trades_GKOHNP140.csv), the pinned dataset commit via bt.gitdata, and the per-cycle cache built by replication/data.py (git-ignored).
set -euo pipefail; cd "$(dirname "$0")/src"
python3 build_lots.py        # unit lots under 4 ownership conventions -> outputs/lots.csv.gz, cycles.csv (primary D1 reading)
python3 build_lots.py unrecorded_short   # alternative D1 reading -> outputs/lots_alt_unrecorded_short.csv.gz
python3 reconcile.py         # exact P&L reconciliation -> cycle_reconciliation.csv
python3 audit_opening_book.py  # defect E audit -> opening_book_audit.csv
python3 run_remediation.py   # defects A-C: simulator v2, matching sensitivity
python3 carried_lots.py && python3 carried_analysis.py     # Phase 3
python3 replacement.py       # Phase 4 (about 3 minutes; 200 null draws)
python3 link_wings.py        # wing / replacement association layer
python3 figures.py           # charts
cd .. && python3 -m pytest tests -q
