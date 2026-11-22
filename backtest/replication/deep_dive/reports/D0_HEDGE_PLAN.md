# D0 chunk 3: hedge wings, lump salvage, body-stream longs — plan

*Written before the tests. In-sample: D0 of the 30 cycles with both logs. Builds on `D1_LONG_SIDE.md`, where the D-1 rules were found:*
* *the controller buys the gap S − L per right about 4 s after a body order;*
* *the wing strike is the premium nearest 2.5% of the ATM same-right premium;*
* *releases are the outermost or cheapest wing;*
* *opening wings are bought by the body stream;*
* *the overnight lump is `v_`.*

*Inventory (`D0_INVENTORY.md`, all D0 cycles):*
* *`h_` buys 9,370 and sells 9,941 lots;*
* *`h_` shorts 302 / covers 485;*
* *`v_` sells 843 (18 cycles);*
* *body-stream long buys 1,216 (829 in the 09:00 hour) and sells 2,496 (1,268 in the 15:00 hour).*

## Tests (the D-1 rules first, unchanged)
**H1 — controller quantity**
* `h_` waves are orders on one right whose decision stamps fall within 0.05 s.
* Each wave is compared with the gap S − L just before it. S and L include all modules, and the position carried from D-1.
* Reported: the share where wave lots = gap, and the sign agreement.
* Variants of L: with and without the carried `v_` lump longs.

**H2 — wing strike**
* For `h_` buys: the share at the strike whose premium is nearest X% of the ATM same-right premium.
* X = 2.5% (D-1, unchanged), and X refit on one cycle half from {0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10}% and scored on the other.
* Reported: exact and ±1-strike shares, against the chance of picking a random OTM strike among the 10 nearest the chosen one.

**H3 — release choice**
* When `h_` sells while ≥ 2 long strikes are held on that right, which wing goes: outermost, innermost, cheapest, dearest, oldest, newest, or nearest 2.5%.
* Compared with chance = 1 / strikes held.

**H4 — timing.** Seconds from the body order that changes S to the controller wave that follows (D-1: about 4 s).

**H5 — `h_` shorts and covers on D0.** Descriptive: when they happen, their strikes, and the gap state at the time.

**H6 — lump salvage (`v_` sells)**
* Descriptive:
  * time of day;
  * all at once or in pieces;
  * premium at sale / lump entry;
  * spot distance from the lump strike.
* Simple rules, scored on lots at ±1 minute against nulls:
  * a fixed clock;
  * a premium ratio threshold (sell when the premium recovers to ≥ r × entry);
  * the end of the cycle's body activity.

**H7 — body-stream longs on D0 (`num` buys and sells).**
* Descriptive: time, strike offset from ATM, and the gap S − L before and after.
* Do the D-1 opening-wing rules (pre-bought far wings before the first straddles) carry over?
* The 15:14 sells belong to chunk 4.

**H8 — one ranking number.**
* Cells: cycle × minute × right. Positive = an `h_` buy in the cell; a second model for `h_` sells.
* Leave-one-cycle-out gradient boosting on:
  * the real gap at the start of the minute and the body orders in the minute (teacher-forced);
  * clock features.
* Reported: AUC with cycle-bootstrap CIs.

## Acceptance
* As in chunks 1–2: a rule is kept if it beats its null or chance by ≥ 1.5× and the CI excludes it.
* Parameters come from the training half.
* Evidence labels; post-hoc steps are labelled.

## Addendum 3b — post-hoc, written after H1–H7 and before the tests below
**Context.**
* The controller gap matches only when the carried `v_` lump longs are counted in L (94% vs 46%).
* The lump is sold off in 10–24 pieces through the day at about 6% of its D-1 cost.
* The 2.5%-of-ATM wing rule is weaker on D0: 38% exact, 69% within one strike.

**3b-T1 — are lump sales controller releases?**
* `v_` sell waves (orders on one right within 0.05 s), against the excess L − S just before.
* Reported: the share equal to the excess, and the share ≤ the excess.
* Also the share of `v_` sell lots made while L > S on that right.
* Compared with `h_` sell waves.

**3b-T2 — wing strike reference, refit on one half and scored on the other (exact share).** Candidate references:
* (a) X% of the ATM premium, X from H2's grid;
* (b) a fixed premium in ₹ {0.5, 1, 1.5, 2, 3, 4, 5};
* (c) a fixed distance in strike steps {5, 8, 10, 12, 15, 20, 25};
* (d) X% of the premium of the body short sold just before on that right.

**H6 rules and H8 (as planned).** For lump sales:
* a fixed clock (the training half's median first-sale minute);
* sell when L > S on that right;
* the end of the cycle's body activity.

Each is scored on lots at ±1 minute against a +30-minute shifted null. H8: the hedge AUC.
