# Parity scorecard

Classification rules fixed in `EXECUTION_PARITY_METHODOLOGY.md` section 6 **before** any result (all thresholds provisional). Event agreement is classified at strike-agnostic identity (timing, right, lots); strike, quantity and wing strike have their own rows. **All figures are in-sample** (rules were read from these cycles; the 35 cycles are not a holdout). **No overall parity percentage is shown on purpose.**

Counts of classes: {'MISMATCH': 8, 'PARTIAL MATCH': 7, 'MATCH': 3, 'NOT TESTABLE': 2, 'UNRESOLVED': 1}

| ID | Component | Class | Comparable | Result | Safe to freeze |
|---|---|---|---|---|---|
| S1 | Core = legacy R1/R2 simulator (refactor correctness) | **MATCH** | 70 cycle x variant | 70 identical (100.0 %); max |gross diff| 0.0e+00 | YES (as an implementation of the R1 hypotheses only) |
| S2 | Accounting conservation and inventory bookkeeping (Mode 3) | **MATCH** | 35 cycles x 4 conventions | path/net/cash all equal; max |identity residual| 2.9e-11; max |gross - lot engine| 7.3e-12; gross identical across conventions: True | YES (accounting only) |
| S3 | No-look-ahead integrity of the core | **MATCH** | unit tests (tests/test_core_integrity.py) | all pass | YES |
| S4 | Event sequencing within a second / within a poll | **NOT TESTABLE** | n/a | n/a | n/a |
| S5 | D-1 scheduled body entries (timing, right, count) | **PARTIAL MATCH** | 2234 original lots / 1664 simulated | matched 1484: precision 89.2 %, recall 66.4 %; lift vs null 1.76; with same strike 1360 (precision 81.7 %, recall 60.9 %) | AS A LABELLED SCENARIO |
| S6 | D-1 body entries including off-schedule | **PARTIAL MATCH** | 4834 / 1664 | precision 96.2 %, recall 33.1 % (2600 original lots lie outside the scheduled windows) | NO |
| S7 | D0 body entries (expiry-day sales) | **MISMATCH** | 12686 original lots | R1 reproduces 0; R2 matched 2521 (precision 76.6 %, recall 19.9 %; fitted on the same cycles) | NO |
| S8 | Strike selection (previous completed close, nearest step) | **MISMATCH** | 14312 original body sells | exact 44.7 % (null 22.3 %), within one step 81.5 %; D-1 50.3 %, D0 42.1 %, scheduled windows 60.3 %, off-schedule 33.2 %; NIFTY 52.2 %, SENSEX 38.2 % | AS A LABELLED SCENARIO (scheduled windows only) |
| S9 | Quantity per slot-leg (D-1 ladder) | **PARTIAL MATCH** | 1088 slot-legs | exact 68.5 % (null mean 24.6 %, 95th pct 36.9 %); MAE 0.52 lots | AS A LABELLED SCENARIO |
| S10 | Wing entries (D-1) event agreement | **PARTIAL MATCH** | 4337 original wing lots | precision 85.3 %, recall 32.7 %; with same strike precision 58.8 %, recall 22.6 % | NO |
| S11 | Wing strike selection (price ~ 2.45 % of body) | **MISMATCH** | 8315 body orders with partner (58.5 % of 14300 body sells have one) | exact 32.0 % (null 8.2 %), within one step 55.0 %, within two 67.3 %; median price ratio 0.025 | NO |
| S12 | D-1 body buy-backs (events) | **PARTIAL MATCH** | 1640 original lots | precision 79.1 %, recall 24.4 %, lift 17.1; with same strike precision 63.6 %, recall 19.6 % | NO (stop only as a labelled hypothesis) |
| S13 | D0 body buy-backs (events) | **MISMATCH** | 12714 original lots | precision 55.9 %, recall 5.4 %, lift 4.7 | NO |
| S14 | Wing sells / releases | **MISMATCH** | D-1 1192 / D0 10243 lots | D-1: PARTIAL MATCH, precision 72.3 %, recall 30.7 %; D0: MISMATCH, precision 37.7 %, recall 4.5 % | NO |
| S15 | Per-lot stop (H-LEG): 32 cells = k {1.55..1.70} x {own, cheapest} x 4 conventions | **MISMATCH** | 12173 original buy-back lots; 1166-6722 simulated stop events per cell | own-entry reference: precision 62.9 %-74.6 %, recall 6.9 %-16.9 %, lift 9.1-11.4; cheapest-entry reference: precision 25.5 %-33.1 %, recall 8.3 %-14.4 %; best recall in any cell 16.9 % | NO (hypothesis only) |
| S16 | Cycle stop (H-CYC) | **MISMATCH** | 30 cycles, 11 with an actual stop | causal: TP 0 of 11 at every L (recall 0.0 %); non-causal diagnostic: TP 1-3 of 11 (precision 100 %, no false positives); 8 of the 11 actual stops occur within the first 15 minutes of D0 | NO |
| S17 | Final flatten at 15:14 on D0 (after 2026-08-03) | **PARTIAL MATCH** | 12 post-cutover cycles with shorts (1529 short lots at 15:13) and 9 pre-cutover cycles | post-cutover: 1213 of 1529 short lots closed in the 15:14 minute (79.3 %); 10 of 12 cycles fully flat; the two exceptions (NIFTY 2026-08-11, SENSEX 2026-08-13) keep ~100 % short; pre-cutover cycles keep 93.2 % (median share) of shorts through 15:14 | AS A LABELLED SCENARIO (date-conditioned) |
| S18 | Carry to settlement vs distance from spot (H-CARRY) | **UNRESOLVED** | 2259 short lots (contract basis), 4163 (body-module basis) | contract-level (all modules): carried share 0.0 %-0.2 % in every distance bin (nothing is carried: 24 of 35 cycles end exactly flat at contract level, the others hold long wings only (one D-1-only cycle holds shorts)); body-module basis: 9.9 % (<=0.5 steps) rising monotonically to 97.8 % (>6 steps) | NO |
| S19 | Inventory trajectory (contract-level, event by event) - fully simulated | **MISMATCH** | 30 cycles, 505598 active contract-minutes | exact share 5.0 % (mean of cycles), normalised MAE median 0.91; overnight net short lots mean original 104 vs simulated 36 | NO |
| S20 | Settlement valuation of residual positions | **NOT TESTABLE** | n/a | n/a | n/a |
| S21 | Historical mechanics robustness across expiry structures | **PARTIAL MATCH** | 274 eligible cycles of 319 expected | hard checks pass in 274/274; brittle: fills priced from a missing open and zero-volume bars differ several-fold between structures; cycle-stop incidence 3%-20% | NO (mechanics pass; policies must be set) |

## Detail per component

### S1 Core = legacy R1/R2 simulator (refactor correctness) — **MATCH**
* **Original-system evidence:** stored simulator replication/sim.py (not original behaviour)
* **Our implementation:** exec_core.py + components.py + runner.py
* **Comparison methodology:** event-by-event equality of all events, fills, gross, stop flags on every live cycle, R1 and R2
* **Comparable events:** 70 cycle x variant
* **Matches:** 70 identical (100.0 %); max |gross diff| 0.0e+00
* **Material discrepancies:** none
* **Data limitations:** proves the refactor equals the old code, NOT that either equals the original
* **Confidence:** high (hard criterion)
* **Required next action:** none
* **Safe to freeze:** YES (as an implementation of the R1 hypotheses only)

### S2 Accounting conservation and inventory bookkeeping (Mode 3) — **MATCH**
* **Original-system evidence:** original fills (exact prices)
* **Our implementation:** PortfolioState under FIFO/LIFO/LOW/HIGH
* **Comparison methodology:** replay all fills: contract net after every fill vs cumulative sum; cash vs ledger; cash-based gross vs realised+open P&L; gross vs lot engine (30 cycles)
* **Comparable events:** 35 cycles x 4 conventions
* **Matches:** path/net/cash all equal; max |identity residual| 2.9e-11; max |gross - lot engine| 7.3e-12; gross identical across conventions: True
* **Material discrepancies:** none
* **Data limitations:** cash conservation is tautological for any allocation; says nothing about ownership or behaviour; settlement uses the Yahoo close proxy
* **Confidence:** high (hard criterion)
* **Required next action:** none
* **Safe to freeze:** YES (accounting only)

### S3 No-look-ahead integrity of the core — **MATCH**
* **Original-system evidence:** n/a (design property)
* **Our implementation:** MarketView exposes only completed bars
* **Comparison methodology:** perturbation tests: future bars changed, earlier decisions unchanged; D-1 minute 0 has no bar; D0 minute 0 reads the last D-1 bar
* **Comparable events:** unit tests (tests/test_core_integrity.py)
* **Matches:** all pass
* **Material discrepancies:** none found
* **Data limitations:** covers the new core; the stored legacy event table (D0 minute-0 look-ahead) is not used
* **Confidence:** high (hard criterion)
* **Required next action:** independent review of the perturbation design
* **Safe to freeze:** YES

### S4 Event sequencing within a second / within a poll — **NOT TESTABLE**
* **Original-system evidence:** fills carry whole seconds; within-second order = file order (documented)
* **Our implementation:** deterministic: minute loop, module order exits -> entries, file order for injected fills
* **Comparison methodology:** determinism test passes; original sub-second order cannot be compared
* **Comparable events:** n/a
* **Matches:** n/a
* **Material discrepancies:** unobservable
* **Data limitations:** no sub-second timestamps, no parent ids (U6, U13)
* **Confidence:** n/a
* **Required next action:** request sub-second timestamps
* **Safe to freeze:** n/a

### S5 D-1 scheduled body entries (timing, right, count) — **PARTIAL MATCH**
* **Original-system evidence:** 17 scheduled windows act in 544/544 session-windows (TP-03); ladder is a tendency (deterministic ladder falsified)
* **Our implementation:** LadderEntries (R1 ladder 3,2,3,1,3,1,2,2,1,1,3,1,0,2,0,0,1)
* **Comparison methodology:** one-to-one match, same cycle/right, +-1 min, strike ignored; phase-preserving null (40 draws)
* **Comparable events:** 2234 original lots / 1664 simulated
* **Matches:** matched 1484: precision 89.2 %, recall 66.4 %; lift vs null 1.76; with same strike 1360 (precision 81.7 %, recall 60.9 %)
* **Material discrepancies:** quantity per slot is the modal tendency, not the original rule; timing alone is schedule-trivial (lift low)
* **Data limitations:** in-sample; 3-minute window after each slot; orders vs lots
* **Confidence:** medium
* **Required next action:** resolve quantity rule (needs decision logs)
* **Safe to freeze:** AS A LABELLED SCENARIO

### S6 D-1 body entries including off-schedule — **PARTIAL MATCH**
* **Original-system evidence:** off-schedule entries exist; trigger unknown (U10)
* **Our implementation:** none (not implemented)
* **Comparison methodology:** same as S5, all original D-1 body sells
* **Comparable events:** 4834 / 1664
* **Matches:** precision 96.2 %, recall 33.1 % (2600 original lots lie outside the scheduled windows)
* **Material discrepancies:** off-schedule share of original D-1 sells is large and absent from the engine
* **Data limitations:** trigger unrecoverable from the available records
* **Confidence:** medium
* **Required next action:** decision logs / sub-second timestamps
* **Safe to freeze:** NO

### S7 D0 body entries (expiry-day sales) — **MISMATCH**
* **Original-system evidence:** D0 body sells are the largest order class; cluster at Clock-B ticks (times observed, decision not); replacement rejected
* **Our implementation:** R1: none. R2: median ladder fitted to the live window (hypothesis)
* **Comparison methodology:** same as S5
* **Comparable events:** 12686 original lots
* **Matches:** R1 reproduces 0; R2 matched 2521 (precision 76.6 %, recall 19.9 %; fitted on the same cycles)
* **Material discrepancies:** the largest behavioural gap: most original orders are D0 sales
* **Data limitations:** U11 unresolved
* **Confidence:** high that it fails
* **Required next action:** decision logs
* **Safe to freeze:** NO

### S8 Strike selection (previous completed close, nearest step) — **MISMATCH**
* **Original-system evidence:** first order = ATM in 31/32 cycles (opening); scheduled additions 63 % exact, 93 % within one step (TP-03)
* **Our implementation:** R.nearest_strike on MarketView.spot_prev
* **Comparison methodology:** Mode 1: actual decision minute given; compare rule strike with actual strike; null = same rule at a phase-shifted minute
* **Comparable events:** 14312 original body sells
* **Matches:** exact 44.7 % (null 22.3 %), within one step 81.5 %; D-1 50.3 %, D0 42.1 %, scheduled windows 60.3 %, off-schedule 33.2 %; NIFTY 52.2 %, SENSEX 38.2 %
* **Material discrepancies:** off-schedule and D0 sells follow a different (unknown) strike logic or the 1-minute spot lags the original
* **Data limitations:** minute spot vs live ticks; mean signed error -0.13 steps
* **Confidence:** medium
* **Required next action:** sub-second timestamps and tick spot
* **Safe to freeze:** AS A LABELLED SCENARIO (scheduled windows only)

### S9 Quantity per slot-leg (D-1 ladder) — **PARTIAL MATCH**
* **Original-system evidence:** window mode explains 64.5 % of quantities (TP-03); deterministic ladder falsified
* **Our implementation:** R1 ladder per slot
* **Comparison methodology:** Mode 1: actual lots in the first 3 min of each slot vs ladder; null = ladder shuffled across slots (300 draws)
* **Comparable events:** 1088 slot-legs
* **Matches:** exact 68.5 % (null mean 24.6 %, 95th pct 36.9 %); MAE 0.52 lots
* **Material discrepancies:** what moves quantity off the modal value is unknown
* **Data limitations:** ladder was read from the same cycles
* **Confidence:** medium
* **Required next action:** decision logs / sizing inputs
* **Safe to freeze:** AS A LABELLED SCENARIO

### S10 Wing entries (D-1) event agreement — **PARTIAL MATCH**
* **Original-system evidence:** wing buy within +-15 s of body sells in ~58-78 % of orders (timing only)
* **Our implementation:** wing with each body lot (U3 scenario: one per lot)
* **Comparison methodology:** same as S5, h_ Buy
* **Comparable events:** 4337 original wing lots
* **Matches:** precision 85.3 %, recall 32.7 %; with same strike precision 58.8 %, recall 22.6 %
* **Material discrepancies:** original D-1 wing lots outnumber simulated ones (4337 vs 1664) because the engine has no off-schedule entries
* **Data limitations:** association is timing-only (U3)
* **Confidence:** low
* **Required next action:** wing/hedge association identifiers
* **Safe to freeze:** NO

### S11 Wing strike selection (price ~ 2.45 % of body) — **MISMATCH**
* **Original-system evidence:** median wing/body price 0.025
* **Our implementation:** R.wing_strike_index
* **Comparison methodology:** Mode 1: for each actual body sell with an identified wing partner (+-15 s, one-to-one) apply the rule; compare strikes; null = rule of a random other body
* **Comparable events:** 8315 body orders with partner (58.5 % of 14300 body sells have one)
* **Matches:** exact 32.0 % (null 8.2 %), within one step 55.0 %, within two 67.3 %; median price ratio 0.025
* **Material discrepancies:** distance of the wing from its body strike, median in steps: original 12.0 vs rule 14.0; the original wing is on average 2.43 steps closer to the body than the rule picks
* **Data limitations:** 41 % of body sells have no identifiable wing partner: bounded uncertainty, not a deterministic relation
* **Confidence:** low
* **Required next action:** wing association identifiers
* **Safe to freeze:** NO

### S12 D-1 body buy-backs (events) — **PARTIAL MATCH**
* **Original-system evidence:** D-1 buy-backs exist (1,640 lots); per-lot stop band 1.55-1.70x is a hypothesis
* **Our implementation:** LegStop (R1)
* **Comparison methodology:** one-to-one, +-2 min, strike ignored; null
* **Comparable events:** 1640 original lots
* **Matches:** precision 79.1 %, recall 24.4 %, lift 17.1; with same strike precision 63.6 %, recall 19.6 %
* **Material discrepancies:** the stop rule explains at most 24.4 % of original D-1 buy-backs
* **Data limitations:** in-sample
* **Confidence:** medium
* **Required next action:** stop configuration / trigger log
* **Safe to freeze:** NO (stop only as a labelled hypothesis)

### S13 D0 body buy-backs (events) — **MISMATCH**
* **Original-system evidence:** 12,714 original lots; scheduled/Clock-B behaviour and flatten
* **Our implementation:** LegStop + CycleStop + Flatten (R1)
* **Comparison methodology:** same as S12
* **Comparable events:** 12714 original lots
* **Matches:** precision 55.9 %, recall 5.4 %, lift 4.7
* **Material discrepancies:** engine explains ~5 % of D0 body buy-backs
* **Data limitations:** D0 decision rules unknown (U11)
* **Confidence:** high that it fails
* **Required next action:** decision logs
* **Safe to freeze:** NO

### S14 Wing sells / releases — **MISMATCH**
* **Original-system evidence:** wing closes with body in 84 % of short closings (TP-02)
* **Our implementation:** wing closes with its body lot
* **Comparison methodology:** same as S12 for h_ Sell
* **Comparable events:** D-1 1192 / D0 10243 lots
* **Matches:** D-1: PARTIAL MATCH, precision 72.3 %, recall 30.7 %; D0: MISMATCH, precision 37.7 %, recall 4.5 %
* **Material discrepancies:** D0 wing sells are mostly outside the engine
* **Data limitations:** U3 unresolved
* **Confidence:** low
* **Required next action:** wing association identifiers
* **Safe to freeze:** NO

### S15 Per-lot stop (H-LEG): 32 cells = k {1.55..1.70} x {own, cheapest} x 4 conventions — **MISMATCH**
* **Original-system evidence:** about 95 % of stop buy-backs at >= 1.5x lowest entry; 0 of 18 candidate rules at 80/80 (earlier)
* **Our implementation:** LegStop evaluated on the actual book (lot_lifecycle lots) and actual market
* **Comparison methodology:** rule fires once per lot at first breach; one-to-one with actual body buy-backs, +-2 min, same contract; null (20 draws)
* **Comparable events:** 12173 original buy-back lots; 1166-6722 simulated stop events per cell
* **Matches:** own-entry reference: precision 62.9 %-74.6 %, recall 6.9 %-16.9 %, lift 9.1-11.4; cheapest-entry reference: precision 25.5 %-33.1 %, recall 8.3 %-14.4 %; best recall in any cell 16.9 %
* **Material discrepancies:** when the rule fires a buy-back usually follows (high precision, 8-11x chance) but it explains at most ~17 % of body buy-backs
* **Data limitations:** ownership-dependent through which lots are open; all cells reported, none selected
* **Confidence:** medium
* **Required next action:** stop configuration; trigger log
* **Safe to freeze:** NO (hypothesis only)

### S16 Cycle stop (H-CYC) — **MISMATCH**
* **Original-system evidence:** cumulative LTP MTM stop; s_ liquidation in 11 of the 30 complete cycles (earlier research: ~-Rs 1.30 to -1.44 L)
* **Our implementation:** CycleStop (MTM at the previous completed close)
* **Comparison methodology:** Mode 1: MTM from actual fills (excluding s_) and minute marks; first breach of L in {1.30, 1.35, 1.44} lakh vs first actual s_ order; non-causal diagnostic uses the decision-minute close
* **Comparable events:** 30 cycles, 11 with an actual stop
* **Matches:** causal: TP 0 of 11 at every L (recall 0.0 %); non-causal diagnostic: TP 1-3 of 11 (precision 100 %, no false positives); 8 of the 11 actual stops occur within the first 15 minutes of D0
* **Material discrepancies:** at the decision minute the MTM seen with previous-completed marks has median Rs -105,372 (range Rs -133,341 to Rs 30,889) against thresholds of Rs -130,000 to -144,000: the right region but no crossing
* **Data limitations:** minute marks cannot reproduce a stop that fires within seconds of the open: partly a data-resolution limit, partly an unrecovered rule (U8)
* **Confidence:** medium
* **Required next action:** risk-engine parameters and poll log; sub-second quotes
* **Safe to freeze:** NO

### S17 Final flatten at 15:14 on D0 (after 2026-08-03) — **PARTIAL MATCH**
* **Original-system evidence:** 15:14 flatten after the cut-over (EXT-08); earlier rule unknown
* **Our implementation:** Flatten(minute 359)
* **Comparison methodology:** Mode 1, contract-level (all modules): net short lots at the end of 15:13 vs 15:14
* **Comparable events:** 12 post-cutover cycles with shorts (1529 short lots at 15:13) and 9 pre-cutover cycles
* **Matches:** post-cutover: 1213 of 1529 short lots closed in the 15:14 minute (79.3 %); 10 of 12 cycles fully flat; the two exceptions (NIFTY 2026-08-11, SENSEX 2026-08-13) keep ~100 % short; pre-cutover cycles keep 93.2 % (median share) of shorts through 15:14
* **Material discrepancies:** two exceptions in the first two weeks after the stated cut-over; the exact cut-over date looks like later than 2026-08-03 (a post-hoc observation, not adopted); the flatten includes num SELLS of wing contracts (cross-role), so the body-module view hides it
* **Data limitations:** contract-level inventory; 15:14 is minute-resolution
* **Confidence:** medium
* **Required next action:** platform release history
* **Safe to freeze:** AS A LABELLED SCENARIO (date-conditioned)

### S18 Carry to settlement vs distance from spot (H-CARRY) — **UNRESOLVED**
* **Original-system evidence:** deep-OTM carried body lots are held to settlement (76 % beyond 6 steps, earlier lot-level result)
* **Our implementation:** Flatten + hold (R1 holds nothing past 15:14)
* **Comparison methodology:** short lots at 15:13 still short at the end of the ledger, by |strike - spot| in steps; two inventory bases
* **Comparable events:** 2259 short lots (contract basis), 4163 (body-module basis)
* **Matches:** contract-level (all modules): carried share 0.0 %-0.2 % in every distance bin (nothing is carried: 24 of 35 cycles end exactly flat at contract level, the others hold long wings only (one D-1-only cycle holds shorts)); body-module basis: 9.9 % (<=0.5 steps) rising monotonically to 97.8 % (>6 steps)
* **Material discrepancies:** the carry relationship exists only on the role-routing basis; at contract level the body shorts are offset by same-contract long wings (economically flat)
* **Data limitations:** depends on an unvalidated role-routing assumption (num fills touch only body inventory)
* **Confidence:** medium
* **Required next action:** parent ids / hedge association
* **Safe to freeze:** NO

### S19 Inventory trajectory (contract-level, event by event) - fully simulated — **MISMATCH**
* **Original-system evidence:** original contract-level net lots at every minute (ownership-free), 30 complete cycles
* **Our implementation:** R1 engine
* **Comparison methodology:** net lots per contract at the end of every minute; active contract-minutes only; exact share and MAE / mean |original|
* **Comparable events:** 30 cycles, 505598 active contract-minutes
* **Matches:** exact share 5.0 % (mean of cycles), normalised MAE median 0.91; overnight net short lots mean original 104 vs simulated 36
* **Material discrepancies:** the engine carries 35% of the original overnight short book and none of the D0 activity
* **Data limitations:** cascades from S6/S7/S13
* **Confidence:** high that it fails
* **Required next action:** decision logs
* **Safe to freeze:** NO

### S20 Settlement valuation of residual positions — **NOT TESTABLE**
* **Original-system evidence:** no settlement fills in the ledger; official close proxy differs from the 15:29 spot bar by up to 89 points in 13 early cycles
* **Our implementation:** settle at the Yahoo official close
* **Comparison methodology:** cannot compare
* **Comparable events:** n/a
* **Matches:** n/a
* **Material discrepancies:** unobservable
* **Data limitations:** U12
* **Confidence:** n/a
* **Required next action:** exchange settlement prices
* **Safe to freeze:** n/a

### S21 Historical mechanics robustness across expiry structures — **PARTIAL MATCH**
* **Original-system evidence:** no original records for 2023-2025: tests mechanics only
* **Our implementation:** R1 modules on 274 eligible cycles (5 expiry structures)
* **Comparison methodology:** hard checks (inventory reconciles, finite P&L, no over-closing, determinism) + price-quality and stop-incidence diagnostics by structure
* **Comparable events:** 274 eligible cycles of 319 expected
* **Matches:** hard checks pass in 274/274; brittle: fills priced from a missing open and zero-volume bars differ several-fold between structures; cycle-stop incidence 3%-20%
* **Material discrepancies:** stale-price fallback; unfillable exits; size-dependent rupee constants
* **Data limitations:** cannot show historical parity; structures differ in weekday, lot size and liquidity
* **Confidence:** medium
* **Required next action:** explicit price-quality policy; scaling convention (U14)
* **Safe to freeze:** NO (mechanics pass; policies must be set)

