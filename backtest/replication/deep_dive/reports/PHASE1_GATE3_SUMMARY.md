# Phase 1, Gate 3 summary: D-1 buy-back, wing and lump reconstruction

*2026-11-25. All sub-gates run to their preregistered stop rules on existing data; no correction met its criteria; nothing added to the baseline. Everything uncommitted.*

## Status: **CONDITIONAL**
| Sub-gate | Result | Key numbers |
|---|---|---|
| 3a buy-back stop | CONDITIONAL | 54.5% of missing buy-backs and 17.2% of extra ones are **upstream position differences**; the rest is count/supply and an independent trigger gap (163 missing orders with the real lot well below 1.6x); no stop mechanism supported (K1-K5); latency K6 rejected |
| 3b wing release | CONDITIONAL | outermost 0.411 / cheapest 0.413 vs chance 0.262; nothing supported; quantity and timing already Confirmed |
| 3c lump | CONDITIONAL | side 0.93, size not explained by position (constant as good as the engine form) |

## What the gate establishes
* **Inherited versus separate (user condition met):** wing and buy-back errors are in large part inherited from upstream position and timing (Gate 2 residual); buy-back stop, wing choice and lump size have **separate** components that are not recoverable here. No buy-back, wing or lump rule was changed to compensate for missing body sells.
* **Not changed:** the engine rules for buy-backs, wings and the lump; all baselines (B0, B1).
* **Candidate conventions** (not adopted): `stop_latency_s` (rejected), plus the Gate 2 candidates V01, C1 (C1 is a diagnostic input convention only, per the user's decision).

## Carried forward
Buy-back stop **Decoded** (part) / independent gap **Unresolved**; wing release **Partial**; lump size **Unresolved**; the D-1 engine remains **B1**.

## Addendum (Phase 1 final loop, 2026-11-25): cycle stop
The cycle-stop rule is confirmed on the real book in D-1 and D0 (12/12 stops, 0 false alarms) with the constant corrected from 1.20 to the interval (1.2177, 1.2902] lakh (frozen 1.25): the earlier D0-only test missed two D-1 false alarms. A free-running D-1 stop in the engine was rejected (4 false stops). `PHASE1_LOOP2_RESULT.md` section 2.
