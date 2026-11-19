# Historical data feasibility and cycle eligibility register

**Status:** computed from the independent expiry calendar and the full-chain minute caches built from the pinned dataset commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`. The eligibility criteria (`config/eligibility_criteria.yaml`) were written **before** this table existed; a cycle's class depends only on data availability, never on P&L. No replica performance exists yet.
Register (one row per expected expiry): `experiments/results/cycle_eligibility_register.csv`. Rebuild: `python3 tools/build_eligibility.py && python3 tools/make_feasibility_md.py`.

## 1. Result first
* **Expected cycles: 319** (NIFTY 160, SENSEX 159). **FULLY_FEASIBLE 153 · FEASIBLE_WITH_DECLARED_SUBSTITUTION 121 · PARTIAL 6 · UNUSABLE 39.** Results will be reported on (a) strictly complete cycles, (b) substituted cycles separately, (c) the full expected-cycle denominator.
* **Scheduled ATM entries are executable almost everywhere** (every usable cycle has all 17 D-1 windows with an executable ATM CE+PE; D0 windows ≥ 21 of 23). **The binding constraint is the seed wings:** both exact wings trade in the 09:16–09:20 window in only the share shown in §3, so a large part of the history needs a declared wing substitution.
* **SENSEX before 2024-05-30 does not exist** (30 expected Friday expiries; plus 5 unreported). The brief's "Nov 2023 – May 2024 development" block is NIFTY-only.
* **Nothing here is out-of-sample.** The evidence tiers of §4 apply; see `PHASE0_REPOSITORY_AUDIT.md` §5.

## 2. Eligibility by index and by proposed period (D0 date)
| und | FULLY_FEASIBLE | FEASIBLE_WITH_DECLARED_SUBSTITUTION | PARTIAL | UNUSABLE | expected | usable (fully + substituted) |
|---|---|---|---|---|---|---|
| NIFTY | 71 | 84 | 2 | 3 | 160 | 155 |
| SENSEX | 82 | 37 | 4 | 36 | 159 | 119 |

| period | und | FULLY_FEASIBLE | FEASIBLE_WITH_DECLARED_SUBSTITUTION | PARTIAL | UNUSABLE | expected | usable (fully + substituted) |
|---|---|---|---|---|---|---|---|
| P1_dev_2023-11_to_2024-05 | NIFTY | 7 | 23 | 0 | 1 | 31 | 30 |
| P1_dev_2023-11_to_2024-05 | SENSEX | 0 | 1 | 0 | 30 | 31 | 1 |
| P2_validation_2024-06_to_2025-05 | NIFTY | 21 | 30 | 1 | 0 | 52 | 51 |
| P2_validation_2024-06_to_2025-05 | SENSEX | 22 | 25 | 2 | 3 | 52 | 47 |
| P3_primary_2025-06_to_2026-06-21 | NIFTY | 29 | 25 | 1 | 0 | 55 | 54 |
| P3_primary_2025-06_to_2026-06-21 | SENSEX | 41 | 9 | 2 | 3 | 55 | 50 |
| P4_live_window_2026-06-22_to_10-22 | NIFTY | 13 | 5 | 0 | 0 | 18 | 18 |
| P4_live_window_2026-06-22_to_10-22 | SENSEX | 16 | 2 | 0 | 0 | 18 | 18 |
| P5_after_live_window | NIFTY | 1 | 1 | 0 | 2 | 4 | 2 |
| P5_after_live_window | SENSEX | 3 | 0 | 0 | 0 | 3 | 3 |

## 3. What is executable in the usable cycles
| und | cycles | opening_atm_executable | CE_wing_exact | PE_wing_exact | both_wings_exact | min_D1_windows_of_17 | min_D0_windows_of_23 |
|---|---|---|---|---|---|---|---|
| NIFTY | 155 | 100.0% | 62.6% | 83.2% | 45.8% | 17 | 21 |
| SENSEX | 119 | 100.0% | 79.8% | 80.7% | 68.9% | 17 | 22 |

Policy (fixed in advance): a bar is executable only if its volume is > 0 (zero-volume bars are carried prices); the fill is the open of the first executable bar in the decision minute and the next two; otherwise `NO_MARKET` and no price is invented. A missing exact wing is substituted by the nearest traded strike toward ATM **and flagged**; the replica must record the substitution distance.

## 4. Evidence tiers (contamination), by class
| tier | FULLY_FEASIBLE | FEASIBLE_WITH_DECLARED_SUBSTITUTION | PARTIAL | UNUSABLE | expected | usable (fully + substituted) |
|---|---|---|---|---|---|---|
| T1_never_evaluated | 4 | 1 | 0 | 2 | 7 | 5 |
| T2_previously_scored_by_related_strategies | 39 | 21 | 1 | 1 | 62 | 60 |
| T3_in_sample_of_prior_programmes | 81 | 92 | 5 | 36 | 214 | 173 |
| T4_live_window_reverse_engineering | 29 | 7 | 0 | 0 | 36 | 36 |

| Tier | Meaning |
|---|---|
| T3 in-sample of prior programmes | D0 ≤ 2025-11-17: used for configuration selection in the 4-leg backtest and as IS for the R1/R2 ladder replication |
| T2 previously scored by related strategies | 2025-11-18 → 2026-06-21: scored once by the 4-leg backtest (OOS) and by R1/R2 (OOS clean) |
| T4 live window | 2026-06-22 → 2026-10-22: reverse-engineering sample, repeatedly inspected |
| T1 never evaluated | after 2026-10-22: 7 expiries, too few for inference |

**Consequence.** No block can be called an untouched out-of-sample for a strategy that contains the rules of R1. The brief's three-period split (dev / validation / primary OOS) is retained **as a chronological partition**, but its OOS block is labelled "previously inspected by related strategies" in every table, and conclusions rest on consistency across blocks and on bounded scenarios, not on one number. This treatment is my proposal and is recorded before any replica result exists; if you prefer a different treatment (for example treating everything before 2025-06 as in-sample and refusing to quote any OOS Sharpe), say so before the freeze.

## 5. Unusable and partial cycles (all listed, none dropped silently)
| und | validation_status | eligibility | cycles |
|---|---|---|---|
| NIFTY | Missing | UNUSABLE | 2 |
| NIFTY | Partial | PARTIAL | 2 |
| NIFTY | Partial | UNUSABLE | 1 |
| SENSEX | Complete | PARTIAL | 2 |
| SENSEX | Missing | UNUSABLE | 35 |
| SENSEX | Partial | PARTIAL | 2 |
| SENSEX | Partial | UNUSABLE | 1 |

Reasons: {'validation status Missing': 37, 'status Partial; no full-chain cache': 4, 'D-1 is a special (Muhurat) session': 2, 'only 12/17 D-1 windows executable': 1, 'outage session': 1}. Special/outage sessions come from the data-validation defects D04 and D21; they are excluded, not repaired.

## 6. Known data conditions the loader must apply (REPORTED by `data_validation`, not re-derived here)
09:15–15:29 bars only (15:39 option bars after 2026-08-03; **no NIFTY spot after 15:14** on those sessions, D05) · volume 0 = no trade · drop volumes outside [0, 2^31) (23 wrap-around rows, D06) · mask the four outage sessions (D21) · no SENSEX open interest (D03) · **the existing per-cycle caches contain open, close and volume only — no high/low**, so the replica needs a new loader that also reads high and low for stop-crossing logic · lot size is inferred from the volume gcd, not supplied · option universe = ATM ± 45 around the D-2 close; contracts outside it are `NO_MARKET`.

## 7. Limits of this table
It checks availability of the instruments a scheduled ATM entry and the seed wings would need. It does **not** check the routine-wing budget strike, ladder quantities, stop-crossing bars (no high/low in the cache) or settlement; those are examined when the modules exist. A FULLY_FEASIBLE label means "the entry skeleton can be priced from traded bars", not "the replica is valid in that cycle".
