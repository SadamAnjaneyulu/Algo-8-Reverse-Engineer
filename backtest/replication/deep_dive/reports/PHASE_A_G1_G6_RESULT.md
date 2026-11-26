# Phase A investigations G1-G6: results

*Plan: [`PHASE_A_G1_G6_PLAN.md`](PHASE_A_G1_G6_PLAN.md) (written before any run; two addenda record the follow-up G1b and the post-run corrections). Existing data only, development cycles, decisions not P&L, frozen objects untouched. **These are historical reproductions on the development cycles, not independent validation.***

## Result first
| ID | Question | Result | Pre-set rule | Evidence |
|---|---|---|---|---|
| **G1** | Are the 8 CE+PE bursts at/after 15:15 the breakout rule with its gate extended? | **0 of 8** matched (null mean 0.54); the extended rule matches 0 of 42 burst orders | not supported | Observed |
| **G1b** (follow-up, pre-registered before it ran) | Are they tied to the **close of the 15:00-15:30 candle** outside the previous two candles' channel? | **7 of 8** burst cycles meet the condition; Fisher one-sided p = 0.0033, odds ratio 22; but the condition holds in 12 of 29 cycles (precision 7/12) | **supported** | Weak-moderate (hypothesis formed after seeing the burst times; one test; 8 events) |
| **G2** | How big is the true residual of the 176 late open-short orders? | Unexplained: **43 (24%)** at +/-1 min, 35 (20%) at +/-2, 26 (15%) at +/-5. Ladder explains 113, the extended breakout adds at most 1-2, the closing pairs (G1b) 31. 34 of the 43 are post-auction; 34 sit in 15:20-15:29; one cycle (NIFTY 24 Aug) holds 11 | accounting, no rule | Observed |
| **G3** | Is the weak exact-strike agreement a data-lag artefact? | **No.** Median drift between the decision price and the minute close is 2.5%; the median gap between adjacent strikes is 21%; 92% of orders are low-lag. Exact agreement is 0.44-0.47 in the low-lag subset | both eras: *inconclusive*; post-auction: *rule incomplete* | Observed |
| **G4** | What are the body-module long closes and do the two exceptions belong to them? | 124 of 134 `num` long closes (93%) are opening-wing contracts; 84% are within 10 s of a buy-back. SENSEX 9 Sep (2 orders): **in class**. NIFTY 3 Aug (5 lots, 15:29:05-07): **not**; it is a body-module sale of a contract the lump (`v_`) bought at 15:06:47 | **not met** (one exception unexplained) | Observed |
| **G5** | Pin the cycle-stop constant with decision prices | 7 non-gap stops at decision prices: **-Rs 1.36 to -1.53 lakh, median -1.43 lakh, 7/7 within +/-10%** (bar marks: spread 0.45-0.58, inconsistent); non-stop cycles' worst minute-close MTM -Rs 1.17 lakh stays above the smallest stop | **consistent with a single MTM constant** | Observed; latency reading Inferred |
| **G6** | Do D0 residual buy-back classes show a price threshold in decision-price terms? | **No.** IQR of the decision ratio is 1.6-2.7x the known stop class (0.30); medians 0.99-1.10 vs 1.64; carried residual (643 lots) IQR 0.83. The AUC gate is **not testable** (no decision price for non-events) | no candidate | Observed |

**Register status of G1b (decided by the user 2026-11-25): Candidate, exploratory; excluded from the baseline reconstruction; configurable candidate only.** The word "supported" in the table above refers only to the pre-set success rule of that single test. The threshold is not adjusted to capture the one missed cycle.

## What each result changes in the reconstruction
* **Late D-1 sales (D1-14).** The unexplained part is now **24% of late open-short orders** (43 of 176), not "about a third" (that was event-level and pre-G1b). The CE+PE closing bursts are not a gate extension of the breakout rule (G1) but a **candle-end close** condition (G1b); this is a candidate rule, with its caveats: 8 events, post-hoc origin, precision 58%. The condition did not hold for one burst (NIFTY 24 Aug missed the channel top by 1.6 points).
* **Strike selection (D1-08).** G3 and a reconciliation below.
* **Body-module closes (D1-11).** The two "exceptions" split: SENSEX 9 Sep belongs to the opening-wing class; **NIFTY 3 Aug does not** and stays unexplained. Ten body-module long closes in 3 cycles are cross-module (the contract was bought by another module): NIFTY 3 Aug (5), NIFTY 31 Aug (33 lots at 14:46:29-31: the stop liquidation), SENSEX 21 Oct (1).
* **Cycle stop (D1-15).** The two earlier ranges are reconciled: the **threshold** on live prices is about Rs 1.2-1.36 lakh (non-stop cycles never go below -1.17 lakh on minute-close marks; the smallest stop is -1.36 lakh at decision prices), and the MTM at the **order second** is larger (-1.36 to -1.53 lakh, median -1.43) because of the 1-20 s latency (Inferred). Exact constant and timing stay open without ticks. The earlier rebuild used 1.45 lakh for the same reason; that choice was not the cause of its failure.
* **D0 residual buy-backs (D0-04).** They have no price structure in decision-price terms; the three residual classes stay **unresolved** (data-limited: the trigger, if any, is not the lot's own premium).

## Correction recorded: the 0.31 exact-strike figure
`FORWARD_TEST.md` (hash-frozen, not edited) reports exact strike agreement of **0.31** for the engine's premium-matched rule in the last 25 minutes, and concludes the earlier 0.54 "does not carry over". The development dry run built its last-sale reference from sales in **earlier minutes only** (`jj < j`); the engine rule and the live recorder use the latest sale **including earlier ones in the same minute**, which matters for one-lot drips. With the live definition, on the same 98 ladder-matched post-auction orders the exact agreement is **0.54** (0.46 on all 148; 0.30 on the 50 ladder-unmatched). So 0.54 **does** carry over for ladder-matched orders. The forward evaluation will use the live definition, so the live comparison is unaffected; the development baseline in `FORWARD_TEST.md` is understated and should be read as 0.54.

## Limits
Same development cycles throughout; G1/G1b rest on 8 bursts, G5 on 7 stops, G4 on 134 orders in 30 cycles. G1b was formed after G1 and after looking at the burst times; its p-value is for that single pre-registered test, not for the search that produced the idea. G3's comparison between low-lag and high-lag orders has only 12-15 high-lag orders. Nothing here changes the frozen late-sale rule or score, nor the NO-GO.

## Files
`src/bl_pa_g1.py` (also the shared loader), `bl_pa_g1b.py`, `bl_pa_g2.py`, `bl_pa_g3.py`, `bl_pa_g4.py`, `bl_pa_g5.py`, `bl_pa_g6.py`; `tests/test_phase_a_g.py`; outputs in `outputs/phaseA/`.
