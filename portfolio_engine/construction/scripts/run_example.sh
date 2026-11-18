#!/usr/bin/env bash
# Runs the 195-unit example (scenarios/s05_reentry_success.scn) in Python and in C++, shows the step-by-step walkthrough and checks that both write identical files.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-$(mktemp -d)}"
mkdir -p "$OUT/python" "$OUT/cpp"
PYTHONPATH=python python3 -m pc.cli run scenarios/s05_reentry_success.scn --out "$OUT/python"
[ -x build/pc_run ] || { cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release >/dev/null && cmake --build build >/dev/null; }
./build/pc_run scenarios/s05_reentry_success.scn "$OUT/cpp"
diff -r "$OUT/python" "$OUT/cpp" && echo "Python and C++ outputs are byte-identical ($OUT)"
cat examples_output/walkthrough_s05_reentry_success.txt
