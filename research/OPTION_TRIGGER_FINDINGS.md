# Options received: first premium-selector and stop tests

All **3,243 requested traded-option contract-days** were received from the local
download in commit `9953c0d` and independently reproduced from their saved raw
responses in the cloud. No further credential entry or repeat bulk download is
needed for this observed-contract study.

This first pass improves the evidence and rejects overly simple reconstructions.
It does not yet identify the original selection/stop code or establish the
economic alpha. The earlier index result remains: 31/32 observed pre-expiry
initial entries start in 09:16 and match the nearest prior-minute index strike.

## Coverage and price agreement

| Data | NIFTY | SENSEX | Total |
| --- | ---: | ---: | ---: |
| Option contract-days | 1,445 | 1,798 | 3,243 |
| Observed candles | 545,979 | 684,086 | 1,230,065 |
| Contract-days with full minute grid | 1,315 | 1,728 | 3,043 |
| Contract-days with gaps | 130 | 70 | 200 |
| Missing minute slots | 5,266 | 684 | 5,950 |
| Logged fills with an event-minute candle | 19,904 | 21,517 | 41,421 |
| Fill inside candle range plus one tick | 19,575 | 20,945 | 40,520 |

Thus every recorded fill has a corresponding candle, and **97.8%** fall inside
that minute's low/high range with a 0.05 allowance. The 901 outside-range records
remain visible; event-time latency, trade-versus-quote differences and other
data issues are not resolved by this test. No timestamp shift is fitted to make
them disappear.

There are no zero-price bars. There are 29,391 zero-volume observations. Returned
prices on those bars are preserved, but they do not establish fresh executable
liquidity. Options use the derivatives session: 375 minutes before 3 August and
385 afterward, including the cash-market CAS transition.

## Conditional marked-position replay

The script rebuilds the actual observed cash flows and quantities across all
35 cycles, then marks active contracts with their exact observed minute closes:

```
marked equity = cumulative observed execution cashflow
              + sum(signed current quantity × observed option price)
```

These are conditional portfolio values assuming zero pre-log inventory and
complete recorded fills, before costs/funding/settlement. They are not a verified
account equity curve or returns on margin.

- 25,565 session-minute snapshots were evaluated.
- 107 snapshots are unavailable because an active contract lacks that exact
  minute. They are left blank; no prices are filled or carried forward.
- 5,005 snapshots have at least one active contract marked on a zero-volume
  candle, which is separately flagged.
- 24 cycles end with zero observed net contract flow; 11 retain contracts.
  Residual positions are not silently settled at zero.
- Cash amounts and residual inventories agree with the independent earlier
  log reconstruction for **all 35 cycles**.

The event-minute close is available only at the next minute boundary. The replay
therefore retains a separate immediately previous completed-minute mark before
the current minute's fills. At expiry 09:15, yesterday's close is not substituted
for a nonexistent 09:14 candle; opening marks are reported separately.

## Wing selection: premium concentration is not the complete selector

The routine cohort is stable inferred new-long buys from 09:18 inclusive to
14:45 exclusive, before expiry. Multiple fills in the same minute/strike/right
are grouped into one observation. This differs from counting child orders.

Test the previously recorded hypotheses of ₹2 NIFTY / ₹7 SENSEX against the
**previous completed** option close. For each purchase, compare its distance to
the target with other quoted OTM contracts of that right/expiry in the received
dataset. Require at least three candidates and include ties.

| Routine cohort | Minute/strike groups | Median selected prior close | Selected contract tied closest to target |
| --- | ---: | ---: | ---: |
| NIFTY | 1,181 | ₹1.90 | 233/1,181 (19.7%) |
| SENSEX | 1,306 | ₹6.65 | 387/1,306 (29.6%) |

The June–September / October counts are respectively 183/939 and 50/242 for
NIFTY, and 264/990 and 123/316 for SENSEX. October has already been inspected;
these are chronological comparisons, not blinded validation results.

The broad price concentration is real, but **“always buy whichever prior-minute
option is closest to ₹2/₹7” does not reproduce the chosen contracts**. A ceiling
or band, a dynamic target, delta/volatility constraints, liquidity or allocation
state remain alternatives. An intraminute quote-based nearest-price rule can
differ from this completed-minute test.

The candidate universe is restricted to contracts traded somewhere in these
cycles. It is retrospective and is not the full eligible chain. Quotes are trade
candles rather than bid/ask depth. These comparisons cannot establish which
unselected options passed the original liquidity and eligibility constraints.

Initial distance-based seed wings and large late long additions remain separate
behaviors. Do not apply one routine price target to all buying. The separate
₹5/₹20 late-premium columns in the detailed CSV are exploratory candidate tests,
not confirmed parameters.

## Loss exits: a simple portfolio threshold is not established

`Info.txt` states a 4% stop on carried positions and 1% on entire capital on
expiry day, with capital of ₹2 crore. The latter implies **₹200,000**, but the
loss reference, per-position/basket scope, accounting basis and monitoring
schedule are not specified.

The replay retains candidate comparisons against cycle-start equity,
previous-derivative-close equity and expiry-opening equity. ₹140k/₹150k cycle
loss candidates are exploratory, motivated by the observed closing cash amounts;
they are not confirmed replacements for the documented rule.

Examples with no final residual contracts:

| Expiry cycle | Prior completed-minute cycle equity near material closure | Final observed net cashflow before costs |
| --- | ---: | ---: |
| NIFTY 14 July | −₹143,523.25 | −₹142,944.75 |
| SENSEX 16 July | −₹141,041.00 | −₹141,580.00 |
| SENSEX 15 October | −₹127,706.00 | −₹149,911.00 |

“Material closure” is a descriptive terminal reduction to at most 5% of the
carried short quantity, after which it never exceeds that level again. This
helps distinguish large risk reductions from small trailing fills; it is not a
claimed strategy parameter. Exact final short-flat times are retained too.

For NIFTY 14 July, previous-day closing marked equity was +₹24,537.50; expiry
opening marked equity before fills was −₹113,581.00. At the completed 09:15
close it was −₹143,523.25, and material closure occurred at 09:16:12. That path
shows overnight repricing plus first-minute movement. It does not uniquely tell
us whether a carried-position stop, a portfolio stop or another control fired.

The OHLC adverse/favorable columns freeze the book before a minute and combine
each contract's extremes. Those extremes are not necessarily simultaneous and
can occur after an execution. They are diagnostic bounds, **not observed
portfolio losses or proof of an intraminute stop crossing**.

## Original carry: a separate 4% reference test

The analysis also separates original overnight shorts from fresh expiry-day
shorts with two allocation bounds: carried units covered first versus new units
covered first. Do not assume an expiry-day buy necessarily closes an old lot.

For 358 carried-short contracts with an observed previous-close reference:

- 204 have the same completion time under both allocation bounds.
- Of those, 122 have a price observation crossing 104% of the prior derivative
  close during the expiry session.
- 46 finish covering within 0–2 minutes after that candidate crossing.
- 42 finish more than ten minutes later; 18 finish before that price crossing.

This does not establish **a universal per-contract 4% stop relative to yesterday's
close**. The real reference might be entry premium, a straddle/basket value, an
allocation-specific basis or another measure. Close-based crossings can miss
intraminute highs. Completion times also differ from the first partial buyback.
These tests distinguish a specific hypothesis from the much less specific note;
they do not disprove the existence of its documented carry stop.

## What this changes about the investigation

The observed-contract data acquisition is finished. We can now study the actual
option-price path and exposure changes rather than explain every outcome with
generic theta decay or index direction. The strongest current reconstruction is
still time/calendar opening, near-ATM short allocations and distinct initial,
routine and late hedge behavior. The exact dynamic selector and stop reference
remain open.

The next discriminating work is comparing alternative selection constraints at
the decision time and identifying the stop's reference on original allocations.
Neighboring unselected contracts and quote-side liquidity may still be required.
Theta/IV/spot attribution needs an explicit pricing and attribution model; this
report does not turn marked trade-candle changes into a measured theta edge.
The supplied screenshot's earlier backtest period remains separate evidence.

## Reproduce

```sh
python research/analyze_option_triggers.py --plot
python research/test_option_trigger_analysis.py
```

The script validates every raw/CSV/metadata triple before analysis. Outputs:
`option_trigger_summary.json`, `option_marked_cycle_summary.csv`,
`option_minute_portfolio_replay.csv`, `option_premium_selection_checks.csv`,
`option_carry_stop_checks.csv` and the PNG/SVG evidence charts, all under
`research/outputs/`. Source data and original logs remain unchanged.
