# Body / Hedge module investigation — plan (written before any new analysis of this milestone)

Scope: investigation only. No simulator or engine change, no alpha, no optimisation. Original ledger and earlier reports are read-only; new code lives in `backtest/replication/deep_dive/src/bh_*.py`, outputs in `deep_dive/outputs/bh_*`, tests in `deep_dive/tests/test_bh.py`. The 35 live cycles are not a holdout; nothing here is out-of-sample.

## 1. What the repository already provides (audited)
| Asset | Content | Used for |
|---|---|---|
| `Trades_GKOHNP140.csv` | 41,421 fills / 39,874 orders / 35 cycles (NIFTY 65, SENSEX 20 per lot); 167 columns | source of truth |
| Order-level columns **not used before DD-1** | col 17 limit price, col 18 fill price, col 22 validity (**body = DAY, hedge `h_`/lump `v_` = IOC**, stop `s_` mixed), col 27 status (**1,550 `PartiallyFilled` fill rows**: 701 body, 372 hedge, 346 stop, 130 lump), col 20 remaining qty, col 154 exchange price band | marketable vs passive, partial fills, IOC behaviour (new this milestone) |
| Tag decode (DD-1) | `h_/s_/v_/m_` + `DDHHMMSSffffff` UTC = order decision stamp; numeric tags = body order keys | decision time of non-body modules |
| `lot_lifecycle` | reconstructed lots (4 ownership conventions), wing links (timing only), carried lots, contract-minute panel | lot-level lifecycle (ownership is a convention, not an observation) |
| `execution_parity` | `ref.py` loaders, contract-level inventory, parity scorecard, U1–U14 register | inventory without ownership assumptions |
| `replication/data.py` | per-cycle minute **open/close/volume** by strike and right; spot close (no bid/ask, no high/low, no IV) | contemporaneous prices for strike/price tests |
| Existing evidence (not re-trusted blindly) | HDG-02 wing ≈ 2.44 % of body premium (n = 2,884, IQR 2.21–2.59 %), exact strike agreement 45 %; HDG-03 wing lots per body lot 1.0 vs 1.5 conflict; STK-02 sold strike = nearest to previous-minute close 50 % exact; SIZ-03 D-1 ladder; DD-1 F1–F4 | starting hypotheses only |

## 2. Known limits that fix what is answerable
* No bid/ask/depth, no sub-minute option prices, no high/low → "bid/ask/mid" pricing rules: **NOT TESTABLE**; LTP reference = minute open/close only.
* Body orders have no microsecond stamp (fills at second resolution, order time at minute resolution); hedge/stop/lump orders do.
* No parent/basket id, no cancelled or unfilled order records: an IOC hedge that got zero fills is **invisible**. The numeric order-id counter was tested as a hidden-order detector and is **not usable** (gap median 26 ids inside one second ⇒ a shared/global counter).
* Lot ownership is a reconstruction convention; hedge↔body linking is by timing/contract only.

## 3. Questions and how each is answered
| # | Question | Method | Pre-registered null / criterion | Answerable? |
|---|---|---|---|---|
| B1 | Is the Body a four-leg Iron Butterfly? | per slot: short CE/PE strikes equal? long wings OTM on each side? quantities equal? sequence CE-before-PE? sequencing from fill seconds | structure counts as "butterfly" only if short strikes equal **and** wings exist on both sides with matching lots; report the share per slot/day | yes |
| B2 | Strike selection | candidate reference prices: previous-minute spot close, current-minute spot open, ATM by combined premium; exact / ±1 step; CE vs PE; slot; D-1 vs D0; SENSEX vs NIFTY | compare with a shuffled-spot null (same schedule) | yes (resolution-limited) |
| B3 | Quantity | per-slot lots (DD-1 F3 negative result), CE=PE symmetry, order sizes, partial fills, DAY-order residuals | descriptive + variance decomposition | partly |
| B4 | Entry execution style | limit price vs fill price vs minute open/close (marketable-ness), partial-fill fraction, multi-fill orders, same-second sequencing | descriptive | yes |
| B5 | Position management | D-1 clocked exits, D0 exits (re-use DD-1 + existing EXT/RSK registers), buy-back/re-sell, exits vs premium ratio | restated with explicit status; **no new exit rule claimed** | partly |
| H1 | Does a hedge follow every body short fill? | independent re-implementation (order-level, not burst-level) of DD-1 F1; react to placement vs execution, partial fills, ordering, per-right, 1 vs many hedge orders per body fill, hedge-before-body | verify 92.6 / 92 % ; sensitivity to the 3 s / 10 s windows | yes |
| H2 | Hedge strike selection | test, **all on a pre-registered list** (fixed offset in steps; fixed offset in points; premium ratio to body fill price with k ∈ {2.0, 2.5, 3.0 %}; premium ratio to body strike's LTP; nearest-to-target premium; distance from spot; delta-like moneyness) against the contract-minute chain at the hedge decision minute; compare exact-hit rate with a same-day shuffled-body null; Holm over the list | a rule is "supported" only if exact-hit ≥ 80 % with CI above null and stable across slots/und | yes (prices only) |
| H3 | Hedge quantity | per fill vs per slot vs inventory-aware target (W = S per right); explain the ≈ 8 % mismatches; existing wing inventory; duplicates; partial IOC | classify every mismatch into mutually exclusive classes | yes |
| H4 | Hedge pricing | IOC limit price vs LTP and vs body fill price; limit-fill offsets; share of partial fills; retries (repeat orders after a partial); D-1 vs D0 | descriptive + dependence on body price | partly (no bid/ask) |
| H5 | Hedge lifecycle | contract-level wing inventory vs body-short inventory per right; closes with body? survive body close? carry/settle; salvage; stop/flatten paths; reuse; replace | contract-level (ownership-free) first; lot-level only as bounded convention | yes (contract level) |
| H6 | 928 body bursts without wing response | classify by day, right, slot, hour, existing wing inventory, preceding hedge activity, stop/lump/flatten proximity, fill status | mutually exclusive classes with counts; remainder reported as UNRESOLVED | yes |
| I1 | Interaction timeline | event-level join body decision → order → fill → hedge stamp → hedge order → fill → later adjustments → closure; representative cycles chosen by **pre-registered rules** (first instance of each class by cycle order), not by attractiveness | cases: normal, partial body fill, delayed hedge, quantity differs, missing hedge, reused inventory, body exits first, hedge exits first | yes |

## 4. Evidence rules
Labels: CONFIRMED · STRONGLY SUPPORTED · PARTIALLY SUPPORTED · HYPOTHESIS · REJECTED · UNRESOLVED · NOT TESTABLE. Each important finding reports n (observations), cycles, period, method, null/baseline, CI where meaningful, limitation. Window parameters (3 s, 10 s, 60 s) are analysis choices; sensitivity is reported. Multiple-testing: Holm over each pre-registered list in H2/B2. Thresholds are fixed above before running; none is tuned after seeing results.

## 5. Order of work
1. Data/loader extension (`bh_common.py`: order-level table with limit price, validity, status, remaining qty, stamp) + tests.
2. H1 independent verification → H6 exceptions → H3 quantity.
3. H2 strike tests (pre-registered list) → H4 pricing.
4. Body B1–B4.
5. H5 lifecycle (contract-level), B5 restatement.
6. I1 timelines/cases, figures.
7. Report, evidence table, tests, adversarial self-review, commit/PR (stacked on PR #16).

Honest-labelling commitments: code written ≠ executed ≠ verified; no result quoted that the scripts did not produce; independent review is a **self red-team pass** unless a separate reviewer is run.

---
## Addendum (written after the analysis; the plan above is unchanged)
Added during the work, each because an earlier result or a proofread of the draft exposed a gap: `bh_h3b/h3c` (contract-level balance, after the first hedge test showed the numeric stream also buys wings), `bh_h7` (isolated-order lag test, snapshot-delay test, sign-wrong breakdown, offset test for unmatched body lots), `bh_h8` (wave-level quantity test), `bh_h9` (chance baselines for the level-control claims — the shuffled-gap null turned out to be ≈ 50 %, so the claim rests on the ≈ 40-point excess). Post-hoc items are labelled in the report (strike variants FLOOR/CEIL/NEAREST_LOG, the D0-open exception class). DD-1's hedge "mirror" statement is superseded by the controller description in the report.
