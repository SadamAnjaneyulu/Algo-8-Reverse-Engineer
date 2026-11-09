# Algo 8 — Strategy Reconstruction Readiness

Part of the [complete reconstruction audit](ALGO8_COMPLETE_RECONSTRUCTION_AUDIT.md) ·
[findings register](ALGO8_MASTER_FINDINGS_REGISTER.md) · [strategy specification](ALGO8_STRATEGY_SPECIFICATION.md) ·
[data gaps](ALGO8_DATA_GAPS_AND_REQUIREMENTS.md) · [roadmap](ALGO8_RECONSTRUCTION_ROADMAP.md)

## 1. Readiness matrix

Implementation levels used in the last two columns (defined before scoring):

| Level | Meaning | Score |
|---|---|---:|
| **Exact** | Rule identified and validated; an implementation would reproduce the original decisions | 1.00 |
| **Approximate – high** | Implementable; reproduces the observed behaviour in ≳ 80–90 % of measured cases, with stated exceptions | 0.75 |
| **Approximate** | Implementable; reproduces roughly half to most of the measured cases | 0.50 |
| **Approximate – low** | Only part of the behaviour (e.g. timing or quantity) can be implemented; the trigger is unknown | 0.25 |
| **Not possible yet** | No rule or model reaches even rough fidelity; a placeholder would be a guess | 0.00 |

| # | Component | What we know | What remains unknown | Evidence quality | Can we implement it? | Exact / Approximate / Not possible yet |
|---|---|---|---|---|---|---|
| 1 | **Entry timing** | 09:16 opening (31/32); 17 pre-expiry windows 544/544; D0 windows while the book is active (95.1 % / 100 %) | Extra-sale trigger; D0 active-book state autonomously; 5 Oct delay; eligibility | Strong, in-sample, two lineages agree | Yes for the schedule | **Approximate – high** (0.75) |
| 2 | **Strike selection** | Opening nearest ATM to the 09:15 close (31/31); later within one strike 95–97 %, exact ≈ 70 %; directional shift for extra sales (later 33/39, 26/34) | Exact selector for later/extra sales; quote source; the P4 68.5 % model is unverified | Strong for opening; partial later | Yes, approximately | **Approximate** (0.50) |
| 3 | **Initial position construction** | Four roles; wings first within 1–5 s; seed wings ± 2,000 / ± 4,000 (SENSEX change 16 Sep); joint structure 28/32 | Reason for the SENSEX change and exceptions; split across strikes | Strong | Yes | **Approximate – high** (0.75) |
| 4 | **Initial quantity** | 3 base units per role (195 / 60): 13/14, 15/17 dates | Exceptions (21 Sep, 30 Sep, 14 Oct); capital/margin link | Strong | Yes | **Approximate – high** (0.75) |
| 5 | **Dynamic quantity management** | Base-unit ladder modes (3, 2, 3, 1, …); D0 ladder differs; child unit 65/20 | Per-day variation (templates ≈ 50 % of later slots; best model 45 %); exposure ceiling; capital formula | Partial | Only as modal templates | **Approximate – low** (0.25) |
| 6 | **Scheduled rebalancing** (grid A / :00 rebalances, Clock-B replacement) | Clock times; replacement re-sells the same lots at ATM ≈ 28 s later | Whether a tick rebalances; which contract | Partial | Timing and replacement only | **Approximate – low** (0.25) |
| 7 | **Intermediate exits** (overall) | Many categories classified (EXT-01); losing covers follow adverse moves | No tested rule ≥ 30 % precision and recall jointly; frozen global first-reduction match ≈ 29 % | Strong negative evidence | No | **Not possible yet** (0.00) |
| 8 | **Individual stops** | One lot at a time; D-1 response 88 % within 1 min at 1.7× cheapest entry (38 % at 1.55×); coverage of stop-like exits ≈ 45 % | Exact constant and reference (lot entry, allocation, tick LTP); D0 scope | Strong existence; level bracketed | Yes, approximately (D-1) | **Approximate – low** (0.25) |
| 9 | **Side-level exits** | Exist (5.7 % of lots); clock / time-to-expiry dominate timing | Trigger (VAL tree precision 0.11) | Negative | No | **Not possible yet** (0.00) |
| 10 | **Basket-level exits** | Exist (11.8 %); same picture | Trigger (VAL tree precision 0.05) | Negative | No | **Not possible yet** (0.00) |
| 11 | **Clock B** | Tick times; 42–47 % of ticks act; 1 lot; re-sell at ATM | Act/no-act rule (AUC 0.78; tree 0.77 / 0.55); contract choice (hit 0.66 vs 0.41) | Partial | Timing, quantity, replacement | **Approximate – low** (0.25) |
| 12 | **Contract selection** (in reductions / Clock B) | Largest exposure / most lots is the best single criterion | Exact rule; allocation identity | Partial | No reliable rule | **Not possible yet** (0.00) |
| 13 | **Re-entry and replacement** | Same-side sale within 60 s after 55 % of unscheduled buy-back episodes; replacement lots = closed lots | Re-entry trigger; association ≠ instruction | Partial | Replacement rule only | **Approximate – low** (0.25) |
| 14 | **Hedge adjustment** (later wings, replacements, releases, lump) | Routine budget ≈ 2.5 % of ATM premium (± 1 strike 92–95 %); expiry replacements inward (81.5 %); lump on heavier short side | Exact strikes (≈ 50 %); late/large protection trigger; release quantity; **lump size** | Mixed | Routine wings yes; the rest no | **Approximate – low** (0.25) |
| 15 | **Carry-forward logic** | The carry book = surviving allocations; long ≥ short per right 31/31; carried lots unwound gradually | 4 % carry SL; lump sizing; carried-lot stop scope | Partial | Inventory only | **Approximate – low** (0.25) |
| 16 | **Cycle stops** | Cumulative LTP MTM ≈ −₹1.30–1.35 L; D-1 and D0; size-independent; 1–20 s latency; no re-entry after | Exact constant and its origin; tick-level trigger | Strong (12 events, exact quotes) | Yes | **Approximate – high** (0.75) |
| 17 | **Expiry-day stops** ("1 % of capital") | ₹2 L reading contradicted by the data | What "1 %" refers to | Negative | No | **Not possible yet** (0.00) |
| 18 | **Final flattening** | 15:14 in 9/10 later-period late closures; 27/29 by 15:27:33; best later program 7/12 within 2 min | Earlier-period rule; residual wings; configuration history | Strong (later period) | Yes for the later period | **Approximate** (0.50) |
| 19 | **Execution and order handling** | Tags, base-unit children, LTP × 1.15 / 0.85 limits, IOC/DAY, fills ≤ 57 s | Cancellations, rejections, retries, poll cadence, pending-order handling | Strong for what is logged | Yes | **Approximate – high** (0.75) |

## 2. Estimated coverage score (a subjective evidence index, not a probability)

**Calculation.** Unweighted mean of the scores in the matrix:

  | Level | Rows | Count | Contribution |
  |---|---|---:|---:|
  | Exact | — | 0 | 0.00 |
  | Approximate – high | 1, 3, 4, 16, 19 | 5 | 3.75 |
  | Approximate | 2, 18 | 2 | 1.00 |
  | Approximate – low | 5, 6, 8, 11, 13, 14, 15 | 7 | 1.75 |
  | Not possible yet | 7, 9, 10, 12, 17 | 5 | 0.00 |
  | **Total** | | **19** | **6.50** |

- **Estimated coverage score = 6.50 / 19 = 34 %.**

**Sensitivity.** If "approximate – low" counts as 0 (only usable parts count), the score is 4.75 / 19 = **25 %**. If every
implementable approximation counts as 1, the share of components that can be implemented at all is 14 / 19 = **74 %**.
The share implemented **exactly** is **0 / 19**.

**Methodology and limits.** The 19 components and the five levels were fixed before scoring. Each component was placed
by judgement from the register's evidence (precision / recall, coverage, whether the trigger is known), then scored
unweighted. It is therefore a **subjective, unweighted evidence-and-readiness index**. It is **not** the fraction of code or
decision logic recovered, and it does not use PR #1's or PR #3's classifier metrics directly. Re-examining the matrix after the
9 Nov reconciliation changed no component: the stop-definition check (audit §7A) left row 8 at Approximate – low, and
PR #1's artifact (0 / 20 tasks at 75 %) left rows 7, 9, 10, 12 and 13 unchanged.

**What the score means.** Read it as "about a third of the strategy's components are understood well enough to implement
with fair-to-high fidelity". It is not a probability that a replica would behave like Algo 8, and components are not
equally important. Exits (rows 7–12, 17) carry most of the unexplained behaviour and score 0–0.25.

## 3. Direct answers

1. **Can we reproduce the opening book?** **Approximately, yes.** Timing, ATM strike, four roles, seed-wing distances and
   3-unit sizes match 28/32 sessions jointly (C01). Exceptions and the exact quote input remain.
2. **Can we reproduce the subsequent position changes?** **Partly.** The scheduled ladder (times, ATM strikes, wings) is
   reproducible. Per-slot quantities only match about half the time. Extra sales, reductions and re-entries are not
   reproducible as rules.
3. **Can we reproduce the complete exit engine?** **No.** The cycle stop and late flatten are approximately reproducible.
   The per-lot stop is reproducible on D-1 only as a band (≈ 1.6–1.7×), with ≈ 45 % coverage. Side-level, basket,
   partial and Clock-B decisions are not.
4. **Can we reproduce the strategy's risk management?** **Partly.** The cycle stop: yes, approximately. The 4 % carry SL,
   the expiry-day 1 % stop, side/basket limits and capital/margin sizing: no.
5. **Can we reproduce the complete order-generation process?** **No.** Child-order units, pricing and tags are known.
   Decision timestamps for body orders, unfilled requests, cancellations and allocation identities are not in the data.
6. **Can we build a faithful historical simulator?** **Yes, as an accounting simulator of the recorded orders.** The teacher-
   forced replay reproduces features and P&L exactly. **No, as a simulator of Algo 8's decisions**: the decision rules are
   incomplete.
7. **Can we build an autonomous model that makes similar decisions without seeing the actual future orders?** **Only a
   coarse one.** Lineage X's best autonomous controller reaches a later event macro-F1 of 23–24 %. Lineage Y's
   autonomous replay matches actual exits with precision 0.40 / recall 0.24 on TEST when given the actual entries, and
   0.37 / 0.12 fully autonomously. PR #1's replay abstained (0 orders). None approaches the 80 % target; these are
   different measures (audit §7.0) and are not combined.
8. **What percentage of the complete strategy is genuinely understood?** The estimated coverage score is **≈ 34 %**
   (25–34 % depending on how partial components are counted; 0 % exact), calculated above. It is not a probability of
   exact replication.

## 3a. The same evidence partitioned by what can be done

| Partition | Components / rules |
|---|---|
| **Implementable with high confidence** | 17 pre-expiry windows; 09:16 opening, ATM seed strikes, wings, 3-unit size; base-unit child orders, limit band, tags; cycle stop (constant approximate); 15:14 flatten (later period) |
| **Only approximable** | D-1 per-lot stop band 1.6–1.7× of the cheapest entry (≈ 45 % coverage); later strikes; routine wings; modal ladder quantities; Clock-B timing / one-lot ATM re-sale; carry book |
| **Triggers unknown** | extra sales; side-level / basket / partial reductions; Clock-B act / no-act and choice; D0 stop scope; re-entry |
| **Blocked by missing data** | lump size; sizing and exposure ceiling; 4 % / 1 % denominators; eligibility; pending orders; allocation ownership; tick-level stop timing |
| **Requires genuinely new historical observations** | out-of-sample validation of any decision rule; more cycle stops; no-trade sessions |

## 4. Approximate behavioural replica vs exact reconstruction

* An **approximate behavioural replica** can be built now. It would follow the specification's
  [executable approximation](ALGO8_STRATEGY_SPECIFICATION.md#executable-approximation-for-a-first-replica--clearly-labelled):
  same calendar, clocks, ATM strikes, wings, base units, a D-1 stop band, the cycle stop and the late flatten. The existing
  rule clone already does a subset of this and reaches per-cycle P&L correlation **0.48** (ALP-03).
* **Is an approximate behavioural replica possible?** Yes, now, with explicit placeholders and per-component fidelity.
  **Is exact reconstruction possible from the current data?** No.
* An **exact reconstruction** cannot be built now. Five components have no usable rule and seven are only partly
  implementable. A replica that produces similar P&L or similar-looking orders would still not be the original strategy.
