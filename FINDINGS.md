# Algo 8 — Reverse-Engineering Findings (v2, deep pass)

Sources: `Info.txt` + `Trades_GKOHNP140.csv` (41,421 fills, 2026-06-23 → 2026-10-22, 65 days, client `GKOHNP140`).
Reproduce everything: `python3 analysis/report.py` · `python3 analysis/modules.py` · `python3 analysis/ladder.py`.
Labels: **[OBSERVED]** measured from fills · **[INFERRED]** pattern fit · **[RULED OUT]** tested and rejected · **[UNKNOWN]**.

> v1 was a structural summary. v2 uses three signals v1 ignored: the **order tag** (raw col 163), the **limit-price band** (which leaks the live quote at decision time), and second-level timing. Several v1 statements were wrong and are corrected in §9.

---

## 1. The algo is a set of tagged modules  [OBSERVED]

Raw column 163 is the client order tag. It names the module that sent the order:

| Tag | Module | Order type | Fills / lots | Meaning |
|---|---|---|---|---|
| *numeric* | **BODY** | DAY limit | 26,954 / 31,874 | Short ATM straddle legs (sells) and their buy-backs |
| `h_…` | **WING HEDGE** | IOC limit | 13,181 / 25,627 | Long OTM wings bought with each body sell; sold when body is closed |
| `v_…` | **LUMP HEDGE** | IOC limit | 515 / 2,441 | Overnight single-strike tail hedge (bought D‑1 ≈15:10, salvaged D0) |
| `s_…` | **STOP-LOSS** | DAY+IOC | 763 / 3,678 | Whole-cycle liquidation. Present on exactly the 12 stop-out days |
| `m_…` | manual | IOC | 8 / 32 | Human intervention, one day only (2026‑07‑07 NIFTY) |

## 2. Order pricing: the algo's quote is recoverable  [OBSERVED]

Every algo order is a **marketable limit at ±15 % of LTP**, rounded to the 0.05 tick:

* BUY limit = LTP × **1.15** (median limit/fill = 1.146 body, 1.157 wing/stop)
* SELL limit = LTP × **0.85** (median 0.852 body, 0.842–0.843 wing/stop)
* `v_` BUY limit = LTP × **≈1.03–1.04** (tighter; it is a patient buyer), `v_` SELL ×0.85.

So `L = limit/1.15` (buys) or `limit/0.85` (sells) is the live quote the algo saw at decision time (±tick). Fills happen at the actual book, better than the limit. This turns the fill log into a sparse tick feed and is what made §4 solvable.

## 3. Weekly rhythm and the clock  [OBSERVED]

* **Cycle = D‑1 (BTST day) + D0 (expiry)**. NIFTY Mon/Tue, SENSEX Wed/Thu. Always one underlying per day.
* **15-minute grid at 09:16, 09:31, 09:46, 10:01 …** Orders are decided in the first ~3 min of each slot (second-of-minute clusters at :00–:02, :09–:11, :30–:32 → the engine polls roughly every 10 s).
* **Hard-coded lot ladder** (body sells per leg, identical for NIFTY and SENSEX, all months). Modal value, with share of days exactly equal to mode:

| Slot | 09:16 | 09:31 | 09:46 | 10:01 | 10:16 | 10:31 | 10:46 | 11:01 | 11:16 | 11:31 | 11:46 | 12:01 | 12:16 | 12:31 | 12:46 | 13:01 | 13:16 | 13:31+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **D‑1** CE/PE lots | 3 (88 %) | 2 | 3 | 1 | 2–3 | 1 | 2 (91 %) | 2 | 1 | 1 | 2–3 | 1 | 0 | 2 | 0 | 0 | 1 / 0 | 0 |
| **D0** CE/PE lots | 10 / 7 | 0–4 | 4 | 0–1 | 4 | 3 | 2 | 3 / 2 | 2 | 2 | 3 | 1 / 0 | 0 | 4 | 2 | 3 | 1 | 3,0,2,0,0… |

  Hit-rates 28–100 % per slot: the ladder is the baseline; off-ladder lots are event-driven additions (§5). D0 is a *different* ladder, not a scaled D‑1.
* D0 forced flatten ≈ **15:14** (1,259 + 1,224 lots at 15:14 across D0 days).

## 4. STOP-LOSS module: cracked numerically  [OBSERVED]

Reconstructed the cycle's mark-to-market **at the instant the first `s_` order fires**, marking every open instrument at its LTP taken from that order's limit:

| Date | Und | Trigger | Short lots | **MTM at trigger** | Final cycle P&L |
|---|---|---|---:|---:|---:|
| 06‑30 | NIFTY | 14:25:17 | 145 | −152,326 | −153,392 |
| 07‑14 | NIFTY | 09:15:19 | 56 | −137,178 | −142,889 |
| 08‑31 | NIFTY | 14:46:28 | 71 | −144,360 | −144,833 |
| 09‑22 | NIFTY | 14:14:30 | 209 | −144,105 | −146,237 |
| 10‑13 | NIFTY | 09:18:03 | 104 | −145,339 | −139,347 |
| 10‑19 | NIFTY | 09:26:21 | 120 | −141,418 | −144,684 |
| 07‑16 | SENSEX | 11:00:52 | 96 | −142,497 | −141,524 |
| 08‑06 | SENSEX | 09:24:39 | 65 | −142,262 | −140,045 |
| 09‑24 | SENSEX | 09:15:12 | 62 | −157,754 | −152,852 |
| 10‑15 | SENSEX | 09:16:31 | 60 | −134,256 | −149,885 |
| *08‑18* | NIFTY | 09:15:12 | 61 | *−213,587* | *−222,118* (gap-through) |
| *08‑20* | SENSEX | 09:15:13 | 45 | *−252,607* | *−189,732* (gap-through) |

**Findings**
1. **The stop base is the whole-cycle (D‑1 + D0 cumulative) MTM of body + hedges at LTP**, not day P&L. Cycle-cumulative: CV 4.7 % across the 10 non-gap stops. Day-only vs previous close: ±40 % scatter. Body-only (hedges ignored): CV 19.7 %. Band-marked (shorts at LTP×1.15): SD 26 K vs 6.8 K.
2. **Threshold ≈ −₹1.44 L** (mean −144,150, SD 6,779, range −134 K … −158 K; scatter is consistent with the ±tick/±1 % error of L). It is **size-independent**: short lots ranged 56 → 209 yet the threshold did not move, so it is a fixed rupee amount, not a % of margin or of premium.
3. **It applies on D‑1 as well as D0** (08‑31 stopped on a D‑1 at −144,360; no D0 trades followed). Info.txt's "4 % carry / 1 % on expiry day" is **not reproduced**: there is one empirical number, ≈ 0.72 % of ₹2 Cr.
4. **Action:** everything is closed within 3 s – 5 min (body buy-backs `DAY`, wings/lump `IOC`), then **no new entries that cycle**.
5. Two cycles gapped through the line at the 09:15 print (−213 K, −253 K MTM at the first tick) — the loss limit is not hard.

Open: what the −1.44 L is derived from (e.g. 1 % of ₹2 Cr less a cost reserve? a stored constant?). **[UNKNOWN]** — fills cannot tell.

## 5. BODY module  [OBSERVED / INFERRED]

* Each slot **sells 1 ATM CE + 1 ATM PE at the same strike** per ladder lot and the wing module buys one wing per sold lot. (Pre-lump D‑1 book: long CE = short CE **and** long PE = short PE exactly on 16/31 days, within ±3 lots on 24/31.)
* **On D‑1 the book is an accumulating ladder, not a re-centered position.** Example 7/6 NIFTY: strikes sold 24350 → 24400 → 24450 → 24500 as spot drifted 24325 → 24440; old strikes are kept. Only 1,326 body lots are bought back on D‑1 across all 31 days, and **every D‑1 exit is a loser** (median exit/entry 1.38, −₹2.28 M total), i.e. D‑1 buy-backs are loss-cuts, never profit-takes.
* Strike is **not** reliably the nearest-to-spot. Over 916 grid slots, the modal sold strike equals the nearest strike (by parity-derived spot) in **61.5 %**; (S−K)/step has SD ≈ 0.7 with tails to ±1.5 steps (≈ 10 % of slots are > 1 step away). Part of that spread is spot-proxy error (≈ 10–25 pts), but not 40 %. A sticky-strike (hysteresis) rule is **not** supported cleanly: strikes that stay have |S−K_prev| median 0.33 step (p95 1.09), strikes that switch have median 0.83 step (p5 0.12), the distributions overlap heavily. **[UNKNOWN]** rule (different reference price — futures/prev-close? straddle-balance? config offset?).
* Carried D‑1 shorts (2,323 lots) are unwound **gradually through D0** (exit/entry ratio falls 1.5 at 09:15 → 0.02 by 15:00), 425 lots at the 09:15 open (these are the stops, −₹977 K) and the rest as decay.
* Wing selection is premium-based: wing price ≈ **1.0–1.4 % of the straddle premium** (median ≈ 1.2 %); first D‑1 slot (09:16) uses much cheaper far wings (~0.3 %).

## 6. LUMP hedge (`v_`)  [OBSERVED]

* **Buy:** one OTM strike, one ~3 % limit band, ≈15:06–15:14 (until Aug‑12) then ≈15:23–15:38; on the heavier short side (29/31 days); 2–153 lots; price ₹3–9 NIFTY / ₹12–22 SENSEX.
* **Sell (D0):** not a signal. It is a **salvage dribble**: IOC sells of 1–8 lots at 0.03–0.25× entry (typically 14:00–15:15), plus a lump liquidation inside stop events (e.g. 7/14: 15 lots at ₹3.50 in the first second). Sizing rule for the buy: **[UNKNOWN]** (not constant ₹, not CE/PE imbalance, not constant % of short lots).

## 7. What I tested and RULED OUT  [RULED OUT]

| Hypothesis | Test | Result |
|---|---|---|
| Per-leg stop at fixed premium multiple (e.g. +50 %, +100 %) | exit/entry ratios, FIFO and running-average per strike, using LTP at decision time | Continuous 0.5×–2× spread; no spike |
| Exit when spot moves X % from entry spot | adverse move at exit | Smooth 0.1 %–0.75 %, no threshold |
| Exit when spot is X strike-steps from the sold strike | (spot − strike)/step at exit | Exits from −10 to +10 steps, including dead ATM |
| Fixed holding time (15 min multiples) | 9,127 D0 lots | Flat distribution, no peaks |
| D0 profit-target fraction / absolute price | ratio × time, absolute L × time | Mixed 0.05×–2.5×, no cluster |
| Stop gap vs −₹2 L explained by costs | STT+exchange charges per cycle | ₹1.2–3.3 K, far too small |
| Stop base = day P&L vs prior close | day MTM − carried value at prior close | ±40 % scatter |

**Not ruled out (competing hypothesis):** the stop is really −₹2 L (= 1 % × ₹2 Cr per Info.txt) measured on *band-marked* P&L (shorts at LTP×1.15, longs at LTP×0.85). That version gives mean −207 K (≈ −2 L!) but SD 26.5 K vs 6.8 K for plain LTP-MTM. Dispersion favours the LTP-MTM / −1.44 L reading, but the −207 K mean coincidence is notable; n = 10 cannot separate them with certainty and a quote feed could.

## 8. Performance (fills only, gross of brokerage)  [OBSERVED]

| Slice | Cycles | Total | Mean | Win % | Stops | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| All clean D‑1+D0 | 30 | **+₹15.53 L** | ₹51.8 K | 47 % | 11 | −₹6.82 L |
| NIFTY | 13 | +₹2.78 L | ₹21.4 K | 38 % | 6 | −₹3.38 L |
| SENSEX | 17 | +₹12.74 L | ₹75.0 K | 53 % | 5 | −₹3.44 L |

Non-stop mean +₹172 K (74 % win); stops mean −₹157 K. t-stat of cycle mean 1.39 (n = 30): **edge not established**. ≈ 37 K orders, so brokerage at ₹20/order ≈ ₹7.5 L, about half the gross. Four log gaps (8/10, 9/1, 9/14, 9/29) and three D0-only cycles are excluded.

## 9. Corrections to v1

* v1 §5 called D‑1 behaviour "re-centering". **Wrong** — D‑1 accumulates new ATM straddles at the current spot; old strikes stay.
* v1 said the stop "does not reconcile" (−0.7 % of ₹2 Cr). Now resolved empirically: the **base is cycle-cumulative LTP MTM** and the threshold is a **fixed ≈ −₹1.44 L**. Info.txt's 1 %/4 % wording does not map onto it.
* v1 listed the first-slot far wings and ladder loosely; v2 gives the modal ladder and hit-rates.
* v1 labelled the lump "sizing rule open"; still open, but its **sell side is now identified as salvage**, not a signal.

## 10. Still not cracked

1. **Exit / adjustment trigger** for off-ladder body buy-backs on D‑1 and D0 (the largest P&L driver). Needs the real quote path.
2. **Strike selection rule** for the body (≈ 20 % of entries are not nearest-to-spot).
3. **Lump lot-sizing** and exact **wing-premium target**.
4. **D0 09:16 slot** (10–12 lots/leg, hit-rate 17 %) — varies; likely sized off the carried book.
5. **Origin of −₹1.44 L**, and whether it is time/day dependent (all 12 stops are consistent, but all are at one threshold).
6. The Aug‑12 timestamp regime change (lump at 15:23–15:38).

**To go further I need one of:** (a) 1-minute NIFTY/SENSEX spot + option-chain/IV for 2026‑06‑23 → 2026‑10‑22 — then I can regress every off-ladder order against state; (b) the Algo's config/settings (ladder arrays, stop value, hedge %); or (c) the broker's *rejected/cancelled* order log (this file has only fills — modified/cancelled orders carry the trigger state).
