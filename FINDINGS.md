# Algo 8 — Reverse-Engineering Findings (v5, allocation chains + indicator search)

Sources: `Info.txt` + `Trades_GKOHNP140.csv` (41,421 fills, 2026-06-23 → 2026-10-22, 65 days, client `GKOHNP140`)
+ **Breeze 1-minute market data and prior research on branch `research/ml-decision-engine`** (also `data/local-breeze-fetch`, `research/strong-findings`).
Reproduce: `python3 analysis/report.py` · `analysis/modules.py` · `analysis/ladder.py` (fills only) — and, with market data,
`ALGO8_MARKET_DIR=<checkout of research/ml-decision-engine>/data/breeze/normalized python3 analysis/mtm.py` · `analysis/leg_stop.py`
(`analysis/market.py` loads the candles; first run caches them in `analysis/_cache/`).
Labels: **[OBSERVED]** measured · **[VALIDATED]** confirmed on independent market data · **[INFERRED]** pattern fit · **[RULED OUT]** · **[UNKNOWN]**.

> v1 = structural summary. v2 = order tags (raw col 163), limit-band quote recovery, second-level timing. **v3 = the same findings re-tested on real NIFTY/SENSEX index bars and 1.23 M option candles (3,243 traded contract-days) that already existed on the other branches**, plus a corrected per-leg stop test. §0 is new; §4, §6, §7, §9, §10 are updated.

---

## 0. v3 — what the market data confirms  [VALIDATED]

**Relation to the prior research on the other branches.** That work (36–55 commits, `ALGO8_CURRENT_PICTURE.md`, `ALGO8_RULEBOOK.md`, Rahul report) established the 17 recurring pre-expiry windows, the 65/20-unit parent orders, the ~2.5 %-of-ATM-premium hedge budget, directional placement of extra straddles, and the 15:14 late exit. It **did not use** the order-tag column, the ±15 % limit band, or identify a stop threshold (it lists the stop as "unknown" and the 4 %/1 % note as unverified). v3 adds those, tested on its data.

| Claim (from v2) | Test on market data | Result |
|---|---|---|
| Limit = LTP×1.15 (buy) / ×0.85 (sell) ⇒ L = recovered live quote | L vs Breeze candle of the order minute, 37,258 orders | **L inside the real candle range for 96.6 %** of orders (hedge orders 99.8 %); fills inside range 97.8 % |
| Stop = cycle-cumulative MTM at LTP ≈ −₹1.44 L | Minute MTM of every cycle from exact fills + real candle marks; directional intraminute extreme (calls at high & puts at low, or the reverse) | **No non-stop cycle ever went below −₹1.43 L** (worst −142.6 K, 10/22 SENSEX) even at intraminute extremes; stop cycles reach −139.9 K … −351 K inside the trigger minute (10/13 −144.5 K, 7/16 −147.3 K, 8/06 −139.9 K) |
| Competing: stop = −₹2 L on band-marked P&L | Band-marked minute MTM | **Falsified** — SENSEX 10/01 cycle hit −218.9 K band-marked at 10:07 with no stop (LTP-MTM then ≈ −117 K) |
| "Aug-12 timestamp regime change" | Breeze session metadata | **Resolved, not a regime change**: derivatives session runs to 15:39 from 3 Aug (385 bars); late lumps are inside the session |

**Stop-loss, final reading:** the `s_` module liquidates the whole cycle when **cycle-cumulative (D‑1+D0) mark-to-market at LTP, body + hedges, falls to ≈ −₹1.43–1.45 L**; bracketed above by −142.6 K (never fired) and below by ≈ −144 K (fires). It is size-independent, applies on D‑1 and D0, and ends trading for the cycle. −₹1.5 L and −₹2 L thresholds are inconsistent with the data.

**Per-leg stop (new, corrected test)** — each body short lot is bought back when its own option first trades at ≈ **1.5–1.6× that lot's entry fill** (minute high), cheapest-entry lot first:

| D‑1 (4,834 lots, 1,640 body buy-back lots) | Value |
|---|---|
| After a lot first trades ≥ 1.55× entry, an actual buy-back of that contract within 2 min | **74 %** (82 % within 15 min; 12.7 % never on D‑1) |
| Actual D‑1 exits at ≥ 1.45× cheapest open entry predicted within 2 min | **80–86 %** (691 events) |
| Price had already closed ≥2 % above the exit level earlier (first-passage check) for exits ≥ 1.3× | 0–7 % (a stop's signature) |
| Best grid point (threshold 1.5–1.6, on minute high) lot-level precision / recall | 0.50–0.59 / 0.35 |

* The remaining ~640 D‑1 exits at < 1.45× are largely **companions**: 36 % (1.0–1.45×) fire within 5 s of a stop-class exit, mostly other strikes on the **same side**; 53 % of ≤ 1.0× exits do, often the **same-strike other side**. A triggered leg stop closes a group whose exact definition is still **[UNKNOWN]**.
* **D0:** weaker and higher — a D0 lot at 1.6–1.8× entry is exited within 2 min in 69–76 % of cases, but recall is only 0.22–0.25 (expiry-day exits mix several mechanisms). **[INFERRED]**

---

## 0b. v4 — ML attack on the six open questions

Method: one targeted supervised problem per question, built from tagged fills + Breeze bars; interpretable models (shallow trees) next to LightGBM; **chronological 60/40 split by session** (train on earlier dates, score on later), grouped CV where n is small. Scripts: `analysis/p1_*.py … p6_*.py`, `analysis/ml_followups.py`. All 35 cycles were already explored, so these are reconstruction fits, not independent evidence.

| # | Question | Verdict | Key evidence (out-of-sample unless noted) |
|---|---|---|---|
| P6 | Why −₹1.44 L, not −₹2 L? | **Metric cracked; level bracketed** | Only gross **cycle-cumulative LTP-MTM** separates stop vs non-stop cycles (margin +₹12.5 K, CV 4.7 %); drawdown-from-peak, day P&L, day drawdown all fail (non-stop drawdowns reach −₹3.65 L). Configured level ≈ **−₹1.30–1.35 L**: deepest non-stop instantaneous MTM −₹1.302 L; 8/06 and 7/16 were already at −₹1.35 L / −₹1.37 L **1 s** before firing. The −₹1.44 L average is level + overshoot from a **1–20 s check latency** (gap opens fire 10–20 s after 09:15:00). No tested P&L definition puts it at −₹2 L. Origin of the constant: **[UNKNOWN]** |
| P1 | Which lots close together on a leg stop? | **No group rule (negative)** | Candidate model F1 0.23; other open contracts close within 30 s only 6.9 %. Each lot has its **own ≈1.55× stop**: 82 % (D‑1) / 78 % (D0) of crossings bought back ≤ 15 min, **89 %** for lots entered ≥ ₹16; lots ≤ ₹4 effectively exempt (tick noise); off-grid lots stopped less (66 % vs 92 %). "Companions" = same-side lots crossing their own levels in the same move |
| P3 | When do extra entries fire? | **Largely cracked** | Off-grid minute model AP 0.45 vs base 0.105. Mechanism = **per-leg 15-min timers**: 24 % of D‑1 off-grid sale minutes come 14–15 min after that side's previous sale. Whether a due timer fires is predictable (**grouped-CV AUC 0.887**), almost purely by **time window**: 09:16–11:15 33–43 %, 11:16–13:27 3–11 % (dead), 13:28–14:36 56 % → **93 %** if no sale on either side for > 14.5 min, after ~14:47 ≈ 0. Plus batch spill-over (12 % D‑1, 26 % D0 at 1-min gap). Re-entry after stops is **not** it (1–2 % same side) |
| P4 | Exact strike rule | **Partial (68.5 %)** | Candidate-choice LightGBM **68.5 %** top-1 vs 58.4 % nearest-ATM (D‑1 scheduled 78.5 %, D0 scheduled 74 %, off-grid 61–63 %). Best single reference = previous-minute index close (72 % D‑1 scheduled); more lag/smoothing is worse. Even generous intraminute bound for nearest-to-live-spot explains only 80 % (scheduled D‑1) / 45 % (off-grid) → the rest are **deliberate offsets**, mostly 1 strike lower. Top features: closeness to the previous same-side sale's premium, same strike as previous sale. Fixed ₹ premium target **ruled out** (sold premium tracks ATM premium, corr 0.96). Book-state (delta/imbalance) adds < 1 pt |
| P2 | Expiry-day exits beyond the stop | **Decomposed, not one rule** | Minute exit hazard AP 0.11 vs base 0.018. Exit minutes split: leg stop 22.7 %, salvage of near-worthless OTM shorts (≤ 5 % of entry or ≤ ₹1) 11.5 %, **afternoon exit clock** 6.5 % (hazard at :14/:29/:44 is **22 % vs 3.7 %** in 14:15–14:45, 6× lift), other 59 %. 63 % of exit minutes have a same-side sale within 1 min (baseline 50 %). **22 %** of D0 buy-backs have a sale of the *same contract* within 2 min → several allocations trade the same contracts concurrently |
| P5 | Overnight lump lot count | **Not cracked (negative)** | Leave-one-out ridge / random forest 35–37 % median error, **worse than** the naive per-index median (24 %). Cost / day credit median 3.9 % but CV 0.44; delta/gamma/vega-neutral sizes don't fit. Rules that hold: heavier short side (90 %), 0.9–2.3 % OTM. Sizing likely depends on something not in the data (overnight margin or config) |

**Structural insight behind the partial results.** The fills are the **superposition of several concurrently running allocations**, each with its own 15-min timer, ≈1.55× leg stop and exit clock, all sharing one cycle-level stop. Same-contract buy-and-sell within minutes (22 % on D0) is the fingerprint. This is why no single per-contract trigger reproduces every fill, and why the per-lot rules work best on D‑1, where allocations overlap least.

---

## 0c. v5 — allocation chains and the indicator search

### Allocation / timer structure (`analysis/chains.py`, `a2_*.py`)
Sale bursts were clustered by their **second-level phase modulo 15 min**, with a jitter null calibrated so the false-discovery rate is ≈ 0 (p < 1e-12; at p < 1e-4 the null produced 55 % false chains, so the strict level is required).

| Clock | Where | Phase | Role |
|---|---|---|---|
| Grid A | D‑1 and D0 | :01/:16/:31/:46 (from 09:16) | Ladder entries; sells nearest ATM (D‑1 77.6 %, 85.6 % allowing intraminute) |
| Grid :00 | D‑1 13:30–15:00, some D0 | :00/:15/:30/:45 | Afternoon additions; mostly **one strike low** (CE ITM 73 %) |
| **Clock B** | D0 from **09:29** | :14/:29/:44/:59 | **Rebalance scheduler**: 25.5 % of D0 buy-backs in 8.3 % of the time; buys and sells per event correlate 0.91; closes ≈ 10–12 % of a contract per tick |
| Extra clocks | D0, early weeks only (6/25, 7/02) | :05/:20…, :10/:25… | Disappear later → configuration change |

* **Event-anchored chains do not survive the null**: every confirmed chain is a fixed clock. Off-grid "extra" sales are timer chains (≈ 24 % on D‑1), batch spill-over, or unchained (see §0b P3).
* At a Clock‑B tick, *which* lots are closed is **not** a per-lot price rule (fungible-lot count test: profit-target and stop conditions ≤ 10 % precision at every threshold). Contract-level model AUC 0.84 but F1 0.23 (lots held and time). Lots are interchangeable in the fills, so allocation identity cannot be recovered → this stays **[UNKNOWN]**.
* Strike choice depends on the module: grid A sells ATM; grid :00 and unchained sales shift **toward the recent move** (CE ITM 73–78 % on D‑1). A premium-parity ATM (min |CE−PE|) is **worse** than index-nearest (54 % vs 78 %).

### Does it use indicators? (`analysis/indicators*.py`, `b2_*.py`)
Library: **75 causal index indicators** at 1/5/15 min (EMA 5/9/20/50 distance, EMA 9/20 spread and slope, SMA20, MACD and histogram, RSI 7/14, Stochastic, CCI, ROC, ATR, Bollinger %b/width, ADX/DI, Supertrend(10,3), realized vol, prior-day H/L/C, pivot/R1/S1, gap, day open/high/low distance, opening-range breakout), **14 option measures** (ATM IV, CE−PE IV, straddle, 1.5 %-OTM skew, PCR-OI, their changes), and **crossover events** (EMA cross, Supertrend flip, MACD flip, RSI 30/70, BB touch, first ORB break). VWAP is impossible (index has no volume); SENSEX OI is zero in the data.

Test: 8 decisions; nested out-of-sample LightGBM (3 expanding chronological folds) **base (clock+book) → +raw price moves → +indicators**, against 5 nulls that take indicators from a different random date at the same time of day; then univariate tests with BH-FDR, re-checked **within date** to remove between-day confounding.

| Decision | Gain from indicators over raw price (null max) | Verdict |
|---|---|---|
| Extra off-grid sale | −0.002 (−0.015) | none |
| Timer-due fire | −0.030 (−0.012) | none |
| D0 buy-back hazard | −0.008 (−0.007) | none |
| Clock-B rebalance choice | −0.002 (−0.028) | none |
| Slot sized above ladder | −0.021 (−0.078) | none |
| Strike off ATM | +0.026 (+0.002) | options family; **no single feature** (all AUC 0.46–0.52) |
| Leg stop executed vs survived | +0.099 (+0.062); trend family +0.105 (+0.050) | **no single feature** (best 15m ADX, within-date AUC 0.58); not the wick, not spot-since-entry, not a 1/3/5/15-min candle-close stop (none beats "always stop") |
| Offset direction (OTM vs ITM) | +0.005 overall; **levels +0.013** (+0.002) | **spot vs the day's high / prior high / R1**: within-date AUC 0.69–0.74 |

* The univariate scan flags 335/1,008 tests at q < 0.05, but the top hits are all **1-minute momentum readings** (RSI 7/14, Stochastic, EMA 5/9/20 distance, %b, DI diff). These are near-copies of the recent price move and add **nothing** beyond raw moves in the model-level test. They show the algo reacts to recent movement, **not** that it computes RSI or an EMA.
* **Conclusion [INFERRED, strong]: no classical technical or option indicator is identifiably used.** Decisions are driven by fixed clocks, its own P&L and premium ratios, and **price location** (recent move and where spot sits in the day's range) for the direction of strike shifts. Residual unexplained variation (leg-stop survival, strike off-ATM) shows only diffuse, interaction-level association.

### Parameter sheet (everything decoded so far)

| Parameter | Value | Status |
|---|---|---|
| Cycle | D‑1 (BTST) + D0 expiry; NIFTY Mon/Tue (lot 65), SENSEX Wed/Thu (lot 20) | observed |
| Orders | 1 lot per order; limit = LTP×1.15 buy / ×0.85 sell (lump buy ×1.03); tags num/h_/v_/s_/m_ | validated |
| D‑1 ladder (lots/leg) | 09:16 3, 09:31 2, 09:46 3, 10:01 1, 10:16 3, 10:31 1, 10:46 2, 11:01 2, 11:16 1, 11:31 1, 11:46 3, 12:01 1, 12:16 0, 12:31 2, 12:46 0, 13:01 0, 13:16 1 | observed (modal) |
| Clocks | grid A :01/:16/:31/:46; grid :00 13:30–15:00; D0 Clock B :14/:29/:44/:59 from 09:29 | validated (null-calibrated) |
| Timer windows | active 09:16–11:15, quiet 11:16–13:27, active 13:28–14:36 (93 % if no sale for 14.5 min), off after ≈ 14:47 | ML (AUC 0.887) |
| Strike | nearest to previous-minute index close (grid); ±1 strike toward recent move / day-range position (other modules) | partial (68.5 %) |
| Wings | premium ≈ 1.0–1.4 % of straddle (prior work: ≈ 2.5 % of each ATM leg); 09:16 seed wings far (~0.3 %) | partial |
| Leg stop | ≈ 1.55× the lot's own entry; lots ≤ ₹4 effectively exempt | validated (82–89 %) |
| Cycle stop | cumulative LTP-MTM ≤ ≈ −₹1.30–1.35 L; 1–20 s check latency (fills average −₹1.44 L); ends cycle | validated |
| Lump hedge | heavier short side (90 %), 0.9–2.3 % OTM, ₹3–9 NIFTY / ₹12–22 SENSEX, ≈ 15:06–15:38; sold as salvage on D0; **lot count not predictable** | partial |
| D0 exits | leg stop 23 %, salvage ≤ ₹1 / ≤ 5 % of entry 12 %, Clock-B rebalance, 15:14 flatten | partial |
| Indicators | none identifiable | tested |

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

* **Buy:** one OTM strike, one ~3 % limit band, ≈15:06–15:14 (until Aug‑12) then ≈15:23–15:38 (inside the 15:39 derivatives session that starts 3 Aug — not a clock anomaly); on the heavier short side (29/31 days); 2–153 lots; price ₹3–9 NIFTY / ₹12–22 SENSEX.
* **Sell (D0):** not a signal. It is a **salvage dribble**: IOC sells of 1–8 lots at 0.03–0.25× entry (typically 14:00–15:15), plus a lump liquidation inside stop events (e.g. 7/14: 15 lots at ₹3.50 in the first second). Sizing rule for the buy: **[UNKNOWN]** (not constant ₹, not CE/PE imbalance, not constant % of short lots).

## 7. What I tested and RULED OUT  [RULED OUT]

| Hypothesis | Test | Result |
|---|---|---|
| ~~Per-leg stop at fixed premium multiple~~ | v2 used FIFO / running-average entry pairing | **v2 conclusion was wrong** — the pairing was mis-specified. Measured against the *cheapest open lot* with real candles (§0) a ≈1.5–1.6× leg stop is supported on D‑1 |
| Exit when spot moves X % from entry spot | adverse move at exit | Smooth 0.1 %–0.75 %, no threshold |
| Exit when spot is X strike-steps from the sold strike | (spot − strike)/step at exit | Exits from −10 to +10 steps, including dead ATM |
| Fixed holding time (15 min multiples) | 9,127 D0 lots | Flat distribution, no peaks |
| D0 profit-target fraction / absolute price | ratio × time, absolute L × time | Mixed 0.05×–2.5×, no cluster |
| Stop gap vs −₹2 L explained by costs | STT+exchange charges per cycle | ₹1.2–3.3 K, far too small |
| Stop base = day P&L vs prior close | day MTM − carried value at prior close | ±40 % scatter |

| Stop = −₹2 L on band-marked P&L (shorts ×1.15, longs ×0.85) | v2: mean −207 K but SD 26.5 K; v3: market-data minute MTM | **Falsified in v3** — a non-stop cycle (SENSEX 10/01) reached −218.9 K band-marked without a stop |

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
* **v3 corrections to v2:** (a) v2 "ruled out" a per-leg premium stop — that test paired exits to the wrong lots; with cheapest-lot pairing and real candles a ≈1.5–1.6× D‑1 leg stop is supported (§0). (b) v2 left "−₹2 L on band-marked P&L" open — now falsified. (c) v2's "Aug‑12 timestamp regime change" is the extended 15:39 derivatives session. (d) v2 said market data was needed — it was already in the repo on the other branches.

## 10. Still not cracked

*After v5 (see §0b, §0c):* indicator use is tested (none identifiable) and clock structure is decoded. Still open are the Clock-B lot-selection rule (needs allocation identity), the leg-stop survival residual (~21 %), and also the D0 "other" exits (59 % of exit minutes), the ~20–30 % deliberate strike offsets, lump lot-sizing, and the origin of the ≈ −₹1.30–1.35 L stop constant. The most promising next step is to reconstruct **allocation identity** (assign each lot to a timer chain) so per-allocation rules can be fitted instead of per-contract ones. The v3 list below is kept for history.

### v3 list

1. **Leg-stop grouping** — which other lots close when one leg stops (same side? same allocation/slot? straddle partner?), and the exact multiple (1.5 vs 1.6, high vs LTP crossing).
2. **D0 exit controller** — the leg stop explains only ~¼ of D0 exits; decay closes, rebalancing and the 15:14 flatten still need separating.
3. **Extra (off-ladder) entry trigger** — prior work's directional strike placement fits, but *when* they fire is unknown.
4. **Strike selection** for ladder entries (61.5 % nearest-to-spot); prior work finds the nearest preceding index close matches the 31 opening strikes — test that rule for all later slots with the real index bars.
5. **Lump lot-sizing**, exact wing/hedge premium target (prior work: ≈ 2.5 % of ATM premium per side, 50 % exact / 92–95 % ±1 strike).
6. **Origin of −₹1.44 L** (not 1 % of ₹2 Cr on any P&L definition tested).

All of 1–5 can now be attacked with the market data on `research/ml-decision-engine`; none of it needs new downloads. Guardrail: every fit here is on the same 35 cycles that were explored, so these are reconstruction fits, not out-of-sample evidence of an edge.
