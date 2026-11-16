#!/usr/bin/env bash
# Build the condensed report:  bash report/build/build_rahul.sh  (any directory)
set -euo pipefail
cd "$(dirname "$0")/.."
pandoc ALGO8_RESEARCH_REPORT_RAHUL.md -f markdown+smart -t html5 --standalone --css build/rahul.css --resource-path=. --embed-resources \
  --metadata pagetitle="Algo 8 Research Summary" -o build/rahul.html
node build/print_rahul.js build/rahul.html ALGO8_RESEARCH_REPORT_RAHUL.pdf
