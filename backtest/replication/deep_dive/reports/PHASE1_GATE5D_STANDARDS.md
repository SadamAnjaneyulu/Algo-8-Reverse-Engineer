# Phase 1, Gate 5d: quality standards for the D0 full-system validation (fixed before the 5d report is generated)

*Written 2026-11-25 before `bl_p1_5d.py` produced the 5d report. **Honesty note:** the 5b and 5c values (OOF keys F1 0.42, legacy 0.41) were already known to the author, so these are **public yardsticks**, not blind targets. They are set at what a defensible approximate D0 reconstruction from fills and one-minute bars should show (lower than the D-1 standards because D0 has more modules and order splitting), not tuned to the current numbers; several are expected to fail. Evaluated object: **D0-C = Gate 5a engine + accepted candidate X1 (era clearance clock)**, mode T (teacher-forced start from the real carried book), OOF 30 cycles with forward A (9) and forward B (10) reported separately; convention `events` (primary) and `one_lot` (sensitivity). Evidence label: historical reproduction. Free-running D-1 -> D0 (mode F) is Gate 6 and is never mixed with these numbers. Nothing committed.*

| # | Standard (60 s, one-to-one matching, spec v1.1 unless stated) |
|---|---|
| D1 | pooled order-level F1 (keys) >= 0.55 |
| D2 | pooled strict F1 (strike and lots exact) >= 0.35 |
| D3 | legacy lot-level OOF F1 >= 0.55 |
| D4 | per-cycle F1 (keys) >= 0.35 in at least 80% of cycles |
| D5 | every class with >= 100 real orders has F1 (keys) >= 0.40 |
| D6 | the +15-minute shift placebo F1 is at most 60% of the actual F1 |
| D7 | cycle stop: the engine stops in >= 8 of the 11 real-stop cycles and in at most 3 cycles without a real stop |
| D8 | risk controls (enforce): 0 refused orders on the 49 split-cycle runs; short lots per right never above 306; sell decisions per minute never above 90 |
| D9 | portfolio state: median normalised contract-level book distance at matched events <= 0.45 |
| D10 | forward A and forward B keys F1 each >= OOF - 0.05 |
| D11 | clearance volume: over the OOF cycles with a real clearance, the median ratio (simulated clearance lots) / (real clearance lots, orders from the real clearance start) is within 0.8-1.2 |
| D12 | the full replay reproduces identically on rerun, the default configuration still reproduces the Gate 5a reference 49/49, and all test suites pass |
| D13 | every class with more than 5% of its orders unmatched has a root-cause classification or an explicit data-limit statement |
**Pass rule:** Gate 5d is PASS if all hold. If every failure is classified as data-limited (or execution-layer) with its impact quantified, Gate 5d is CONDITIONAL. A failure attributable to an identifiable, testable component returns to that component (5c). Candidates (X1) are reported with and without; X3 and variants rejected at 5c do not appear except as listed rejections.
