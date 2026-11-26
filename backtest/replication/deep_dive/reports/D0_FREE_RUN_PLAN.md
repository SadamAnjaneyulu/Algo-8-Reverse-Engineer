# D0 chunk 5: free-running D0 reconstruction — plan

*Written before the tests. In-sample: D0 of the 30 cycles with both logs. It assembles the rules kept in chunks 1–4 into one simulator, started from the **real carried book** (the D-1 orders' end state). Parameters are learned on training cycles only.*

## Simulator (minute by minute, 09:15–15:29)
**1. Cycle stop.**
* Cumulative MTM (cash since the D-1 open plus simulated positions at the minute close) ≤ −L → liquidate everything at that minute and stop all activity.
* L = 1.20 lakh (chunk 4). Using the minute close is a look-ahead of less than one minute, and it is labelled.

**2. Body buy-backs** (chunk 2, K3). A body short lot is bought back when:
* its premium high ≥ θ × entry; or
* its low ≤ tp × entry.

θ and tp are fitted on the training cycles. The highest-ratio lots go first.

**3. Body sells** (chunk 1), each at the strike nearest the previous minute's close:
* the **timetable waves** of the cycle's underlying × version, learned on the training cycles;
* the **D-1 breakout machine** (one pair at ATM ± 1 step, 10:30–15:15);
* the **D0 solo ladder** (M1, configuration fitted on training), with its reference reset at simulated pairs;
* the **counter-sell**: r × the simulated other-right buy-back lots in the same minute (r fitted on training, M4).

**4. Opening wings** (chunk 3, H7). At 09:15 the body stream buys the training median number of far wings, split CE/PE, 17 steps OTM.

**5. Hedge controller** (chunk 3).
* After the body orders of the minute: if S > L on a right, buy the gap at the wing strike, the premium nearest 2.5% of the ATM premium.
* If L > S, release the excess from `h_` wings and the `v_` lump, outermost first.
* L includes the carried lump and the opening wings.

**6. 15:14 clearance** (chunk 4). Buy back all body shorts and sell all longs. The controller does not act after the clearance.

## Scoring
* **Classes:**
  * body sell (`num` open_short);
  * body buy-back (`num` cover_short);
  * wing buy (`h_` open_long);
  * wing/lump sell (`h_` + `v_` close_long);
  * body-stream longs (`num` open_long + close_long);
  * stop (`s_`, all roles).
* **Not modelled:** `h_` shorts/covers, `v_` shorts/buys, `m_`. Their lots are counted and reported.
* **Lot-level matching**, one-to-one per cycle × class × right: same minute first, then ±1, with the nearest strike breaking ties.
  * Reported: F1, precision, recall, F1 with an exact strike, and F1 within one strike step; overall (modelled classes) and per class.
  * Null: predictions shifted +15 minutes.
* **AUC (as D-1):**
  * an any-activity cell model (cycle × minute × right), gradient boosting trained on training cycles only;
  * features: market, decoded-rule features (training-learned timetable waves, breakout fires, fresh extremes, clock) and the simulator's own activity in the cell;
  * also the raw simulator activity as a score.

## Splits
* **OOF:** cycle halves by parity.
* **Forward (unseen cycles), by expiry date:**
  * **A:** within each version, the earliest two thirds train and the rest test;
  * **B:** train V1, test V2. V2 test cycles use the training waves of the same underlying in V1.
* Every fitted part is refit on each split's training cycles: waves, θ/tp, ladder configuration and r, and the opening-wing count.

## Variant
**Chained** (started from the simulated D-1 book of `bl_fr_sim.py` instead of the real carried book): reported if built in this chunk, otherwise listed as not done.

## Evidence rules
Observed / Inferred / Not testable. No metric is added to flatter the result.
