# Algo 8: validation of Rahul's risk rules against order-level data

Client wording (`Info.txt`), tested exactly as written:

> "It is a BTST algorithm which carry forward SL of 4% on the positions carry forward to expiry and 1% on the entire capital on expiry day. The capital required for the following algorithm is 2 crore."

* **Rule 1:** carry-forward stop, 4 % on the positions carried to expiry. The 4 % is **not** read as 4 % of capital.
* **Rule 2:** expiry-day kill switch at 1 % of ₹2 crore = **₹2,00,000**.

Both remain **client-provided hypotheses** (register RSK-07 and RSK-08). No threshold was fitted or tuned; the client
constants are used as stated. Every number comes from executed code (`run_all.py`, 12 tests pass).

## 1. Verdicts

| Rule | Classification | Why |
|---|---|---|
| **4 % carry-forward stop** | **Inconsistent with observed behaviour** (readings A–D); **not identifiable** (reading E) | Position readings: 28–38 % of 4 % crossings get no buyback within 5 min, 60–72 % of stop-like buybacks of carried positions have no prior crossing, and the response does not change at 4 % (placebo 2 % → 64 % is flat). The portfolio vs D-1 value reading (C) fires 7–14 times without any liquidation. The portfolio vs entry reading (E) crosses only in cycles where the cycle stop fires at the same moment, so it cannot be separated from that stop |
| **1 % (₹2 L) expiry-day kill switch** | **Inconsistent with observed behaviour** | Expiry-day MTM falls below −₹2 L twice with **no** liquidation and continued trading (SENSEX 9 Jul −₹2.16 L, SENSEX 22 Oct −₹2.47 L). At the 9 non-gap expiry-day stops, expiry-day MTM ranged −₹0.69 L to −₹2.85 L, so the stop is not keyed to expiry-day P&L |
| **Observed ≈ ₹1.3–1.4 L cycle stop** (control) | **Strong evidence** of a separate operational stop on **cumulative D-1 + D0** MTM | Quote-based MTM at the trigger: median −₹1.419 L, SD ₹5.5 K (10 non-gap stops). NIFTY and SENSEX are alike, it fires on D-1 too, and it is not a minute-data artefact. Its exact constant and origin are **not identifiable** |

A threshold crossing is not proof that the algorithm used that threshold. Lacking order-lifecycle records, a kill
switch cannot be told apart from ordinary liquidation except through behaviour after the crossing.

## 2. Data and inventory (Phase 1)

| Item | Result |
|---|---|
| Orders / lots | 39,874 orders (column-163 `UniqueOrderIdentifier`) = 63,652 lots = fills, in every cycle |
| Cycles | 35. D-1 present 32, D0 present 33, both 30. Carry tests run on **30**: NIFTY 1 Sep stopped on D-1 (nothing carried); NIFTY 29 Sep has D-1 trades but **no D0 fills in the export** (109 short / 186 long lots carried and still open at the end) |
| Genuinely carried inventory | 3,238 short and 4,749 long lots (net position per contract at the D-1 close, convention-free) |
| **Ledger defect found** (DAT-10) | PR #3's lot ledger maps orders placed after the last D-1 bar onto the first D0 minute: 77 orders / 1,024 lots in 18 cycles, mostly late lump (`v_`) and wing (`h_`) orders. Its carried counts differ from the fills in 18 of 32 cycles (229 short, 989 long lots). The session-aware copy built here matches the fills in **all 32** cycles under all conventions. PR #3 outputs are not modified |
| Final inventory | Matches the fills per contract under cheapest / FIFO / LIFO: 110 short and 630 long lots open at the end of the export (settle at expiry) |
| MTM reconciliation | Lot-ledger MTM = independent fills + candles MTM (`analysis/mtm.py`) at the end of the export in 31 / 35 cycles (< ₹1). The rest differ by ₹65–3,468 because the fills-based MTM marks open positions at post-close bars |
| D0 identity | Realised + unrealised D0 = cumulative(t) − cumulative(D-1 close): maximum error ₹2 × 10⁻⁹ |
| Ambiguous ownership | 1,971 of 8,674 D0 short buybacks (2,903 of 12,025 lots) split between carried and new lots differently across conventions. Every convention-dependent result is reported per convention |
| D-1 closing mark | From 4 Aug, using the last print (15:30–15:39 post-close bars) instead of the 15:29 bar changes the book's D-1 value by a median ₹4.8 K and up to ₹31.5 K (19 cycles > ₹1 K). That is the same order as the 4 % thresholds, so it was run as a sensitivity |
| Platform / manual orders | 1,111 orders (2,920 lots) from the platform risk actor, hedge app or `m_`: kept, labelled |

## 3. Rule 1: 4 % carry-forward stop (Phase 2)

Carried = lots opened on the D-1 date and not closed on that date. Short carried lots are the positions. Wings
carried overnight are included in portfolio P&L (C, E).

| ID | Reading | Denominator (explicit) | Trigger |
|---|---|---|---|
| A | 4 % of the carried lot's entry premium | that lot's entry price × lot size | mark ≥ 1.04 × the lowest entry among its open carried lots |
| B | 4 % of the carried position's reference value | D-1 closing mark × lot size | mark ≥ 1.04 × D-1 close |
| C | 4 % of the carried portfolio's reference value | Σ carried short lots × D-1 closing mark | carried book's D0 P&L (shorts + carried wings, vs D-1 close) ≤ −4 % × denominator |
| D | 4 % individual-position loss | Σ over the contract's carried short lots of entry × lot size | that position's P&L since entry (realised + unrealised) ≤ −4 % × denominator |
| E | 4 % combined carried-portfolio loss | Σ carried short lots × entry price | carried book's P&L since entry ≤ −4 % × denominator |

Per-cycle denominators (30 cycles): carried short value at the D-1 close ₹1.71–6.54 L (median ₹4.34 L). **C threshold**
₹6.9–26.2 K and **E threshold** (FIFO) ₹9.2–30.6 K. Per-position thresholds: A ₹1–603 (median ₹199), B ₹1–578 (median ₹169), D ₹60–11,346 (median ₹1,342).

**Action matching.**
- **Position readings:** the first short buyback of that contract within 5 min of the first crossing. It counts as a match only if it is not a scheduled or clock exit.
- **Portfolio readings:** the cycle-stop module within 5 min (GT1), or ≥ 50 % of the open carried short lots bought back within 5 min (GT2).
- **Stop events** used for recall are the first stop-like buyback of each carried contract (A, B, D), or GT1 / GT2 (C, E).

**Position readings (A, B, D).** 349 carried short contracts:

| Reading | Conv. | Crossings | at D0 open | Matched | of which same minute | Followed by a scheduled / clock exit | False triggers | Stop events | Missed | Precision | Recall | Hit rate after the open (baseline) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | cheapest | 181 | 109 | 92 | 64 | 37 | 52 | 232 | 140 | 0.51 | 0.40 | 0.68 (0.065) |
| A | FIFO | 176 | 116 | 81 | 54 | 39 | 56 | 229 | 148 | 0.46 | 0.35 | 0.61 (0.043) |
| B | cheapest | 201 | 111 | 86 | 56 | 41 | 74 | 232 | 146 | 0.43 | 0.37 | 0.66 (0.071) |
| B | FIFO | 194 | 111 | 79 | 53 | 41 | 74 | 229 | 150 | 0.41 | 0.35 | 0.62 (0.047) |
| D | cheapest | 153 | 91 | 82 | 52 | 28 | 43 | 232 | 150 | 0.54 | 0.35 | 0.71 (0.076) |
| D | FIFO | 134 | 95 | 65 | 42 | 29 | 40 | 229 | 164 | 0.49 | 0.28 | 0.60 (0.053) |

(LIFO is within 0.015 of cheapest-first: see the CSV.)

- **Crossings are followed by buybacks far more often than baseline minutes,** but **4 % is not special.** The placebo
  ladder ([`results/carry_forward_placebo_ladder.csv`](results/carry_forward_placebo_ladder.csv)) gives hit rates after
  the open of 0.65–0.76 (A, cheapest) at 2 %, 4 %, 8 %, 16 %, 32 % and 64 %, with no step at 4 %. The association
  measures "price rose and the algo bought back", which the known per-lot stop and management already produce.
- **As a stop rule it fails:** 40–74 crossings (28–38 %) get no buyback within 5 min, and 60–72 % of stop-like buybacks of
  carried positions happen with no prior 4 % crossing.
- 55–71 % of crossings occur in the first D0 minute (the overnight gap), and 63–71 % of matches are in the same minute
  as the crossing, where the order of price and decision inside the minute cannot be established.

**Portfolio readings (C, E).** 30 cycles; 11 D0 cycle stops (GT1); GT2 events 11 (18 under FIFO):

| Reading | Ownership | Crossings | Matched with cycle stop | Matched without cycle stop | False triggers | Recall of D0 cycle stops |
|---|---|---:|---:|---:|---:|---:|
| C | as traded (cheapest / FIFO / LIFO) | 15–16 | 7 | 1* | 7–8 | 0.64 |
| C | held book, convention-free | 19 | 7 | 1* | 11 | 0.64 |
| C | held, D-1 ref = last print (sensitivity) | 22 | 7 | 1* | 14 | 0.64 |
| E | as traded, FIFO | 6 | 6 | 0 | 0 | 0.55 |
| E | as traded, cheapest / LIFO | 6 | 4 | 0 | 2 | 0.36 |
| E | held book | 14 | 7–9 | 0 | 5–7 | 0.64–0.82 |

\* SENSEX 6 Aug: carried-book liquidation starts at 09:17. Its window includes the 09:22:40 cycle stop, so it is not independent of it.

- **C false-triggers on ordinary expiry days:** SENSEX 9 Jul, the held carried book lost ₹2.36 L against an ₹8.6 K
  threshold with no liquidation.
- **E (FIFO) never false-triggers,** but each of its 6 crossings is a cycle-stop cycle crossing at the same minute. It
  misses 5 of 11 D0 cycle stops, and at 2 % it behaves the same way. The evidence cannot separate E from the cycle stop.

## 4. Rule 2: ₹2 L expiry-day kill switch (Phase 3)

Expiry-day P&L uses the D-1 closing mark for carried lots and the entry price for new D0 lots. Cycle-cumulative MTM is
reported separately (S6). Kill-switch behaviour = liquidation within 5 min (cycle-stop module, or ≥ 50 % of open short
lots bought back) **and** no new short entries after a 5-minute in-flight allowance.

| Series | Conv. | Sessions crossing −₹2 L (of 33) | With kill-switch behaviour | Of which with the cycle stop | No kill-switch behaviour |
|---|---|---:|---:|---:|---:|
| S1 realised only | cheapest / FIFO / LIFO | 18 / 8 / 16 | 3 / 2 / 2 | all | 15 / 6 / 14 |
| S2 unrealised only | all | 0 | — | — | — |
| **S3 combined (D0 MTM)** | convention-free | **4** | 1 | 1 | **2** (+1 liquidation with a later entry, with the cycle stop) |
| S4 carried inventory only | cheapest / FIFO / LIFO | 2 / 1 / 2 | 2 / 1 / 2 | all | 0 |
| S5 new D0 positions only | cheapest / FIFO / LIFO | 4 / 3 / 4 | 1 | 1 | 3 / 2 / 3 |
| S6 context: cycle-cumulative | convention-free | 1 (20 Aug gap) | 1 | 1 | 0 |

S3 crossings, chronologically ([`order_action_matching.csv`](order_action_matching.csv)):

| Session | Crossing | Before | After | Verdict |
|---|---|---|---|---|
| SENSEX 9 Jul | 11:28, D0 MTM −₹2.16 L (cumulative −₹0.16 L) | 11:27:41 platform sell CE 78300 | 11:28:41 partial buyback CE 77300. No liquidation; **233** new short orders after 5 min; trades to the close | **No kill-switch behaviour** |
| SENSEX 20 Aug | 09:15 (open), −₹2.21 L | cycle stop already sent at 09:14:13 | liquidation | Coincides with the cycle stop (gap) |
| NIFTY 13 Oct | 09:17, −₹2.79 L minimum | 09:16:57 buy CE 22850 | cycle stop 09:18:01; 1 short entry later | Coincides with the cycle stop |
| SENSEX 22 Oct | 12:53, −₹2.47 L | 12:52:39 lump disposal | 12:53:00 side-level buyback. No liquidation; **67** new short orders after 5 min | **No kill-switch behaviour** |

## 5. Control: the observed cycle stop (Phase 4)

Reconstructed independently at each `s_` trigger: fills before the trigger, plus open positions marked at the recovered
quotes of the liquidation orders (limit ÷ 1.15 / ÷ 0.85; 100 % of position value quote-marked).
[`results/cycle_stop_control.csv`](results/cycle_stop_control.csv)

| Measure | Value |
|---|---|
| Quote MTM at trigger, 10 non-gap stops | median **−₹1.419 L**, mean −₹1.422 L, **SD ₹5.5 K**, range −₹1.356 to −₹1.533 L |
| By underlying | NIFTY −₹1.428 L (6), SENSEX −₹1.412 L (4) |
| Gap-through stops | NIFTY 18 Aug −₹2.14 L, SENSEX 20 Aug −₹2.71 L (sent 09:14:13) |
| Day | 11 on D0, 1 on D-1 (NIFTY, 31 Aug 14:46) |
| Minute-close MTM one minute before the stop | median −₹1.09 L: minute data understate the trigger-time MTM |
| Deepest non-stop cycle, minute close | −₹1.218 L |
| D0-only MTM at the 9 non-gap D0 stops | −₹0.69 L to −₹2.85 L (not constant) |
| After the stop | Short-opening fills in 11 of 12 cycles (116 orders): within 60 s in 10 cycles (67 were body orders entered by the stop minute), later than 5 min in 2 (SENSEX 6 Aug, NIFTY 13 Oct) |

**Findings:**
- **Separate operational stop:** yes. It is on cumulative D-1 + D0 MTM, tight across cycles, fires on either day, and
  is implemented by the `s_` module.
- **Result of another rule:** none of the 4 % or ₹2 L readings explains it. Its level is about 0.71 % of ₹2 Cr; that
  is arithmetic, not evidence of a base.
- **Minute-data artefact:** no. The quote reconstruction does not use minute closes, and it is tight.
- **NIFTY vs SENSEX:** no material difference (n = 6 / 4).
- **Exact constant:** between the deepest non-stop mark (−₹1.22 L) and the trigger quotes (≈ −₹1.36 L), so **not identifiable**.

## 6. Limitations

1. Minute closes are not the broker's MTM. The decision time of body orders is known only to the minute.
2. Fills only: no order lifecycle, so a kill switch and normal liquidation are separated only by behaviour.
3. Lot ownership is a convention: 2,903 D0 buyback lots are allocated differently across conventions.
4. The D-1 closing mark is ambiguous by up to ₹31.5 K per book (post-close prints).
5. NIFTY 29 Sep has no D0 fills, and three cycles have no D-1 session.
6. Not used and not invented: margin, capital deployment, bid/ask, broker MTM convention.
7. Everything is in-sample (all sessions inspected before). The Info.txt sentence has no stated accounting
   convention, so other readings remain possible.

## 7. Cycle-by-cycle table

Full columns: [`cycle_level_risk_reconciliation.csv`](cycle_level_risk_reconciliation.csv); events:
[`results/carry_forward_4pct_events.csv`](results/carry_forward_4pct_events.csv), [`expiry_day_1pct_tests.csv`](expiry_day_1pct_tests.csv).
D0 P&L columns are minimum values over the expiry session.

| Expiry | Und | Carried short / long lots | Carried short value at D-1 close (₹ L) | 4 % C / E thresholds (₹ K) | D0 realised min (FIFO, ₹ L) | D0 unrealised min (₹ L) | D0 combined min (₹ L) | −₹2 L crossing | Observed stop | Quote MTM at stop (₹ L) | C (held) | E (FIFO) | ₹2 L classification | Limitation |
|---|---|---|---:|---|---:|---:|---:|---|---|---:|---|---|---|---|
| 2026-06-23 | NIFTY | — | — | — | -2.48 | -1.24 | -0.98 |  |  | — | n/a | n/a | — | no D-1 session: nothing carried |
| 2026-06-25 | SENSEX | 85 / 139 | 3.02 | 12.1 / 18.8 | -0.76 | -0.01 | -0.23 |  |  | — | false trigger | missed | — |  |
| 2026-06-30 | NIFTY | 99 / 173 | 4.97 | 19.9 / 24.7 | -1.74 | -0.75 | -1.74 |  | 06-30 14:25 (D0) | -1.53 | missed | missed | — |  |
| 2026-07-02 | SENSEX | 94 / 112 | 4.32 | 17.3 / 21.3 | -1.60 | -0.08 | -0.49 |  |  | — | false trigger | — | — |  |
| 2026-07-07 | NIFTY | 123 / 185 | 5.20 | 20.8 / 23.5 | -0.95 | -0.10 | -0.19 |  |  | — | — | — | — | platform/manual orders 7 |
| 2026-07-09 | SENSEX | 98 / 152 | 2.14 | 8.6 / 22.2 | -2.32 | -0.47 | -2.16 | 11:28 |  | — | false trigger | — | **crossed, no action; trading continues** | platform/manual orders 517 |
| 2026-07-14 | NIFTY | 70 / 120 | 3.12 | 12.5 / 17.2 | -1.68 | -0.00 | -1.68 |  | 07-14 09:15 (D0) | -1.38 | with cycle stop | with cycle stop | — |  |
| 2026-07-16 | SENSEX | 97 / 179 | 3.97 | 15.9 / 21.9 | -1.70 | -0.36 | -1.70 |  | 07-16 11:00 (D0) | -1.43 | false trigger | missed | — |  |
| 2026-07-21 | NIFTY | 92 / 148 | 3.79 | 15.2 / 19.0 | -0.75 | -0.08 | -0.04 |  |  | — | false trigger | missed | — | platform/manual orders 139 |
| 2026-07-23 | SENSEX | 113 / 155 | 5.61 | 22.4 / 25.8 | -2.24 | -0.01 | -0.05 |  |  | — | — | — | — | platform/manual orders 89 |
| 2026-07-28 | NIFTY | 121 / 203 | 4.36 | 17.4 / 19.9 | -0.17 | -0.23 | +0.39 |  |  | — | — | missed | — |  |
| 2026-07-30 | SENSEX | 107 / 137 | 4.89 | 19.6 / 20.6 | -1.05 | -0.01 | +0.22 |  |  | — | — | missed | — |  |
| 2026-08-04 | NIFTY | 132 / 196 | 6.40 | 25.6 / 28.2 | -3.27 | -0.68 | -1.76 |  |  | — | false trigger | missed | — |  |
| 2026-08-06 | SENSEX | 62 / 76 | 3.48 | 13.9 / 16.5 | -0.92 | -0.53 | -0.91 |  | 08-06 09:22 (D0) | -1.39 | liquidation (cycle stop 7 min later) | with cycle stop | — |  |
| 2026-08-11 | NIFTY | — | — | — | -0.00 | -0.13 | -0.13 |  |  | — | n/a | n/a | — | no D-1 session: nothing carried |
| 2026-08-13 | SENSEX | 79 / 99 | 2.45 | 9.8 / 12.9 | -0.41 | -0.15 | -0.18 |  |  | — | false trigger | — | — |  |
| 2026-08-18 | NIFTY | 94 / 164 | 3.51 | 14.0 / 15.7 | -1.17 | +0.00 | -1.17 |  | 08-18 09:15 (D0) | -2.14 | with cycle stop | with cycle stop | — | platform/manual orders 68 |
| 2026-08-20 | SENSEX | 120 / 157 | 5.01 | 20.1 / 21.9 | -2.21 | +0.00 | -2.21 | 09:15 | 08-20 09:14 (D0) | -2.71 | with cycle stop | with cycle stop | with cycle stop |  |
| 2026-08-25 | NIFTY | 116 / 163 | 4.61 | 18.4 / 24.0 | -1.97 | -1.16 | -1.34 |  |  | — | false trigger | missed | — |  |
| 2026-08-27 | SENSEX | 108 / 151 | 3.96 | 15.8 / 22.3 | -0.45 | -0.04 | -0.02 |  |  | — | — | — | — |  |
| 2026-09-01 | NIFTY | 0 / 0 | — | — | — | — | — |  | 08-31 14:46 (D-1) | -1.45 | n/a | n/a | n/a | no D0 fills in the export |
| 2026-09-08 | NIFTY | 133 / 203 | 6.54 | 26.2 / 30.6 | -1.13 | +0.00 | +1.02 |  |  | — | — | — | — | platform/manual orders 291 |
| 2026-09-10 | SENSEX | 102 / 181 | 4.25 | 17.0 / 23.4 | -0.06 | -0.02 | -0.08 |  |  | — | missed | missed | — |  |
| 2026-09-15 | NIFTY | — | — | — | -0.98 | -0.08 | -0.13 |  |  | — | n/a | n/a | — | no D-1 session: nothing carried |
| 2026-09-17 | SENSEX | 92 / 110 | 5.43 | 21.7 / 23.4 | -0.95 | -0.30 | -0.81 |  |  | — | — | missed | — |  |
| 2026-09-22 | NIFTY | 112 / 174 | 4.64 | 18.5 / 20.3 | -2.96 | -0.30 | -1.59 |  | 09-22 14:14 (D0) | -1.41 | false trigger | missed | — |  |
| 2026-09-24 | SENSEX | 124 / 159 | 4.96 | 19.8 / 22.0 | -1.80 | +0.00 | -1.80 |  | 09-24 09:15 (D0) | -1.36 | with cycle stop | with cycle stop | — |  |
| 2026-09-29 | NIFTY | 109 / 186 | 5.80 | 23.2 / 30.8 | — | — | — |  |  | — | n/a | n/a | n/a | no D0 fills in the export |
| 2026-10-01 | SENSEX | 70 / 110 | 3.52 | 14.1 / 17.1 | -1.79 | -0.46 | -0.56 |  |  | — | — | — | — |  |
| 2026-10-06 | NIFTY | 58 / 72 | 3.01 | 12.0 / 13.6 | -1.05 | -0.00 | +0.18 |  |  | — | false trigger | — | — |  |
| 2026-10-08 | SENSEX | 51 / 51 | 2.19 | 8.7 / 11.3 | -1.60 | -0.00 | -0.00 |  |  | — | false trigger | — | — |  |
| 2026-10-13 | NIFTY | 105 / 167 | 4.87 | 19.5 / 27.0 | -2.79 | -1.41 | -2.79 | 09:17 | 10-13 09:18 (D0) | -1.45 | with cycle stop | missed | with cycle stop (1 later entry) |  |
| 2026-10-15 | SENSEX | 41 / 42 | 1.71 | 6.9 / 9.2 | -0.73 | -0.51 | -0.73 |  | 10-15 09:16 (D0) | -1.46 | with cycle stop | with cycle stop | — |  |
| 2026-10-19 | NIFTY | 328 / 395 | 5.28 | 21.1 / 24.1 | -1.52 | -0.64 | -1.52 |  | 10-19 09:26 (D0) | -1.36 | with cycle stop | missed | — |  |
| 2026-10-22 | SENSEX | 103 / 190 | 4.36 | 17.5 / 27.7 | -3.48 | +0.00 | -2.47 | 12:53 |  | — | — | — | **crossed, no action; trading continues** |  |


## 8. Files

| File | Content |
|---|---|
| `rr_common.py` | Session-aware unit-lot ledger (PR #3 algorithm, own-session minute mapping), P&L engine, client constants |
| `phases.py` | Phases 1–4 and the placebo ladder |
| `run_all.py` | Runs everything (≈ 70 s) and writes all CSVs |
| `tests/test_risk_rules.py` | 12 tests: constants, causality of crossing detection, session mapping, lot / inventory / MTM reconciliation, D0 identities |
| `carry_forward_4pct_tests.csv`, `expiry_day_1pct_tests.csv`, `order_action_matching.csv`, `cycle_level_risk_reconciliation.csv` | Deliverables |
| `results/` | Phase 1 inventory and ownership ambiguity, carry events, placebo ladder, cycle-stop control |

Register: new rows **DAT-10, RSK-07, RSK-08, RSK-09** only; existing rows unchanged.
