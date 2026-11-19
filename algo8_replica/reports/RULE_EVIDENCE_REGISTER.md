# Rule evidence register (generated from `config/rule_evidence.yaml`)

Register sha256 `bd2179d66a0074ac252c816f9a259cc99ea305c9ba6939ab0800586cdebabee1` · base commit `9e64fbadccce8a09e102e539572b74ae71935380` · 42 rules. **Classifications come from earlier evidence only and are never upgraded because a rule performs well in a backtest.**

| Class | Rules |
|---|---:|
| CONFIRMED_OBSERVATION | 10 |
| STRONGLY_SUPPORTED | 8 |
| HYPOTHESIS | 9 |
| UNKNOWN | 12 |
| REJECTED | 3 |

May run historically: {'True': 16, 'conditional': 15, 'False': 11}

## A_cycle_market_structure

| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |
|---|---|---|---|---|---|---|
| A-01 | A cycle is one weekly expiry of one underlying: session D-1 (last session before expiry) plus D0 (expiry day); NIFTY and SENSEX are separate cycles. | **CONFIRMED_OBSERVATION** | OBSERVED_CONSTANT | True | STR-01; tp_reconstruction TP-01; lot_lifecycle cycles.csv | Live ledger: 35 cycles, 3 D0-only (no D-1 log), 2 without D0 log. History: only D-1 and D0 sessions exist in the dataset. |
| A-02 | Actual historical expiry calendar (weekday changes, holidays, special sessions) taken from an independent calendar, never from the future. | **CONFIRMED_OBSERVATION** | OBSERVED_CONSTANT | True | data_validation/validation/calendar_evidence.py; reports/tables/*_expiry_coverage.csv | Independent of the dataset manifest but built from public exchange-rule reports + Yahoo trading days; special-session dates 2023-2025 not independently verifiable (data_validation report A). Muhurat sessions mis-taken as D-1 for two expiries (defect D04). |
| A-03 | Session calendar: regular sessions 09:15-15:29 bars; special sessions (Muhurat, outages) flagged and excluded or repaired. | **CONFIRMED_OBSERVATION** | OBSERVED_CONSTANT | True | data_validation defects D04, D05, D21 | NIFTY spot after 15:14 invalid on sessions after 2026-08-03 (D05); four intraday outage sessions must be masked (D21). |
| A-04 | Index-to-option contract mapping: weekly options on the same underlying and expiry; CE/PE; strike grid 50 (NIFTY) / 100 (SENSEX). | **CONFIRMED_OBSERVATION** | OBSERVED_CONSTANT | True | STR-01; DAT-01; STK-01 | Historical strike spacing assumed constant over 2023-2026; not independently verified per session. |
| A-05 | Contract lot size per session. Live (2026): 65 NIFTY / 20 SENSEX. Historical: inferred per session as the gcd of option volumes (NIFTY 50/25/75/65; SENSEX 10/20). | **STRONGLY_SUPPORTED** | OBSERVED_CONSTANT | conditional | SIZ-01 (live); backtest/bt/cycles.py (inferred history) | Historical lot size is inferred, not supplied (data_validation D-readiness 'lot-size history not supplied'). Sizing variable is LOTS, not units (decision to be confirmed before freeze). |
| A-06 | Option universe available to the simulator: ATM +-45 strikes around the D-2 close; a contract outside it, or without a bar, yields NO_MARKET (never a fabricated fill). | **CONFIRMED_OBSERVATION** | ACCOUNTING | True | data_validation D_RESEARCH_READINESS_REPORT; defects D08/D09 | Far strikes without rows cannot be classed as unlisted or failed; 20 SENSEX contract-days of the earlier exact-trade data lie outside the window. |

## B_entry_modules

| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |
|---|---|---|---|---|---|---|
| B-01 | Initial opening around 09:16 of D-1: CE and PE shorts within ~1 s, 3 base units per role. | **STRONGLY_SUPPORTED** | BAND | conditional | ENT-01; SIZ-02; lot_lifecycle reports | Observed Jun-Oct 2026 only. Whether the same opening applied in 2023-2025 is UNKNOWN (backtest report: 'extrapolation to 2023-2025'). |
| B-02 | Opening strike K = step*floor(S/step+0.5), S = completed 09:15 index close (previous completed minute). | **STRONGLY_SUPPORTED** | OBSERVED_CONSTANT | conditional | STK-01; TP-03 E5 (31/32 first orders; 88.4 % of 190 initial orders, NIFTY 98.9 %, SENSEX 79.2 %, misses <= 2 steps) | SENSEX opening strike matches only 79 %. |
| B-03 | 17 pre-expiry (D-1) scheduled windows 09:30..14:30; each window creates a fresh same-strike CE+PE body short pair (window start T-2 s, end T+3 min). | **CONFIRMED_OBSERVATION** | BAND | conditional | ENT-02; TP-03 E1 (544/544 windows act; 587/672 over all 21 candidate windows; control windows 12:15, 12:45, 13:00 act 19-22 %, 13:15 75 %) | Window set was chosen from this data (selection-conditioned). 'Timer is the trigger' is only WEAKLY_SUPPORTED. Why 12:15/12:45/13:00 are skipped is unexplained. Not every scheduled window must be assumed to act in history. |
| B-04 | Expiry-day (D0) entries at the quarter-hour windows while the book is active (book holds any short). | **STRONGLY_SUPPORTED** | BAND | conditional | ENT-03; TP-03 (510/543 = 94 % of applicable windows) | Quantity and strike rules on D0 less certain; D0 sale trigger unidentified (see B-07). |
| B-05 | Scheduled-window strike: near the previous-minute ATM (offset 0 default). | **HYPOTHESIS** | BAND | conditional | STK-02; TP-03 E5 (63.0 % exact, 93.2 % within one step; chance 23.6 %) | Residual (off-grid) tilt unresolved (STK-03/STK-04: CE ~0.55-0.58 delta, one strike toward the move). Greeks need reliable IV, which is unavailable; delta-placement stays USER_RULE_ONLY. |
| B-06 | Quantity per scheduled window: modal ladder per slot. Lineage Y and X templates disagree (2-3 vs 4 at 10:15/10:16). | **HYPOTHESIS** | BAND | conditional | SIZ-03; REC-04; TP-03 E3 (window mode explains only 64.5 % of pre-expiry and 40 % of D0 quantities; deterministic ladder FALSIFIED) | What moves quantity off the mode is unknown. Template tendency is WEAKLY_SUPPORTED, template as a rule is falsified. |
| B-07 | Additional (off-schedule) entries. Trigger not recovered (a fitted classifier reaches AUC 0.887 but is NOT a recovered rule). | **UNKNOWN** | DISABLED_BY_DEFAULT | False | ENT-04; TP-03 E2 (no feature survives Holm; 13 nominal p<0.05 of 96 vs ~4.8 expected) | TEACHER_FORCED is for live-ledger behavioural validation only. No fitted ML substitution. D-1 off-schedule sales were worth ~Rs469/lot vs Rs323 scheduled (replication report): excluding them is a known economic gap. |
| B-08 | Entry order pricing: marketable limit = LTP x 1.15 (buy) / x 0.85 (sell); lump buy ~x 1.03; Rs 0.05 tick; body DAY, wings/lump/stop IOC. | **CONFIRMED_OBSERVATION** | OBSERVED_CONSTANT | True | DAT-05; DAT-06 | Band observed in 2026 orders only; a 1-minute bar says nothing about queue position or depth. |
| B-09 | Entry eligibility / no-trade filter. | **UNKNOWN** | DISABLED_BY_DEFAULT | True | ENT-05; skeleton UNRESOLVED list | No eligibility data. Margin / capital gate NOT TESTABLE (TP-03 E4). |

## C_position_management

| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |
|---|---|---|---|---|---|---|
| C-01 | Old exposure is retained across windows (D-1 accumulates; no re-centring of earlier shorts). | **CONFIRMED_OBSERVATION** | OBSERVED_CONSTANT | True | MGT-01 | Observed in 35 cycles only. |
| C-02 | Short-lot lifecycle: whole-lot unit lots; each closing fill is allocated to open lots under an ownership convention. Ownership is NOT identifiable from the ledger. | **UNKNOWN** | BAND | True | lot_lifecycle LOT_IDENTITY_METHODOLOGY / EXECUTIVE_SUMMARY (89 % of body shorts ambiguous in 30 complete cycles; carried/D0 P&L split moves Rs 4.9 L across conventions) | Each convention is a SCENARIO, never selected by profit. D1 (body buy with no recorded short) unresolved: both readings implemented upstream. |
| C-03 | Partial buy-backs: buy-back orders close 1-42 lots (median 1); lot-level assignment ambiguous. | **CONFIRMED_OBSERVATION** | TEACHER_FORCED_ONLY | False | lot_lifecycle CARRIED_LOT_BUYBACK_ANALYSIS | Contract-level exact; the TRIGGER of buy-backs is not recovered (no hypothesis exceeds 7.5 % precision). |
| C-04 | Per-lot stop: buy back one lot when LTP >= k x reference. Reference candidates: own entry; cheapest open entry. Entries <= Rs 4 exempt in the earlier model. | **HYPOTHESIS** | BAND | conditional | EXT-02..EXT-04; ALC-02..ALC-04; replication/rules.py R-LEGSTOP; ~95 % of stop buy-backs at >= 1.5x lowest entry | Exact rule UNKNOWN (0 of 18 candidate rules at 80/80 precision/recall). D0 scope is weaker (EXT-05). Stop executes on OHLC crossing under a conservative intrabar policy, never at the bar high. |
| C-05 | Carried-lot management: deep-OTM carried lots are held to settlement (76 % beyond 6 strike steps vs <=1 % within 3 steps); no recovered buy-back trigger. | **STRONGLY_SUPPORTED** | BAND | conditional | lot_lifecycle CARRIED_LOT_BUYBACK_ANALYSIS; VALIDATION_AND_LIMITATIONS | The OBSERVATION (held) is supported; the DECISION RULE is unknown. FIFO-set statistic; ~same under other conventions. |
| C-06 | Side/basket reductions: contract choice 'largest exposure' hit@1 0.77/0.58, fraction median 11-20 %; trigger unknown. | **UNKNOWN** | DISABLED_BY_DEFAULT | False | MGT-05; MGT-06; EXT-10 | Choice rule usable only if a trigger exists. |
| C-07 | Clock-B: D0 tick times :14/:29/:44/:59 from 09:29; one lot per acting tick per contract; re-sale at ATM ~28 s later. Act/no-act and contract choice unknown. | **HYPOTHESIS** | DISABLED_BY_DEFAULT | False | MGT-02..MGT-04; STK-05; ALC-08; TP-02 (15-min block end has 2.7x the closing hazard, Holm p=0.030) | Tick TIMES are observed; the DECISION is not. Same-contract replacement REJECTED as general rule (C-09). |
| C-08 | Expiry settlement of residual lots at the settlement value (see C-10 for the proxy treatment). | **CONFIRMED_OBSERVATION** | ACCOUNTING | True | bt/account.py; lot_lifecycle PNL_RECONCILIATION | No exchange settlement price in the data: every settled P&L is proxy-based. The Yahoo official close differs from the 15:29 spot bar by up to 89 points in 13 early live cycles. |
| C-09 | Replacement after a buy-back (same-contract / same-right / cross-right). Same-contract replacement as a general rule REJECTED; cross-right sale ~2.8x chance at 0-30 s is an exploratory hypothesis only. | **REJECTED** | DISABLED_BY_DEFAULT | False | lot_lifecycle REPLACEMENT_ANALYSIS (v2: same-right <=60 s ratio 1.25, CI 0.91-1.56; 0 strongly supported at primary thresholds) | REJECTED covers 'replacement as a general rule' and '60 % of D0 sales are replacements'. The cross-right pattern is a separate HYPOTHESIS and must be tested on new data. |
| C-10 | Final liquidation: flatten the short book at 15:14 in the later live period (after 3 Aug 2026); earlier-period rule unknown. | **HYPOTHESIS** | BAND | conditional | EXT-08 | Cut-over date and pre-cut-over rule UNKNOWN. Cutover must be explicit in every config. |
| C-11 | Decay take-profit (price <= 0.5x entry) as a general trigger. | **REJECTED** | DISABLED_BY_DEFAULT | False | lot_lifecycle CARRIED_LOT_BUYBACK_ANALYSIS H2 (lift 0.87 / 0.69) | Must not be enabled as a default. |
| C-12 | Salvage: buy back every option <= Rs 1 (or <= 5 % of entry). | **REJECTED** | DISABLED_BY_DEFAULT | False | lot_lifecycle H6 (lift 0.11 / 0.04: near-worthless contracts are HELD); EXT-07 labelling thresholds | Rejected as a trigger; some expiry-day wing sales at <= Rs 1 exist as labels, not recovered instructions. |

## D_hedge_modules

| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |
|---|---|---|---|---|---|---|
| D-01 | Seed wings before/with the opening shorts: NIFTY K +-2,000; SENSEX K +-4,000 before 2026-09-16, +-2,000 from 2026-09-16. | **STRONGLY_SUPPORTED** | BAND | conditional | HDG-01 | Historically the wing often did not trade at 09:16-09:20 (substituted toward ATM in 54 % NIFTY / 31 % SENSEX cycles in the BT). A substituted wing must be labelled, not silently accepted. |
| D-02 | Routine wing with each addition: highest OTM premium <= 2.5 % of the ATM leg premium, per right. | **HYPOTHESIS** | BAND | conditional | HDG-02; HDG-03 (strike match only ~50 % exact) | Budget supported; strike choice only ~50 % exact. |
| D-03 | Overnight lump (v_) hedge: late D-1, heavier short side, 0.9-2.3 % OTM; size not predictable. | **UNKNOWN** | DISABLED_BY_DEFAULT | False | SIZ-04; HDG | Timing/strike band only; size is a placeholder. |
| D-04 | Wing release: wings are sold with short buy-backs (same side, within 60 s; 84 % of short closings have a same-right wing closing within +-10 s). | **STRONGLY_SUPPORTED** | BAND | conditional | HDG-06; TP-02 | Association, not a recovered ratio. Release ratio unknown. |
| D-05 | Wing coupling to replacement (sale) orders. Ledger gives a wing for ~41 % of replacement-labelled sales. | **UNKNOWN** | BAND | True | lot_lifecycle SIMULATOR_DEFECT_REMEDIATION defect B | Two bounds only; neither is a recovered rule. |
| D-06 | Expiry hedge replacement inward (81.5 %) and hedge sizing beyond the budget. | **UNKNOWN** | DISABLED_BY_DEFAULT | False | HDG-04 | Association only. |
| D-07 | Carry book is long >= short per right (assertion check, not an action). | **STRONGLY_SUPPORTED** | ACCOUNTING | True | HDG-05 | Constraint check on the live book. |

## E_risk_modules

| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |
|---|---|---|---|---|---|---|
| E-01 | Cycle-level MTM stop on cumulative LTP MTM (body + hedges, D-1 + D0): approx -Rs 1.30 to -1.35 L configured (the stop sits near -1.44 L). | **HYPOTHESIS** | BAND | conditional | RSK-01; backtest capital_stop plugin; d0_sim_v2 | Threshold was read from live (Rs 2 Cr) book size; scaling to historical sizing is an assumption. Passive-lot behaviour at a stop is an ASSUMPTION with two bounds (sign of later-block D0 P&L depends on it). The stop does not execute at the threshold. |
| E-02 | No new entries after the s_ cycle stop. | **HYPOTHESIS** | BAND | conditional | RSK-01; ALC-09 (post-stop short fills occur in 7/12 stop cycles) | Contradicted in 7 of 12 live stop cycles; not simulated beyond the stop. |
| E-03 | Stop polling latency and post-stop order behaviour. | **UNKNOWN** | BAND | True | lot_lifecycle D0 simulator v2; d0_reconstruction | Second-level latency not observable. |
| E-04 | '4 % carry SL' (Info.txt) and '1 % of capital on expiry day': stated, not reproduced. | **UNKNOWN** | USER_RULE_ONLY | False | RSK-02; RSK-03; Info.txt | Six interpretations exist upstream; each must carry a user-rule label. |
| E-05 | Margin and capital constraint: Rs 2 Cr capital stated; margin modelled only as worst-case expiry loss proxy, not SPAN. | **UNKNOWN** | ACCOUNTING | True | bt METHODOLOGY section 5; TP-03 E4 NOT_TESTABLE | Capital figure unverified; real broker margin unknown. |

## X_accounting_execution

| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |
|---|---|---|---|---|---|---|
| X-01 | Cost model: brokerage, STT, exchange charge, SEBI, GST, stamp, slippage, spread. | **UNKNOWN** | ACCOUNTING | True | bt/account.py; Part K of the brief | Export has no charges. All historical cost rates except STT 2026 were quoted from memory in the earlier BT and are unverified. |
| X-02 | Execution models: decision-minute open, next-minute open, adverse bar, configurable delay, NO_MARKET when the bar is absent. | **HYPOTHESIS** | BAND | True | skeleton spec section 4; analysis/engine.py | 97.3 % of live fills lie inside their own-minute bar. No bid/ask, depth, queue or impact data. |
| X-03 | Benchmark Sharpe 2.19 (3 Mar 2025 - 27 May 2026, 47.22 %, CAGR 36.88 %): methodology UNKNOWN; comparison label NOT COMPARABLE unless identical methodology is established. | **UNKNOWN** | ACCOUNTING | False | ORIGINAL_SHARPE_BENCHMARK.md; BENCHMARK_METHODOLOGY_STATUS.md | Screenshot not in the repository; return frequency, annualisation, capital, risk-free, costs, instruments unknown. |

