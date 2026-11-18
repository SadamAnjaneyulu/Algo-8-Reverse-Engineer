# Market Regime Analysis

Source: `regimes.py` → `regime_features_cycles.csv`, `regime_terciles.csv`, `regime_spearman.csv`, `regime_descriptive.csv`, `regime_volclustering.csv`; `figures/regime_terciles.png`, `figures/premium_vs_move.png`. Code executed, outputs observed.

## 0. Rules followed
* **Decision-time features** use only information available at the 09:16 D-1 entry: Yahoo daily bars up to the trading day **before D-1**, the 09:15 spot bar and the traded entry premium.
* **Outcome features** (D-1/D0 realised moves, overnight gap into D0, expiry-day range) are ex-post and are used **only to describe what happened**, never as predictors.
* **No implied volatility or surface data exist** in this project. "Straddle premium % of strike" is an *observed traded price* (short CE + short PE at entry), a proxy for the market's expected move, **not IV**.
* Terciles are cut on **IS only, per index**, then applied unchanged to OOS. Nothing is selected or tuned from OOS.

## 1. Structural identity (established)
At settlement a short straddle's gross P&L is exactly `qty × (premium collected − |close − K|)` (correlation 1.0000, max abs error ₹0.0 across all 275 cycles; wings add a small cost). **The whole strategy is therefore one bet: does the entry premium exceed the realised distance between the settlement price and the strike?** The other features can matter only through that.

## 2. What happened in each window (descriptive, means; ratio = median premium ÷ \|move\|)

| Index | Window | Cycles | Premium % K | \|move\| % K | D0 range % | Overnight \|gap\| % | RV5 % | median premium/\|move\| | Mean net ₹ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NIFTY | IS | 105 | 0.81 | 0.72 | 0.96 | 0.28 | 0.70 | 1.38 | +3,049 |
| NIFTY | OOS clean | 31 | **1.04** | **1.05** | 1.08 | **0.62** | 0.89 | **1.08** | **−1,860** |
| NIFTY | OOS exposed | 18 | 0.73 | **0.47** | 0.95 | 0.21 | 0.66 | **2.28** | **+11,351** |
| SENSEX | IS | 70 | 0.86 | 0.79 | 1.05 | 0.30 | 0.73 | 1.35 | +2,528 |
| SENSEX | OOS clean | 33 | 0.89 | 0.82 | 1.09 | 0.46 | 0.87 | 1.38 | +2,920 |
| SENSEX | OOS exposed | 18 | 0.78 | 0.79 | 0.94 | 0.28 | 0.70 | **0.96** | −1,371 |

Reading: NIFTY clean OOS had **higher premium but equally higher realised distance** (1.04 vs 1.05) → the cushion vanished; overnight gaps doubled (0.62 % vs 0.28 %). NIFTY exposed was an unusually calm window (|move| 0.47 %, premium cushion 2.3×) → the large profit. SENSEX exposed lost money because settlement distance matched premium. These differences are **observed outcomes**, not demonstrated causes.

## 3. Do decision-time regimes predict P&L? (no)

Spearman correlation of each decision-time feature with cycle net P&L, IS vs OOS (`regime_spearman.csv`): every |ρ| ≤ 0.25 and **all p-values ≥ 0.07** (best: SENSEX OOS \|gap\|, ρ = +0.25, p = 0.072 — would not survive multiplicity over 10 features × 2 indices × 2 samples).

Tercile results (net per cycle, IS-cut terciles) are **non-monotonic and sign-unstable**, e.g. NIFTY RV5: IS LOW +4.4k / MID +0.0k / HIGH +4.7k; OOS LOW +2.4k / MID **−12.0k** / HIGH +12.0k. SENSEX RV5: IS MID **+14.0k**, HIGH **−8.8k**; OOS MID +3.8k, HIGH +0.5k. A real regime effect would be monotone and persist across IS/OOS; none does.

**What *is* informative about the outcome (not about P&L):** the entry premium predicts the *size of the move* (corr(premium %, |move| %): NIFTY 0.47, SENSEX 0.37; RV5 vs |move|: 0.42 / 0.34) but not the *net* (corr(premium, net) = 0.05 / −0.02). I.e. the market already prices realised-vol clustering into the premium; selling the richer premium is **not** richer after the fact. Autocorrelation of |move| across weekly expiries is ≈0 (NIFTY 0.03, SENSEX 0.13): little volatility clustering at weekly horizon.

## 4. Specific questions

| Item | Finding |
|---|---|
| Directional movement | IS short-put leg earned the money (gross +₹656k vs short-call −₹35k, a rising market). OOS reversed: short-call +₹282k, short-put +₹16k; exposed window: call +₹325k, put −₹118k. The edge is **direction-dependent by window**: the straddle sums two legs whose sign of luck flips. Plausible link to the market's net drift, not tested. |
| Intraday realised vol / range expansion | D0 range % of price: NIFTY IS 0.96, clean 1.08; SENSEX 1.05/1.09. Mild expansion only. |
| Overnight gaps | The largest observed shift: NIFTY \|gap\| 0.28→0.62 %. P&L-time decomposition (`POSITION_AND_LEG_ATTRIBUTION.md` §5): the overnight segment is the dominant loss source in the worst cycles. |
| Opening vol | Not measured separately (only 09:15 spot gap used). Unknown. |
| Trend vs mean reversion | 5/20-day trend features have no significant relation to net P&L (see §3). |
| Expiry-day movement / large adverse moves | The 10 worst cycles had \|close−K\| of 359…2,410 pts (≈1.4–3.1 %); see leg report. |
| Volatility clustering | Weak at weekly horizon (above). |
| NIFTY vs SENSEX | Both index-level; SENSEX has fewer wing substitutions but wider distances (4000 pts). SENSEX IS is partly driven by one anomalous entry print (see leg report). |

## 5. Conclusion
* **Established:** P&L is premium − realised settlement distance; the OOS shortfall in the clean sample comes from NIFTY's thinner premium cushion (1.08×) and a left tail of gap-driven losses.
* **Plausible, not established:** the exposed window was a favourable (calm, for NIFTY) window.
* **Not supported:** any decision-time regime filter. I have **not** looked for filters that improve P&L and am not proposing one; the evidence above says none is available from these features.
