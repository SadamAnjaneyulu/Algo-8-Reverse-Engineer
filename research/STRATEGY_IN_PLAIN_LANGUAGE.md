# What the opening basket, later trades and exits mean

The normal opening is still a four-leg basket around 09:16 before expiry:
sell one CE and one PE at the same near-ATM strike, and buy an OTM CE and PE as
protection. They are separate orders, usually beginning seconds apart.

The earlier opening-sequence study finds the first four leg starts within
1–5 seconds on the 31 ordinary 09:16 dates. This is not atomic execution or
full-basket completion. On 13 July the first buys begin at 09:16:00, first sells
at 09:16:01, and that opening allocation's fills continue through 09:16:07.

For that 13 July NIFTY opening:

| Action | Contract |
| --- | --- |
| Sell | 24,000 CE |
| Sell | 24,000 PE |
| Buy | 26,000 CE |
| Buy | 22,000 PE |

Those initial protective wings are about 2,000 points from the sold strike.
SENSEX's initial wings show about 4,000 points earlier in the sample and 2,000
later. These are concentrated patterns with exceptions, not universal exact rules.

The strategy does not simply place four orders and leave the same four positions
unchanged until expiry. The logs show later additions, adjustments and exits.
The ₹2 NIFTY / ₹7 SENSEX observation describes **later routine new-long buys**;
it does not replace the initial-wing distance finding. Even for later buys, these
are price clusters and not a confirmed instruction to choose the closest premium.

Some cycles close near the end of expiry day; others close earlier. Some hedges
have no recorded closing trade and cannot be treated as observed square-offs.
Settlement and omitted opening inventory are separate reconciliation questions.
The 15:14 post-CAS exit concentration describes one late-exit pattern, not a
promise that all four original legs close then on every date.

## What we can say about where money came from

For the fully observed, zero-net-flow NIFTY cycle of **6–7 July**, trade accounting
over all of that cycle's recorded trades gives:

| Recorded position role | Round-trip result before costs |
| --- | ---: |
| Short option positions | +₹240,002.75 |
| Long option positions | −₹47,232.25 |
| Combined | +₹192,770.50 |

This assumes zero opening inventory and complete recorded fills. It includes
the changing book across the cycle, not just its first four legs. It is one
example, not a strategy win-rate or an aggregate return estimate.

It supports premium collection from the short-option trading as the profit source
in this cycle, with a cost from the long-option positions. It does **not** tell us
how much of the short profit came from time decay, IV changes, direction, strike
changes or timing. Nor does subtracting actual long losses simulate trading
without hedges: hedges may change margin, allowed size and risk behavior.

The actual alpha question is whether the entry/strike/adjustment/exit rules earn
more after costs and tail losses than a simple timed hedged-straddle baseline
at comparable risk and capital. Identifying those decision rules and comparing
them with that baseline remains necessary. Fast expiry decay alone is not proof.

Reproduce the role accounting with:

```sh
python research/analyze_profit_sources.py
python research/test_profit_sources.py
```

Full option-data tests are in `OPTION_TRIGGER_FINDINGS.md`. This explanation
does not change the observed normal opening sequence; it separates that opening
from the many later trades and from the still-unresolved exact trigger rules.
