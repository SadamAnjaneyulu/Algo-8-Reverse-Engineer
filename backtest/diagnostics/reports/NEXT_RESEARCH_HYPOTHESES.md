# Next Research Hypotheses (NOT implemented, NOT tested)

Every item below is a **hypothesis for a future, pre-registered experiment**. Nothing here was implemented or evaluated in this diagnostic and none of it changes the frozen baseline. Each is derived from evidence in the other eight reports. **No hypothesis may be tested on the clean OOS block** (it has been viewed descriptively in this diagnostic); each needs new data — see "OOS protection".

## Ranked priorities

| Rank | Priority | Why first |
|---:|---|---|
| 1 | **Measure the edge itself, with real execution and settlement inputs** (H1, H2) | Net clean-OOS is ₹39k and flips sign with a 1.6× slippage change or the settlement proxy (₹29k). Until these two inputs are measured, no strategy-level conclusion is safe. |
| 2 | **Overnight/gap and expiry-day risk** (H3, H4) | The overnight leg lost ₹106k IS and ₹111k clean OOS; 48 % of the OOS worst-decile loss is booked before the first plugin tick. |
| 3 | **Premium-vs-realised-move cushion** (H5) | P&L is exactly premium − |move|; the clean NIFTY cushion fell to 1.08× vs 1.38× IS. |
| 4 | **Wing design / purpose** (H6) | Wings never paid (0/154 NIFTY); ₹83k IS cost; but their margin role is unmeasured. |
| 5 | **Sizing / exposure normalisation** (H7) | Lot size changes with a fixed 3-lot rule; exposure in units is not constant. |
| 6 | **Cut / re-entry logic** (H8) | Evidence negative; lowest expected value until H3 is understood. |
| 7 | **Regime-conditional construction** (H9) | No decision-time feature showed a stable relation to P&L; do last, and only with new data. |

## Hypotheses

### H1 — Execution modelling with real quote data
* **Reason:** the result depends on an assumed 0.5 % slippage with no bid/ask. Break-even slippage on the clean block is 1.6× (corrected settlement).
* **Evidence:** `TRANSACTION_COST_ANALYSIS.md` §3; Algo 8 live ledger fills exist for the exposed window (compare backtest fill vs actual fill, same contract and minute).
* **Expected benefit:** replaces an unmeasured input with a measured one; direction of the correction is unknown.
* **Downside:** the live fill record covers only 36 cycles of one period.
* **Required data:** `Trades_GKOHNP140.csv` fills vs minute bars; if obtainable, quote/depth snapshots.
* **Experiment:** compute realised slippage = (live fill − bar-open at same minute) per leg/side/moneyness; fit a distribution; re-price the *existing frozen* backtest with it as a stress, not a tuned parameter.
* **In-sample method:** estimate on exposed-window fills; test on a disjoint set of live cycles.
* **OOS protection:** estimation uses live fills only; backtest P&L is never used to choose the slippage.

### H2 — Settlement price source
* **Reason:** the 15:30-bar proxy is 3.1 pts closer to the strike than the official close in NIFTY (₹50k over the OOS).
* **Evidence:** `TRANSACTION_COST_ANALYSIS.md` §4; `settlement_vs_yahoo.csv`.
* **Expected benefit:** removes a ₹50k OOS (₹24k IS) bias; certain direction (down), exact size unknown.
* **Downside:** none beyond acquiring data.
* **Required data:** exchange-published index closing/settlement values for all expiries (NSE/BSE circulars or archives) to confirm Yahoo equals the settlement price.
* **Experiment:** reconcile exchange settlement vs Yahoo for all 275 cycles; adopt the exchange value as the only settlement source; re-run the baseline once and label it the new baseline.
* **OOS protection:** purely a data-correctness fix, no P&L-based choice.

### H3 — Overnight gap risk
* **Reason:** theta is earned on D0 (+₹496k IS) but overnight cost −₹106k IS / −₹111k clean; the worst-decile OOS loss is 48 % booked by D0 09:16.
* **Evidence:** `POSITION_AND_LEG_ATTRIBUTION.md` §5.
* **Hypothesis:** conditional on a pre-open indicator available *before the close of D-1* (e.g. size of the D-1 move, time-to-event), the carried overnight exposure has a different payoff than the D0 exposure and could be sized or hedged separately.
* **Expected benefit:** a smaller left tail; unknown net effect.
* **Downside:** less premium carried; hedging costs; the gap is not predictable from the features tested here.
* **Required data:** pre-open/overnight proxies (SGX/GIFT Nifty, US close, event calendar) — **not in the project**.
* **Experiment:** decompose P&L into overnight vs intraday for any new variant and pre-register the overnight sizing rule on IS only.
* **In-sample:** IS walk-forward by calendar year; **OOS:** new data only.

### H4 — Expiry-day risk management
* **Reason:** capital stops cut OOS max drawdown (−373k → −266k) and the acted-cycle worst case (−79.7k → −24.7k), but cost ₹117k net.
* **Evidence:** `PLUGIN_EFFECTIVENESS_REPORT.md`.
* **Hypothesis:** the stop's cost is concentrated in cycles where an intraday adverse move later reverses; a stop that acts only on *gap-confirmed* breaches might preserve most of the tail benefit. Untested.
* **Required data:** none new; tick-level data would sharpen it.
* **Experiment:** pre-register stop variants on IS with a drawdown objective, not a P&L objective.

### H5 — Premium/realised cushion as the explanatory variable
* **Reason:** net per cycle = qty × (premium − |move|) − friction, exactly.
* **Evidence:** `MARKET_REGIME_ANALYSIS.md` §1–2 (ratio 1.38 IS → 1.08 clean NIFTY; 2.28 exposed).
* **Hypothesis:** the edge exists only when premium/E[|move|] is high; the premium already prices volatility clustering (corr 0.47 with |move|) so a *premium-relative* signal is more promising than a raw-volatility one.
* **Required data:** a forecast of E[|move|] built from past data only (e.g. trailing realised range) — a **pre-registered** forecast, not fit to P&L.
* **Experiment:** test whether (premium − forecast) predicts net, with a permutation null, on IS then on new data. Report the null result if none.

### H6 — Wing selection and purpose (ATM selection / adaptive wings)
* **Reason:** wings 2–4× farther than any observed move; 0/154 NIFTY in-the-money; ₹83k IS net cost.
* **Evidence:** `POSITION_AND_LEG_ATTRIBUTION.md` §2.
* **Hypothesis A:** wings exist for margin, not P&L protection — this needs SPAN data to test.
* **Hypothesis B:** wing distance scaled to the entry premium (a volatility-aware width) would pay off in the tail while costing less than the current wings at similar protection. Untested; the current sample contains no tail event of that size.
* **Required data:** margin/SPAN figures or the broker's margin statements.
* **Experiment:** compare structures by *worst-case loss per unit margin* and cost, on IS stress scenarios plus historical longer samples (pre-2023, large-move events).
* **Downside:** a 275-cycle sample cannot validate a tail hedge.

### H7 — Sizing / exposure normalisation
* **Reason:** 3 lots/leg fixed while NIFTY lot size changed 50→25→75→65; units at entry therefore vary.
* **Evidence:** `exposure_summary.json` (avg units 681 NIFTY), `SHARPE_METHODOLOGY_AUDIT.md` S-3.
* **Hypothesis:** the Sharpe comparison across years is distorted by changing rupee notional.
* **Experiment:** re-express each cycle's P&L per unit of notional or per constant-notional lot count; compare Sharpe. Diagnostic only.

### H8 — Conditional cuts and re-entry logic
* **Reason:** frozen cut/re-entry is −₹151k vs plain hold in OOS and does not reduce the worst cycle.
* **Evidence:** `PLUGIN_EFFECTIVENESS_REPORT.md`.
* **Hypothesis:** cuts should be evaluated on D-1 and on *carried* risk, not on D0 gaps; re-entry after a gap restores exposure at inflated premium and may be the more valuable half (+₹259k vs cut-only OOS).
* **Experiment:** only after H3: pre-register one structural change, measure on IS walk-forward.
* **Downside:** high multiple-testing risk — 18 cut configs already searched.

### H9 — Regime-dependent construction
* **Reason/Evidence:** none: no decision-time feature predicted P&L (`MARKET_REGIME_ANALYSIS.md` §3).
* **Hypothesis:** an economically motivated regime (event days, expiry-week-of-month, gap days) might matter; would require new data.
* **Experiment:** pre-register ≤ 3 regimes with an economic rationale before looking; test on new data with a permutation null. **Do not** mine terciles again.

## Data to acquire before any of the above
1. Exchange settlement/closing values for every expiry. 2. Live-fill vs bar comparison (already in the repo). 3. Margin statements. 4. Longer history (pre-2023 NIFTY) as the first fresh independent sample. 5. Forward paper-trading log from 2026-11-18, frozen baseline unchanged.
