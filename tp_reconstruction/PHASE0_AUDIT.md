# TP-01 · Phase 0: repository and research audit (written before any implementation)

## 1. Repository state
| Item | Value |
|---|---|
| Working branch | `research/tp01-position-reconstruction`, created from `origin/research/algo8-skeleton-tp` (`80baac08`) |
| Why this base | It is the tip of the Stage 1 chain (PR #1 → #2 → #3 → #4 → #5 → #6 → #7 → #8) and holds the corrected session-aware ledger (`risk_rule_validation/rr_common.py`), the PR #5 allocation work and the final dependency audit. `research/stage2-independent-alpha` (PR #9) is the alpha branch and is **not** used. No branch ambiguity |
| Working tree | Clean (one untracked `stage2_alpha_research/` folder of caches left by the other branch; not touched, not committed) |
| Open PRs | #1–#9, all drafts, none merged. TP-01 does not modify PR #8 or PR #9 |

## 2. Canonical raw data (re-verified from the file, not from earlier reports)
| Fact | Verified value |
|---|---|
| File | `Trades_GKOHNP140.csv`, 167 columns, no header |
| Fill rows | **41,421** |
| Parent orders (col 163 `UniqueOrderIdentifier`) | **39,874** (col 4 order number: 37,258 unique, reused across days, therefore not an order identity) |
| Sessions | 65 trading dates, 2026-06-23 to 2026-10-22; fills 09:15:00–15:39:27 IST |
| Contracts (underlying, expiry, type, strike) | 1,674 (NIFTY on NSEFO 19,904 fills; SENSEX on BSEFO 21,517) |
| Order of the file | Chronological by execution second (0 inversions), so file order is a valid tie-break |
| Fill status | 39,871 `Filled` + 1,550 `PartiallyFilled`; a partial fill is its own row. 38,815 orders have 1 fill, 1,059 have 2–15 |
| Quantity | Column 33 is in **units** (all multiples of 65 NIFTY / 20 SENSEX; always > 0). P&L in rupees = price points × units; **no lot multiplier is applied** |
| Prices | **Column 137 is the per-fill price** (100 % on the 0.05 tick grid). **Column 18 is the running order-average price** repeated on each fill row (equal to the order VWAP on the last fill; differs from column 137 in 431 rows of multi-fill orders). Per-fill accounting uses column 137 |
| Time | Column 161 execution epoch (whole seconds), IST = +5:30. Column 23 is the order-entry minute and is not used as execution time |
| Identifier consistency | Description text (col 32) agrees with underlying, type, strike and expiry columns in 100 % of rows |
| Duplicates | 0 duplicate rows; 0 duplicates on (order, trade id, time, qty, price, side, contract) |
| Trade id (col 28) | **Not unique** (41,399 values for 41,421 rows; one id is shared by two different orders on one date). Used as a reference, never as a key |
| Exchange token (col 143) | 1,666 tokens for 1,674 contracts: tokens are **reused across expiries**, so a token is not an instrument identity. Identity = (underlying, expiry, type, strike) |
| Order quantity vs fills | Σ fill quantity = order quantity for 39,871 of 39,874 orders; 3 `h_` orders were only partly filled (remainder not executed) |
| Charges | **No brokerage, tax or charge field exists** in the raw file. Net P&L cannot be computed; only gross |
| Equal-timestamp ties | 4,464 contract-seconds hold ≥ 2 fills; only **56** mix buys and sells; under the three tie orderings 6 fills change their closing quantity (150 units of 1,377,065) |
| Reversals | 23 fills cross zero inventory; 81 of 1,674 contracts end the export with non-zero net inventory |

## 3. Existing research reused (read-only) and independently re-validated
| Component | Use in TP-01 | Independent check |
|---|---|---|
| `analysis/load.py` column map | Cross-check only; TP-01 has its own loader reading the raw file with the map in `config.yaml` | Loader equality test (`test_event_ledger.py`) |
| `risk_rule_validation/rr_common.py::ledger` (session-aware unit-lot ledger) | Cross-check of lot counts (opened / closed / remaining) | Not an input: it is order-level (VWAP, decision-time ordering), TP-01 is fill-level (per-fill price, execution time) |
| PR #5 (`analysis/allocation`) | Establishes that **allocation ownership is not identified** (3.5 % of replacement pairs) | Motivates the FIFO / LIFO / average-cost sensitivity; no PR #5 output is an input |
| PR #8 final audit | Module-tag meaning (`h_` wing, `s_` stop, `v_` lump, `m_` manual, numeric body); stop overshoot facts | Tag decoding re-derived from column 163 |
| Raw Breeze index / option 1-minute bars | Market-context features only (Phase 5D, 6) | Raw files only; no PR #3 / PR #6 cache is read |
| Stage 2 / PR #9 | **Not used** (alpha branch) | — |

Nothing from `analysis/_cache`, PR #3 panels or model outputs is an input to the ledger or the matching.

## 4. Method decisions made before implementation (no result seen)
1. **Instrument identity:** (underlying, expiry, option type, strike). Never merged across expiries or strikes.
2. **Role of a fill** is decided only by the current net inventory of its contract. A fill against the inventory closes `min(qty, |inventory|)`; any excess opens the opposite direction (a reversal).
3. **Event order:** (execution second, file row). Alternatives for ties inside one contract-second: sells first, buys first. A closing fill whose closing quantity changes between the three orderings is labelled UNRESOLVED.
4. **Matching:** FIFO, LIFO and average cost, all run on the same fills; none is called the truth. Average cost uses the running quantity-weighted average of the open inventory; reversals open at the reversing fill price.
5. **Position (episode):** a maximal run of non-zero inventory in one direction in one contract. Zero or a reversal ends it.
6. **Remaining inventory at the end:** `EXPIRED_UNCLOSED` when the contract expiry date is on or before the last data date (no settlement fill exists, settlement price is not in the data, so no P&L is invented); `OPEN_AT_END_OF_DATA` otherwise.
7. **Labels per closed quantity:** PROFIT / LOSS if |gross P&L per unit| exceeds the tolerance, BREAKEVEN otherwise, UNRESOLVED if the quantity cannot be matched or its role depends on an unresolvable tie. **Tolerance = 0.025 points per unit (half the 0.05 tick), fixed in `config.yaml` before any classification.**
8. **Stability across methods is judged on the closing fill** (the matched pieces differ between methods, the closing fill does not): STABLE if all three methods give the same label, otherwise CONVENTION_SENSITIVE.
9. **Gross P&L only;** net P&L is not available (no charge fields).
10. **No threshold is searched.** Phase 5 is descriptive; Phase 6 evaluates a handful of post-hoc candidate patterns once each and labels them hypotheses.
