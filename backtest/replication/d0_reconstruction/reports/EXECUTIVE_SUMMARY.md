# Executive Summary — Phase 5: D0 short-sale, buy-back and replacement logic

**Bottom line:** the D0 *decision triggers* of Algo 8 were **not recovered**. What was recovered is the **timing structure** (a Clock-B minute for buy-backs, grid-A windows for scheduled sales, a 15:14 clearance, a cycle stop) and several **negative findings** that remove wrong explanations. A frozen rule set tested on a chronological holdout passes the pre-registered criterion for **one** category only (15:14 final-liquidation timing, wide interval) and fails scheduled-sale quantity (recall 0.48 vs 0.50 required), Clock-B buy-backs, replacements, price-stop buy-backs and hedge actions. Nothing was ported into the engine (Gate 7 not entered); existing engine tests (180) still pass.

## What we now know (status)
| Finding | Evidence | Status |
|---|---|---|
| A reconciled order-level event table exists for all 35 cycles (39,874 orders; 29,959 on D0). D0 analysis is possible for 33 cycles, state-dependent analysis for 30. | reconciles with the ledger (lots, all 1,674 contract nets; P&L to 0.11 %) | Established |
| Buy-backs concentrate in the **Clock-B minute** (17.3 % of lots vs 6.7 % uniform) and late in the day; most are 1 lot. Whether a tick acts is **not** predicted by a transferable rule (book-size threshold fails out of sample). | discovery 460 ticks; holdout sim 5 vs 113 lots | Timing Strongly supported; trigger Unknown |
| **Replacement is much weaker than previously reported.** The "60 % of D0 sales are replacements" was mostly chance overlap: within 60 s of a buy-back only **43 % of sold lots vs 29 % by chance** (ratio 1.5); no excess beyond 2 minutes. Above-chance replacement exists for Clock-B-minute buy-backs (+31 pts), salvage (+18) and other (+13); never for late buy-backs. When it happens: same lots (92 %), same right, usually another strike (same contract ≤ 13 %). | time-shift null, 25 discovery cycles | Association Established; trigger Unknown |
| **Off-schedule D0 sales** have no ATM-migration, spot-move or CE/PE-balance explanation, and are **not demonstrably more profitable** than scheduled ones (₹62 / ₹81 / ₹117 per lot; intervals overlap zero; sign flips under LIFO). The previous "₹469 vs ₹323 per lot" ordering does not reproduce. | discovery lineage + convention test | Rejected explanations; trigger Unknown |
| Scheduled D0 sale **quantity depends on the time slot** (R² 0.26), **not** on the book size (0.02). | 797 slot-legs | Strongly supported |
| The **cycle stop** (−₹1.44 L LTP MTM) reproduces 6/7 (discovery) and 4/4 (holdout) live stop cycles **when started from the actual carried book** — but a flatten-only control finds the same true positives (6/7 and 4/4, with one false positive in each split; V1 has none), so this mostly reflects the carried book. | replay | Supported, conditional |
| The largest unreproduced P&L stream is the **intraday buy-back of carried lots** (+₹27.5 L actual vs −₹4.3 L simulated in discovery); D0-opened sales are small and convention-dependent. | lineage FIFO/LIFO | Indicative |

## Holdout outcome (8 cycles, frozen rules, partially exposed)
Scheduled sales L2 precision 0.65 / recall 0.48; final liquidation 0.79 / 0.60 (**passes**); price-stop-like buy-backs 0.47 / 0.35; Clock-B buy-backs 0.20 / 0.01; replacement sales 0 / 0; hedge additions 0.69 / 0.20. Simulated net short book ≈ 17 lots vs 75 actual (state correlation −0.33; discovery +0.79). D0 P&L is not matched and is sensitive to intra-minute fill assumptions (+₹0.08 L vs −₹1.26 L with a one-minute latency; live +₹1.9 L).

## Integrity notes
* Rules were fitted on 25 discovery cycles, frozen with hashes and committed (`40642216`) before the holdout run; holdout event data was locked by code until then. The holdout is **not pristine** (earlier research scored the same TEST cycles; Phase-4 pooled descriptive tables included them).
* A start-book bug in the simulator found by a unit test was fixed (addendum 1; rules unchanged); the corrected holdout re-run is **not** independent evidence; the original outputs are kept. Conclusions are identical.
* An independent reviewer audited the event table, simulator, matching and holdout discipline (`INDEPENDENT_REVIEW_D0.md`).
* A previous-phase claim was corrected ("60 % replacements"; "off-schedule sales are the profitable class").

## Benchmark
The Sharpe **2.19** remains **unverified** and **not comparable** (screenshot absent, methodology unknown; no new evidence found). See `BENCHMARK_METHODOLOGY_STATUS.md`.

## What to do next
1. **Obtain independent evidence**: a new live export (forward period) or the screenshot's source ledger; no further validation is possible inside these 35 cycles.
2. Investigate the **intraday buy-back of carried lots** as the highest-value gap, using lot-level lineage (allocation ids would resolve the ownership ambiguity; ask whether the platform can export parent/allocation ids and order timestamps with sub-second precision).
3. Treat Clock-B action and replacement as one **per-lot timer process**, not a book-level rule: model per-lot chains (earlier timer-phase work) rather than book-size thresholds.
4. Only then port validated pieces (flatten at 15:14; phase-aware cycle stop) to the engine with C++ parity.

Documents: `D0_EVENT_SEQUENCE_ANALYSIS`, `BUYBACK_AND_REPLACEMENT_ANALYSIS`, `OFF_SCHEDULE_SALE_ANALYSIS`, `CHRONOLOGICAL_HOLDOUT_REPORT`, `D0_DECISION_RULE_REGISTER`, `D0_REPLAY_METHODOLOGY`, `ACTUAL_VS_SIMULATED_COMPARISON`, `D0_PNL_ATTRIBUTION`, `ENGINE_INTEGRATION_REPORT`, `BENCHMARK_METHODOLOGY_STATUS`.
