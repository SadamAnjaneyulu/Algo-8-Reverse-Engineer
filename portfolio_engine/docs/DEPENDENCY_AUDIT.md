# Dependency audit (checked in this environment)

| Item | Present | Version | Decision |
|---|---|---|---|
| Python | yes | 3.13.18 | use |
| pytest | yes | 9.2.0 | use |
| numpy / pandas / pyarrow | yes | 2.5.3 / 3.0.5 / 26.0.1 | pandas/pyarrow only in the **historical generator** (reads TP-01 parquet); the engine itself is pure Python stdlib |
| matplotlib / plotly | yes | 3.11.2 / 7.1.0 | matplotlib for charts (already used by TP-01/02/03); plotly not needed |
| PyYAML | yes | 6.0.3 | config files |
| g++ / clang++ | yes | g++ 13.3.0 (C++17/20 available) | C++17, no third-party libs |
| cmake / make | yes | 3.28.3 | CMake build; `make`-free fallback `g++` one-liner in `tools/` |
| nlohmann/json | **no** | — | not used (TSV shared format) |
| pybind11 | **no** | — | not added in M1: fixture-based parity needs no binding; revisit in M3 with a recorded justification |
| GoogleTest/Catch2 | **no** | — | C++ tests use a tiny assert harness in the repo |
| Raw market bars | outside the repo (`ALGO8_MARKET_DIR`) | — | not needed for M1; M5/M6 marks will need them (documented) |
