# What makes Algo 8 sell on D-1: the 15-minute clock vs single-leg sales

*In-sample, observational (32 cycles with a D-1 log, 4,408 body short-sale orders, 4,671 lots). Observed / Inferred / Unresolved tags. Scripts `src/bl_trigger1-3.py`, `bl_trigger_fig.py`; figure `figures/bl_trigger_NIFTY_2026-06-30.png`.*

## 1. Answer in one view

| | Paired straddle sales (CE + PE together) | Single-leg sales (CE only or PE only) |
|---|---|---|
| Share of D-1 sold lots | 64.9 % | **35.1 %** (CE 40.3 % of CE lots, PE 28.4 %) |
| Time structure | **clock**: 15-minute period concentration R = 0.74; 47.2 % of paired lots in the slot minutes (09:16 + 15 k) | **none**: R = 0.11 (15 min), 0.06 (1 min); seconds-of-minute flat |
| What decides it | the clock (+ a per-slot lot ladder) | **an event**: the market has moved *away from that right's existing shorts* (book in profit) — a tendency, no exact threshold found |
| Strike | ATM of the previous minute (88.9 %) | premium of the previous sale on that right (47.7 % exact) rather than ATM (19.6 %) |

## 2. The 15-minute clock (Observed)

* Paired sales sit in the slot minute: share of paired **orders** by minute of the 15-minute cycle (0 = slot minute 09:16 + 15 k): minute 0 48.5 %, minute 14 (the minute before) 20.6 %, minute 1 9.5 %, all other 12 minutes 21.5 %. Within the slot minute 75 % of paired orders fill in seconds 0–15 and 36 % of the minute-before orders fill at seconds 55–59 (i.e. the order fires about at the minute mark, a few seconds early).
* **Strike:** nearest strike to the previous completed minute's spot close (Body lifecycle study: 84 % exact on slot-minute sells).
* **Quantity:** a fixed lots-per-right ladder by slot index (table in the Body lifecycle report §3B; 3 lots per right in the 09:16 slot, then mostly 1–2, differing somewhat between NIFTY and SENSEX; stable across cycles: 73.1 % of 872 slot-rights equal the modal ladder). The deviation from the ladder is **not** explained by state: Spearman of the residual with shorts held before the slot 0.07, with lots bought back in the previous 15 minutes -0.13 (a refill rule would give a positive value), with the 15-minute spot move 0.02. **Unresolved:** where the ladder comes from.

## 3. Single-leg sales (the calls or puts that appear alone)

**Not time-based (Observed).** Their times show no period (R ≤ 0.11 for periods 30 s – 15 min, vs 0.74 for the paired sales) and the second-of-minute is flat. They come in short runs: median gap to the previous sale on the same right 22 s.

**What precedes them (Observed, AUC test).** I defined an *episode start* as the first single-leg sale on a right with none in the previous 5 minutes (376 starts in 32 cycles) and compared the minute before it with all other minutes of the same cycle-right (19,575 minutes). Features use only data available before the minute; the list was fixed in advance (Holm over 13 features, cluster bootstrap over cycles). AUC 0.5 = no association; < 0.5 = lower at episode starts.

| feature | AUC (95 % CI) | holm_p |
|---|---|---|
| adv1 | 0.301 (0.279–0.322) | 0.032 |
| adv3 | 0.277 (0.261–0.292) | 0.032 |
| adv5 | 0.272 (0.255–0.288) | 0.032 |
| adv15 | 0.239 (0.220–0.259) | 0.032 |
| abs5 | 0.552 (0.528–0.573) | 0.032 |
| abs15 | 0.583 (0.553–0.611) | 0.032 |
| dev_book | 0.283 (0.260–0.306) | 0.032 |
| ratio_book | 0.274 (0.250–0.297) | 0.032 |
| ratio_last | 0.328 (0.306–0.348) | 0.032 |
| imb | 0.587 (0.557–0.617) | 0.032 |
| S_right | 0.590 (0.568–0.615) | 0.032 |
| tsl | 0.519 (0.495–0.542) | 0.21 |
| tslot | 0.511 (0.478–0.543) | 0.46 |

(`adv k` = spot move over the last k minutes in steps, **positive = adverse to a short of that right** — up for calls, down for puts; `dev_book` = spot minus the weighted strike of the right's shorts, + = shorts ITM; `ratio_book` = current price ÷ average entry price of the right's short book; `ratio_last` = current price of the last-sold contract ÷ its sale price; `imb` = shorts of this right minus the other right.)

Reading: single-leg sales start when the market has just moved **in favour of the right's existing shorts** (adv AUC 0.24–0.30), the shorts are OTM-ward of the spot (`dev_book` 0.28) and the book is **in profit** (`ratio_book` 0.27, `ratio_last` 0.33). Hazard per minute:

| book price ratio | minutes | episode starts | rate per 1000 min | lift vs base |
|---|---|---|---|---|
| (0.0, 0.7] | 1786 | 75 | 42.0 | 2.19 |
| (0.7, 0.8] | 2027 | 92 | 45.4 | 2.36 |
| (0.8, 0.9] | 3333 | 109 | 32.7 | 1.7 |
| (0.9, 1.0] | 3800 | 56 | 14.7 | 0.77 |
| (1.0, 1.1] | 3157 | 20 | 6.3 | 0.33 |
| (1.1, 10.0] | 5472 | 24 | 4.4 | 0.23 |

| adverse spot move, 5 min (steps) | minutes | episode starts | rate per 1000 min | lift vs base |
|---|---|---|---|---|
| (-10.0, -0.5] | 1050 | 56 | 53.3 | 2.78 |
| (-0.5, -0.25] | 1965 | 79 | 40.2 | 2.09 |
| (-0.25, 0.0] | 6238 | 173 | 27.7 | 1.44 |
| (0.0, 0.25] | 6537 | 50 | 7.6 | 0.4 |
| (0.25, 0.5] | 2331 | 10 | 4.3 | 0.22 |
| (0.5, 10.0] | 1414 | 4 | 2.8 | 0.15 |

The rate is about 2–2.4× the base rate (19.2 per 1,000 minutes) when the book price ratio is ≤ 0.9 and about 0.2–0.3× when the book is losing (> 1.1); adverse moves almost never start an episode. **There is no sharp threshold** (rule "book ratio ≤ 0.85" flags 27 % of minutes and catches 60 % of starts; "last-sold ratio ≤ 0.8" flags 1.5 % and catches 6 %). **Inferred:** the single legs are *adds on the profitable side* after premium has decayed on that right; the exact trigger level is **Unresolved**.

**Which strike (Inferred).** Not the ATM (hit 19.6 %): the sale price is close to the previous sale's price on that right (median ratio 1.0), so after a favourable move the strike moves one step further ITM. Rule "strike whose current price is nearest to the previous sale price on that right":

| group | n | ATM_exact | ATM_pm1 | PREVPX_exact | PREVPX_pm1 | AVGPX_exact | PREVPX_null_exact |
|---|---|---|---|---|---|---|---|
| single-leg (all) | 1376 | 19.6 % | 84.9 % | 47.7 % | 84.4 % | 32.8 % | 30.7 % |
| single-leg, other class | 1070 | 20.8 % | 86.0 % | 50.2 % | 85.7 % | 34.5 % | 33.0 % |
| paired slot-minute (comparison) | 1369 | 88.9 % | 98.2 % | 68.4 % | 96.3 % | 68.4 % | 40.8 % |

The premium-continuity rule beats the ATM rule for single legs (47.7 % vs 19.6 %) and the shuffled-price null (30.7 %), while paired slot-minute sales follow the ATM (88.9 %). The null is high because prices barely change within minutes, so this is **PARTIALLY SUPPORTED**, not a recovered rule.

## 4. Exceptions and what remains unresolved

* Not every single-leg sale follows a favourable move: 12 % of episode starts have a losing book (e.g. the NIFTY 2026-06-30 burst at 14:55, where puts were sold with the put book at 1.2–1.35× entry — this is part of the heavy end-of-day selling).
* No explicit trigger level, no per-lot timer, and no link to buy-backs (only 13.5 % of single-leg sales follow a body buy-back on the same right within the previous 15 minutes) was found. **Unresolved:** exact threshold, the quantity per episode, and why the end-of-day bursts differ.
* Pairing is defined as a sale on the other right at the same strike within 3 s; a looser definition would move a few lots between the two groups but not change the clock/non-clock split.
