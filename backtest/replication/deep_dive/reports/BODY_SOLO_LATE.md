# Algo 8 — after-15:00 solo sells: what drives them

*Investigation; plan `BODY_SOLO_LATE_PLAN.md`, written before the tests. In-sample: D-1 of 32 live cycles. "Late solo" means regular solo lots at or after 15:00: body `open_short` lots that are not part of a scheduled or reactive pair and are within 4 strikes of ATM. That is **336 lots, all single-lot orders, in 31 cycles**. Deep-OTM batch lots are excluded. Steps 6–8 were added after seeing results and are labelled post-hoc. Figure: `figures/bl_sl_summary.png`.*

## 0. Result

* **The late regime uses the same trigger as the intraday solo drip, with one extra input.** 65% of late solo lots are sold in a minute where the spot makes a fresh 15-minute extreme on the favourable side (CE on a new low, PE on a new high). Adding the sold option's **own premium making a fresh 15-minute low** brings this to **90%** of late lots (post-hoc). *Observed.*
* **Why it looks like a different regime.** Into the close, time decay and the fall in implied volatility push option premiums to new lows **without** a spot extreme. Late, such a minute is followed by a sale 29% of the time. Intraday the figure is 5%. Minutes with **neither** condition carry a sale 1.2% of the time late, against 0.1% intraday. So the late book reacts to the premium falling, not only to the spot. *The data observe this; the mechanism is inferred.*
* **Model.** Among the blocks fitted leave-one-cycle-out, **market variables alone reach AUC 0.82**. Adding every other block (clock, history, option volume, volatility, inventory, Greeks, order flow) lifts this only to 0.87. Greeks, inventory and order flow are each at chance (about 0.5) when used alone. *Observed.*
* **As a rule** with no fitted parameter, R3 ("spot fresh 15-minute extreme OR premium fresh 15-minute low") gives **F1 0.65** (precision 0.51, recall 0.90, ±1 minute). This is **below the 0.70 "decoded" bar**. Recall is high, but about half of the qualifying minutes have no sale. Nothing tested separates them well: earlier minutes, higher option volume and a recent sale only reach AUC 0.6. *Unresolved.*
* **Rejected:** overnight delta shaping (H1), financing the wings (H2), CE/PE inventory balancing (H3), and replacing a bought-back leg (H4). *Observed.*

## 1. Description (test 1)
* Late solo lots by minute show three spikes: **15:00 (56 lots)**, **15:23 (26)** and **15:29–15:30 (38)**. Share at a spot extreme: 82% / 35% / 21%. Share at a spot extreme or premium low: 93% / 88% / 63%. Share with a body buy-back within 60 s: 5% / 69% / 34%.
* The 15:00 spike is the drip itself: the first late minute picks up spot extremes. At 15:23 the lots not at a spot extreme (17) come from 3 cycles; most of these lots (82%) have a body buy-back within 60 s. In those cycles the sold premiums are at fresh lows but the spot is not at an extreme.
* Late solo lots: CE 54% of orders. The usual strike is 1 strike in the money.

## 2. Same trigger, stronger response late (test 4; premium rows post-hoc)
| condition (on the right) | intraday: minutes with it | intraday: P(sale) | intraday: share of sales | late: minutes with it | late: P(sale) | late: share of sales |
|---|---|---|---|---|---|---|
| spot fresh 15-min extreme (same minute) | 14% | 17% | 90% | 14% | 34% | 65% |
| ITM premium fresh 15-min low (same minute) | 14% | 17% | 88% | 11% | 40% | 59% |
| premium low **without** spot extreme | 4% | 5% | 8% | 5% | 29% | 21% |
| either (R3) | 18% | 14% | 97% | 19% | 32% | 86% |

P(sale) is per minute × right. Minutes with neither condition: P(sale) 0.1% intraday, 1.2% late.

Reading the table:
* Late sales still follow the market signal.
* Late, the response to the **premium** signal is about 5 times stronger.
* Late, the "no signal" sale probability is 10 times higher.

That pattern fits a tracker that watches the sold contract's premium as well as the spot. Into the close the premium decays even when the spot does not move.

Caveats:
* Both conditions use the **same minute's** true one-minute high/low. Inside a minute we cannot tell whether the extreme came before or after the sale (no ticks).
* The causal versions, using the previous minute, give recall 37% for the spot extreme and 32% for the premium low. So the same-minute alignment matters.
* Only 14% of late sales are priced within 0.2% of the minute low, so Algo 8's own fills are not what makes the premium lows.

## 3. Block models (test 5): late minute × right panel, 15:00–15:29, 1920 cells, 138 with a sale
| block | boosting AUC | logistic AUC |
|---|---|---|
| market | 0.815 | 0.819 |
| history | 0.643 | 0.567 |
| clock | 0.612 | 0.581 |
| micro | 0.548 | 0.545 |
| volatility | 0.495 | 0.53 |
| inventory | 0.515 | 0.452 |
| greeks | 0.504 | 0.482 |
| flow | 0.437 | 0.482 |
| all | 0.866 | 0.821 |

Strongest single variables (AUC): bk15 0.78, bk5 0.77, pos60 0.71, fav30 0.70, rsi_fav 0.69, fav15 0.69. These are fresh 15- and 5-minute extremes, position in the 60-minute range, the favourable 30-minute move and RSI. All of them are directional.

## 4. Linked to pairs, wings and buy-backs? (tests 2 and 5)
* **Wings follow, they do not lead.** A wing (`h_`) order follows within 10 s after 97% of late solo sales. That is the known deterministic follower, about 4 s after every sell. A wing order *before* the sale is rare and does not separate anything.
* **Buy-backs.** A cross-right body buy-back comes within 10 s of 17% of late solo lots. Earlier work counted the cross-right pairings: PE covered and CE sold, 231 order rows; CE covered and PE sold, 56; never the same right. Every one of those lots is already explained by a spot extreme or a premium low.
* **Per cycle.** Late solo lots rise with late buy-backs (ρ 0.45), wing closes (0.41), late reactive lots (0.48) and lumps (0.39). *Inferred:* that is the common driver, a moving market late in the day, which feeds every module. Inside the minute panel the order-flow block is at chance (AUC 0.48).

## 5. Portfolio hypotheses (H1–H4): rejected
| hypothesis | test | result |
|---|---|---|
| H1 overnight delta shaping | does the sale reduce whole-book |delta| (all modules)? | 47% late (intraday 28%); sale side opposes the book delta 50%; |delta| is not driven toward 0 into 15:30 |
| H2 financing the wings | late solo ₹ vs late long-premium ₹ per cycle | ρ 0.31 (p 0.08); solo ₹ is a median 3.2× the long ₹, so there is no matching |
| H3 CE/PE inventory target | sale on the lighter side? imbalance shrinks into the close? | lighter side 45%; imbalance shrinks in 56% of cycles; median |imbalance| 0.39 → 0.43 |
| H4 leg replacement | same-right roll after a buy-back? | none; cross-right pairings are all already explained by the extreme/premium-low trigger |
| H6 clock | fixed late times | the spikes at 15:00, 15:23 and 15:29 are explained by the trigger (section 1); clock block AUC 0.61 |

## 6. Rules (post-hoc; no fitted parameter; ±1 minute per cycle and right)
| rule | fires | positives | precision | recall | F1 |
|---|---|---|---|---|---|
| R1 spot fresh 15-min extreme | 266 | 138 | 0.541 | 0.717 | 0.617 |
| R2 ITM premium fresh 15-min low | 205 | 138 | 0.571 | 0.71 | 0.633 |
| R3 = R1 or R2 | 367 | 138 | 0.507 | 0.899 | 0.648 |
| R1 on previous minute (causal) | 271 | 138 | 0.498 | 0.696 | 0.581 |
| R2 on previous minute (causal) | 198 | 138 | 0.566 | 0.667 | 0.612 |
| R3 on previous minute (causal) | 366 | 138 | 0.484 | 0.884 | 0.625 |

Within R3-minutes, the variables that best separate sale from no sale (post-hoc):
| variable | AUC | AUC_even | AUC_odd |
|---|---|---|---|
| minute | 0.375 | 0.386 | 0.374 |
| vol_rel | 0.613 | 0.643 | 0.574 |
| min_since_last | 0.393 | 0.366 | 0.438 |
| bk60 | 0.586 | 0.633 | 0.544 |
| pos60 | 0.583 | 0.612 | 0.558 |
| react_min | 0.582 | 0.575 | 0.586 |


## 7. What this means for the D-1 reconstruction
* The after-15:00 class was scored F1 0 in the combined reconstruction. A single rule, R3, would cover it at about F1 0.65. That share of lots is small, so the combined D-1 F1 would barely move. The combined numbers in `D1_SELLING_RECONSTRUCTION.md` were **not** changed: R3 is post-hoc and was not pre-registered.
* **Still unknown:** which qualifying minutes get a sale (about half do), and how many lots each burst sells.

## Evidence labels
Observed: sections 1, 2 (tables), 3, 4 (counts), 5. Inferred: the premium decay / vol crush explanation, and the common market driver behind the per-cycle correlations. Unresolved: the selection among qualifying minutes, and burst size. Not testable: order of events inside a minute (no ticks); the algorithm's true internal premium reference.
