# Algo 8: combined-rule search and historical curve fits

The combined search ran **15,906,565 new calibration rule/parameter/context
comparisons**, in addition to the previous 71,720. It produced executable
historical mimics and explicit, partially matching candidate rules. **It did
not identify the original extra-entry trigger, complete exit controller or
repeatable incremental alpha.** Treat the strategy as automated throughout.

All trading times are IST. This study uses the June–October 2026 export and
the stored index/traded-option minute candles. The backtest screenshot covers
a different period, March 2025–May 2026, and is not reproduced here.

## What was searched

| Search | Calibration comparisons/settings |
| --- | ---: |
| Indicator + actual prior portfolio/order state, AND/OR and temporal combinations | 132,922 |
| Additional option volume, PCR, OI and price/OI combinations | 75,804 |
| Composite loss/profit/trailing/time exits, across accounting scopes and closure targets | 15,636,600 |
| Conditional hedge-budget branches | 1,655 |
| Allocation-quantity model settings | 48 |
| Joint entry/exit-lock programs | 51,840 |
| Stronger active-book/time baselines | 1,936 |
| Hedge-budget × volume/OI eligibility combinations | 5,760 |

Counts are repeated parameter/context evaluations, **not independent tests or
15.9 million distinct trading strategies**. The exit count dominates: 510 atoms,
130,305 unordered OR pairs including single-rule cases, 20 time-cutoff pairs,
three closure labels and two opening-mark treatments. The entry search uses
a finite, deterministic beam over up-to-three-atom Boolean expressions, followed
by cooldown, signal-count, position-cap and book-state wrappers. It does not
exhaust all possible expressions. Trees add interactions beyond three atoms.
Sizing's 48 settings require 192 whole-cycle fold fits, not counted again.

Inputs extend the earlier RSI, EMA, Bollinger, ATR, ADX, Supertrend, breakout,
spot/premium, estimated IV and exposure features with pooled entry costs,
short-premium stress, trailing recovery, realized/unrealized P&L, inventory,
hedge coverage and prior order history. OI/volume and exact historical-program
exports were added after reviewing the initial combined results.

Selection uses expiries through **31 August**; the reported later checks use
September–October. Those later dates had already been inspected in previous
research, so this is chronological checking, **not an untouched holdout**.
All-observed fits are labeled separately. Trees use whole-cycle calibration CV;
Boolean candidates are ranked on earlier labels. No future target quantity,
selected strike or fill price is an input feature.

At physical minute T, market features use completed candles through T−1, and
inventory/order history use fills strictly before T. Quarter-window targets can
start one second before T, so their context retains an extra minute of embargo.
All programs that use inventory/P&L condition on the **recorded prior book**;
they are not autonomous portfolio replays after their own incorrect trades.

## 1. Additional entries: schedule survives; extra-entry trigger remains weak

For pre-expiry quarter windows, the earlier-selected schedule predicts 252
later opportunities: **242 correct, 10 false signals, three missed**. This is
96.0% precision and 98.8% recall; the combined Boolean search does not improve it.
These window labels tolerate execution delay and differ from exact fill minutes.

The important expiry-day comparison is:

| Rule at the 273 later expiry quarter opportunities | Correct additions | False signals | Missed additions | F1 |
| --- | ---: | ---: | ---: | ---: |
| Earlier clock attendance, requiring an active short book | 119 | 15 | 38 | 0.818 |
| Simply require an active short book at each opportunity | 157 | 27 | 0 | **0.921** |
| Selected indicator/book-state tree | 147 | 20 | 10 | 0.907 |
| Fitted time/loss gates on the active-book baseline | 145 | 19 | 12 | 0.903 |

Thus “the short book is still active” explains much of apparent expiry filtering.
The more complex tree does not beat that simple comparator. The **27 suppressed
additions while the book remains active** are a specific unresolved target.
This is conditional on actual prior inventory, not an independently runnable rule.

Outside quarter windows, the selected Boolean/temporal programs fare poorly:

| Later extra-pair timing | Actual event minutes | Correct predictions | False signals | Recall |
| --- | ---: | ---: | ---: | ---: |
| Pre-expiry | 93 | 13 | 41 | 14.0% |
| Expiry | 172 | 36 | 39 | 20.9% |

The pre-expiry candidate combines a long interval since a cover with a Bollinger
extreme, OR a crossing of time since the prior pair, then a 15-minute cooldown.
It misses 80/93 later events. **This does not identify Algo 8 as a Bollinger
strategy.** Adding OI/volume leaves these selected Boolean results unchanged.
Some flexible flow trees improve recall by producing many more false signals.

The previous directional extra-sale strike candidate remains a separate finding:
conditional on an order occurring, an ATM strike shifted one grid step with
recent movement matches many later sold strikes. It does not solve entry timing.

## 2. Exits and re-entry: large search, incomplete controller

Programs test capital-denominated loss/profit thresholds across net, short-book,
long-book, realized/unrealized and previous-close scopes; open-short-credit
losses including 4%; activated profit trails; stress-gated losses; and separate
pre/post-3-August time cutoffs. First substantial reduction, first flat short
book and final flat short book are scored separately.

The earlier-selected opening-inclusive program is essentially **net cycle loss
0.5% OR a time cutoff**. On 12 later cycles with usable closure labels it matches
substantial reduction within two minutes on **8/12**, first flat on **8/12**,
and final flat on **7/12**. Mean absolute errors are about 75 minutes because
the failures can be very early or very late. Excluding opening-price proxies
reduces these matches further. Even full-sample fitting of this exit grammar
only matches final flat within two minutes on **16/29** cycles.

The fitted 0.5% is **not a recovered stop and does not replace the supplied 1%**.
The precise stated 4% carry denominator, per-allocation references and resets
are still unknown. Do not equate short-credit loss tests with every possible
interpretation of the stated carry rule.

Joint tests include no lock, permanent day lock and 1/5/15/30-minute post-stop
locks with entry cooldowns/count limits. Five distinct calibration stop-time
programs remain after deduplication. All selected joint programs choose **no
additional lock**, with no later improvement over their entry-only counterparts.
That does not establish that the original has no re-entry restrictions: its
actual stop/reset/cancellation events are not known.

## 3. Hedge selection and large late protection

Conditional branches choose among 360 premium-budget/rounding/selector variants,
using known market, right, time and book state. Later exact-strike matching is:

| Routine hedge cohort | Earlier-selected constant budget | Conditional budget |
| --- | ---: | ---: |
| NIFTY pre-expiry | 316/637 (49.6%) | 323/637 (50.7%) |
| SENSEX pre-expiry | 321/623 (51.5%) | 327/623 (52.5%) |
| NIFTY expiry | 253/743 (34.1%) | 306/743 (41.2%) |
| SENSEX expiry | 526/806 (65.3%) | 493/806 (61.2%) |

For NIFTY expiry the older unrefined 2.5% budget already matches 288/743 (38.8%);
the conditional gain is smaller against that reference. Before expiry, the
simple 2.5% budget still puts roughly 92–95% of later selections within one
strike step. It remains a useful approximation, not exact hedge-code recovery.

OI/volume eligibility combinations do not improve selected later exact counts.
**All supplied SENSEX OI values are zero**, treated as unavailable, not evidence
of no open interest. NIFTY OI is positive in the stored bars. OI changes/PCR use
a previously known paired strike and completed same-strike candles; price/OI
quadrants do not establish who initiated a trade.

An oracle choosing a different budget rule after seeing each target strike can
represent most events. It is exported only as a representability diagnostic,
not a strategy. Even flexible all-observed conditional-budget fits fall short
of exact hedge reproduction. Large late-protection timing also fails: later
Boolean F1 is 0.074 pre-expiry and zero on expiry, with few positive events.
Routine budget branches do not solve these larger hedge changes.

## 4. Sizing and exposure

Targets are joint CE/PE new-short quantities per quarter window, normalized by
65 NIFTY / 20 SENSEX units. The selected depth-8, minimum-leaf-10 classifier
matches exact quantities on **257/567 later windows (45.3%)**, compared with
239/567 (42.2%) for the earlier clock-modal quantity baseline. On nonzero actual
allocations its exact rate is **36%**, versus 40% for the clock baseline.
It reduces missed allocations but still does not recover order multiplicity.

An unrestricted full-sample sizing tree achieves 100% fit using hundreds of
leaves. This is a historical quantity mimic, not a capital/margin sizing formula.
Maximum admissible exposure, margin limits and original allocation IDs remain
unidentified; observing a maximum is not proof of a configured cap.

## 5. Eligibility and configuration

Retrospective one-break fits perfectly describe the disappearance of observed
13:15 pre-expiry attendance from **28 September for NIFTY** and **16 September
for SENSEX**. These use all dates and are descriptive change points. SENSEX PE
seed-gap fitting also locates a 16 September change, but a single universal
CE/PE seed-gap switch leaves exceptions; the CE fit chooses another date.

This does not prove software releases or reveal the cause. Sessions absent from
the trade export have no verified original eligibility label, so no-trade expiry
selection and all delayed-start conditions cannot be recovered from these fits.

## 6. Economic alpha check

Later-period signals select identically constructed four-leg baskets at a given
minute: independently chosen ATM shorts and 2.5%-budget outward wings, chosen
from prior quotes. Entry is next-minute open; exits are 15 minutes later or
expiry 15:14. Missing endpoint quotes are excluded explicitly. Cost stress is
25 bps of premium turnover, eight ₹20 orders and ₹0.05 per transacted quantity.
PnL is scaled by theoretical static expiry tail loss, not margin or account NAV.

For 15-minute baskets, the selected Boolean program differs from the fixed-clock
active-book baseline by **−₹5.03 per ₹10,000 tail-loss budget**; the later-week
bootstrap 95% interval is **[−₹24.59, +₹8.41]**. For the expiry-cutoff version
the difference is **+₹105.00**, interval **[−₹221.04, +₹416.15]**. All six saved
model/horizon comparison intervals include zero, using six or eight common weeks.

This diagnostic establishes **no repeatable incremental alpha**. It is not the
recorded Algo 8 return: it uses static independently selected baskets, overlapping
allocations, incomplete chain coverage and actual-book-conditioned signals.
Negative average stressed basket results do not establish that the original
strategy loses money. A complete independently replayable controller and new
data are still needed to test the economic effect of the decoded decisions.

## Exact historical mimics: what they do and do not reproduce

`combo_full_history_programs.json` contains **13 executable decision trees**:
12 phase/action models and one allocation-quantity model. Their fitted labels
are reproduced exactly. `combo_full_history_flow_programs.json` adds six models
with option-flow inputs. Each artifact stores numeric input names, fitted
imputation/missingness handling, branches and leaf classes. The adjacent
`*_rules.txt` files contain every branch; `predict_model()` executes the JSON.

These are deliberately flexible **all-observed resubstitution fits**. They
reproduce minute action presence and quarter-window quantities on their modeled
rows, including no-action rows. They do **not** reproduce all 41,421 individual
orders, exact seconds, selected hedge strikes, limit prices, pending orders,
account state or the screenshot. Most action models need hundreds of leaves;
exact historical fit alone cannot choose the original program among alternatives.

The export records `Limit` on all 41,421 rows, with zero buy-above-limit or
sell-below-limit violations under the inferred price fields. The order-minute
label can precede first fill; switching the same execution cohorts to that
label does not rescue the entry matching. Pre-expiry fresh-pair Boolean F1
falls from 0.745 to 0.668. This label is not a verified signal timestamp or basket
ID. Software stops may submit limit orders; `Limit` does not disprove stops.
The timing audit retains and flags timestamp inversions and long delays.

## Artifacts, validation and reproduction

Start with [machine-readable overview](outputs/combo_overview.json),
[candidate branches](outputs/combo_action_rules.txt),
[exit programs](outputs/combo_exit_programs.json),
[conditional hedge programs](outputs/combo_hedge_programs.json) and
[full historical branches](outputs/combo_full_history_rules.txt).
Prediction tables contain target/predicted labels for finding individual
failures; hedge predictions include exact selected/predicted strikes. Exit
histograms retain the calibration score distribution for all 15.6 million
comparisons, plus best candidates and their parameter grammar. The overview
hashes all 57 result artifacts and verifies counts, later-date membership and
24,860 causal option-flow reference timestamps.

The repository's **125 tests pass**, including 14 combined-search checks for
causal/target separation, own-signal cooldown state, cycle resets, hedge split
selection, stop-lock semantics, executable JSON, quote exclusions and costs.

From the repository root (existing earlier-study outputs are prerequisites):

```bash
python -m pip install -r research/requirements-combinations.txt
python research/combo_features.py
python research/search_rule_combinations.py
python research/search_exit_combinations.py
python research/search_conditional_hedges.py
python research/search_sizing_configuration.py
python research/search_joint_entry_exit.py
python research/check_combo_markouts.py
python research/combo_option_flow.py
python research/search_rule_combinations.py --flow-only
python research/search_hedge_liquidity.py
python research/export_historical_mimic.py
python research/export_historical_mimic.py --flow
python research/audit_combo_order_timing.py
python research/summarize_combination_search.py
python -m unittest discover -s research -p 'test_*.py'
```

The next targeted reconstruction is the allocation/order-state controller:
the 27 expiry quarter-window suppressions, the unmatched extra-entry events,
and first-cover decisions before covering bursts have started. Exact per-order
decision quotes, allocation IDs, stop references and cancellation logs would
distinguish rules that minute candles and pooled inventory currently cannot.
