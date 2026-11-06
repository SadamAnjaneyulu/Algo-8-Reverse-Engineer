# Algo 8 — Reverse-Engineering Findings (v1)

Source material: `Info.txt` (the only spec) + `Trades_GKOHNP140.csv` (41,421 fills, 2026-06-23 → 2026-10-22, 65 trading days, one client `GKOHNP140`).
All numbers below were produced by code in `analysis/` (run: `python3 analysis/report.py`). Evidence labels: **[OBSERVED]** = measured directly from fills · **[INFERRED]** = pattern fit, not proven · **[UNKNOWN]** = cannot be determined from this data.

> **Hard limit of this dataset:** it contains *fills only*. No spot, no option chain, no IV, no margin, no order-trigger log. Every "rule" below is inferred from what the algo *did*, not from what it *saw*. Underlying spot was reconstructed from put-call parity on same-strike CE/PE fills (`S = K + CE − PE`).

---

## 1. What the file is  [OBSERVED]

| Item | Value |
|---|---|
| Format | Headerless broker order/fill dump, 167 columns, ~120 constant/empty. **One row = one fill** (large orders are filled 1 lot at a time, e.g. 975 qty → 15 rows) |
| Instruments | NIFTY weekly options (NSE, lot 65, expiry Tue) and SENSEX weekly options (BSE, lot 20, expiry Thu) |
| Order type | All `Limit`; entries/exits are *marketable* limits (buy limit ≈ LTP+10–15%, sell limit ≈ LTP−15%) → fills are better than limit. `IOC` for wing legs, `DAY` for body legs |
| Source | `ClientAPI` — fully automated |
| Useful columns | 11 side · 12 underlying · 14 strike · 16 CE/PE · 18 fill price · 33 fill qty · 32 contract text (use this for expiry; col 15/158 are *not* expiry) · 161 fill epoch (IST = +5:30) |

## 2. Weekly rhythm  [OBSERVED]

Each expiry **cycle** = two sessions:

| Session | NIFTY | SENSEX | Role |
|---|---|---|---|
| **D‑1** (BTST day) | Mon | Wed | Build the book all day, carry overnight |
| **D0** (expiry day) | Tue | Thu | Unwind carry, run a fresh intraday book, flatten ≈ **15:14** |

One underlying and one expiry per day; NIFTY and SENSEX alternate so the account always has something live. After a holiday shift D‑1 can be 3 calendar days (10/16 Fri → 10/19 Mon).

## 3. Core structure: hedged short straddle ("iron-fly in 1-lot slices")  [OBSERVED + INFERRED]

Per **slot** the algo:
1. **Sells 1 ATM CE + 1 ATM PE** (same strike, nearest listed strike to spot; NIFTY step 50, SENSEX step 100).
2. **Buys 1 CE wing + 1 PE wing**, one-for-one with the shorts.

Evidence it is one-for-one: on the D‑1 evening (before the lump below) `long CE lots = short CE lots` **and** `long PE lots = short PE lots` exactly on 16 of 31 days, within ±3 lots on 24 of 31; the rest drift (max |imbalance| = 123 lots on 10/16, a 3-day carry). So the hedge is one-for-one *by design*, with execution/adjustment drift.

**Wing selection is premium-based, not distance-based** [OBSERVED]: wing price ÷ straddle premium has median ≈ **1.15–1.27 %** (IQR ≈ 1.0–1.4 %) for both NIFTY and SENSEX, while wing distance varies (CE ≈ 2.4–2.5 % OTM, PE ≈ 2.7–3.8 % OTM — PE wings sit further out for the same price, consistent with skew). The exact target ratio/rounding rule is **[UNKNOWN]** (1.0 %? 1.2 %? nearest-strike?).

Exception: the **first slot of D‑1 (09:16)** uses much cheaper, far wings (~0.3 % of straddle; e.g. NIFTY CE 26250 / PE 22350 at ₹0.4–0.6). Slot ≥ 2 uses the ~1.2 % wings.

## 4. The clock and the lot ladder  [OBSERVED]

* **15‑minute grid anchored at 09:16** (`:16 :31 :46 :01`), each slot spilling 1–2 min as orders are sliced per second.
* Lots-per-leg per slot is a **fixed, day-independent ladder** (sold ATM lots per leg, D‑1, slots from 09:16):

  `3, 2, 3, 1, 3, 1, 2, 2, 1, 1, 3, 1, 0, 2, 0, 0, 1 …`

  This pattern repeats almost identically on all 31 D‑1 days → the entry schedule is **hard-coded / time-driven, not signal-driven**. Deviations from the ladder (extra lots, spikes of 5–22) are *adjustment/re-entry* activity layered on top.
* D0 uses the same 15-min clock with a different ladder (CE+PE lots/slot ≈ 8, 9, 3, 8, 6, 4, 5, 4 …) on top of unwinding the carried book.

## 5. Re-centering / adjustments  [OBSERVED, trigger INFERRED]

Straddle strikes track spot: e.g. SENSEX 7/8 shorts start at 77 700 and step down to 76 200 as spot fell ~1.7 %. Clusters of `Buy ATM + Sell FAR` (closing a straddle and its wings, then re-selling at the new ATM) occur at 12:31/12:47, 13:41–13:47, 14:46, 14:54–55, 15:05, 15:15. The *trigger* (spot-move threshold? leg-premium SL? time?) is **[UNKNOWN]**: FIFO leg-matching gives a smooth continuum of exit/entry price ratios (0.5×→5×) with no clustering at a round SL multiple, so a simple "+X % per leg" stop is *not* supported by the data.

## 6. The overnight "lump" hedge (BTST carry)  [OBSERVED]

Near the end of every D‑1 the algo makes **one large single-strike purchase** of an OTM option on the side that has more short lots:

* Side: the side with more short lots (≈ 29/31 days).
* Strike: ≈ 1.1–2.5 % OTM, premium ≈ ₹3–9 (NIFTY) / ₹12–22 (SENSEX).
* Size: 2 – 153 lots, e.g. 7/6 NIFTY: **62 × PE 24100 @5.51**; 7/8 SENSEX: **54 × CE 78200 @15.0**.
* Timing: ≈ 15:06–15:14 until Aug 12, then **15:23–15:38** from Aug 12 onward (a regime/timestamp change — **[UNKNOWN]** whether the algo or the venue clock shifted).
* Effect: caps the heavy-side tail. Expiry-payoff of the carried book without the lump loses ≈ ₹41.5 L at a −4 % move (intrinsic-at-expiry model) on 7/6; with the lump ₹13.5 L. The sizing rule (what number of lots?) is **[UNKNOWN]** — it is *not* a constant rupee cost (₹6 K–₹87 K), not equal to the CE/PE imbalance, and not a constant fraction of short lots (0.04–0.85).

The carried book on a typical D‑1 close: ~100 short ATM lots + ~100 wing lots + the lump. On D0 the exact inverse trades happen (net per instrument over D‑1+D0 = 0; positions are always squared off, never left to settle).

## 7. Stop-losses  [partly OBSERVED]

Info.txt: *"carry-forward SL of 4 % on positions carried forward to expiry, and 1 % on the entire capital on expiry day"*, capital ₹2 Cr.

What the fills show:
* **11 of 30 clean cycles were whole-book stop-outs**: everything is liquidated in seconds (e.g. 7/14: 09:15:00 → 09:16:12, buy-back of shorts first with `DAY` limits, then wings sold `IOC`). Eight of the 11 trigger **within seconds–minutes of the 09:15 open** after an overnight gap (|gap| ≈ 0.3–0.7 % by my spot proxy, both directions); three triggered intraday (6/30 14:25, 9/22 14:14, 7/16 11:01). A 12th stop occurred on a D‑1 itself (8/31 14:46, gross −₹145 K; D0 shows no trades afterward) and is outside the 30-cycle count.
* Realised **gross cycle P&L at the stop clusters tightly at −₹139 K … −₹153 K** (9 of 11), plus two gap-through outliers (−₹190 K, −₹222 K).
* This is **≈ 0.70–0.77 % of ₹2 Cr, not 1 %**. Statutory costs are only ₹1.2–3.3 K per cycle so costs do not explain the gap. Candidate explanations (all **[UNKNOWN]**): SL base is *used margin* (~₹1.4–1.5 Cr), not the full ₹2 Cr; SL evaluated on a different MTM (e.g. vs previous close); the "4 %" is on something other than spot/premium. I could **not** reconcile the 4 % with any measurable quantity (gap sizes are 0.6–0.7 %, carried premium is small).

## 8. P&L (fills only, **gross of brokerage**)  [OBSERVED]

| Slice | n cycles | Total | Mean | Win % | Stops | Worst | Max DD (cycle seq) |
|---|---:|---:|---:|---:|---:|---:|---:|
| All clean D‑1+D0 | 30 | **+₹15.53 L** | ₹51.8 K | 47 % | 11 | −₹222 K | −₹682 K |
| NIFTY | 13 | +₹2.78 L | ₹21.4 K | 38 % | 6 | −₹222 K | −₹338 K |
| SENSEX | 17 | +₹12.74 L | ₹75.0 K | 53 % | 5 | −₹190 K | −₹344 K |

* Non-stop cycles: mean **+₹172 K**, 74 % win. Stop cycles: mean **−₹157 K**. The profile is classic *short-vol*: many modest wins, a capped (by design) but frequent loss.
* 7.8 % gross on ₹2 Cr over ~4 months, **t-stat of cycle mean = 1.39 → not statistically distinguishable from zero** at n = 30.
* **Brokerage is the elephant**: 37 258 orders. At a flat ₹20/order that is ≈ ₹7.5 L — roughly **half** the gross profit. Slippage is also not modelled (fills are the real fills, so it is already inside the P&L, but not the exchange/broker fees).
* Data gaps: no rows for 8/10, 9/1, 9/14, 9/29 (and 9/29's carried book is open in the file). Cycles 6/23, 8/11, 9/15 are D0-only; 9/1 is D‑1-only (stopped). All excluded from the 30-cycle stats.

## 9. What is cracked vs not

| Component | Status |
|---|---|
| Underlying/expiry/day mapping | **Cracked** |
| Strategy family (hedged ATM short straddle, 1-lot slices) | **Cracked** |
| 15-min clock @09:16, fixed lot ladder | **Cracked** (ladder values extracted; exact tail after slot ~16 needs per-regime table) |
| Wing = ~1.2 % of straddle premium | **Strong fit**, exact rule open |
| EOD lump hedge: side, ~1–2.5 % OTM, one strike | **Cracked qualitatively**; lot-sizing & strike rule open |
| Re-center trigger | Open |
| Stop-loss (4 % carry / 1 % capital) arithmetic | **Does not reconcile** — open |
| D0 final flatten ≈ 15:14 | **Cracked** |
| Edge significance | **Not established** (n = 30, t = 1.4, fees ≈ half of gross) |

## 10. Decisions needed from you (blocking, not guessed)

1. **Data:** can you provide NIFTY/SENSEX 1-min spot + option-chain (or at least 1-min spot and Black-Scholes IV) for 2026-06-23 → 2026-10-22? Without it, the re-center trigger, wing rule and SL arithmetic cannot be pinned down — only fitted.
2. **Goal of "crack":** (A) exact replica that reproduces these fills, (B) a re-implementation of the *idea* with my own validated rules, or (C) estimate whether the edge is real? Each needs different next steps.
3. **Costs:** broker brokerage per order (flat ₹20? zero?) so net P&L can be stated.
4. **SL:** do you know whether "1 % of capital" is measured on ₹2 Cr, on used margin, or as MTM vs previous close? And what the "4 %" is a percentage *of*?
5. **Timestamp regime change from 12 Aug** (lump at 15:23–15:38, trades stamped after 15:30): was the algo changed that day, or did the broker/venue clock change?
