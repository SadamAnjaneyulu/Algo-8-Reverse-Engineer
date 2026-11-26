# D0 chunk 1: body sells — plan

*Written before the tests. In-sample: D0 of 32 live cycles, 8,955 body sell orders and 10,190 lots. Builds on `D0_INVENTORY.md`, the `d0_reconstruction` register (grid-A windows, replacement after a buy-back) and the D-1 sell decode (scheduled waves, reactive two-candle breakout, solo ladder).*

## Labels (descriptive, no parameters)
* **Pair:** a CE and a PE sell order at the same strike within 3 s, matched one-to-one, closest first (the same definition as D-1).
* **Grid pair:** a pair whose first order is inside a grid-A window (minute-of-hour 1–3, 16–18, 31–33, 46–48). **Off-grid pair:** every other pair.
* **Solo:** an unpaired sell order.
* Lots are counted per order.

## Tests
**T1 — the 15-minute slot clock (grid pairs)**
* Slots run from 09:16 to 15:01, every 15 minutes (24 slots). Per version, I measure:
  * the share of cycles with a pair in each slot window;
  * the spread across cycles of the seconds from slot start to the first pair. D-1 waves had fixed seconds.
* Rule S0: one CE and one PE lot at every slot, at the minute of the median offset learned on the training half, at the strike nearest the previous minute's close.
* Scored on grid pairs: lot F1 at ±1 minute, out-of-fold over cycle halves.
* Null: the same density measured in shifted windows (minute-of-hour 6–8 / 21–23 / 36–38 / 51–53 and 11–13 / 26–28 / 41–43 / 56–58).

**T2 — the reactive breakout (off-grid pairs)**
* I run the D-1 machine unchanged on D0 spot: first intrabar break, per side, of the previous two clock-aligned 30-minute candles' high and low, 10:30–15:15. Nothing is refitted.
* Scored on off-grid pair minutes: minute F1 at ±1 minute, plus the share whose strike sits one step on the side of the break.
* Placebos:
  * the same machine on another cycle's D0 spot (cyclic permutation of cycles);
  * the fires shifted by +15 minutes.
* Descriptive: off-grid pairs by hour, including before 10:30, when the machine is silent.

**T3 — solo sells**
* **(a) Direction.** The share of solo lots sold after a favourable spot move (CE after a fall, PE after a rise) over the previous 5 and 15 minutes. Null: random minutes in the same cycle and hour.
* **(b) The D-1 solo ladder unchanged.** A 0.2-step spot ladder, gated by a fresh 60-minute extreme, with its reference reset at pairs. Lot F1 at ±1 minute against solo lots. Placebo: cycle-permuted spot.
* **(c) Replacement.** The share of solo lots sold within 60 s **after** a body buy-back on the same right, against a null of buy-back times shifted by ±10 minutes. The same-lots share is also reported.
* **(d) Counter-sell.** The share of solo lots sold within 60 s **before or after** a body buy-back on the **other** right, with the same null.
* **(e) Burst structure.** Solo orders grouped into bursts (gap ≤ 30 s, same right). Reported: lots per burst, strikes per burst, and spot and premium moves inside a burst.

**T4 — strike choice**
* Pairs: the exact share at the strike nearest the previous minute's close (the D-1 rule), and the ±1-step share.
* Solo: the share at the nearest ATM, against the D-1 solo rule (the premium nearest the last sale's premium on that right).

**T5 — one ranking number for D0 selling (as D-1)**
* Cells: cycle × minute × right, 09:16–15:29. Positive = a body sale in the cell.
* Leave-one-cycle-out gradient boosting:
  * **A:** market and decoded-rule features (slot clock, breakout machine, fresh extremes, premium lows);
  * **B:** A with market data lagged one minute (causal);
  * **C:** A plus the real D0 buy-back history from **earlier minutes** (teacher-forced).
* Report AUC overall and by sell label, with cycle-bootstrap CIs.

## Acceptance
* A rule is **kept** if it beats its null or placebo by a clear margin: F1 or share ≥ 1.5× the null, and the bootstrap CI excludes the null.
* Otherwise it is **rejected**, or kept as descriptive only.
* Parameters (slot offsets) come from the training half only.
* Evidence labels: Observed / Inferred / Unresolved / Not testable; post-hoc steps are labelled.

## Addendum 1b — written after T1, before the tests below
T1 showed that pair start seconds are identical across cycles of the same **underlying and version**, to within 1–2 s. D-1 pooled the underlyings, but on D0 each underlying has its own pattern. Body selling stops at the first stop-module (`s_`) order. Here that stop time is taken from the real orders (teacher-forced); chunk 4 decodes it.

**T1b — D0 timetable per (underlying, version), out-of-fold (cycle parity halves)**
* **Wave discovery** on the training half, using every pair start (grid and off-grid). Only cycles still active (before their stop) count in a wave's denominator.
  * Greedy: take the second where the most active training cycles have a pair start within ±3 s.
  * It becomes a wave if that is at least 50% of the active cycles. The wave time is the median of those starts, and the wave's lots per right are the median pair lots.
  * One start per cycle is then removed, and the step repeats. Two pairs at the same second can therefore give two waves.
* **Prediction:** each wave before the real stop time sells 1 CE + 1 PE × the wave lots, at the strike nearest the previous minute's close.
* **Scoring:** lot F1 at ±1 minute against all pair lots and against grid-pair lots, with the strike-exact share.
* **T2b:** the T2 breakout machine and placebos, re-run on the pair minutes the timetable does not explain (pairs more than 3 s from every wave of the cycle's own group, learned on the other half).
* The acceptance rules are unchanged.

## Addendum 1c — solo sells, written after T3 and before the tests below
**Context.** T3 found three things:
* 64% of solo lots fall within ±60 s of a buy-back on the other right (null 33%);
* bursts of up to 20 lots;
* the D-1 ladder unchanged is precise (73%) but finds only 9% of D0 solo lots.

A descriptive look at the bursts gave no fixed lot or premium ratio between a burst and the other-right buy-back (median 0.5, IQR 0.25–1). The look also gave no fixed order in time: the buy-back comes −62 s to +16 s around the burst start. So the coupling may be a common cause, the same spot move, rather than a mechanical rule.

**Competing machines.** Each is fitted on one cycle half by grid search and scored on the other (lot F1 at ±1 minute against solo lots). Activity stops at the real stop time. References reset at real pair sales and at the machine's own fires.
* **M1 — spot ladder.** Step X ∈ {0.05, 0.1, 0.2, 0.3, 0.5} strike steps. Fresh-extreme gate ∈ {none, 15, 30, 60} min. Lots per fire = 1, or the number of steps crossed (capped at 10).
* **M2 — premium ladder.** Fire when the minute low of the last-sold contract on that right is at least δ below the reference premium, δ ∈ {2, 3, 5, 8, 12}%. Lots per fire = 1 or the number of δ steps crossed (cap 10). The reference is that contract's sale premium, moved down δ per step.
* **M3 — counter-sell on a real buy-back.** r × the bought-back lots, on the other right, in the buy-back's minute, r ∈ {0.25, 0.5, 1, 2}. Teacher-forced on the real buy-backs.
* **M4 — union of M1 or M2 with M3.** Lots are summed per minute, and parameters are chosen jointly on the training half.

**T5 (as planned) — the D0 sell AUC.** Variant C adds the real buy-back history from earlier minutes. Two post-plan extensions are pre-declared here:
* variant **C0**, which adds the **same-minute** other-right buy-back. It is labelled teacher-forced and same-minute, and it measures the coupling, not a causal trigger;
* the share of the C-over-A gain that is still there when spot moves are held fixed. This is the common-cause check: the AUC of the buy-back feature inside spot-move quintiles.
