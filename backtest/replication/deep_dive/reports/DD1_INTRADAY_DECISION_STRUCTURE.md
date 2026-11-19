# DD-1 — Intraday decision structure of Algo 8 (35 live cycles)

**Purpose.** Look under the "top layer": find the *structure* of the mid-session activity (what drives what, and when) using the microsecond decision stamps embedded in order tags and the fill clock. **IN-SAMPLE, descriptive, read-only.** Nothing here is a recovered trading rule unless labelled so; the 35 cycles are not a holdout. Code `src/dd_*.py`, tables `outputs/dd_*.csv`, tests `tests/test_dd1.py`, report generator `src/make_dd_report.py` (all numbers below are computed by it).

## 1. Result first
| # | Finding | Evidence | Status |
|---|---|---|---|
| F1 | The hedge module (`h_`) is a **reactive per-right mirror of body lot changes**, lagging the body fill by ≈ 3.7 s. 12,812 of 39,874 orders (32.1 %) are therefore largely determined by body activity. | 92.6 % of 12,490 body bursts get a wing response within 10 s; wing Δlots = body Δlots in 92.0 % of responses; wing level equals body-short level after the response in 66.8 % (the level is not always balanced because bursts start from an existing gap: median |W−S| before a burst 0 lots) | **STRONGLY SUPPORTED** |
| F2 | **D-1 body exits are minute-clocked; D0 body exits are not.** | buy-backs of a recorded short filled in second :00 — D-1 47.6 %, D0 10.4 %; within :00–:02 D-1 58.4 %, D0 17.4 %; Rayleigh concentration of second-of-minute D-1 0.63 vs D0 0.18; the :00 share is similar for the stop-like 1.55–1.8× class (49.9 %) and all D-1 exits | **CONFIRMED OBSERVATION** (timing). *Mechanism is inferred, not observed:* D-1 exit logic evaluates once per completed minute; D0 exit logic runs on a different loop |
| F3 | **Slot sizing is not premium-budgeted and not book-state dependent.** | within-slot CV of lots 0.43 vs CV of lots×premium 0.77 (a premium budget would make the second *smaller*); slot-adjusted size vs premium / book shorts / 15-min move: |Spearman| 0.12 / 0.15 / 0.07; slot id explains 32.6 % of size variance | premium-budget and book-state hypotheses **REJECTED**; actual size driver **UNKNOWN** |
| F4 | **"Sell-and-re-centre" explains a minority of buy-backs.** | 37.3 % of 14,354 body buy-back lots are re-sold on the same right within 60 s (median delay 6 s; same strike in only 7.8 %); on D0 the new strike is nearer the previous completed spot than the old one in 45.1 % of 3,416 pairs (median distance 2.00 → 1.65 strike steps) | re-centring-to-ATM as the general buy-back explanation **REJECTED**; the 60-s pairing is a descriptive filter, not an identified roll rule |

## 2. What the tag stamps give us
Tagged orders (`h_`, `s_`, `v_`, `m_`; 13,621 orders) carry `DDHHMMSSffffff` (UTC; +5:30 = IST). Fill time is whole seconds. Fill second minus decoded decision stamp (positive = fill second later than the stamp): wings median -0.17 s (IQR -0.44–0.08), stop module 2.50 s (IQR -0.02–15.00). Sub-second values are within the fill-second quantisation and possible clock offset between the stamp and the fill log. Body (`num`) orders carry no stamp, so body decision times are known only to the second.

## 3. The hedge module (F1)
* Body bursts (orders ≤ 3 s apart on one right): **12,490**; wing response within 10 s: **92.6 %**.
* Responses to body sells (wings bought) 8,156; to body buy-backs (wings released) 3,406.
* Wing level equals body-short level after the response: sells 68.9 %, buy-backs 61.7 %.
* Latency (wing decision stamp minus nearest opposite-side body fill second): median 3.7 s, IQR 3.1–4.4 s — the hedge reacts to the *completed* body trade, not to the body decision.
* Non-responses: 928 bursts, of which D0 840 and D-1 88; 51 lie within 60 s of an `s_` (stop-module) order of the same cycle. These are the first thing to explain (liquidation, flatten and lump paths are candidates — **hypothesis, untested**).
* **For the engine:** the quantity rule (one wing lot per body short lot, released with it) is right; the wing should be a separate reactive process that follows body fills. The remaining open hedge problem is the wing **strike** only.

## 4. Exit timing (F2)
| day | price_ratio_class | n | at_second_0 | within_0_2 |
|---|---|---|---|---|
| D-1 | 0.5-1x | 222 | 52.3 % | 60.4 % |
| D-1 | 1-1.4x | 436 | 40.8 % | 55.3 % |
| D-1 | 1.4-1.55x | 221 | 51.1 % | 61.1 % |
| D-1 | 1.55-1.8x | 353 | 49.9 % | 59.8 % |
| D-1 | <0.5x | 17 | 29.4 % | 41.2 % |
| D-1 | >1.8x | 77 | 55.8 % | 61.0 % |
| D0 | 0.5-1x | 2186 | 10.4 % | 17.1 % |
| D0 | 1-1.4x | 1941 | 17.5 % | 26.1 % |
| D0 | 1.4-1.55x | 555 | 15.0 % | 23.2 % |
| D0 | 1.55-1.8x | 693 | 15.2 % | 20.1 % |
| D0 | <0.5x | 3666 | 6.1 % | 11.6 % |
| D0 | >1.8x | 1038 | 6.7 % | 17.8 % |

`price_ratio_class` = fill price ÷ average entry price of the recorded open short lots in that contract. D-1 exits of every class fill at the minute boundary far more often than chance (1/60 = 1.7 %); D0 exits do not. **Implication for modelling:** minute-bar evaluation is structurally suited to D-1 exits and structurally unsuited to D0 exits — consistent with the largest parity gap being D0 buy-backs.

## 5. Pre-registered next tests (not yet run — written before looking)
1. **D0 exits as reactions to own fills (H1):** time from the previous algo fill (any module, same underlying) to each D0 body buy-back clusters at a fixed delay (hedge-like) → event-driven chain; otherwise independent clock.
2. **Poll period (H2):** Rayleigh/period scan of D0 buy-back fill seconds over candidate periods 2–59 s with a phase-preserving circular-shift null; a significant period ⇒ polling loop.
3. **Inside-minute price path (H3):** for stop-like D0 exits compare the minute's high/low with 1.55–1.7 × entry; a tick-level trigger predicts crossing within the same minute.
4. **Sizing (H4):** cycle-level scale vs date / spot level / previous-cycle result. Observed so far: std of cycle-mean residual 0.31 vs 0.25 expected if independent across 14 slots (indicative only).
5. **What halts a body entry stream:** number of child orders per slot vs a fill-count target, time box or state condition.

## 6. Limits
In-sample; one ~4-month window; body fills at second resolution; no tick data; the LTP at decision time is available only through prices of fills; D0 exits that are re-sales are separated from genuine exits only by the 60-s pairing used in F4; burst/response definitions (3 s / 10 s) are fixed analysis choices, not recovered parameters.

## 7. Evidence labels used
CONFIRMED OBSERVATION · STRONGLY SUPPORTED · HYPOTHESIS · UNKNOWN · REJECTED (as in earlier reports in this programme).
