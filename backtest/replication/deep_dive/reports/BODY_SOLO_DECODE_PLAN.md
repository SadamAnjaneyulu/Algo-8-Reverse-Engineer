# Solo sells (and reactive repeats / multi-lot entries) — decoding plan

*Written before the tests. Investigation only; in-sample (D-1 of 32 live cycles). Regular solo sells = body `open_short` lots not in a scheduled or reactive pair and within 4 strikes of ATM (deep-OTM batch sells, 6% of D-1 lots in 3 cycles, are reported separately).*

## Starting point
Your description: every minute, if the previous minute's close is a fresh 15-minute low (high), add a single CE (PE); otherwise nothing. As a rule that scores F1 ≈ 0.31; the richer earlier variables rank minutes well (AUC 0.95) but give F1 ≈ 0.45 as a rule. Your observation: solo sells come on **sudden highs/lows** and serve to **manage the running portfolio**.

## Blocks
* **A. Timing structure** of solo sales at the second level: gaps between consecutive sales on the same right (a polling period or fixed spacing would show as peaks), second of minute, clock phase (15/30-min), episodes and drips.
* **B. What happens between two consecutive solo sales on the same right** (inside an episode): spot move, move of the last-sold contract's premium (ratio to its sale price), change in book delta. A constant spacing in one of these is the signature of a ladder rule.
* **C. State at each solo sale vs matched control seconds** (same cycle, right, hour): fresh extremes on true one-minute highs/lows (N = 1–60), last-sold premium ratio, own/other book ratio, book net delta signed toward the right (portfolio management: after a fall the book is long delta and selling a call reduces it), CE/PE lot imbalance, spot move speed.
* **D. Forward-simulated machines** (state reset on each sale), scored like the reactive decode (lots, one-to-one, ±1 minute, out-of-fold parameters): fresh-extreme ladder, premium ladder, delta band (sell when signed delta exceeds a band, each sale moves delta by its own delta), combinations.
* **E. Reactive repeats and multi-lot entries:** what the number of lots in an entry and the repeat entries depend on (levels broken, channel width, book state, pace, other modules).

## Decision rules
A rule "decodes" the solo stream only if its out-of-fold lot-level F1 is ≥ 0.70; otherwise the best description is reported with its accuracy. Steps added after seeing results are labelled post-hoc.
