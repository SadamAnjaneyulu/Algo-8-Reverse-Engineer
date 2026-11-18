# What the observed positions actually do

**Entry-label correction:** earlier “27 suppressed” opportunities lack a
same-strike CE/PE pair, but 18 contain new short sales and only nine are empty.
The newer [allocation/side study](ALLOCATION_SIDE_FINDINGS.md) separates those
outcomes and removes early timer fills from the new off-schedule definition.
The overlapping-inventory and 13 July observations below remain valid.

The original Algo 8 entry/exit causes remain the objective. The current evidence
supports **overlapping protected short allocations with separate reductions**,
not replacing the complete portfolio every 15 minutes. All times here are IST.

## The 09:30 basket usually adds to the earlier positions

Audit the 17 established pre-expiry windows on all 32 observed sessions. In
**544/544 windows**, at least some prior short exposure and prior long exposure
necessarily survive the window. Net short quantity increases in **530/544**.
The bounds conservatively attribute every opposite-side fill on an old contract
to consuming its old inventory first. They require no guessed basket IDs.
The window runs from two seconds before the timer to three minutes after it.

This proves retained older exposure, not that every prior lot survives or that
every newly sold strike is exactly the nearest spot ATM. Later strikes change;
scheduled and extra sales still require distinct selection models.

Actual 13 July NIFTY inventory makes the overlap explicit:

| Snapshot | Original 24,000 CE short | Original 24,000 PE short | Original 26,000 CE hedge | Original 22,000 PE hedge | All short quantity, CE+PE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 09:17 | 195 | 195 | 195 | 195 | 390 |
| 09:33 | 195 | 195 | 195 | 195 | 650 |
| 09:48 | 195 | 195 | 195 | 195 | 1,105 |
| 10:03 | 0 | 195 | 0 | 195 | 975 |

The short columns show absolute quantities. The stored CSV retains signed
inventory. Multiple additions and other trades can occur between snapshots;
these are actual contract inventories, not an asserted one-basket-per-window
allocation map.

The original CE shorts are covered in 65-unit pieces at **09:50, 09:53 and
09:59**, while 65-unit 26,000 CE hedges are sold at each of those timestamps.
The original PE short/hedge contracts remain. Opening CE sale prices were
₹90.10, ₹89.75 and ₹88.20; CE buyback prices were ₹139.20, ₹145.50 and ₹155.20.
These CE reductions occur at worse premiums than any of those opening sales.
The hedge-sale premiums are also below their ₹0.55 opening purchase premium.
This is a concrete loss reduction on that side, not a profit exit after every
quarter-hour entry. No unique entry/exit parent allocation is asserted.

This is a useful lead for **separate CE-side/PE-side or allocation-level risk
control**. It does not identify the exact stop percentage or rule. Different
initial parents closing minutes apart also need explaining. A percentage
inferred from one day's fill prices is not an original stop threshold.

## Expiry day also contains new short allocations

Stable fresh short sales occur in **33/35 observed expiry cycles**. Expiry day
includes fresh selling, protection changes and covers. It is not only adjustment
and liquidation of yesterday's book. Later-period quarter windows have additions
in 157/273 opportunities. Requiring the actual prior short book to be active
explains 157 additions and predicts 27 that do not occur; the complete controller
is still unresolved.

Closures occur early as well as late. Some residual contracts, often long wings,
remain in the export, so it is not established that all four roles always close
together or that every contract is traded out at expiry close. Settlement and
missing-record handling must remain explicit.

## A range-friendly payoff does not identify a range-forecast filter

Normal paired starts are around **09:16**, after the 09:15 candle completes,
on 31/32 observed pre-expiry opening dates. The protective four roles begin close
together, typically within seconds; actual parent fills can take longer and
there can be several parents/strikes per role.

We cannot yet say “an opening spike means no entry.” Observed counterexamples:

| Entry | Completed 09:15 candle high–low range / opening price | Candle open-to-close move | First paired sale |
| --- | ---: | ---: | --- |
| NIFTY, 28 September | 0.464% | −0.456% | 09:16:01 |
| SENSEX, 7 October | 0.391% | −0.370% | 09:16:01 |
| NIFTY, 20 July | 0.375% | +0.256% | 09:16:01 |

These are observed magnitudes, not an inferred definition of a spike. They rule
out an unconditional ban on moves of these magnitudes, not every possible gap,
volatility or trend filter. The export contains observed entry dates; it does
not label all eligible no-trade dates or their reasons. Observed no-entry dates
cannot automatically be labeled “filter rejected” rather than missing history.

Trading at a predefined pre-expiry time is itself an entry condition. A premium
seller can trade a calendar/volatility-risk premium and manage adverse moves
without a per-entry indicator claiming the market will stay in a range. A
range forecast and a time-based risk-premium strategy are competing explanations.
The latter is currently a plausible working hypothesis, not established alpha.
The repeated schedules and additions during both rises and falls support testing
it; they do not prove profitable expected returns.

## Exits happen with both positive and negative whole-book P&L

Among 27 material reductions with available prior-minute whole-book marks,
**15 have positive and 12 negative P&L** before costs. Examples:

| Material reduction | Prior completed-minute net cycle mark, before costs |
| --- | ---: |
| SENSEX 10 September, 13:37:29 | +₹229,304 |
| NIFTY 13 October, 09:18:11 | −₹117,332 |
| SENSEX 17 September, 15:14:32 | −₹36,129 |

These are not exact exit-fill P&Ls, completed-cycle returns or identified exit
reasons. A positive whole-book mark can coexist with a loss in one allocation;
a losing timed exit does not establish that a stop caused it. Distinguish the
condition that requests an exit, the fill time, the P&L reference and its scope.

## The next test should identify the controller's decisions

1. Keep the supported opening/timer schedule as the baseline. Test an additional
   market filter against explicit comparable no-entry opportunities. Do not
   assume a range indicator must exist.
2. Track short CE and PE allocations and their associated long protection, with
   alternative associations when shared strikes and timing prevent unique IDs.
   Test the first reduction of each side, not only whole-book liquidation.
3. Separate carry and fresh risk references. Test per-leg, paired-premium and
   hedge-inclusive P&L triggers, then re-entry and pending-order behavior.
4. Require both 80–90% signal precision and broad event coverage, including
   false signals at no-action opportunities. Match first decisions separately
   from continuation fills and final closure.
5. Evaluate the recovered controller against timed protected selling after
   costs and comparable risk. Order matching is not economic alpha.

The targeted casebook already holds the 27 suppressed active-book expiry
opportunities, 265 later extra-entry minutes and four failed aggregate-stop
cycles. The new `lifecycle_initial_short_first_covers.csv` adds opening-short
first-cover contexts and flags later same-contract additions that contaminate
an initial-cost reference. Its retrospective exclusions cannot be used as
real-time entry rules. These are concrete controller counterexamples rather
than another claim that a high historical fit identifies the original code.

Reproduce this audit with `python research/clarify_position_lifecycle.py`.
Source evidence is in `lifecycle_*.csv` and `lifecycle_summary.json` under
`research/outputs`. Three retention-bound tests were added; all 136 tests pass.
