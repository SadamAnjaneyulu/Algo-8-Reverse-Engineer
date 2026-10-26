# Algo 8 — working trading rulebook, v0.1

**Purpose:** describe the strategy supported by the logs and supplied notes.
This is a research specification, not a fully decoded executable clone.
All clock times below are **IST**. The evidence covers June–October 2026;
contract sizes, expiries and exchange hours must be date-specific.

Labels: **Observed** = reconstructed pattern, with possible exceptions;
**Stated** = supplied in `Info.txt`; **Unresolved** = the exact rule is not known.
An observed pattern must not be mistaken for a universal original instruction.

## 1. Strategy structure and eligible sessions

| ID | Rule or condition | Evidence status |
| --- | --- | --- |
| C1 | Trade NIFTY and SENSEX options, with a hedged short CE/PE core. | Observed |
| C2 | Normally begin the carry cycle in the trading session preceding the selected expiry, and manage it into expiry day. | Observed; BTST description also stated |
| C3 | Use the actual listed expiry and exchange calendar. A holiday can move the expiry or make the previous trading session several calendar days earlier. | Observed calendar requirement |
| C4 | Do not assume the strategy is only four opening orders and four closing orders. It makes further trades on both days. | Observed |
| C5 | Eligibility/no-trade filters based on gap, trend, VIX, IV, RSI, VWAP, events or liquidity are not identified. | Unresolved |

The logs do not establish that all eligible expiries must be traded. No specific
indicator filter should be invented to fill that gap.

## 2. Initial entry

**E1 — Time:** normally start around **09:16 on the pre-expiry trading session**.
The first paired sale is in 09:16 on 31/32 observed pre-expiry opening dates.
The delayed 5 October entry is an exception, not a decoded second entry rule.

**E2 — Sold strike:** sell CE and PE at the same near-ATM strike for an allocation.
The best-fitting initial strike reconstruction is:

```
K = d × floor(S / d + 0.5)
d = 50 for NIFTY; 100 for SENSEX
S = the previous completed index minute's close, as a tested proxy
```

This matches the initial strike on the 31 ordinary 09:16 dates. The exact
decision quote, spot/futures reference and rounding implementation are unresolved.
Later allocations can use another near-ATM strike as the index moves.

**E3 — Initial protection:** buy an OTM CE above the sold strike and an OTM PE
below it. For the first seed wing on each side, observed nominal gaps are:

| Index / observed period | CE seed | PE seed | Qualification |
| --- | --- | --- | --- |
| NIFTY | About `K + 2,000` | About `K − 2,000` | Concentrated around these gaps, with exceptions |
| SENSEX, earlier observations | About `K + 4,000` | About `K − 4,000` | Deviations exist |
| SENSEX, observations from 16 September | `K + 2,000` | `K − 2,000` | Exact for the 12 first-wing observations in this cohort |

These describe the first observed seed wings. They do not determine every hedge
strike in every opening allocation. The date/cause of the original configuration
change and its premium/liquidity constraints are unresolved.

**E4 — Order sequence:** protection normally begins before the short sales, with
the four roles starting within 1–5 seconds on ordinary opening dates. Some starts
are interleaved. Full fills may take longer; this is not an atomic four-leg fill.
The original partial-fill, retry and rejection handling is unresolved.

**E5 — Four roles, potentially more contracts:** the opening can consist of
multiple allocations across neighboring strikes. At the 09:17 snapshot, 24/31
ordinary opening dates already have more than four nonzero contracts. “Four-leg
structure” means long CE, long PE, short CE and short PE roles; it does not
guarantee exactly four unique contracts or four exchange orders.

Example of a clean four-contract allocation, **13 July NIFTY**:

| Role | Contract | Quantity |
| --- | --- | ---: |
| Short CE | 24,000 CE | 195 |
| Short PE | 24,000 PE | 195 |
| Long CE protection | 26,000 CE | 195 |
| Long PE protection | 22,000 PE | 195 |

## 3. Position sizing

**S1 — Capital:** `Info.txt` states **₹2 crore**. This is not a verified account
balance or a decoded sizing formula.

**S2 — Observed opening quantities:** aggregate the reconstructed positions
strictly before 09:17 across all strikes in each role:

| Index | Common aggregate opening size | Exceptions / limitations |
| --- | --- | --- |
| NIFTY | 195 units in each of the four roles on 13/14 ordinary dates | 21 September has 325 per role |
| SENSEX | Short CE total 60 on 16/17 ordinary dates; normally 60 in the other roles too | 30 September has 40 per role; 14 October has CE totals 60 and PE totals 80 |

These are **observed aggregate quantities**, not “always buy 195/60 of one
contract.” Protection can be split among strikes. Execution quantities have
observed GCDs of 65 for NIFTY and 20 for SENSEX; that alone does not verify the
exchange lot size for another date or the number of original allocations.

**S3 — Subsequent size:** the book grows and changes during the cycle. The amount
and trigger of each addition, sizing as a function of capital/margin/premium,
maximum lots, maximum exposure and CE/PE quantity ratios are **unresolved**.
Equal opening-role quantities do not imply the later book stays equal-sized.

**S4 — No borrowed benchmark sizes:** the 2,600 NIFTY / 680 SENSEX quantities
used in the research benchmark were comparison-size calibrations. They are
**not Algo 8 sizing rules**.

## 4. Pre-expiry intraday management

**A1 — Further allocations occur.** The logs show new near-ATM CE/PE short groups,
covering/reducing positions and additional long options. New sales are often
clustered around quarter-hour boundaries, but there is no verified instruction
to add a basket unconditionally every 15 minutes.

**A2 — Routine later protection differs from initial seed protection.** Routine
new-long fill premiums cluster near **₹2 for NIFTY / ₹7 for SENSEX**, with changing
and asymmetric strike gaps. These values are **descriptive price clusters**.
“Buy whichever previous-minute option is closest to ₹2/₹7” fails to reproduce
most selections. The exact premium band, delta/IV/distance/liquidity selector and
reference quote remain unresolved.

**A3 — Late protection can be much larger or nearer the short strikes.** It must
be modeled separately from the initial wings and routine buys. The exact
overnight-hedge sizing and trigger are unresolved. Do not assign every late buy
to a confirmed trend, MTM or delta threshold.

**A4 — Carry:** reconstruct the full resulting inventory after the day's trades.
That resulting book, not just its first four orders, is what is carried. It can
contain several short strikes and extra long options. Some cycles close before
expiry and carry nothing.

## 5. Expiry-day activity and exit

**X1 — Manage carried positions and fresh positions separately.** Expiry day is
not merely liquidation of yesterday's basket. Inferred stable new short sales
occur on expiry day in 33/35 observed cycles. A buy may cover an old short, cover
a newly sold short or create a new long; its role must come from inventory.

**X2 — Early exits occur.** The strategy sometimes closes significant exposure
early in the session. The exact position-stop, portfolio-stop, profit-target
and re-entry conditions are unresolved. An observed exit does not establish
which control fired.

**X3 — Late exits occur.** In the post-3-August CAS period, 15:14 is a strong
observed late short-book exit pattern, just before the 15:15 cash transition.
Earlier-period late exits are more spread out, and exceptions remain afterward.
The universal final time-exit rule and its configuration history are unresolved.
The benchmark's fixed 15:14 cutoff is not proof of the original exit instruction.

**X4 — Closing sequence is not always simultaneous.** Short CE, short PE and
long wings can finish at different times. Some cycles leave net quantities in
the export, often long wings. A missing closing trade must be reconciled with
settlement or missing records before calling the entire book squared off.

**X5 — Profit-taking / trailing / post-stop entry lock:** exact levels, whether
entries resume after a stop, and the handling of outstanding opening orders
are unresolved. Do not invent a take-profit percentage or assume a permanent
entry lock from the currently available logs.

## 6. Risk-management rules supplied in the note

| ID | Stated rule | What can be specified | What remains unresolved |
| --- | --- | --- | --- |
| R1 | 4% stop on positions carried forward to expiry | A carried-position risk control belongs in the specification | 4% of entry premium, previous close, straddle/basket value or another reference; individual lots versus aggregate scope; reset and monitoring schedule |
| R2 | 1% stop on entire capital on expiry day | At stated ₹2 crore capital, 1% equals **₹200,000** | Loss from cycle start, prior close or expiry open; costs included or excluded; instrument/account aggregation; exact trigger and execution behavior |
| R3 | Protection accompanies short-option exposure | Initial OTM wings and subsequent long positions are observed | Original margin, net-delta/gamma limits, maximum loss budget, hedge ratios and emergency controls |

Do **not** turn the 4% carried-position statement into a ₹8 lakh capital stop.
Do **not** replace the documented 1% rule with a ₹1.4–1.5 lakh stop solely because
some losses cluster there. Nor does a 4% rise from yesterday's option close
consistently reproduce all observed carry-cover times.

Stops are conditions to submit exits, not guaranteed fill prices. The observed
overnight and intraminute price moves matter. Re-entry and pending-order behavior
must be specified before any executable version can apply those limits correctly.

## 7. Conditions that must remain explicit unknowns

| Required decision | Current status |
| --- | --- |
| Why one eligible expiry is traded and another is skipped | Unresolved |
| Whether the entry reference is spot, futures or another quote | Strong nearest-index-strike fit; exact reference unresolved |
| Exact initial-wing exception/configuration rule | Unresolved |
| Trigger for additional short allocations | Unresolved |
| Quantity for every new allocation | Unresolved |
| Later wing selector and large late hedge trigger | Unresolved |
| 4% carry-stop denominator and position/basket scope | Unresolved |
| 1% capital-stop accounting reference and scope | Unresolved |
| Scheduled final exit, profit targets and re-entry restrictions | Unresolved |
| Order failure handling, margin/exposure caps and settlement reconciliation | Unresolved |

These are parameters to discover, not permission to substitute familiar RSI,
VWAP, breakout, delta or fixed-premium rules without evidence.

## 8. Rulebook boundary and alpha status

The reconstructed structure is:

```
pre-expiry opening: start protected near-ATM short allocations around 09:16
pre-expiry session: add/reduce positions and change protection
overnight: carry the resulting inventory if still open
expiry session: manage carry, make further trades and reduce/exit exposure
after trading: reconcile actual residual positions and settlement
```

Only the structure and concentrated patterns are currently established. Several
decision functions remain unknown. This rulebook therefore cannot yet be
compiled into a faithful original Algo 8 without choosing new assumptions.

The first benchmark does not establish repeatable incremental alpha overall.
SENSEX's later trades outperform the tested frozen-basket baseline in both
research periods; NIFTY's do not. That is a research lead, not an inferred
“trade SENSEX only” rule or a promise of future results.

Evidence: [Info.txt](Info.txt),
[index trigger study](research/INDEX_TRIGGER_FINDINGS.md),
[option replay](research/OPTION_TRIGGER_FINDINGS.md),
[benchmark findings](research/HEDGED_STRADDLE_BENCHMARK_FINDINGS.md).
The opening quantities/contract counts are traceable by source row in
`research/outputs/rulebook_opening_allocations.csv`; the corresponding summary
is `research/outputs/rulebook_evidence_summary.json`.
