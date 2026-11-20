# Reactive pairs: which indicator best reproduces the direction and the neutral zone? — plan, written before the tests

**User's framing (restated).** The behaviour resembles a moving-average trend indicator with a neutral zone: spot above/below its average gives the strike side (one strike above/below ATM); spot close to the average gives fewer pairs. Distinction to keep: we can find which indicator **explains** the behaviour best; we cannot establish that Algo 8 **literally uses** an SMA/EMA/named indicator — it could be a custom calculation with similar behaviour. Task: find the best-fitting indicator.

**Known (read-only).** Rule "nearest strike to the live spot + 1 step × sign(live spot − X)" hits 89–91% for X = spot 10–60 min ago or SMA 5–60 on the live-spot proxy; anchors tied to the book/day fit worse. Reactive-pair rate: ≈ 4 per 1000 cycle-minutes when |spot − SMA60| < 0.1 step vs 27–41 above; dead zone, saturating; |spot − SMA| (AUC 0.65 plateau N = 15–45) separates events from controls better than |spot − spot N ago| (0.55–0.60).

## Locked definitions
* **Data/points:** the 363 D-1 reactive pairs and the 10,890 random control seconds of the activation study (`bl_act_table.pkl.gz` times and strikes), live-spot proxy at the order second (linear interpolation of the two bracketing minute closes; flagged), indicators computed on **completed minute closes** only (spot close; there is no spot high/low or volume in the data, so high/low/volume indicators are **not testable**).
* **Candidate indicator value v(t)** (signed; direction = sign(v), strength = |v|), pre-registered families and parameter grids (N / span in minutes ∈ {3, 5, 8, 10, 15, 20, 30, 45, 60, 90, 120} unless stated):
  F1 SMA gap: live − SMA_N · F2 EMA gap: live − EMA_span (α = 2/(span+1)) · F3 WMA gap (linear weights) · F4 momentum: live − close N min earlier · F5 regression: slope × N (fitted drift) and live − extrapolated regression line, N ∈ {10, 15, 20, 30, 45, 60} · F6 dual-SMA crossover: SMA_fast − SMA_slow for (3,15), (5,20), (5,30), (10,30), (10,60), (15,60) · F7 MACD-like EMA_fast − EMA_slow for (5,15), (8,21), (12,26) · F8 Donchian midpoint gap: live − (max+min)/2 over N ∈ {15, 30, 60} · F9 volatility-normalised gaps: (live − SMA_N)/σ_N (Bollinger z) and (live − SMA_N)/ATR_N (ATR = mean |Δclose| over N).
* **Metrics:** (D) direction hit: strike = nearest(live) + step × sign(v) on the 363 pairs (sign 0 → ATM); (A) activation: AUC of |v| for pair seconds vs control seconds (cluster bootstrap over cycles; within-cycle permutation null).
* **Parameter selection without optimism:** per family the parameter is chosen on one half of the cycles (alternating by cycle order) and scored on the other half, both ways; the cross-validated score is the family's result. Full-sample best parameters are reported only as descriptive.

## Tests
1. Family ranking by cross-validated (D) and (A); plateau width per family (parameters within 1 point / 0.01 AUC of the best).
2. Pairwise paired cluster-bootstrap differences between the top families.
3. **Absolute vs volatility-scaled neutral zone:** (A) of |gap| in steps vs |z| (Bollinger) vs |gap|/ATR for the same N — which gives the deeper dead zone (hazard ratio outside/inside at the 20th percentile of the control distribution).
4. **Neutral-zone model** for the leading indicator: pair rate by |v| in control-quantile bins; estimate the zone width θ (point where the rate reaches half of its plateau) in index points / % / ATR multiples; stability across halves and underlyings.
5. **Combination:** does adding a second indicator (e.g., crossover or normalised gap) to the leading gap improve (A) in leave-one-cycle-out logistic regression by ≥ 0.01 AUC (permutation null)?

## Decision rules (fixed now)
* A **specific indicator/parameter** is "identified" only if it beats every other family on both (D) and (A) in the cross-validated scores by ≥ 1 point and ≥ 0.01 AUC with paired-bootstrap CIs excluding 0. Otherwise the answer is the **family** (the set that is statistically indistinguishable from the best).
* A **volatility-scaled** neutral zone is called supported only if |z| or |gap|/ATR beats |gap| in steps by ≥ 0.01 AUC with CI excluding 0.
* Labels: Observed / Inferred / Not identifiable. In-sample; the best family is a description, not evidence that Algo 8 uses it.

## Limits (known in advance)
Spot close only (no high/low/volume): Supertrend, Parabolic SAR, ATR from ranges, VWAP are not testable; minute resolution; live-spot proxy uses the current minute's close; 363 events; many correlated candidates (plateaus); the grids are my choice.
