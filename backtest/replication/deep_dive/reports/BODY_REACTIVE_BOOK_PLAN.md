# Reactive pairs — is the trigger the state of the book? Pre-registered plan

*Written before any of the tests below were run. Investigation only; in-sample (D-1 of 32 live cycles). No engine/simulator change, no new alpha.*

## Why a new approach
Everything so far describes **price**: where the spot is relative to its range, and how long since the last pair. A range edge is only about half of the story: it is necessary-looking but fires a pair in a minority of cases, and a fixed "cooldown" has no economic meaning. A practitioner who runs a short-premium book on expiry-eve manages **the book**, not the chart: net delta, gamma, how far the spot has moved through the strikes already sold, running P&L, margin, and how rich premium is. A reactive pair is sold one strike *with* the move (ATM + 1 on a rise, ATM − 1 on a fall): the put at ATM + 1 is in the money (delta ≈ +0.6 for the seller) and the call is out of the money (≈ −0.4), so each such pair adds about **+0.2 lot of delta in the direction of the move** — what a seller who has become short delta after a rise needs, and the other way round. If that is the mechanism, the spacing between pairs is not a timer: it is the book delta being restored by the previous pair, and not every range break needs a pair because the book may already be neutral.

## Hypotheses (all fixed now)
* **H1 delta re-centring:** a pair fires when the book's net delta, signed against the move, is large (book is short delta after a rise / long delta after a fall), and each fire reduces it.
* **H2 book breach:** a pair fires when the spot moves through or beyond the outermost short strike of the existing book on that side (the book is "in the money").
* **H3 premium/vol richness:** a pair fires when the premium at the target strike (or the ATM straddle, i.e. implied σ√T) has jumped or is rich relative to its own recent range.
* **H4 P&L / exposure state:** a pair fires depending on running mark-to-market P&L (normalised by ₹ 2 crore), recent P&L change, gross short lots, or in-the-money short lots.
* **H5 other-order coupling:** hedge/stop/lump/buy-back orders change the book (35% of pairs come within 60 s of one); their effect on delta explains the coupling.

## Data and construction
* Book at time t = all orders of the cycle (every module) with te < t − 3 s on D-1 (the book starts flat at the open, as the first orders show), net lots per (CE/PE, strike). Lot unit per cycle from `bl_size_cycles.csv`.
* Greeks: σ√T from the ATM straddle close (σ√T = straddle / (0.7979 × spot)), Black–Scholes delta/gamma with r = 0 per strike from that single σ√T (no smile). Option prices are the last **completed** minute close; spot is the live proxy (seconds table) or the completed close (minute panel). Delta in lots-equivalent (Σ net lots × delta), gamma in lots-equivalent per index point, ₹ notional = delta × unit × spot.
* MTM P&L = cash flows of all fills (fill average price) + marks at the last completed minute close; normalised by ₹ 2 crore.
* Tables: (S) the 363 reactive pairs vs 10,890 random control seconds in 10:30–15:15 (as in earlier studies); (M) the 9,152 cycle-minutes panel (label = pair in the minute).

## Tests
**A. Single variables.** AUC (S) of each state variable and of its absolute value; hazard by decile; each also within the range-edge population (position beyond ±0.5 of the 60-minute range) so that book variables are judged *given* the edge. Variables: net delta (signed and signed against the move side), |delta|, gamma, short lots, ITM short lots, distance to the outermost short strike on the move side and on the opposite side, MTM P&L, P&L change over 5/15/30 min, σ√T and its change over 5/15/30 min, target-strike premium and its position in its own trailing range, premium per ₹ of spot.
**B. Mechanism.** Effect of each reactive pair on book delta (before → after, in lots): share that reduce |delta|, share placed when the book is exposed against the move, and the same for scheduled pairs and random seconds.
**C. Block models.** Leave-one-cycle-out logistic and gradient boosting on (S) and (M): edge-only vs edge + book greeks/exposure vs edge + premium vs edge + P&L vs everything; paired cluster-bootstrap AUC gains. A block "explains non-firing" if it adds ≥ 0.03 AUC with a CI excluding 0 in both cycle halves.
**D. Rules (M).** Teacher-forced rule evaluation on pair-minutes with ±1-minute tolerance and thresholds chosen on the other cycle half: (i) delta rule, (ii) range edge AND delta rule, (iii) range edge + best book variable, vs the range edge + refractory machine of the previous study (F1 0.49) and the stateless range edge (F1 0.34). **Success** = out-of-fold precision and recall both ≥ 0.6 for pair-minutes (±1 minute) **without** any refractory timer.
**E. Time-aligned plot** of one cycle: book delta, ITM short lots/P&L and premium state through the day with every reactive pair and other-module orders marked.

## Evidence rules
Observed / Inferred / Unresolved / Not testable. Any step added after seeing results is labelled post-hoc. The number of variables and rules examined is reported. No metric added to improve any score.

## Not testable (stated in advance)
True implied volatility per strike (smile) and exact broker margin; the real internal state of the algorithm; tick timing.
