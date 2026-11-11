# Data map (Stage 1)

Counts are from [`stage1_audit.py`](stage1_audit.py) (executed; [`results/stage1_audit.txt`](results/stage1_audit.txt)) or from the cited files.

## 1. Authoritative sources

| Dataset | Location | Key / grain | Size | Notes |
|---|---|---|---|---|
| Broker trade export | `Trades_GKOHNP140.csv` (`main`), 167 columns, no header | fill row; order = column 163 tag | 41,421 fills, 39,874 orders, 35 cycles | **Fills only**: no cancels, rejects, modifications, charges or decision logs. Column 4 is reused across days: never a key (DAT-02) |
| Index 1-min bars | `data/breeze/normalized/indices` on `research/ml-decision-engine` (170 files); cache `analysis/_cache/idx_candles.pkl` | (underlying, minute) | 85 sessions × 2 indices | Volume is zero in every row |
| Option 1-min bars | `data/breeze/normalized/options` (3,243 contract-days); cache `analysis/_cache/opt_candles.pkl` | (underlying, expiry, right, strike, minute) | 1,230,065 rows | Only D-1 and D0 of each expiry; only contracts Algo 8 traded (+ neighbours). Open interest present, not used |
| Supplied description | `Info.txt` | — | 3 sentences | ₹2 Cr capital; 4 % carry SL; 1 % on expiry day |

## 2. Export fields used

| Column | Field | Use |
|---|---|---|
| 11, 12, 14, 16, 15/32 | side, underlying, strike, right, expiry (from the description) | contract identity |
| 17 / 18 | order (limit) price / fill price | recovered quote = limit ÷ 1.15 (buy) or ÷ 0.85 (sell) |
| 33 | filled quantity | lots = quantity ÷ 65 / 20 |
| 22 | validity | DAY / IOC |
| 23 | order minute | decision lower bound for body orders |
| 161 | fill epoch (s) | fill time (IST) |
| 144 | AlgoId | 99999 NIFTY, 1E+16 SENSEX, 152432 platform risk actor, 2.18811E+15 hedge app |
| 163 | order tag | order key; module prefix; microsecond decision time for tagged orders |

## 3. Derived products (read-only reuse)

| Product | File (cache) | Built by | Grain | Size |
|---|---|---|---|---|
| Clean order table with decision-time bounds and taxonomy label | `exit_orders.pkl` | `exit_engine/common.py::orders` | order | 39,874 (body 26,253 · `h_` 12,812 · `s_` 417 · `v_` 385 · `m_` 7) |
| Closing-order ledger with pre-decision state (entries by convention, ratios, MTM, spot, Greeks) | `exit_ledger.pkl`, `exit_taxonomy.pkl` | `exit_engine/ledger.py`, `taxonomy.py` | closing order | 16,733 (11,007 short buy-backs) |
| Unit-lot ledgers, one per ownership convention | `exit_lots_{cheap,fifo,lifo}.pkl` | `exit_engine/ledger.py` | unit lot | 32,196 (15,408 short, 16,788 long); open at end of export: 110 short, 630 long |
| Market matrices per cycle (O/H/L/C, forward-filled close, ATR, RV) | `exit_mkt.pkl` | `exit_engine/common.py::markets` | cycle × contract × minute | 35 cycles |
| Contract-minute panel | `exit_panel.pkl` | `exit_engine/panel.py` | contract-minute | 205,752 |
| Allocation ledgers (slot, chain, lot) | `analysis/allocation/results/allocation_ledger_*.csv`, `allocation_lots.csv.gz` | `allocation/alloc.py` | allocation / lot | 6,545 slot, 4,355 chain short allocations |
| Replacement links and lifecycle ledger | `replacement_event_links.csv`, `position_lifecycle_ledger.csv.gz` | `allocation/replacement.py` | event / lot state | — |
| Causal OHLCV features | `ohlcv_research/_cache` (rebuilt by `build_features.py`) | PR #6 | decision minute | 42 market features + 4 clock fields |

## 4. Splits

Chronological, whole cycle, by expiry (`exit_engine/common.py::split_of`): **DEV 18 cycles (expiry ≤ 20 Aug 2026),
VAL 8 (≤ 22 Sep), TEST 9 (≥ 23 Sep)**. 32 of 35 cycles have a D-1 session in the export; 3 are D0-only
([`results/stage1_cycles.csv`](results/stage1_cycles.csv)). TEST is contaminated for constants derived on all 35 cycles.

## 5. Short vs long separation

| Population | Rule | Unit lots (cheapest-first) |
|---|---|---:|
| Short options opened by the body (numeric tag) | sign −1, entry module body | 14,744 closed |
| Short lots opened by non-body modules | sign −1, entry module `s_` 244 / `h_` 230 / `v_` 80 | 554 closed |
| Long options (wings, seed wings, lump) | sign +1 | 16,788 |

Shorts are positions where the lot book is net short; a non-body module can "open" a short when it sells more of a
contract than the book holds long. These 554 lots are kept as a separate population (question Q6).

## 6. Market-data limits that bind the skeleton and the TP study

* One-minute resolution: stop and target crossings inside a minute are ambiguous; decision times of body orders are bracketed.
* Option universe = contracts Algo 8 traded: the simulator cannot price a strike Algo 8 never touched (`no_market` intents).
* D0 ATM-straddle coverage 84–91 % (worst sessions 0–6 %).
* No bid/ask: the recovered quote is the algo's own LTP; spread costs cannot be measured.
* NIFTY and SENSEX are not independent (open-to-close correlation 0.95).

## 7. Storage risk

The normalized Breeze files exist in a scratch worktree of `research/ml-decision-engine` in this container and in git on
that branch. The `analysis/_cache` pickles are not in git. If the container is lost, Stage 2 must rebuild them from that
branch (`run_all.py`).
