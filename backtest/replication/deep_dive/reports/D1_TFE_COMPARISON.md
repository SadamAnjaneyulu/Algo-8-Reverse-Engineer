# D-1: per-event teacher-forced (TF-E) vs free-running (F), under `one_lot_v2`

*2026-11-25. Diagnostic only (spec v1.1 section 6): TF-E is never a primary score, a closure gate, or evidence the strategy is reproduced. Evidence label for every number: **historical reproduction** on the same 32 development cycles. F = the accepted `one_lot_v2` F run. Pre-registration: `D1_TFE_PLAN.md` (with two dated addenda). No parameter, threshold or class map was changed. Everything uncommitted.*

## Result in one paragraph
**Correcting the portfolio state after every real order does not improve F; it lowers the order-level score in all 32 cycles, and the reasons are mostly artefacts of the reset itself, not strategy errors.** What the data do support is narrower: **the order classes that do not read the book (body sells 4,408 and opening wings 186 real orders, 46% of the log) are identical in F and TF-E, so their misses are decision/trigger errors, not book divergence.** For the classes that do read the book (wing buys/sells, buy-backs, lump), state correction recovers at most about 10% of F's misses (about 30% if two fill-derived memory inputs are also forced), and that figure is unreliable in one direction (below).

## The four questions
| Question | Answer (60 s tolerance, keys; first-decision reading unless stated) |
|---|---|
| **1. How much does F improve with the state corrected?** | It does not. Pooled F1: **F 0.739** → TF-E 0.597 (all orders, as pre-registered) / **0.645** (first decisions) / 0.603 / 0.649 (memory variant). F1 is lower than F in **32 of 32** cycles (median change -0.13 all-orders, -0.10 first-decision). At the **exact-second tier only** TF-E is slightly better (keys F1 0.213 → 0.230; memory 0.260). |
| **2. Which mismatches disappear?** | Few. Of F's **2,911** unmatched real orders: **213 recovered** (7.3%): wing sells 81, buy-backs 38, wing buys 35, body sells 34, lump 8. Memory variant: **552** (19.0%): wing buys 255, wing sells 171, body sells 54, buy-backs 42, lump 9. |
| **3. Which persist with the correct state?** | **2,698** (92.7%; memory variant 2,359 = 81.0%): body sells **1,145** of 1,179 missed (97%), buy-backs 637 of 675, wing buys 501 of 536 (memory 281), wing sells 273 of 354 (memory 183), lump 45 of 53, opening wings 4. The late session barely moves: 15:00 block F1 F 0.369 → 0.342 (memory 0.412); 15:30 block 0.180 → 0.202 (0.319). |
| **4. Accumulated book divergence vs wrong decisions?** | **Mostly decisions, for what can be measured.** (a) Classes independent of the book: no change at all (*Observed*; the engine's sell rules do not read the book). (b) Book-dependent classes: recovered 162 of 1,618 misses (10.0%; memory 477 = 29.5%). (c) Within a TF-E epoch the simulator wanders little from the real book (5,705 resets: median normalised L1 0, mean 0.027, 67% with short and long lots equal); F's books at matched events differ much more (median 0.51), yet that divergence produces few extra wrong decisions. These two divergence measures are not like for like (F accumulates from the open, TF-E resets). *Inferred.* |

## Why TF-E scores lower than F (found, not tuned)
1. **Pre-emption of reactive orders (the largest effect).** Wing buys are reactions to body orders. Under per-event forcing the real system's own wing buy is already in the book when the simulator's reaction would fire, so the simulator sees no gap and stays silent. Of the **1,165 wing buys F matched but TF-E lost**, **96%** had the simulator firing *after* the real order in F (median +1 s), against 29% among wing buys matched in both. Simulator wing buys fall 3,270 → 2,046. This is a property of forcing the outcome of the same reaction chain, not a worse decision. *Observed.*
2. **Re-decision loop (pre-registered definition).** Where the simulator buys back a lot the real system kept, the next reconciliation restores it and the same rule fires again: **2,649 of 3,140** simulated buy-backs are repeats, **1,227 buy-backs plus 20 other orders were rejected** by the per-minute decision cap (NIFTY 28 Jul 433, NIFTY 29 Sep 425, SENSEX 9 Jul 177, 16 Jul 130, 13 Aug 62, NIFTY 18 Aug 18, 1 Sep 2). Repeats also inflate matches by chance: **81%** of the matched buy-back orders in the all-orders reading are repeats. So buy-back numbers in TF-E are not usable in either reading (all orders: inflated; first decisions: strict, no repeat credit).
3. **Cap collateral:** the 20 non-buy-back rejections (wing sells 14, wing buys 3, ladder 3) are blocked by the same loop; the first-decision reading does not remove them.
**Consequence:** the "recovered" counts for pre-emptable classes are a **lower bound** of what an ideal state correction would give; the "harmed" counts (1,525, of which 1,165 wing buys) are largely this artefact and must not be read as decision damage.

## Side by side (pooled F1, cumulative tolerance)
| | F | TF-E all orders (pre-reg.) | TF-E first decisions (post hoc) | TF-E-m all | TF-E-m first |
|---|---:|---:|---:|---:|---:|
| 0 s keys | 0.213 | 0.215 | 0.230 | 0.242 | 0.260 |
| 5 s keys | 0.498 | 0.410 | 0.416 | 0.439 | 0.448 |
| 60 s keys | **0.739** | 0.597 | 0.645 | 0.603 | 0.649 |
| 60 s strike + lots exact | 0.472 | 0.373 | 0.417 | 0.402 | 0.448 |
| Simulated orders | 9,035 | 10,397 | 7,748 | 10,818 | 8,218 |
Per class F1 (60 s): body sell 0.759 → 0.756; opening wings 0.854 → 0.954 (granularity artefact of F, see the split report); wing buy 0.822 → 0.570; wing sell 0.497 → 0.471 (memory 0.561); lump 0.328 → 0.401. Full tables: `outputs/scoring/tfe_comparison/`.

## What is supported / suspicious / unknown
* **Supported (Observed):** body-sell and opening-wing misses are not book-driven; the pre-emption, re-decision and cap effects exist as described; at the exact-second tier TF-E scores above F (keys F1 0.213 vs 0.230, memory 0.260), i.e. state-correct decisions are slightly better timed.
* **Inferred:** most of F's real-order misses are decision-rule, timing or input problems (late session, solo ladder, burst, buy-back rule), not accumulated state.
* **Unreliable:** any share attributed to book divergence for wing/buy-back/lump classes (pre-emption and repeats distort it).
* **Unknown:** how much of the book-dependent misses a TF-E that holds reactive real orders back from the book until the simulator has had its chance would recover; that needs a new variant (below).
* **Not evidence of reproduction:** TF-E receives real information throughout; here it still scores below F.

## Decisions for you (no run depends on them yet)
1. **Which TF-E reading goes in the register?** (A) pre-registered all-orders (inflated repeats), (B) first decisions (post hoc, strict), (C) neither as a score, keep both only as diagnostics. I recommend **C with B as the reference table**.
2. **Do you want a corrected TF-E variant** that applies real *reactive* orders (wing module) to the book only after the simulator's own reaction window, or forces module by module (body, wing, lump separately)? It adds one design choice (the window or the module split), so I have not run it. It is the cleanest route to a real answer for question 4 on book-dependent classes.
3. Otherwise the next planned step is the mismatch classes in F (late session, solo ladder, buy-back rule, wing sells), where TF-E already says the misses are decisions.

## Verification (executed)
`tests/test_tfe.py` (14): rebuilt real book equals the cumulative real position after all 9,915 orders; empty log equals F; oracle (the simulator's own fills as the log change nothing, drift 0); reset replaces the book including entry prices; no use of real orders at or after the decision second; window violations raise; memory variant differs only by the two named inputs; re-decision flag (6 cases). Mutation-checked: removing the reset, moving the reset before the step, dropping the memory input, disabling the flag, removing the real-lot cap, and removing the own-buy-back restriction are each caught. `freeze_v1` replay still equals the saved baseline exactly; the `one_lot_v2` replay is unchanged by the decision-ID refactor (`split_comparison/freeze_integrity.json`).

## Deviation record (nothing silently rewritten)
Addendum 1 (drift measured before the decision, found by the oracle test, before any real-data run); Addendum 2 (re-decision flag and first-decision reading, written after I read the first run; labelled post hoc). The first execution's log is kept at `outputs/scoring/d1_TFE_v2_onelot/run_prereg_definition_first_execution.log`.

## Files
`src/bl_tfe.py`, `src/bl_tfe_compare.py`, `tests/test_tfe.py`; runs `outputs/scoring/{d1_TFE_v2_onelot, d1_TFE_first_v2_onelot, d1_TFE_m_v2_onelot, d1_TFE_m_first_v2_onelot}`; tables `outputs/scoring/tfe_comparison/`; F and its baselines untouched.
