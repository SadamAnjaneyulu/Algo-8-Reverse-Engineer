# D0: burst buy-backs, the remaining buy-back types, and the body-stream longs — plan

*Written before the tests below. Builds on `D0_BUYBACKS.md`, `D0_BB_TYPES.md`, `D0_PAIR.md`, `D0_HEDGE.md`, `D0_QTY.md`, `D0_FULL_AUC.md`. In-sample discovery on D0 (26 cycles with minutes before their stop; 14,962 minute cells (cycle × minute × right), as in `D0_FULL_AUC`). Every score below is leave-one-cycle-out (LOCO) or forward, never in-fold.*

## What "90% of D0" will mean (locked before any test)
* **Coverage measure.** The share of the 49,997 D0 lots that sit in a class whose **timing/ranking passes the unseen-cycle gate** (below) **or** whose quantity follows a rule that fits ≥ 90% of events. Computed from the same lot shares as before, with each class's status taken from the tests, not from my judgement. Current (before this step): rule found ≈ 60%, ranked-only ≈ 24%, unresolved ≈ 15%.
* **Not promised:** a 90% lot-by-lot match. The lot count inside a minute depends on the tick path (`D0_QTY.md`); lot F1 stays reported separately (now 0.39–0.45 on unseen cycles) and is re-scored if a rule here changes the simulator.
* **Gate for timing / ranking of a class** (same family as `D0_CAUC`, `D0_FULL_AUC`): causal LOCO AUC ≥ 0.85 with cycle-bootstrap lower bound > 0.82; forward AUC ≥ 0.80 (first two thirds of each version by expiry → rest); cycle-shuffled placebo < 0.65. Within-cycle AUC is reported, not a gate.
* **Gate for a quantity or selection rule:** exact fit ≥ 60% of events, **or** mean error ≥ 20% below the best baseline with ρ ≥ 0.5 (as in `D0_QTY_PLAN`).
* A class that does not pass stays labelled **ranked-only** or **unresolved**; nothing is relabelled to reach 90%.

## Part 1 — buy-backs: bursts and the types that are still open
Population: D0 body buy-back lots by type from `bl_d0y_lots` (precedence 1 cycle-stop … 8 other). Unresolved or weak today: **burst member 11.7%, other 8.8%** of buy-back lots, plus roll-out 13% and partner 4% (mechanism known, timing only ranked), stop-loss/take-profit 36% (threshold known, F1 0.39).

**Outcomes (cell = cycle × minute × right):** any buy-back; burst (≥ 5 lots in the cell); each type's presence (stop-loss, take-profit, roll-out, partner, burst member, other).

**New hypotheses (each can fail), all decision-time (bars to j−1, orders strictly before the minute):**
* **H-B1 ITM depth / re-centring.** A burst takes the lots that have drifted ITM: the trigger is the **deepest ITM lot of the right** (steps = (spot − strike)/step for calls, (strike − spot)/step for puts), or the **drift of the right's mean strike from ATM**, crossing a threshold; and the lots taken are the ones ITM beyond a second threshold. *Test:* AUC of burst presence from ITM-depth features alone and added to the existing families; at lot level, AUC of "taken in the burst" among open lots of the right in a burst minute from ITM depth, ratio, premium, age, origin.
* **H-B2 Side loss.** Unrealised loss of the right's open lots in ₹ lakh, as % of premium collected, and lots at risk (ratio ≥ 1.2, ≥ 1.4). (D0_PAIR planned this with a weaker feature set; here lot-level aggregates from the lot panel are used.)
* **H-B3 Book/cycle.** Distance of the cycle MTM from the stop, lots open on both rights, balance.
* **H-B4 Clock.** The learned recurrence of buy-back minutes/seconds per underlying × version (share of training cycles with a buy-back in that minute, ±1), as for sells. (Buy-backs are 11% at second :00 against 48% on D-1, so a clock is expected to be weak.)
* **H-B5 Cluster / continuation.** Buy-backs on the right in the previous 1/5/15 minutes, sells on either right in the previous minutes (roll), premium at a new high (`D0_PAIR`'s top feature).
* **Model.** LOCO histogram gradient boosting with the fixed settings (200 iterations, depth 3, lr 0.05, min leaf 50, L2 1.0), by feature family and all together; AUC with cycle-bootstrap CI; forward; placebo; the same-minute-information variant reported separately (as in `D0_FULL_AUC`) and **not** used for the gate.
* **Size rule for burst events** (given an event): share of the right's lots taken vs ITM depth thresholds (exact-fit test: "all lots ITM beyond k steps", k fitted on training cycles).

## Part 2 — body-stream longs (7.4% of lots: 1,216 bought, 2,496 sold)
Exploration that shaped the plan (descriptive, not a finding): bought mostly at 09:15–09:20 (725 lots) plus 491 lots later; the strike moves from about 17 steps OTM at the open to 3–5 steps OTM in the afternoon at a **median price of ₹2.15** (IQR 0.8–3.25); 1,246 of the 2,496 sold lots go after 15:14 (clearance); the rest are sold during the day, at a median 0.76 of the buy price, after a median hold of 70 minutes.

* **H-L1 Strike rule.** The long strike is the OTM strike whose premium (previous-minute close) is closest to a constant P\*, or to a fraction of the ATM premium (the 2.5% hedge rule, already known to fit less well on D0). *Test:* exact and ±1-strike match rate of both rules, parameter fitted on training cycles; against the chance rate.
* **H-L2 Opening count.** The number of lots bought at 09:15 equals (or is a fixed fraction of) a book quantity: carried short lots, carried long lots, the lump, the carried shorts minus longs, per underlying. *Test:* exact-fit rate and ρ of each candidate with the opening lots.
* **H-L3 Intraday buys.** Occur when the book needs protection that the hedge controller does not give (gap S−L, new sells, a spot gap), or after the stop. *Test:* AUC of buy presence in a cell (families as above + gap S−L, L on each right, premium at the target strike).
* **H-L4 Intraday sells.** Triggered by the long's premium ratio to its buy price (profit-taking or cut), by the spot returning toward the strike, or by the hedge releasing excess. *Test:* lot-level hazard of sale vs price ratio, hold time, OTM steps; cell AUC of sale presence.
* **H-L5 Clearance.** All remaining longs sold at 15:14 (87% sold; `D0_STOP_CLEAR`); the kept 13% are the cheap ones. Re-measured here as a rule with its exceptions.
* Gate: the cell timing/ranking gate for buy and for sell presence; the rule gates for H-L1, H-L2, H-L5.

## Part 3 — put it back into the free run and re-count
Only for rules that pass: replace the simulator's opening-wing constant (training median) and the missing day buys/sells and the burst handling, rescore the free-run lot F1 on the same splits as `D0_FREE_RUN`, and recompute the coverage measure above. If no rule passes, the simulator is unchanged and the coverage number moves only by the ranking gates.

## Rules for reading the results
* No tuning on a test cycle; thresholds fitted on training cycles per fold. Any step added after seeing results is **post-hoc**, labelled in an addendum.
* A class gets "gate met" only by the rule above. Failures are reported, not tuned away.
* **Not testable here:** the tick path (what sets counts and exact seconds), the vendor's feed, the real system's capital or margin.
* This is in-sample discovery on 32 cycles from one period; passing a LOCO or forward gate is not a statement about other periods.
