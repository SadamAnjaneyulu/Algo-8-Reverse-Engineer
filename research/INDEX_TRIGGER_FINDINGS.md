# Algo 8: first results from the index-data join

This records the index-only stage. The subsequent options download and initial
marked replay are documented in `OPTION_TRIGGER_FINDINGS.md`.

The index download is complete for the requested study: **170 index-days, 85 per
index, 22 June–22 October 2026**. All 510 raw/normalized/metadata artifacts pass
hash and reproduction validation. There are 63,678 stored normalized bars.
Date-effective continuous-session coverage is complete; auction observations
are treated separately. Option-history bars were not yet available at this stage.

The strongest working reconstruction is a **calendar/time-based near-expiry
short-straddle program, with repeated allocations and multiple hedge behaviors**.
The opening ATM strike now has direct index evidence. The economic source of
returns and the exact adjustment/stop function remain unverified.

## Initial entry and sold strike

The analysis reads all 41,421 export records, cross-checks incremental quantities
and executed prices against cumulative order fields, and reconstructs opening
versus closing quantities. It finds 35 underlying/expiry cycles and 32 observed
pre-expiry dates with paired opening-short sales. Within-second role assignments
that change when source order is reversed are excluded from pair selection.

On **31/32 dates**, the first paired sale starts in **09:16 IST**. Those same
31 dates sell the nearest strike to the **09:15 bar's completed close**:

| Index | Nearest-strike grid | Initial observations | Exact prior-close rounding matches |
| --- | ---: | ---: | ---: |
| NIFTY | 50 points | 15 | 14 |
| SENSEX | 100 points | 17 | 17 |
| Total | — | 32 | 31 (96.9%) |

Examples:

| Entry date | Index | Prior completed index close | Nearest strike | Sold CE and PE strike |
| --- | --- | ---: | ---: | ---: |
| 13 July | NIFTY | 24,021.55 | 24,000 | 24,000 |
| 12 October | NIFTY | 22,633.00 | 22,650 | 22,650 |
| 21 October | SENSEX | 74,348.29 | 74,300 | 74,300 |

**Exception:** NIFTY on 5 October first pairs at 09:30:59, selling 22,600.
The last fully completed minute closes at 22,568.95, whose nearest strike is
22,550. Even the 09:30 minute open rounds to 22,550. A movement later in that
minute, a different decision reference, or other execution context could explain
this; the previous-minute proxy does not explain it and the exception is retained.

First entries occur after both rising and falling opening moves: 15 positive
and 17 negative completed opening-to-reference returns, ranging from −0.456%
to +0.256%. Initial entries also occur across sizeable opening gaps. This supports
testing the simple time/calendar baseline first. It does **not** establish that
there is no entry filter: the complete eligible no-trade expiry universe is not
established by observed trades alone.

The June–September block matches initial rounding on 25/25 observations; October
matches on 6/7. October was already inspected and is a replication check, not an
untouched test set. Nor does a matching prior close prove that the implementation
uses a one-minute close instead of a contemporaneous spot quote or another close
reference.

## Further sales: a clock pattern with exceptions

There are **1,087 pre-expiry minute/strike groups** containing stable inferred
opening shorts in both CE and PE. These are descriptive baskets, not confirmed
parent orders or independent strategy signals.

The recorded plan tests a 15-minute clock anchored at 09:16, allowing that minute
and two following minutes. It captures **639/1,087 groups (58.8%)**. Across 779
such opportunities on observed trading dates, 480 have a paired opening event.
Thus, “open another identical basket every 15 minutes” does not fully reproduce
the record.

The phase histogram also concentrates on the minute just before that window.
A descriptive sensitivity using each quarter-hour minute and its next two
minutes captures **878/1,087 groups (80.8%)**: 76.6% for NIFTY and 84.4% for
SENSEX. This alternative window was chosen **after** inspecting the phase counts;
it is evidence of clock concentration, not a validated new trigger rule.

The sold strike keeps following the moving index approximately, rather than
remaining fixed at the first strike. Using only the immediately prior completed
continuous minute:

| Index | Pair groups with usable prior index | Exactly nearest strike | Within one strike step |
| --- | ---: | ---: | ---: |
| NIFTY | 501 | 352 (70.3%) | 488 (97.4%) |
| SENSEX | 579 | 395 (68.2%) | 548 (94.6%) |

The other seven groups have no immediately prior completed continuous-session
bar; no stale index value is carried forward to score them. One-minute data
cannot resolve the index level at each second of an execution burst.

A simple direction sign does not separate the observed clock opportunities:
paired events occur at 225/362 (62.2%) opportunities when the completed return
from the open is positive, and 255/417 (61.2%) when it is nonpositive. These are
repeated observations within dates, not independent statistical trials. Other
thresholds, option-price rules and risk-state conditions remain possible.

## Bought strikes: separate the initial wings from later buys

The first new-long CE and PE buys in 09:15–09:16 on the 31 ordinary opening dates
give 62 seed observations. Gap means outward distance from that date's first
paired sold strike, which the index join now independently places at nearest ATM.

| Initial-wing cohort | Observations | Nominal gap | Exact | Near nominal |
| --- | ---: | ---: | ---: | --- |
| NIFTY | 28 | 2,000 | 19/28 | 26/28 within 100 |
| SENSEX before 16 September | 22 | 4,000 | 16/22 | 21/22 within 200 |
| SENSEX from 16 September | 12 | 2,000 | 12/12 | All exact |

This supports distance-based initial protection, with exceptions and a change in
the observed SENSEX configuration. It does not prove the exact date or cause of
that configuration change.

Later routine purchases have another useful signature. Counting stable new-long
fills from 09:18 inclusive to 14:45 exclusive:

| Index | Fill records | Median executed premium | Concentration |
| --- | ---: | ---: | --- |
| NIFTY | 1,357 | ₹1.95 | 917/1,357 (67.6%) within ₹1.50–₹2.50 |
| SENSEX | 1,496 | ₹6.70 | 1,312/1,496 (87.7%) within ₹5–₹9 |

These are executions, not the quotes seen at selection time. A roughly ₹2/₹7
premium-aware wing selector is plausible; delta, IV, liquidity and distance-cap
selectors remain competing explanations. Test neighboring **unselected** strikes
before declaring which function chooses the contract.

There are 39 descriptive large late new-long groups (at/after 14:45, at least ten
observed quantity-GCD units). Only 19 have an immediately preceding continuous
index bar; 20 occur later and are left unscored by this causal feature rule.
Among the 19, only four are CE purchases after an upward open-to-now move or PE
purchases after a downward move. The other 15 have the opposite orientation.
Therefore, “buy calls when the index rises and puts when it falls” does not
explain this cohort. This does not identify portfolio delta or the intended risk.

For example, 6 July adds 4,030 NIFTY 24,100 puts near 15:10 at a weighted ₹5.52
while the last completed index return from the open is approximately **+0.55%**.
Late buying may rebalance the book, protect against reversal/overnight scenarios,
or depend on option MTM. Those possibilities need the actual option-price path.

## Underlying economic reason: what is and is not supported

Selling near-expiry CE and PE collects time value, but its profitability depends
on the premium collected versus the subsequent movement, option repricing, wing
costs and trading costs. The useful hypothesis is **option carry/risk-premium
collection with active risk controls**, rather than treating rapid theta decay as
an independently established edge.

The joined paths show why the simple rule “directional day loses, sideways day
wins” is insufficient for this changing portfolio. For example:

| SENSEX expiry | Expiry continuous open-to-close move | Observed net cashflow before costs | Final short closure |
| --- | ---: | ---: | --- |
| 8 October | −1.69% | +₹328,620 | 15:14:40 |
| 15 October | +1.36% | −₹149,911 | 09:16:41 |

Both cycles finish with zero observed net contract flow and have observed
pre-expiry entries. Cash amounts are conditional on zero opening inventory,
complete fills and no external settlement; they are not verified net strategy
P&L. The daily moves continue after the second cycle exits and cannot be used to
explain its 09:16 decision. These examples reject a blanket directional-day label;
they do not prove a directional trading rule or a theta/IV attribution.

Only 22 cycles have both an observed pre-expiry paired entry and final zero net
contract flow. They are a selected subset; they must not be used to estimate the
whole strategy's win rate. Ten negative-cashflow cycles cluster between roughly
−₹139,000 and −₹154,000, suggesting a common loss-control question, but this
interval is an exploratory description. It does not verify the stated 1% stop:
1% of the documented ₹2 crore is ₹200,000, and the 4% carry-stop denominator is
unspecified.

The 15:14 late-exit concentration after the 3 August CAS change remains consistent
with leaving before the 15:15 transition. See `CAS_SESSION_FINDING.md`. Earlier
exits need option marks to distinguish portfolio stops, position stops, profit
targets and discretionary actions. Index returns cannot provide marked basket
loss or isolate theta from IV and spot/gamma effects.

The supplied backtest screenshot covers March 2025–May 2026, while these logs
cover June–October 2026. This analysis does not explain the screenshot's Sharpe
or reproduce its return curve.

## Next discriminating data and reproducibility

The index stage is finished. The next missing evidence is expired-option minute
history for the exact positions, plus neighboring eligible strikes at selection
times. Start with one NIFTY and one SENSEX contract/day to verify availability,
exchange mapping, hours, timezone and agreement with recorded fill prices before
expanding.

`outputs/next_option_sample_contract_days.csv` prepares **356 exact traded-contract
days across four cycles**, without making broker requests:

- NIFTY 6–7 July: positive cashflow and a large late put purchase after a rally.
- NIFTY 13–14 July: early expiry exit after a negative opening jump.
- SENSEX 7–8 October: a large expiry decline with positive observed cashflow.
- SENSEX 14–15 October: an early expiry exit with negative observed cashflow.

The manifest requests full-session one-minute prices for traded contracts. It
does not yet contain unselected neighbors, imply expired BSE derivatives support,
or provide a full-strategy backtest dataset. Selectors need neighbor quotes;
marked replay needs all held contracts and holdings over time. Do not enter keys
again merely to run this analysis.

Run from the repository root:

```sh
python research/analyze_index_triggers.py --plot
python research/test_index_triggers.py
```

The script is self-contained apart from the existing downloader/publisher and
standard library; optional plots require matplotlib. It preserves source files,
validates every stored data triple and cross-checks inferred fill fields. Tests
cover exclusion of the unfinished minute, rejection of stale auction references,
strike grids and later re-entry effects on final closure time.

The outputs retain source row references without copying account/order IDs:
initial entries/wings, all paired opening events, clock opportunities, cycle paths,
hedge events, the machine-readable summary, the next option sample manifest and
PNG/SVG evidence charts. Complete-session path features are clearly retrospective;
candidate decision features use only completed continuous-session bars.
