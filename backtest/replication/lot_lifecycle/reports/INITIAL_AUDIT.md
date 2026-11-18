# Initial Source-of-Truth Audit (Phase 0)

**Result:** the branch is `engineering/position-lifecycle-basket-reconstruction` at `328cd1e1` with a clean working tree (185 commits). I read the D0 executive summary and the independent review (`d0_reconstruction/reports/`), inspected the reconstruction, matching, accounting and simulator code, and tested the ledger's identifiers. **Three facts change the plan:** (1) the ledger carries a **per-fill price** (raw column 137) that earlier phases did not use, making fill-level, exact lot accounting possible; (2) **no allocation, parent-order or strategy-basket id exists** — lot ownership will have to be represented as an ambiguity, not assumed; (3) one existing test was **failing because of my own earlier diagnostic runs** (fixed, see §6). Nothing historical was overwritten.

## 1. Repository state
| Item | Value |
|---|---|
| Branch / HEAD | `engineering/position-lifecycle-basket-reconstruction` / `328cd1e1` ("independent review findings recorded") |
| Working tree | clean |
| Tests at start | 33 pass, **1 fail** (`test_every_stored_engine_run_has_python_cpp_parity`: 400 OOS diagnostic engine runs from my D0-free *diagnostics* phase were run with `check=False`; fixed by re-running with the C++ parity check; 400/400 now `parity=True`; 34 pass) |
| Engine tests | `portfolio_engine/construction/tests`: 180 pass (unchanged, last run in the D0 phase) |

## 2. Data sources (what exists)
| Source | Content | Resolution / caveat |
|---|---|---|
| `Trades_GKOHNP140.csv` | 41,421 fills, 39,874 orders, 23 Jun–22 Oct 2026, 35 cycles (33 with D0, 30 with D-1+D0) | seconds; raw, 167 columns, **headerless** |
| Breeze 1-minute option chain + spot (pinned dataset commit `eb409730`) | ~87–91 strikes per cycle, D-1/D0 | minute bars; contracts absent when never downloaded (far wings) |
| Yahoo daily index OHLC | official close for settlement | daily |
| `Info.txt` | BTST; 4 % carry SL; 1 % expiry-day; capital ₹2 Cr | text, unverified |
| Prior research outputs | event table, lot lineage (FIFO/LIFO), snapshots, replay results | see §4 |

**Ledger identifiers (tested here):**
* **Order id:** the column-163 tag is unique per order (39,874). The numeric `oid` (col 4) is **reused across days** (DAT-02); do not key on it.
* **Trade (fill) id (col 28):** 41,399 unique of 41,421 rows. The 22 repeated ids are **different orders/contracts on different dates** (coincidental exchange ids, e.g. NIFTY CE 24000 buy 2026-06-23 vs NIFTY CE 24050 buy same day with the same id; not duplicates: 0 exact duplicate rows). A fill key must be (date, trade id, row), not the trade id alone.
* **Per-fill price (col 137 = `px137`):** verified — values are exchange ticks (all multiples of 0.05); the order VWAP computed from `px137` equals the repo's `px_fill` (running average, last row) **exactly** (max difference 0.0000 over 39,874 orders). Earlier phases used the order average, which is exact in total but hides intra-order price dispersion (e.g. one 15-lot order filled at 74.35/74.35/74.40/74.40).
* **Quantities** are always whole multiples of the lot (65 NIFTY, 20 SENSEX), so every fill splits into whole unit lots without remainder (100 %).
* **Timestamps:** whole seconds (trade time); `h_/s_/v_/m_` tags embed a microsecond UTC decision time (median −0.17 s vs the first fill). Body-order decision times are not recorded.
* **Not available:** allocation id, parent/child relation, strategy or basket id (AlgoId col 144 identifies the underlying only), order lifecycle messages, quotes/bid-ask.

## 3. Architecture of the existing research code
| Layer | Files | Responsibility |
|---|---|---|
| Ledger loading | `analysis/load.py`, `replication/common.py::live_ledger` | typed ledger, tag decoding |
| Market data | `replication/data.py`, `bt/gitdata.py`, `bt/cycles.py` | minute arrays per cycle from the pinned dataset commit |
| Decision-event table | `d0_reconstruction/build_events.py` | one row per order, per-role FIFO books, classification, features |
| Lot lineage | `build_lineage.py` / `_lifo.py` | FIFO/LIFO lot pairs, order-level prices |
| Snapshots/analyses | `build_snapshots.py`, `build_final_snapshot.py`, `b_*`, `c_*` | Clock-B ticks, 15:10 book, discovery analyses |
| Simulators | `replication/sim.py` (R1/R2 ladder), `d0_reconstruction/d0_sim.py` (D0, v1.1) | rule replay from the actual overnight book |
| Matching/evaluation | `compare_events.py`, `mismatch_report.py` | hierarchical count-based matching, fixed bins |
| Engine | `portfolio_engine/construction` (Python + C++) | plugin engine; **no D0 rule is ported** |

## 4. Reports and results with known reliability problems (preserved, not edited)
| Item | Problem | Source |
|---|---|---|
| R1 pre-fix results (`results/v1_lookahead_biased/`) | D0-open look-ahead | marked DO_NOT_CITE |
| D0 simulated P&L, stop-cycle counts, hold-out portfolio-state level | defect A (lump lots kept after stop) | `INDEPENDENT_REVIEW_D0.md` A1 |
| D0 hedge-add recall | defect B (replacement sales get no wings: `floor(1×0.47)=0`) | A2 |
| Scheduled-sales holdout verdict (0.483 vs 0.548) | defect C (fixed bins) | A3 |
| Event-table "previous-minute" features at 09:15 | defect D (same-bar close at minute 0: 1,311 orders) | A4 |
| REPLACEMENT_SALE labels | coincidence contamination (~⅔ of labelled lots expected by chance) | A5 |
| D0 start book | defect E (fixed in v1.1 after the holdout was seen; addendum 1) | review §B |
| Lineage P&L | order-level price; FIFO vs LIFO flips the sign of D0-opened P&L | `D0_PNL_ATTRIBUTION.md` |

**Evidence status of the 35 cycles:** every cycle has been inspected repeatedly (discovery/holdout of the D0 phase, the earlier TEST boundary, Phase-4 pooled tables). **There is no untouched holdout in this ledger.**

## 5. Existing tests
`backtest/tests` 34 (backtest 10, diagnostics 6, replication 10, d0 8); `portfolio_engine/construction/tests` 180. Not covered (per the D0 review): matching algorithm, classification precedence, 09:15 features, passive-lot stops, wing flooring.

## 6. Findings during the audit
1. The failing parity test (above) was caused by 400 stored diagnostic engine runs without a parity check; **fixed** by re-running them with the check (no result changed).
2. The decoder `analysis/load.py` converts `status` to a string and filters fills by status text; partially filled rows ("PartiallyFilled") are included. Fill-level quantities sum exactly to the order lots.
3. `data_validation` found SENSEX open-interest unavailable and int32-wrapped volumes; I will not use OI.

## 7. Implementation plan (this milestone)
1. **Remediation (`src/`)**: corrected modules, not edits of historical ones — fill-level ledger with `px137`; start-book audit; feature timing helper (no same-bar data); one-to-one sliding-window event matching with tolerance sensitivity; simulator v2 that closes passive lots at a stop and treats replacement wings as an explicit unknown (bounds); each with a regression test that fails on the old behaviour.
2. **Lot engine (`src/lots.py`)**: unit lots with identity `tradeid/fill row/unit`; lifecycle events; three allocation conventions (FIFO, LIFO, highest-price-first) run side by side, ownership ambiguity quantified per lot; wing/hedge links only where a stated, tested association exists; settlement at the official close.
4. **Accounting**: lot P&L reconciled to fill-level cash (exact) per cycle.
5. **Carried-lot buyback analysis**, **replacement analysis**, validation labelling, charts.
6. **Independent review** with adversarial fixtures.
Python/C++ parity: none of this logic exists in C++ and none is ported; parity applies only to the unchanged engine (verified: 400/400 stored diagnostic runs plus the engine suite).
