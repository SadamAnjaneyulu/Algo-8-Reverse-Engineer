# Buyback and Replacement Analysis (Phase B, discovery cycles only)

**Result:** D0 buy-backs have identifiable **timing structure** (Clock-B minute, rising late-day hazard, price stops on a minority) but **no deterministic trigger was recovered**. Replacements exist as an **above-chance association only for specific subtypes** (Clock-B-minute buy-backs: 58 % followed within 60 s vs 27 % by chance; salvage +18 points; price-stop-like +8 points), and what follows is usually the **same lots (92 %) on the same right at a nearby strike (only 27 % exactly nearest to ATM)**. The replace-or-not decision is **Unknown**. All statistics on the 25 discovery cycles (22 with a known carry-in book); the holdout was not opened (guard in `d0common.load_events`). Code executed: `b_replacement.py`, `build_snapshots.py`, `c_clockb_discovery.py`, `build_final_snapshot.py`.

## 1. Correction of the previous headline ("60 % of D0 sales are replacements")
Share of D0 sold lots whose **previous same-right buy-back** is within *W* seconds, observed vs a null that shifts every buy-back by ±20–120 minutes inside the session (200 draws):

| W (s) | Observed | Null mean (p95) | Ratio |
|---:|---:|---:|---:|
| 30 | 33.2 % | 16.8 % (18.9 %) | 1.98 |
| 60 | **42.8 %** | 28.9 % (31.9 %) | **1.48** |
| 120 | 51.7 % | 45.4 % (48.3 %) | 1.14 |
| 180 | 54.7 % | 55.8 % (58.8 %) | 0.98 |
| 300 | 59.5 % | 68.4 % (71.4 %) | 0.87 |

Beyond ~2 minutes there is no excess at all. The "60 %" in the previous report counted sales in the same *or previous minute* (up to ~120 s) against any buy-back; at that horizon about 45 % is the chance level. **Only ≈ 14 percentage points of sold lots (≈ ⅓ of those within 60 s) are attributable above chance to a preceding buy-back.** Status: association **Established**, size **corrected**.

## 2. Which buy-backs are followed by a sale, beyond chance? (`b3_followup_excess_over_null.csv`)
P(same-right sale within W s of the buy-back) observed vs a null that places the same number of buy-backs at random times in the D0 session:

| Subtype | n | W=60: observed | null | **excess** |
|---|---:|---:|---:|---:|
| Late (≥ 15:10) | 1,534 | 14.8 % | 25.9 % | **−11.1 pts** (no replacement; flatten) |
| Salvage (≤ ₹1 or ≤ 5 % entry) | 379 | 48.3 % | 30.1 % | +18.2 pts |
| Price ≥ 1.55 × cheapest | 2,835 | 32.1 % | 24.1 % | +8.0 pts |
| Clock-B tick minute | 264 | 58.0 % | 26.8 % | **+31.1 pts** (W=30: −1.4: the sale comes after the minute rolls) |
| Other | 3,281 | 40.8 % | 27.9 % | +13.0 pts |

**What follows** (buy-backs with a same-right sale ≤ 60 s, n = 2,904): sold lots = bought lots in **92.2 %**; strike exactly nearest to ATM (previous-minute spot) 27.5 %, within one step 44.1 %; delay quantiles 10/25/50/75/90 % = 2/11/44/88/131 s; ratio follow-lots/bought-lots median 1.0 (mean 1.67). **Same contract in only 2–13 %** of followed cases by subtype.

## 3. Clock-B ticks (minute-of-hour 14, 09:29–14:59; 460 discovery ticks, 37 % have ≥ 1 body buy-back within 120 s)
**Tick acts** (AUC): total short lots 0.72, wing lots 0.69, CE/PE skew 0.66, number of contracts 0.65, unrealised P&L 0.60, absolute spot move 0.53, ITM share 0.52, time left 0.27 (i.e. action rises as expiry nears). The best single threshold (total short lots ≥ 134) reaches F1 0.62 (precision 0.47, recall 0.91) on discovery — but see the holdout: this scale-dependent threshold **fails** when the carried book is smaller (holdout mean 75 lots vs 134), indicating the real trigger is not an absolute lot count.
**Which contract** (single-criterion hit@1 on 169 acting ticks): most lots **0.48**, largest gamma proxy 0.41, worst unrealised P&L 0.29, highest price/cheapest 0.28, **random 0.27**, largest |offset| 0.15, highest premium 0.08, most ITM 0.08. Bought contracts have more lots (22.7 vs 13.2) and lower prices (₹65 vs ₹97) than other candidates. The typical action is **1 lot** (median 1, 75th pct 3).

## 4. Price-stop-like buy-backs on D0
*(The slot-level exit-rate tables in this section are the Phase-4 descriptive tables, pooled over all 35 cycles; no rule was fitted to them. Discovery-only counts are given where stated.)*
Buy-back rate per 15-minute slot by price ÷ cheapest open entry (D0): 7 % (≤ 0.8), 12 % (1.0–1.2), 19–23 % (1.2–1.7), 20 % (1.7–2.0), 15 % (2–3), 10 % (> 3). There is no step at 1.55–1.7 as on D-1 (EXT-05). 2,835 discovery buy-backs satisfy price ≥ 1.55 × cheapest entry but 51 % of D-1-like exits occur below 1.2×; the stop explains a minority at best.

## 5. Final-hour behaviour
* Of body shorts open at 15:10, held to settlement: 0.05–0.25: 22 %; 0.25–0.5: 47 %; 0.5–1: 4 %; 2–5: 60 %; > 20: 0.3 % — **non-monotonic in price**, so "hold the cheap ones" is not the rule (`build_final_snapshot.py`). Settled body lots are worthless at expiry in 98 % of cases. Which lots are left is **Unknown**.

## 6. Candidate mechanisms tested (association ≠ trigger)

| Candidate trigger | Supporting | Counter-examples | Verdict |
|---|---|---|---|
| Clock-B timing (minute 14) | 17.3 % of buy-back lots vs 6.7 % uniform; 3.4× for non-stop-like | 37 % of ticks act; 63 % do not | Timing **Strongly supported**; acting **Unknown** |
| Price ≥ k × entry | exit rate rises on D-1 | flat on D0; 51 % of exits < 1.2× | Weak on D0 |
| Book size / scale | tick-acts AUC 0.72; contract choice "most lots" 0.48 | threshold does not transfer to holdout | Proxy, not trigger |
| ATM migration | — | atm-changed-in-prior-minute 15.7 % (off-schedule) vs 12.5 % null | Not supported |
| Time to expiry | action rises later in the day (AUC 0.27 for time left) | — | Supported as modulator |
| Premium threshold / salvage | salvage buy-backs replaced +18 pts | no premium level separates held lots | Partial |
| Replace-or-not | Clock-B-minute +31 pts | late −11 pts; other subtypes +8…+18 pts | **Unknown** |

## 7. Answers to the research questions
| # | Question | Answer | Status |
|---|---|---|---|
| 1 | When does Algo 8 initiate a D0 short? | Grid-A windows (first 3 min of :01/:16/:31/:46) while the book is active; off-schedule sales at any minute; some following buy-backs | Timing partly **Strongly supported** |
| 2 | Why that strike? | Nearest to previous-minute ATM 57 % (scheduled), 41 % (off-schedule), 31 % (replacement); within ±1 step 78 % / 67 % / 50 % | Tendency |
| 3 | CE vs PE? | Same right as the bought-back lot for followed buy-backs; scheduled slots sell both (equal in 53 % of slots) | Partly |
| 4 | Quantity? | Scheduled: depends on the slot (R² 0.26 slot vs 0.02 own-side book); replacements: same lots as bought (92 %) | Partly |
| 5 | What causes a buy-back? | Clock-B tick minute (timing), late-day clearance; price ≥ 1.55× only a minority | **Unknown** (trigger) |
| 6–8 | Replace? different strike? no replacement? | Replaced mostly at another strike (same contract ≤ 13 %); late buy-backs not replaced; otherwise unpredictable | **Unknown** |
| 9 | Why within a minute? | Median delay 44 s; Clock-B pairs straddle the minute boundary | Observed |
| 10 | Timing of off-schedule sales? | No ATM-migration or spot-move relation; no clock found beyond the grid | **Unknown** |
| 11 | Replacement wings | 41 % of replacement sales paired with a wing (0.47 wing lots per lot) priced ≈ 4 % of the body, vs 63 % / 0.9 and 2.7–2.9 % for scheduled/off-schedule | Observed |
| 12 | Response to prices/exposure | Action intensity rises with book size and nearness to expiry; no price/exposure trigger identified | **Unknown** |
