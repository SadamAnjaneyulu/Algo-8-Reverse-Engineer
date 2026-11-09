# Algo 8 — Data Gaps and Requirements

Part of the [complete reconstruction audit](ALGO8_COMPLETE_RECONSTRUCTION_AUDIT.md) ·
[findings register](ALGO8_MASTER_FINDINGS_REGISTER.md) · [strategy specification](ALGO8_STRATEGY_SPECIFICATION.md) ·
[readiness](ALGO8_RECONSTRUCTION_READINESS.md) · [roadmap](ALGO8_RECONSTRUCTION_ROADMAP.md)

## 1. Data we already have

| Dataset | Where | Coverage | Granularity / fields | Limitations |
|---|---|---|---|---|
| Broker trade export `Trades_GKOHNP140.csv` (client GKOHNP140) | `main` ([`../Trades_GKOHNP140.csv`](../Trades_GKOHNP140.csv)) | 23 Jun – 22 Oct 2026; 41,421 fill rows; 39,874 orders; 35 cycles | 167/168 columns, no header (names inferred from Algo 7's export, which has one): fill time (epoch, 1 s), order time (minute), side, underlying, strike, CE/PE, expiry, limit and fill price, quantities, validity, status (`Filled` / `PartiallyFilled`), **col 163 order tag** (module + microsecond decision time for `h_/s_/v_/m_`), col 144 AlgoId, col 145 AlgoCategory, col 166 app key, col 154 price band | **Fills only.** No unfilled, cancelled, rejected or modified requests; no acknowledgements; body-order decision time only to the minute; no allocation/parent-strategy ids; col 4 order id reused across days (use col 163); four log gaps (10 Aug, 1 Sep, 14 Sep, 29 Sep) and three D0-only cycles |
| Supplied note `Info.txt` | `main` ([`../Info.txt`](../Info.txt)) | — | Three sentences: BTST; "carry forward SL of 4 % on positions carried forward to expiry and 1 % on the entire capital on expiry day"; capital ₹2 Cr | Wording only; denominators and scope unstated |
| Breeze 1-min index bars | lineage X `data/breeze/` (639 MB incl. options) | 170 index-days from 22 Jun 2026; 63,678 bars | OHLC | No volume (no VWAP); minute resolution |
| Breeze 1-min option candles | lineage X `data/breeze/` | 3,243 contract-days; 1,230,065 candles | OHLC, volume, OI | **Only contracts Algo 8 traded**, not the full chain; SENSEX OI is zero; no bid/ask; minute resolution; missing minutes where no trade |
| Derived research outputs | lineage X `research/outputs/` (committed); lineage Y `analysis/_cache/` (699 MB, git-ignored, local) and `analysis/exit_engine/results/` (committed) | — | Parent ledgers, books, panels, model outputs | `_cache` exists only in this container; regenerable from the scripts |
| Algo 7 report and dump | user uploads in this session (`ALGO7_FINAL_REPORT.pdf`, `Algo_7_Dump.xlsx`) | 13 Apr – 15 Sep 2026; 30,192 fills; client PCHNA531 | Same 168-column export **with a header** | **Not in the repository**; different strategy (supporting evidence for platform/column semantics only) |
| PR #1 Actions artifacts | GitHub Actions run 41223605040 | — | dataset, action/quantity/replay folds, `algo8-research-report` | **`algo8-research-report` reviewed 9 Nov** (0 / 20 tasks at 75 %; replay abstains); artifacts expire 30 Nov 2026 — download them before then if the fold CSVs are needed |
| Prior backtest screenshot | referenced in lineage X docs | 3 Mar 2025 – 27 May 2026 | Return 47.22 %, CAGR 36.88 %, Sharpe 2.19 | Different period; not reproduced; no trades for it |
| 2025–26 Breeze history (for the locked alpha OOS) | **not yet fetched** (user said they would pull it) | — | — | Needed only for the economic OOS test, not for reconstruction |

## 2. Data we are missing — and the unknown each item would resolve

Only items tied to a specific unknown are listed. Register IDs in brackets.

| Missing data | Unknown it would resolve | How it resolves it | Priority |
|---|---|---|---|
| **Original strategy source code or configuration file** | Everything marked [U]: stop multiple and reference (EXT-02/05), cycle-stop constant and origin (RSK-01), 4 % / 1 % semantics (RSK-02/03), ladder sizes and their variation (SIZ-03), extra-sale and Clock-B conditions (ENT-04, MGT-03), configuration-change dates (HDG-01, MGT-02) | Direct reading | Highest (would make most research unnecessary) |
| **Decision / signal logs** (what the algo evaluated and why, with timestamps) | Stop trigger reference and timing; extra-sale trigger; Clock-B act/no-act and contract choice; reduction triggers (MGT-05) | Labels with the cause attached, instead of inferring causes from fills | Highest |
| **Per-order allocation / parent-strategy id** | Which allocation a buy-back closes; per-allocation stop level; D0 stop scope for carried vs fresh lots (EXT-05); re-entry linkage (MGT-07); contract selection (MGT-04/06) | Removes the fungible-lot ambiguity that limits every lot-level test | High |
| **Order submission / acknowledgement / modification / cancellation / rejection timestamps** | Body-order decision times (EXT-11); pending-order handling after closure; rapid reversal motifs vs duplicate submissions (MGT-08); partial-fill retry logic | Exact decision times and the full request stream, including unfilled requests | High |
| **Tick-level option quotes (LTP, bid/ask) for held contracts** | Exact stop trigger price (minute high vs tick LTP); intrabar ambiguity in first-passage tests; exact cycle-stop constant (minute closes cannot see it: RSK-01) | Lets the trigger be timed to the second instead of bracketed by one minute | High (tick data is a market-data purchase, not privileged) |
| **Portfolio NAV, capital allocation and margin records** | Sizing formula and exposure ceiling (SIZ-03, SIZ-05); lump size (SIZ-04); denominators of the 4 % and 1 % rules (RSK-02/03) | Tests whether sizes and limits are functions of margin or capital | Medium–high |
| **Original risk-control settings** | 4 % carry SL, 1 % expiry-day stop, cycle-stop constant | Direct | Medium–high |
| **Full option chain (all strikes)** | Exact later strike selector (STK-02), hedge selector (HDG-02), liquidity filters | Removes the traded-only universe bias; enables exact selector tests | Medium |
| **Platform Greeks / IV inputs (if the platform computes them)** | Whether Clock-B/side selection uses Greeks (MGT-04/06) | Tests against the values the algo actually saw | Medium |
| **Broker / platform risk events** (AlgoId 152432 logs) | Separating platform liquidations from strategy decisions (RSK-04) | Labels platform actions | Medium |
| **Broker position snapshots / settlement records** | Residual wings and positions at expiry; the zero-initial-inventory assumption (DAT-08/09) | Verifies inventory reconstruction end to end | Medium |
| **Certified eligible-session calendar incl. no-trade days** | Entry eligibility filter (STR-01, ENT-05) | Provides negatives (sessions where it chose not to trade) | Medium |
| **More months of Algo 8 trade exports** (before June / after October 2026) | Whether rules hold out of sample (e.g. the 1.6–1.7× D-1 band, the 17 windows); configuration change history; more cycle stops (only 12 observed) | Independent validation sample for the decision rules | High for validation; it is also the only route to genuine OOS evidence |

## 3. Research that can still be done with existing data

Ordered by expected information value about the **original** strategy. None was run during the audit. **Completed since the
first audit:** PR #1 artifact review, the stop-definition reconciliation and the ladder-window reconciliation (audit §7A).

| # | Experiment | Gap addressed | Why it is informative | Expected information value |
|---|---|---|---|---|
| 1 | **Reconcile the exact per-lot stop reference using the recovered per-order quotes** (limit ÷ 1.15 / ÷ 0.85 as a sparse tick feed), comparing own-entry, cheapest-entry and per-allocation references | EXT-02, REC-01/02 | The one stop rule that is known to exist; removes most intrabar ambiguity without new data | High |
| 2 | **Reconstruct allocation ownership and per-allocation state** (slot / clock chains; does the stopped lot belong to the slot whose own entry crossed?) | EXT-03, EXT-05, MGT-04 | The one-lot-at-a-time stop implies per-allocation logic; this tests it directly | High |
| 3 | **Investigate Clock-B selection and act / no-act** with allocation-age and inventory-shape features | MGT-03 | Act / no-act AUC 0.78; contract choice hit@1 0.56–0.66 vs 0.35–0.41 random | Medium–high |
| 4 | **Reconcile extra-sale triggers across both lineages** (one definition scored by both on the same later cycles) | ENT-04, REC-03 | Y's timer ranking and X's 13 / 93 are different targets | Medium |
| 5 | **Obtain / review original configuration, risk settings and decision logs** (not an experiment: a data request) | all [U] | Would resolve most unknowns directly | Highest if obtainable |
| 6 | **Obtain additional historical Algo 8 trade data** | validation | The only genuinely unseen test | High for validation |
| 7 | Locate or rewrite the P4 cache writer and re-run `p4_ml.py` with the correct key | STK-03 | Verifies or retracts the 68.5 % figure | Low–medium |

No general-purpose ML tuning is recommended: every model family tried fails at ≥ 0.75 / 0.75 and the limiting factor is
missing information, not model capacity.

The locked alpha OOS test (`analysis/oos_run.py`, frozen in `alpha_freeze/`) needs the 2025–26 history and lot sizes.
It tests an **economic** hypothesis (H1), not a reconstruction of Algo 8's rules.
