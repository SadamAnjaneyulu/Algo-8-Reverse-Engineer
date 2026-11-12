# Algo 8 skeleton and take-profit research: Stage 1 implementation specification

Branch `research/algo8-skeleton-tp`, stacked on `docs/algo8-complete-research-report` (PR #7). It contains PRs #3–#7.
**Stage 1 only.** There is no strategy code yet. Stage 2 starts only after this specification is approved.

| Document | Content |
|---|---|
| This file | Evidence audit, rule inventory, architecture, module specification, simulation semantics, validation plan |
| [`DATA_MAP.md`](DATA_MAP.md) | Authoritative data, keys, caches, existing reconstruction code |
| [`TP_RESEARCH_METHODOLOGY.md`](TP_RESEARCH_METHODOLOGY.md) | Take-profit research design, null models, pre-registered grid |
| [`UNRESOLVED_RULES_AND_QUESTIONS.md`](UNRESOLVED_RULES_AND_QUESTIONS.md) | Unresolved rules, placeholders, decisions needed |
| [`stage1_audit.py`](stage1_audit.py) → [`results/`](results/) | Executed descriptive counts quoted here (no thresholds fitted) |

Nothing existing is modified: `alpha_freeze/`, the stop models, PR #1–#7 results, the raw export and the caches in
`analysis/_cache/` are read only. New derived data will go to `algo8_skeleton/_cache/` (git-ignored).

---

## 1. Evidence sources audited

| Source | Branch / PR | Used for | Status of the source |
|---|---|---|---|
| `Trades_GKOHNP140.csv` | `main` | Every fill; 39,874 orders (column-163 key), 41,421 fills, 35 cycles | Authoritative; fills only |
| `Info.txt` | `main` | "BTST; 4 % carry SL; 1 % of capital on expiry day; ₹2 Cr" | Supplied statement; 4 % and 1 % not reproduced (RSK-02, RSK-03) |
| Breeze 1-minute bars | `research/ml-decision-engine` (`data/breeze/normalized`), cached in `analysis/_cache` | Index and option OHLCV | Authoritative market data; option universe = contracts Algo 8 traded |
| `audit/ALGO8_MASTER_FINDINGS_REGISTER.md`, `audit/ALGO8_STRATEGY_SPECIFICATION.md` | PR #4 | Rule IDs (DAT/STR/ENT/STK/SIZ/HDG/MGT/EXT/RSK/ML/REC/ALC) and status tags | Consolidated, reconciled register (both lineages) |
| `analysis/exit_engine/` | PR #3 | Clean order table, lot ledgers (cheap/FIFO/LIFO), taxonomy, first-passage, replay | Clean build on column 163 |
| `analysis/allocation/` | PR #5 | Slot/chain allocation ledgers, stop-reference study, replacement links | Allocation ids are hypotheses (ALC-01) |
| `ohlcv_research/` | PR #6 | Causal OHLCV features with leakage tests | Phase 0–1 complete; Phase 2 not run |
| `analysis/engine.py`, `clone_validate.py` | lineage Y base | Existing minute-bar clone (30 cycles) | Approximate clone; poor cycle P&L match (see `analysis/_cache/clone_validation.pkl`) |
| `ALGO8_RULEBOOK.md` (lineage X) | `data/local-breeze-fetch` | Cross-check: X2–X5 state early exits, profit-taking and trailing are **unresolved** | Folded into the register (REC rows) |
| `FINDINGS.md` | lineage Y base | Older findings; L258 ("every D-1 exit is a loser") and L276 ("D0 profit-target fraction: no cluster") predate the column-163 ledger | Re-checked on the clean ledger in Stage 3 (see the TP methodology) |

---

## 2. Rule inventory by evidence class

The confidence labels are the register's. **Implementation mode** says how Stage 2 will encode each rule:
`fixed` = a constant from the evidence; `band` = configurable inside the evidenced range, every value reported
separately; `placeholder` = no rule identified, so the run refuses to start until the user sets a mode (§5).

### 2.1 Confirmed observations

| Rule | Evidence | Mode |
|---|---|---|
| Cycle = D-1 (pre-expiry) + D0 (expiry) per underlying weekly expiry; NIFTY and SENSEX | STR-01 | fixed |
| One order = one column-163 tag; module from the tag prefix: body (numeric), `h_` wing, `v_` lump, `s_` stop, `m_` manual | DAT-01, DAT-06 | fixed |
| Child order = one base unit: 65 NIFTY / 20 SENSEX | SIZ-01 | fixed |
| Marketable limit = LTP × 1.15 (buy) / × 0.85 (sell); `v_` buy ≈ × 1.03; ₹0.05 tick; body DAY, wings / lump / stop IOC | DAT-05, DAT-06 | fixed |
| 17 pre-expiry windows (09:30 … 14:30, start T−2 s, end T+3 min) with fresh same-strike CE/PE shorts, 544/544 | ENT-02 | fixed |
| Old exposure is retained across windows (D-1 accumulates; no re-centring) | MGT-01 | fixed |
| Unit-lot book reconciles exactly to fills; lot MTM = fills-plus-candles MTM | DAT-08 | fixed (accounting) |

### 2.2 Strong evidence (precise original rule not fully identified)

| Rule | Value used | Evidence | Mode |
|---|---|---|---|
| Opening at 09:16, CE and PE shorts within 1 s | 09:16 | ENT-01 | fixed |
| Opening strike `K = d·floor(S/d + 0.5)`, S = completed 09:15 index close; d = 50 / 100 | as stated | STK-01 | fixed |
| Seed wings before / with the opening shorts | NIFTY K ± 2,000; SENSEX K ± 4,000 before 16 Sep 2026, ± 2,000 from 16 Sep | HDG-01 | fixed (date switch explicit) |
| Opening size | 3 base units per role | SIZ-02 | fixed |
| Ladder sizes per slot | modal; lineage Y and X disagree at 10:15/10:16 (2–3 vs 4) | SIZ-03, REC-04 | band (both ladders) |
| Routine wing with each addition | highest OTM premium ≤ 2.5 % of the ATM leg premium, per right | HDG-02, HDG-03 | fixed (budget); strike match only ≈ 50 % exact |
| Expiry-day entries at the quarter windows while the book is active | active = book holds any short | ENT-03 | fixed |
| Carry book long ≥ short per right | constraint check | HDG-05 | fixed (assertion) |
| Per-lot stop: one lot per decision; D-1 level band 1.6–1.7 × cheapest open entry; ≈ 95 % of stop buy-backs at ≥ 1.5× lowest entry | band | EXT-02–EXT-04, ALC-02–ALC-04 | band; exact rule **[U]** (0 of 18 rules at 80/80) |
| Cycle stop on cumulative LTP MTM (body + hedges, D-1 + D0) | ≈ −₹1.30 to −1.35 L configured | RSK-01 | band |
| No new entries after the `s_` cycle stop | — | RSK-01; spec §F | fixed (but see ALC-09: post-stop short fills in 7/12 stop cycles) |
| Final flatten of the short book at 15:14 in the later period (after 3 Aug) | 15:14 | EXT-08 | band (cut-over date and earlier-period rule **[U]**) |
| Clock-B tick times on D0 | :14 / :29 / :44 / :59 from 09:29 | MGT-02 | fixed (times) |
| Clock-B quantity and replacement | one lot per acting tick per contract; re-sale at ATM ≈ 28 s later | MGT-04, STK-05, ALC-08 | fixed (quantity); act/no-act and contract **[U]** |
| No classical indicator used | — | STR-03 | fixed (no indicator inputs) |

### 2.3 Partial reconstruction

| Rule | What is known | Evidence | Mode |
|---|---|---|---|
| Later scheduled strikes | near the moving ATM: within one strike 95–97 %, exact ≈ 70 % | STK-02 | band (offset 0 / user rule) |
| Off-grid strike tilt | CE ≈ 0.55–0.58 Δ, one strike toward the move | STK-03, STK-04 | placeholder |
| Clock-B contract choice | "most lots" hit 0.66 vs random 0.41 | MGT-04 | band (rule = most lots; reported as approximate) |
| Side / basket contract choice and fraction | largest exposure hit@1 0.77 / 0.58; fraction median 11–20 % | MGT-06 | placeholder (choice rule usable only if a trigger exists) |
| Re-entry after buy-backs | same-side sale ≤ 60 s after 54.6 % of unscheduled episodes; association only | MGT-07, ALC-08 | placeholder |
| Expiry-day salvage | shorts ≤ ₹1 or ≤ 5 % of entry bought back; wings sold ≤ ₹1 | EXT-07 | band (these are labelling thresholds, not recovered instructions) |
| Expiry hedge replacement inward | 81.5 % | HDG-04 | placeholder |
| Wing release with short buy-backs | same side, within 60 s | HDG-06 | placeholder (ratio unknown) |
| Overnight lump `v_` | late D-1, heavier short side, 0.9–2.3 % OTM; size not predictable | SIZ-04 | timing band; **size placeholder** |
| D0 per-lot stop | weak, scope-dependent | EXT-05 | band, lower confidence |

### 2.4 Unresolved rules (no rule identified in the available data)

Extra (off-schedule) sale trigger (ENT-04) · ladder quantity beyond the modal template (SIZ-03) · side-level and basket
reduction triggers (MGT-05) · same-contract partial buy-back trigger · Clock-B act / no-act (MGT-03) · re-entry trigger ·
replacement strike and quantity (ALC-08) · allocation ownership (ALC-01, ALC-07) · lump size (SIZ-04) · capital / margin
sizing (SIZ-05) · eligibility / no-trade filter (ENT-05) · "4 % carry SL" (RSK-02) · "1 % on expiry day" (RSK-03) ·
exact per-lot stop reference and constant (ALC-03) · profit target / trailing stop (EXT-06: none found so far; the
subject of Stage 3) · post-cycle-stop fills (ALC-09) · within-poll module order (spec §D, [H]).

---

## 3. Architecture

```text
algo8_skeleton/
  config/        rules.yaml (every parameter: value, evidence ID, confidence, mode); costs.yaml; fills.yaml
  core/          calendar.py (cycles, sessions, splits) · market.py (minute bars, causal views) · book.py (unit lots, allocations,
                 ownership conventions) · orders.py (OrderIntent, limit band, child splitting) · fills.py (fill models) ·
                 costs.py · ledger.py (event log) · rulemeta.py (evidence / confidence / mode registry, refuse-to-run check)
  modules/       opening.py · ladder.py · strikes.py · wings.py · lump.py · lot_stop.py · side_basket.py · cycle_stop.py ·
                 clock_b.py · salvage.py · final_flatten.py · extra_sales.py · reentry.py   (one rule family per file)
  sim/           engine.py (minute loop, module order, state transitions) · teacher.py (inject actual orders per module)
  validate/      match_entries.py · match_strikes.py · match_qty.py · match_hedges.py · match_exits.py · match_inventory.py · pnl.py
  tp/            Stage 3 take-profit research (separate from the simulator)
  tests/         unit tests per module + accounting reconciliation + leakage tests
```

* **Reuse, do not modify:** `analysis/load.py` (raw parsing), `analysis/exit_engine/common.py` (order table, market matrices,
  splits), the PR #3 lot ledgers and the PR #5 allocation ledgers are read through thin adapters. `analysis/engine.py` is
  **not** extended; its design (decision at the start of minute *m* from bars completed before *m*) is kept.
* **Module interface:** `on_minute(state, view) -> list[OrderIntent]`. `view` exposes only bars completed before the
  decision minute (asserted by tests). Every intent carries `module`, `rule_id`, `evidence`, `confidence`.
* **State:** unit lots (contract, side, entry time, entry price, module, allocation id under each hypothesis), cycle MTM,
  flags (active book, cycle stopped, flattened).
* **Module order inside a minute:** cycle stop → per-lot stop → clock events (ladder, Clock B) → extra sales / reductions →
  salvage → final flatten. This order is **[H]** (spec §D) and will be configurable and reported.

## 4. Simulation semantics

| Item | Specification |
|---|---|
| Time step | 1 minute, IST, bars labelled by start (confirmed: 97.3 % of fills inside their own-minute bar) |
| Decision information | bars completed before the decision minute; index close of *m*−1 for strike selection |
| Sub-minute events | not representable; tagged orders' second-level times are used only in validation |
| Fill models (each reported separately) | `open` (decision-minute open) · `delay1` (next-minute open) · `adverse` (buy at minute high, sell at minute low), as in PR #3 |
| Limit band | fills outside LTP × 1.15 / × 0.85 of the decision quote are rejected and logged |
| Stops on minute data | triggered by minute high (short) vs threshold; fill per fill model; intrabar order of stop vs other events is **never assumed**: ambiguous minutes are flagged |
| Missing option bar | no fill; intent logged as `no_market` (option universe = contracts Algo 8 traded) |
| Expiry settlement | lots open after the last bar settle at intrinsic value from the last index close (official settlement price not in the data; flagged) |
| Costs | applied per order from `costs.yaml`; **values not set** (the export has no charges; see the questions) |

## 5. Placeholders (no silent substitution)

Every `placeholder` rule must be given one of these modes in `rules.yaml`. The engine refuses to run if any is unset:

| Mode | Meaning | Allowed use |
|---|---|---|
| `disabled` | the module never acts | baseline skeleton |
| `teacher_forced` | that module's actual historical orders are injected at their decision times | validation only, to isolate other modules; labelled in every output |
| `user_rule` | an explicit rule supplied by the user, with its own label | experiments; never reported as recovered |

Band parameters run over their evidenced values separately. No value is chosen on TEST.

## 6. Validation plan (Stage 4): separate metrics, no combined score

| Dimension | Unit | Match definition | Metrics |
|---|---|---|---|
| Entry | short-sale event (contract-side-minute) | same underlying, right, side, minute ± tolerance | precision, recall per module (opening, ladder, D0 ladder, extra) |
| Strike | matched entry | exact strike; within ± 1 step | exact rate, ± 1 rate, signed step error distribution |
| Quantity | matched slot | lots per leg per slot | exact rate, mean absolute lot error |
| Hedge | wing / lump buy | strike exact / ± 1 step, minute ± tolerance, quantity | precision, recall, strike error |
| Exit | buy-back event | same contract, minute ± 2 (as PR #3) | precision, recall, quantity agreement, per exit category |
| Inventory | contract-minute | simulated vs actual open lots | share of contract-minutes exact; mean absolute lot difference; relative divergence |
| Portfolio P&L | cycle | simulated vs actual (actual from fills, same cost model) | ₹ difference per cycle, correlation, sum; gross and net separately |

Each table is reported by split (DEV / VAL / TEST), by underlying, by fill model, and for each placeholder mode. Two
modes are kept apart: **Mode A** (actual entries teacher-forced, simulated exits) and **Mode B** (fully simulated).
TEST is contaminated for hand-derived constants (all 35 cycles were inspected); it is reported, never used to select.

## 7. Explicit exclusions

No live trading or broker integration · no ML controller · no unbounded parameter search · no change to existing results ·
no claim that the original strategy has been recovered.
