# First index-data trigger study

Record the candidate tests before running the joined study. Do not optimize an
indicator across these 35 cycles and describe the best fit as the original rule.

1. Initial entry: compare an expiry-calendar/09:16 baseline with opening gaps and
   the first completed minute. Eligible no-trade expiries are not fully known;
   observed dates cannot establish the absence of an entry filter.
2. Sold strike: compare the nearest 50-point NIFTY / 100-point SENSEX strike using
   the previous completed continuous-cash minute. Inspect the current minute's
   open as a boundary sensitivity, never its future close as a signal input.
3. Further allocations: test a 15-minute clock anchored at 09:16, allowing the
   anchor minute and two following minutes for recorded fills. Count actual
   paired opening-short minute/strike events, not child orders. Report off-clock
   events and missing clock opportunities; do not force all trades into the model.
4. Later hedges: test fixed strike distances against the prior log finding of
   concentrated executed premiums. Compare CE/PE purchases with index movement
   already observed, separating initial, routine and large late additions.
5. Exits: compare final short-book closure with the date-effective session and
   index path. A 4% position stop and 1% capital stop cannot be tested without
   contemporaneous option marks and a defined loss reference/denominator.
6. Economics: describe pre-expiry movement and expiry movement separately. Relate
   complete observed net-flow cash amounts to path range only as an exploratory
   association, conditional on zero opening inventory and before costs. Do not
   turn incomplete inventory, credit received, or static expiry payoff into P&L.

Use only completed continuous-session bars for candidate decision features.
Auction-phase observations remain distinct; do not forward-fill them. Bar labels
remain the documented start-label assumption. Event clocks may include latency.
Index data do not supply option IV, theta, spreads, Greeks or marked stop values.

Report June–September and October separately as a chronological replication
check. October has already been inspected; it is not an untouched holdout. Count
independent dates/cycles and retain every exception. Preserve original inputs.
