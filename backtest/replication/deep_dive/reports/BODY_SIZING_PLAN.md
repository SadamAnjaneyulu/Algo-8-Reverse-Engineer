# Body position sizing: how many lots, when, and why — plan, written before the tests

**User questions.** (1) How is quantity gradually increased; is it exactly 1 lot of CE+PE every 15 minutes, or more — and what triggers more? (2) Did a SEBI lot-size change in September alter it? (3) How many lots are added as single-option (solo) sells in between?

**What is already established (read-only, from this session's data check, before the plan).**
* Contract unit in the ledger: every order quantity is a multiple of **65 (NIFTY) / 20 (SENSEX) in every month June–October 2026** (min quantity 65/20; gcd 65/20 per month). No unit change is observed.
* Public sources (web search) show the last NIFTY lot revision (75→65) took effect 30 Dec 2025, computed from September **2025** prices; SENSEX 20. I found no report of a September 2026 revision; I did not read the NSE/BSE circulars themselves (unverified beyond the ledger).
* Earlier finding (paired-sell study): D-1 CE+PE paired sells follow a fixed 15-minute slot schedule, same for NIFTY/SENSEX, with a version change between D-1 2026-09-09 and 2026-09-16.

## Locked definitions
* **Pair** = body `open_short` CE and PE at the **same strike within ±3 s** (each pair = 1 lot + 1 lot in all but a few cases; lots are 1-lot orders in 99.5% of D-1 sells). **Solo sell** = body `open_short` not in a pair.
* **Block** k = 15-minute block starting 09:16:00 + 900·k s (the slot minutes of earlier studies); **offset** = seconds from the block start.
* **Wave** = a group of pairs at the same offset cell; **timetable** = the set of (block, offset cell) in which ≥ 90% of the cycles of a version fire a pair. **Version** V1/V2 as found earlier (cut between D-1 2026-09-09 and 09-16; to be re-derived here, not assumed).
* D-1 primary (position building); D0 reported for totals only.

## Tests
1. **Unit constancy:** raw quantity gcd/min per underlying-month (done above; re-run in the script and stored); notional per lot (lot size × spot at D-1 open) per cycle — does it move with the version?
2. **Timetable:** extract the modal timetable for V1 and V2 (cells, per-cell fire frequency), adherence per cycle, totals of scheduled pairs per cycle; V1→V2 differences cell by cell.
3. **Is the timetable state-independent?** Fire frequency of each scheduled cell vs market state (spot move since open, straddle premium, IV, DTE, book P&L): cells with frequency < 100% — what separates misses? Cross-cycle variance of the scheduled total vs spot level/notional/premium (a sizing rule linked to capital or notional would show a relation).
4. **Version-change timing:** bracket the change date; compare with candidate events: lot-size/unit (none), notional-per-lot jump, volatility regime, cycle calendar (DTE, weekday), the 09-15 NIFTY expiry gap.
5. **Quantity build-up:** cumulative body short lots per right through D-1 by hour (quantiles across cycles): scheduled pairs, solo sells, buy-backs, net; end-of-D-1 short lots; notional of the short book (lots × unit × spot) and premium collected, as multiples of the stated ₹2 crore (context only).
6. **Solo sells in between:** lots per cycle, per block, per right, per version; share of D-1 sold lots; multi-lot bursts (several 1-lot orders in the same second at one strike) vs single lots; relation of mid-block pairs (offset > 100 s) to solo triggers.
7. **Reactive quantity (offset > 100 s, outside the timetable):** is the number of reactive lots tied to the lots just bought back (replacement), or to the move variables found earlier (breakout, favourable move)?

## Decision rules (fixed now)
* "Fixed timetable" if every scheduled cell fires in ≥ 95% of the cycles of its version and the per-cycle scheduled total has zero or near-zero variance.
* "Sized from notional/capital" only if the scheduled total (or reactive total) correlates with notional per lot, spot, or premium across cycles beyond a permutation null (|Spearman| ≥ 0.4, p < 0.01 after Holm over the list) — otherwise not supported.
* A change date is "explained" by a candidate only if that candidate changes on the same date window and nothing else in the list does.
* Labels: Observed / Inferred / Unresolved. In-sample; unit/notional facts are Observed; reasons for the version change cannot be observed.

## Limits (known in advance)
Second-resolution fills; pair detection is a ±3 s rule (coincident solo sells at one strike may be mislabeled as pairs); no source code; no external circular read; D-1 timetable only; 5 cycles have no D-1 or D0 log.
