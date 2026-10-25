# Closing-auction structure changes the data validation and strategy questions

The fixed 375-minute validation rule was too strict for the whole study. It treated
15:16–15:19, and sometimes 15:29, as missing ordinary cash-market minutes after
the Closing Auction Session (CAS) had changed the trading phases.

## Primary evidence

SEBI's [16 January 2026 circular](https://www.sebi.gov.in/sebi_data/attachdocs/jan-2026/1768576287344.pdf),
effective **3 August 2026**, provides:

- Paragraph 4.2.1: transition from continuous trading at 15:15–15:20; auction
  order entry begins at 15:20; matching is 15:30–15:35.
- Paragraph 4.2.2: auction entry closes randomly between 15:28 and 15:30.
- Paragraph 4.2.3: equity derivatives continue trading until 15:40.
- Paragraph 6.1: CAS implementation starts 3 August 2026.

SEBI's [September consultation paper](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2026/1789202841824.pdf)
corroborates the then-existing framework: page 13 explicitly compares the old
15:30 continuous close with the current 15:15 close for CAS stocks and 15:40
derivatives close. Its proposed alternatives are not applied retroactively here.
Source hashes and the bounded study policy are in `market_sessions_2026.json`.

The absent 15:16–15:19 observations align with transition, while a missing 15:29
observation is compatible with the random auction close. This does not prove
why a vendor emitted or omitted each individual quote. Auction observations
must not be assumed to be continuously executed cash-market prices.

## What the received data and logs show

Among 154 received index sessions through 9 October:

- 58 precede CAS and 96 follow its introduction.
- In 95 of the 96 post-CAS sessions, the four provider bars at 15:16–15:19
  are identical flat OHLC observations. These are provider records, not fills
  manufactured by our analysis. The other session is preserved without being
  forced into that pattern.
- All 420 trade-log event timestamps after 15:30 occur after CAS implementation
  and before 15:40. They fall inside the documented derivatives session. Earlier
  reports calling them potentially outside normal hours were based on the old
  cutoff and need that correction. Exact execution-versus-notification semantics
  still cannot be established solely from this export.

For reconstructed final short-book closures, split by the actual rule-change date:

| Cohort | Reconciled short-book closures | Closures at/after 15:00 | Of those, closures in 15:14 |
| --- | ---: | ---: | ---: |
| Before 3 August | 10 | 7 | 0 |
| From 3 August | 19 | 10 | 9 |

The late-exit definition (at/after 15:00) is descriptive; it is not a confirmed
normal-exit classifier. These counts do not say that 90% of all exits occur at
15:14, or prove a programmed trigger. They make a deliberate exit before the
15:15 transition an important hypothesis to test against risk exits and other
candidate rules.

## Corrected data contract

- Before 3 August: require all 375 continuous-cash minute starts from 09:15
  through 15:29 IST.
- CAS-period version 2: require all 360 continuous-cash minute starts from
  09:15 through 15:14. Preserve actual subsequent provider observations through
  15:39, with `session_phase` labels for transition, order entry/random close,
  matching and post-auction. No missing price is synthesized.
- Missing continuous-session minutes, wrong series, malformed prices and
  duplicates still fail. Lack of a fixed one-minute grid during auction phases
  is not automatically a continuous-market data failure.
- Existing version-1 files/hashes remain immutable and are not duplicated.
  They need date-effective phase interpretation when used for market features.
- New metadata status is `continuous_cash_complete_with_observed_auction`.
  The legacy `regular_session_bars` field is the observed row count, not a claim
  of 375 ordinary tradable minutes.

This policy is scoped to the current study, ending 22 October 2026. Later rules
need a newly verified session snapshot.

## Why it matters to the alpha investigation

Expiry-day closing and settlement mechanics add risk beyond generic time decay.
The original circular also changes how constituent closing prices feed index
derivative settlement. A frozen displayed index during transition is not proof
that options are riskless: derivatives still trade while auction information and
the eventual closing price can change exposure.

Separate continuous-session returns/variance from auction and settlement changes.
Do not count flat transition observations as evidence that the underlying was
economically low-risk throughout the closing process. Test whether the strategy's
15:14 behavior is auction-risk avoidance, while using option marks and holdings
to examine the separate effect of theta, IV, directional risk and hedge costs.

The 16 local raw responses from 12–22 October should first be revalidated offline
under this date-effective contract, then pushed. No broker credential, fresh
request, interpolation or replacement of original raw responses is required.
