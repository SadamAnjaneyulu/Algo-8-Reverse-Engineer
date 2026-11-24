# Late D-1 strike, side and timing rule, and two corrections to the reconstruction-gap diagnosis

*Exploratory work on the real log (post-auction = D0 on or after 3 Aug 2026). No rule was adopted. All scoring is teacher-forced (each decision is judged from the real state before it); cycles are kept whole (leave-one-cycle-out, cycle-cluster bootstrap).*
*Scripts: `src/bl_late_table.py`, `bl_late_rules.py`, `bl_late_trigger.py`, `bl_late_value.py`, `bl_late_audit.py` → `outputs/late/`.*

## Result first
1. **Strike and side of the late sales are already mostly explained** by rules the engine has. The late timing that remains unexplained is small: about **7.7 lots per cycle**.
2. **Two earlier conclusions were wrong, and I withdraw them:**
   * **"The real book is bigger (+16 lots) and further OTM."** This rested on **one cycle**: NIFTY D-1 16 Oct 2026, a 240-lot deep out-of-the-money call ratio, which no other cycle has. Without that cycle the real book is +4 short lots (median +9.5) and **not** further OTM (−0.2 steps).
   * **"Fix A rejected, P&L worse by ₹38k."** **97% of that change is one stop flip** (SENSEX 8 Oct, −₹7.09 lakh). On the other 18 cycles Fix A changes P&L by −₹1.0k on average and ₹0 at the median. Fix A is **unresolved**, not rejected.
3. **On these 19 cycles, nearly every P&L comparison is decided by one or two cycle-stop flips**, each worth ±₹4–7 lakh. That is how we have been overfitting: accepting or rejecting rules on coin-flip stop events. From now on, every P&L check reports the stop flips separately (Section 5).

## 1. The late-order table (`outputs/late/late_sales.csv`)
This table holds every real D-1 short sale from 14:15 to 15:40. Fields:
* timestamp, CE/PE, strike, lots and premium;
* spot, ATM and offset;
* the short and long lots held on each side, and the imbalance;
* the last same-side strike and price, and whether the strike was already held short;
* the 15-minute spot move, new 60-minute highs and lows, and the gap since the previous order.

After the auction: **680 orders across 21 cycles**. Of these, **93% sell a strike that is already held short**, and most are 1 lot.

## 2. Strike rule (exact match; 95% interval from the cycle bootstrap)
| rule | after: exact | after: within 1 step | before: exact |
|---|---|---|---|
| ATM | 0.25 [0.20, 0.31] | 0.84 | 0.25 |
| modal offset (leave-one-cycle-out) | 0.44 | 0.77 | 0.47 |
| **same strike as the last same-side sale** | **0.54 [0.48, 0.59]** | 0.83 | 0.50 |
| **engine rule: premium closest to the last sale, within ±4 strikes** | 0.51 [0.46, 0.56] | 0.83 | 0.46 |
| biggest held short | 0.21 | 0.55 | 0.28 |

The engine's existing ladder rule (premium-matched) is within noise of the best candidate. **No change to the strike rule is supported.**

## 3. Side rule
| rule | after | before |
|---|---|---|
| always the majority side (base rate) | 0.556 | 0.561 |
| **trend: sell CE after a 15-minute fall, PE after a rise** | **0.679 [0.62, 0.74]** | 0.664 |
| sell the side that is already heavier / lighter | 0.58 / 0.43 | 0.51 / 0.49 |
| alternate sides | 0.37 | 0.39 |

The trend rule beats the base rate in both eras by about 0.11. That is the engine's ladder direction: the ladder sells calls into falls and puts into rises. **This is already in the engine.**

## 4. Timing trigger
* **Ladder gate G** (minutes over which a fresh extreme is required; G ∈ {5, 10, 15, 30, 60}, chosen leave-one-cycle-out): F1 is 0.46 vs 0.47 at the current G = 60 after the auction, and 0.41 vs 0.44 before. **No improvement.**
* **Clock:** after 14:45 the late sales follow no clock. The clusters at 14:15, 14:30 and 14:45 are the existing timetable.
* **Attribution of the real late short lots** (±1 minute, 20 cycles after the auction, the 16 Oct outlier excluded). For the timetable and breakouts the match ignores the side, so these shares are upper bounds.

| window | timetable | breakout | ladder | unexplained | no data (15:30–15:40) |
|---|---|---|---|---|---|
| 14:15–14:59 | 153 | 135 | 86 | 23 | – |
| 15:00–15:14 | – | 63 | 39 | 35 | – |
| 15:15–15:29 | – | – | 56 | **80** | – |
| 15:30–15:40 | – | – | – | – | 15 |

Over the whole window, 78% of late lots match an existing rule. Unexplained: **153 lots, 7.7 per cycle**, mostly after 15:15, where the breakout window has ended.

## 5. What the late sales are worth (teacher-forced)
Method: start the D0 simulator from the **real** carried book, then remove the real short-side orders after a cutoff. The difference is the in-simulator value of the real late selling. The full real book reproduces `gap_decomposition.csv` exactly.

| sales removed after | era | mean (₹/cycle) | median | stop flips | mean excluding flips | median excluding flips |
|---|---|---|---|---|---|---|
| 15:15 | after (18) | +15,391 | +1,303 | 0 | +15,391 | +1,303 |
| 15:00 | after | +33,578 | +9,363 | 2 (₹1.25 lakh) | +29,968 | +9,363 |
| 14:15 | after | +64,846 | +721 | 5 (₹9.29 lakh) | +18,299 | −457 |
| 15:15 | before (11) | −2,753 | 0 | 0 | −2,753 | 0 |

* Late selling after 15:00 is worth roughly **₹15–30k per cycle after the auction**, but the medians are only ₹1–9k. A few cycles carry it.
* Before the auction it is worth about zero.

**The overnight-book gap (₹74.9k per cycle, 18 cycles, outlier excluded):** 63% of it (₹8.43 lakh) comes from **2 cycles where the free-run simulator stops and the real book does not** (NIFTY 6 Oct, SENSEX 1 Oct). The other 16 cycles: mean ₹31.5k, median ₹19.8k.

## 6. Interpretation (adversarial)
* **Supported:**
  * The late strike and side choices are the ladder's own rules (premium-matched strike, trend side).
  * The remaining timing gap is about 7.7 lots per cycle, mostly 15:15–15:29.
* **Not supported:** "the real system builds a bigger or further-OTM book". That was one cycle.
* **Could be luck:** most of the P&L gap between the simulator and the real system. Two to five binary stop events decide it. With 18 to 19 cycles no rule can be validated on cycle P&L.
* **Unknown:**
  * the trigger of the unexplained 15:15–15:29 sales;
  * the 15:30–15:40 session (the option cache ends at 15:29);
  * what the 16 Oct call ratio was (an event trade, or a different module).

## 7. Decision and next steps
* **No rule adopted.** Strike and side: keep the engine's. Timing: nothing beat the current rule out-of-fold.
* **Fix A is reopened as unresolved.** Its P&L verdict was one stop flip.
* **New binding reporting rule:** every P&L comparison reports (a) the number of stop flips and their sum, and (b) the mean and median excluding flips. A rule is never accepted or rejected on flips alone.
* Next:
  * (1) extend the option cache to 15:39, so that the 15:30–15:40 session and the post-15:30 lump buys can be simulated;
  * (2) re-score Fix A and a "breakout after 15:15" variant at the decision level, using the flip-separated P&L;
  * (3) keep collecting the real log forward as a clean hold-out. The NO-GO verdict of the pre-paper battery stands.
