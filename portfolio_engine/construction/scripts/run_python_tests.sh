#!/usr/bin/env bash
# Python tests of the plugin framework (includes the Python/C++ parity tests; they build the C++ code with cmake in a temp directory).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest tests -q -p no:cacheprovider "$@"
