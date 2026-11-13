# TP-02 · Phase 0: evidence base and pre-registered methodology

Written and committed **before** any mechanism flag or hypothesis was computed. Definitions are fixed in [`tp02/config.yaml`](tp02/config.yaml).

## 1. Repository and branch state
| Item | Value |
|---|---|
| Branch | `research/tp02-exit-mechanism-attribution`, created from TP-01 commit `086b86125345eaeba427164f3f54f3543e72269a` |
| TP-01 branch / PR | `research/tp01-position-reconstruction`, PR #10 (draft, open); its head is still `086b8612`, so it is the correct starting point |
| Stage 1 base | `research/algo8-skeleton-tp` `80baac08` (PR #8, untouched) |
| Alpha branch | `research/stage2-independent-alpha` (PR #9, untouched, not an ancestor; no Stage 2 file is on this branch) |
| Working tree | clean apart from an untracked `stage2_alpha_research/` folder of caches left by the alpha branch (not committed) |
| Rules kept | PR #10, #8, #9 not modified; nothing merged; TP-01 outputs and raw data not overwritten (TP-02 writes only under `tp_reconstruction/tp02/` and two new top-level documents) |

## 2. Source datasets (all read-only)
| Dataset | Content | Rows |
|---|---|---|
| `Trades_GKOHNP140.csv` | raw broker fills; column 137 per-fill price, column 18 running order average, column 163 parent order, column 33 units, column 161 execution epoch (whole seconds), column 23 order-entry minute, column 4 order number, column 166 app key | 41,421 |
| `data/fill_event_ledger.parquet` | normalised fills, module tag, tie-group flags, quality flags | 41,421 |
| `data/fill_roles.parquet` | per fill and convention: inventory before / after, close and open quantity, reference price after the fill | 124,263 (3 × 41,421) |
| `data/exit_events.parquet`, `exit_event_consensus.parquet` | closing fills (17,760) by convention; consensus label and stability | 53,280 / 17,760 |
| `data/position_episodes.parquet` | inventory episodes | 8,001 (3 × 2,667) |
| `data/short_exposure_panel.parquet` | contract-minute panel of short inventory with the previous-bar mark and the decay ratio under each convention | 209,131 |
| Raw Breeze 1-minute bars (`ALGO8_MARKET_DIR`) | index and option bars for the contracts Algo 8 traded (not a full chain) | — |
| TP-01 analysis CSVs | clock clusters, hazard by decay, behaviour summary | — |

## 3. Verified findings reused (not re-derived)
TP-01: 2,667 episodes, 17,760 closing fills, labels stable for 86.5 % of closed units, no fixed decay level, stop-like hazard peak near 160–170 % of the reference, clock closing minutes 09:15 / 14:29 / 14:44 / 14:58 / 14:59 / 15:14 / 15:19, 91 % partial and 90 % one-lot short closings.
Stage 1: cycle stops are executed by the `s_` module (12 cycles); stop orders overshoot (RSK-12); the per-lot stop is **not** tagged (body orders), so it can only be inferred from price (≈ 1.6–1.7×, unresolved constant); order numbers are comparable only inside a number block (DAT-12).

## 4. Data limits and timestamp ambiguities (binding)
1. **Three different times.** *Decision time* is exact only for tagged orders (`h_`, `s_`, `v_`, `m_`: the tag holds DDHHMMSSffffff UTC); for body (`num`) orders it is unavailable and only bounded (order-entry minute ≤ decision ≤ first fill). *Order-entry time* is stamped to the minute. *Fill time* is whole seconds. No decision time is invented.
2. **Equal-second ordering.** Fills in one contract and second are ordered by file row; 56 buy/sell groups (6 fills) change role with the ordering; they are excluded from the clean population.
3. **Order sequence.** Submission order is known only inside an app-key number block (DAT-12; 0.74 % fill-time inversions). Outside a block the sequence is unknown and is reported as such.
4. **Lot ownership is unidentified.** Every attribution runs under FIFO, LIFO and average cost; stable and convention-sensitive closings are kept apart.
5. **No settlement, no charges, no complete option chain, no logs.** The market data cover only contracts Algo 8 traded; stale closing minutes of the index (DAT-15, alpha branch) are excluded from market-context work.
6. **In-sample.** All 65 sessions were inspected before. Nothing here is externally validated.

## 5. Mechanism taxonomy: evidence flags, not forced labels
Each closing fill gets **non-exclusive evidence flags**; `candidate_mechanism` is then derived: one flag → that family; several unrelated flags → `MULTIPLE_POSSIBLE_MECHANISMS`; none → `UNEXPLAINED`; ordering-ambiguous or missing data → `UNRESOLVED` / `INSUFFICIENT_EVIDENCE`. Families A–G of the assignment map to flags as follows (operational definitions in `config.yaml`).

| Family | Flag | Operational definition |
|---|---|---|
| A stop | `STOP_CONFIRMED` | module `s_` |
| A stop | `STOP_POSSIBLE` | not confirmed and any of: inside the execution-time window of a cycle stop (same underlying and expiry, 60 s before the first to 300 s after the last `s_` fill); the contract mark reached ≥ 1.25× the reference entry (any convention) in the previous 15 completed minutes; exit price ≥ 1.25× the reference |
| A stop | `STOP_NOT_EVIDENCED` | otherwise. **Not** proof that no stop occurred (no decision logs) |
| B clock | `CLOCK` | execution minute is one of **all** registered TP-01 clock clusters (7 minutes) |
| C expiry | `EXPIRY_MGMT` | expiry day and execution in LATE / FINAL / POST (14:30 onward); day type (`CARRY_DAY` vs `EXPIRY_DAY`) and phase are reported for every closing |
| D replacement | `REPLACEMENT` | an opening short fill of a different parent order, same underlying and **same right**, within 60 s after the closing fill; relation (same contract / other strike / opposite right), Δt, quantity ratio and, inside one number block, whether the opening order was submitted after the closing order are recorded; association is compared with a time-shifted null |
| E wing | `WING_MODULE` / `WING_LINKED` | `h_` closing / a wing closing in the same underlying and right within ±10 s of a body closing |
| F body | `module == num` | the central population |
| G other | `m_`, unresolved | kept separate |
| (H4) basket | `BASKET` | ≥ 2 other contracts closed in the same underlying within ±5 s. **Analysed, not used to remove events from the unexplained population** (it is nearly saturated) |

Populations: **Pop 1** stable-PROFIT short closings (convention-sensitive ones kept as a subgroup); **Pop 2** stop-related (`STOP_CONFIRMED` or `STOP_POSSIBLE`); **Pop 3** clean profitable non-stop: Pop 1 ∧ `num` ∧ `STOP_NOT_EVIDENCED` ∧ not order-ambiguous ∧ no data-quality flag; **Pop 4** unexplained body: Pop 3 ∧ no `CLOCK`, `EXPIRY_MGMT`, `REPLACEMENT` or `WING_LINKED` flag. The flags are deliberately generous so that Pop 4 is conservative: it is the set where a take-profit remains possible, not a set proven to be take-profits.

## 6. Event timeline (Phase 2)
For every closing fill: previous fill and order, own order and fill, next closing and next opening events by relation, other activity in the same underlying and in the other right, within 5 s / 30 s / 60 s / 120 s / 300 s; separate decision, order-entry and fill timestamps (decision marked unavailable for body orders); reference price and decay ratio under each convention; stable or convention-sensitive classification.

## 7. Hypotheses, tests and verdict rubric (registered)
| # | Hypothesis | Test on Pop 3 / Pop 4 (and the exposure panel) |
|---|---|---|
| H1 | fixed premium-decay take-profit | decay-bin cluster rule (5-point bins, ≥ 30 events, ≥ 3× neighbours) under each convention; absolute premium drop and profit per unit / lot repetition; closing hazard by decay bin standardised for day type and hour. No threshold sweep |
| H2 | scheduled profit harvesting | second-of-minute, minute-of-hour and holding-time-modulo-15-minute concentration against a uniform and a time-shift null; expiry vs carry days; same schedule across contracts |
| H3 | position-level profit reduction | fraction of the position closed, closings per episode, time to the next closing, re-add within 300 s against a null |
| H4 | basket / portfolio management | simultaneous multi-contract closings, both rights, concurrent loss legs, cycle mark-to-market (average-cost realised plus marks) at the minute before the closing and the hazard by mark-to-market bin |
| H5 | market-state exit | event minutes against exposed-but-not-closed minutes, AUC within day-type × hour strata, completed bars only, cycle-clustered bootstrap |
| H6 | replacement-related realisation | sequence classification (same contract, other strike, opposite right), quantity relation, strike migration relative to ATM, whether profitable closings with a replacement differ from those without |

Verdicts use the rubric in `config.yaml`: **SUPPORTED** (all three conventions, both underlyings, ≥ 60 % of cycles, Holm-adjusted bootstrap p < 0.05, ≥ 100 events), **PARTIAL**, **NOT_SUPPORTED** (controlled ratio within 0.8–1.25 or opposite sign), **INCONCLUSIVE** (< 100 events or < 10 cycles). Uncertainty: expiry-cycle bootstrap (1,000 resamples, seed fixed); Holm correction over the registered primary tests. Hazard ratios are descriptive, not causal. No ML is used.

## 8. Reuse and independence
Reused read-only: TP-01 data and `scripts/matching.py` / `tp_common.py`. New: tag-time decoding (re-implemented from the tag specification and cross-checked against Stage 1 where its cache exists), mechanism flags, timelines, hypothesis tests. Stage 1 labels are supporting context only; no TP-02 flag uses them as input.
