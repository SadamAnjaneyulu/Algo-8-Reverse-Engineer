# Transaction Cost Analysis

Source: `cost_analysis.py`, `settlement_check.py`, `settlement_sensitivity.py` → `cost_components_{cycles,summary}.csv`, `slippage_scan.csv`, `breakeven_slippage.csv`, `entry_drift.csv`, `settlement_vs_yahoo.csv`, `settlement_sensitivity.csv`. Code executed, outputs observed. Costs are **re-implemented independently** from the trade list; the reconstruction equals the reported cycle costs to 3e-14.

## 1. Verified vs assumed inputs (read this first)

| Input | Value in the model | Status |
|---|---|---|
| STT on option sells | 0.0625 % to 2024-09-30, 0.10 % to 2026-03-31, **0.15 % from 2026-04-01** | Only the **2026 change is externally confirmed** (budget reports). The 0.0625→0.1 % date is from memory, **unverified**. |
| STT on exercise (ITM long at expiry) | 0.125 %, 0.15 % from 2026-04-01 | Same status. |
| Exchange transaction charge | NSE 0.035 %, BSE 0.0325 % of premium | Quoted from memory, **unverified**. |
| Brokerage | ₹20 per order | **Assumption**; Algo 8's broker terms unknown. |
| SEBI 0.0001 %, stamp 0.003 % (buys), GST 18 % on brokerage+txn+SEBI | | Quoted from memory, **unverified**. |
| Slippage | max(₹0.10, 0.5 % of the bar-open price) per fill, against the trader | **Pure assumption.** No bid/ask data exist. |
| Fill price | open of the first traded bar of the entry minute; engine-driven actions at the last mark | Assumption (no tick/book data). |
| Settlement | cash-settled intrinsic at the official close proxy | Proxy; see §4. |
| Lot sizes | inferred per session as gcd of volumes | Inferred; consistent with known revisions, not checked against circulars. |
| Missing bid/ask | not available for any contract | **Unresolved** |

## 2. Cost reconstruction (₹, HOLD baseline)

| Sample | Cycles | Gross | Slippage | Brokerage | Exch. txn | SEBI | GST | Stamp | STT (sells) | STT exercise | **Total stat. costs** | **Net** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IS | 175 | 551,185 | 30,627 | 14,000 | 1,820 | 5 | 2,849 | 2 | 4,790 | 0 | 23,467 | 497,091 |
| Full OOS | 100 | 258,406 | 23,470 | 8,000 | 1,425 | 4 | 1,697 | 2 | 5,442 | 37 | 16,608 | 218,329 |
| OOS exposed | 36 | 192,538 | 7,140 | 2,880 | 423 | 1 | 595 | 0 | 1,857 | 0 | 5,756 | 179,642 |
| OOS clean | 64 | 65,867 | 16,329 | 5,120 | 1,002 | 3 | 1,103 | 2 | 3,585 | 37 | 10,851 | 38,687 |

* **Friction (slippage + costs) as a share of gross:** IS 9.8 %, full OOS 15.5 %, exposed 6.7 %, **clean 41.3 %**.
* Per cycle: gross ₹3,150 (IS) → ₹1,029 (clean); friction ₹309 → ₹425. Of the ₹2,237/cycle drop in net between IS and clean OOS, **₹2,121 (95 %) is lower gross P&L and ₹116 (5 %) is higher friction**. **Execution costs did not cause the weakness; they make a thin gross edge thinner.**
* Statutory costs are small (₹134/cycle IS); slippage is 57 % of friction. Wings generate disproportionate friction: ₹20 brokerage on a ₹0.5–1 option is a large fraction of its price (wing friction IS ₹12.3k for two wings, with zero pay-off).
* STT is the one cost that rose over time: ×1.6 (0.0625→0.10 %) then ×1.5 (→0.15 %) on sell premium.

## 3. Slippage sensitivity and break-even

Slippage multiple × base (0.5 % of price, min ₹0.10); costs at 1×. Net ₹:

| × | IS | OOS | OOS clean | OOS exposed | OOS (Yahoo settle) | OOS clean (Yahoo settle) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 527,685 | 241,764 | 54,993 | 186,771 | 191,351 | 25,634 |
| 1 | 497,091 | 218,329 | 38,687 | 179,642 | 167,916 | 9,328 |
| 2 | 466,498 | 194,894 | 22,381 | 172,513 | 144,481 | −6,978 |
| 3 | 435,904 | 171,459 | 6,074 | 165,384 | 121,046 | −23,284 |
| 4 | 405,310 | 148,024 | −10,232 | 158,256 | 97,611 | −39,590 |
| 6 | 344,123 | 101,154 | −42,844 | 143,998 | 50,741 | −72,203 |
| 10 | 221,748 | 7,414 | −108,069 | 115,483 | −42,999 | −137,428 |

**Break-even slippage** (multiples of base; base ≈ ₹0.5 per NIFTY short leg, ₹1.7 per SENSEX short leg): clean OOS **3.4×** with the original settlement proxy but **1.6×** with the corrected settlement; full OOS 8.2× (corrected) and not reached by 10× (original); IS not reached by 10×. Note the two baselines: what the market's real spread is relative to my base is **unknown**. 1.6× corresponds to 0.8 % of premium per fill.

Interpretation: **the clean-OOS result is not robust to execution assumptions** — a fill ~0.4 % of price worse than the base removes the profit on corrected settlement. The IS and exposed results survive 10×. This asymmetry is again the same finding: the edge is large only where the gross edge is large.

## 4. Settlement assumption (a model defect with measured effect)

The original run settles on the **15:30 spot bar close** (150 NIFTY, 93 SENSEX cycles; otherwise the Yahoo official close for 32 cycles). Compared with the independent Yahoo official daily close:

| | NIFTY | SENSEX |
|---|---:|---:|
| Cycles using the 15:30 bar | 150 | 93 |
| Mean \|difference\| (pts) | 14.9 | 22.0 |
| Median \|difference\| | 9.5 | 0.0 |
| Max \|difference\| | 120.8 | 240.7 |
| Cycles with \|diff\| > 50 pts | 6 | 17 |

Measured bias (243 cycles using the 15:30 bar): the proxy sits on average **3.1 pts (NIFTY) / 0.9 pts (SENSEX) closer to the strike** than the official close (mean distance to K 325.4 vs 328.6 pts; the proxy was closer in 52.7 % of cycles; correlation of the difference with the settlement move −0.24 NIFTY). That favours a short straddle by ≈ 3 pts × ~195 units ≈ ₹0.5k per cycle ≈ ₹50k over the 100 OOS cycles. The mechanism (e.g. closing-period averaging in the official index close versus a last-print spot bar) is **not determined**. **Corrected run (`SETTLE_YAHOO`, separately labelled; original results untouched)**:

| Config | Sample | Net original | Net corrected | Δ | Sharpe orig → corrected |
|---|---|---:|---:|---:|---:|
| HOLD | IS | 497,091 | 473,197 | −23,894 | 1.10 → 1.01 |
| HOLD | Full OOS | 218,329 | **167,916** | −50,413 | 0.69 → **0.54** |
| HOLD | OOS exposed | 179,642 | 158,588 | −21,054 | 2.26 → 2.02 |
| HOLD | OOS clean | 38,687 | **9,328** | −29,359 | 0.17 → **0.04** |
| Frozen | Full OOS | 67,163 | 18,944 | −48,219 | 0.22 → 0.06 |
| Frozen | OOS clean | −114,188 | −135,571 | −21,383 | −0.51 → −0.61 |

Status: that the two proxies differ is **established**; that the Yahoo close equals the exchange settlement value is **plausible (it is the published official index close) but unverified** — a settlement-price source from the exchange has not been used.

## 5. Entry timing and the delay anomaly (resolved)
One-minute entry delay raised SENSEX IS P&L by ₹99.8k. Mean one-minute drift of short-leg prices: NIFTY IS −0.39 %, SENSEX IS **+28.4 %**, but SENSEX median −0.6 %; the +28 % mean is a single contract (2025-04-08, ₹38.30 → ₹1,535.55 ≈ ₹90k). Ex-outlier, entry drift is about −0.4 to −0.7 %/min for NIFTY and slightly positive for SENSEX OOS; premium decays after the open on average (a later entry would have sold at a slightly lower price, i.e. delay *hurts* the short seller in the typical cycle).

## 6. Market behaviour vs execution assumptions
* **Market behaviour (gross):** explains ~95 % of the IS→clean drop in net per cycle.
* **Execution assumptions:** can move the clean-OOS result from +₹55k (no slippage) to −₹108k (10×), and the settlement proxy by ₹29k. Both are **unmeasured model inputs** in a sample whose net is ₹39k.
* Therefore the correct answer to "is it profitable after realistic costs?" is: **not demonstrated.** Net over the full OOS is positive under every tested slippage ≤ 8× (corrected settlement), but its t-statistic is 0.73 before correction (see `RETURN_DISTRIBUTION_ANALYSIS.md`).
