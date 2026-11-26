# Phase 1 final loop, Investigation C: D0 clearance spread 15:14-15:34. Preregistration

*Written 2026-11-25. **Honest ordering:** the per-cycle real clearance table (`outputs/phase1/9/C_real_clearance_cycles.csv`: shorts at 15:09, main-wave minute, first/last clearance order, residual positions) was computed first as an inspection. It showed (a) post-auction clearance is a single wave at minute 359 (15:14) in 8 of the 9 clearing cycles (NIFTY 2026-08-04: 358/359; SENSEX 2026-08-13: **378**, i.e. 15:33); (b) **all 138 real orders from 15:30 belong to that one cycle (SENSEX 2026-08-13)**; (c) pre-auction bulk clearance sits at 364 for all five SENSEX cycles and 362-364 for NIFTY, with 90% done 2-5 minutes after the start, and the early "starts" at 349/352 are partial buy-backs, not the clearance wave; (d) SENSEX 2026-09-10 holds no short lots at 15:09. Everything below was fixed before any variant ran. Experiments `P1-9-C*`. Baselines: V0 = D0 engine default (clearance at 359 in every cycle, the Gate 5a engine); X1 = the existing in-sample candidate (363 pre-auction, 359 post). Evidence: historical reproduction on development cycles. Nothing committed.*

## 1. Measures of real clearance (per cycle; non-stop cycles with shorts at 15:09)
Clearance lots = real body buy-back lots from minute 345 (the shorts open at 15:09 are bought back before the close, 99.95%, `D0_STOP_CLEAR.md`). **m50 / m90** = the minute at which the cumulative clearance lots reach 50% / 90% of the shorts held at 15:09. **Spread** = m90 - m50. **Residual** = short and long lots still open after the last order. Stop cycles are excluded (the stop module liquidates). Final residual-position clearance and session end are reported per cycle from the same table.

## 2. Hypotheses (small, interpretable set; each tested once)
| ID | Hypothesis | Definition |
|---|---|---|
| CH1 | **Fixed clock by era** | every short is bought back in one minute `c_era`; `c_era` = median m50 of the OTHER cycles of the same era (leave-one-cycle-out), rounded; post-auction era expected 359 |
| CH2 | **Staggered clearance by era** | the clearance follows the era's empirical cumulative profile: share of lots cleared by minute `c_era + k` (k = 0..6) = median over the other same-era cycles (LOCO); applied proportionally to every contract (per-contract cumulative rounding, largest first, deterministic) |
| CH3 | **State-dependent clearance** | the clearance timing (m50 - c_era) or spread depends on the book at 15:09: short lots, long lots, cumulative MTM, share of shorts in the money, spot move since the open (5 variables); Spearman |rho| >= 0.5 and permutation q < 0.05 (Benjamini-Hochberg over the 5 variables per era) |
CH3 is analytic first: if nothing is supported no engine variant exists. CH1 and CH2 are engine runs (LOCO constants in the per-cycle configuration; the engine has one new default-off option `clearance_profile`). Compared with V0 and X1. Selection counted: CH1, CH2, CH3 = 3 tests (+ the existing X1, X1s364).

## 3. Evaluation (separate modes; never mixed)
* **Mode T** (starting from the real carried book, 30 cycles, OOF / forward A / forward B / LOCO): the 5c criteria plus clearance measures below.
* **Mode F** (integrated, free-running, 30 cycles): D0 and combined keys F1.
* Clearance measures (pre-auction and post-auction cycles separately): **timing error** = lot-weighted mean absolute difference (minutes) between the simulated and real cumulative clearance distributions over minutes >= 345 (area between the two normalised CDFs); **order count and lots** in the clearance window (minute >= 345) real vs simulated; **residual lots** after minute 374; clearance-window keys F1 (`events` and `one_lot`, 60 s); cash/position reconciliation (`reconcile`).

## 4. Acceptance (fixed now)
A candidate (CH1 or CH2) can be **adopted in the historical-reproduction configuration in place of X1** only if all hold:
* **CA1** pooled timing error over the pre-auction clearing cycles <= 0.85 x X1's (a >= 15% relative improvement) **and** <= 0.5 x V0's; post-auction timing error not worse than V0's by more than 0.05 minutes per lot.
* **CA2** clearance-window `one_lot` keys F1 >= X1's.
* **CA3** overall keys F1 >= X1 - 0.003 (mode T OOF); legacy lot-level >= X1 - 0.005; no class F1 down by more than 0.02; no cycle down by more than 0.05; forward A and B not lower by more than 0.003.
* **CA4** (CH1) the LOCO `c_era` is the same value in >= 80% of the folds of each era.
* **CA5** the improvement is not driven by one cycle: removing any single pre-auction cycle from the evaluation keeps the timing-error improvement over X1 and V0 positive.
* **CA6** mode F (integrated) D0 keys F1 and combined keys F1 not lower than the X1 configuration by more than 0.003; risk and determinism unchanged; `reconcile` holds in every run.
If neither passes, X1 stays as it is (**experimental in-sample candidate**), unchanged. Independently of the result: **X1 is never a production default** (see section 5).

## 5. What "default" means here (decision fixed in advance)
The era rule can only ever affect historical (pre-3-August-2026) expiries; every future expiry is post-auction, where the clock is the engine default 359. Therefore: the **forward/production D0 configuration keeps clearance at 359 for all cycles (no era rule)**; the **historical-reproduction configuration** may carry the best supported era setting, labelled in-sample/experimental. The frozen manifest will contain both and say so.

## 6. Limits stated in advance
Pre-auction evidence is 8 cycles (forward sets contain none); the era boundary and constants come from the same cycles (LOCO only for constants); one cycle (SENSEX 2026-08-13) clears at 15:33 and is an unexplained exception (not modelled; the engine session ends at minute 374 = 15:29 and is not extended); regime B (after 7 Dec 2026) has no log; clearance order within a minute across contracts is unknown (per-contract proportional rule is an assumption of CH2).

## Addendum 1 (before any variant ran): correction of my own normalisation
The first computation normalised cumulative clearance by the shorts held at 15:09 and produced shares above 1 (up to 2.6) because shorts opened **after** 15:09 (the scheduled and ladder sells continue to the clearance in the pre-auction era) are bought back in the same wave. **Definition fixed:** cumulative shares are normalised by the **total buy-back lots from minute 345 to the end of the session** (all covers, including stop-loss and take-profit buy-backs: the same population on the simulated side). m50, m90, spread and the timing error use this normalisation on both sides. The first table is kept as `C_clearance_measures_first_normalisation.csv`.

## Addendum 2 (before any variant ran): the stable anchor is m90, not m50
With the corrected normalisation the table (`C_clearance_measures.csv`) shows: **post-auction** m50 = m90 = 359 in 8 of 10 cycles (NIFTY 2026-08-04: 358/359; SENSEX 2026-10-22: 357/359; SENSEX 2026-08-13: **376/379**); **pre-auction** m50 is unstable (350-362, a gradual flow of buy-backs from 15:00) but **m90 is 364 in 7 of 8 cycles (363 in one)**: the pre-auction structure is a gradual flow plus a final sweep at about 15:19. A fixed clock anchored on m50 (my first CH1) would describe the flow, not the sweep, and would be a worse test of the hypothesis. **Amended before any run (the criteria in section 4 are unchanged):**
* **CH1:** one-minute sweep at `c_era` = the LOCO median **m90** of the other same-era cycles (expected 364 pre, 359 post); everything still open is bought back at that minute (the engine's single-minute clearance).
* **CH2:** staggered sweep: for offsets k = -5..0 relative to `c_era`, a **hazard** h_k = the LOCO median over the other same-era cycles of (F(c_era+k) - F(c_era+k-1)) / (1 - F(c_era+k-1)), F = the cumulative share of total buy-back lots from minute 345 (clipped to [0,1]); at minute c_era + k the engine buys back round(h_k x lots) of every contract's **open** lots, h_0 = 1 (all remaining). The engine's own buy-back rules (theta, take-profit) and sells continue as before in minutes before the sweep.
* **CH3:** analytic only, variable = spread (m90 - m50) and the deviation of m90 from `c_era`, against the five state variables, per era (n = 8 and 10: low power, stated).
The existing candidates X1 (363) and X1s364 (364, a labelled sensitivity) are kept as comparators. X1s364 equals CH1 for the pre-auction era if the LOCO median is 364, so CH1 differs from X1s364 only by being selected leave-one-cycle-out.
