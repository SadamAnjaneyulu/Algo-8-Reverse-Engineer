# Algo 8 — consolidated findings and remaining work

This is the current overview, reconciling the research from the original logs
through the mass matching and rule refinements. Treat Algo 8 as automated:
unresolved means its programmed rule has not yet been recovered.
All trading times below are **IST**.

**Current reconstruction:** start protected near-ATM short allocations before
expiry, build positions at recurring times, make additional trades and change
protection, carry the resulting inventory, then manage carried and fresh
positions on expiry day. The complete decision code and economic alpha are
not yet established.

## 1. Evidence available

| Evidence | What we have |
| --- | --- |
| Trade export | 41,421 records across 35 expiry cycles; 32 observed pre-expiry opening sessions |
| Index data | 170 validated index-days; 63,678 stored minute bars |
| Options data | 3,243 traded-option contract-days; 1,230,065 minute candles |
| Fill-price check | All recorded fills have an event-minute candle; 97.8% fit its range within one tick |
| Position/P&L reconstruction | 25,565 session-minute snapshots; role ledgers reconcile to the original full-book marks |
| Rule matching | 71,720 calibration parameter/context comparisons, with chronological later-cycle checks |

These are not 71,720 independent experiments. Later data had already been
inspected, some hypotheses were introduced after exploration, and the option
universe contains traded contracts rather than the full historical chain.
Trade field meanings are inferred and internally cross-checked. Missing prices
are not filled to manufacture marks or returns.

The supplied backtest screenshot covers **3 March 2025–27 May 2026**, whereas
the analysed logs cover **June–October 2026**. We have not reproduced the
screenshot's 47.22% return, 36.88% CAGR or 2.19 Sharpe from matching-period data.

## 2. Strong findings supported by the observed logs

| Part of the strategy | What is established | Boundary |
| --- | --- | --- |
| Instruments and structure | NIFTY/SENSEX options with short CE/PE allocations and purchased CE/PE protection | The book can hold many contracts and allocations |
| Initial timing | First paired sale around 09:16 on 31/32 pre-expiry opening dates | 5 October is a delayed 09:30 exception |
| Initial sold strike | Same near-ATM strike for CE/PE; nearest preceding index close matches all 31 ordinary starts | Exact live quote and rounding implementation remain unknown |
| Initial wings | NIFTY seed gaps cluster near ±2,000; earlier SENSEX near ±4,000; later SENSEX from 16 September near ±2,000 | These are seed-wing patterns with exceptions, not all later hedge gaps |
| Opening execution | Protection usually starts before shorts; the four roles start within about 1–5 seconds | Full fills can take longer and can interleave |
| Multiple allocations | 24/31 ordinary opening books already have more than four nonzero contracts at 09:17 | Four option roles do not mean exactly four orders/contracts |
| Common opening size | NIFTY normally 195 units per role; SENSEX commonly 60, with documented exceptions | Aggregate across strikes, not necessarily one contract per role |
| Repeated order size | Pre-expiry fresh-short parents request 65 NIFTY units in 2,022/2,032 cases; 20 SENSEX units in all 2,375 cases | Several parents can arrive together; not the complete sizing formula or verified lot rules for other dates |
| Later sold strikes | Later allocations change strike instead of always retaining the opening strike | Scheduled and extra sales need separate selectors |
| Fresh protection | New outward CE and PE buys occur near most paired-short batches | Temporal/inventory associations do not establish complete risk coverage |
| Expiry activity | Fresh short sales occur on expiry in 33/35 observed cycles | Expiry day is more than liquidation of the carry |
| Exit behaviour | Both early and late reductions occur; 15:14 is a concentrated late short-exit pattern in the post-3-August period | No universal final exit time has been decoded |
| Closure and renewed exposure | Ten cycles have fresh-short fills after the short book first reaches zero; four also have later order-label minutes | Closure reason, new-entry permission and pending-order handling remain distinct unknowns |

### The recurring pre-expiry schedule

Every observed pre-expiry session has a fresh same-strike short CE/PE pair around
each of these **17 windows**:

| Window starts | Observed recurrence |
| --- | --- |
| 09:30, 09:45 | 32/32 sessions at each time |
| 10:00, 10:15, 10:30, 10:45 | 32/32 at each time |
| 11:00, 11:15, 11:30, 11:45 | 32/32 at each time |
| 12:00, 12:30 | 32/32 at each time |
| 13:30, 13:45, 14:00, 14:15, 14:30 | 32/32 at each time |

This is **544/544 observed session-window occurrences**. A window spans two
seconds before the stated time until three minutes afterward. The delayed
5 October opening overlaps 09:30; this is not a count of 544 extra four-leg
baskets on top of completed opening baskets.

12:15, 12:45, 13:00 and 13:15 are less consistent. The 13:15 pattern changes
over the sample. The cause of that change has not been decoded.

This schedule is established for **pre-expiry**. Later-period expiry sessions
contain fresh pairs in only 157/273 tested quarter-hour opportunities. The algo
does not simply add every 15 minutes unconditionally on both days.

### Fresh hedge purchases around later sales

Within the studied 09:18–14:45 band, both outward CE and PE new-long parents
occur within five seconds of these paired-short batches:

| Index | Pre-expiry | Expiry |
| --- | ---: | ---: |
| NIFTY | 497/535 (92.9%) | 615/839 (73.3%) |
| SENSEX | 535/595 (89.9%) | 256/303 (84.5%) |

Existing long options also protect the book. Both outward long rights are
present shortly afterward in all these pre-expiry batches. A missing fresh
paired purchase within five seconds does not imply an unhedged position.

### What the exposure study supports

All 31 modeled ordinary opening books have positive theta, negative Vega and
negative gamma. Time decay helps if other factors stay fixed; IV increases and
sharp moves can hurt. A loss does not require IV to rise.

Most modeled new-short addition batches increase short-Vega exposure; most
large late long-adjustment batches reduce its magnitude. Thus middle trades
have different jobs: building premium-selling exposure and changing protection.
They must not all be called risk-reducing adjustments. Scheduled additions
occur with spot moving either way, and with reference premiums/IV rising or
falling. No IV-rise-only or proven range-forecast entry rule has been found.

## 3. Strong candidates, still incomplete

### Candidate A: routine hedge budget proportional to ATM premiums

For routine pre-expiry protection, the strongest current reconstruction is:

```
CE budget ≈ 2.5% × current ATM CE premium
PE budget ≈ 2.5% × current ATM PE premium
select outward strikes using each side's premium budget
```

Earlier calibration selects a ceiling-style premium selector for both indices;
the refined SENSEX version rounds the budget to nearest ₹0.10.

| Later pre-expiry check | NIFTY | SENSEX |
| --- | ---: | ---: |
| Exact bought strike | 316/637 (49.6%) | 321/623 (51.5%) |
| Exact or adjacent strike | 586/637 (92.0%) | 589/623 (94.5%) |

An adjacent strike is one 50-point NIFTY / 100-point SENSEX step. These are
partial selector matches, not exact-code recovery. A SENSEX expiry variant
matches 526/806 (65.3%) exactly; NIFTY expiry refinement is less stable.
Do not apply one routine hedge rule to every seed or late purchase.

The older ₹2 NIFTY / ₹7 SENSEX observations are **price clusters**, not confirmed
fixed targets. A relative budget fits substantially better and explains why
both premium targets and strike gaps can move.

### Candidate B: extra pre-expiry straddles shift toward recent movement

Conditional on an extra sale occurring outside the scheduled windows:

```
candidate sold strike = nearest ATM + one strike step after a rise
candidate sold strike = nearest ATM − one strike step after a fall
```

Earlier-selected lookbacks are 10 minutes for NIFTY and 15 for SENSEX. Later
exact-strike matches are **33/39 NIFTY (84.6%)** and **26/34 SENSEX (76.5%)**.
This is a useful directional-placement lead. It does **not** identify the
trigger time, establish the exact original lookback, or prove profitable alpha.
The hypothesis was introduced after inspecting the data.

## 4. Risk controls supplied in the note

| Stated control | Known | Still to decode |
| --- | --- | --- |
| 4% stop on positions carried into expiry | A carry-specific control is stated | 4% of which price/value; individual leg, allocation or basket; reference/reset time |
| 1% stop on entire capital on expiry | With stated ₹2 crore, the amount is ₹200,000 | P&L reference, included positions, accounting scope, monitoring, re-entry/cancellation behaviour |

These are supplied specifications, not execution-verified formulas. Do not
replace them with a fitted 0.5% rule or reinterpret the carry 4% as 4% of capital.
The tested simple interpretations fail many observed exits.

## 5. What still needs finding, in priority order

| Priority | Missing programmed decision | What would resolve it |
| --- | --- | --- |
| 1 | **When extra entries fire** | An event/state rule that explains actual extra orders and stays quiet at comparable no-order times; directional strike fit alone is insufficient |
| 2 | **Complete exit/re-entry controller** | Distinguish carry exits, fresh-position exits, portfolio stop, profit-taking, time exit and pending-order handling; match first and final closures separately |
| 3 | **Exact hedge selection and late protection** | Reproduce exact strikes, quote timing, rounding, liquidity constraints and the size/trigger of large late purchases |
| 4 | **Sizing and exposure limits** | Explain how many 65/20-unit orders are submitted, total lots, maximum exposure, margin/capital allocation and later CE/PE ratios |
| 5 | **Eligibility and configuration changes** | Explain skipped/delayed starts, the SENSEX seed-wing change, schedule changes and date-specific calendar behaviour |
| 6 | **Economic alpha and original backtest** | Test a sufficiently specified reconstruction on independent data with costs and comparable risk; reconcile the screenshot's earlier period/configuration |

The mass RSI/EMA/Bollinger/ATR/ADX/Supertrend/breakout/price/IV searches did not
recover a simple universal trigger or exit instruction. That does not exclude
combinations, allocation-specific state or intraminute controls. No missing
function should be replaced by the highest-fitting historical threshold.

## 6. What the alpha comparison says

The earlier frozen-basket comparison tests trading **after a shared opening
selection**, not whether the opening calendar/strike selection itself has an
edge. Its size/risk matching is approximate; margin and tail risks are not equal.

SENSEX's later activity beats that tested baseline in both research periods;
NIFTY's does not. Combined performance changes sign between periods, and the
later uncertainty interval includes no advantage. Repeatable incremental alpha
has therefore **not been established overall**. This is separate from the
strong execution patterns and the screenshot's reported performance.

## 7. One real cycle makes the structure concrete

Actual NIFTY selections on 13 July:

| Time | Sold CE and PE strike | Nearby bought CE | Nearby bought PE |
| --- | ---: | ---: | ---: |
| Around 09:16 | 24,000 | 26,000 | 22,000 |
| 09:31 | 24,050 | 24,800 | 23,300 |
| 09:46 | 24,100 | 24,750 | 23,250 |
| 13:30 | 24,150 | 24,700 | 23,000 |

The four roles can execute seconds apart. The opening's fixed-distance seed
wings give way to changing later protection. The portfolio carried overnight
contains the accumulated surviving positions, not just the first four orders.

## Sources

- [Working trading rulebook](ALGO8_RULEBOOK.md)
- [Initial index and entry study](research/INDEX_TRIGGER_FINDINGS.md)
- [Option replay and initial hedge/stop tests](research/OPTION_TRIGGER_FINDINGS.md)
- [Repeated addition windows](research/ADDITION_PATTERN_DISCOVERY_FINDINGS.md)
- [Mass rule matching](research/MASS_RULE_MATCH_FINDINGS.md)
- [Hedge rounding, P&L scopes and closure episodes](research/RULE_REFINEMENT_FINDINGS.md)
- [Theta/IV/movement study](research/IV_THETA_HYPOTHESIS_FINDINGS.md)
- [Benchmark and its limitations](research/HEDGED_STRADDLE_BENCHMARK_FINDINGS.md)
- [Supplied capital and stop note](Info.txt)
