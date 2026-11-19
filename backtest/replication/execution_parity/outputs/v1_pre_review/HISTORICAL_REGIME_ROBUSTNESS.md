# Historical regime and mechanics robustness (Phase 5)

**Purpose.** Find brittle execution assumptions when the reconstructed engine is replayed under different expiry structures and market regimes. **This is not a performance test and not a parity test**: no original execution records exist for these periods, so nothing here can show that the original behaved this way, and no historical P&L is compared with the original. Rahul's warning is applied: the three years are **not** treated as one sample.
**Data.** 319 expected weekly expiries; eligibility register of PR #14 (criteria fixed before use). **Strict (FULLY_FEASIBLE) and substituted (FEASIBLE_WITH_DECLARED_SUBSTITUTION) cycles are kept apart below where it matters; excluded cycles are listed in §6, not dropped silently.** Code: `src/run_historical.py`, `src/make_historical_md.py`; tables `outputs/historical_regime_register.csv`, `outputs/historical_mechanics_by_cycle.csv`.

## 1. Result first
* **Hard mechanics hold in every structure:** 274/274 eligible cycles run, inventory reconciles with the fills in 274, P&L finite in 274, settlement close present in all but 0, no body lot closed more often than opened (0 violations), 0 duplicate event sequences. Look-ahead and determinism are tested in `tests/test_core_integrity.py` (passing).
* **The scheduled decisions are identical by construction in every structure (about 208 orders per cycle); what differs is the quality of the prices behind them** (§3): fills that rely on a stale last-close because the decision minute has no open price, fills on zero-volume bars, and exits that cannot execute under a strict "volume > 0" policy differ strongly between structures: fills priced from a missing open 1.70 vs 0.05 per cycle (SENSEX Tuesday-expiry segment, Jan–Aug 2025, vs NIFTY Tuesday segment), fills on zero-volume bars 2.03 vs 1.03, strict NO_MARKET exits 2.07 vs 0.90. A simulator that silently falls back to the previous close is therefore **brittle exactly where liquidity was thinnest**.
* **The same rupee cycle-stop constant is not comparable across structures** (§4): its incidence ranges from 3% to 20% of cycles depending on structure, and the lot-size assumption (2026 sizes vs inferred historical sizes) changes it further. This confirms that the constant was read at the 2026 size and must not be transported.

## 2. Expiry-calendar structures (weekday of the expected expiry; rolling mode of 5, holiday shifts ignored)
| expiry_structure | first_D0 | last_D0 | expected | eligible | fully | substituted | partial | unusable |
|---|---|---|---|---|---|---|---|---|
| NIFTY-Thursday-expiry#1 | 2023-11-02 | 2025-08-28 | 96 | 94 | 36 | 58 | 1 | 1 |
| NIFTY-Tuesday-expiry#2 | 2025-09-02 | 2026-11-17 | 64 | 61 | 35 | 26 | 1 | 2 |
| SENSEX-Friday-expiry#1 | 2023-11-03 | 2025-01-03 | 62 | 29 | 9 | 20 | 2 | 31 |
| SENSEX-Thursday-expiry#3 | 2025-09-04 | 2026-11-12 | 63 | 60 | 51 | 9 | 1 | 2 |
| SENSEX-Tuesday-expiry#2 | 2025-01-07 | 2025-08-26 | 34 | 30 | 22 | 8 | 1 | 3 |

NIFTY changed from Thursday to Tuesday expiries on 2025-09-02; SENSEX moved Friday → Tuesday (2025-01) → Thursday (2025-09). **The 35 live cycles (2026-06 to 2026-10) are NIFTY-Tuesday and SENSEX-Thursday.** A mechanics result in an older structure therefore carries different D-1/D0 weekdays, different lot sizes and different liquidity.

## 3. Execution-price mechanics by structure (eligible cycles, per cycle means unless stated)
| expiry_structure | cycles | lot_size_inferred | orders_per_cycle | fills_on_zero_volume_bar | fills_where_open_missing | strict_no_market_entries | strict_no_market_exits | leg_stops | wing_dist_steps | wing_px_ratio |
|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY-Thursday-expiry#1 | 94 | 50 | 208 | 1.41 | 0.202 | 0.309 | 1.16 | 26 | 13.5 | 0.0244 |
| NIFTY-Tuesday-expiry#2 | 61 | 65 | 208 | 1.03 | 0.0492 | 0.131 | 0.902 | 25 | 15.5 | 0.0245 |
| SENSEX-Friday-expiry#1 | 29 | 10 | 208 | 2.14 | 0.69 | 0.828 | 1.1 | 23.9 | 23 | 0.0245 |
| SENSEX-Thursday-expiry#3 | 60 | 20 | 208 | 0.917 | 0.0667 | 0.0833 | 0.867 | 26.4 | 20 | 0.0245 |
| SENSEX-Tuesday-expiry#2 | 30 | 20 | 208 | 2.03 | 1.7 | 0.3 | 2.07 | 21.9 | 22.5 | 0.0245 |

`fills_where_open_missing` = fills the permissive policy priced at the last completed close because the decision minute has no open price; `fills_on_zero_volume_bar` = fills on a bar with volume 0 (carried price, not executable under the strict policy); `strict_no_market_*` = intents that cannot be executed at all under the strict policy (an unfillable exit leaves a lot open). Neither policy is "the original"; the original's behaviour in illiquid minutes is unobserved.

## 4. Stop incidence by structure (mechanics, not performance)
| expiry_structure | cycle_stop_share_2026_lot | cycle_stop_share_inferred_lot | leg_stops_2026_lot | leg_stops_inferred_lot |
|---|---|---|---|---|
| NIFTY-Thursday-expiry#1 | 0.117 | 0.0319 | 26 | 26.7 |
| NIFTY-Tuesday-expiry#2 | 0.0328 | 0.0328 | 25 | 25 |
| SENSEX-Friday-expiry#1 | 0.103 | 0 | 23.9 | 24.8 |
| SENSEX-Thursday-expiry#3 | 0.0833 | 0.0833 | 26.4 | 26.4 |
| SENSEX-Tuesday-expiry#2 | 0.2 | 0.2 | 21.9 | 21.9 |

Lot sizes inferred per session (volume gcd): see `lot_size_inferred` above (NIFTY 50→65, SENSEX 10→20). Stop counts differ with the lot-size assumption because the rupee cycle stop is size-dependent.

## 5. Regime labels (Yahoo daily only; computed strictly before D-1)
| und | vol_regime | cycles | rv20_mean | zero_volume_fills | strict_no_market_exits | cycle_stop_share |
|---|---|---|---|---|---|---|
| NIFTY | high_vol | 49 | 0.181 | 1.37 | 1.29 | 0.143 |
| NIFTY | low_vol | 53 | 0.0831 | 1.32 | 0.925 | 0.0755 |
| NIFTY | mid_vol | 53 | 0.114 | 1.11 | 0.981 | 0.0377 |
| SENSEX | high_vol | 47 | 0.183 | 1.91 | 1.32 | 0.234 |
| SENSEX | low_vol | 41 | 0.0805 | 0.78 | 0.585 | 0.0244 |
| SENSEX | mid_vol | 31 | 0.12 | 1.81 | 1.94 | 0.0645 |

| und | trend_regime | cycles | cycle_stop_share | zero_volume_fills |
|---|---|---|---|---|
| NIFTY | downtrend | 36 | 0.111 | 1.42 |
| NIFTY | flat | 55 | 0.0909 | 1.53 |
| NIFTY | uptrend | 64 | 0.0625 | 0.953 |
| SENSEX | downtrend | 36 | 0.194 | 1.33 |
| SENSEX | flat | 40 | 0.125 | 1.6 |
| SENSEX | uptrend | 43 | 0.0465 | 1.53 |

Volatility regime also moves the mechanics: cycle-stop incidence ranges 2%–23% and zero-volume fills 0.78–1.91 per cycle across the tercile labels (confounded with the structure and the lot size). No regime-conditional conclusion about the original is drawn.

## 6. Excluded cycles and reasons
| und | eligibility | reasons | cycles |
|---|---|---|---|
| NIFTY | PARTIAL | status Partial; no full-chain cache | 2 |
| NIFTY | UNUSABLE | D-1 is a special (Muhurat) session | 1 |
| NIFTY | UNUSABLE | validation status Missing | 2 |
| SENSEX | PARTIAL | only 12/17 D-1 windows executable | 1 |
| SENSEX | PARTIAL | outage session | 1 |
| SENSEX | PARTIAL | status Partial; no full-chain cache | 2 |
| SENSEX | UNUSABLE | D-1 is a special (Muhurat) session | 1 |
| SENSEX | UNUSABLE | validation status Missing | 35 |

## 7. Brittle assumptions identified (no fix is applied here)
1. **Stale-price fills:** the permissive fill policy of the stored simulator prices unavailable-open minutes at the last close. Needs an explicit documented policy; affects ≈ 1–2 fills per cycle in thin structures.
2. **Unfillable exits:** a strict policy leaves lots open when the exit bar has no volume (≈ 1–2 per cycle): the original's behaviour is unknown (it may chase with marketable limits).
3. **Constants in rupees and units:** cycle stop in rupees at the 2026 size; ladder in lots at the inferred size. Cross-structure comparison needs a stated scaling convention (U14).
4. **Wing placement drifts with the strike grid / premium level** (median wing distance 17 strikes; ratio ≈ 0.024 by construction of the 2.45 % rule).
5. **Data conditions** the loader must apply: 09:15–15:29 bars, no NIFTY spot after 15:14 on post-2026-08-03 sessions, volume wrap-around rows, four outage sessions, SENSEX no open interest, strikes limited to ATM ± 45 around the D-2 close (REPORTED by `data_validation`).

## 8. Limits
Only D-1 and D0 sessions exist; option universe is ATM ± 45; no bid/ask; lot sizes inferred; per-cycle caches contain open/close/volume only (no high/low), so intrabar stop crossing cannot be examined; the engine used is the R1 rule set (a hypothesis, fitted on the 2026 window), so these runs test **mechanics**, not that the rules are right.
