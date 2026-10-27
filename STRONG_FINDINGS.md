# Algo 8 — cumulative strong findings

**Updated:** 27 October 2026 · **Version:** 2 · **Branch:** `research/strong-findings`

**Evidence snapshot:** F01–F30 and C01/C02 use research/data inherited from
`60427b2`. The additional cover-to-re-entry assessment is from `984164c`.

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

## 1. Opening entries and the initial protection

| ID | Strong finding | Evidence and scope | Meaning / limit |
| --- | --- | --- | --- |
| F01 | The first paired CE/PE short sale normally starts in **09:16 IST**. | **31/32 sessions, 96.9%.** The exception is NIFTY 5 October at 09:30:59. | Observed timing; eligible no-trade dates are not fully labeled. |
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

## 9. Verified constraints and claims excluded from the strong register

These constraints prevent the strong findings from being combined incorrectly:

- **Separate-side closure is directly observed.** On 13 July, initial NIFTY
  24000 CE shorts close in 65-unit pieces at 09:50, 09:53 and 09:59 while their
  26000 CE protection is sold. Initial PE/22000 PE protection survives. New
  24050 CE/PE shorts had been added at 09:30 while the original holdings remained.
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
[latest controller search](research/DEEP_CONTROLLER_FINDINGS.md),
[economic candidate limits](research/ALPHA_CANDIDATE_FINDINGS.md).

## 10. How to add the next strong finding

1. Append a new stable **F31, F32, …** ID; do not silently rewrite an old claim.
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

- **v2 · 27 October 2026:** Added the controlled cover-to-re-entry assessment
  from `984164c` as a constraint, including weak balance/common support and the
  NIFTY/SENSEX distinction. F01–F30 and C01/C02 remain unchanged; no new rate or
  original trigger is promoted. The expanded research suite passes 177 tests.
- **v1 · 27 October 2026:** Consolidated F01–F30 from the research through
  `60427b2`; corrected skipped-entry and exit-time scopes; computed joint
  opening C01 and recurring-window C02; kept unverified controllers outside
  the strong register. Created this dedicated branch/reference file.
