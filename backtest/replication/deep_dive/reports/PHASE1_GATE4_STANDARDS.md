# Phase 1, Gate 4: quality standards for the D-1 full-system validation (fixed before the report is generated)

*Written 2026-11-25 before `bl_p1_gate4.py` produced the Gate 4 report. **Honesty note:** the B1 values were already known to the author (Gates 2-3), so these standards are **public yardsticks fixed before the report**, not blind targets. They were chosen as what a defensible approximate reconstruction from fills and one-minute bars should show, not tuned to B1. Evaluated object: the frozen B1 (accepted `one_lot_v2`), mode F, 32 development cycles; evidence label: historical reproduction. Nothing committed.*

| # | Standard (all measured at 60 s, one-to-one matching, spec v1.1 unless stated) |
|---|---|
| Q1 | pooled order-level F1 (keys) >= 0.70 |
| Q2 | pooled strict F1 (strike exact and lots exact) >= 0.55 |
| Q3 | legacy lot-level F1 >= 0.65 |
| Q4 | per-cycle F1 (keys) >= 0.60 in **every** cycle |
| Q5 | every class with >= 100 real orders has F1 (keys) >= 0.50 |
| Q6 | the +15-minute time-shift placebo F1 is at most half of the actual F1 |
| Q7 | >= 95% of simulated scheduled straddles matched |
| Q8 | risk controls: 0 rejected orders; short lots per right never above the 400 limit; no decision count above 40 per minute (as enforced) |
| Q9 | portfolio state: median normalised contract-level book distance at matched events <= 0.35 |
| Q10 | the full replay reproduces identically on rerun and all test suites pass |
| Q11 | every class with more than 5% of its orders unmatched has a root-cause classification or an explicit data-limit statement |
**Pass rule:** Gate 4 is PASS if all hold. If the only failures are classified as data-limited with their impact quantified, Gate 4 is CONDITIONAL. If a failure is attributable to an identifiable, testable component, Gate 4 returns to that component's gate. F and TF-E are reported separately and never mixed; C1 and V01 appear only as sensitivity rows.
