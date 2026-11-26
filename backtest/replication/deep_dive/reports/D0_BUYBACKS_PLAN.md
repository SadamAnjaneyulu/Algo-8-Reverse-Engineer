# D0 chunk 2: body buy-backs — plan

*Written before the tests. In-sample: D0 of the 30 cycles with both logs, 9,656 body buy-back lots. The ledger is `bl_d0b_ledger.py`:*
* *lots enter at their decision price;*
* *a buy-back removes the highest-ratio open lot on the contract (the D-1 convention), with FIFO as a check;*
* *carried lots keep their D-1 entry.*

**Pre-plan look (descriptive, used to shape this plan):**
* 49% of all D0 buy-back lots are in loss (D-1: 87%).
* Before 15:10, 60% are in loss and 16% are below 0.25× entry. These deep-profit lots are mostly 13:00–15:00, median premium ₹4.65.
* Buy-backs concentrate in minute 14 and minute 0 of each 15-minute block counted from 09:15: 12% each, against 6.7% uniform.

## Population
Body buy-back lots **before 15:10 and before the cycle's stop**. From 15:10 on (the 15:14 clearance and after) is chunk 4.

**Groups by ratio** (decision price / entry):
* **loss** > 1;
* **mid-profit** 0.25–1;
* **deep-profit** < 0.25.

## Tests
**B1 — hazard panel**
* Every open body short lot × D0 minute (before 15:10 and the stop). Label = the lot is removed in that minute.
* Hazard by ratio bin, on the minute high and on the previous close; by origin (D-1 / D0) and by hour.
* Question: does the hazard jump at a stop level, and at a low take-profit level?

**B2 — machines.**
* All machines are teacher-forced on the real book: real sells, and lots removed by the real buy-backs. They are fitted on one cycle half and scored on the other.
* Lot F1 at ±1 minute against real buy-back lots, with precision and recall by group.

The machines:
* **K1 — the D-1 stop unchanged.** A lot is bought back in the first minute its premium high is ≥ 1.6 × entry.
* **K2 — D0 refit.**
  * θ ∈ {1.2, 1.3, …, 2.2}, on the minute high or the close.
  * Variants: θ per hour block (09–11, 11–13, 13–15:10) and θ per origin.
* **K3 — K2 plus a take-profit.**
  * A lot is bought back when its minute low is ≤ θp × entry, θp ∈ {0.1, 0.15, 0.2, 0.25, 0.3, 0.4}.
  * Optional time gate: from 12:00, 13:00 or 14:00, or none.
* **K4 — K3 plus partner.** When a stop fires on a contract, the same-strike other-right lots are bought back too, one for one.
* **K5 — K4 checked only at the block clock** (minutes 14 and 0 of each 15-minute block) instead of every minute.
* **Nulls for the chosen machine:**
  * its predictions shifted by +15 minutes;
  * a rate-matched null: the same lots per cycle and right at random minutes before 15:10.

**B3 — clocking.** Share at second :00 and in block minutes 14 / 0, by group, against uniform.

**B4 — context of in-profit buy-backs.** The share of mid- and deep-profit lots that have, against nulls with times shifted ±10 minutes:
* a loss buy-back on the other right at the same strike within ±60 s (partner);
* a body pair sale within 60 s after (re-centre);
* a same-right sale within 60 s after (roll).

**B5 — one ranking number.**
* Cells: cycle × minute × right, active and before 15:10. Positive = a body buy-back in the cell.
* Leave-one-cycle-out gradient boosting:
  * **A:** market plus book features (the open lots' highest ratio, the share above 1.5×, the lowest premium held, lot counts), from the real book, as on D-1;
  * **B:** A with market data lagged one minute;
  * **clock only.**
* AUC overall and by group, with cycle-bootstrap CIs.

## Acceptance
* As in chunk 1: a rule is kept if it beats its null by ≥ 1.5× and the CI excludes the null.
* Parameters come from the training half only.
* Evidence labels: Observed / Inferred / Unresolved / Not testable; post-hoc steps are labelled.

## Addendum 2b — written after B1–B5, before the tests below
**Context.**
* The per-lot stop (refit θ = 1.4) gives lot F1 0.39. The AUC is 0.82.
* A descriptive look at bursts (same right, gap ≤ 30 s):
  * bursts of 5+ lots carry 64% of in-scope buy-back lots;
  * a typical burst spans 3–5 strikes and takes about 10% of the right's open lots;
  * it mixes profit and loss lots (lowest ratio median 0.9, highest 1.6);
  * it takes only about a third of the lots above its lowest ratio.
* So a burst looks like a **side-level decision** (reduce this right by N lots), not per-lot stops.

**2b-T1 — what triggers a burst.**
* Event = the first minute of a burst of at least 3 lots. Cells as in B5.
* Single-variable AUC (pooled, cycle-bootstrap CI, and by cycle half) of each candidate side-level state:
  * the per-lot stop variable (the highest open-lot ratio);
  * premium imbalance, log(own-right open premium value / other right's);
  * lot imbalance, log(own open lots / other's);
  * delta imbalance, own share of |book delta|, from D0 Black–Scholes;
  * the right's unrealised P&L (index points × lots);
  * the adverse 5-minute spot move.
* A variable counts as a trigger candidate if its AUC is ≥ 0.70 in both halves.

**2b-T2 — burst size.** Spearman correlation of burst lots with:
* lots above 1.4×;
* the imbalance excess;
* the right's open lots.

**2b-T3 — rebalancing machine.**
* At each minute, if the best 2b-T1 variable on a right exceeds a band b, buy back q lots on that right (the highest-ratio lots first).
* q is either a fraction f of the open lots or the number needed to bring the variable back to the band.
* b and f are fitted on one half; lot F1 is scored on the other.
* Scored alone and as a union with K3. Nulls as in B2.

## Addendum 2c — post-hoc, written after the B1 figure and before the test below
**Context.** The B1 hazard is steep for lots sold on D0 (15–26% per minute above 1.7×) but flat for lots carried from D-1 (about 3.5% even at 2× the D-1 entry).

**Hypothesis.** For carried lots, the stop reference is the **D0 opening premium** (the 09:15 minute close), not the D-1 entry.

**2c-T1 — carried lots only, lot-minute panel.**
* AUC of the buy-back label for the minute-high ratio against the D-1 entry and against the D0 open.
* Hazard by bin under both references.
* Cycle-bootstrap CI on the AUC difference.

**2c-T2 — machine.**
* K3 re-fitted (θ, take-profit) with carried lots measured against the D0 open, out-of-fold as in B2.
* Kept if F1 rises by more than the bootstrap noise (CI of the paired difference excludes 0).
