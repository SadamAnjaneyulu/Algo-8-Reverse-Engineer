# TP-03 · Phase 0: research audit and pre-registration (amended, v2)

Written and committed **before** any TP-03 experiment. Definitions and thresholds are fixed in [`tp03/config.yaml`](tp03/config.yaml) (v2). "Established" items are quoted from earlier milestones with register IDs and are **re-verified in Phase 1 / 2, not assumed**. Entry-trigger reconstruction (Part B) and exit-trigger reconstruction (Part C) are kept separate and use separate Holm families.
Execution sequence (reviewer's instruction): **Phase 1 entry only → stop for review of `TP03_ENTRY_REPORT.md` → Phase 2 exit only → stop for review of `TP03_EXIT_REPORT.md` → Phase 3 join.** The programs are not run back to back.

## 0. Amendment log (review of Phase 0, 7 points)

| # | Review point | What changed | Where |
|---|---|---|---|
| 1 | Reconcile 544/544 and 529/544 | Five counts are now reported separately (expected, any new short, complete paired structure, partial, genuine no-action). 544/544 is **not** an unconditional action rate: the 17 windows were selected because they recur. The 529/544 joint result stays explicit | §B1a, table 1 |
| 2 | Decision-time attribution | Actions are attributed to a window by **submission** (order-entry minute and S0 / S1), never by fill time alone; four attribution classes; one common state snapshot `floor_minute(T − 2 s)` that is never later than the earliest possible decision | §B4, tables 2 |
| 3 | Entry action definition | Opening orders of **every** module are classified; only `num` sells, `s_` overshoot sells and one `h_` sell open shorts; `v_` never opens a short; separate action classes; opening orders are never `NO_ACTION` because of their tag; 44–57 % of body short openings fall outside the candidate windows and are `OFF_WINDOW_ACTION` events | §B4, table 3 |
| 4 | Entry permutation design | The cycle × window design is degenerate (verified: one observation per stratum). New primary design: cycle-block permutation inside underlying × day type; shown non-degenerate; E2 on the action outcome is degenerate on the 17 registered windows and is moved to the 21 candidate windows and expiry-day windows; testability gates | §B5, table 4 |
| 5 | CONFIRMED standard | Claim types (observation, attribution, trigger); a tag or timestamp confirms attribution only; a confirmed trigger needs direct evidence of the condition or a deterministic reproduction of a rule specified **before** the fit; an in-sample fit tops out at STRONGLY_SUPPORTED | §A, `config.yaml` |
| 6 | 15-minute test alignment | Two separate tests: the full mod-15 test over **all 15 residues** (config now lists 0–14) and the exact observed clock-minute candidates (the 7 TP-01 minutes), plus descriptive grid labels that are not test inputs | §C6, `config.yaml` |
| 7 | Statistical resolution; stop figures | Final inference uses **10,000 permutations** with a Besag–Clifford sequential rule (and a pre-defined extension to 100,000); family sizes and why 500 cannot pass Holm; the ₹1.38–1.43 L and ₹1.22–1.36 L figures are reconciled | §D, §C0 |
| — | Defect | The v1 `config.yaml` did not parse (an unquoted `>=`); fixed in v2 and the file is parse-checked | `config.yaml` |

The structural counts used for points 1–4 come from [`tp03/scripts/phase0_structure_counts.py`](tp03/scripts/phase0_structure_counts.py): **descriptive denominators only, no state variable, no hypothesis test, no threshold**. The testability gates in §B5 were set after seeing those counts and before any test; they limit what may be claimed, not what is found.

## A. Scope, state and rules

| Item | Value |
|---|---|
| Branch | `research/tp03-entry-exit-trigger-reconstruction`, from TP-02 head `a5feffafb5ba230f52ec8232390de3a8e10fb774` (verified = PR #11 head; TP-01 tip `086b8612` is its ancestor) |
| Not touched | PR #8, #9, #10, #11 and their branches; nothing merged; TP-01 / TP-02 outputs read-only; PR #12 stays a draft |
| Data | `Trades_GKOHNP140.csv` (41,421 fills, 39,874 parent orders, 35 cycles, 65 sessions); raw Breeze 1-minute bars (options only for contracts Algo 8 traded); TP-01 ledger, roles, episodes; TP-02 timelines, mechanisms, exposure panel |
| Reused code | `tp_reconstruction/scripts/` (`matching.py`, `tp_common.py`, `market_data.py`), `tp02/scripts/tp02_common.py` (tag-time decoding, number blocks, phases), `risk_rule_validation/` stop readings A–E |
| Boundaries | no alpha discovery, no supervised model, no threshold sweep, no future information, no invented Greeks / IV / margin |

All 65 sessions were inspected before; **every result is in-sample and exploratory**; no external validation is claimed.

**Evidence standard (point 5).** Every claim carries a *claim type*: **observation** (a fact recorded in the data), **attribution** (which module issued an order and when) or **trigger** (why the algorithm acted).

| Class | Meaning |
|---|---|
| CONFIRMED (observation / attribution) | directly recorded: the fact, the module tag, the validated timestamp. It says nothing about the condition |
| CONFIRMED (trigger) | requires (a) direct evidence of the condition itself and the rule linking it to the action (for example the condition's inputs recorded at the decision, such as the algorithm's own quote carried by an order), **or** (b) a deterministic reproduction of a rule **specified before the fit** (from an independent source such as a client statement), no parameter fitted on the same data, reproduced in both underlyings with every exception explained, and a registered alternative rule matching materially worse. **A match rate, however high, from a rule fitted or selected on these 65 inspected sessions is never CONFIRMED** |
| STRONGLY_SUPPORTED | ≥ 2 independent observations; effect in both underlyings and ≥ 60 % of cycles; Holm-adjusted p < 0.05 in its family; effect above the registered size; survives the decision-time and convention sensitivities. **The ceiling for an in-sample fitted trigger** |
| WEAKLY_SUPPORTED | effect present but fails one of the above |
| UNRESOLVED | the evidence cannot separate competing explanations |
| NOT_TESTABLE | the required source data do not exist |

## B. ENTRY-trigger reconstruction

### B1. What is already established (to be re-verified)
| Component | Earlier finding (register ID, class) | Sample |
|---|---|---|
| First paired CE/PE short at 09:16 on the pre-expiry session | ENT-01, strong; exception NIFTY 5 Oct (09:30:59) | 31/32 |
| 17 recurring pre-expiry windows `[T − 2 s, T + 3 min)` with fresh same-strike CE/PE shorts (09:30 … 14:30; 12:15, 12:45, 13:00, 13:15 inconsistent) | ENT-02 / source F07: same-strike pair in 544/544 session-windows; **joint structure 529/544 (97.2 %)** — see B1a | 32 cycles |
| Expiry day: fresh shorts at quarter windows while the book is active | ENT-03: timer + active-book baseline precision 95.1 %, recall 100 % | 273 windows |
| Child unit 65 NIFTY / 20 SENSEX; opening book 195 / 60 units per role | SIZ-01, SIZ-02 (exceptions 21 Sep 325; 30 Sep 40; 14 Oct 60/80) | all; 13/14, 15/17 |
| Opening strike `K = d·floor(S/d + 0.5)` on the completed 09:15 close | STK-01, 31/31 ordinary starts | 31 |
| Later strikes within one strike of the previous-minute ATM; exact only ≈ 70 % | STK-02, partial | 501 / 579 |
| Seed wings ± 2,000 (NIFTY); ± 4,000 then ± 2,000 from 16 Sep (SENSEX) | HDG-01 | 26/28, 21/22, 12/12 |
| Routine wing: highest OTM premium ≤ 2.5 % of the ATM leg; exact strike ≈ 50 %, within one strike 92–95 % | HDG-02, HDG-03 | ≈ 1,260 |
| Old exposure retained across windows; carry book long ≥ short per right | MGT-01, HDG-05 | 544/544; 31/31 |
| No classical indicator, direction or IV filter on additions | STR-03, ENT-05 | counter-examples |

### B1a. Reconciling 544/544 and 529/544 (point 1)
Source definitions: F07 "each recurring window contains fresh same-strike CE/PE short quantities" (544/544); F08 older short and long exposure survive (544/544); F09 all four roles receive new quantity (541/544); F10 net short quantity grows (530/544); F11–F12 Greek signs (531/543, 533/543); **joint (retention + four roles + short growth + Greek signs) 529/544 = 97.2 %**.
Recount on the TP-01 execution-time ledger, **descriptive counts only** (`phase0_table1_window_reconciliation.csv`):

| Count (session-windows) | 17 registered windows | 4 control windows | All 21 candidate pre-expiry | Expiry day, 23 windows × 33 sessions |
|---|---:|---:|---:|---:|
| Expected | **544** (17 × 32) | 128 | 672 | 759 |
| Any new short, any module | 544 | 43 | 587 | 510 |
| New short by a body (`num`) order | 544 | 43 | 587 | 510 |
| Complete same-strike CE + PE short pair | **544** | 33 | 577 | 412 |
| Partial (body short without a same-strike pair) | 0 | 10 | 10 | 98 |
| All four roles receive new quantity | **541** | 32 | 573 | 477 |
| Net short quantity grows | 529 (source F10: 530) | 38 | 567 | 434 |
| **Joint non-Greek: four roles AND net short growth** | **529** | — | — | — |
| `NO_ACTION_ACTIVE` (system running, no opening) | 0 | **85** | 85 | 40 |
| `NO_ACTION_UNCERTAIN` | 0 | 0 | 0 | 4 |
| `NOT_APPLICABLE` (after a cycle stop, before the first fill, or no open short) | 0 | 0 | 0 | 205 |

What this does and does not say:
* **544/544 means "a new body short pair is observed in the window", not an unconditional action rate.** The 17 windows were *selected because they recur*; the four windows excluded as inconsistent contain the actions that did not recur: of the 128 control session-windows, 43 contain a new short (33 complete pairs) and **85 are genuine no-action windows with the system active**. Over all 21 candidate windows the action rate is 587/672 = 87.4 %, not 100 %.
* The F07 pair count (544) and F09 four-role count (541) reproduce exactly. **529/544 reproduces from the non-Greek components alone** (four roles ∧ net short growth); the Greek components are source-only and are **not recomputed** (no Greeks are invented). The 15 windows that miss the joint contain a new short pair but no net short growth in the window (closings or other flows offset it), not an absent action.
* On the expiry day the schedule is conditional (205 `NOT_APPLICABLE` windows: book inactive, stopped, or not yet started); applicable windows are 554, of which 510 act, 40 are genuine no-action, 4 uncertain.

### B2. What remains unresolved
1. **Whether additions are state-gated.** The registered pre-expiry windows always act (544/544, by selection); gating can only show in the 85 control no-action windows, the expiry-day windows (40 genuine no-action) and in quantity. The **quantity ladder** (modal 3, 2, 3, 1, 4, 1, 2 …; lineages disagree at 10:15/10:16) and the **extra off-schedule sales** (ENT-04: a ranking with AUC 0.887, not an executable rule; **44 % of pre-expiry and 57 % of expiry-day body short openings fall outside every candidate window**) are open.
2. **Exact strike selector** (STK-02/03/04: ≈ 70 % exact; tilt toward the move is a post-hoc hypothesis).
3. **Exact wing selector** (HDG-02: ≈ 50 % exact strike; wing quantity ratio unknown).
4. **Capital / margin sizing** (SIZ-05): not recoverable without margin data.
5. **Lump (`v_`) sizing** (SIZ-04) — `v_` only buys (a hedge), it never opens a short; **re-entry trigger** (MGT-07).
6. **D-1 versus D0**: D0 shows far more gross trading (31,293 fills, 2.22 M units vs 10,128 fills, 0.57 M units pre-expiry); whether it creates more inventory is not yet separated into opening, closing and net units.

### B3. Data limits that bind the entry analysis
| Limit | Consequence |
|---|---|
| Option bars exist only for contracts Algo 8 traded | alternatives to the selected strike are partly invisible; **no claim about the full eligibility universe**; coverage of each alternative is recorded per window |
| Body-order decision time unavailable (order-entry minute only, minute precision) | decision attributed by submission class; state at one snapshot never later than S0, with S1 as sensitivity |
| The algorithm's own quote is recoverable only for the traded contract (limit ÷ 1.15 or ÷ 0.85, DAT-05) | premium reference for the traded strike and wing; other contracts use bars |
| No margin, SPAN, capital use, Greeks, IV | margin / capital sizing **NOT_TESTABLE**; only the labelled proxy `gross_short_notional` |
| Missing record ≠ no action | skipped windows are classified (B4); never inferred from absence of a record alone |
| Three cycles have no pre-expiry session; NIFTY 29 Sep and 1 Sep have no D0 fills | `NOT_APPLICABLE`, not skips (32 pre-expiry and 33 expiry sessions) |
| Whole-second fills; equal-second ordering ambiguity (6 fills) | tie orderings carried from TP-01 |

### B4. Window-level dataset: attribution, snapshot and action classes
**Window.** `[T − 2 s, T + 3 min)`, exclusive upper bound, as in the source; an execution allowance, not a recovered signal time. Pre-expiry: opening 09:16, 17 registered + 4 control windows; expiry day: 15-minute windows 09:30–15:00.

**Attribution by submission (point 2).** A first fill inside a window does not mean the decision was made in it. For a body parent order the only submission time is the **order-entry minute E** (minute precision); tagged orders carry an exact tag time. With `W0m` = the minute containing `T − 2 s`:

| Class | Rule | Treatment |
|---|---|---|
| `SUBMITTED_BEFORE_WINDOW` | `E < W0m` | decision belongs to an earlier time; not an action of this window; its fills are flagged as carry-in |
| `AMBIGUOUS_BOUNDARY_MINUTE` | `E == W0m` | may have been submitted up to 58 s before the window opened; analysed **both included and excluded** |
| `ENTERED_INSIDE_WINDOW` | `W0m < E < W1m` | decision attributable to the window |
| `DECISION_IN_WINDOW_FILL_OUTSIDE` | entered inside, first fill after the window end | attributable to the window; a fill-only count would miss it |

Counts of body short-opening parent orders (`phase0_table2_attribution_classes.csv`): with a fill inside a window, pre-expiry **2,306** (2,140 inside; **166 = 7.2 % boundary-ambiguous**; **0 submitted before**); expiry day **3,791** (3,672 inside; 119 = 3.1 % ambiguous; 0 before); entered inside with the first fill outside: pre-expiry 0, expiry day 3. So the attribution issue is real but small: it is a **boundary** issue, not a systematic early-submission issue, and it is handled explicitly.

**State snapshot reconciled with S0 / S1 (point 2).** S0 = order-entry minute start (or tag time); S1 = first fill of the attributed order. The previously proposed "T − 2 s" snapshot could sit **after** S0 (an order stamped in the minute containing `T − 2 s` has S0 up to 58 s earlier). The registered primary snapshot is therefore **one common time for every window of every cycle, `floor_minute(T − 2 s)`**: fills strictly before it, bars completed at or before it minus one minute. Every order attributed to the window or ambiguous at the boundary has `S0 ≥ ` that snapshot, so **no state measurement lies after the earliest possible decision time**. The S1 snapshot (last completed minute before the first fill; `T` for no-action windows) is the sensitivity; a result is robust only if it holds under both.

**Action classes (point 3).** From the opening-fill counts by module (`phase0_table3_opening_modules.csv`):

| Class | Orders | Short inventory? |
|---|---|---|
| `BODY_SHORT_OPEN` | `num` sell opening a short: 4,406 fills pre-expiry, 9,173 expiry day | **yes** — the scheduled and extra additions |
| `BODY_LONG_OPEN` | `num` buy opening a long: 203 / 977 | no (separate class) |
| `WING_OPEN` | `h_` buy opening a long: 3,187 / 5,393 | no (hedge) |
| `LUMP_OPEN` | `v_` buy opening a long: 181 / 1 | no — **`v_` never opens a short**; its sizing is a hedge question |
| `STOP_MODULE_SHORT_OPEN` | `s_` sell opening a short: 10 / 107 | yes — stop-module overshoot, never a scheduled add |
| `OTHER_OPEN` | `m_`, and one `h_` sell opening | — |

A real opening order of **any** module is never `NO_ACTION`; a window containing only non-`BODY_SHORT_OPEN` openings is `ACTION_OTHER_CLASS` (none occur in the candidate windows). Scheduled-add analyses (E1–E3, E5) use `BODY_SHORT_OPEN`; the other classes are analysed under E6–E8 and the stop work. `BODY_SHORT_OPEN` fills outside every window are `OFF_WINDOW_ACTION` events (ENT-04), analysed and not dropped.

**No-action classes.** `NO_ACTION_ACTIVE` = no opening of any class attributed to the window AND any algo fill of the same underlying and cycle within ±30 min AND index bars complete for the 60 minutes before the snapshot; `NO_ACTION_UNCERTAIN` otherwise; `NOT_APPLICABLE` after a cycle-stop liquidation, before the first fill, or (expiry day) with no open short. One row per opportunity, action and no-action alike.

### B5. Entry hypotheses, tests, falsifiers and the permutation design
| # | Hypothesis | Test | Falsified if |
|---|---|---|---|
| E1 | Deterministic schedule: a body short pair is added at every registered window regardless of state | per-window action rate with Wilson interval on the 17 windows **and** the unconditional rate over the 21 candidates (87.4 %); list every `NO_ACTION_ACTIVE` window | the action rate is materially < 100 % on the registered windows, or skips associate with state beyond chance |
| E2 | State-gated addition | per-feature association with the action and the quantity outcome (25 features), cycle-block permutation | no feature survives Holm in both underlyings, or the association disappears at S0 / S1 |
| E3 | Quantity = ladder template | share equal to the slot mode; deviations vs state | the mode explains < 80 % or deviations are state-explained |
| E4 | Capital / margin gates additions | **NOT_TESTABLE**; proxy association labelled a proxy | — |
| E5 | Strike = ATM of the last completed index close | exact-match under R1 / R2 (R3 for the opening); tilt by sign test | exact match < 100 % under every reference → the rule is a fit, ceiling STRONGLY_SUPPORTED |
| E6 | Wing = highest OTM strike with premium ≤ 2.5 % of the ATM leg quote | exact-match under three premium references; budget values reported as a sensitivity set, not a search | exact match not reproduced → STRONGLY_SUPPORTED at best |
| E7 | Wing quantity tracks short quantity | wing/body unit ratio under three matching conventions | no stable mode |
| E8 | Re-entry follows closures | time-shift null | excess over chance indistinguishable from zero |

**Permutation design (point 4).** The previously described *cycle × window* strata hold **one observation each** (verified: 1.0), so labels cannot be shuffled; that design is withdrawn. Registered design:
* **Exchangeability unit:** the expiry cycle. **Primary scheme: cycle-block permutation** — the whole outcome vector of a cycle is paired with the whole state vector of another cycle of the *same underlying and day type*; windows stay aligned (time-of-day and window effects are preserved), within-cycle sequence dependence is preserved, cells missing in either cycle are dropped for that pair. Statistic: per-window association across cycles, standardised within window and summed. **Sensitivity:** within-window shuffle across cycles of the same underlying and day type (15–17 observations per stratum).
* **Not degenerate** (`phase0_table4_permutation_design.csv`):

| Design | Underlying | Cycles | Non-constant windows | Minority events | log10 distinct cycle-block permutations |
|---|---|---:|---:|---:|---:|
| E2 action, **17 registered windows** | NIFTY / SENSEX | 15 / 17 | **0 / 0** | **0 / 0** | 12.1 / 14.6 — **degenerate: every window acts** |
| E2 action, 21 candidate windows | NIFTY / SENSEX | 15 / 17 | 4 / 4 | 36 / 49 | 12.1 / 14.6 |
| E2 action, expiry-day applicable windows | NIFTY / SENSEX | 12 / 14 | 5 / 7 | 17 / 27 | 8.7 / 10.9 |
| E3 quantity, 17 registered windows | NIFTY / SENSEX | 15 / 17 | 16 / 17 | 14 / 13 distinct values | 12.1 / 14.6 |
| E3 quantity, expiry-day action windows | NIFTY / SENSEX | 12 / 14 | 23 / 23 | 30 / 22 distinct values | 8.7 / 10.9 |

* **Testability gates** (set after these counts, before any test): minority-class events ≥ 30 pooled and ≥ 10 per underlying, ≥ 10 cycles per underlying; otherwise the test is reported **NOT_TESTABLE**, not "no effect". E2 on the action outcome is therefore run on the **21 candidate windows** and the **expiry-day windows**, not on the 17 registered windows alone; quantity outcomes vary in every window and are testable throughout.

### B6. D-1 versus D0 reconciliation (accounting, no hypothesis)
Per cycle and day type: opening units, closing units, net inventory change, gross traded units, parent orders, distinct contracts, starting and ending inventory, CE / PE changes. Identity `opened − closed = Δinventory` per contract; reconciled to TP-01 (opened 1,414,545; closed 1,377,065; remaining 37,480). Gross volume is never evidence of net book-building.

## C. EXIT-trigger reconstruction

### C0. The two cycle-stop figures (point 7)
They describe different quantities and use different marks:

| Figure | Quantity | Marks | Source |
|---|---|---|---|
| **−₹1.38 to −1.43 L** | **executed** cumulative D-1 + D0 MTM at the first `s_` decision, 10 non-gap stops, SD ₹5.4–6.3 K | the algorithm's own trigger-time prices: V4 `s_` fill VWAP (−1.383); V1 recovered quotes (limit ÷ 1.15 / ÷ 0.85) of the `s_` orders, else other orders' quotes within 60 s, else previous-minute close (−1.419); V3 300 s quote window (−1.429) | `FOLLOWUP_LEDGER_AND_STOP_AUDIT.md` §4; `RISK_RULE_VALIDATION_REPORT.md` §5 |
| **−₹1.22 to −1.36 L** | **bounds on the configured constant** | lower magnitude: deepest MTM among cycles that did **not** stop (−1.218, **minute-close** marks); upper: shallowest trigger quote among the stops (−1.356, quote marks) | same reports; `non_stop_cycles_deepest_mtm.csv` |
| −₹1.30 to −1.35 L (RSK-01) | earlier lineage-Y estimate of the configured level; executed average −1.44 L (SD ₹6.8 K) | lineage-Y marks | register RSK-01; superseded for the constant by the bounds |

The executed level is deeper than the constant because of decision-to-fill latency and quote movement. The bounds constrain the constant, not the executed level, and **mix mark conventions** (minute closes understate trigger-time MTM: median −1.09 L one minute before the stops against −1.42 L at the trigger), so the interval is a coarse bracket and the constant stays **UNRESOLVED**. Phase 2 will not compare numbers across conventions.

### C1. What is already established (TP-01, TP-02, Stage 1)
| Finding | Source |
|---|---|
| 4.0 % of short closings are `s_` cycle-stop liquidations (12 cycles); 56.3 % are STOP_POSSIBLE on price / timing only | TP-02 (EXT-14) |
| Per-lot stop-like response near 1.6–1.7× the cheapest open entry on D-1 (constant and reference unresolved; 0 of 18 rules reach 80/80) | EXT-02–04, ALC-03 |
| Cycle stop on cumulative D-1 + D0 MTM: executed ≈ −₹1.38 to −1.43 L; constant bracketed by ≈ −₹1.22 to −1.36 L (C0) | RSK-01, risk-rule study |
| Closing hazard 2.70× at minute-of-hour :14 :29 :44 :59 (Holm 0.03); 09:15 cluster 82 % stop-related; late expiry-day activity | TP-02 (EXT-15) |
| 50 % of clean profitable body closings are in ≥ 2-contract batches (43 points above chance); wing closings accompany body closings (84 % vs 12 %) | TP-02 |
| No fixed premium-decay take-profit; replacement and re-adding not above chance; no cycle mark-to-market level distinguishable at minute level | TP-01, TP-02 |
| Rahul's 4 % carry stop (readings A–D) and the ₹2 L kill switch were inconsistent with behaviour; reading E not identifiable | RSK-07–09 |
| Side-level and basket reductions timed by clock / time-to-expiry; contract choice partly predictable (hit@1 0.77 vs 0.47) | MGT-05, MGT-06 |

### C2. What remains unresolved
The **decision that starts a batch**; **which contracts it selects**; whether the 15-minute concentration is a decision timer, an execution artefact or both; the expiry-day afternoon driver; how wings are released relative to bodies; whether Rahul's stop readings fail because they are wrong or because the reconstruction is limited.

### C3. Data limits that bind the exit analysis
Decision times of `num` orders unavailable (bounds); lot ownership unidentified (three conventions); no decision logs; marks are 1-minute closes of contracts Algo 8 traded; no Greeks, IV or margin; the cycle-stop constant is bracketed only coarsely (C0); stale index closing minutes on 96 sessions (DAT-15, alpha branch) excluded from market features.

### C4. Batch reconstruction
Unit = **parent order**. Primary batch = consecutive closing parent orders of one underlying with gaps ≤ 10 s; sensitivities at 2, 5, 30, 60 s and an order-number-block definition. Each batch records members, rights, strikes, short-body vs long-wing, CE / PE / mixed, profit / loss (three conventions), TP-02 stop class, expiry class, 15-minute tick, and pre-batch portfolio state at S0 and S1 (same snapshot rule as B4: never later than the earliest possible decision).

### C5. Competing exit explanations and the tests that separate them
| # | Hypothesis | Predicts | Test | Falsified if |
|---|---|---|---|---|
| X1 | Individual-position exit | closed vs retained contracts separate on a per-position criterion; first-passage ordering; sides need not be pure | rank the open contracts on the registered position metrics at each decision opportunity; AUC of closed vs retained (cycle-clustered) | no position metric separates closed from retained beyond chance (Holm) |
| X2 | Side-level exit | side-pure selection; a side-level state decides the side | side purity vs permutation among open contracts of the same size; side MTM / premium ratio | purity at chance; side state uninformative |
| X3 | Portfolio-level exit | batch timing tracks a cycle-level state crossing, in both underlyings | pre-batch portfolio metrics vs exposed non-batch minutes, max-statistic permutation | no metric distinguishable; differs between underlyings |
| X4 | Scheduled workflow with an internal condition | decisions only at ticks; selection depends on a condition | full residue test (C6); order-entry minute also concentrated; share of open contracts closed per tick; composition of selected vs retained | concentration only in fill time; or closing probability equal across contracts |
| X5 | Expiry-management process | timing depends on time to expiry and phase, selection on absolute premium / size | hazard by minutes-to-expiry and absolute premium (fixed bins, max-statistic) | state explains more than time and premium |
| X6 | Execution batching / coincidence | batches are chance co-occurrences or one execution loop with no shared property | inter-order gaps vs a Poisson null at the same time-of-day intensity; members' shared property vs random subsets; submission order inside one number block | members share a property beyond chance and gaps are shorter than the null |

Two or more may hold at different times. If the registered tests cannot separate them the verdict is **UNRESOLVED**.

### C6. 15-minute behaviour: two separate tests (point 6)
1. **Full residue test.** Statistic = maximum over **all 15 minute-of-hour residues (0–14)** of the controlled closing hazard, with the permutation corrected for the choice of residue, computed on **fill minute** and on the independent **order-entry minute**, by day type, phase, module, body vs wing, profit vs loss, and **including the pre-expiry day** (TP-02 pooled them). This is the only 15-minute inference.
2. **Observed clock-minute candidates.** The seven exact minutes found in TP-01 (09:15, 14:29, 14:44, 14:58, 14:59, 15:14, 15:19) are tested and reported **separately** as descriptive candidates; they never select the residue.
Grid labels from the register (grid A :01/:16/:31/:46, Clock B :14/:29/:44/:59) are used only for reporting. Further: fraction of open contracts closed per tick and composition of the selected set; the same tests outside expiry-day sessions. The pattern is **not** called a timer unless 1 and (order-entry minute, per-tick composition, non-expiry sessions) agree.

### C7. Expiry-day exits
Separate analyses for 09:15, 14:29–14:59, 15:14, 15:19 and other expiry-day closings: hazard against minutes to expiry, absolute premium, position-level loss and cycle mark-to-market; inventory reduction per tick; salvage thresholds (≤ ₹1, ≤ 5 % of entry) remain **labels**, not rules.

### C8. Wing release
Order of wing and body closing orders (inside one number block where comparable), time offset distribution, wing units against body units closed and against remaining body units, CE / PE coupling, wings retained after body closure; ownership alternatives (nearest-time same-right, proportional, FIFO); conclusions that change with the matching are reported as sensitive.

### C9. Rahul's stated rules (client-provided hypotheses, retested unchanged)
Readings A–E of the 4 % carry stop and the ₹2,00,000 expiry-day kill switch exactly as defined in the risk-rule study (no constant tuned), recomputed with fills-based state at **S0 and S1**; threshold timestamps compared with actual liquidation orders (5-minute window; GT1 / GT2). A failure is classified *rule fails* only when the discrepancy exceeds what price, ownership and decision-time uncertainty can explain, otherwise `UNRESOLVED`.

### C10. Decision-time handling (both programs)
Tagged orders: validated tag time. Body orders: **S0** order-entry minute start, **S1** first fill. State at S0 uses fills strictly before S0 and bars completed at or before minute(S0) − 1; S1 likewise. A conclusion is robust only if it holds at both; otherwise `WEAKLY_SUPPORTED` or `UNRESOLVED`. No post-decision price enters any predictor.

## D. Statistical plan (point 7)
* Independence unit: expiry cycle; fills, orders and minutes within a cycle are never independent. Permutation schemes as in B5 (entry) and cycle × day-type × hour strata with more than one exposed minute (exit). Bootstrap over whole cycles, **2,000** resamples.
* **Permutations.** Exploratory development runs may use 500 and are never reported as inference. **Final inference uses 10,000 permutations with a Besag–Clifford sequential rule**: draw until 100 exceedances or 10,000 draws, p = (exceedances + 1)/(draws + 1); a test ending the 10,000 draws with ≤ 10 exceedances is extended to 100,000 draws under the same rule, decided by the exceedance count only and before any significance claim.
* **Why 500 is not enough.** Family sizes (upper bounds): entry **120** (E1 1 + E2 25 features × {action, quantity} × {pre-expiry, expiry day} = 100 + E3 3 + E5 6 + E6 6 + E7 3 + E8 1) → smallest Holm threshold 0.05/120 = **0.000417**; exit **60** → **0.000833**. With 500 permutations the smallest attainable p is 1/501 = **0.0020**, above both, so no test could ever survive Holm. With 10,000 it is **0.0001**, within half of the smallest entry threshold (0.00021), which is the registered resolution requirement.
* NIFTY and SENSEX are reported separately before pooling; every result also by expiry cycle.
* Fixed candidate lists only; no threshold sweep. A numeric level may appear only as the output of a registered max-statistic, never as a tuned parameter.
* Sensitivities: decision-time bound (S0 / S1), boundary-ambiguous orders included / excluded, matching convention (FIFO / LIFO / AVG), batch gap (2–60 s and block), premium reference (three), tie ordering.
* Negative results are reported in full; hazard ratios, AUCs and match rates are descriptive; **no association becomes a rule without the evidence required by §A for a confirmed trigger**.

## E. Known confounders
Time of day and expiry proximity; opening position size; strike-universe selection by the algorithm's own trading; the clock grid itself (the schedule creates the residues); module heterogeneity; stop-module overshoot near stops; ownership ambiguity; 1-minute marks and carried prices; cycles without a pre-expiry session or without an expiry-day session; one pre-expiry session per cycle (no within-cycle replication); **selection of the 17 windows by their own recurrence** (point 1).

## F. Acceptance criteria (mapping to the 15 required checks)
| # | Criterion | Evidence that it is met |
|---|---|---|
| 1–2 | Entry opportunities and actions reconstructed; skipped windows separated from missing data | window dataset with the four classes and reasons; the 85 + 40 `NO_ACTION_ACTIVE` windows listed individually |
| 3–4 | Quantity and strike selection examined inside the available universe | E3, E5 tables with alternative-availability flags |
| 5 | Hedge creation and release analysed | E6, E7, C8 |
| 6 | D-1 / D0 gross separated from net | B6 table with identity checks |
| 7 | Batches without double counting | parent-order unit; gap and block sensitivities |
| 8–9 | Pre-event state; individual vs side vs portfolio compared | X1–X6 with Holm |
| 10 | 15-minute pattern tested without assuming a timer | C6 |
| 11–12 | Expiry-day exits; stop rules checked | C7, C9 |
| 13 | Decision-time uncertainty explicit | S0 / S1 and boundary-class sensitivities |
| 14 | Reproducible | `run_tp03.py`, two identical full runs, tests |
| 15 | Unknowns and missing data documented | per-component table with `NOT_TESTABLE` / `UNRESOLVED` and the missing evidence named |

## G. How "what fraction of the architecture is mapped" will be defined
Two denominators, both reported: (a) the **14 decision components** of the final table, counted by evidence class and **claim type** (a component whose only support is an attribution or observation is not counted as a recovered trigger); (b) **event coverage**: share of the 39,874 parent orders (and gross units) that a recovered CONFIRMED or STRONGLY_SUPPORTED rule assigns to a component, with its reproduction rate. A figure is reported only with numerator, denominator and rule; it is not a readiness score.

## H. Deliverables and order of work
Phase 0 (this document, `config.yaml` v2, the structural-count script and tables) → **review** → Phase 1 entry (`TP03_ENTRY_REPORT.md`) → **stop for approval** → Phase 2 exit (`TP03_EXIT_REPORT.md`) → **stop for approval** → Phase 3 join (`TP03_REPORT.md`, `ALGO8_DECISION_FLOW.md`, final table). No alpha discovery, supervised learning or model training at any stage.

## I. Expected blockers (stated in advance)
1. E2 on the action outcome cannot run on the 17 registered windows (degenerate by construction); it rests on the 21 candidate windows (85 genuine no-action) and the expiry-day windows (40 genuine no-action, minorities of 17 and 27 per underlying) and may stay UNRESOLVED.
2. Strike and wing alternatives are only partly observable, so E5 / E6 cannot reach CONFIRMED (an in-sample fit); STRONGLY_SUPPORTED at best.
3. Without decision logs or body-order decision times, X1–X6 may remain partly UNRESOLVED; the report will name the missing evidence for each.
