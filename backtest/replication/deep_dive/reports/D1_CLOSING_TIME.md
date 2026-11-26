# D-1 closing time: exchange rules, what Algo 8 actually does, and a data bug in our index after 15:15

*Scripts: `src/bl_bt3s_data.py`, `bl_bt3u_data.py`, `bl_cas_rescore.py` → `outputs/cas/`; caches `outputs/bt3f`, `bt3s`, `bt3u` (git-ignored). Rule sources are listed at the end. They are secondary sources: the SEBI and NSE circulars themselves were not fetched.*

## Result first
1. **The closing auction is not paused.**
   * **Since 3 Aug 2026:** F&O stocks stop continuous trading at **15:15**, then go through the closing auction from 15:15 to 15:35. **Index options (NIFTY, SENSEX) trade until 15:40.**
   * **Next change, 7 Dec 2026 (SEBI circular of 15 Oct 2026, as reported):**
     * the auction moves to 15:30–15:40;
     * derivatives trade until 15:45;
     * expiring index contracts stop at 15:30 on expiry day;
     * expiry settlement goes back to the 15:00–15:30 VWAP.
2. **Algo 8 follows the new rules.**

   | Day | Era | Real Algo 8 last activity |
   |---|---|---|
   | D-1 | after the auction | 15:30–15:39 (orders on options) |
   | D-1 | before the auction | up to 15:29 |
   | D0 | after the auction | **15:14**: about 2,500 lots cleared, just before continuous trading stops at 15:15 |
   | D0 | before the auction | 15:15–15:19 (peak 15:19), with a tail to 15:26 |

3. **Data bug (now fixed): after the auction, our index between 15:15 and 15:29 is not a tradeable price.**
   * It is frozen from 15:15 to 15:19.
   * From 15:20 to 15:28 it shows **indicative auction values**: NIFTY 22,336–22,669 inside one minute, SENSEX 72,096–74,793.
   * It shows the official close from 15:29.
   * Over 15:15–15:29 the median range is 261 NIFTY / 418 SENSEX points. The option-implied index moves 37 / 173 points over 15:15–15:39.
   * **Our D-1 rules (ladder extremes, ATM strike, Fix A's breakouts) were reading these fake swings.**
4. **The real system watches a live underlying after 15:15.** With the index frozen at 15:15, the simulator sells nothing after 15:15, but the real system sells 8.2 lots per cycle. Futures and the option-implied index both fit about equally; the data cannot tell them apart.
5. **The Fix A stop flip was an artefact of the bad index.** On a clean underlying, SENSEX 8 Oct does not flip. Fix A becomes P&L-neutral, but it still lowers timing precision: not adopted.
6. **The late-timing gap remains.** On every clean underlying the simulator makes 1–3 late lots per cycle after 15:15, against 8.2 real; recall is about 0.2.

## 1. Re-score: same rules, different underlying after 15:15 (19 complete post-auction cycles)
| variant | underlying after 15:15 | sim gross (₹) | stops agree | 15:00–15:40 precision / recall | **15:15–15:40 precision / recall** | late lots after 15:15 (sim / real) |
|---|---|---|---|---|---|---|
| X | published index (indicative) | −26,767 | 12 | 0.62 / 0.46 | 0.41 / 0.24 | 1.7 / 8.2 |
| XF | frozen at 15:15 | −26,841 | 12 | 0.76 / 0.35 | **0 / 0** | 0 / 8.2 |
| XS | option-implied (put-call parity) | −23,308 | 12 | 0.70 / 0.45 | **0.57 / 0.22** | 1.1 / 8.2 |
| XU | index future minus basis | −23,717 | 12 | 0.64 / 0.44 | 0.42 / 0.20 | 1.3 / 8.2 |
| XSA | XS + Fix A | −19,971 | 12 | 0.65 / 0.46 | 0.48 / 0.24 | 2.3 / 8.2 |
| XUA | XU + Fix A | −20,898 | 12 | 0.58 / 0.46 | 0.36 / 0.26 | 3.2 / 8.2 |

*Real sim-vs-real P&L error is about ₹1.32 lakh per cycle for every variant. Real total ₹25,968 per cycle. Late lots exclude the 16 Oct call-ratio cycle.*

Changes vs X (paired cycle bootstrap, 15:15–15:40 window):

| variant | precision change | recall change | P&L mean / median | stop flips |
|---|---|---|---|---|
| XF | **−0.41 [−0.53, −0.26]** | **−0.24 [−0.36, −0.13]** | −₹74 / +₹391 | 0 |
| XS | +0.17 [−0.04, +0.34] | −0.02 [−0.16, +0.15] | +₹3,459 / +₹1,109 | 0 |
| XU | +0.01 [−0.21, +0.22] | −0.04 [−0.18, +0.13] | +₹3,050 / +₹1,445 | 0 |

* **Frozen is falsified:** recall collapses. The real system keeps acting on market moves after 15:15.
* **Option-implied vs futures:** both are within noise of each other and of X on recall. The option-implied index has the better precision, but not significantly.
* **Recommended post-auction underlying for fidelity work: the option-implied index** (`BT3_DIR=outputs/bt3s`). Reasons:
  * the published indicative index is not tradeable information, so a simulator must not trade on it;
  * the frozen index is ruled out by the data;
  * the option-implied index is built from the instruments actually traded, with no fitted parameter.
* **Limits:**
  * The option-implied index is aligned to the index level with the 15:00–15:14 basis (day-to-day spread about 20 NIFTY points). It uses close-only bars, so it invents no range.
  * Futures are aligned the same way (median basis 66 NIFTY / 326 SENSEX points).
  * Neither choice is a fitted parameter, but both are measurement choices.

## 2. Fix A on a clean underlying
* **SENSEX 8 Oct:**
  * on the indicative index, Fix A sold 15 late lots and hit the cycle stop (−₹7.09 lakh);
  * on the option-implied index it sells 5 (real 3) and **does not stop** (XS ₹5.96 lakh, XSA ₹6.03 lakh, real ₹3.29 lakh).
* **XSA vs XS:**
  * precision −0.089 [−0.167, +0.006] (15:15 window) and −0.048 [−0.076, −0.013] (15:00 window);
  * recall +0.019 [0.000, +0.064];
  * P&L +₹3,337 mean, ₹0 median, 0 flips.
* **Verdict:** Fix A is no longer harmful, but it adds mostly unmatched sales. Precision falls and recall gains are marginal. **Not adopted.** The decision reason in `EXTENDED_SESSION_FIXA.md` is corrected: that stop flip came from fake auction prices, not from Fix A's logic.

## 3. Consequences
* **The pre-paper battery is unaffected.** It ran on 15:29 data where the post-auction ladder could read indicative values. Only 19–29 of its 276 cycles are post-auction; on them the clean underlying changes P&L by about +₹3k per cycle with no flips. The NO-GO verdict stands. The flawed post-auction slice is now documented.
* **D0 clearance timing before the auction:** the simulator clears at 15:14 in every era, but the real system cleared at 15:15–15:19 before the auction. That is 1–5 minutes later in high-gamma minutes. **Not changed here; next test** (teacher-forced D0 from the real book, clearance at the observed minute).
* **New regime from 7 Dec 2026:** auction 15:30–15:40, derivatives until 15:45, expiring contracts stop at 15:30 on expiry day, settlement back to the 15:00–15:30 VWAP. Cycles after 7 Dec are a **third regime**. The hold-out must be reported separately by regime, and the simulator needs the new session ends before it can score them.

## 4. Still unknown
* What triggers the real post-15:15 sales: 8.2 lots per cycle, recall about 0.2 on any underlying. No new timing parameter was added.
* Whether the real system's live underlying is futures or option-implied: the data cannot tell them apart.
* SENSEX / BSE auction rules: the sources cover NSE; BSE was not confirmed.
* Which settlement method actually applies between 3 Aug and 6 Dec: sources conflict between auction-close and VWAP. Our check against the NIFTY official close is in `EXTENDED_SESSION_FIXA.md`.

## Sources (secondary; not the SEBI/NSE circulars)
* Outlook Business, 1 Aug 2026: https://www.outlookbusiness.com/amp/story/markets/sebi-closing-auction-session-new-stock-market-timings-from-august-3
* Tick2Trade, 16 Oct 2026 (cites SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/23843/2026 of 15 Oct 2026): https://www.tick2trade.com/blogs/sebi-revises-nse-closing-auction-session-rules
* ETV Bharat / IANS, 7 Nov 2026: https://www.etvbharat.com/en/business/nse-to-overhaul-closing-auction-session-extend-derivatives-trading-hours-from-dec-7-enn26110704969
