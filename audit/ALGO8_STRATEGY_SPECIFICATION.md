# Algo 8 — Reconstructed Strategy Specification

Part of the [complete reconstruction audit](ALGO8_COMPLETE_RECONSTRUCTION_AUDIT.md) ·
[findings register](ALGO8_MASTER_FINDINGS_REGISTER.md) · [readiness](ALGO8_RECONSTRUCTION_READINESS.md) ·
[data gaps](ALGO8_DATA_GAPS_AND_REQUIREMENTS.md) · [roadmap](ALGO8_RECONSTRUCTION_ROADMAP.md)

This is the best evidence-backed description of what Algo 8 does, written as a system from the first order to the last.
It is **not** original source code. Every rule carries a status and the register ID(s) that support it:

| Tag | Meaning |
|---|---|
| **[C]** | CONFIRMED as an observed property of the June–October 2026 export |
| **[S]** | STRONG EVIDENCE — repeatedly observed; the precise original rule is not fully identified |
| **[P]** | PARTIALLY UNDERSTOOD |
| **[H]** | HYPOTHESIS |
| **[U]** | UNKNOWN — do not fill with an assumption |
| **[X]** | CONTRADICTED / INVALIDATED |

**Snapshot:** 9 November 2026 (PR #3 head `6b4ef390`). **[U] means "not identified in the available data"** — it does not
mean the strategy has no such rule. Conflicting measurements behind some tags are reconciled in the audit's
[§7A](ALGO8_COMPLETE_RECONSTRUCTION_AUDIT.md#7a-reconciliation-of-conflicting-measurements): the per-lot stop level is
tagged as a **band** (1.6–1.7× of the cheapest open entry on D-1), not a constant, and PR #2's 1.55× own-entry figure is
not used.

Times are IST. Data scope: 35 cycles, 22/23 June – 22 October 2026 (see the [register](ALGO8_MASTER_FINDINGS_REGISTER.md#how-to-read-this-register)).

---

## A. Strategy architecture

```text
              ┌──────────── one cycle = (underlying, weekly expiry) ────────────┐
 D-1 (BTST)   │ opening assembly → scheduled ladder windows → extra sales /      │
 pre-expiry   │ protection changes / partial reductions → end-of-day carry book   │
 session      │ (+ overnight lump hedge, v_)                                      │
              │                       ── carry overnight ──                       │
 D0 expiry    │ D0 ladder windows (while the book is active) → Clock-B rebalances │
 session      │ → stops / reductions / salvage → late liquidation (~15:14 later)  │
              └───────────────────────────────────────────────────────────────────┘
 Over everything: cycle-level stop (s_ module) on cumulative LTP MTM → liquidate all, no new entries.
 Outside the algo: platform risk actor (AlgoId 152432) and a separate SENSEX hedge app (2.18811E+15).
```

**Modules (order tag, column 163)** [C] DAT-06:

| Module | Tag | Order type | Observed role |
|---|---|---|---|
| Body | numeric | DAY limit | Short CE/PE sales and their buy-backs |
| Wing hedge | `h_…` | IOC limit | Long OTM wings bought with body sales, sold when body exposure is reduced |
| Lump hedge | `v_…` | IOC limit | Single-strike overnight tail hedge bought late D-1, salvaged on D0 |
| Stop-loss | `s_…` | DAY + IOC | Whole-cycle liquidation; present on exactly the 12 stop-out cycles |
| Manual | `m_…` | IOC | One day only (7 July NIFTY) |

**AlgoIds (column 144)** [C] DAT-07: one id per **underlying** (99999 = NIFTY, 1E+16 = SENSEX), plus the platform risk
actor and a separate hedge app. AlgoId does **not** identify sub-strategies or allocations. NIFTY and SENSEX share one
normalized framework (same clocks, same base-unit ladder after ÷65/÷20 [S] SIZ-03) but differ in wing configuration and
exceptions; identical complete code is not established.

**Allocations** [S] STR-02: the book is the superposition of many small concurrently managed allocations (one base unit
per child order), across neighbouring strikes. Original allocation IDs are not in the export [U]; the same contract can be
bought and sold within minutes by different allocations (26 % of unscheduled buy-back episodes have a same-contract sale
within 60 s, MGT-07).

---

## B. Market data and inputs

| Input | Evidence that it affects decisions | Status |
|---|---|---|
| Clock time (fixed grids, Clock B, late flatten) | Every confirmed chain is a fixed clock; schedule 544/544 | **[C]** affects decisions (ENT-02, MGT-02) |
| Index level (previous completed minute close or a live quote) | Opening strike 31/31 nearest ATM; later strikes track the moving ATM | **[S]** (STK-01, STK-02); exact feed **[U]** |
| Option LTP of held contracts | Recovered decision quote; stop hazard rises with price / entry | **[S]** (DAT-05, EXT-02, EXT-04) |
| Option premium of the ATM leg | Routine wing budget ≈ 2.5 % of the ATM leg premium | **[S]** (HDG-02) |
| Own position state (open lots, entry prices, active/flat) | Expiry entries conditional on an active book; one-lot stop quantities; Clock-B picks the contract with most lots | **[S]** (ENT-03, EXT-03, MGT-04) |
| Cycle-cumulative P&L (LTP MTM, body + hedges) | Cycle stop | **[S]** (RSK-01) |
| Recent index movement (5–15 min) | Off-grid strikes shift toward the move; 68.6 % of orders add delta in the move's direction | **[S]** descriptive (STK-04, MGT-09); as a trigger **[U]** |
| Spot location in the day's range / prior high / R1 | Within-date AUC 0.69–0.74 for offset direction | **[H]** (STR-03) |
| Expiry / calendar (DTE, exchange holidays) | Cycle definition; D0 vs D-1 ladders | **[C]** (STR-01) |
| Greeks (delta/gamma/vega/theta of the book) | Clock-B contract choice correlates with largest gamma/vega exposure; side reductions with exposure | **[P]** associated, not shown to be computed (MGT-04, MGT-06) |
| IV level/changes, realized vol | No separable effect found | **[U]** (likely not used; not excluded) |
| Classical indicators (EMA, RSI, MACD, ATR, …) | None identifiably used | **[S]** negative (STR-03) |
| Capital / margin / NAV | ₹2 Cr stated; no sizing formula found | **[U]** (SIZ-05) |
| External data (VIX, news, events) | Not tested; no data | **[U]** |

---

## C. Entry engine

### C1. Eligibility
* Trade the weekly expiry cycle of NIFTY and SENSEX: start on the pre-expiry session, manage into expiry. **[C]** STR-01
* Whether every expiry is traded, and any no-trade filter (gap, VIX, trend, events): **[U]**. Large opening candles do not
  block entry (counterexample 28 Sep). **[S]** ENT-05

### C2. Opening assembly (pre-expiry session)
1. **Time:** 09:16; first CE and PE short fills within 1 s on 31/31 ordinary starts. **[S]** ENT-01
2. **Strike:** `K = d · floor(S / d + 0.5)`, d = 50 NIFTY / 100 SENSEX, S ≈ the completed 09:15 index close; same K for CE and PE. **[S]** STK-01
3. **Protection first:** buy an outward CE wing and PE wing; the CE wing precedes its short on 28/31, PE on 30/31; all four roles start within ≈ 1–5 s. **[S]** (F32)
4. **Seed-wing distance:** NIFTY ≈ K ± 2,000; SENSEX ≈ K ± 4,000 before 16 Sep, exactly ± 2,000 from 16 Sep. **[S]** HDG-01. Cause of the change **[U]**.
5. **Size:** 3 base units per role (195 NIFTY / 60 SENSEX) on most ordinary dates, possibly split across strikes. **[S]** SIZ-02
6. Each child order requests **one base unit** (65 NIFTY / 20 SENSEX); several children make up a slot. **[C]** SIZ-01

### C3. Scheduled ladder (both days)
* **Pre-expiry windows** (start T−2 s, end T+3 min): 09:30, 09:45, 10:00, 10:15, 10:30, 10:45, 11:00, 11:15, 11:30, 11:45, 12:00, 12:30, 13:30, 13:45, 14:00, 14:15, 14:30 — fresh same-strike CE/PE shorts in **544/544** observed windows; older exposure is retained; wings are added. **[C]** ENT-02, MGT-01
* **Ladder size per leg (base units)** — modal, not deterministic **[S]** SIZ-03:

  | Slot (D-1) | 09:16 | 09:31 | 09:46 | 10:01 | 10:16 | 10:31 | 10:46 | 11:01 | 11:16 | 11:31 | 11:46 | 12:01 | 12:16 | 12:31 | 12:46 | 13:01 | 13:16 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | Lineage Y modal | 3 | 2 | 3 | 1 | 2–3 | 1 | 2 | 2 | 1 | 1 | 2–3 | 1 | 0 | 2 | 0 | 0 | 1/0 |
  | Lineage X modal | 3 | 2 | 3 | 1 | 4 | 1 | 2 | … | | | | | | | | | |

  Per-slot hit rates 28–100 %; fixed templates match ≈ 50 % of later slots. The D0 ladder differs (e.g. 09:16 ≈ 8–10 lots CE).
* **Later strikes:** near the moving ATM (within one strike 95–97 %, exact ≈ 70 %). **[P]** STK-02
* **Expiry day:** fresh shorts continue at the quarter windows **while the book is active** (95.1 % precision / 100 % recall,
  given the actual book); none in inactive windows (89/89). **[S]** ENT-03

### C4. Extra (off-schedule) sales
* They exist on both days **[C]**. Timing: per-leg 15-minute timers gated by time windows is a **[P]** lineage-Y model
  (AUC 0.887); lineage X catches only 13/93 later events with its best rule → executable trigger **[U]** (ENT-04).
* Placement: one strike in the direction of the last 10-min (NIFTY) / 15-min (SENSEX) move. **[H]** STK-04, STK-03

### C5. Deterministic or adaptive?
Clock times and base units are deterministic **[C]**. The number of units per slot, extra sales and strike offsets vary
from day to day in ways not explained by any tested market variable **[U]**. They could come from state we cannot see
(allocation budgets, margin) or from configuration changes.

---

## D. Position-management engine

Likely decision sequence on each engine poll (orders cluster at :00–:02, :09–:11, :30–:32 seconds, suggesting a ≈ 10-second
poll [P] — [`FINDINGS.md#L216`](../FINDINGS.md#L216)):

```text
1. cycle stop check (cumulative LTP MTM)                     → if breached: liquidate everything, stop the cycle   [S]
2. per-allocation price stops                               → buy back ONE lot of the stopped allocation          [S]/[U] level
3. clock events (grid A / :00 ladder slots, Clock B on D0)  → add allocations; Clock-B: buy 1 lot, re-sell at ATM  [C] times / [P] choices
4. extra sales / protection changes / partial reductions    → triggers unknown                                    [U]
5. salvage of near-worthless shorts and wings on D0          → buy back / sell at ≤ ≈ ₹1                            [P]
6. late liquidation (15:14 in the later period)             → flatten the short book; wings may remain             [S]
```
The order of steps 1–6 inside one poll is **[H]**. Processes overlap, and fills are not atomic.

| Action | What is known | Status |
|---|---|---|
| Scheduled additions | ENT-02; retained older exposure; theta up, vega/gamma more negative (531/543, 533/543) | [C] |
| Hedge with each addition | Wings within 5 s of ≈ 90 % of paired batches; budget ≈ 2.5 % of ATM leg premium (exact strike ≈ 50 %, ± 1 strike 92–95 %) | [S] HDG-02, HDG-03 |
| Clock B (D0, :14/:29/:44/:59 from 09:29) | 42–47 % of ticks act; **buy back one lot** of usually the contract with the most lots / largest gamma–vega exposure (hit 0.65–0.66 vs 0.41 random); **re-sell the same lots at ATM** ≈ 28 s later | times [S]; quantity/replacement [S]; whether a tick acts / which contract [U] (MGT-03, MGT-04, STK-05) |
| Side-level reductions | Several contracts of one side closed together; timed by clock/time-to-expiry; spot ATR adds little | trigger [U] (MGT-05) |
| Basket reductions | Both sides at once; same picture | trigger [U] (MGT-05) |
| Contract selection in reductions | Largest exposure is the best single criterion (0.77 vs 0.47 random for side-level) | [P] MGT-06 |
| Quantity in reductions | Usually a fraction of a contract (median 11–20 %; one lot in 46–56 %) | [P] MGT-06 |
| Re-entry / replacement | Same-side sale within 60 s after 55 % of unscheduled buy-back episodes; association only | [P] MGT-07 |
| Expiry hedge replacement | Inward moves of protection (81.5 %); more gamma protection (82.0 %) | [P] HDG-04 |
| Wing release | Same-side wings sold around short buy-backs; ratio and choice | [P] HDG-06 |
| Rapid reversal motifs | 59 close/reopen/neutralize cases | [H] MGT-08 |
| Carry book | End-of-D-1 inventory = all surviving allocations; long ≥ short on each right in 31/31 carry books | [S] HDG-05 |
| Overnight lump (`v_`) | Late D-1 (15:06–15:14 until 12 Aug, then 15:23–15:38), heavier short side, 0.9–2.3 % OTM; **size [U]**; D0 salvage dribble | SIZ-04 |

---

## E. Exit engine

For every category, "classified" means its orders can be labelled. It does **not** mean the trigger is recovered.

| Category (share of short buy-back lots, clean build) | Trigger | What is closed | Type | Replacement | Delay | Evidence / validation | Trigger status |
|---|---|---|---|---|---|---|---|
| **Cycle stop** (13.8 %) | Cumulative LTP MTM ≤ ≈ −₹1.30–1.35 L | Everything (body, wings, lump), then no new entries | portfolio risk | No | 1–20 s check latency; fills within 3 s–5 min | 12 stop cycles bracketed; deepest non-stop −₹1.302 L | **[S]** RSK-01; exact constant / origin [U] |
| **Per-lot price stop** (22.5 % labelled) | Price crosses roughly 1.6–1.7 × the cheapest open entry (D-1); weaker and scope-dependent on D0 | **One lot** per decision | individual stop | Often a same-side re-sale (≈ 52 % within 60 s, old ledger) | median ≤ 2–3 min (minute data) | D-1: 88 % answered within 1 min at 1.7×, 38 % at 1.55×; coverage of stop-like exits ≈ 45 % | **[S]** that it exists (EXT-02–EXT-04); exact level/reference [U]; D0 scope [U] (EXT-05) |
| **Side-level reduction** (5.7 %) | Unknown; timed by clock / time-to-expiry | Several contracts of one side, fractions | side-level | Sometimes | — | Best tree VAL precision 0.11 | **[U]** MGT-05 |
| **Basket reduction** (11.8 %) | Unknown | Both sides together | basket-level | Sometimes | — | Best tree VAL precision 0.05 | **[U]** MGT-05 |
| **Same-contract partial** (5.3 %) | Unknown | Part of one contract | allocation-level | Sometimes | — | — | **[U]** |
| **Clock-B rebalance** (4.9 %) / **Clock-B without replacement** (2.7 %) | Clock tick + unknown condition | 1 lot of the selected contract | time-based rebalance | Yes for rebalance: same lots at ATM | ≈ 28 s to the re-sale | Tick act AUC 0.78 | time [S]; condition [U] |
| **Grid rebalance** (A/:00 clocks, 4.6 %) | Clock + unknown | — | time-based | Yes | — | — | [P] |
| **Expiry-day salvage** (13.5 %) | Short premium ≤ ≈ ₹1 or ≤ 5 % of entry on D0 | Whole contract | clean-up | No | — | labelling definition | [P] EXT-07 |
| **Final flatten** (13.1 %) | Time: 15:14 after 3 Aug (9/10 late closures); spread earlier | Short book; wings may remain | scheduled | No | — | 27/29 closures by 15:27:33 | [S] post-Aug; universal rule [U] (EXT-08) |
| **Platform / manual** (1.7 %) | External actor | Positions it did not open | broker/platform | — | — | — | [S] not Algo 8 logic (RSK-04) |
| **Unexplained** (0.6 %) | — | — | — | — | — | — | [U] |
| **Trailing stop / profit target** | No rule found | — | — | — | — | Trailing and target references fail out of sample | **[S] negative** (EXT-06) |

Notes:
* Stops close **one lot at a time** (EXT-03), which fits per-allocation stops on fungible contracts.
* No intermediate-exit rule tested by either lineage reaches 80 % precision and recall (EXT-10).
* Info.txt's "4 % carry-forward SL" and "1 % on expiry day" are treated in section F.

---

## F. Risk management and carry-forward engine

| Control | Evidence | Status |
|---|---|---|
| **Cycle-level stop** | ≈ −₹1.30–1.35 L configured; executed ≈ −₹1.44 L; D-1 and D0; size-independent; gap-through possible | **[S]** RSK-01 |
| **Position-level stop** | Per-allocation one-lot stop; D-1 effective level ≈ 1.6–1.7 × cheapest entry | **[S]** existence / **[U]** exact rule (EXT-02–EXT-05) |
| **Side / basket risk limits** | No threshold on side P&L, basket P&L, drawdown, Greeks or spot-ATR separates actions out of sample; lineage X's best (side drawdown 0.5 % of capital) 18 % / 17 % | **[U]** (MGT-05, EXT-10) |
| **Expiry-day "1 % of capital" stop** | ₹2 L at ₹2 Cr is not observed; the only loss limit seen is ≈ −₹1.3 L and also fires on D-1 | **[X]** as "₹2 L on expiry day"; meaning of "1 %" **[U]** (RSK-03) |
| **"4 % carry-forward SL"** | Six interpretations tested (carried premium vs D-1 close, book value, capital 2 Cr / 1 Cr, \|D-1 MTM\|, spot, D0 drawdown vs premium collected); none separates DEV, VAL and TEST; capital-based and literal-spot readings never trigger before the cycle stop | **[U]** (RSK-02) |
| **Carried positions** | Carried lots have the weakest per-lot stop response (28–35 % within 5 min; hazard 2.9 %/min at ≥ 1.5×); they are unwound gradually through D0, by salvage, cycle stop and late flatten | **[P]** EXT-05 |
| **Overnight protection** | Long ≥ short on each right in 31/31 carry books; lump hedge on the heavier short side | **[S]** HDG-05, SIZ-04 |
| **Hedge release** | Same-side wings sold with buy-backs | **[P]** HDG-06 |
| **Final flattening** | 15:14 (later period); residual wings may remain to expiry | **[S]** EXT-08 |
| **Salvage** | ≤ ₹1 shorts bought back, ≤ ₹1 wings sold on D0 | **[P]** EXT-07 |
| **Capital / margin constraint** | Not observable | **[U]** SIZ-05 |
| **Post-stop entry lock** | After the `s_` cycle stop, no new entries in that cycle [S]; but after the short book first goes flat for other reasons, new short fills follow in ten cycles | **[S]** for the cycle stop; general lock **[X]** |

---

## G. Execution engine

| Item | Evidence | Status |
|---|---|---|
| Order = one tag (column 163); child request = one base unit (65 / 20) | 39,874 tags; 2,022/2,032 and 2,375/2,375 base-unit requests | **[C]** DAT-01, SIZ-01 |
| Price = marketable limit LTP × 1.15 buy / × 0.85 sell (`v_` buy × ≈1.03), 0.05 tick | Median limit/fill ratios; recovered quote inside candle 96.6 % | **[C]** DAT-05 |
| Validity | Body DAY; wings / lump / stop IOC (stop also DAY) | **[C]** DAT-06 |
| Fill reconstruction | Fills of an order within ≤ 57 s; partial fills exist (1,550 `PartiallyFilled` rows) | **[C]** DAT-01 |
| Decision → fill latency | Tagged orders ≈ 0–1 s; body orders ≤ ≈ 14–30 s after the order minute starts (upper bound) | **[P]** EXT-11 |
| Poll cadence | Second-of-minute clusters suggest ≈ 10 s polling | **[H]** |
| Cancellations, rejections, modifications, acknowledgements | Not in the export | **[U]** |
| Rapid reversal motifs | Could be execution artefacts or duplicate submissions | **[H]** MGT-08 |

**Separating decision logic from execution.** Strategy decisions are the clocks, strikes, quantities, stops and
liquidations above. Broker/platform behaviour is the limit band, partial fills, the platform risk actor (152432) and the
second hedge app. The export records **fills, not decisions**. For body orders the decision time is bracketed, not
known, and unfilled or cancelled requests are invisible. Any stop with a level near the price at which it fired can
therefore be mis-measured by up to one minute and one tick.

---

## Executable approximation (for a first replica) — clearly labelled

A developer could implement the following today. Each line is an **approximation** whose status is shown; it is not the
original algorithm.

1. Cycle calendar: D-1 + D0 per weekly expiry (NIFTY, SENSEX). [C]
2. 09:16 opening: K = nearest ATM to the previous minute's index close; buy CE/PE seed wings at K ± 2,000 (SENSEX ± 4,000
   before 16 Sep 2026); sell 3 base units per role. [S]
3. Ladder: at each of the 17 pre-expiry windows sell the modal base units per leg at the current ATM, each with a wing at the
   2.5 %-of-ATM-premium budget. On D0, use the D0 ladder while the book is active. [S] times / [S] sizes as modes
4. Per-lot stop: buy back one lot when the option trades ≥ ≈ 1.6–1.7 × that allocation's entry (D-1). D0 behaviour is
   uncertain; use the same rule with lower confidence. [S]/[U]
5. Clock B on D0 (from 09:29, every 15 min at :14/:29/:44/:59): optionally buy back one lot of the contract with the most lots
   and re-sell it at ATM. [P]
6. Cycle stop: liquidate everything when cumulative LTP MTM ≤ −₹1.33 L; then stop. [S]
7. Salvage at ≤ ₹1 on D0; flatten the short book at 15:14. [P]/[S]
8. Execution: one base unit per child order at LTP × 1.15 / 0.85 limits. [C]

Components that remain **[U]** and must be left as explicit placeholders, not filled with guesses: extra-sale trigger,
side/basket reduction triggers, re-entry trigger, contract selection in reductions, lump size, 4 % carry SL,
expiry-day 1 % stop, eligibility filter, capital/margin sizing.
