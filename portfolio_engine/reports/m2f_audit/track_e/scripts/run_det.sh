#!/bin/bash
# usage: run_det.sh <repo-clone-root> <log>   (clone root contains portfolio_engine/; env vars TZ/LC_ALL/PYTHONHASHSEED are inherited)
# Deletes generated outputs (keeps hand-written review_dispositions.json), then runs the 7 generators in dependency order, timing each.
ROOT=$1; LOG=$2; RUNCWD=${3:-$ROOT}; cd "$ROOT" || exit 1; R=portfolio_engine/reports
rm -rf $R/m2c_data $R/m2d_data $R/m2e_figures $R/M2E_POSITION_CASE_STUDIES.md $R/M2E_VISUALIZATION_CATALOG.md $R/M2E_CYCLE_COVERAGE_REPORT.md
find $R/m2e_data -mindepth 1 ! -name review_dispositions.json -exec rm -rf {} + 2>/dev/null
: > "$LOG"
for t in m2c_closing_batches m2d_wing_body m2e_build m2e_charts m2e_cases m2e_catalog m2e_coverage_report; do
  s=$(date +%s.%N); (cd "$RUNCWD" && PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/portfolio_engine/tools/$t.py") > "$LOG.$t.out" 2>&1; rc=$?; e=$(date +%s.%N)
  echo "$t rc=$rc seconds=$(echo "$e - $s" | bc)" >> "$LOG"
done
