# TP-03 · Phase 0: research audit and pre-registration

Written and committed **before** any TP-03 experiment. Definitions and thresholds are fixed in [`tp03/config.yaml`](tp03/config.yaml). Nothing below is a result; "established" items are quoted from earlier milestones with their register IDs and are **re-verified in Phase 1 / 2, not assumed**.
Entry-trigger reconstruction (Part B) and exit-trigger reconstruction (Part C) are kept separate throughout and use separate Holm families.

## A. Scope, state and rules

| Item | Value |
|---|---|
| Branch | `research/tp03-entry-exit-trigger-reconstruction`, created from TP-02 head `a5feffafb5ba230f52ec8232390de3a8e10fb774` |
| Verification | `origin/research/tp02-exit-mechanism-attribution` = `a5feffaf` = PR #11 head; TP-01 tip `086b8612` (PR #10) is its ancestor; no discrepancy |
| Not touched | PR #8, #9, #10, #11 and their branches; nothing merged; TP-01 / TP-02 outputs read-only |
| Untracked | `stage2_alpha_research/` (alpha-branch caches, never committed here) |
| Data | `Trades_GKOHNP140.csv` (41,421 fills, 39,874 parent orders, 35 cycles, 65 sessions); raw Breeze 1-minute bars (index; options only for contracts Algo 8 traded); TP-01 ledger / roles / episodes; TP-02 timelines, mechanisms, exposure panel |
| Reused code | `tp_reconstruction/scripts/` (`matching.py`, `tp_common.py`, `market_data.py`), `tp02/scripts/tp02_common.py` (tag-time decoding, number blocks, phases), `risk_rule_validation/` stop readings A–E |
| Evidence classes | CONFIRMED / STRONGLY_SUPPORTED / WEAKLY_SUPPORTED / UNRESOLVED / NOT_TESTABLE, defined operationally in `config.yaml` (`evidence_rubric`) |
| Boundaries | no alpha discovery, no supervised model, no threshold sweep, no future information, no invented delta / gamma / vega / IV / margin |

All 65 sessions were inspected before; **every result is in-sample and exploratory**; no external validation is claimed.

## B. ENTRY-trigger reconstruction

### B1. What is already established (to be re-verified)
| Component | Earlier finding (register ID, class) | Sample |
|---|---|---|
| First paired CE/PE short at 09:16 on the pre-expiry session | ENT-01, strong; exception NIFTY 5 Oct (09:30:59) | 31/32 |
| 17 recurring pre-expiry windows with fresh same-strike CE/PE shorts (09:30 … 14:30; 12:15, 12:45, 13:00, 13:15 inconsistent) | ENT-02: 544/544 session-windows; joint structure 529/544 (97.2 %) | 32 cycles |
| Expiry day: fresh shorts at quarter windows while the book is active | ENT-03: timer + active-book baseline precision 95.1 %, recall 100 % | 273 windows |
| Child unit 65 NIFTY / 20 SENSEX; opening book 195 / 60 units per role | SIZ-01, SIZ-02 (exceptions 21 Sep 325; 30 Sep 40; 14 Oct 60/80) | all / 13 of 14, 15 of 17 |
| Opening strike `K = d·floor(S/d + 0.5)` on the completed 09:15 close | STK-01, 31/31 ordinary starts | 31 |
| Later strikes within one strike of the previous-minute ATM; exact only ≈ 70 % | STK-02, partial | 501 / 579 |
| Seed wings ± 2,000 (NIFTY); ± 4,000 then ± 2,000 from 16 Sep (SENSEX) | HDG-01 | 26/28, 21/22, 12/12 |
| Routine wing: highest OTM premium ≤ 2.5 % of the ATM leg; exact strike ≈ 50 %, within one strike 92–95 % | HDG-02, HDG-03 | ≈ 1,260 |
| Old exposure retained across windows; carry book long ≥ short per right | MGT-01, HDG-05 | 544/544; 31/31 |
| No classical indicator, direction or IV filter on additions | STR-03, ENT-05 | counter-examples |

### B2. What remains unresolved
1. **Whether additions are state-gated at all.** On the pre-expiry day 544/544 windows were active, so the schedule itself looks deterministic; the open questions are the **quantity ladder** (modal 3, 2, 3, 1, 4, 1, 2 …; lineages disagree at 10:15/10:16), the **zero-quantity / skipped windows** (12:15, 12:45, 13:00, 13:15; D0 windows with an inactive book) and the **extra off-schedule sales** (ENT-04: timer gating, AUC 0.887 on a ranking, not an executable rule).
2. **Exact strike selector** (STK-02/03/04: ≈ 70 % exact; tilt toward the move is a post-hoc hypothesis).
3. **Exact wing selector** (HDG-02: ≈ 50 % exact strike; wing quantity ratio unknown).
4. **Capital / margin sizing** (SIZ-05): not recoverable without margin data.
5. **Lump (`v_`) size** (SIZ-04), **re-entry trigger** (MGT-07).
6. **D-1 versus D0**: D0 shows more gross trading (31,293 fills, 2.22 M units vs 10,128 fills, 0.57 M units pre-expiry); whether D0 creates more inventory or only trades and closes more has not been separated into opening, closing and net units.

### B3. Data limits that bind the entry analysis
| Limit | Consequence |
|---|---|
| Option bars exist only for contracts Algo 8 traded (universe selected by its trading; Stage 2 M1 leak of +0.88 between universe centre and the day's move) | strike-selection alternatives are partly invisible; **no claim about the full eligibility universe**; coverage of each alternative is recorded per window and a window with unavailable alternatives cannot test a "nearest" rule |
| Body-order decision time is unavailable (bounds only) | state is measured at two bounds (S0 earliest, S1 latest) and conclusions must survive both |
| The algorithm's own quote at decision time is recoverable only for the traded contract (limit ÷ 1.15 or ÷ 0.85, DAT-05) | used as the premium reference for the traded strike and wing; other contracts use bars |
| No margin, SPAN, capital use, Greeks or IV | margin / capital sizing is **NOT_TESTABLE**; only the labelled proxy `gross_short_notional` is computed |
| Missing record ≠ no action | skipped windows are classified (below); a window without evidence that the system was running is `NO_ACTION_UNCERTAIN`, never a confirmed skip |
| Three cycles have no pre-expiry session in the export; NIFTY 29 Sep has no D0 fills | those cycle-days are `NOT_APPLICABLE`, not skips |
| Whole-second fills; equal-second ordering ambiguity (6 fills) | tie orderings carried from TP-01 |

### B4. Window-level dataset (Phase 1 design)
One row per **opportunity**, action and no-action alike, per underlying and cycle: pre-expiry day (opening 09:16, 17 registered windows, 4 control windows) and expiry day (15-minute windows 09:30–15:00). Columns: window id, classification (`ACTION`, `NO_ACTION_ACTIVE`, `NO_ACTION_UNCERTAIN`, `NOT_APPLICABLE`), reason, data-completeness flags, pre-window state at S0 and S1 (feature list in `config.yaml`), and for actions the parent orders, units (requested and filled), strikes, wings, net inventory change. State is always measured **before** the window opens (`T − 2 s`), never from the order's own fills.

### B5. Entry hypotheses, tests and falsifiers
| # | Hypothesis | Test (registered) | Falsified if |
|---|---|---|---|
| E1 | Deterministic schedule: an addition occurs at every registered window of an active cycle regardless of state | per-window action rate with Wilson interval; list every `NO_ACTION_ACTIVE` window individually; state vs action by permutation inside cycle × window strata | the action rate is materially < 100 % **and** skips associate with state beyond chance (Holm) |
| E2 | State-gated addition: skipping or adding depends on pre-window state | same permutation test per registered feature (family of 25 features, Holm) | no feature survives Holm in both underlyings, or the association disappears at S0 / S1 |
| E3 | Quantity = ladder template (fixed units per slot) | share of window observations equal to the slot mode; deviations vs state (Holm); base-unit multiples | the slot mode explains < 80 % of observations **or** deviations are explained by state |
| E4 | Capital / margin gates additions | **NOT_TESTABLE**; proxy association with `gross_short_notional` reported as a proxy only | — |
| E5 | Strike = ATM of the last completed index close (rounded to the step) | exact-match rate under R1 / R2 (and R3 for the opening); directional tilt by sign test against the previous 10 / 15-minute move; alternatives' availability recorded | exact match < 99 % under every reference (not CONFIRMED); tilt not significant → no tilt rule |
| E6 | Wing = highest OTM strike with premium ≤ 2.5 % of the ATM leg quote | exact-match under the three premium references; neighbour-strike coverage; alternative budget values reported as a **sensitivity set**, not a search | exact match < 99 % → remains STRONGLY_SUPPORTED at best; ownership alternatives reported |
| E7 | Wing quantity tracks short quantity | wing/body unit ratio per window under three matching conventions | ratio varies without a stable mode |
| E8 | Re-entry follows closures | time-shift null for same-side openings after closing batches (reuses TP-02 flags) | excess over chance not distinguishable from zero |

### B6. D-1 versus D0 reconciliation (accounting, no hypothesis)
Per cycle and day type: opening units, closing units, net inventory change, gross traded units, parent orders, distinct contracts, starting and ending inventory, CE / PE inventory changes. Identity checked: `opened − closed = Δinventory` per contract; reconciled to the TP-01 totals (opened 1,414,545; closed 1,377,065; remaining 37,480). Gross volume is never used as evidence of net book-building.

## C. EXIT-trigger reconstruction

### C1. What is already established (TP-01, TP-02, Stage 1)
| Finding | Source |
|---|---|
| 4.0 % of short closings are `s_` cycle-stop liquidations (12 cycles); 56.3 % are STOP_POSSIBLE on price / timing only | TP-02 (EXT-14) |
| Per-lot stop-like response near 1.6–1.7× the cheapest open entry on D-1 (constant and reference unresolved; 0 of 18 rules reach 80/80) | EXT-02–04, ALC-03 |
| Cycle stop on cumulative D-1 + D0 mark-to-market ≈ −₹1.38 to −1.43 L at quote-based marks | RSK-01, risk-rule study |
| Closing hazard 2.70× at minute-of-hour :14 :29 :44 :59 (Holm 0.03); 09:15 cluster 82 % stop-related; late expiry-day activity | TP-02 (EXT-15) |
| 50 % of clean profitable body closings are in ≥ 2-contract batches (43 points above chance); wing closings accompany body closings (84 % vs 12 %) | TP-02 |
| No fixed premium-decay take-profit; replacement and re-adding not above chance; no cycle mark-to-market level distinguishable (minute-level) | TP-01, TP-02 |
| Rahul's 4 % carry stop (readings A–D) and the ₹2 L expiry-day kill switch were inconsistent with behaviour; reading E not identifiable | RSK-07–09 |
| Side-level and basket reductions are timed by clock / time-to-expiry; contract choice partly predictable (largest exposure hit@1 0.77 vs 0.47) | MGT-05, MGT-06 |

### C2. What remains unresolved
The **decision that starts a batch**; **which contracts it selects**; whether the 15-minute concentration is a decision timer, an execution artefact or both; the expiry-day afternoon driver (decay, time, risk or schedule); how wings are released relative to bodies; and whether Rahul's stop readings fail because they are wrong or because the reconstruction is limited.

### C3. Data limits that bind the exit analysis
Decision times of `num` orders are unavailable (bounds only); lot ownership is unidentified (three conventions); no decision logs; marks are 1-minute closes of contracts Algo 8 traded; no Greeks, IV or margin; the cycle-stop constant is known only within ₹1.22–1.36 L; stale index closing minutes on 96 sessions (DAT-15, alpha branch) are excluded from market features.

### C4. Batch reconstruction (Phase 2 design)
Unit = **parent order** (partial fills of one parent are one decision). Primary batch = consecutive closing parent orders of one underlying with gaps ≤ 10 s; sensitivities at 2, 5, 30, 60 s and an order-number-block definition (one app key, one number block, consecutive numbers). Each batch records: members, rights, strikes, short-body versus long-wing, CE / PE, mixed, profit / loss labels (three conventions), stop class (TP-02), expiry class, 15-minute tick, and the pre-batch portfolio state at S0 and S1.

### C5. Competing exit explanations and the tests that separate them
| # | Hypothesis | Predicts | Test (registered) | Falsified if |
|---|---|---|---|---|
| X1 | Individual-position exit | closed vs retained contracts separate on a **per-position** criterion; closings follow the first passage of that criterion; sides need not be pure | within each decision opportunity rank the open contracts on the registered position metrics; AUC of closed vs retained (cycle-clustered), first-passage ordering | no position metric separates closed from retained beyond chance (Holm) |
| X2 | Side-level exit | selection is side-pure beyond chance; a side-level state variable determines which side | side purity vs permutation of closures among open contracts of the same size; side MTM / side premium ratio explain the side | purity at chance; side state uninformative |
| X3 | Portfolio-level exit | batch timing tracks a cycle-level state crossing; the same state precedes batches in both underlyings | pre-batch portfolio metrics vs exposed non-batch minutes with the max-statistic permutation (inside cycle × day-type × hour strata) | no metric distinguishable; metric differs between underlyings |
| X4 | Scheduled workflow with an internal condition | decisions only at ticks; which contracts close depends on a condition | tick residue test over all 15 residues; **order-entry minute** (independent of execution) also concentrated; share of open contracts closed per tick; composition of selected vs retained | concentration only in fill time, not in order-entry minute; or closing probability equal across contracts |
| X5 | Expiry-management process | timing depends on time to expiry and session phase, selection on absolute premium / size, not on state | hazard by minutes-to-expiry and absolute premium bins (fixed bins; max-statistic permutation); D0 vs D-1 composition | state variables explain more than time and premium |
| X6 | Execution batching / coincidence | apparent batches are chance co-occurrences or one execution loop with no shared property | inter-order gaps vs a Poisson null at the same time-of-day intensity; shared property of members vs random subsets; submission order within one number block | members share a property beyond chance and gaps are shorter than the null |

Two or more may hold at different times. If the registered tests cannot separate them the verdict is **UNRESOLVED**, never the explanation that fits most events.

### C6. 15-minute behaviour
(1) All 15 minute-of-hour residues for closings versus exposed minutes, by day type, phase, module, body versus wing, profit versus loss and **pre-expiry day** (TP-02 pooled them); (2) the same residues on the **order-entry minute** (minute-stamped, independent of fill time) to test the execution-timestamp explanation; (3) at each tick the fraction of open contracts closed and the composition of the selected set; (4) the same tests outside expiry-day sessions. The pattern is **not** called a timer unless (1)–(4) agree.

### C7. Expiry-day exits
Separate analyses for 09:15, 14:29–14:59, 15:14, 15:19 and other expiry-day closings: hazard against minutes to expiry, absolute premium, position-level loss and cycle mark-to-market; inventory reduction pattern per tick; salvage thresholds (≤ ₹1, ≤ 5 % of entry) remain **labels**, not rules.

### C8. Wing release
Order of wing and body closing orders (inside one number block where comparable), time offset distribution, wing units against body units closed and against remaining body units, CE / PE coupling, wings retained after body closure. Ownership alternatives: nearest-time same-right matching, proportional matching, FIFO matching; conclusions that change with the matching are reported as sensitive.

### C9. Rahul's stated rules (client-provided hypotheses, retested unchanged)
Readings A–E of the 4 % carry stop and the ₹2,00,000 expiry-day kill switch, exactly as defined in the risk-rule study (no constant tuned), recomputed with fills-based state at **S0 and S1**; threshold timestamps are compared with actual liquidation orders (5-minute match window; GT1 / GT2 portfolio matches); failures are classified as *rule fails* only when the discrepancy exceeds what price, ownership and decision-time uncertainty can explain, otherwise `UNRESOLVED`.

### C10. Decision-time handling (both programs)
Tagged orders: validated tag time. Body orders: **S0** = order-entry minute start (earliest), **S1** = first fill (latest). State is computed from fills strictly before the bound and from marks of the last completed bar before it. A conclusion is reported as robust only if it holds at both bounds; otherwise it is `WEAKLY_SUPPORTED` or `UNRESOLVED`. No post-decision price enters any predictor.

## D. Statistical plan
* Independence unit: expiry cycle (underlying × expiry); fills, orders and minutes within a cycle are never treated as independent.
* Permutation labels shuffled only inside cycle × day-type × hour strata (500 permutations); bootstrap over whole cycles (1,000 resamples); Holm within the entry family and, separately, the exit family. Max-statistics are used wherever a bin or residue is searched.
* NIFTY and SENSEX are reported separately before pooling; every result also by expiry cycle.
* Fixed candidate lists only (features, bins, windows in `config.yaml`); no threshold sweep. A numeric threshold may be reported only as the output of a registered max-statistic, never as a tuned parameter.
* Sensitivities: decision-time bound (S0 / S1), matching convention (FIFO / LIFO / AVG), batch gap (2–60 s and block definition), premium reference (three), tie ordering.
* Negative results are reported in full. Hazard ratios, AUCs and exact-match rates are descriptive; **no association is converted into a rule without a direct decision-evidence or deterministic-reproduction test**.

## E. Known confounders
Time of day and expiry proximity (every state variable is correlated with the clock); opening position size; strike-universe selection by the algorithm's own trading; the clock grid itself (the schedule creates the residues); module heterogeneity (`s_ h_ v_ m_ num`); stop-module overshoot contaminating batches near stops (TP-02 stop windows are excluded or flagged); ownership ambiguity; 1-minute marks and carried prices; the three cycles without a pre-expiry session and the one without D0; one trading day per cycle on the pre-expiry side (no within-cycle replication).

## F. Acceptance criteria (mapping to the 15 required checks)
| # | Criterion | Evidence that it is met |
|---|---|---|
| 1–2 | Entry opportunities and actions reconstructed; skipped windows separated from missing data | window dataset with the four classes and reasons; each `NO_ACTION_ACTIVE` window listed |
| 3–4 | Quantity and strike selection examined inside the available universe | E3, E5 tables with alternative-availability flags |
| 5 | Hedge creation and release analysed | E6, E7, C8 |
| 6 | D-1 / D0 gross separated from net | B6 table with identity checks |
| 7 | Batches without double counting | parent-order unit; gap and block sensitivities |
| 8–9 | Pre-event state; individual vs side vs portfolio compared | X1–X6 tests with Holm |
| 10 | 15-minute pattern tested without assuming a timer | C6 (1)–(4) |
| 11–12 | Expiry-day exits; stop rules checked | C7, C9 |
| 13 | Decision-time uncertainty explicit | S0 / S1 reported for every state-based result |
| 14 | Reproducible | `run_tp03.py`, two identical full runs, tests |
| 15 | Unknowns and missing data documented | per-component table with `NOT_TESTABLE` / `UNRESOLVED` and the missing evidence named |

## G. How "what fraction of the architecture is mapped" will be defined (no invented percentage)
Two denominators, both reported: (a) the **14 decision components** of the final table (initial entry … re-entry), counted by evidence class (unweighted); (b) **event coverage**: share of the 39,874 parent orders (and of gross units) that a recovered CONFIRMED or STRONGLY_SUPPORTED rule assigns to a component with a stated reproduction rate. A coverage figure is reported only with its numerator, denominator and rule; it is not a readiness score.

## H. Deliverables and order of work
Phase 0 (this document and `config.yaml`) → **review checkpoint** → Phase 1 entry (`TP03_ENTRY_REPORT.md`) → Phase 2 exit (`TP03_EXIT_REPORT.md`) → Phase 3 join (`TP03_REPORT.md`, `ALGO8_DECISION_FLOW.md`, final component table). Data: entry opportunities and actions, skipped windows, quantity and strike selection, closing batches, pre-exit portfolio state, body / wing closure relationships, D-1 vs D0 inventory. No alpha discovery, supervised learning or model training at any stage.

## I. Expected blockers (stated in advance)
1. If the pre-expiry day has no `NO_ACTION_ACTIVE` window at all, E1 / E2 cannot be tested on it; the expiry-day active-book windows and the zero-quantity control windows then carry the skip analysis, with small samples.
2. Strike and wing alternatives are only partly observable, so E5 / E6 may remain STRONGLY_SUPPORTED rather than CONFIRMED.
3. Without decision logs or body-order decision times, X1–X6 may remain partly UNRESOLVED; the report will name the exact missing evidence for each.
