# Algo 8 — cumulative strong findings

**Updated:** 27 October 2026 · **Version:** 6 · **Branch:** `research/strong-findings`

**Evidence snapshot:** F01–F30 and C01/C02 use research/data inherited from
`60427b2`. The additional cover-to-re-entry assessment is from `984164c`.
F31–F34 and the independent operational audit are from `58ae0cf`.
The constrained autonomous-controller assessment is from `8524844`.
The policy/execution separation and fixed-cohort forensic assessment are from
`8e32701`. F01–F34 and C01/C02 retain their existing definitions and counts.
The registered intermediate-exit event study is from `12dc6af`.

This is the single cumulative reference for strong findings. Preserve its finding
IDs when adding evidence. The original research continues on
`data/local-breeze-fetch`; this branch keeps the consolidated reference separate.

**The strongest combined pattern is a scheduled build-up of protected,
near-expiry short-option exposure, followed by separate side/risk management.**
The recurring build-up pattern holds jointly in **529/544 windows (97.2%)**.
That is an observed structural match, not 97.2% recovery of the full strategy,
an identified entry/exit trigger, or a probability of future profit.

## How to read “80–100% strong”

The percentages below describe exactly the stated sample and measurement:

- **Observed:** reconstructed executions/inventory or directly measured counts.
- **Conditional:** true only inside the stated cohort, such as losing covers or
  late exits. It is not an all-trade prediction rate.
- **Approximate:** a stated strike tolerance, not exact contract selection.
- **Modeled:** Greeks/IV estimated from minute candles under the documented model.
- **Template:** an agreement between modal quantities, not between every order.

A historical 100% match is not 100% confidence in an unknown original condition.
Repeated windows/parents within a cycle are related observations. The findings
and Greek signs are also correlated; do not multiply their percentages or count
them as independent confirmations. Several schedules and tolerances were found
after inspecting this dataset. Later dates have already been inspected too.

**Scope:** 41,421 fill records; 39,874 reconstructed parent orders; 35
underlying/expiry cycles; 32 observed pre-expiry entry sessions, in June–October
2026. Market data comprise 170 index-days/63,678 stored bars and 3,243 option
contract-days. These logs do not cover the screenshot's March 2025–May 2026
backtest. No screenshot CAGR/Sharpe or future win probability is reproduced.
Inventory/role reconstruction assumes zero inventory before each contract's first
observed fill and the received records' completeness. Unobserved holdings,
settlement and missing executions are not invented. Parent/hedge associations
are inferred where the export supplies no original allocation IDs.
An inventory-opening fill is not automatically an intended new allocation:
rapid close/opposite-reopen/neutralize sequences also occur. Protection present
in the book does not imply continuously matched quantities or unique pairing.

## 1. Opening entries and the initial protection

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F01 | The first paired CE/PE short sale normally starts in **09:16 IST**. | **31/32 sessions, 96.9%.** The exception is NIFTY 5 October at 09:30:59; its first single CE short is earlier, at 09:21:21. | First pair, not first exposure. Observed timing; eligible no-trade dates are not fully labeled. |
| F02 | On those same 31 ordinary starts, the initial sold CE/PE strike is nearest ATM using the completed 09:15 index close: NIFTY 50-point grid, SENSEX 100-point grid. | **31/32 overall, 96.9%; 31/31 ordinary starts.** | Exact proxy match. It does not distinguish a completed-close implementation from a contemporaneous spot quote producing the same strike. |
| F03 | The ordinary 09:17 inventory contains all four roles: short CE, short PE, long CE and long PE. | **31/31 ordinary opening snapshots, 100%.** | These are roles across the inventory, not necessarily exactly four contracts or one simultaneous order. |
| F04 | Ordinary opening quantities commonly equal **195 per role for NIFTY; 60 per role for SENSEX**. | All four roles match together on **13/14 NIFTY dates (92.9%)** and **15/17 SENSEX dates (88.2%)**. | Observed 09:17 net quantities, not gross buys, broker margin or an unconditional size instruction. |
| F05 | Initial NIFTY seed wings are near an outward **2,000-point gap**. | **26/28 first-wing observations within 100 points, 92.9%.** | Approximate seed geometry. Only 19/28 are exactly 2,000; do not promote the nominal gap to an exact universal rule. |
| F06 | Earlier SENSEX seed wings are near **4,000 points**; later observed seed wings use **2,000 points**. | Before 16 September: **21/22 within 200 points of 4,000 (95.5%)**. From 16 September: **12/12 exactly 2,000 (100%)**. | A strong observed configuration difference. The reason and precise original configuration-change instruction are unknown. |

Sources: [initial entries](research/outputs/trigger_initial_entries.csv),
[opening inventory](research/outputs/rulebook_opening_allocations.csv),
[first seed wings](research/outputs/trigger_initial_wings.csv),
[index study](research/INDEX_TRIGGER_FINDINGS.md).

Pre-expiry does not always mean one calendar day: 31/32 observed initial dates
have calendar DTE 1; NIFTY's 16 October opening precedes Monday 19 October by
three calendar days. All times in this document are IST.

## 2. The recurring allocation engine

The **17 recurring pre-expiry windows** are:

`09:30, 09:45, 10:00, 10:15, 10:30, 10:45, 11:00, 11:15, 11:30, 11:45,
12:00, 12:30, 13:30, 13:45, 14:00, 14:15, 14:30`.

Each execution window is **T−2 seconds through T+3 minutes, exclusive**. This
allows execution delays; it is not a recovered signal timestamp. The schedule
has gaps and other entries occur outside it. “Every 15 minutes all day” is not
the supported rule.

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F07 | Each recurring window contains fresh same-strike CE/PE short quantities. | **544/544 windows, 100%**: 17 windows × 32 sessions. | A descriptive same-strike pair exists in each window; several parents/strikes may coexist. |
| F08 | Some older short exposure **and** some older long exposure necessarily survive each window. | **544/544 windows, 100%.** | Conservative inventory-retention bounds. It does not say every old lot survives. |
| F09 | All four roles receive new quantities within the window. | **541/544 windows, 99.4%.** | Gross opening-role quantities, not a proof of equal size or unique hedge ownership. |
| F10 | Net short quantity grows across the window. | **530/544 windows, 97.4%.** | The recurring action generally accumulates exposure rather than replacing the whole book. |
| F11 | The trade batch increases modeled theta. | **531/543 fully modeled windows, 97.8%.** One window lacks full model coverage. | The same pre-window state prices both inventories. Positive theta is exposure to time decay, not guaranteed profit. |
| F12 | The batch makes Vega and Gamma more negative. | **533/543 windows, 98.2%, for each sign separately.** | The net effect normally increases short-volatility/movement exposure even though protection is bought. |
| F13 | Independently computed modal four-role size vectors agree across indices after dividing NIFTY by 65 and SENSEX by 20. | **22/22 nominal pre-expiry clock slots, 100%.** | A common relative sizing template. Many individual dates differ from those modes; this is not 100% sizing prediction. |

The modal base-unit sequence starts **3, 2, 3, 1, 4, 1, 2** at
09:16, 09:30, 09:45, 10:00, 10:15, 10:30 and 10:45. These are descriptive base
units; they are not asserted exchange lot sizes or measured capital allocation.

Sources: [window sizes](research/outputs/allocation_window_sizes.csv),
[retention bounds](research/outputs/lifecycle_scheduled_window_retention.csv),
[fixed-state risk changes](research/outputs/building_rationale_windows.csv),
[cross-index modes](research/outputs/allocation_cross_index_modal_schedule.csv).

## 3. Strike selection after the opening

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F14 | Subsequent pre-expiry paired short strikes remain near the moving index rather than always using the initial strike. | Within one strike of the nearest previous completed-minute ATM: **488/501 NIFTY groups (97.4%)**, **548/579 SENSEX groups (94.6%)**. | Approximate proximity, not an exact ATM selector: exact matches are only about 70%/68%. Seven groups without an immediate prior continuous index bar are excluded. |
| F15 | A routine hedge budget near **2.5% of the corresponding ATM leg premium** approximates pre-expiry wing selection. | In the later checked cohort, selected refinements are within one strike on **586/637 NIFTY events (92.0%)** and **589/623 SENSEX events (94.5%)**. | Separate CE and PE premium budgets; NIFTY unrounded ceiling selector, SENSEX nearest-₹0.10 budget then ceiling selector. Exact matches are only 49.6%/51.5%. Incomplete historical chain and minute timing prevent exact rule recovery. |
| F16 | The SENSEX expiry-day budget refinement remains approximately consistent. | 2.5%, budget rounded down to ₹0.10, nearest-premium selector: **696/806 within one strike (86.4%)**. | Exact 526/806 (65.3%). The analogous NIFTY expiry result does not meet this register's 80% threshold. |

“Ceiling selector” above means choose the highest eligible quoted premium **at
or below** the budget. The opening seed rule and routine premium-budget rule
are distinct cohorts. Rough ₹2 NIFTY / ₹7 SENSEX hedge prices are not fixed
universal targets. Nor do F14–F16 mean all later shorts form ATM straddles:
different-strike CE/PE sales and one-sided entries are observed.

Sources: [index study](research/INDEX_TRIGGER_FINDINGS.md),
[hedge refinement scores](research/outputs/rule_refine_hedge_evaluation.csv),
[hedge refinement rules](research/RULE_REFINEMENT_FINDINGS.md).

## 4. Expiry-day entries and state dependence

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F17 | Expiry day includes fresh shorts, not only yesterday's liquidation. | **33/35 observed cycles, 94.3%.** | Fresh opening inventory is distinguished from covers/long sales. |
| F18 | At tested later expiry quarter windows with an actual active short book, another short usually opens. | **175/184 active windows, 95.1%**; NIFTY 80/83, SENSEX 95/101. | Conditional on actual prior inventory; not an autonomous forecast of whether the book should still be active. |
| F19 | Both rights are usually sold in those active windows. | **169/184, 91.8%**; same-strike CE/PE pairs occur in **157/184, 85.3%**. | Both-right activity and same-strike pairs are different targets. |
| F20 | Tested inactive-book expiry quarter windows have no fresh shorts. | **89/89, 100%.** | Only these quarter windows. This does not establish a permanent lock after the first closure. |

The combined timer + actual-active-book baseline has **95.1% signal precision
and 100% recall** for any new short in that 273-window cohort. It has nine false
signals. Of the old “27 skipped” same-strike-pair windows, 12 contain both-right
sales and six contain one-right sales; only nine are empty. Treating all 27 as
entry-filter rejections was incorrect.

Sources: [corrected labels](research/outputs/allocation_entry_label_summary.json),
[window evidence](research/outputs/allocation_entry_window_labels.csv),
[lifecycle study](research/POSITION_LIFECYCLE_CLARIFICATION.md).

## 5. Protection has more than one job

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F21 | Most pre-expiry hedge-buy parents accompany fresh same-right short parents. | Within five seconds: **1482/1630 NIFTY (90.9%)**, **1657/1788 SENSEX (92.7%)**. | Temporal association, potentially multiple candidates. Most such buying belongs to fresh allocations; it is not evidence of an IV-defense trigger. |
| F22 | Matched expiry-day hedge replacements usually move the protection strike inward. | **198/243 parent pairs, 81.5% pooled.** NIFTY 128/163 (78.5%), SENSEX 70/80 (87.5%). | Equal-quantity, different-strike long buy/sale within five seconds, with no nearby same-right fresh short. The pooled pattern exceeds 80%; NIFTY alone does not. |
| F23 | Those expiry replacements usually increase modeled Gamma protection. | **191/233 fully modeled cases, 82.0% pooled**; ten pairs lack complete risk fits. | Same preceding snapshot and isolated matched replacement. There are 24 ambiguous expiry associations. This describes effect, not the trigger or proof of realized protection. |
| F24 | Large late pre-expiry long-adjustment batches generally reduce absolute modeled Vega. | **34/37 modeled event minutes, 91.9%**. With zero-volume/very-low-premium active-leg cases removed: **33/35, 94.3%**. | A separately defined late/large cohort, not every hedge buy or a universal adjustment schedule. |

F22 and F23 are **separate marginal results**. Their conjunction is only
**186/233 modeled cases (79.8%)**, or 186/243 confirmed across all matched pairs.
It does not qualify as an 80% joint finding. This distinction prevents combining
two strong percentages into an unsupported stronger rule.

Sources: [hedge/action links](research/outputs/deep_hedge_action_links.csv.gz),
[replacement pairs](research/outputs/deep_hedge_refresh_pairs.csv),
[replacement summary](research/outputs/deep_hedge_refresh_summary.csv),
[late-batch/IV study](research/IV_THETA_HYPOTHESIS_FINDINGS.md).

## 6. Risk exposures and separate-side loss reductions

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F25 | Ordinary opening books are theta-positive, Vega-negative and Gamma-negative. | **31/31 modeled ordinary opening books, 100%, for all three signs.** | Black-model estimates from minute candles, not exchange Greeks. Wings do not remove nearby IV or movement risk. |
| F26 | Observed pre-expiry closing inventory remains net short Vega. | **31/31 modeled carry books, 100%.** | The magnitude changes with hedging; these sampled carry books are not IV-neutral. |
| F27 | Losing pre-expiry first covers usually follow an adverse underlying move since entry. | FIFO: NIFTY CE **276/288 (95.8%)**, PE **127/132 (96.2%)**; SENSEX CE **221/244 (90.6%)**, PE **349/366 (95.4%)**. | Conditional on a losing attributed cover with spot data. A rise normally hurts short CE; a fall normally hurts short PE. This is not a predictive exit rule or a quantified threshold. |
| F28 | Frozen overnight attribution shows a positive time component, often offset by negative IV/surface repricing. | Complete-model subset: time positive **24/24 (100%)**; IV component negative **21/24 (87.5%)**. | Only 24/31 endpoint-priced carry books fit completely. The omitted seven include important losses. This is model attribution, not strategy profit or excess return. |

Sources: [opening Greeks](research/outputs/iv_initial_book_exposures.csv),
[carry Greeks](research/outputs/iv_carry_book_exposures.csv),
[side-cover direction](research/outputs/allocation_side_direction_summary.csv),
[model definitions and limitations](research/IV_THETA_HYPOTHESIS_FINDINGS.md).

## 7. Closing-time findings, with the correct denominators

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F29 | Among observed post-3-August final short-book closures at/after 15:00, most occur in the **15:14 minute**. | **9/10 late closures, 90%.** | Not 90% of all exits. Early risk exits, residual hedges and a 15:36:54 exception remain. The 15:15 cash-market transition is context, not proof of the strategy's purpose. |
| F30 | Across the 29 reconciled final short-book closures, most finish **by 15:27:33**. | **27/29, 93.1%.** | A cumulative timing description, not an exact exit time or a proposed trading instruction. Unresolved/no-expiry-fill cycles are not assigned invented closures. |

Sources: [closure timestamps](research/outputs/rule_refine_exit_target_comparison.csv),
[date-effective session context](research/CAS_SESSION_FINDING.md).

### Additional operational findings from the independent book audit

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F31 | Observed pre-expiry new-short parent requests predominantly use one base quantity: **65 NIFTY / 20 SENSEX**. | NIFTY **2,022/2,032 parents (99.5%)** request 65; SENSEX **2,375/2,375 (100%)** request 20. Every received incremental fill is an integer multiple of its index's base quantity. | Requested child-order granularity, not capital per allocation, verified exchange lot metadata or a number-of-orders formula. Inventory roles are retrospective; some openings can be processing reversals. |
| F32 | Ordinary first short/wing fills are tightly sequenced. | First CE and PE short fills are within one second on **31/31 ordinary starts** (24 at the same second). Each right's first wing/short separation is at most three seconds on **31/31**; the CE wing precedes its short on **28/31 (90.3%)**, PE on **30/31 (96.8%)**. | First observed fills, not completion of all quantities or proof of an atomic basket/guaranteed hedge-first broker instruction. Log seconds are not independently certified exchange timestamps. |
| F33 | Brief states with more short calls than long calls occur in the recorded book. | At least one atomic-second state in **35/35 cycles**. There are **4,457 intervals**, median four seconds; **4,452/4,457 (99.9%)** last at most 60 seconds. The longest is 1,346 seconds in NIFTY on 16 October. | Under the zero-initial-inventory, received-options-only convention, the frozen payoff has a negative upside tail during these states. This does not establish the actual account's total risk, margin or realized loss. Most intervals are brief sequencing states; the long interval is a material exception. |
| F34 | Every observed pre-expiry carry snapshot has long quantities covering shorts on each right. | **31/31 carry books:** long CE >= short CE and long PE >= short PE at the last received pre-expiry execution; all have a finite frozen expiry-payoff loss bound. The other one of 32 pre-expiry session books is flat. | Strong end-book quantity condition, consistent with overnight preparation. It does not identify a coded guard, continuous intraday matching, per-allocation ownership, actual margin or an acceptable loss cap. |

Sources: [operational playbook](ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md),
[independent reconciliation](research/outputs/playbook_book_audit.json),
[parent request granularity](research/outputs/playbook_cadence_summary.csv),
[first-role times](research/outputs/playbook_initial_role_times.csv),
[call-tail intervals](research/outputs/playbook_negative_call_tail_intervals.csv),
[session-end books](research/outputs/playbook_session_end_books.csv).

## 8. What the strong findings establish together

### C01 — a joint opening structure, not separate percentages

Join F01/F02/F25 with the two seed-wing observations per ordinary date. Require:
09:16 first paired sale, nearest previous-close ATM, expected opening Greek signs,
and **both** first wings within the stated index/regime gap tolerance.

This entire structure occurs on **28/32 observed pre-expiry entry sessions
(87.5%)**, or **28/31 ordinary starts (90.3%)**. The exceptions are entry dates
3 August, 7 September and 26 August for the seed-gap condition, plus the delayed
5 October NIFTY start. This is retrospective consistency, not entry eligibility
or proof of the exact spot/quote inputs used by the original program.

### C02 — the recurring build-up is strongly established jointly

On the **same window**, require all of the following, not separate marginal fits:

1. Older short and long exposure are both necessarily retained.
2. Fresh short CE, short PE, long CE and long PE quantities are all present.
3. Total short quantity grows.
4. Modeled theta increases; modeled Vega and Gamma decrease, using one frozen
   pre-window market state for both inventories.

**529/544 windows (97.2%) satisfy the whole conjunction.** Fourteen windows fail
at least one measured condition; one lacks a complete Greek fit and is not
counted as a confirmed match. Among fully modeled windows: **529/543 (97.4%)**.

| Descriptive breakdown | Joint matches / all windows | Rate |
| --- | --- | --- |
| NIFTY | 250/255 | 98.0% |
| SENSEX | 279/289 | 96.5% |
| Expiries through 31 August | 298/306 | 97.4% |
| Later September–October expiries | 231/238 | 97.1% |

Every one of the **32 observed sessions** has at least **15/17 windows** with
this whole pattern: 19 sessions have 17, eleven have 16, and two have 15. That
minimum is an observed summary, not a preselected predictive threshold.

This supports a **programmed allocation engine accumulating protected
short-option exposure across entry times and updated strikes**. Fresh protection
and retention do not guarantee every new short has equal-quantity, uniquely
identified protection. The Greek effects are mechanically related to added
short inventory; they do not provide independent evidence of the hidden trigger.

Reproduce C02 by a one-to-one join on underlying/expiry/date/clock of
`building_rationale_windows.csv`, `lifecycle_scheduled_window_retention.csv` and
`allocation_window_sizes.csv`, restricted to the 17 recurring windows. C01 joins
the initial-entry, initial-wing and opening-Greek files by underlying/expiry.
All three component conditions must be evaluated on the same event/date.

### The supported strategy structure

```text
Observed pre-expiry session
    ↓
Ordinary opening: ATM CE/PE shorts + outward seed protection
    ↓
Recurring clock windows: add allocations; update strikes near current ATM;
retain older exposure; usually add theta and short Vega/Gamma
    ↓
Separate management: some CE/PE reductions, re-entries and protection changes
    ↓
Expiry: fresh selling usually continues at tested timers while the book is active
    ↓
Early closures and/or late-session liquidation; some wings/residuals can remain
```

The middle risk controller is still missing. The strong facts support timed
near-expiry volatility carry with protection and active management more directly
than a recovered range-forecast indicator. They do not prove that no eligibility
filter exists. They also do not establish the optimality of 15-minute spacing.

Combining the operational additions suggests one further constraint: repeated
small order requests assemble a larger book, temporary quantity mismatches can
occur during management, and the last recorded pre-expiry carry book restores
same-right long coverage in all 31 observed carry cases. This is consistent with
an overnight preparation stage around a shared allocation engine with index-
specific configuration. It does not recover the instruction that causes that
stage, prove that one program generated all orders, or turn overnight quantity
coverage into a verified capital-loss limit.

## 9. Verified constraints and claims excluded from the strong register

These constraints prevent the strong findings from being combined incorrectly:

- **Separate-side closure is directly observed.** On 13 July, initial NIFTY
  24000 CE shorts close in 65-unit pieces at 09:50, 09:53 and 09:59 while their
  26000 CE protection is sold. Initial PE/22000 PE protection survives. New
  24050 CE/PE shorts had been added at 09:30 while the original holdings remained.
  Closing the original 24000 CE contract does not mean the entire CE side is
  flat: other CE shorts remain after its final reduction.
  This refutes mandatory all-four-leg replacement every quarter hour; it does
  not identify the general side-stop threshold.
- **Opening movement does not automatically block entry.** The 28 September
  NIFTY opening candle falls about 0.456% and entry still starts at 09:16:01.
  This is a counterexample to that unconditional ban, not evidence against
  every possible range/volatility threshold.
- **The first flat short book is not a universal permanent stop.** Later new
  short fills occur after that point in ten cycles; some later order-label
  minutes also postdate closure. Pending orders and permitted re-entry cannot
  be treated as the same mechanism.
- **A recent cover is not an established re-entry instruction.** The controlled
  follow-up finds later NIFTY expiry fresh same-side entries in **76/97**
  post-cover five-minute windows versus **52/97** matched no-cover windows,
  across only four cycles. Both rights receive entries in 73/97 versus 48/97,
  so the association is not specific to reopening the covered leg. SENSEX is
  **75/113 versus 75/113** across five cycles. Primary matches retain recent-
  activity/range imbalance; stricter matching leaves just 15 later NIFTY cases
  and three SENSEX cases. Adding cover history to known-state prediction does
  not establish a general improvement. These results are constraints/leads,
  **not an additional 80–90%-accurate trigger finding**. The comparison excludes
  full-flat shutdowns and uses minutes after a completed cover minute; it is
  not an exact five-minute-from-fill rule.
- **Inventory openings can reflect rapid liquidation reversals.** The independent
  audit flags 59 conservative close/opposite-reopen/neutralize motifs, fully
  covering 43 new-short and 24 new-long parents. The bounds were specified
  after inspecting the 6 August example; these are processing candidates,
  not proven errors or original rules. Excluding flagged later first-reduction
  cases barely changes the frozen global exit match: **1,313/4,538 (28.93%)**
  becomes **1,310/4,526 (28.94%)**. This does not explain away the missing
  controller or establish a better stop. All 32 pre-expiry sessions also contain
  some inventory-opening flow after 14:30; that alone does not establish a
  planned late allocation schedule.
- **The duplicate-close explanation is a conditional processing lead.** Within
  those 59 conservative reversal motifs, the first opposite quantity equals the
  just-closed quantity in **49/59 cases (83.1%)**. The motif definition already
  restricts holding age, timing and maximum opposite size. This is not an
  independent all-order trigger match or proof of a stale/duplicate submission.
  Original submission, cancellation and acknowledgement records are missing.
- **Autonomous reconstruction still falls well below 80–90%.** A separate
  constrained search evaluates **13,864 definitions** (13,824 main combinations
  and 40 earlier-fit refinements) with their own simulated inventory. The
  August-selected controller reaches later event macro F1 **23.3%**, versus
  **18.2%** for a simple pooled-budget clock controller, over 15 already-inspected
  September–October cycles. Matches are exact contract/action within two minutes;
  all four action types contribute. The normalized quantity/path scores are
  **15.7% / 46.1%**, not exact sizing/book accuracy. These metrics have different
  targets from C02 and the earlier conditional first-reduction studies.
  The selected premium50/clock/budget composite scales opening sizes by 1.25
  and uses budget wings from initialization: it matches both first wing strikes
  and both short quantities on **0/32** received pre-expiry first-three-minute
  gross-action windows. This is a concrete contradiction, not recovered intent.
  A simpler competing controller has almost the same penalized score. Fixed
  range/efficiency gates worsen paired reconstruction in this grammar; this
  does not exclude other eligibility rules. The simulated economics do not
  establish alpha. All 201 software tests and saved-YAML replay checks pass;
  they validate software behavior, not original-strategy truth.
- **Forensic compatibility does not establish duplicate submissions.** The
  unchanged 59-case cohort has distinct received parent references at every
  final-close/opposite-open boundary (59/59). The opposite quantity equals the
  atomic close in 49/59, but only 10/59 repeat both requested size and the inferred
  limit-price candidate. Multiple received children occur in involved parents
  in 27/59. These observations permit mixed execution explanations; submission,
  cancellation and acknowledgement evidence remains absent. Size equality is
  selection-sensitive: the cohort excludes opposite quantities above the close,
  and one-base equality is forced by the quantity restriction. Only one case has
  a non-reversal control matched on index, cycle, phase, old role and closed size;
  even that control is about 109 minutes away. The aggregate equality comparison
  cannot establish a causal duplicate probability. All 59 conservative motifs
  occur before 15:00; the broader 66-case source includes one later,
  nonconservative case, so this is not a universal time restriction.
- **Separating policy from execution does not recover the missing decisions.**
  The limited experiment crosses 12 desired-inventory policies with seven
  execution mechanisms, replaying all 35 cycles. Selection uses the same 32
  starts with known pre-expiry initialization: 11 fit, seven August and 14 later
  cycles. A separate opening module matches both opening short quantities on
  **28/32**, both true first-executed wing strikes on **17/32**, and all four
  09:17 net role quantities on **19/32**. The earlier controller's **0/32**
  contradictions are preserved and independently re-audited; these are different
  models, not revised historical counts. The selected pooled-clock/premium-stop
  policy with safe execution reaches later event macro F1 **24.3%**. Sequential
  and pending-aware variants have the same later minute F1; delay variants add
  about one percentage point but worsen final liquidation and the registered
  composite. Base-unit parent requests better reproduce observed request-size
  granularity, even when minute paths are equivalent; the exact sequencing delay
  remains unidentified. A universal stale-close variant produces **559**
  conservative simulated motifs and matches **0/59** original cases by exact
  contract within two minutes. At those original close times the selected model
  lacks both contract holdings and targets in 32 cases, and retains both in 27;
  none is simply an unfinished execution toward its own zero target. This
  localizes failure in candidate holdings/decisions before adding execution
  detail; it does not reveal the original desired target. The chronological
  later data were already inspected. All **217** software tests pass, request
  quantities conserve, and the public YAML replay reproduces saved child fills,
  targets, requests and books exactly. Those checks do not establish an original
  controller or economic alpha.
- **The 32/27 motif comparison includes protective-long closures.** The absent
  group contains nine short covers and 23 long closures; the retained group
  contains seven short covers and 20 long closures. In M06 the candidate retains
  the opposite direction to the observed long being closed. In the absent group,
  ten cases have another role/right strike near the active epoch's first entry,
  13 have no comparable allocation near that entry, eight previously held that
  role but reduced it earlier, and one lacks initialization. The +/-120-second
  entry comparison is a diagnostic, not unique original allocation ownership.
  Three retained short cases close during 09:15 before a completed session candle
  is available. Their missing minute features are not filled with future data.
- **A finite exit-event study finds relative discrimination, not a general stop.**
  The registered study retains all 11,716 Buy closing children, 8,197 atomic
  contract/second covers and 4,251 grouped reduction episodes. Its 32 initialized
  cycles contain 3,512 intermediate episodes and 326 separately labeled final
  episodes. Twelve fixed hypotheses are compared with training-only clock and
  inventory baselines, with whole-cycle exclusion and 24 expanding chronological
  test cycles (2,200 intermediate episodes). A 50% pooled premium-loss rule has
  **36.4% precision / 9.8% recall** within two minutes. The best average-cycle F1
  hypothesis, sampled side drawdown of 0.5% of supplied capital, has **18.0%
  precision / 16.6% recall**. Its mean cycle F1 improves on clock by 10.1 percentage
  points and inventory by 8.5, but neither it nor another candidate meets both
  80% precision and recall. Matched non-exits often share the conditions; weak
  common support and unknown original ownership remain explicit. This is
  conditional discrimination using received inventory, not a replacement for the
  autonomous controller, an all-action F1 comparison or recovered economic alpha.
  The original selected model and configurations remain unchanged. All 234 tests
  pass; 208,885 opportunity quantities and marks are checked against strict past
  inventory/completed candles. No expanded search follows this negative result.
- **Capital/stop statements are supplied context, not recovered implementation.**
  [Info.txt](Info.txt) states ₹2 crore, a 4% carry-forward stop and a 1% expiry-day
  capital stop. The 4% denominator, scope, reset rules, pending-order handling,
  actual margin and maximum exposure remain unknown.
- **Exact size/strike/exit rules have not met the threshold.** Later fixed
  four-role size templates match only about 54% NIFTY / 49% SENSEX on recurring
  positive slots. Expanded allocation-level exit programs match about 29% of
  later first reductions within two minutes. The broad extra-entry and hedge-
  timing searches do not achieve both 80–90% precision and broad coverage.
- **No economic alpha is established.** Positive premium collection, favorable
  Greek signs and structural order matches are not excess returns after costs
  at comparable risk. The autonomous NIFTY candidate has only a small positive
  sample; its uncertainty includes no edge. The expanded conditional exit test
  improves aggregate results versus a clock hold but remains negative pooled
  and does not establish an independent return advantage.

Sources: [lifecycle examples](research/POSITION_LIFECYCLE_CLARIFICATION.md),
[re-entry/closure evidence](research/RULE_REFINEMENT_FINDINGS.md),
[controlled cover/re-entry follow-up](research/COVER_REENTRY_FINDINGS.md),
[operational playbook](ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md),
[reversal sensitivity](research/outputs/playbook_frozen_exit_reversal_sensitivity.csv),
[constrained autonomous search](research/hypothesis_controller_search/HYPOTHESIS_CONTROLLER_SEARCH.md),
[policy/execution reconstruction](research/policy_execution_separation/POLICY_EXECUTION_RECONSTRUCTION.md),
[fixed-cohort case ledger](research/policy_execution_separation/reversal_motif_ledger.csv),
[reproduction checks](research/policy_execution_separation/validation_audit.json),
[intermediate-exit event study](research/intermediate_exit_study/INTERMEDIATE_EXIT_CONTROLLER.md),
[exit study registration](research/intermediate_exit_study/REGISTERED_PLAN.md),
[cycle validation](research/intermediate_exit_study/cycle_validation_scores.csv),
[latest controller search](research/DEEP_CONTROLLER_FINDINGS.md),
[economic candidate limits](research/ALPHA_CANDIDATE_FINDINGS.md).

## 10. How to add the next strong finding

1. Append a new stable **F35, F36, …** ID; do not silently rewrite an old claim.
2. Record the event/session/cycle definition, numerator, denominator, exclusions,
   exceptions, exact tolerance and source file/commit. Label observed,
   conditional, approximate, modeled or template support.
3. Admit a rate claim only at **80% or above in its explicit cohort**. Show
   weaker subgroups. A verified counterexample or supplied statement belongs
   in section 9, not as an invented 100%-accurate general rule.
4. Recalculate combined **C01/C02** if their inputs change. Add new conjunctions
   only after joining the same events; include missing coverage and the failed
   intersection if relevant. Never infer joint accuracy from marginal rates.
5. Update the date, evidence commit and change log. Mark corrected IDs as
   superseded, preserving why. Keep exact-rule recovery and economic alpha
   separate from structural agreement.

### Change log

- **v6 · 27 October 2026:** Added the finite intermediate-exit study from
  `12dc6af`, including the long/short distinction in the unchanged 32/27 motif
  partition, upstream differences, strict pre-event reconstruction, matched
  controls and chronological negative results. Relative discrimination does not
  establish an original stop. F01–F34, C01/C02 and the selected baseline remain
  unchanged. All 234 software tests pass; no general 80–90% trigger or economic
  alpha is claimed.
- **v5 · 27 October 2026:** Added the policy/execution assessment from
  `8e32701`: immutable 59-case forensics, matched-control limitations, separate
  opening metrics, 84 interpretable models and failure to recover reversal
  activation. Preserved the earlier opening contradiction and distinguished
  base-unit parent granularity from inferred latency/intent. F01–F34 and C01/C02
  remain unchanged. No recovered 80–90% controller or economic alpha is claimed.
  The complete suite passes 217 tests and deterministic saved-YAML replay.
- **v4 · 27 October 2026:** Added the autonomous-controller assessment from
  `8524844` as a constraint, with the relevant baseline, event F1 definition,
  opening contradictions and competing simple controller. Recorded the 49/59
  conditional duplicate-quantity observation without promoting it to a general
  trigger. F01–F34 and C01/C02 remain unchanged. No full-controller 80–90% match
  or economic alpha is claimed. The complete research suite passes 201 tests.
- **v3 · 27 October 2026:** Added F31–F34 from `58ae0cf`: observed request
  granularity, ordinary first-fill sequencing, transient call-tail mismatches
  and the 31/31 carry-book quantity condition. Clarified F01's first-pair versus
  first-exposure distinction without changing its rate. Added rapid-reversal
  limits and the full operational playbook. Independent raw accounting matches
  24,860 cached quantity and 25,565 marked-P&L snapshots over 41,421 fills;
  all 190 research tests pass. C01/C02 remain unchanged. No exact original
  trigger or economic alpha is promoted.
- **v2 · 27 October 2026:** Added the controlled cover-to-re-entry assessment
  from `984164c` as a constraint, including weak balance/common support and the
  NIFTY/SENSEX distinction. F01–F30 and C01/C02 remain unchanged; no new rate or
  original trigger is promoted. The expanded research suite passes 177 tests.
- **v1 · 27 October 2026:** Consolidated F01–F30 from the research through
  `60427b2`; corrected skipped-entry and exit-time scopes; computed joint
  opening C01 and recurring-window C02; kept unverified controllers outside
  the strong register. Created this dedicated branch/reference file.
