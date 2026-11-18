#!/usr/bin/env bash
# Build the PDF from the SAME Markdown file:  bash report/build/build_pdf.sh   (run from the repository root)
set -euo pipefail
cd "$(dirname "$0")/.."
pandoc ALGO8_COMPLETE_RESEARCH_REPORT.md -f markdown -t html5 --standalone --toc --toc-depth=2 \
  --css build/report.css --include-before-body build/titlepage.html --resource-path=. --embed-resources \
  --metadata pagetitle="Algo 8 Complete Research Report" -o build/report.html
node build/print_pdf.js build/report.html ALGO8_COMPLETE_RESEARCH_REPORT.pdf
python3 build/toc_pages.py build/report.html ALGO8_COMPLETE_RESEARCH_REPORT.pdf      # second pass: page numbers in the contents
node build/print_pdf.js build/report.html ALGO8_COMPLETE_RESEARCH_REPORT.pdf
pandoc ALGO8_CALL_BRIEF.md -f markdown -t html5 --standalone --css build/report.css --embed-resources --metadata pagetitle="Algo 8 call brief" -o build/brief.html
node build/print_pdf.js build/brief.html build/ALGO8_CALL_BRIEF_preview.pdf
