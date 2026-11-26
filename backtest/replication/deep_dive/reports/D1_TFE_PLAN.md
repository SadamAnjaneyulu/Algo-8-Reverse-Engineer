# D-1 per-event teacher-forced run (TF-E): pre-registration

*Written 2026-11-25 **before** any TF-E run. Scoring spec v1.1 (frozen). Diagnostic only: TF-E is **never** a primary reconstruction score, a closure gate, or evidence that the strategy is reproduced (spec section 6). No P&L. No tuning. Everything uncommitted.*

## Questions (from the review)
1. How much does F improve when the portfolio state is corrected at every real event?
2. Which mismatches disappear under TF-E?
3. Which mismatches persist even with the correct portfolio state?
4. How much of F's error is accumulated book divergence versus incorrect strategy decisions?

**F reference = the accepted `one_lot_v2` F run** (`outputs/scoring/d1_F_v2_onelot`). The `freeze_v1` baseline (`d1_F`) stays as the archived pre-convention run and is not part of this comparison.

## Definition (frozen before running)
* **Simulator:** the unchanged engine (`d1_algo`, `config_for(und, d1)` with `order_split='one_lot_v2'`), second by second, as in F. No parameter is changed.
* **Real book:** rebuilt from the real log in log order by order-log role: `open_short` adds a short lot (entry price = the order's average fill price, minute = minute of its first fill); `cover_short` removes shorts (the engine's own cheapest-entry-first convention, because the log does not say which lot); `open_long` adds a wing long (`v_` module: lump); `close_long` reduces wing longs, then lump longs; any excess beyond holdings becomes a short lot (net position stays exact). **Validated before use:** this book equals the cumulative real signed position per contract after every one of the 9,915 orders (verified in `tests/test_tfe.py`; the two orders where the log's `close_long` exceeds holdings are the `s_` ones on NIFTY 1 Sep).
* **Reconciliation:** after the simulator's step at second *t*, every real order with first fill at *t* is applied to the real book, then the **simulator's portfolio book is replaced by the real book** (shorts with entry prices, wings, lump). The simulator's own orders (including those at second *t*) stay in its order stream and are scored; only the **book** is reset.
* **No leakage into the scored decision:** at second *t* the simulator sees only real orders with first fill **strictly before** *t* (applied at the end of earlier seconds). The real order at *t* is applied after the simulator has decided at *t*.
* **Not reconciled (primary TF-E):** the rule's own memory: scheduled-wave flags, ladder references, last-sale price, pending breakouts, wing-controller timers, opening/lump done flags. These are the decision rule's state, not the portfolio.
* **Labelled secondary variant TF-E-m (memory):** additionally sets, after each real order, the two fill/event-derived inputs the rules read: `last_sale_price` per right (from real `open_short` fills) and the wing-controller timer (armed by real body-module orders at their second). Purpose: show how much of what persists in TF-E is only those two memory inputs. A sensitivity, not an alternative primary.
* **Mode label:** `TF-E`, evidence label `historical reproduction` (teacher-forced diagnostic). F and TF-E tables are always shown side by side.
* **State tables:** the scorer's after-matched-event and checkpoint state tables are computed from cumulative simulated orders; in TF-E the book is forced, so those tables are **not applicable and are dropped** (the scorer is not changed). Replaced by one TF-E diagnostic: **pre-reset drift**: at each real event, before applying it, the simulator book versus the real book (short lots and long lots per option type, per-contract L1 distance), i.e. how far the simulator wandered since the last reset.

## Reported tables (all by pre-set definition)
* Side by side F vs TF-E: tiers (0 / 5 / 60 s), strictness levels, per-class two-sided recall/precision/F1, class confusion, per-cycle F1 distribution (median, IQR, p10, min, worst five, cycles below 0.5 and 0.3), by underlying/version/era, by 30-minute block, missing/extra by class/block/cycle, ambiguity share, tie-break range, time-shift placebo.
* **Real-order recovery table (answers 2 and 3):** each real order is classed by whether it is matched (any tier, one-to-one) in F and in TF-E: *both*, *TF-E only* (recovered by state correction), *F only* (harmed), *neither* (persistent). By class, by 30-minute block, by cycle.
* **Simulated-extras table:** extra (unmatched) simulated orders in F vs TF-E by class and block.
* **Decomposition (answer 4):** share of F's missing real orders recovered by TF-E = (TF-E only) / (F missing). This is an **upper bound** on the part attributable to accumulated book divergence (TF-E also removes ripple effects of the simulator's own earlier extras); the **remainder (neither)** is the part that state correction does not fix: incorrect or missing decision rules, missing inputs, execution/granularity, data limits. Splitting the remainder further is the next task (mismatch classes), not this one. F1-by-30-minute-block gap F → TF-E shows whether divergence accumulates over the day.
* Tolerance used for "matched" in the recovery table: any tier (cumulative 60 s), with the 0 s and 5 s versions alongside.

## No success criterion
Diagnostic. Whatever the numbers are, they are reported; no strategy parameter, threshold, tie-break or class mapping is changed afterwards. A large TF-E improvement says the book divergence mattered; it does not say the strategy is reproduced.

## Software verification required before reading any number (pre-set)
1. Rebuilt real book equals the cumulative real net position per contract after every order (9,915 of 9,915).
2. TF-E with an **empty** real log equals F (order stream identical).
3. **Oracle test:** feed the simulator's own F fills to TF-E as the "real" log: the TF-E order stream equals F's and drift is 0 everywhere.
4. Reconciliation correctness: after every real second the engine's book equals the real book (shorts, wings, lump, entry prices).
5. No-leakage test: removing every real order with first fill at or after *t* does not change the simulator's orders at *t*.
6. Real orders outside the replay window raise (no silent drop).
7. TF-E-m differs from TF-E only through the two named inputs.

## Stated limits in advance
Same 32 development cycles; every number is a historical reproduction. TF-E receives real information throughout and is an easier test by construction. The decomposition attributes by matching outcomes, not by causal intervention; the attributions overlap (a recovered order may also reflect a corrected rule memory in the variant). The real entry price of a covered lot is an engine convention (which lot the real system closed is not in the log).

## Addendum 1 (written after the harness tests, before any TF-E run on real data)
* **Drift timing corrected.** The plan measured pre-reset drift "before applying" the real order. The oracle test showed that measuring after the simulator's step at second *t* counts the simulator's own order at *t* as drift (the real order of the same second is not yet in the real book). Drift is now measured **at the start of second *t*, before the simulator decides**: simulator book versus real book of orders strictly before *t*. No real-data number had been read.
* Wing-controller timer (variant TF-E-m): armed by real body-module `open_short`, `cover_short` and the opening-wing `open_long` (first minutes), i.e. the same activity for which the engine itself calls its body-activity marker; not by body `close_long` or other open_long.

## Addendum 2 (written AFTER the first real-data TF-E run was read; post hoc, labelled)
**What the first run showed (pre-registered definition, variant `book`):** TF-E scored *below* F (60 s keys F1 0.597 vs 0.739), the simulator emitted 10,397 orders (F: 9,035) and **1,247 orders were rejected** by the per-minute decision cap (1,227 of them stop buy-backs, concentrated in NIFTY 28 Jul and 29 Sep). Diagnosis: a **re-decision loop**. When the simulator's stop rule buys back a lot that the real system kept, the next reconciliation restores the lot, the unchanged rule buys it back again, and so on at every reset. The same single disagreement is therefore counted once per reset epoch, and the loop exhausts the 40-decisions-per-minute cap, which then also blocks some unrelated orders (17 non-stop orders). This is a property of the pre-registered reset definition, not a finding about the strategy.
**Nothing is replaced.** The pre-registered TF-E (all simulated orders) is kept and reported as run. In addition, a **first-decision treatment** is reported, labelled *post hoc, added after seeing the first run*:
* In the harness, a simulated `stop_buyback` is flagged **re-decision** when it targets lots that a reconciliation restored after the simulator's own earlier buy-back of the same contract: at each reset, `undone[contract] = min(simulator stop lots on the contract since the previous reset, max(real short lots - simulator short lots, 0))` is added to a pool (capped at the real short lots); a later simulated stop on that contract consumes the pool lot by lot, and a consumed lot's order is the re-decision. Orders not covered by the pool are first decisions (including stops on lots the simulator never held).
* The first-decision score drops flagged orders from the simulated stream and nothing else. It is a **different scoring of the same run**, not a different simulation, so the cap collateral (rejections of unrelated orders) is **not** removed by it and is reported separately.
* Which of the two readings becomes the TF-E definition for the register is the reviewer's decision; both are shown side by side with F.
No parameter, threshold or class mapping of the strategy was touched. Tests for the flag are added before the rerun.
