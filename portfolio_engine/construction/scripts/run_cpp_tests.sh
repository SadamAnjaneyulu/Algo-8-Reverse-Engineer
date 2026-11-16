#!/usr/bin/env bash
# Builds the C++ side of the plugin framework and runs its own unit tests.
set -euo pipefail
cd "$(dirname "$0")/.."
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/pc_tests
